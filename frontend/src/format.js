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

/** "just now", "5 min ago", "3 h ago", "yesterday", "4 days ago", then the date. */
export function fmtAgo(v) {
  if (!v) return ''
  const s = (Date.now() - new Date(v).getTime()) / 1000
  if (s < 60) return 'just now'
  if (s < 3600) return `${Math.floor(s / 60)} min ago`
  if (s < 86400) return `${Math.floor(s / 3600)} h ago`
  if (s < 172800) return 'yesterday'
  if (s < 7 * 86400) return `${Math.floor(s / 86400)} days ago`
  return fmtDate(v)
}

/** Group items with an ISO date into Today / Yesterday / Previous 7 days / Older. */
export function groupByDay(items, key = 'updated_at') {
  const start = new Date(); start.setHours(0, 0, 0, 0)
  const day = 86400000
  const groups = [['Today', []], ['Yesterday', []], ['Previous 7 days', []], ['Older', []]]
  for (const it of items) {
    const t = new Date(it[key]).getTime()
    const g = t >= start.getTime() ? 0 : t >= start.getTime() - day ? 1 : t >= start.getTime() - 7 * day ? 2 : 3
    groups[g][1].push(it)
  }
  return groups.filter(([, list]) => list.length).map(([name, list]) => ({ name, items: list }))
}
