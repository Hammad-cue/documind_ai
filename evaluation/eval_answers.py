"""
Evaluation 5 — answer quality on CUAD (the "ask a question, get a cited answer" path).

Contracts are loaded into the evaluation organization; for each one we ask clause questions through the real
answer engine (hybrid retrieval + LLM with citations), restricted to that contract:

  answerable questions   (the lawyers marked an answer):
      citation hit   — at least one passage the answer cites contains the lawyers' span
      correct        — an LLM judge, given the lawyers' span, says the answer is right
  unanswerable questions (the clause is absent from the contract):
      abstained      — the answer says the information is not in the document instead of inventing one

Questions whose LLM call failed (rate limit / outage) are recorded as errors and left out of every rate.

    python -m evaluation.eval_answers --n 15
    python -m evaluation.eval_answers --retry-failed     # re-ask only the failed questions of the last run
"""
import argparse
import json
import random
import re
import time

from evaluation import cuad  # noqa: I001  (sets up Django first)
from evaluation.common import RESULTS, save
from evaluation.eval_retrieval import QUESTIONS, contains_answer, ingest

from django.contrib.auth.models import User  # noqa: E402

from accounts.models import Membership, Organization, Role  # noqa: E402
from ai import llm  # noqa: E402
from assistant.engine import run_knowledge  # noqa: E402
from documents.models import Chunk, Document  # noqa: E402

ABSTAIN = re.compile(r"(not (?:mention|contain|include|specif|state|address|provide|found|present)|no (?:mention|information|provision|clause|reference)|"
                     r"does(?:n't| not) (?:say|mention|contain|include|specify|address)|could(?:n't| not) find|isn't (?:mentioned|stated)|silent)", re.I)
LLM_DOWN = 'The language model is unavailable'


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


def ask(user, doc, contract, category, answerable, pause):
    """Ask one question through the answer engine and grade it. Returns a result row."""
    q = QUESTIONS[category]
    base = {'contract': contract['title'], 'category': category, 'answerable': answerable}
    time.sleep(pause)
    try:
        answer, sources, _ = run_knowledge(user, {'keywords': q}, q, [doc.id])
    except Exception as exc:
        return {**base, 'error': str(exc)[:200]}
    if answer.startswith(LLM_DOWN):   # the engine degrades to "passages only" instead of raising
        return {**base, 'error': answer[:200]}
    cited = {int(n) for n in re.findall(r'\[(\d{1,2})\]', answer)}
    cited_chunks = Chunk.objects.filter(id__in=[s['chunk_id'] for s in sources if s['id'] in cited])
    row = {**base, 'answer': answer[:600], 'cited': len(cited), 'abstained': bool(ABSTAIN.search(answer))}
    if answerable:
        spans = contract['gold'][category]
        row['citation_hit'] = any(contains_answer(ch.text, spans) for ch in cited_chunks)
        time.sleep(pause)
        try:
            row['correct'], row['judge_reason'] = judge(q, answer, spans)
        except llm.LLMError as exc:
            row['correct'], row['judge_reason'] = None, f'judge failed: {exc}'[:200]
    return row


def failed(row):
    return 'error' in row or LLM_DOWN in row.get('answer', '') or str(row.get('judge_reason', '')).startswith('judge failed')


def summarize(rows, n):
    ok = [r for r in rows if 'error' not in r and LLM_DOWN not in r.get('answer', '')]
    ans = [r for r in ok if r.get('answerable')]
    judged = [r for r in ans if r.get('correct') is not None]
    unans = [r for r in ok if r.get('answerable') is False]
    rate = lambda xs, key: round(sum(bool(x.get(key)) for x in xs) / len(xs), 3) if xs else None
    return {
        'contracts': n, 'model': llm.settings.LLM_MODEL,
        'answerable_questions': len(ans), 'unanswerable_questions': len(unans), 'judged_questions': len(judged),
        'errors': len(rows) - len(ok),
        'citation_hit_rate': rate(ans, 'citation_hit'),
        'answer_correct_rate': rate(judged, 'correct'),
        'answers_with_citations': rate(ans, 'cited'),
        'abstention_rate_when_absent': rate(unans, 'abstained'),
        'wrongly_abstained_when_present': rate(ans, 'abstained'),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--n', type=int, default=15)
    ap.add_argument('--per-contract', type=int, default=3, help='answerable questions per contract')
    ap.add_argument('--seed', type=int, default=21)
    ap.add_argument('--pause', type=float, default=6.0)
    ap.add_argument('--retry-failed', action='store_true', help='re-ask only the failed questions of the saved run')
    args = ap.parse_args()
    rng = random.Random(args.seed)

    org, _ = Organization.objects.get_or_create(slug='evaluation-cuad', defaults={'name': 'Evaluation (CUAD)'})
    Document.objects.filter(organization=org).delete()
    user, _ = User.objects.get_or_create(username='eval_cuad_bot')
    Membership.objects.update_or_create(user=user, defaults={'organization': org, 'role': Role.ADMIN})

    if args.retry_failed:
        saved = json.loads((RESULTS / 'answers_cuad.json').read_text(encoding='utf-8'))
        rows, n = saved['rows'], saved['summary']['contracts']
        by_title = {c['title']: c for c in cuad.sample(n, args.seed)}
        todo = sorted({r['contract'] for r in rows if failed(r)})
        print(f'{sum(failed(r) for r in rows)} failed questions in {len(todo)} contracts', flush=True)
        try:
            for i, title in enumerate(todo, 1):
                c = by_title[title]
                doc, _ = ingest(org, user, c, 'structure')
                for k, r in enumerate(rows):
                    if r['contract'] == title and failed(r):
                        answerable = r.get('answerable', bool(c['gold'].get(r['category'])))
                        rows[k] = ask(user, doc, c, r['category'], answerable, args.pause)
                print(f'[{i}/{len(todo)}] {title[:70]}', flush=True)
        finally:
            Document.objects.filter(organization=org).delete()
    else:
        n, rows = args.n, []
        try:
            for i, c in enumerate(cuad.sample(args.n, args.seed), 1):
                doc, _ = ingest(org, user, c, 'structure')
                present = [k for k in QUESTIONS if c['gold'].get(k)]
                absent = [k for k in QUESTIONS if not c['gold'].get(k)]
                asks = [(k, True) for k in rng.sample(present, min(args.per_contract, len(present)))]
                asks += [(k, False) for k in rng.sample(absent, min(1, len(absent)))]
                for category, answerable in asks:
                    rows.append(ask(user, doc, c, category, answerable, args.pause))
                print(f'[{i}/{args.n}] {c["title"][:70]}', flush=True)
        finally:
            Document.objects.filter(organization=org).delete()

    summary = summarize(rows, n)
    print(summary)
    save('answers_cuad', {'summary': summary, 'rows': rows})


if __name__ == '__main__':
    main()
