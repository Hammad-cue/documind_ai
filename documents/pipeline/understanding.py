"""
Step 3: understand the document with the LLM.
  - classify(): RECORD vs REFERENCE, document type, one-line summary
  - extract_fields(): structured record fields, each with page + verbatim quote
  - ground(): verify each quote really exists on the cited page (anti-hallucination)
"""
import re
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

from django.conf import settings

from ai import llm
from documents.schema import FIELD_DESCRIPTIONS, FIELD_KEYS, FIELD_LABELS, FIELD_TYPES

RECORD_HINTS = ('agreement', 'contract', 'hereinafter', 'party', 'parties', 'witness whereof',
                'executed', 'lessor', 'lessee', 'employer', 'stamp paper', 'affidavit', 'undertaking')


def _paged_text(pages, budget_chars, head_ratio=0.7):
    """Text with [[PAGE n]] markers. For long documents keep the start and the end
    (signature blocks / dates are usually on the last pages)."""
    blocks = [(p.number, f'[[PAGE {p.number}]]\n{p.text.strip()}') for p in pages if p.text.strip()]
    total = sum(len(b) for _, b in blocks)
    if total <= budget_chars:
        return '\n\n'.join(b for _, b in blocks)
    head, tail, used = [], [], 0
    head_budget = budget_chars * head_ratio
    for _, b in blocks:
        if used + len(b) > head_budget:
            break
        head.append(b)
        used += len(b)
    tail_used = 0
    for _, b in reversed(blocks[len(head):]):
        if tail_used + len(b) > budget_chars - used:
            break
        tail.insert(0, b)
        tail_used += len(b)
    if not head:  # one enormous page
        return blocks[0][1][:budget_chars]
    return '\n\n'.join(head) + '\n\n[[... pages omitted ...]]\n\n' + '\n\n'.join(tail)


def heuristic_classify(pages, page_count):
    sample = ' '.join(p.text for p in pages[:3]).lower()
    hits = sum(1 for h in RECORD_HINTS if h in sample)
    if page_count > 40 and hits < 4:
        return {'kind': 'REFERENCE', 'doc_type': 'Reference document', 'summary': ''}
    if hits >= 2:
        return {'kind': 'RECORD', 'doc_type': 'Agreement', 'summary': ''}
    return {'kind': 'REFERENCE', 'doc_type': 'Document', 'summary': ''}


def classify(pages, page_count):
    if not llm.is_configured():
        return {**heuristic_classify(pages, page_count), 'method': 'heuristic'}
    text = _paged_text(pages[:4], 6000)
    prompt = f"""You classify documents for an organization's legal records system.

RECORD = a document that records a specific transaction or relationship between parties
(contract, NDA, lease, employment letter, MoU, affidavit, deed, power of attorney, invoice, handwritten agreement).
REFERENCE = general knowledge material consulted to answer questions (law book, act/ordinance, policy, handbook, manual, guideline, template).

The document has {page_count} pages. Its first pages:
\"\"\"
{text}
\"\"\"

Return JSON: {{"kind": "RECORD" or "REFERENCE", "doc_type": "specific type in 1-5 words, e.g. Non-Disclosure Agreement, Lease Agreement, Contract Act 1872, HR Policy", "summary": "one sentence, max 25 words"}}"""
    try:
        out = llm.chat_json([{'role': 'user', 'content': prompt}], max_tokens=400)
        kind = str(out.get('kind', '')).upper()
        if kind not in ('RECORD', 'REFERENCE'):
            raise llm.LLMError(f'bad kind {kind}')
        return {'kind': kind, 'doc_type': str(out.get('doc_type', ''))[:120],
                'summary': str(out.get('summary', ''))[:500], 'method': 'llm'}
    except (llm.LLMError, ValueError) as exc:
        return {**heuristic_classify(pages, page_count), 'method': f'heuristic ({exc})'}


# ---------------- field extraction ----------------

MONTHS = {m: i for i, m in enumerate(
    ['january', 'february', 'march', 'april', 'may', 'june', 'july', 'august', 'september',
     'october', 'november', 'december'], start=1)}
MONTHS.update({k[:3]: v for k, v in list(MONTHS.items())})
MONTHS['sept'] = 9


def parse_date(value):
    if not value:
        return None
    s = str(value).strip().lower()
    s = re.sub(r'(\d+)(st|nd|rd|th)\b', r'\1', s)
    s = s.replace('day of', '').replace(',', ' ')
    s = re.sub(r'\s+', ' ', s).strip()
    for fmt in ('%Y-%m-%d', '%d/%m/%Y', '%d-%m-%Y', '%d.%m.%Y', '%Y/%m/%d'):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            pass
    m = re.match(r'^(\d{1,2})[ \-]([a-z]+)[ \-](\d{4})$', s)          # 12 march 2025
    if m and m.group(2) in MONTHS:
        try:
            return date(int(m.group(3)), MONTHS[m.group(2)], int(m.group(1)))
        except ValueError:
            return None
    m = re.match(r'^([a-z]+) (\d{1,2}) (\d{4})$', s)                    # march 12 2025
    if m and m.group(1) in MONTHS:
        try:
            return date(int(m.group(3)), MONTHS[m.group(1)], int(m.group(2)))
        except ValueError:
            return None
    return None


def parse_money(value):
    if not value:
        return None
    digits = re.sub(r'[^\d.]', '', str(value).replace(',', ''))
    try:
        return Decimal(digits) if digits else None
    except InvalidOperation:
        return None


def _norm(s):
    return re.sub(r'\s+', ' ', re.sub(r'[^\w\s]', ' ', (s or '').lower())).strip()


def ground(quote, page_text):
    """True if the quote (or >=80% of its words, in order-insensitive form) is on the page."""
    q, p = _norm(quote), _norm(page_text)
    if not q or not p:
        return False
    if q in p:
        return True
    words = q.split()
    if len(words) < 3:
        return False
    page_words = set(p.split())
    return sum(w in page_words for w in words) / len(words) >= 0.8


def extract_fields(pages):
    """Returns list of dicts ready for RecordField(...)."""
    text = _paged_text(pages, 22000)
    field_spec = '\n'.join(f'- {k}: {FIELD_DESCRIPTIONS[k]}' for k in FIELD_KEYS)
    prompt = f"""Extract structured facts from this legal record. Pages are marked [[PAGE n]].

Fields:
{field_spec}

Rules:
- Only use information explicitly written in the document. If a field is not present, use null.
- Dates must be ISO format YYYY-MM-DD.
- "quote" must be copied VERBATIM from the document (max 30 words) and prove the value.
- "page" is the page number where the quote appears.
- "confidence" is 0.0-1.0 (lower it for unclear handwriting, ambiguous or inferred values).

Return JSON: {{"fields": {{"<field>": {{"value": "...", "page": 1, "quote": "...", "confidence": 0.9}} or null, ...}}}}

DOCUMENT:
\"\"\"
{text}
\"\"\""""
    out = llm.chat_json([{'role': 'user', 'content': prompt}], max_tokens=2000)
    raw = out.get('fields', out) if isinstance(out, dict) else {}

    page_text = {p.number: p.text for p in pages}
    page_source = {p.number: p.source for p in pages}
    results = []
    for key in FIELD_KEYS:
        item = raw.get(key)
        if not isinstance(item, dict) or item.get('value') in (None, '', 'null'):
            continue
        value = str(item['value']).strip()
        try:
            page = int(item.get('page')) if item.get('page') is not None else None
        except (TypeError, ValueError):
            page = None
        quote = str(item.get('quote') or '')[:600]
        try:
            conf = max(0.0, min(1.0, float(item.get('confidence', 0.5))))
        except (TypeError, ValueError):
            conf = 0.5

        grounded = ground(quote, page_text.get(page, '')) if page else False
        if not grounded and quote:  # model may have cited the wrong page: search all pages
            for n, t in page_text.items():
                if ground(quote, t):
                    grounded, page = True, n
                    break
        if not grounded:
            conf *= 0.5

        value_date = parse_date(value) if FIELD_TYPES[key] == 'date' else None
        value_number = parse_money(value) if FIELD_TYPES[key] == 'money' else None
        if FIELD_TYPES[key] == 'date' and value_date is None:
            conf *= 0.7

        needs_review = (conf < settings.REVIEW_CONFIDENCE_THRESHOLD or not grounded
                        or page_source.get(page) in ('HANDWRITING', 'OCR'))
        results.append({
            'key': key, 'label': FIELD_LABELS[key],
            'value_text': value_date.isoformat() if value_date else value,
            'value_date': value_date, 'value_number': value_number,
            'confidence': round(conf, 3), 'source_page': page, 'source_quote': quote,
            'grounded': grounded, 'status': 'NEEDS_REVIEW' if needs_review else 'AUTO',
        })
    return results
