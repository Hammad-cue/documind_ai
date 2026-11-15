export const fmtDate = v => (v ? new Date(v).toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' }) : '—')
export const fmtDateTime = v => (v ? new Date(v).toLocaleString('en-GB', { day: 'numeric', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit' }) : '—')
export const fmtSize = b => (b > 1048576 ? `${(b / 1048576).toFixed(1)} MB` : `${Math.max(1, Math.round(b / 1024))} KB`)

/** ISO date strings (YYYY-MM-DD) shown as "12 Mar 2025"; anything else unchanged. */
export const fmtValue = v => (/^\d{4}-\d{2}-\d{2}$/.test(v || '') ? fmtDate(v + 'T00:00:00') : v)

export const ACCESS_LABELS = { ORG: 'Everyone', DEPARTMENT: 'Department', RESTRICTED: 'Chosen people' }
export const KIND_LABELS = { RECORD: 'Record', REFERENCE: 'Reference', UNKNOWN: 'Classifying…' }

export const FIELD_OPTIONS = [
  ['parties', 'Parties'], ['effective_date', 'Effective date'], ['signed_date', 'Signing date'],
  ['expiry_date', 'Expiry / end date'], ['term', 'Term / duration'], ['auto_renewal', 'Auto-renewal'],
  ['notice_period', 'Termination notice period'], ['governing_law', 'Governing law'],
  ['contract_value', 'Contract value'], ['reference_number', 'Reference number'], ['signatories', 'Signatories'],
]
