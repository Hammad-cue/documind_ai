"""
Evaluation 5 — answer quality on CUAD (the "ask a question, get a cited answer" path).

Contracts are loaded into the evaluation organization; for each one we ask clause questions through the real
answer engine (hybrid retrieval + LLM with citations), restricted to that contract:

  answerable questions   (the lawyers marked an answer):
      citation hit   — at least one passage the answer cites contains the lawyers' span
      correct        — an LLM judge, given the lawyers' span, says the answer is right
  unanswerable questions (the clause is absent from the contract):
      abstained      — the answer says the information is not in the document instead of inventing one

    python -m evaluation.eval_answers --n 15
"""
import argparse
import random
import re
import time

from evaluation import cuad  # noqa: I001  (sets up Django first)
from evaluation.common import save
from evaluation.eval_retrieval import QUESTIONS, contains_answer, ingest

from django.contrib.auth.models import User  # noqa: E402

from accounts.models import Membership, Organization, Role  # noqa: E402
from ai import llm  # noqa: E402
from assistant.engine import run_knowledge  # noqa: E402
from documents.models import Chunk, Document  # noqa: E402

ABSTAIN = re.compile(r"(not (?:mention|contain|include|specif|state|address|provide|found|present)|no (?:mention|information|provision|clause|reference)|"
                     r"does(?:n't| not) (?:say|mention|contain|include|specify|address)|could(?:n't| not) find|isn't (?:mentioned|stated)|silent)", re.I)


def judge(question, answer, spans):
    prompt = f"""You grade answers about a contract. The lawyers' annotated answer is:
\"\"\"{' ... '.join(s[:600] for s in spans[:3])}\"\"\"

Question: {question}
Answer to grade: \"\"\"{answer[:2000]}\"\"\"

Is the answer consistent with the annotation and does it actually answer the question? Minor omissions are fine;
contradictions or claiming the information is missing are not.
Return JSON {{"correct": true or false, "reason": "one short sentence"}}"""
    out = llm.chat_json([{'role': 'user', 'content': prompt}], max_tokens=300, temperature=0)
    return bool(out.get('correct')), str(out.get('reason', ''))[:200]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--n', type=int, default=15)
    ap.add_argument('--per-contract', type=int, default=3, help='answerable questions per contract')
    ap.add_argument('--seed', type=int, default=21)
    ap.add_argument('--pause', type=float, default=6.0)
    args = ap.parse_args()
    rng = random.Random(args.seed)

    org, _ = Organization.objects.get_or_create(slug='evaluation-cuad', defaults={'name': 'Evaluation (CUAD)'})
    Document.objects.filter(organization=org).delete()
    user, _ = User.objects.get_or_create(username='eval_cuad_bot')
    Membership.objects.update_or_create(user=user, defaults={'organization': org, 'role': Role.ADMIN})

    rows = []
    try:
        for i, c in enumerate(cuad.sample(args.n, args.seed), 1):
            doc, _ = ingest(org, user, c, 'structure')
            present = [k for k in QUESTIONS if c['gold'].get(k)]
            absent = [k for k in QUESTIONS if not c['gold'].get(k)]
            asks = [(k, True) for k in rng.sample(present, min(args.per_contract, len(present)))]
            asks += [(k, False) for k in rng.sample(absent, min(1, len(absent)))]
            for category, answerable in asks:
                q = QUESTIONS[category]
                time.sleep(args.pause)
                try:
                    answer, sources, _ = run_knowledge(user, {'keywords': q}, q, [doc.id])
                except Exception as exc:
                    rows.append({'contract': c['title'], 'category': category, 'error': str(exc)[:200]})
                    continue
                cited = {int(n) for n in re.findall(r'\[(\d{1,2})\]', answer)}
                cited_chunks = Chunk.objects.filter(id__in=[s['chunk_id'] for s in sources if s['id'] in cited])
                row = {'contract': c['title'], 'category': category, 'answerable': answerable, 'answer': answer[:600],
                       'cited': len(cited), 'abstained': bool(ABSTAIN.search(answer))}
                if answerable:
                    spans = c['gold'][category]
                    row['citation_hit'] = any(contains_answer(ch.text, spans) for ch in cited_chunks)
                    time.sleep(args.pause)
                    try:
                        row['correct'], row['judge_reason'] = judge(q, answer, spans)
                    except llm.LLMError as exc:
                        row['correct'], row['judge_reason'] = None, f'judge failed: {exc}'[:200]
                rows.append(row)
            print(f'[{i}/{args.n}] {c["title"][:70]}')
    finally:
        Document.objects.filter(organization=org).delete()

    ans = [r for r in rows if r.get('answerable') and 'error' not in r]
    judged = [r for r in ans if r.get('correct') is not None]
    unans = [r for r in rows if r.get('answerable') is False]
    rate = lambda xs, key: round(sum(bool(x.get(key)) for x in xs) / len(xs), 3) if xs else None
    summary = {
        'contracts': args.n, 'model': llm.settings.LLM_MODEL,
        'answerable_questions': len(ans), 'unanswerable_questions': len(unans),
        'errors': sum('error' in r for r in rows),
        'citation_hit_rate': rate(ans, 'citation_hit'),
        'answer_correct_rate': rate(judged, 'correct'),
        'answers_with_citations': rate(ans, 'cited'),
        'abstention_rate_when_absent': rate(unans, 'abstained'),
        'wrongly_abstained_when_present': rate(ans, 'abstained'),
    }
    print(summary)
    save('answers_cuad', {'summary': summary, 'rows': rows})


if __name__ == '__main__':
    main()
