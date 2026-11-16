"""
Evaluation 2 — retrieval ablation on CUAD (no LLM involved).

Contracts are loaded into a throw-away "Evaluation" organization twice:
  - structure-aware chunks (this system: one chunk per clause/section, page-aware)
  - fixed 1000-character windows with 200 overlap (how DocuMind v1 split text)
Then, for every contract × clause question whose answer the lawyers marked, we search inside that contract
with three retrieval modes (dense embeddings, keyword full-text, hybrid RRF) and record where the first chunk
containing the lawyers' span appears.  Metrics: Hit@1, Hit@3, Hit@5, MRR@10.

    python -m evaluation.eval_retrieval --n 40
"""
import argparse
import time

from evaluation import cuad  # noqa: I001  (sets up Django before any model import)
from evaluation.common import overlap, save

from django.contrib.auth.models import User  # noqa: E402
from django.db import connection  # noqa: E402

from accounts.models import Membership, Organization, Role  # noqa: E402
from ai.embeddings import embed_texts
from assistant.retrieval import hybrid_search
from documents.models import Chunk, Document, DocumentVersion
from documents.pipeline.chunking import chunk_pages

QUESTIONS = {
    'Governing Law': 'Which law governs this agreement?',
    'Termination For Convenience': 'Can a party terminate the agreement without cause or for convenience?',
    'Non-Compete': 'Is there a restriction on competing with the other party?',
    'Exclusivity': 'Is this an exclusive arrangement?',
    'Cap On Liability': 'Is liability limited or capped to an amount?',
    'Anti-Assignment': 'Can the agreement be assigned or transferred to someone else?',
    'Audit Rights': 'Does a party have the right to audit books and records?',
    'Insurance': 'What insurance must a party maintain?',
    'Renewal Term': 'Does the agreement renew automatically after the initial term?',
    'Notice Period To Terminate Renewal': 'How much notice is required to prevent renewal?',
    'Expiration Date': 'When does the agreement expire or end?',
    'License Grant': 'What license is granted under the agreement?',
    'Warranty Duration': 'How long does the warranty last?',
    'Change Of Control': 'What happens if a party undergoes a change of control or merger?',
    'Post-Termination Services': 'What obligations continue after the agreement ends?',
    'Minimum Commitment': 'Is there a minimum purchase or order commitment?',
}
MODES = ['dense', 'sparse', 'hybrid']


def fixed_chunks(pages, size=1000, overlap_chars=200):
    """DocuMind v1 behaviour: cut every 1000 characters regardless of structure."""
    text, spans, pos = '', [], 0
    for n, t in pages:
        spans.append((pos, n))
        text += t
        pos = len(text)
    page_at = lambda off: max((p for s, p in spans if s <= off), default=1)
    out, start = [], 0
    while start < len(text):
        piece = text[start:start + size]
        out.append({'text': piece, 'section': '', 'heading': '', 'page_start': page_at(start), 'page_end': page_at(start + len(piece) - 1)})
        start += size - overlap_chars
    return out


def ingest(org, user, contract, strategy):
    pages = cuad.pages(contract['text'])
    doc = Document.objects.create(organization=org, title=contract['title'][:255], kind=Document.Kind.RECORD,
                                  uploaded_by=user, doc_type='CUAD contract')
    v = DocumentVersion.objects.create(document=doc, number=1, file='evaluation/none.txt', original_filename='cuad.txt',
                                       file_type='PDF', status=DocumentVersion.Status.READY, page_count=len(pages), uploaded_by=user)
    if strategy == 'structure':
        pieces = [{'text': c.text, 'section': c.section_path, 'heading': c.heading, 'page_start': c.page_start, 'page_end': c.page_end}
                  for c in chunk_pages(pages)]
    else:
        pieces = fixed_chunks(pages)
    vectors = embed_texts([f"{p['section']}\n{p['text']}" if p['section'] else p['text'] for p in pieces])
    Chunk.objects.bulk_create([Chunk(version=v, sequence=i + 1, section_path=p['section'][:500], heading=p['heading'][:300],
                                     text=p['text'], page_start=p['page_start'], page_end=p['page_end'], embedding=vec)
                               for i, (p, vec) in enumerate(zip(pieces, vectors))])
    with connection.cursor() as cur:
        cur.execute("UPDATE documents_chunk SET search_vector = setweight(to_tsvector('english', coalesce(section_path, '')), 'A') || "
                    "setweight(to_tsvector('english', text), 'B') WHERE version_id = %s", [v.pk])
    doc.current_version = v
    doc.save(update_fields=['current_version'])
    return doc, len(pieces)


def contains_answer(chunk_text, spans):
    # a span counts as found if most of its words are in the chunk (long spans may straddle two chunks)
    return any(overlap(s, chunk_text) >= 0.6 for s in spans)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--n', type=int, default=40)
    ap.add_argument('--seed', type=int, default=11)
    ap.add_argument('--keep', action='store_true', help='keep the evaluation organization afterwards')
    args = ap.parse_args()

    contracts = cuad.sample(args.n, args.seed)
    org, _ = Organization.objects.get_or_create(slug='evaluation-cuad', defaults={'name': 'Evaluation (CUAD)'})
    Document.objects.filter(organization=org).delete()
    user, _ = User.objects.get_or_create(username='eval_cuad_bot', defaults={'is_active': True})
    user.set_unusable_password()
    user.save()
    Membership.objects.update_or_create(user=user, defaults={'organization': org, 'role': Role.ADMIN})

    results = {}
    try:
        for strategy in ('structure', 'fixed'):
            started = time.perf_counter()
            docs, n_chunks = [], 0
            for c in contracts:
                d, k = ingest(org, user, c, strategy)
                docs.append((d, c))
                n_chunks += k
            print(f'{strategy}: {n_chunks} chunks for {len(docs)} contracts in {time.perf_counter() - started:.0f}s')

            stats = {m: {'hit1': 0, 'hit3': 0, 'hit5': 0, 'rr': 0.0, 'n': 0} for m in MODES}
            for doc, c in docs:
                for category, question in QUESTIONS.items():
                    spans = c['gold'].get(category) or []
                    if not spans:
                        continue
                    for mode in MODES:
                        hits = hybrid_search(user, question, document_ids=[doc.id], k=10, candidates=60, mode=mode)
                        rank = next((i + 1 for i, h in enumerate(hits) if contains_answer(h.chunk.text, spans)), None)
                        s = stats[mode]
                        s['n'] += 1
                        s['hit1'] += rank == 1
                        s['hit3'] += bool(rank and rank <= 3)
                        s['hit5'] += bool(rank and rank <= 5)
                        s['rr'] += 1 / rank if rank else 0
            results[strategy] = {
                'chunks': n_chunks, 'avg_chunks_per_contract': round(n_chunks / len(docs), 1),
                'modes': {m: {'queries': s['n'], 'hit@1': round(s['hit1'] / s['n'], 3), 'hit@3': round(s['hit3'] / s['n'], 3),
                              'hit@5': round(s['hit5'] / s['n'], 3), 'mrr@10': round(s['rr'] / s['n'], 3)} for m, s in stats.items()},
            }
            for m, v in results[strategy]['modes'].items():
                print(f'  {strategy:9s} {m:6s}  hit@1 {v["hit@1"]:.3f}  hit@3 {v["hit@3"]:.3f}  hit@5 {v["hit@5"]:.3f}  mrr {v["mrr@10"]:.3f}  ({v["queries"]} q)')
            Document.objects.filter(organization=org).delete()
    finally:
        if not args.keep:
            Document.objects.filter(organization=org).delete()

    save('retrieval_cuad', {'contracts': len(contracts), 'questions_per_category': QUESTIONS, 'results': results})


if __name__ == '__main__':
    main()
