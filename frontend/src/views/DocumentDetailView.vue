<template>
  <div v-if="doc" class="flex h-full flex-col gap-4 overflow-y-auto px-4 pt-6 pb-4 scroll-thin sm:px-6 lg:overflow-hidden lg:pt-4 lg:pr-0 lg:pl-2">
    <!-- header -->
    <header class="flex flex-wrap items-center gap-x-4 gap-y-3">
      <!-- the title keeps at least ~420px; when the row is too narrow the tabs and buttons wrap below together -->
      <div class="min-w-[min(100%,420px)] flex-1">
        <router-link to="/app/documents" class="inline-flex items-center gap-1 text-[13px] font-medium text-muted hover:text-ink">
          <ChevronLeft :size="15" aria-hidden="true" />Documents<span v-if="doc.department_name"> / {{ doc.department_name }}</span>
        </router-link>
        <h1 class="mt-1 truncate text-[28px] leading-tight font-bold tracking-[-0.03em]">{{ doc.title }}</h1>
        <div class="mt-1 flex flex-wrap items-center gap-x-2 gap-y-1 text-[13px] text-muted">
          <span>{{ doc.doc_type || KIND_LABELS[doc.kind] }}</span><span aria-hidden="true">·</span>
          <span class="inline-flex items-center gap-1"><component :is="ACCESS_ICON[doc.access_level]" :size="13" aria-hidden="true" />{{ ACCESS_LABELS[doc.access_level] }}</span>
          <span aria-hidden="true">·</span>
          <span>Version {{ viewVersion }}<span v-if="doc.current_version_number && viewVersion !== doc.current_version_number"> (current is {{ doc.current_version_number }})</span></span>
        </div>
      </div>
      <div class="ml-auto flex flex-wrap items-center gap-3">
      <Segmented v-model="tab" label="Document sections" :options="tabs" />
      <div class="flex items-center gap-2">
        <button v-if="doc.can_edit" type="button" class="btn-ghost w-11 px-0" aria-label="Settings and access" title="Settings and access" @click="showSettings = true"><Settings2 :size="18" /></button>
        <button v-if="doc.can_edit" type="button" class="btn-ghost" @click="showUpload = true"><Upload :size="16" aria-hidden="true" />New version</button>
        <router-link :to="{ path: '/app/ask', query: { doc: doc.id, title: doc.title } }" class="btn-dark"><Search :size="16" aria-hidden="true" />Ask about it</router-link>
      </div>
      </div>
    </header>

    <Transition name="fade">
      <div v-if="latest && latest.status !== 'READY'" :class="['flex items-center gap-3 rounded-[16px] px-4 py-3 text-sm', latest.status === 'FAILED' ? 'bg-bad-soft text-bad' : 'glass-soft text-ink-2']">
        <template v-if="latest.status === 'FAILED'">
          <TriangleAlert :size="17" aria-hidden="true" /><span class="flex-1">Processing failed: {{ latest.error }}</span>
          <button v-if="doc.can_edit" type="button" class="btn-ghost min-h-9" @click="reprocess"><RotateCw :size="15" />Try again</button>
        </template>
        <template v-else>
          <span class="h-2 w-2 animate-pulse rounded-full bg-accent" aria-hidden="true" />
          Reading version {{ latest.number }} — recognising text, splitting it into sections and pulling out the key facts. This updates by itself.
        </template>
      </div>
    </Transition>

    <div class="grid min-h-0 flex-1 gap-4 lg:grid-cols-[minmax(0,1fr)_400px]">
      <div class="h-[70vh] min-h-0 lg:h-auto">
        <DocumentViewer :document-id="doc.id" :version="viewVersion" :file-type="viewVersionObj?.file_type"
                        :filename="viewVersionObj?.original_filename" v-model:page="page" :highlight="highlight" />
      </div>

      <aside class="panel min-h-0 overflow-y-auto p-5 scroll-thin lg:mr-4">
        <!-- FACTS -->
        <div v-if="tab === 'facts'">
          <p v-if="doc.summary" class="text-[14px] leading-relaxed text-ink-2">{{ doc.summary }}</p>

          <template v-if="doc.kind === 'RECORD'">
            <div class="mt-5 mb-2 flex items-baseline justify-between">
              <h2 class="text-[15px] font-semibold">Key facts</h2>
              <span class="text-xs text-muted">Select one to see where it came from</span>
            </div>
            <p v-if="!doc.record_fields.length" class="rounded-[16px] bg-white/60 p-4 text-sm text-muted">No facts extracted yet.</p>
            <ul class="space-y-1.5">
              <li v-for="f in doc.record_fields" :key="f.id">
                <div :class="['rounded-[16px] transition', selected === f.id ? 'bg-white shadow-[0_6px_20px_rgb(28_38_90/0.08)]' : 'hover:bg-white/60']">
                  <button type="button" class="flex w-full items-start gap-3 px-3.5 py-3 text-left" :aria-expanded="selected === f.id" @click="selectField(f)">
                    <span class="min-w-0 flex-1">
                      <span class="block text-xs font-medium text-muted">{{ f.label }}</span>
                      <span class="mt-0.5 block font-semibold break-words text-ink">{{ fmtValue(f.value_text) }}</span>
                    </span>
                    <StatusPill :status="f.status" class="mt-0.5 shrink-0" />
                  </button>
                  <div v-if="selected === f.id" class="px-3.5 pb-3.5">
                    <p v-if="f.source_quote" class="rounded-[12px] bg-mark/40 px-3 py-2 text-[13px] leading-relaxed text-ink-2">“{{ f.source_quote }}”</p>
                    <p v-if="f.status === 'NEEDS_REVIEW' && f.review_reason && /^(Calculated|Second check)/.test(f.review_reason)" class="rounded-[12px] bg-warn-soft/60 px-3 py-2 text-[13px] leading-relaxed text-ink-2">{{ f.review_reason }}</p>
                    <div class="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-muted">
                      <span v-if="f.source_page">Page {{ f.source_page }}</span>
                      <span>{{ Math.round(f.confidence * 100) }}% confidence</span>
                      <span v-if="!f.grounded && f.status !== 'CORRECTED'" class="text-warn">quote not found on the page</span>
                    </div>

                    <form v-if="editing === f.id" class="mt-3 space-y-2" @submit.prevent="saveField(f, 'correct')">
                      <label class="sr-only" :for="`fv-${f.id}`">Correct value</label>
                      <input :id="`fv-${f.id}`" v-model="editValue" class="input" />
                      <label class="sr-only" :for="`fr-${f.id}`">Reason</label>
                      <input :id="`fr-${f.id}`" v-model="editReason" class="input" placeholder="Why? e.g. misread handwriting" />
                      <div class="flex gap-2"><button class="btn-primary min-h-10">Save</button><button type="button" class="btn-ghost min-h-10" @click="editing = null">Cancel</button></div>
                    </form>
                    <div v-else class="mt-3 flex flex-wrap gap-2">
                      <template v-if="can('verify')">
                        <button v-if="f.status !== 'VERIFIED'" type="button" class="btn-ghost min-h-9 text-ok" @click="saveField(f, 'verify')"><Check :size="15" />Verify</button>
                        <button type="button" class="btn-ghost min-h-9" @click="startEdit(f)"><Pencil :size="14" />Correct</button>
                      </template>
                      <button v-if="f.edit_count" type="button" class="btn-ghost min-h-9" @click="toggleHistory(f)"><History :size="14" />{{ history[f.id] ? 'Hide' : 'History' }} · {{ f.edit_count }}</button>
                    </div>
                    <ol v-if="history[f.id]" class="mt-3 space-y-2 border-l-2 border-line pl-3 text-xs">
                      <li v-for="h in history[f.id]" :key="h.id">
                        <span class="font-semibold text-ink">{{ h.edited_by_name }}</span> <span class="text-muted">· {{ fmtDateTime(h.edited_at) }}</span><br>
                        <span v-if="h.old_value !== h.new_value">{{ fmtValue(h.old_value) || '—' }} → <b>{{ fmtValue(h.new_value) }}</b></span>
                        <span v-else>Marked {{ h.new_status.toLowerCase() }}</span>
                        <span v-if="h.reason" class="text-muted"> — {{ h.reason }}</span>
                      </li>
                    </ol>
                  </div>
                </div>
              </li>
            </ul>
            <p v-if="fieldError" class="mt-2 rounded-[12px] bg-bad-soft px-3 py-2 text-sm text-bad">{{ fieldError }}</p>

            <form v-if="can('verify') && missingFields.length" class="mt-4 flex gap-2" @submit.prevent="addField">
              <label for="nf-key" class="sr-only">Fact to add</label>
              <select id="nf-key" v-model="newField.key" class="input w-[140px] shrink-0"><option value="">Add a fact…</option><option v-for="[k, l] in missingFields" :key="k" :value="k">{{ l }}</option></select>
              <label for="nf-val" class="sr-only">Value</label>
              <input id="nf-val" v-model="newField.value" class="input" placeholder="Value" />
              <button class="btn-ghost w-11 shrink-0 px-0" aria-label="Add fact" :disabled="!newField.key || !newField.value"><Plus :size="17" /></button>
            </form>

            <div v-if="doc.clauses?.length" class="mt-6">
              <div class="mb-2 flex items-baseline justify-between">
                <h2 class="text-[15px] font-semibold">Clauses found</h2>
                <span class="text-xs text-muted">by the fine-tuned clause model</span>
              </div>
              <div class="stagger flex flex-wrap gap-1.5">
                <button v-for="c in doc.clauses" :key="c.label" type="button" @click="jump(c.pages[0], c.snippet)"
                        :title="`${Math.round(c.confidence * 100)}% confidence · page ${c.pages.join(', ')}`"
                        class="chip min-h-8 border border-white bg-white/70 px-3 text-[12.5px] text-ink-2 transition hover:bg-white hover:text-ink">
                  {{ c.label }}<span class="text-muted">p.{{ c.pages[0] }}</span>
                </button>
              </div>
            </div>

            <div v-if="doc.record_fields.length" class="mt-5 flex items-center gap-3 rounded-[16px] bg-white/60 p-3.5 text-[13px] text-ink-2">
              <span class="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-ok-soft text-ok" aria-hidden="true"><Check :size="16" :stroke-width="2.4" /></span>
              <span><b>{{ verifiedCount }} of {{ doc.record_fields.length }} facts confirmed by a person.</b> Each one links to the page it came from.</span>
            </div>
          </template>
          <div v-else class="mt-4 space-y-4">
            <p class="rounded-[16px] bg-white/60 p-4 text-sm text-ink-2">
              Reference material: ask questions about it and every answer cites the section and page.
              <span v-if="doc.outline" class="mt-1 block text-[13px] text-muted">{{ doc.outline.pages }} pages · {{ doc.outline.passages }} passages indexed for search</span>
            </p>
            <div v-if="doc.outline?.sections?.length">
              <h2 class="mb-2 text-[15px] font-semibold">Contents</h2>
              <ol class="stagger space-y-1">
                <li v-for="s in doc.outline.sections" :key="s.title + s.page">
                  <button type="button" class="flex w-full items-baseline gap-3 rounded-[12px] px-3 py-2 text-left text-sm hover:bg-white/70" @click="jump(s.page)">
                    <span class="min-w-0 flex-1"><span class="font-semibold">{{ s.title }}</span><span v-if="s.name" class="text-ink-2"> — {{ s.name }}</span></span>
                    <span class="shrink-0 text-xs text-muted">p. {{ s.page }}</span>
                  </button>
                </li>
              </ol>
            </div>
          </div>
        </div>

        <!-- VERSIONS -->
        <div v-else-if="tab === 'versions'" class="space-y-3">
          <ol class="space-y-3">
            <li v-for="v in doc.versions" :key="v.id"
                :class="['rounded-[18px] p-4 transition', v.number === viewVersion ? 'bg-white shadow-[0_6px_20px_rgb(28_38_90/0.08)]' : 'bg-white/50']">
              <div class="flex items-center gap-3">
                <span :class="['flex h-9 w-9 shrink-0 items-center justify-center rounded-[11px] text-xs font-bold', v.number === doc.current_version_number ? 'bg-accent text-white' : 'bg-black/5 text-ink-2']">v{{ v.number }}</span>
                <div class="min-w-0 flex-1">
                  <div class="truncate font-semibold">{{ v.change_note || (v.number === 1 ? 'Original upload' : 'New version') }}</div>
                  <div class="text-xs text-muted">{{ v.uploaded_by_name }} · {{ fmtDateTime(v.uploaded_at) }}</div>
                </div>
                <StatusPill :status="v.status" />
              </div>
              <div class="mt-2 flex items-center justify-between gap-2 text-xs text-muted">
                <span class="truncate">{{ v.original_filename }} · {{ v.page_count }} page{{ v.page_count === 1 ? '' : 's' }} · {{ fmtSize(v.file_size) }}</span>
                <button v-if="v.number !== viewVersion" type="button" class="link shrink-0" @click="viewVersion = v.number; page = 1">View</button>
                <span v-else class="shrink-0 font-semibold text-ink">Viewing</span>
              </div>
            </li>
          </ol>

          <div v-if="doc.versions.length > 1" class="rounded-[18px] bg-white/60 p-4">
            <h2 class="text-[15px] font-semibold">What changed</h2>
            <div class="mt-3 flex items-center gap-2">
              <label for="cmp-a" class="sr-only">From version</label>
              <select id="cmp-a" v-model.number="cmpA" class="input"><option v-for="v in doc.versions" :key="v.number" :value="v.number">Version {{ v.number }}</option></select>
              <ArrowRight :size="16" class="shrink-0 text-muted" aria-hidden="true" />
              <label for="cmp-b" class="sr-only">To version</label>
              <select id="cmp-b" v-model.number="cmpB" class="input"><option v-for="v in doc.versions" :key="v.number" :value="v.number">Version {{ v.number }}</option></select>
            </div>
            <button type="button" class="btn-dark mt-3 w-full" @click="compare">Compare</button>
            <div v-if="comparison" class="mt-4 space-y-4 text-sm">
              <div>
                <div class="text-xs font-semibold text-muted">Facts</div>
                <p v-if="!comparison.field_changes.length" class="mt-1 text-muted">No facts changed.</p>
                <div v-for="c in comparison.field_changes" :key="c.key" class="mt-2 rounded-[12px] bg-white p-3">
                  <div class="text-xs text-muted">{{ c.label }}</div>
                  <div class="mt-0.5"><span class="text-muted line-through">{{ fmtValue(c.from) || '—' }}</span> <ArrowRight :size="13" class="inline text-muted" aria-hidden="true" /> <b>{{ fmtValue(c.to) || '—' }}</b></div>
                </div>
              </div>
              <div>
                <div class="text-xs font-semibold text-muted">Text · {{ comparison.pages_a }} → {{ comparison.pages_b }} pages</div>
                <p v-if="!comparison.page_changes.length" class="mt-1 text-muted">Text is identical.</p>
                <details v-for="p in comparison.page_changes" :key="p.page" class="mt-2 rounded-[12px] bg-white p-3">
                  <summary class="cursor-pointer font-medium">Page {{ p.page }} · {{ p.status }}<span v-if="p.status === 'changed'" class="text-muted"> ({{ Math.round(p.similarity * 100) }}% the same)</span></summary>
                  <pre class="mt-2 overflow-x-auto font-mono text-xs leading-5 whitespace-pre-wrap"><span v-for="(l, i) in p.diff" :key="i" :class="l.startsWith('+') ? 'text-ok' : l.startsWith('-') ? 'text-bad' : 'text-muted'">{{ l }}
</span></pre>
                </details>
              </div>
            </div>
          </div>
        </div>

        <!-- TEXT -->
        <div v-else-if="tab === 'text'" class="space-y-3">
          <p class="text-[13px] text-muted">What the system read on each page, and how it read it.</p>
          <div v-for="p in pages" :key="p.number" class="rounded-[16px] bg-white/70 p-3.5">
            <div class="mb-2 flex items-center justify-between">
              <button type="button" class="link text-[13px]" @click="jump(p.number)">Page {{ p.number }}</button>
              <span :class="['chip', p.source === 'HANDWRITING' ? 'bg-[#FCE7F3] text-[#A21C6B]' : p.source === 'OCR' ? 'bg-warn-soft text-warn' : 'bg-black/5 text-ink-2']">
                {{ p.source === 'HANDWRITING' ? 'Handwriting model' : p.source === 'OCR' ? `Scanned · ${Math.round(p.ocr_confidence || 0)}%` : 'Digital text' }}
              </span>
            </div>
            <p class="max-h-56 overflow-y-auto text-xs leading-relaxed whitespace-pre-wrap text-ink-2 scroll-thin">{{ p.text || '(empty page)' }}</p>
          </div>
          <details v-if="viewVersionObj?.processing_log?.length" class="rounded-[16px] bg-white/60 p-3.5 text-xs">
            <summary class="cursor-pointer font-semibold">Processing steps</summary>
            <ul class="mt-2 space-y-1">
              <li v-for="(s, i) in viewVersionObj.processing_log" :key="i" class="flex justify-between gap-3"><span class="font-medium">{{ s.step }}</span><span class="text-muted tabular-nums">{{ s.ms != null ? `${s.ms} ms` : '' }}</span></li>
            </ul>
          </details>
        </div>

        <!-- ACTIVITY -->
        <ol v-else-if="tab === 'activity'" class="space-y-1">
          <li v-for="e in activity" :key="e.id" class="flex gap-3 rounded-[14px] px-2 py-2.5 hover:bg-white/60">
            <span class="mt-1.5 h-2 w-2 shrink-0 rounded-full bg-accent/60" aria-hidden="true" />
            <span class="min-w-0 text-[13px]">
              <b>{{ e.actor }}</b> {{ ACTION_TEXT[e.action] || e.action.toLowerCase() }}
              <span v-if="e.metadata?.field" class="text-ink-2"> {{ e.metadata.field.replace('_', ' ') }} → “{{ fmtValue(e.metadata.new) }}”</span>
              <span class="block text-xs text-muted">{{ fmtDateTime(e.created_at) }}</span>
            </span>
          </li>
          <li v-if="!activity.length" class="text-sm text-muted">No activity yet.</li>
        </ol>
      </aside>
    </div>

    <UploadModal v-if="showUpload" :document-id="doc.id" @close="showUpload = false" @uploaded="showUpload = false; load(); toast('New version uploaded', { tone: 'info', detail: 'Reading it now — the facts will update by themselves.' })" />

    <Modal :open="showSettings" title="Settings & access" description="Changes to who can see this document are recorded in the activity log." @close="showSettings = false">
      <form class="space-y-4" @submit.prevent="saveSettings">
        <div><label class="label" for="st-title">Title</label><input id="st-title" v-model="settings.title" class="input" /></div>
        <div class="grid gap-3 sm:grid-cols-2">
          <div><label class="label" for="st-kind">Type</label>
            <select id="st-kind" v-model="settings.kind" class="input"><option value="RECORD">Record</option><option value="REFERENCE">Reference</option></select></div>
          <div><label class="label" for="st-dept">Department</label>
            <select id="st-dept" v-model="settings.department" class="input"><option :value="null">None</option><option v-for="d in departments" :key="d.id" :value="d.id">{{ d.name }}</option></select></div>
        </div>
        <fieldset>
          <legend class="label">Who can see it</legend>
          <div class="grid gap-2 sm:grid-cols-3">
            <label v-for="a in ACCESS" :key="a.value" :class="['flex cursor-pointer flex-col gap-1 rounded-[14px] border p-3 text-sm transition', settings.access_level === a.value ? 'border-accent bg-accent-soft' : 'border-black/10 bg-white/60 hover:bg-white']">
              <input v-model="settings.access_level" type="radio" :value="a.value" class="sr-only" />
              <component :is="a.icon" :size="16" :class="settings.access_level === a.value ? 'text-accent' : 'text-muted'" aria-hidden="true" />
              <span class="font-semibold">{{ a.label }}</span>
            </label>
          </div>
        </fieldset>
        <div>
          <div class="label">Also shared with</div>
          <div class="max-h-40 space-y-0.5 overflow-y-auto rounded-[14px] border border-black/10 bg-white/60 p-2 scroll-thin">
            <label v-for="m in members" :key="m.id" class="flex min-h-10 items-center gap-2.5 rounded-lg px-2 text-sm hover:bg-white">
              <input type="checkbox" :value="m.id" v-model="settings.allowed_user_ids" class="h-4 w-4 accent-[#2F4BE0]" /> {{ m.full_name }}
            </label>
          </div>
        </div>
        <p v-if="settingsError" class="rounded-[14px] bg-bad-soft px-3.5 py-2.5 text-sm text-bad">{{ settingsError }}</p>
        <div class="flex items-center justify-between gap-2 pt-1">
          <button type="button" class="btn-danger" @click="archive"><Trash2 :size="16" />Archive</button>
          <div class="flex gap-2"><button type="button" class="btn-ghost" @click="showSettings = false">Cancel</button><button class="btn-primary">Save</button></div>
        </div>
      </form>
    </Modal>
  </div>

  <div v-else-if="notFound" class="flex h-full flex-col items-center justify-center p-10 text-center">
    <Lock :size="28" class="text-muted" />
    <p class="mt-3 font-semibold">This document doesn't exist, or you don't have access to it.</p>
    <router-link to="/app/documents" class="link mt-2 text-sm">Back to documents</router-link>
  </div>
</template>

<script setup>
import { ArrowRight, Building2, Check, ChevronLeft, Globe, History, Lock, Pencil, Plus, RotateCw, Search, Settings2, Trash2, TriangleAlert, Upload } from '@lucide/vue'
import { computed, onBeforeUnmount, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import api, { errorText } from '../api'
import DocumentViewer from '../components/DocumentViewer.vue'
import Modal from '../components/Modal.vue'
import Segmented from '../components/Segmented.vue'
import StatusPill from '../components/StatusPill.vue'
import UploadModal from '../components/UploadModal.vue'
import { ACCESS_LABELS, FIELD_OPTIONS, KIND_LABELS, fmtDateTime, fmtSize, fmtValue } from '../format'
import { can, loadReviewCount, session } from '../session'
import { toast } from '../toast'

const ACCESS_ICON = { ORG: Globe, DEPARTMENT: Building2, RESTRICTED: Lock }
const ACCESS = [
  { value: 'ORG', label: 'Everyone', icon: Globe },
  { value: 'DEPARTMENT', label: 'Department', icon: Building2 },
  { value: 'RESTRICTED', label: 'Chosen people', icon: Lock },
]
const ACTION_TEXT = { UPLOAD: 'uploaded it', NEW_VERSION: 'uploaded a new version', VIEW: 'opened it', DOWNLOAD: 'downloaded it',
  FIELD_EDIT: 'corrected', FIELD_VERIFY: 'verified', ACCESS_CHANGE: 'changed who can see it', UPDATE_DOCUMENT: 'edited its details',
  ARCHIVE: 'archived it', REPROCESS: 'reprocessed it' }

const route = useRoute()
const router = useRouter()
const doc = ref(null)
const notFound = ref(false)
const tab = ref('facts')
const page = ref(Number(route.query.page) || 1)
const highlight = ref(route.query.hl || '')
const viewVersion = ref(null)
const pages = ref([])
const activity = ref([])
const departments = ref([])
const members = ref([])
const history = reactive({})
const selected = ref(null)
const editing = ref(null)
const editValue = ref('')
const editReason = ref('')
const fieldError = ref('')
const newField = reactive({ key: '', value: '' })
const settings = reactive({ title: '', kind: 'RECORD', department: null, access_level: 'ORG', allowed_user_ids: [] })
const settingsError = ref('')
const showSettings = ref(false)
const showUpload = ref(false)
const cmpA = ref(1)
const cmpB = ref(2)
const comparison = ref(null)
let poll = null

const tabs = computed(() => [
  { value: 'facts', label: doc.value?.kind === 'RECORD' ? 'Facts' : 'About' },
  { value: 'versions', label: `Versions · ${doc.value?.versions.length || 0}` },
  { value: 'text', label: 'Text' },
  ...(can('view_audit') ? [{ value: 'activity', label: 'Activity' }] : []),
])
const latest = computed(() => doc.value?.versions[0])
const viewVersionObj = computed(() => doc.value?.versions.find(v => v.number === viewVersion.value))
const missingFields = computed(() => FIELD_OPTIONS.filter(([k]) => !doc.value?.record_fields.some(f => f.key === k)))
const verifiedCount = computed(() => doc.value?.record_fields.filter(f => f.status === 'VERIFIED' || f.status === 'CORRECTED').length || 0)

async function load() {
  try {
    const { data } = await api.get(`/documents/${route.params.id}/`)
    doc.value = data
    if (viewVersion.value === null || !data.versions.some(v => v.number === viewVersion.value))
      viewVersion.value = data.current_version_number || data.versions[0]?.number
    Object.assign(settings, { title: data.title, kind: data.kind === 'UNKNOWN' ? 'RECORD' : data.kind, department: data.department,
                              access_level: data.access_level, allowed_user_ids: data.allowed_users.map(u => u.id) })
    if (data.versions.length > 1) { cmpA.value = data.versions[1].number; cmpB.value = data.versions[0].number }
    clearTimeout(poll)
    if (['QUEUED', 'PROCESSING'].includes(data.versions[0]?.status)) poll = setTimeout(load, 4000)
  } catch (e) {
    if (e.response?.status === 404) notFound.value = true
  }
}

async function loadSide() {
  if (!doc.value) return
  if (tab.value === 'text') pages.value = (await api.get(`/documents/${doc.value.id}/pages/`, { params: { version: viewVersion.value } })).data
  if (tab.value === 'activity') activity.value = (await api.get('/audit/', { params: { target_type: 'Document', target_id: doc.value.id, limit: 100 } })).data.results
}

function jump(n, quote = '') { page.value = n; highlight.value = quote }

function selectField(f) {
  selected.value = selected.value === f.id ? null : f.id
  editing.value = null
  if (selected.value && f.source_page) jump(f.source_page, f.source_quote)
}

function startEdit(f) { editing.value = f.id; editValue.value = f.value_text; editReason.value = '' }

async function saveField(f, action) {
  fieldError.value = ''
  try {
    await api.patch(`/records/fields/${f.id}/`, { action, value: editValue.value, reason: editReason.value })
    editing.value = null
    delete history[f.id]
    await load()
    loadReviewCount()
    toast(action === 'verify' ? `${f.label} verified` : `${f.label} corrected`, { detail: 'Saved to the field history and activity log.' })
  } catch (e) { fieldError.value = errorText(e) }
}

async function toggleHistory(f) {
  if (history[f.id]) { delete history[f.id]; return }
  history[f.id] = (await api.get(`/records/fields/${f.id}/history/`)).data
}

async function addField() {
  fieldError.value = ''
  try {
    await api.post('/records/fields/', { document_id: doc.value.id, key: newField.key, value: newField.value })
    newField.key = ''; newField.value = ''
    await load()
    toast('Fact added')
  } catch (e) { fieldError.value = errorText(e) }
}

async function saveSettings() {
  settingsError.value = ''
  try {
    await api.patch(`/documents/${doc.value.id}/`, settings)
    showSettings.value = false
    await load()
    toast('Settings saved', { detail: 'Access changes are recorded in the activity log.' })
  } catch (e) { settingsError.value = errorText(e) }
}

async function archive() {
  if (!confirm('Archive this document? It disappears for everyone but stays in the activity log.')) return
  await api.delete(`/documents/${doc.value.id}/`)
  toast('Document archived', { tone: 'info' })
  router.push('/app/documents')
}

async function reprocess() { await api.post(`/documents/${doc.value.id}/reprocess/`); load() }
async function compare() { comparison.value = (await api.get(`/documents/${doc.value.id}/compare/`, { params: { a: cmpA.value, b: cmpB.value } })).data }

watch(tab, loadSide)
watch(viewVersion, loadSide)
watch(showSettings, async open => {
  if (open && !departments.value.length) {
    const [d, m] = await Promise.all([api.get('/org/departments/'), api.get('/org/members/')])
    departments.value = d.data
    members.value = m.data.filter(x => x.id !== session.me.id)
  }
})
load()
onBeforeUnmount(() => clearTimeout(poll))
</script>
