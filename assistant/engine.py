"""Executes a routed query and builds the answer + sources the frontend renders."""
from django.db.models import Q

from ai import llm
from documents.models import Chunk, Document, RecordField
from documents.schema import DOC_TYPE_ALIASES, FIELD_LABELS, FIELD_PHRASES, FIELD_TYPES

from . import retrieval, router

NOT_FOUND = "I couldn't find anything about that in the documents you have access to."


def _fmt_value(field):
    if field.value_date:
        return field.value_date.strftime('%d %B %Y').lstrip('0')
    return field.value_text


def doc_type_filter(term):
    term = (term or '').lower().strip()
    if not term or term in ('record', 'records', 'contract', 'contracts', 'agreement', 'agreements', 'document'):
        return Q()
    words = {term}
    for key, aliases in DOC_TYPE_ALIASES.items():
        if term == key or term in aliases or any(a in term for a in aliases) or key in term:
            words.update(aliases)
            words.add(key)
    q = Q()
    for w in words:
        q |= Q(doc_type__icontains=w) | Q(title__icontains=w)
    return q


def _source_from_hit(i, hit):
    c = hit.chunk
    doc = c.version.document
    return {
        'id': i, 'type': 'chunk', 'chunk_id': c.id, 'document_id': doc.id, 'document_title': doc.title,
        'version': c.version.number, 'page': c.page_start, 'page_end': c.page_end,
        'section': c.section_path, 'snippet': c.text[:700], 'score': hit.score,
    }


# ---------------- LOOKUP ----------------

def run_lookup(user, plan, document_ids):
    docs = retrieval.scoped_documents(user, document_ids, kinds=[Document.Kind.RECORD])
    if plan.get('doc_type'):
        docs = docs.filter(doc_type_filter(plan['doc_type']))
    if plan.get('party'):
        party = plan['party']
        with_party = RecordField.objects.filter(key='parties', value_text__icontains=party).values('version_id')
        docs = docs.filter(Q(title__icontains=party) | Q(current_version_id__in=with_party))

    field_key = plan.get('field')
    if not field_key and (plan.get('date_from') or plan.get('date_to')):
        field_key = 'expiry_date'
    fields = RecordField.objects.filter(version_id__in=docs.values('current_version_id')) \
        .select_related('version__document')

    if field_key:
        fields = fields.filter(key=field_key)
        if FIELD_TYPES.get(field_key) == 'date':
            if plan.get('date_from'):
                fields = fields.filter(value_date__gte=plan['date_from'])
            if plan.get('date_to'):
                fields = fields.filter(value_date__lte=plan['date_to'])
            fields = fields.order_by('value_date')
    else:
        fields = fields.filter(key__in=['parties', 'signed_date', 'expiry_date'])

    rows = []
    for f in fields[:50]:
        doc = f.version.document
        rows.append({
            'document_id': doc.id, 'document_title': doc.title, 'doc_type': doc.doc_type,
            'field_id': f.id, 'field': f.key, 'label': f.label, 'value': _fmt_value(f),
            'page': f.source_page, 'quote': f.source_quote, 'status': f.status,
            'verified': f.status in (RecordField.Status.VERIFIED, RecordField.Status.CORRECTED),
            'version': f.version.number,
        })
    if not rows:
        return None

    unverified = any(r['status'] == 'NEEDS_REVIEW' for r in rows)
    note = '\n\n_Some values were extracted automatically and have not been verified yet._' if unverified else ''
    if field_key and len({r['document_id'] for r in rows}) == 1 and len(rows) == 1:
        r = rows[0]
        page = f" (page {r['page']})" if r['page'] else ''
        answer = f"The {r['doc_type'] or 'record'} **{r['document_title']}** {FIELD_PHRASES[field_key]} **{r['value']}**{page}."
    else:
        label = FIELD_LABELS.get(field_key, 'key details')
        n_docs = len({r['document_id'] for r in rows})
        answer = f'I found **{n_docs}** matching record(s). {label}:'
    sources = [{'id': i + 1, 'type': 'field', 'document_id': r['document_id'], 'document_title': r['document_title'],
                'version': r['version'], 'page': r['page'], 'page_end': r['page'], 'section': r['label'],
                'snippet': r['quote']} for i, r in enumerate(rows[:10])]
    return answer + note, sources, rows


# ---------------- KNOWLEDGE ----------------

SYSTEM_PROMPT = """You are the research assistant of an organization's legal records system.
Answer ONLY from the numbered sources provided. After every factual statement cite its source like [1] or [2][3].
Quote short exact wording for legal provisions when useful. If the sources do not contain the answer,
say so plainly instead of guessing. Be concise and well structured (use short paragraphs or bullet points).
You provide information from documents, not legal advice."""


def run_knowledge(user, plan, text, document_ids):
    hits = retrieval.hybrid_search(user, plan.get('keywords') or text, document_ids, k=8)
    if not hits:
        return NOT_FOUND, [], []
    sources = [_source_from_hit(i + 1, h) for i, h in enumerate(hits)]
    if not llm.is_configured():
        top = sources[0]
        return f"Most relevant passage, from **{top['document_title']}** (page {top['page']}) [1]:\n\n> {top['snippet'][:500]}", sources, []

    context = '\n\n'.join(
        f"[{s['id']}] {s['document_title']} — {s['section'] or 'text'} (page {s['page']})\n{h.chunk.text}"
        for s, h in zip(sources, hits))
    try:
        answer = llm.chat([
            {'role': 'system', 'content': SYSTEM_PROMPT},
            {'role': 'user', 'content': f'SOURCES:\n{context}\n\nQUESTION: {text}'},
        ], max_tokens=1500, temperature=0.1)
    except llm.LLMError as exc:
        return f'The language model is unavailable right now ({exc}). The most relevant passages are listed as sources.', sources, []
    return answer, sources, []


# ---------------- SEARCH ----------------

def run_search(user, plan, text, document_ids):
    query = plan.get('keywords') or text
    hits = retrieval.hybrid_search(user, query, document_ids, k=40, candidates=80)
    best = {}
    for h in hits:
        doc = h.chunk.version.document
        if doc.id not in best or h.score > best[doc.id]['score']:
            best[doc.id] = {'document_id': doc.id, 'document_title': doc.title, 'doc_type': doc.doc_type,
                            'kind': doc.kind, 'page': h.chunk.page_start, 'snippet': h.chunk.text[:300],
                            'score': h.score, 'summary': doc.summary}
    # boost documents whose title / type match the query words
    terms = retrieval.query_terms(query)
    if terms:
        tq = Q()
        for t in terms:
            tq |= Q(title__icontains=t) | Q(doc_type__icontains=t)
        if plan.get('doc_type'):
            tq |= doc_type_filter(plan['doc_type'])
        for doc in retrieval.scoped_documents(user, document_ids).filter(tq)[:20]:
            entry = best.setdefault(doc.id, {'document_id': doc.id, 'document_title': doc.title, 'doc_type': doc.doc_type,
                                             'kind': doc.kind, 'page': 1, 'snippet': doc.summary, 'score': 0,
                                             'summary': doc.summary})
            entry['score'] += 0.05
        # boost documents containing a clause the fine-tuned classifier labelled with a query word
        cq = Q()
        for t in terms:
            if len(t) >= 6:
                cq |= Q(clause_label__icontains=t.rstrip('s'))
        if cq:
            docs = retrieval.scoped_documents(user, document_ids)
            for c in (Chunk.objects.filter(cq, version_id__in=docs.values('current_version_id'))
                      .select_related('version__document')[:30]):
                doc = c.version.document
                entry = best.setdefault(doc.id, {'document_id': doc.id, 'document_title': doc.title, 'doc_type': doc.doc_type,
                                                 'kind': doc.kind, 'page': c.page_start, 'snippet': c.text[:300], 'score': 0,
                                                 'summary': doc.summary})
                if not entry.get('clause'):
                    entry.update(score=entry['score'] + 0.04, clause=c.clause_label, page=c.page_start, snippet=c.text[:300])
    results = sorted(best.values(), key=lambda r: r['score'], reverse=True)[:10]
    if not results:
        return NOT_FOUND, [], []
    answer = f'I found **{len(results)}** document(s) that match.'
    sources = [{'id': i + 1, 'type': 'document', 'document_id': r['document_id'], 'document_title': r['document_title'],
                'page': r['page'], 'page_end': r['page'],
                'section': f"{r['clause']} clause · {r['doc_type']}" if r.get('clause') else r['doc_type'], 'snippet': r['snippet']}
               for i, r in enumerate(results)]
    return answer, sources, results


# ---------------- entry point ----------------

def answer(user, text, document_ids=None, history=None):
    plan = router.plan_query(text, history)
    intent = plan['intent']
    if intent == 'LOOKUP':
        out = run_lookup(user, plan, document_ids)
        if out is None:  # no stored record matches -> read the documents instead
            plan['fallback'] = 'no matching record fields; answered from document text'
            intent = 'KNOWLEDGE'
            out = run_knowledge(user, plan, text, document_ids)
    elif intent == 'SEARCH':
        out = run_search(user, plan, text, document_ids)
    else:
        out = run_knowledge(user, plan, text, document_ids)
    answer_text, sources, results = out
    return {'intent': intent, 'plan': plan, 'answer': answer_text, 'sources': sources, 'results': results}
