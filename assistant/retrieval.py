"""
Permission-aware hybrid retrieval.

1. Restrict to chunks of the CURRENT version of documents the user may see.
2. Dense search: pgvector cosine distance over the HNSW index.
3. Sparse search: Postgres full-text search (tsvector, section titles weighted higher).
4. Fuse both rankings with Reciprocal Rank Fusion (RRF).
"""
import re
from dataclasses import dataclass

from django.contrib.postgres.search import SearchQuery, SearchRank
from django.db import connection, transaction
from pgvector.django import CosineDistance

from ai.embeddings import embed_query
from documents.access import visible_documents
from documents.models import Chunk

RRF_K = 60
STOPWORDS = set('''the and for are was were with what when where which who whom whose why how does did done
this that these those from into onto about above below under over than then them they their there here
have has had having can could should would will shall may might must not any all our your you his her its
tell show find give list please document documents file files say says said according'''.split())


@dataclass
class Hit:
    chunk: Chunk
    score: float
    dense_rank: int | None
    sparse_rank: int | None


def query_terms(text):
    words = re.findall(r'[A-Za-z0-9]{3,}', (text or '').lower())
    seen, out = set(), []
    for w in words:
        if w not in STOPWORDS and w not in seen:
            seen.add(w)
            out.append(w)
    return out[:12]


def scoped_documents(user, document_ids=None, kinds=None):
    docs = visible_documents(user).filter(current_version__isnull=False)
    if document_ids:
        docs = docs.filter(id__in=document_ids)
    if kinds:
        docs = docs.filter(kind__in=kinds)
    return docs


def hybrid_search(user, text, document_ids=None, kinds=None, k=8, candidates=40, mode='hybrid'):
    """mode: 'hybrid' (default, RRF of both), 'dense' (embeddings only) or 'sparse' (full-text only) — the
    last two exist for the evaluation's ablation study."""
    docs = scoped_documents(user, document_ids, kinds)
    base = Chunk.objects.filter(version_id__in=docs.values('current_version_id'))

    dense = []
    if mode in ('hybrid', 'dense'):
        qv = embed_query(text)
        with transaction.atomic():
            with connection.cursor() as cur:
                cur.execute('SET LOCAL hnsw.ef_search = 100')
                cur.execute('SET LOCAL hnsw.iterative_scan = relaxed_order')
            dense = list(base.annotate(distance=CosineDistance('embedding', qv))
                         .order_by('distance').values_list('id', flat=True)[:candidates])

    sparse = []
    terms = query_terms(text) if mode in ('hybrid', 'sparse') else []
    if terms:
        sq = None
        for t in terms:
            q = SearchQuery(t, config='english')
            sq = q if sq is None else sq | q
        sparse = list(base.filter(search_vector=sq).annotate(rank=SearchRank('search_vector', sq))
                      .order_by('-rank').values_list('id', flat=True)[:candidates])

    scores, d_rank, s_rank = {}, {}, {}
    for i, cid in enumerate(dense):
        d_rank[cid] = i + 1
        scores[cid] = scores.get(cid, 0) + 1 / (RRF_K + i + 1)
    for i, cid in enumerate(sparse):
        s_rank[cid] = i + 1
        scores[cid] = scores.get(cid, 0) + 1 / (RRF_K + i + 1)

    top = sorted(scores, key=scores.get, reverse=True)[:k]
    chunks = Chunk.objects.select_related('version__document').in_bulk(top)
    return [Hit(chunks[cid], round(scores[cid], 5), d_rank.get(cid), s_rank.get(cid)) for cid in top if cid in chunks]
