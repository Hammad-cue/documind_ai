"""
Query router: decides HOW a question should be answered.

  LOOKUP    -> a fact stored in the records table ("When was the NDA with Acme signed?")
  KNOWLEDGE -> an explanation from document text ("What does the Contract Act say about void agreements?")
  SEARCH    -> find documents ("Find the lease for the Lahore office")
  COMPARE   -> the same point across several records ("Compare the termination notice in all our NDAs")

The LLM only produces a *plan* (intent + filters as JSON). It never writes SQL and
never sees documents the user is not allowed to access.
"""
import re
from datetime import date

from ai import llm
from documents.schema import FIELD_DESCRIPTIONS, FIELD_KEYS

INTENTS = ('LOOKUP', 'KNOWLEDGE', 'SEARCH', 'COMPARE')

FIELD_SYNONYMS = [
    ('signed_date', r'\b(signed|executed|signing|signature date)\b'),
    ('expiry_date', r'\b(expir\w*|end date|ends?|terminat\w* date|valid (till|until))\b'),
    ('effective_date', r'\b(effective|start date|commence\w*|starts?)\b'),
    ('notice_period', r'\bnotice\b'),
    ('governing_law', r'\b(governing law|jurisdiction|governed)\b'),
    ('contract_value', r'\b(value|worth|amount|price|fee|cost)\b'),
    ('auto_renewal', r'\b(renew\w*)\b'),
    ('signatories', r'\b(who signed|signator\w*)\b'),
    ('parties', r'\b(parties|party|between whom|counterpart\w*)\b'),
    ('term', r'\b(term|duration|how long)\b'),
    ('reference_number', r'\b(reference|ref\.? ?(no|number)|file number)\b'),
]
LOOKUP_DOC_WORDS = r'\b(ndas?|agreements?|contracts?|leases?|deeds?|mous?|affidavits?|letters?|tenancy|tenancies|records?)\b'
SEARCH_START = r'^(find|show|open|get|fetch|pull up|locate|where is|list|search)\b'
COMPARE_RX = (r'\b(compare|comparing|comparison|contrast|side[- ]by[- ]side|versus|vs\.?)\b'
              r'|\bdiffer(?:s|ence|ences)?\s+(?:between|across|among)\s+(?:our|all|the|these|my)\b'
              r'|\bhow\s+do\s+(?:our|the|these|all|my)\b.*\bdiffer\b')
GENERIC_DOC_WORDS = {'agreement', 'contract', 'record', 'document', 'letter'}
NOT_NAMES = {'compare', 'comparing', 'how', 'what', 'which', 'show', 'list', 'nda', 'ndas', 'mou', 'mous', 'i', 'the', 'our'}
ASPECT_FILLER = set('''the a an in of on for all our my these those between across among and with how do does differ
differs difference differences compare comparing comparison side by versus vs what are is me show please list their
each every them two both'''.split())


def is_comparison(t):
    """Explicit comparison wording. Comparing versions of one document is done on the document page instead."""
    return bool(re.search(COMPARE_RX, t)) and not re.search(r'\bversions?\b', t)


def _compare_plan(text, t):
    """Fields, named records and the compared point of a comparison question (keyword version)."""
    fields = [k for k, rx in FIELD_SYNONYMS if re.search(rx, t)]
    kinds = {w[:-3] + 'y' if w.endswith('ies') else w.rstrip('s') for w in re.findall(LOOKUP_DOC_WORDS, t)}
    specific = kinds - GENERIC_DOC_WORDS
    names = []
    for m in re.finditer(r'\b[A-Z][\w&.\-]*(?:\s+[A-Z][\w&.\-]*)*', text):
        name = m.group(0).strip(' .')
        if m.start() == 0 or name.lower() in NOT_NAMES or name.lower().rstrip('s') in kinds:
            continue
        names.append(name)
    aspect = None
    if not fields:
        named = {w for p in names for w in p.lower().split()}
        words = [w for w in re.findall(r"[a-z][a-z'\-]*", t)
                 if w not in ASPECT_FILLER and w.rstrip('s') not in kinds and w not in named]
        aspect = ' '.join(words) or None
    # records named by party ("Acme and Orion") or, failing that, by type ("the NDA and the lease")
    records = names or (sorted(specific) if len(specific) > 1 else [])
    return {'fields': fields, 'records': records, 'names': names, 'aspect': aspect,
            'doc_type': next(iter(specific)) if len(specific) == 1 else None, 'kinds': kinds}


def heuristic_plan(text):
    t = text.lower().strip()
    field = next((k for k, rx in FIELD_SYNONYMS if re.search(rx, t)), None)
    years = re.findall(r'\b(20\d{2}|19\d{2})\b', t)
    plan = {'intent': 'KNOWLEDGE', 'doc_type': None, 'party': None, 'field': None,
            'date_from': None, 'date_to': None, 'keywords': text, 'method': 'heuristic'}
    m = re.search(r'\b(?:with|between|for|of)\s+([A-Z][\w&.\- ]{1,40}?)(?:\s+(?:signed|expire|was|is|end|start)|[?.,]|$)', text)
    if m:
        plan['party'] = m.group(1).strip()
    dm = re.search(LOOKUP_DOC_WORDS, t)
    if dm:
        plan['doc_type'] = dm.group(1)
    if is_comparison(t):
        cp = _compare_plan(text, t)
        # generic words ("agreements", "contracts") only mean records when they are the organization's own
        # ("our contracts"); "void agreements vs voidable contracts" is a question about the law
        own = re.search(r'\b(our|all|these|my|every|each)\b', t)
        if (cp['kinds'] - GENERIC_DOC_WORDS) or (cp['kinds'] and own) or len(cp['names']) >= 2 or cp['fields']:
            plan.update(intent='COMPARE', fields=cp['fields'], records=cp['records'], aspect=cp['aspect'],
                        doc_type=cp['doc_type'], party=None, types_named=sorted(cp['kinds']))
            return plan
    if field and (dm or plan['party']):
        plan['intent'] = 'LOOKUP'
        plan['field'] = field
    elif re.search(SEARCH_START, t):
        plan['intent'] = 'SEARCH'
    if years and plan['intent'] == 'LOOKUP':
        plan['date_from'] = f'{years[0]}-01-01'
        plan['date_to'] = f'{years[-1]}-12-31'
    return plan


def confident_search(text):
    """'Find/show/list ...' requests that mention no record field are always document searches (21 of 21 in the
    labelled router set), so they skip the LLM routing call and save API quota."""
    t = text.lower().strip()
    return (bool(re.search(SEARCH_START, t)) and not re.search(COMPARE_RX, t)
            and not any(re.search(rx, t) for _, rx in FIELD_SYNONYMS))


def plan_query(text, history=None):
    if not llm.is_configured():
        return heuristic_plan(text)
    if confident_search(text) and not history:
        plan = heuristic_plan(text)
        plan.update(intent='SEARCH', method='keyword rules (confident search)')
        return plan
    hist = ''
    if history:
        hist = 'Previous questions in this conversation (resolve words like "it" / "that contract"):\n' + \
               '\n'.join(f'- {h}' for h in history[-3:]) + '\n\n'
    fields = '\n'.join(f'  {k}: {FIELD_DESCRIPTIONS[k]}' for k in FIELD_KEYS)
    prompt = f"""You route questions in an organization's legal document records system. Today is {date.today().isoformat()}.

Intents:
- LOOKUP: asks for a specific stored fact about one or more records (contracts, NDAs, leases, agreements), or asks to list records by a field/date. Examples: "When was the NDA with Acme signed?", "Which contracts expire in 2027?", "Who are the parties to the office lease?"
- KNOWLEDGE: asks for an explanation, rule, clause content or reasoning that must be read from document text (law books, policies, or clause wording). Examples: "What does the Contract Act say about consideration?", "What are the confidentiality obligations in the Acme NDA?"
- SEARCH: asks to find / open / show documents. Examples: "Find the lease agreement for the Lahore office", "Show me all handwritten affidavits".
- COMPARE: asks to compare the same point across several records, or how records differ from each other. Examples: "Compare the termination notice in all our NDAs", "How do our leases differ on rent and notice?", "Compare the confidentiality obligations in the NDAs with Acme and Orion". Explaining the difference between two legal concepts ("void vs voidable") is KNOWLEDGE, not COMPARE.

Record fields:
{fields}

{hist}Question: "{text}"

Return JSON with exactly these keys:
{{"intent": "LOOKUP|KNOWLEDGE|SEARCH",
  "doc_type": "type of record mentioned, e.g. NDA, lease, employment contract, or null (null if several types are named)",
  "party": "organization/person name the record is with, or null",
  "field": "one record field key from the list above, or null",
  "fields": ["for COMPARE: the record field keys being compared; [] if none fits"],
  "records": ["for COMPARE: the specific records compared, each as its other party's name or a short description (e.g. \"Acme\", \"courier agreement\", \"lease\"); [] when all records of a type are compared"],
  "aspect": "for COMPARE: the point compared when it is not a record field (e.g. confidentiality obligations), else null",
  "date_from": "YYYY-MM-DD or null", "date_to": "YYYY-MM-DD or null",
  "keywords": "the question rewritten as a standalone search query"}}"""
    try:
        out = llm.chat_json([{'role': 'user', 'content': prompt}], max_tokens=300, temperature=0.0, deadline=12)
    except llm.LLMError:
        return heuristic_plan(text)
    plan = {
        'intent': str(_clean(out.get('intent')) or '').upper(),
        'doc_type': _clean(out.get('doc_type')),
        'party': _clean(out.get('party')),
        'field': out.get('field') if out.get('field') in FIELD_KEYS else None,
        'date_from': _iso(_clean(out.get('date_from'))),
        'date_to': _iso(_clean(out.get('date_to'))),
        'keywords': _clean(out.get('keywords')) or text,
        'method': 'llm',
    }
    if plan['intent'] not in INTENTS:
        fallback = heuristic_plan(text)
        plan['intent'] = fallback['intent']
    keyword = heuristic_plan(text)
    if keyword['intent'] == 'COMPARE' and plan['intent'] != 'COMPARE':
        # explicit comparison wording ("compare", "how do our ... differ") about records: the model sometimes
        # calls these lookups, which would list the values without comparing them
        plan['intent'] = 'COMPARE'
        plan['method'] = 'llm, comparison wording'
    if plan['intent'] == 'COMPARE' and re.search(r'\bversions?\b', text.lower()):
        plan['intent'] = keyword['intent']       # versions of one document are compared on its page
    if plan['intent'] == 'COMPARE':
        listed = out.get('fields') if isinstance(out.get('fields'), list) else []
        plan['fields'] = [f for f in listed if f in FIELD_KEYS] or ([plan['field']] if plan['field'] else [])
        named = out.get('records') if isinstance(out.get('records'), list) else []
        plan['records'] = [n for n in (_clean(x) for x in named) if n] or ([plan['party']] if plan['party'] else [])
        plan['aspect'] = _clean(out.get('aspect'))
        if keyword['intent'] == 'COMPARE':
            if not (plan['fields'] or plan['aspect']):
                plan['fields'], plan['aspect'] = keyword['fields'], keyword['aspect']
            if not plan['records']:
                plan['records'] = keyword['records']
            if len(keyword['types_named']) > 1:
                plan['doc_type'] = None      # "the NDA and the lease": both types, not one
    return plan


def _clean(value):
    """LLMs sometimes return the *string* "null" / "none" / "N/A" instead of a JSON null."""
    if value is None:
        return None
    s = str(value).strip()
    return None if s.lower() in ('', 'null', 'none', 'n/a', 'na', 'unknown', 'any', 'all') else s


def _iso(value):
    if not value:
        return None
    try:
        return date.fromisoformat(str(value)[:10]).isoformat()
    except ValueError:
        return None
