"""
Query router: decides HOW a question should be answered.

  LOOKUP    -> a fact stored in the records table ("When was the NDA with Acme signed?")
  KNOWLEDGE -> an explanation from document text ("What does the Contract Act say about void agreements?")
  SEARCH    -> find documents ("Find the lease for the Lahore office")

The LLM only produces a *plan* (intent + filters as JSON). It never writes SQL and
never sees documents the user is not allowed to access.
"""
import re
from datetime import date

from ai import llm
from documents.schema import FIELD_DESCRIPTIONS, FIELD_KEYS

INTENTS = ('LOOKUP', 'KNOWLEDGE', 'SEARCH')

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
LOOKUP_DOC_WORDS = r'\b(nda|agreement|contract|lease|deed|mou|affidavit|letter|tenancy|records?)\b'
SEARCH_START = r'^(find|show|open|get|fetch|pull up|locate|where is|list|search)\b'


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
    if field and (dm or plan['party']):
        plan['intent'] = 'LOOKUP'
        plan['field'] = field
    elif re.search(SEARCH_START, t):
        plan['intent'] = 'SEARCH'
    if years and plan['intent'] == 'LOOKUP':
        plan['date_from'] = f'{years[0]}-01-01'
        plan['date_to'] = f'{years[-1]}-12-31'
    return plan


def plan_query(text, history=None):
    if not llm.is_configured():
        return heuristic_plan(text)
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

Record fields:
{fields}

{hist}Question: "{text}"

Return JSON with exactly these keys:
{{"intent": "LOOKUP|KNOWLEDGE|SEARCH",
  "doc_type": "type of record mentioned, e.g. NDA, lease, employment contract, or null",
  "party": "organization/person name the record is with, or null",
  "field": "one record field key from the list above, or null",
  "date_from": "YYYY-MM-DD or null", "date_to": "YYYY-MM-DD or null",
  "keywords": "the question rewritten as a standalone search query"}}"""
    try:
        out = llm.chat_json([{'role': 'user', 'content': prompt}], max_tokens=400, temperature=0.0)
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
