import { reactive } from 'vue'
import api from './api'

export const session = reactive({
  me: null,
  loading: false,
  recent: [],        // latest conversations, shown in the sidebar
  reviewCount: 0,    // fields waiting in the review queue
})

export async function loadMe(force = false) {
  if (session.me && !force) return session.me
  if (!localStorage.getItem('access_token')) return null
  session.loading = true
  try {
    const { data } = await api.get('/auth/me/')
    session.me = data
  } catch {
    session.me = null
  } finally {
    session.loading = false
  }
  return session.me
}

export async function loadRecent() {
  try {
    session.recent = (await api.get('/assistant/conversations/')).data.slice(0, 6)
  } catch { /* sidebar extra; ignore */ }
}

export async function loadReviewCount() {
  if (!session.me?.can?.verify) return
  try {
    session.reviewCount = (await api.get('/records/review-queue/')).data.length
  } catch { /* ignore */ }
}

export function logout() {
  localStorage.removeItem('access_token')
  localStorage.removeItem('refresh_token')
  session.me = null
  session.recent = []
  session.reviewCount = 0
}

export const can = perm => !!session.me?.can?.[perm]

/* ---- per-viewer display preferences (best effort: storage may be unavailable) ---- */
function readPref(key, fallback) {
  try { return localStorage.getItem(key) ?? fallback } catch { return fallback }
}
export const BACKDROPS = [
  { value: 'grain', label: 'Paper grain' },
  { value: 'dots', label: 'Dot grid' },
  { value: 'plain', label: 'Plain' },
]
const storedBackdrop = readPref('dm-backdrop', 'grain')
export const prefs = reactive({ backdrop: BACKDROPS.some(b => b.value === storedBackdrop) ? storedBackdrop : 'grain' })
export function setBackdrop(value) {
  prefs.backdrop = value
  try { localStorage.setItem('dm-backdrop', value) } catch { /* ignore */ }
}
