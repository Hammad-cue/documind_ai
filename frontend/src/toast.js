import { reactive } from 'vue'

/** Tiny toast store: toast('Fact verified') or toast('Upload failed', { tone: 'bad' }). */
export const toasts = reactive([])
let seq = 0

export function toast(message, { tone = 'ok', detail = '', ms = 3200 } = {}) {
  const id = ++seq
  toasts.push({ id, message, tone, detail })
  setTimeout(() => dismiss(id), ms)
  return id
}

export function dismiss(id) {
  const i = toasts.findIndex(t => t.id === id)
  if (i >= 0) toasts.splice(i, 1)
}
