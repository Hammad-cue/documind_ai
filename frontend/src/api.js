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
