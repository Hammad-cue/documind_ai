"""The structured fields extracted from every RECORD document."""

# key, label, value type, phrase used when answering ("was signed on ...")
RECORD_FIELDS = [
    ('parties', 'Parties', 'text', 'is between'),
    ('effective_date', 'Effective date', 'date', 'became effective on'),
    ('signed_date', 'Signing date', 'date', 'was signed on'),
    ('expiry_date', 'Expiry / end date', 'date', 'expires on'),
    ('term', 'Term / duration', 'text', 'has a term of'),
    ('auto_renewal', 'Auto-renewal', 'text', 'has renewal terms:'),
    ('notice_period', 'Termination notice period', 'text', 'requires a termination notice of'),
    ('governing_law', 'Governing law', 'text', 'is governed by'),
    ('contract_value', 'Contract value', 'money', 'has a value of'),
    ('reference_number', 'Reference number', 'text', 'has reference number'),
    ('signatories', 'Signatories', 'text', 'was signed by'),
]

FIELD_KEYS = [f[0] for f in RECORD_FIELDS]
FIELD_LABELS = {f[0]: f[1] for f in RECORD_FIELDS}
FIELD_TYPES = {f[0]: f[2] for f in RECORD_FIELDS}
FIELD_PHRASES = {f[0]: f[3] for f in RECORD_FIELDS}

FIELD_DESCRIPTIONS = {
    'parties': 'All contracting parties, separated by "; "',
    'effective_date': 'Date the agreement takes effect',
    'signed_date': 'Date the document was signed/executed',
    'expiry_date': 'Date the agreement ends or expires (compute only if explicitly stated)',
    'term': 'Duration, e.g. "2 years"',
    'auto_renewal': 'Whether/how it renews automatically',
    'notice_period': 'Notice required to terminate, e.g. "30 days written notice"',
    'governing_law': 'Governing law or jurisdiction',
    'contract_value': 'Total monetary value with currency',
    'reference_number': 'Agreement / file / stamp paper number',
    'signatories': 'Names (and titles) of people who signed',
}

# Free-text document type -> words that identify it, used by the query router.
DOC_TYPE_ALIASES = {
    'nda': ['non-disclosure', 'nondisclosure', 'non disclosure', 'confidentiality agreement', 'nda'],
    'lease': ['lease', 'tenancy', 'rent agreement', 'rental'],
    'employment': ['employment', 'offer letter', 'appointment letter'],
    'service': ['service agreement', 'services agreement', 'consultancy', 'consulting'],
    'mou': ['memorandum of understanding', 'mou'],
    'sale': ['sale deed', 'sale agreement', 'purchase agreement'],
    'partnership': ['partnership'],
    'affidavit': ['affidavit'],
    'power of attorney': ['power of attorney'],
}
