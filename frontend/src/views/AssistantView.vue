<template>
  <div class="relative flex h-full flex-col">
    <!-- history and a fresh start, always at hand -->
    <div class="pointer-events-none absolute inset-x-0 top-0 z-20 flex justify-end gap-2 px-4 pt-3 sm:px-6">
      <Transition name="fade">
        <button v-if="queries.length" type="button" class="glass-soft pointer-events-auto flex min-h-10 items-center gap-2 rounded-[12px] px-3 text-[13px] font-medium text-ink-2 transition hover:bg-white/85 hover:text-ink active:scale-[0.97]"
                @click="newQuestion">
          <SquarePen :size="15" aria-hidden="true" /><span class="hidden sm:inline">New question</span>
        </button>
      </Transition>
      <button type="button" class="glass-soft pointer-events-auto flex min-h-10 items-center gap-2 rounded-[12px] px-3 text-[13px] font-medium text-ink-2 transition hover:bg-white/85 hover:text-ink active:scale-[0.97]"
              aria-label="Your earlier questions" @click="historyOpen = true">
        <History :size="15" aria-hidden="true" /><span class="hidden sm:inline">History</span>
        <span v-if="session.conversations.length" class="rounded-full bg-black/5 px-1.5 text-[11px] font-semibold tabular-nums text-muted">{{ session.conversations.length }}</span>
      </button>
    </div>
    <HistoryDrawer :open="historyOpen" :current-id="convId" @close="historyOpen = false" />

    <!-- thread -->
    <div ref="thread" class="fade-top min-h-0 flex-1 overflow-y-auto scroll-thin">
      <div class="mx-auto max-w-[800px] px-4 pt-16 pb-44 sm:px-6">
        <!-- empty state -->
        <Transition name="rise" appear>
          <div v-if="!queries.length && !busy">
            <p class="text-[15px] font-medium text-muted">{{ greeting }}, {{ firstName }}</p>
            <h1 class="mt-1.5 text-[34px] leading-[1.1] font-bold tracking-[-0.035em] sm:text-[42px]">What do you need from the records?</h1>
            <p class="mt-3 max-w-xl text-[15px] text-muted">Ask for a date, a clause or a document. Every answer shows the page it came from, and only uses documents you can open.</p>
            <div class="stagger mt-9 grid gap-3 sm:grid-cols-2">
              <button v-for="ex in examples" :key="ex.q" type="button" @click="ask(ex.q)"
                      class="glass lift group rounded-[20px] p-4 text-left">
                <span class="flex items-center gap-2 text-xs font-semibold text-muted">
                  <component :is="ex.icon" :size="14" aria-hidden="true" />{{ ex.kind }}
                </span>
                <span class="mt-2 block text-[15px] font-medium text-ink">{{ ex.q }}</span>
              </button>
            </div>

            <div v-if="session.recent.length" class="mt-10">
              <div class="flex items-baseline justify-between gap-3">
                <h2 class="text-sm font-semibold text-muted">Pick up where you left off</h2>
                <button type="button" class="link text-[13px]" @click="historyOpen = true">All {{ session.conversations.length }} questions</button>
              </div>
              <div class="stagger mt-3 grid gap-2 sm:grid-cols-2">
                <router-link v-for="c in session.recent.slice(0, 4)" :key="c.id" :to="`/app/ask/${c.id}`"
                             class="glass-soft lift group flex min-w-0 items-center gap-3 rounded-[16px] px-4 py-3">
                  <MessageSquare :size="16" class="shrink-0 text-muted" aria-hidden="true" />
                  <span class="min-w-0 flex-1">
                    <span class="block truncate text-[14px] font-medium text-ink">{{ c.title || 'Untitled question' }}</span>
                    <span class="block text-xs text-muted">{{ fmtAgo(c.updated_at) }}</span>
                  </span>
                  <ChevronRight :size="16" class="shrink-0 text-muted transition-transform duration-200 group-hover:translate-x-0.5" aria-hidden="true" />
                </router-link>
              </div>
            </div>
          </div>
        </Transition>

        <!-- answers -->
        <div class="space-y-6">
          <TransitionGroup name="rise">
            <article v-for="q in queries" :key="q._key || q.id" class="panel p-6 sm:p-7">
              <div class="flex flex-wrap items-center gap-x-3 gap-y-1 text-[13px] font-medium text-muted">
                <span class="inline-flex items-center gap-2"><span class="h-2 w-2 rounded-full" :class="INTENT[q.intent]?.dot" aria-hidden="true" />{{ INTENT[q.intent]?.label }}</span>
                <span v-if="!q._streaming">{{ (q.latency_ms / 1000).toFixed(1) }} s</span>
                <span v-else class="inline-flex items-center gap-1.5 text-accent"><span class="h-3 w-3 animate-spin rounded-full border-2 border-current border-t-transparent" aria-hidden="true" />{{ q._stage }}</span>
                <span v-if="q.plan?.fallback" class="chip bg-warn-soft text-warn" :title="q.plan.fallback">Answered from the text</span>
                <span class="ml-auto flex items-center gap-1">
                  <button type="button" class="rounded-lg px-2 py-1 hover:bg-black/5 hover:text-ink" @click="q._plan = !q._plan">
                    {{ q._plan ? 'Hide details' : 'How this was answered' }}
                  </button>
                  <button type="button" aria-label="Copy answer with citations" title="Copy with citations"
                          class="flex h-8 w-8 items-center justify-center rounded-lg hover:bg-black/5 hover:text-ink" @click="copy(q)">
                    <Copy :size="15" />
                  </button>
                </span>
              </div>
              <Transition name="fade">
                <dl v-if="q._plan" class="mt-3 grid grid-cols-[auto_1fr] gap-x-4 gap-y-1 rounded-[14px] bg-white/70 p-3 text-xs">
                  <template v-for="(v, k) in planRows(q.plan)" :key="k"><dt class="text-muted">{{ k }}</dt><dd class="font-mono text-ink-2">{{ v }}</dd></template>
                </dl>
              </Transition>

              <h2 class="mt-3 text-[21px] leading-snug font-semibold tracking-[-0.02em]">{{ q.query }}</h2>

              <!-- comparison: one row per record, each value opens its page -->
              <div v-if="q.intent === 'COMPARE' && q.results.length && q.plan?.columns" class="mt-4 overflow-x-auto rounded-[20px] bg-white/75 scroll-thin">
                <table class="w-full min-w-[520px] text-left text-[14px]">
                  <thead>
                    <tr class="border-b border-line text-[12px] font-semibold text-muted">
                      <th scope="col" class="px-4 py-3 font-semibold">Record</th>
                      <th v-for="c in q.plan.columns" :key="c.key" scope="col" class="px-4 py-3 font-semibold">{{ c.label }}</th>
                    </tr>
                  </thead>
                  <tbody class="stagger divide-y divide-line">
                    <tr v-for="r in q.results" :key="r.document_id" class="align-top">
                      <th scope="row" class="px-4 py-3 font-semibold">
                        <button type="button" class="text-left hover:text-accent" @click="open(r.document_id, 1, '')">{{ r.document_title }}</button>
                        <span class="block text-[12px] font-normal text-muted">{{ r.doc_type }}</span>
                      </th>
                      <td v-for="c in q.plan.columns" :key="c.key" class="px-4 py-3">
                        <template v-if="r.cells[c.key]?.value">
                          <button type="button" class="group text-left" :title="r.cells[c.key].quote"
                                  @click="open(r.document_id, r.cells[c.key].page, r.cells[c.key].quote)">
                            <span class="font-medium text-ink group-hover:text-accent">{{ r.cells[c.key].value }}</span>
                            <span v-if="r.cells[c.key].page" class="ml-1.5 text-[12px] font-semibold whitespace-nowrap text-accent">p.{{ r.cells[c.key].page }}</span>
                          </button>
                          <span v-if="r.cells[c.key].status === 'NEEDS_REVIEW'" class="mt-1 block text-[11px] font-medium text-warn">Needs review</span>
                          <span v-else-if="r.cells[c.key].status === 'TEXT'" class="mt-1 block text-[11px] font-medium text-muted">Read from the text</span>
                        </template>
                        <span v-else class="text-muted">Not stated</span>
                      </td>
                    </tr>
                  </tbody>
                </table>
              </div>

              <!-- single record fact -->
              <div v-if="q.intent === 'LOOKUP' && q.results.length === 1" class="mt-4 flex flex-wrap items-end justify-between gap-4 rounded-[20px] bg-white/75 p-5">
                <div>
                  <div class="text-[13px] font-medium text-muted">{{ q.results[0].label }} · {{ q.results[0].document_title }}</div>
                  <div class="mt-1 text-[32px] leading-none font-bold tracking-[-0.03em]" :class="q._fresh && 'animate-pop'">{{ q.results[0].value }}</div>
                </div>
                <div class="flex items-center gap-2">
                  <StatusPill :status="q.results[0].status" />
                  <button type="button" class="btn-dark" @click="open(q.results[0].document_id, q.results[0].page, q.results[0].quote)">
                    Open page {{ q.results[0].page || '' }}<ArrowRight :size="16" aria-hidden="true" />
                  </button>
                </div>
              </div>

              <!-- several records -->
              <div v-else-if="q.intent === 'LOOKUP' && q.results.length" class="stagger mt-4 divide-y divide-line overflow-hidden rounded-[20px] bg-white/75">
                <button v-for="r in q.results" :key="r.field_id" type="button" @click="open(r.document_id, r.page, r.quote)"
                        class="flex w-full flex-wrap items-center gap-x-4 gap-y-1 px-5 py-3.5 text-left hover:bg-white">
                  <span class="min-w-0 flex-1"><span class="block font-semibold">{{ r.document_title }}</span><span class="block text-[13px] text-muted">{{ r.label }}</span></span>
                  <span class="text-[17px] font-semibold tabular-nums">{{ r.value }}</span>
                  <StatusPill :status="r.status" />
                  <span class="text-[13px] font-semibold text-accent">p.{{ r.page || '–' }}</span>
                </button>
              </div>

              <!-- written answer -->
              <div v-else-if="q._streaming && !q.answer" class="mt-4 space-y-2" aria-hidden="true">
                <div class="shimmer h-3.5 w-full rounded-md" /><div class="shimmer h-3.5 w-11/12 rounded-md" /><div class="shimmer h-3.5 w-3/5 rounded-md" />
              </div>
              <div v-else class="prose prose-slate dark:prose-invert mt-3 max-w-none text-[16px] leading-[1.7] text-ink-2 prose-p:my-2 prose-strong:text-ink prose-li:my-0.5"
                   :class="q._streaming && 'streaming-caret'" :aria-busy="q._streaming ? 'true' : null"
                   v-html="render(q)" v-reveal="q._fresh" @click="onAnswerClick($event, q)" />

              <!-- sources -->
              <div v-if="q.sources.length && q.intent !== 'LOOKUP' && q.intent !== 'COMPARE'" class="stagger mt-5 grid grid-cols-[minmax(0,1fr)] gap-2.5" :class="q.intent === 'SEARCH' ? 'sm:grid-cols-2' : ''">
                <button v-for="s in visibleSources(q)" :key="s.id" type="button" :id="`src-${q.id}-${s.id}`"
                        class="flex min-w-0 items-center gap-3.5 rounded-[18px] bg-white/70 p-3 text-left transition hover:bg-white"
                        @click="open(s.document_id, s.page, s.snippet)">
                  <PageThumb class="shrink-0" />
                  <span class="min-w-0 flex-1">
                    <span class="flex items-center gap-2">
                      <span v-if="q.intent === 'KNOWLEDGE'" class="flex h-5 min-w-5 items-center justify-center rounded-full bg-accent-soft px-1 text-[11px] font-bold text-accent">{{ s.id }}</span>
                      <span class="truncate text-[14px] font-semibold">{{ s.document_title }}</span>
                    </span>
                    <span class="mt-0.5 flex min-w-0 gap-1 text-[13px] text-muted" :title="s.section ? s.section.replaceAll(' > ', ' › ') : ''">
                      <span v-if="s.section" class="truncate">{{ s.section.replaceAll(' > ', ' › ') }} ·</span>
                      <span class="shrink-0">page {{ s.page }}</span>
                    </span>
                  </span>
                  <ChevronRight :size="18" class="shrink-0 text-muted" aria-hidden="true" />
                </button>
              </div>
              <button v-if="hiddenCount(q)" type="button" class="mt-2 rounded-lg px-2 py-1 text-[13px] font-medium text-muted hover:bg-black/5 hover:text-ink"
                      @click="q._allSources = true">
                Show {{ hiddenCount(q) }} more passage{{ hiddenCount(q) > 1 ? 's' : '' }} that were searched
              </button>
            </article>
          </TransitionGroup>

          <!-- thinking -->
          <div v-if="busy && !live" class="panel p-6 sm:p-7" aria-live="polite">
            <h2 class="text-[21px] leading-snug font-semibold tracking-[-0.02em]">{{ pending }}</h2>
            <ol class="mt-4 space-y-2.5">
              <li v-for="(s, i) in STEPS" :key="s" class="flex items-center gap-3 text-[14px] transition-opacity duration-300"
                  :class="i <= step ? 'opacity-100' : 'opacity-35'">
                <span class="flex h-6 w-6 items-center justify-center rounded-full" :class="i < step ? 'bg-ok-soft text-ok' : i === step ? 'bg-accent-soft text-accent' : 'bg-black/5 text-muted'" aria-hidden="true">
                  <Check v-if="i < step" :size="13" :stroke-width="2.6" class="animate-pop" />
                  <span v-else-if="i === step" class="h-3 w-3 animate-spin rounded-full border-2 border-current border-t-transparent" />
                  <span v-else class="h-1.5 w-1.5 rounded-full bg-current" />
                </span>
                <span :class="i === step ? 'font-medium text-ink' : 'text-ink-2'">{{ s }}</span>
              </li>
            </ol>
            <div class="mt-5 space-y-2"><div class="shimmer h-3.5 w-full rounded-md" /><div class="shimmer h-3.5 w-4/5 rounded-md" /></div>
          </div>
          <p v-if="error" class="rounded-[14px] bg-bad-soft px-4 py-3 text-sm text-bad">{{ error }}</p>
        </div>
      </div>
    </div>

    <!-- docked search bar -->
    <div class="pointer-events-none absolute inset-x-0 bottom-0 px-4 pb-5">
      <form class="glass-strong pointer-events-auto mx-auto flex max-w-[760px] items-center gap-2 rounded-[30px] py-2 pr-2 pl-5" @submit.prevent="ask()">
        <button type="button" :aria-label="scope.length ? 'Change which documents to search' : 'Choose documents to search'"
                :title="scope.length ? 'Change documents' : 'Search only some documents'"
                class="-ml-2 flex h-10 w-10 shrink-0 items-center justify-center rounded-full text-muted transition hover:bg-black/5 hover:text-ink" @click="openPicker">
          <Files v-if="!scope.length" :size="19" />
          <Search v-else :size="19" />
        </button>
        <span v-if="scope.length" class="chip animate-pop shrink-0 bg-accent-soft py-1 text-accent">
          <FileText :size="13" aria-hidden="true" />
          <button type="button" class="max-w-[160px] truncate" @click="openPicker">{{ scope.length === 1 ? scope[0].title : `${scope.length} documents` }}</button>
          <button type="button" aria-label="Search all documents instead" class="-mr-1 rounded-full p-0.5 hover:bg-accent/15" @click="clearScope"><X :size="13" /></button>
        </span>
        <label for="ask-input" class="sr-only">Ask the records</label>
        <input id="ask-input" ref="inputEl" v-model="input" :disabled="busy" autocomplete="off"
               :placeholder="scope.length === 1 ? 'Ask about this document…' : scope.length ? 'Ask about these documents…' : 'Ask about a contract, a date or a clause…'"
               class="min-h-11 min-w-0 flex-1 bg-transparent text-[17px] text-ink outline-none placeholder:text-muted/80" />
        <kbd class="hidden shrink-0 rounded-md border border-line px-1.5 py-0.5 text-xs text-muted sm:block" title="Press / to type here">/</kbd>
        <button type="submit" aria-label="Ask" :disabled="busy || !input.trim()"
                class="flex h-12 w-12 shrink-0 items-center justify-center rounded-full bg-accent text-on-accent shadow-[0_8px_20px_rgb(47_75_224/0.3)] transition hover:bg-accent-hover disabled:opacity-40">
          <ArrowUp :size="20" :stroke-width="2.2" />
        </button>
      </form>
    </div>

    <Modal :open="pickerOpen" title="Which documents should I search?" description="Answers will only use the documents you tick. Leave all unticked to search everything you can open." wide @close="pickerOpen = false">
      <div class="glass-soft flex min-h-11 items-center gap-2 rounded-[14px] px-3.5">
        <Search :size="16" class="text-muted" aria-hidden="true" />
        <label for="pick-filter" class="sr-only">Filter documents</label>
        <input id="pick-filter" v-model="pickFilter" placeholder="Filter by title or type" class="min-w-0 flex-1 bg-transparent text-sm outline-none" />
      </div>
      <ul class="mt-3 max-h-[46vh] space-y-1 overflow-y-auto pr-1 scroll-thin">
        <li v-for="d in pickable" :key="d.id">
          <label :class="['flex min-h-12 cursor-pointer items-center gap-3 rounded-[14px] px-3 transition', picked.has(d.id) ? 'bg-accent-soft' : 'hover:bg-white/70']">
            <input type="checkbox" :checked="picked.has(d.id)" class="h-4 w-4 accent-accent" @change="togglePick(d)" />
            <span class="min-w-0 flex-1">
              <span class="block truncate text-sm font-semibold">{{ d.title }}</span>
              <span class="block truncate text-xs text-muted">{{ d.doc_type || d.kind.toLowerCase() }}</span>
            </span>
            <span class="chip bg-black/5 text-ink-2">{{ d.kind === 'REFERENCE' ? 'Reference' : 'Record' }}</span>
          </label>
        </li>
        <li v-if="!pickable.length" class="py-8 text-center text-sm text-muted">No documents match.</li>
      </ul>
      <div class="mt-5 flex items-center justify-between gap-2">
        <span class="text-[13px] text-muted">{{ picked.size ? `${picked.size} selected` : 'Searching everything' }}</span>
        <div class="flex gap-2">
          <button type="button" class="btn-ghost" @click="picked = new Map()">Clear</button>
          <button type="button" class="btn-primary" @click="applyPick">Done</button>
        </div>
      </div>
    </Modal>
  </div>
</template>

<script setup>
import { ArrowRight, ArrowUp, CalendarClock, Check, ChevronRight, Copy, FileSearch, FileText, Files, History, MessageSquare, ScrollText, Search, SquarePen, Table2, X } from '@lucide/vue'
import DOMPurify from 'dompurify'
import { marked } from 'marked'
import { computed, nextTick, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import api, { errorText, postStream } from '../api'
import HistoryDrawer from '../components/HistoryDrawer.vue'
import Modal from '../components/Modal.vue'
import { fmtAgo } from '../format'
import PageThumb from '../components/PageThumb.vue'
import StatusPill from '../components/StatusPill.vue'
import { loadRecent, session } from '../session'
import { toast } from '../toast'

/** v-reveal: fade a freshly arrived answer in word by word. */
const vReveal = {
  mounted(el, { value }) {
    if (!value) return
    const walker = document.createTreeWalker(el, NodeFilter.SHOW_TEXT)
    const nodes = []
    while (walker.nextNode()) nodes.push(walker.currentNode)
    let i = 0
    for (const node of nodes) {
      const frag = document.createDocumentFragment()
      for (const part of node.textContent.split(/(\s+)/)) {
        if (!part) continue
        if (/^\s+$/.test(part)) { frag.appendChild(document.createTextNode(part)); continue }
        const span = document.createElement('span')
        span.className = 'reveal-word'
        span.style.animationDelay = `${Math.min(i++ * 22, 1600)}ms`
        span.textContent = part
        frag.appendChild(span)
      }
      node.parentNode.replaceChild(frag, node)
    }
  },
}

const STEPS = ['Understanding your question', 'Checking which documents you can open', 'Reading the relevant pages', 'Writing the answer with citations']
const step = ref(0)
let stepTimers = []

const route = useRoute()
const router = useRouter()
const queries = ref([])
const convId = ref(null)
const input = ref('')
const busy = ref(false)
const pending = ref('')
const live = ref(null)      // the answer currently being written
const error = ref('')
const thread = ref(null)
const inputEl = ref(null)
const scope = ref(route.query.doc ? [{ id: Number(route.query.doc), title: route.query.title || 'Selected document' }] : [])
const historyOpen = ref(false)

function newQuestion() {
  if (busy.value) return
  convId.value = null
  queries.value = []
  error.value = ''
  if (route.params.conversationId) router.push('/app/ask')
  nextTick(() => inputEl.value?.focus())
}

/* ---- choose which documents to search ---- */
const pickerOpen = ref(false)
const pickFilter = ref('')
const allDocs = ref([])
const picked = ref(new Map())
const pickable = computed(() => {
  const f = pickFilter.value.trim().toLowerCase()
  return allDocs.value.filter(d => d.status === 'READY' && (!f || d.title.toLowerCase().includes(f) || (d.doc_type || '').toLowerCase().includes(f)))
})
async function openPicker() {
  picked.value = new Map(scope.value.map(d => [d.id, d]))
  pickFilter.value = ''
  pickerOpen.value = true
  if (!allDocs.value.length) allDocs.value = (await api.get('/documents/')).data
}
function togglePick(d) {
  const m = new Map(picked.value)
  m.has(d.id) ? m.delete(d.id) : m.set(d.id, { id: d.id, title: d.title })
  picked.value = m
}
function applyPick() {
  scope.value = [...picked.value.values()]
  pickerOpen.value = false
  nextTick(() => inputEl.value?.focus())
}

const INTENT = {
  LOOKUP: { label: 'From the records register', dot: 'bg-[#7C5CFF]' },
  KNOWLEDGE: { label: 'Answered from documents', dot: 'bg-accent' },
  SEARCH: { label: 'Document search', dot: 'bg-[#0E9F8E]' },
  COMPARE: { label: 'Compared across records', dot: 'bg-[#E08A2F]' },
}
const examples = [
  { kind: 'Record lookup', icon: CalendarClock, q: 'When was the NDA with Acme signed?' },
  { kind: 'Compare records', icon: Table2, q: 'Compare the termination notice in all our NDAs' },
  { kind: 'From the law & policies', icon: ScrollText, q: 'Is an agreement without consideration valid?' },
  { kind: 'Find a document', icon: FileSearch, q: 'Find the lease for the Lahore office' },
]

const firstName = computed(() => session.me?.first_name || session.me?.username || '')
const greeting = computed(() => {
  const h = new Date().getHours()
  return h < 12 ? 'Good morning' : h < 18 ? 'Good afternoon' : 'Good evening'
})

/** Knowledge answers: show the passages the answer actually cites; the rest on request. */
function citedIds(q) {
  return new Set([...(q.answer || '').matchAll(/\[(\d{1,2})\]/g)].map(m => +m[1]))
}
function visibleSources(q) {
  if (q.intent === 'SEARCH') return q.sources.slice(0, 8)
  if (q._allSources) return q.sources
  const cited = citedIds(q)
  const list = q.sources.filter(s => cited.has(s.id))
  return list.length ? list : q.sources.slice(0, 2)
}
function hiddenCount(q) {
  return q.intent === 'KNOWLEDGE' ? q.sources.length - visibleSources(q).length : 0
}

function planRows(plan) {
  const rows = {}
  for (const k of ['intent', 'doc_type', 'party', 'field', 'fields', 'records', 'aspect', 'date_from', 'date_to', 'keywords', 'method', 'fallback']) {
    const v = plan?.[k]
    if (Array.isArray(v) ? v.length : v) rows[k] = Array.isArray(v) ? v.join(', ') : v
  }
  return rows
}

/** Markdown -> safe HTML; [n] citations become small clickable pills. */
function render(q) {
  const html = DOMPurify.sanitize(marked.parse(q.answer || ''))
  if (q.intent !== 'KNOWLEDGE' && q.intent !== 'COMPARE') return html
  return html.replace(/\[(\d{1,2})\]/g, (m, n) =>
    q.sources.some(s => s.id === +n)
      ? `<a href="#" data-cite="${n}" class="not-prose mx-0.5 inline-flex h-5 min-w-5 items-center justify-center rounded-full bg-accent-soft px-1.5 align-[2px] text-[11px] font-bold text-accent no-underline hover:bg-accent/25">${n}</a>`
      : m)
}

function onAnswerClick(e, q) {
  const n = e.target?.closest?.('[data-cite]')?.dataset?.cite
  if (!n) return
  e.preventDefault()
  const s = q.sources.find(x => x.id === +n)
  if (s) open(s.document_id, s.page, s.snippet)
}

function open(documentId, page, snippet) {
  router.push({ path: `/app/documents/${documentId}`, query: { page: page || 1, hl: (snippet || '').slice(0, 400) } })
}

async function loadConversation(id) {
  if (!id) { convId.value = null; queries.value = []; return }
  try {
    const { data } = await api.get(`/assistant/conversations/${id}/`)
    convId.value = data.id
    queries.value = data.queries
    scrollDown(false)
  } catch { router.replace('/app/ask') }
}

async function ask(text) {
  const q = (text ?? input.value).trim()
  if (!q || busy.value) return
  input.value = ''
  pending.value = q
  busy.value = true
  error.value = ''
  step.value = 0
  stepTimers = [600, 1400].map((ms, i) => setTimeout(() => { step.value = Math.max(step.value, i + 1) }, ms))
  scrollDown()
  let entry = null
  let frame = 0
  try {
    // The answer arrives as events: plan -> sources -> pieces of text -> done (saved to history).
    await postStream('/assistant/ask/stream/', {
      query: q, conversation_id: convId.value, document_ids: scope.value.map(d => d.id),
    }, ev => {
      if (ev.type === 'plan') {
        if (!entry) {
          entry = reactive({ _key: `live-${Date.now()}`, id: null, query: q, intent: ev.intent, plan: ev.plan, answer: '',
                             sources: [], results: [], latency_ms: 0, _streaming: true, _stage: 'Reading the relevant pages' })
          queries.value.push(entry)
          live.value = entry
          scrollDown()
        } else {
          entry.intent = ev.intent
          entry.plan = ev.plan
        }
      } else if (ev.type === 'sources') {
        entry.sources = ev.sources
        entry.results = ev.results
        entry._stage = 'Writing the answer'
      } else if (ev.type === 'delta') {
        entry.answer += ev.text
        cancelAnimationFrame(frame)
        frame = requestAnimationFrame(() => scrollDown(false))
      } else if (ev.type === 'done') {
        const { type, ...saved } = ev
        Object.assign(entry, saved, { _streaming: false, _fresh: saved.intent === 'LOOKUP' })
        if (convId.value !== saved.conversation_id) {
          convId.value = saved.conversation_id
          router.replace({ path: `/app/ask/${saved.conversation_id}`, query: route.query })
        }
      } else if (ev.type === 'error') {
        throw new Error(ev.message)
      }
    })
    if (entry?._streaming) throw new Error('The answer stopped before it finished. Please ask again.')
    loadRecent()
  } catch (e) {
    if (entry && !entry.answer) queries.value = queries.value.filter(x => x !== entry)
    else if (entry) entry._streaming = false
    error.value = e.status === 429 ? 'You are asking a little too quickly. Wait a moment and try again.' : errorText(e)
    if (!entry?.answer) input.value = q
  } finally {
    stepTimers.forEach(clearTimeout)
    busy.value = false
    live.value = null
    scrollDown()
    nextTick(() => inputEl.value?.focus())
  }
}

/** Copy the answer as plain text with its sources listed underneath. */
async function copy(q) {
  const cell = c => c?.value ? `${c.value}${c.page ? ` (page ${c.page})` : ''}` : 'Not stated'
  const answer = q.intent === 'LOOKUP' && q.results.length
    ? q.results.map(r => `${r.document_title} — ${r.label}: ${r.value}${r.page ? ` (page ${r.page})` : ''}`).join('\n')
    : q.intent === 'COMPARE' && q.results.length && q.plan?.columns
      ? q.results.map(r => `${r.document_title}\n` + q.plan.columns.map(c => `  ${c.label}: ${cell(r.cells[c.key])}`).join('\n')).join('\n')
        + '\n\n' + (q.answer || '').replace(/\*\*/g, '').replace(/\s*\[\d{1,2}\]/g, '')
      : (q.answer || '').replace(/\*\*/g, '')
  const sources = q.intent === 'KNOWLEDGE'
    ? '\n\nSources:\n' + visibleSources(q).map(s => `[${s.id}] ${s.document_title}${s.section ? ', ' + s.section.replaceAll(' > ', ' › ') : ''}, page ${s.page}`).join('\n')
    : ''
  const text = `${q.query}\n\n${answer}${sources}`
  try {
    await navigator.clipboard.writeText(text)
    toast('Copied with citations')
  } catch {
    // fallback for browsers / unfocused windows that block the async clipboard API
    const ta = Object.assign(document.createElement('textarea'), { value: text })
    ta.style.cssText = 'position:fixed;opacity:0'
    document.body.appendChild(ta)
    ta.select()
    const ok = document.execCommand('copy')
    ta.remove()
    ok ? toast('Copied with citations') : toast('Could not copy to the clipboard', { tone: 'bad' })
  }
}

function askFromRoute() {
  const text = route.query.q
  if (!text) return
  const { q, ...rest } = route.query
  router.replace({ path: '/app/ask', query: rest })
  convId.value = null
  queries.value = []
  ask(String(text))
}

function clearScope() {
  scope.value = []
  const { doc, title, ...rest } = route.query
  router.replace({ query: rest })
}

async function scrollDown(smooth = true) {
  await nextTick()
  thread.value?.scrollTo({ top: thread.value.scrollHeight, behavior: smooth ? 'smooth' : 'auto' })
}

function onKey(e) {
  const typing = /^(INPUT|TEXTAREA|SELECT)$/.test(document.activeElement?.tagName) || document.activeElement?.isContentEditable
  if (e.key === '/' && !typing && !e.ctrlKey && !e.metaKey) { e.preventDefault(); inputEl.value?.focus() }
}

watch(() => route.params.conversationId, id => { if (!route.query.q && Number(id) !== convId.value) loadConversation(id ? Number(id) : null) })
watch(() => route.query.q, askFromRoute)
onMounted(() => {
  if (route.query.q) askFromRoute()
  else loadConversation(route.params.conversationId ? Number(route.params.conversationId) : null)
  window.addEventListener('keydown', onKey)
  inputEl.value?.focus()
})
onBeforeUnmount(() => { window.removeEventListener('keydown', onKey); stepTimers.forEach(clearTimeout) })
</script>
