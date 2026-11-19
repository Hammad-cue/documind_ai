import axios from 'axios'

export const API_BASE = import.meta.env.VITE_API_BASE || 'http://127.0.0.1:8000/api'

const api = axios.create({ baseURL: API_BASE })

api.interceptors.request.use(config => {
  const token = localStorage.getItem('access_token')
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

let refreshing = null
api.interceptors.response.use(
  r => r,
  async error => {
    const original = error.config
    const refresh = localStorage.getItem('refresh_token')
    if (error.response?.status === 401 && refresh && !original._retried && !original.url.includes('/auth/token')) {
      original._retried = true
      try {
        refreshing = refreshing || axios.post(`${API_BASE}/auth/token/refresh/`, { refresh })
        const { data } = await refreshing
        localStorage.setItem('access_token', data.access)
        return api(original)
      } catch {
        localStorage.removeItem('access_token')
        localStorage.removeItem('refresh_token')
        window.location.href = '/login'
      } finally {
        refreshing = null
      }
    }
    return Promise.reject(error)
  }
)

/**
 * POST and read the response as it arrives: one JSON object per line (used for streamed answers).
 * Calls onEvent(obj) for each line. Refreshes an expired session once, like the axios client.
 * Throws an Error with .status and .data when the server rejects the request.
 */
export async function postStream(path, body, onEvent, retried = false) {
  const res = await fetch(`${API_BASE}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${localStorage.getItem('access_token') || ''}` },
    body: JSON.stringify(body),
  })
  if (res.status === 401 && !retried && localStorage.getItem('refresh_token')) {
    try {
      refreshing = refreshing || axios.post(`${API_BASE}/auth/token/refresh/`, { refresh: localStorage.getItem('refresh_token') })
      const { data } = await refreshing
      localStorage.setItem('access_token', data.access)
    } finally { refreshing = null }
    return postStream(path, body, onEvent, true)
  }
  if (!res.ok || !res.body) {
    const err = new Error(`Request failed (${res.status})`)
    err.status = res.status
    try { err.data = await res.json() } catch { /* not JSON */ }
    err.response = { status: res.status, data: err.data }
    throw err
  }
  const reader = res.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  for (;;) {
    const { value, done } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })
    let nl
    while ((nl = buffer.indexOf('\n')) >= 0) {
      const line = buffer.slice(0, nl).trim()
      buffer = buffer.slice(nl + 1)
      if (line) onEvent(JSON.parse(line))
    }
  }
  if (buffer.trim()) onEvent(JSON.parse(buffer))
}

/** Turn a DRF error response into one readable sentence. */
export function errorText(e, fallback = 'Something went wrong.') {
  const d = e?.response?.data
  if (!d) return e?.message || fallback
  if (typeof d === 'string') return d.slice(0, 200)
  if (d.detail) return d.detail
  const first = Object.entries(d)[0]
  if (first) return `${first[0] === 'non_field_errors' ? '' : first[0] + ': '}${[].concat(first[1]).join(' ')}`
  return fallback
}

/** Download a protected file as an object URL (files are never public). */
export async function fileObjectUrl(documentId, version) {
  const { data } = await api.get(`/documents/${documentId}/file/`, {
    params: version ? { version } : {},
    responseType: 'blob',
  })
  return URL.createObjectURL(data)
}

export default api
