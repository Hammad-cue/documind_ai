import { reactive } from 'vue'
import api from './api'

export const session = reactive({
  me: null,
  loading: false,
  conversations: [], // the user's question history, newest first (Ask screen history panel)
  recent: [],        // the latest few, shown on the Ask screen and in the command palette
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
    session.conversations = (await api.get('/assistant/conversations/')).data
    session.recent = session.conversations.slice(0, 6)
  } catch { /* history is an extra; ignore */ }
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
  session.conversations = []
  session.reviewCount = 0
}

export const can = perm => !!session.me?.can?.[perm]

/* ---- per-viewer display preferences (best effort: storage may be unavailable) ---- */
function readPref(key, fallback) {
  try { return localStorage.getItem(key) ?? fallback } catch { return fallback }
}
export const BACKDROPS = [
  { value: 'contours', label: 'Contours', note: 'A slowly shifting topographic map', moving: true },
  { value: 'constellation', label: 'Constellation', note: 'Drifting points joined by fine lines; blue near the pointer', moving: true },
  { value: 'grid', label: 'Living grid', note: 'Dots that breathe in slow waves and swell under the pointer', moving: true },
  { value: 'flow', label: 'Flow lines', note: 'Fine threads moved by a slow current', moving: true },
  { value: 'grain', label: 'Paper grain', note: 'A very fine paper texture' },
  { value: 'dots', label: 'Dot grid', note: 'Faint, still dots' },
  { value: 'plain', label: 'Plain', note: 'Flat background' },
]
export const THEMES = [
  { value: 'light', label: 'Light' },
  { value: 'dark', label: 'Dark' },
  { value: 'system', label: 'Match device' },
]
const storedBackdrop = readPref('dm-backdrop', 'contours')
const storedTheme = readPref('dm-theme', 'dark')
export const prefs = reactive({
  backdrop: BACKDROPS.some(b => b.value === storedBackdrop) ? storedBackdrop : 'contours',
  theme: THEMES.some(t => t.value === storedTheme) ? storedTheme : 'dark',   // what the person chose
  mode: 'dark',                                                             // what is shown: light or dark
})
export function setBackdrop(value) {
  prefs.backdrop = value
  try { localStorage.setItem('dm-backdrop', value) } catch { /* ignore */ }
}

/* ---- light / dark mode: data-theme on <html> switches every colour token (style.css) ---- */
const deviceDark = window.matchMedia?.('(prefers-color-scheme: dark)')
function applyTheme(fade = false) {
  const mode = prefs.theme === 'system' ? (deviceDark?.matches ? 'dark' : 'light') : prefs.theme
  const root = document.documentElement
  if (fade && !window.matchMedia?.('(prefers-reduced-motion: reduce)').matches) {
    root.classList.add('theme-fade')
    setTimeout(() => root.classList.remove('theme-fade'), 450)
  }
  root.dataset.theme = mode
  document.querySelector('meta[name="theme-color"]')?.setAttribute('content', mode === 'dark' ? '#0B0E15' : '#F3F4F8')
  prefs.mode = mode
}
export function setTheme(value) {
  prefs.theme = value
  try { localStorage.setItem('dm-theme', value) } catch { /* ignore */ }
  applyTheme(true)
}
deviceDark?.addEventListener?.('change', () => { if (prefs.theme === 'system') applyTheme(true) })
applyTheme()
