<template>
  <section aria-label="Document viewer" class="glass-soft relative flex h-full min-h-[420px] flex-col overflow-hidden rounded-[26px]">
    <div ref="scroller" class="min-h-0 flex-1 overflow-auto px-4 pt-6 pb-24 scroll-thin sm:px-8">
      <div v-if="loading" class="mx-auto aspect-[1/1.3] max-w-[620px] animate-pulse rounded-[12px] bg-white/70" />
      <p v-else-if="error" class="mx-auto max-w-md rounded-[14px] bg-bad-soft p-4 text-sm text-bad">{{ error }}</p>

      <div v-else-if="fileType === 'PDF'" class="mx-auto max-w-[680px] overflow-hidden rounded-[10px] bg-white shadow-[var(--shadow-paper)]">
        <VuePdfEmbed :source="url" :page="page" text-layer @loaded="onLoaded" @rendered="onRendered" />
      </div>
      <img v-else-if="fileType === 'IMAGE'" :src="url" alt="Scanned page" class="mx-auto max-w-full rounded-[10px] bg-white shadow-[var(--shadow-paper)]" />
      <div v-else class="mx-auto max-w-[680px] space-y-5">
        <div v-for="p in textPages" :key="p.number" :id="`textpage-${p.number}`"
             :class="['rounded-[10px] bg-white p-10 text-[14px] leading-relaxed whitespace-pre-wrap text-ink-2 shadow-[var(--shadow-paper)] transition', p.number === page ? 'ring-4 ring-mark' : '']">{{ p.text }}</div>
      </div>
    </div>

    <!-- floating controls -->
    <div class="glass-strong absolute bottom-4 left-1/2 flex -translate-x-1/2 items-center gap-1 rounded-[18px] p-1.5 text-sm">
      <template v-if="fileType === 'PDF' && pageCount">
        <button type="button" aria-label="Previous page" :disabled="page <= 1" @click="go(page - 1)"
                class="flex h-10 w-10 items-center justify-center rounded-[12px] hover:bg-black/5 disabled:opacity-30"><ChevronLeft :size="18" /></button>
        <span class="px-2 font-semibold tabular-nums">{{ page }} / {{ pageCount }}</span>
        <button type="button" aria-label="Next page" :disabled="page >= pageCount" @click="go(page + 1)"
                class="flex h-10 w-10 items-center justify-center rounded-[12px] hover:bg-black/5 disabled:opacity-30"><ChevronRight :size="18" /></button>
        <span class="mx-1 h-6 w-px bg-black/10" aria-hidden="true" />
      </template>
      <span v-else class="px-3 text-[13px] text-muted">{{ fileType === 'DOCX' ? 'Word document · extracted text' : 'Scanned image' }}</span>
      <button type="button" aria-label="Download file" title="Download" @click="download"
              class="flex h-10 w-10 items-center justify-center rounded-[12px] hover:bg-black/5"><Download :size="17" /></button>
    </div>
  </section>
</template>

<script setup>
import { ChevronLeft, ChevronRight, Download } from '@lucide/vue'
import { nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import VuePdfEmbed from 'vue-pdf-embed'
import 'vue-pdf-embed/dist/styles/textLayer.css'
import api, { fileObjectUrl } from '../api'

const props = defineProps({
  documentId: { type: Number, required: true },
  version: { type: Number, default: null },
  fileType: { type: String, default: 'PDF' },
  filename: { type: String, default: 'document' },
  page: { type: Number, default: 1 },
  highlight: { type: String, default: '' },
})
const emit = defineEmits(['update:page'])

const url = ref(null)
const loading = ref(true)
const error = ref('')
const pageCount = ref(0)
const textPages = ref([])
const scroller = ref(null)

async function load() {
  loading.value = true
  error.value = ''
  if (url.value) URL.revokeObjectURL(url.value)
  url.value = null
  try {
    if (props.fileType === 'DOCX') {
      textPages.value = (await api.get(`/documents/${props.documentId}/pages/`, { params: props.version ? { version: props.version } : {} })).data
    } else {
      url.value = await fileObjectUrl(props.documentId, props.version)
    }
  } catch (e) {
    error.value = e.response?.status === 404 ? 'File not found, or you do not have access to it.' : 'Could not load the file.'
  } finally {
    loading.value = false
  }
}

function onLoaded(doc) { pageCount.value = doc.numPages }
function go(n) {
  if (!n || n < 1 || (pageCount.value && n > pageCount.value)) return
  emit('update:page', n)
}

// The PDF text layer is filled after the canvas: re-apply the highlight whenever it changes.
let observer = null
let debounce = null
function onRendered() { applyHighlight() }
onMounted(() => {
  observer = new MutationObserver(muts => {
    if (muts.some(m => m.target.closest?.('.textLayer') || [...m.addedNodes].some(n => n.classList?.contains('textLayer')))) {
      clearTimeout(debounce)
      debounce = setTimeout(applyHighlight, 60)
    }
  })
  observer.observe(scroller.value, { childList: true, subtree: true })
})

const norm = s => (s || '').toLowerCase().replace(/[^a-z0-9]+/g, ' ').trim()

/** [start, end) of the cited passage inside the page text, or null. The passage may run past the page or differ
 * slightly (hyphenation, page breaks), so when it is not found whole, its first and last words are used as anchors. */
function findRegion(full, target) {
  if (!full || target.length < 4) return null
  const whole = full.indexOf(target)
  if (whole >= 0) return [whole, whole + target.length]
  const words = target.split(' ')
  for (const n of [8, 6, 4]) {
    if (words.length < n) continue
    const head = words.slice(0, n).join(' ')
    const start = full.indexOf(head)
    if (start < 0) continue
    const tail = words.slice(-n).join(' ')
    const tailAt = full.indexOf(tail, start + head.length)
    const end = tailAt >= 0 ? tailAt + tail.length : Math.min(full.length, start + target.length)
    return [start, end]
  }
  for (const n of [8, 6]) {   // passage started on the previous page: anchor on its last words
    if (words.length < n) continue
    const tail = words.slice(-n).join(' ')
    const at = full.indexOf(tail)
    if (at >= 0) return [Math.max(0, at + tail.length - target.length), at + tail.length]
  }
  return null
}

/** Mark text-layer spans that belong to the cited passage. */
function applyHighlight() {
  if (!props.highlight || !scroller.value) return
  const target = norm(props.highlight)
  // Join the text layer into one string, remember where each span sits in it, then find the cited passage as a
  // whole. Matching span by span would light up every short word ("this", "void") that also occurs in the quote.
  const spans = [...scroller.value.querySelectorAll('.textLayer span')]
  let full = ''
  const ranges = spans.map(span => {
    const t = norm(span.textContent)
    if (!t) return null
    if (full) full += ' '
    const start = full.length
    full += t
    return [start, full.length]
  })
  const region = findRegion(full, target)
  let first = null
  spans.forEach((span, i) => {
    const r = ranges[i]
    const hit = !!(region && r && r[0] < region[1] && r[1] > region[0])
    span.style.backgroundColor = hit ? 'rgba(255, 214, 102, 0.55)' : ''
    span.style.borderRadius = hit ? '3px' : ''
    if (hit) first = first || span
  })
  if (first) first.scrollIntoView({ block: 'center', behavior: 'smooth' })
}

async function download() {
  const { data } = await api.get(`/documents/${props.documentId}/file/`, {
    params: { download: 1, ...(props.version ? { version: props.version } : {}) }, responseType: 'blob' })
  const a = document.createElement('a')
  a.href = URL.createObjectURL(data)
  a.download = props.filename
  a.click()
  URL.revokeObjectURL(a.href)
}

watch(() => [props.documentId, props.version, props.fileType], load, { immediate: true })
watch(() => props.highlight, () => nextTick(applyHighlight))
watch(() => props.page, async n => {
  if (props.fileType === 'DOCX') {
    await nextTick()
    document.getElementById(`textpage-${n}`)?.scrollIntoView({ behavior: 'smooth' })
  }
})
onBeforeUnmount(() => { observer?.disconnect(); if (url.value) URL.revokeObjectURL(url.value) })
</script>
