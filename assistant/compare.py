"""
Comparison questions: "Compare the termination notice in all our NDAs", "How do our leases differ on rent?".

The answer is a table: one row per record the user may open, one column per point compared.
  - Points that are record fields come straight from the records table, with their page and evidence quote.
  - Anything else (a clause topic such as "confidentiality obligations", or a field the extraction missed) is
    read from that record's own passages by the LLM. As with extracted fields, the quote it gives must be found
    in the passage (grounding); otherwise the cell says "Not stated".
Below the table, one bullet per stored field says how the records differ (earliest / latest date, shortest /
longest duration, which records agree), computed from the table so it cannot misstate a value. Only free-text
points are summarized by the LLM, from the cells alone, citing them.
"""
import re

from django.db.models import Q

from ai import llm
from documents.models import Document, RecordField
from documents.pipeline.understanding import ground, parse_term
from documents.schema import DOC_TYPE_ALIASES, FIELD_DESCRIPTIONS, FIELD_KEYS, FIELD_LABELS, FIELD_TYPES

from . import retrieval

MAX_DOCS = 12
MAX_COLUMNS = 4
MAX_READS = 24          # cells read from document text in one LLM call
DEFAULT_FIELDS = ['term', 'notice_period', 'expiry_date', 'governing_law']


def select_documents(user, plan, document_ids):
    from .engine import doc_type_filter
    docs = retrieval.scoped_documents(user, document_ids, kinds=[Document.Kind.RECORD])
    named = [p for p in plan.get('records') or [] if p]
    doc_type = (plan.get('doc_type') or '').strip()
    # with named records, a type only narrows them when it is a known one ("the NDAs with Acme and Orion"); a free
    # description such as "courier agreement, supply agreement" is already covered by the names
    if doc_type and not document_ids and (not named or known_type(doc_type)):
        docs = docs.filter(doc_type_filter(doc_type))
    if named and not document_ids:
        q = Q()
        for name in named:
            q |= record_filter(name)
        docs = docs.filter(q)
    docs = docs.select_related('current_version').order_by('title')
    return list(docs[:MAX_DOCS]), docs.count()


def known_type(term):
    t = term.lower().strip().rstrip('s')
    return any(t == key or t in aliases for key, aliases in DOC_TYPE_ALIASES.items())


NAME_FILLER = {'the', 'and', 'our', 'with', 'agreement', 'agreements', 'contract', 'contracts', 'record', 'records'}


def record_filter(name):
    """A record named by its other party ("Acme"), its type ("lease") or a short description ("courier agreement",
    "Acme NDA"): matches the parties field, the title, or the type."""
    from .engine import doc_type_filter
    with_party = RecordField.objects.filter(key='parties', value_text__icontains=name).values('version_id')
    q = Q(title__icontains=name) | Q(current_version_id__in=with_party)
    words = [w for w in re.findall(r'\w+', name.lower()) if len(w) > 2 and w not in NAME_FILLER]
    if words:
        every = Q()
        for w in words:            # every word of the description in the title, type or (for types) an alias
            every &= Q(title__icontains=w) | Q(doc_type__icontains=w) | doc_type_filter(w)
        q |= every
    return q


def columns_for(plan):
    keys = []
    for f in plan.get('fields') or []:
        if f in FIELD_KEYS and f not in keys:
            keys.append(f)
    cols = [{'key': f, 'label': FIELD_LABELS[f], 'kind': 'field'} for f in keys]
    aspect = (plan.get('aspect') or '').strip()
    if aspect:
        cols.append({'key': 'aspect', 'label': aspect[:1].upper() + aspect[1:80], 'kind': 'text'})
    if not cols:
        cols = [{'key': f, 'label': FIELD_LABELS[f], 'kind': 'field'} for f in DEFAULT_FIELDS]
    return cols[:MAX_COLUMNS]


def _empty_cell():
    return {'value': None, 'page': None, 'quote': '', 'status': None, 'from': None}


def build_rows(user, docs, columns):
    from .engine import _fmt_value
    field_keys = [c['key'] for c in columns if c['kind'] == 'field']
    stored = {}
    for f in RecordField.objects.filter(version_id__in=[d.current_version_id for d in docs], key__in=field_keys) \
            .order_by('id'):
        stored.setdefault((f.version_id, f.key), f)       # first value if a field was added twice
    rows, missing = [], []
    for d in docs:
        row = {'document_id': d.id, 'document_title': d.title, 'doc_type': d.doc_type,
               'version': d.current_version.number, 'cells': {}}
        for c in columns:
            f = stored.get((d.current_version_id, c['key'])) if c['kind'] == 'field' else None
            if f:
                row['cells'][c['key']] = {'value': _fmt_value(f), 'page': f.source_page, 'quote': f.source_quote,
                                          'status': f.status, 'from': 'record',
                                          'date': f.value_date.isoformat() if f.value_date else None}
            else:
                row['cells'][c['key']] = _empty_cell()
                missing.append((row, c, d))
        rows.append(row)
    read_from_text(user, missing)
    return rows


def read_from_text(user, pending):
    """Fill the cells that are not stored record fields by reading each record's most relevant passages."""
    if not pending or not llm.is_configured():
        return
    pending = pending[:MAX_READS]
    blocks, passages = [], {}
    for n, (row, col, doc) in enumerate(pending, 1):
        query = f"{col['label']}: {FIELD_DESCRIPTIONS[col['key']]}" if col['kind'] == 'field' else col['label']
        chunks = [h.chunk for h in retrieval.hybrid_search(user, query, [doc.id], k=2)]
        passages[n] = chunks
        text = '\n---\n'.join(f'(page {c.page_start}) {c.text[:1500]}' for c in chunks) or '(no text)'
        blocks.append(f'[Q{n}] Document: {doc.title}\nPoint: {col["label"]}\nPassages:\n{text}')
    prompt = ('For each numbered item, read ONLY its passages and state what that document says about the point.\n'
              'Return JSON: {"answers": [{"id": "Q<n>", "value": "what the document says, at most 20 words, or null '
              'if the passages do not say", "quote": "exact words copied from the passages that show it (max 30 words)"}]}\n'
              'Never use another item\'s passages or general knowledge.\n\n' + '\n\n'.join(blocks))
    try:
        out = llm.chat_json([{'role': 'user', 'content': prompt}], max_tokens=1500, temperature=0.0, deadline=40)
    except llm.LLMError:
        return
    for a in out.get('answers') or []:
        try:
            n = int(str(a.get('id', '')).strip().upper().lstrip('Q'))
            row, col, _doc = pending[n - 1]
        except (TypeError, ValueError, IndexError):
            continue
        value, quote = str(a.get('value') or '').strip(), str(a.get('quote') or '').strip()
        if not value or value.lower() in ('null', 'none', 'not stated') or not quote:
            continue
        chunk = next((c for c in passages.get(n, []) if ground(quote, c.text)), None)
        if chunk is None:          # the model's words are not in this document: leave the cell empty
            continue
        row['cells'][col['key']] = {'value': value[:200], 'page': chunk.page_start, 'quote': quote[:400],
                                    'status': 'TEXT', 'from': 'text'}


def sources_for(rows, columns):
    """Every filled cell becomes a numbered source, so the summary can cite it and the UI can open its page."""
    sources = []
    for r in rows:
        for c in columns:
            cell = r['cells'][c['key']]
            if cell['value'] and cell['page']:
                sources.append({'id': len(sources) + 1, 'type': 'field' if cell['from'] == 'record' else 'chunk',
                                'document_id': r['document_id'], 'document_title': r['document_title'],
                                'version': r['version'], 'page': cell['page'], 'page_end': cell['page'],
                                'section': c['label'], 'snippet': cell['quote']})
                cell['source'] = sources[-1]['id']
    return sources


def _names(items):
    names = [r['document_title'] for r in items]
    return ', '.join(names) if len(names) <= 3 else f'{len(names)} records'


def _cite(cells):
    return ''.join(f"[{c['source']}]" for c in cells if c.get('source'))


def _days(value):
    term = parse_term(value)
    if not term:
        return None
    unit, n = term
    return n * 30 if unit == 'months' else n


def describe(rows, col):
    """One bullet on how the records differ on a stored field, computed from the table (no model involved, so it
    cannot misstate a value): earliest / latest date, shortest / longest duration, or which records agree."""
    key, label = col['key'], col['label']
    stated = [(r, r['cells'][key]) for r in rows if r['cells'][key]['value']]
    missing = [r for r in rows if not r['cells'][key]['value']]
    gap = f' Not stated in {_names(missing)}.' if missing else ''
    if not stated:
        return f'**{label}**: not stated in any of these records.'
    if len(stated) == 1:
        r, c = stated[0]
        return f"**{label}**: only {r['document_title']} states it: {c['value']} {_cite([c])}.{gap}"

    rank = None
    if FIELD_TYPES.get(key) == 'date' and all(c.get('date') for _, c in stated):
        rank = lambda rc: rc[1]['date']
    elif key in ('term', 'notice_period') and all(_days(c['value']) for _, c in stated):
        rank = lambda rc: _days(rc[1]['value'])
    if rank:
        ordered = sorted(stated, key=rank)
        lo, hi = ordered[0], ordered[-1]
        if rank(lo) == rank(hi):
            return f"**{label}**: the same in all {len(stated)} records that state it: {lo[1]['value']} " \
                   f"{_cite([c for _, c in stated])}.{gap}"
        words = ('earliest', 'latest') if FIELD_TYPES.get(key) == 'date' else ('shortest', 'longest')
        return (f"**{label}**: {words[0]} {lo[0]['document_title']} ({lo[1]['value']}) {_cite([lo[1]])}, "
                f"{words[1]} {hi[0]['document_title']} ({hi[1]['value']}) {_cite([hi[1]])}.{gap}")

    groups = {}
    for r, c in stated:                                  # same value, ignoring case and punctuation
        groups.setdefault(' '.join(re.findall(r'\w+', c['value'].lower())), []).append((r, c))
    if len(groups) == 1:
        return f"**{label}**: the same in all {len(stated)} records that state it: {stated[0][1]['value']} " \
               f"{_cite([c for _, c in stated])}.{gap}"
    parts = [f"{g[0][1]['value']} in {_names([r for r, _ in g])} {_cite([c for _, c in g])}"
             for g in sorted(groups.values(), key=len, reverse=True)]
    return f"**{label}**: {'; '.join(parts)}.{gap}"


SUMMARY_PROMPT = """Below is what several records of an organization say about one point. Using ONLY these
statements, write 1 to 3 short bullet points on how the records differ (e.g. one is stricter, one is silent).
Cite a record's statement like [3] only when you mention that record's statement. Do not explain the law and do
not give legal advice."""


def prepare(user, plan, text, document_ids):
    """Returns (intro, sources, rows, messages) or None when no record matches. `messages` is None when no
    summary is needed (one record, nothing filled, or no LLM)."""
    docs, total = select_documents(user, plan, document_ids)
    if not docs:
        return None
    columns = columns_for(plan)
    plan['columns'] = columns
    rows = build_rows(user, docs, columns)
    sources = sources_for(rows, columns)
    labels = ', '.join(c['label'].lower() for c in columns)
    if len(docs) == 1:
        intro = (f'Only one matching record was found (**{docs[0].title}**), so there is nothing to compare it with. '
                 f'Its {labels}:')
    else:
        intro = f'Compared **{len(docs)}** records on {labels}.'
        if total > len(docs):
            intro += f' Showing the first {len(docs)} of {total}; ask about fewer records to see the rest.'
    messages = None
    if len(docs) >= 2:
        bullets = [describe(rows, c) for c in columns if c['kind'] == 'field']
        if bullets:
            intro += '\n\n' + '\n'.join(f'- {b}' for b in bullets)
        # a free-text point (clause content) cannot be compared by rules: the model summarizes it
        aspect = next((c for c in columns if c['kind'] == 'text'), None)
        if aspect and llm.is_configured():
            stated = [(r, r['cells'][aspect['key']]) for r in rows]
            if sum(bool(c['value']) for _, c in stated) >= 2:
                lines = '\n'.join(f"- {r['document_title']}: " +
                                  (f"{c['value']} [{c['source']}]" if c['value'] else 'does not say')
                                  for r, c in stated)
                messages = [{'role': 'system', 'content': SUMMARY_PROMPT},
                            {'role': 'user', 'content': f"POINT: {aspect['label']}\n\nSTATEMENTS:\n{lines}"}]
            else:
                intro += '\n\n- ' + describe(rows, aspect)
    unverified = any(cell['status'] in ('NEEDS_REVIEW', 'TEXT') for r in rows for cell in r['cells'].values())
    if unverified:
        intro += '\n\n_Some values have not been confirmed by a person yet._'
    return intro, sources, rows, messages


def run(user, plan, text, document_ids):
    out = prepare(user, plan, text, document_ids)
    if out is None:
        return None
    intro, sources, rows, messages = out
    answer = intro
    if messages:
        try:
            answer += '\n\n' + llm.chat(messages, max_tokens=500, temperature=0.1, deadline=30)
        except llm.LLMError:
            pass                 # the table is the answer; the summary is optional
    return answer, sources, rows
