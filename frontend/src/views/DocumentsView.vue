<template>
  <div class="h-full overflow-y-auto scroll-thin">
    <div class="mx-auto max-w-[1180px] px-4 py-8 sm:px-6 lg:py-10">
      <PageHeader title="Documents" :subtitle="`Everything you can open in ${session.me?.organization.name}.`">
        <button v-if="can('upload')" type="button" class="btn-primary" @click="showUpload = true"><Plus :size="17" aria-hidden="true" /> Add document</button>
      </PageHeader>

      <div class="mt-7 flex flex-wrap items-center gap-3">
        <div class="glass-soft flex min-h-11 min-w-[240px] flex-1 items-center gap-2 rounded-[14px] px-3.5 sm:max-w-sm">
          <Search :size="17" class="text-muted" aria-hidden="true" />
          <label for="doc-filter" class="sr-only">Filter documents</label>
          <input id="doc-filter" v-model="q" placeholder="Filter by title or type" class="min-w-0 flex-1 bg-transparent text-sm outline-none placeholder:text-muted/80" @input="debouncedLoad" />
        </div>
        <Segmented v-model="kind" label="Kind" :options="[{ value: '', label: 'All' }, { value: 'RECORD', label: 'Records' }, { value: 'REFERENCE', label: 'Reference' }]" />
        <label for="doc-dept" class="sr-only">Department</label>
        <select id="doc-dept" v-model="department" class="input w-auto min-w-[170px] rounded-[14px] bg-white/60" @change="load">
          <option value="">All departments</option>
          <option v-for="d in departments" :key="d.id" :value="d.id">{{ d.name }}</option>
        </select>
      </div>

      <div class="panel mt-5 overflow-hidden">
        <div class="hidden gap-4 border-b border-line px-6 py-3 text-xs font-semibold text-muted lg:grid lg:grid-cols-[minmax(0,1fr)_140px_150px] xl:grid-cols-[minmax(0,1fr)_130px_140px_150px_100px]">
          <span>Document</span><span class="hidden xl:block">Department</span><span>Who can see it</span><span>Status</span><span class="hidden text-right xl:block">Updated</span>
        </div>
        <TransitionGroup name="fade" tag="ul" class="stagger divide-y divide-line">
          <li v-for="d in docs" :key="d.id">
            <router-link :to="`/app/documents/${d.id}`"
              class="grid grid-cols-[minmax(0,1fr)_auto] items-center gap-4 px-4 py-3.5 transition hover:bg-white/70 sm:px-6 lg:grid-cols-[minmax(0,1fr)_140px_150px] xl:grid-cols-[minmax(0,1fr)_130px_140px_150px_100px]">
              <span class="flex min-w-0 items-center gap-3.5">
                <span :class="['flex h-11 w-11 shrink-0 items-center justify-center rounded-[13px]', d.kind === 'RECORD' ? 'bg-[#EEEAFF] text-[#5B3FD9]' : d.kind === 'REFERENCE' ? 'bg-accent-soft text-accent' : 'bg-black/5 text-muted']" aria-hidden="true">
                  <component :is="d.kind === 'REFERENCE' ? BookOpen : d.file_type === 'IMAGE' ? PenLine : FileText" :size="19" />
                </span>
                <span class="min-w-0">
                  <span class="block truncate font-semibold text-ink">{{ d.title }}</span>
                  <span class="block truncate text-[13px] text-muted">{{ d.doc_type || KIND_LABELS[d.kind] }}<span v-if="d.version_count > 1"> · {{ d.version_count }} versions</span></span>
                </span>
              </span>
              <span class="hidden truncate text-sm text-ink-2 xl:block">{{ d.department_name || '—' }}</span>
              <span class="hidden items-center gap-1.5 text-sm text-ink-2 lg:flex">
                <component :is="ACCESS_ICON[d.access_level]" :size="15" class="text-muted" aria-hidden="true" />{{ ACCESS_LABELS[d.access_level] }}
              </span>
              <span class="flex flex-wrap items-center justify-end gap-1.5 lg:justify-start">
                <StatusPill :status="d.status" />
                <span v-if="d.needs_review" class="chip bg-warn-soft text-warn">{{ d.needs_review }} to review</span>
              </span>
              <span class="hidden text-right text-[13px] text-muted xl:block">{{ fmtDate(d.updated_at) }}</span>
            </router-link>
          </li>
        </TransitionGroup>
        <div v-if="!loading && !docs.length" class="flex flex-col items-center px-6 py-16 text-center">
          <span class="flex h-14 w-14 items-center justify-center rounded-full bg-white shadow-[0_6px_16px_rgb(28_38_90/0.08)]"><FileText :size="22" class="text-muted" /></span>
          <p class="mt-4 font-semibold">{{ q || kind || department ? 'Nothing matches those filters' : 'No documents yet' }}</p>
          <p class="mt-1 text-sm text-muted">{{ q || kind || department ? 'Try a different word or clear the filters.' : 'Add a contract, a law book or a scanned page to get started.' }}</p>
        </div>
        <div v-if="loading" class="space-y-3 p-6"><div v-for="i in 4" :key="i" class="shimmer h-11 rounded-[13px]" /></div>
      </div>
    </div>

    <UploadModal v-if="showUpload" @close="showUpload = false" @uploaded="onUploaded" />
  </div>
</template>

<script setup>
import { BookOpen, Building2, FileText, Globe, Lock, PenLine, Plus, Search } from '@lucide/vue'
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import api from '../api'
import PageHeader from '../components/PageHeader.vue'
import Segmented from '../components/Segmented.vue'
import StatusPill from '../components/StatusPill.vue'
import UploadModal from '../components/UploadModal.vue'
import { ACCESS_LABELS, KIND_LABELS, fmtDate } from '../format'
import { can, session } from '../session'
import { toast } from '../toast'

const ACCESS_ICON = { ORG: Globe, DEPARTMENT: Building2, RESTRICTED: Lock }
const router = useRouter()
const route = useRoute()
const docs = ref([])
const departments = ref([])
const q = ref('')
const kind = ref('')
const department = ref('')
const loading = ref(true)
const showUpload = ref(route.query.upload === '1')
let timer = null
let poll = null

async function load() {
  const params = {}
  if (q.value) params.q = q.value
  if (kind.value) params.kind = kind.value
  if (department.value) params.department = department.value
  const { data } = await api.get('/documents/', { params })
  docs.value = data
  loading.value = false
  clearTimeout(poll)
  if (data.some(d => d.status === 'QUEUED' || d.status === 'PROCESSING')) poll = setTimeout(load, 4000)
}
const debouncedLoad = () => { clearTimeout(timer); timer = setTimeout(load, 300) }

function onUploaded(doc) {
  showUpload.value = false
  toast('Document uploaded', { tone: 'info', detail: 'Reading it now — this takes a few seconds.' })
  router.push(`/app/documents/${doc.id}`)
}

watch(kind, load)
onMounted(async () => {
  load()
  departments.value = (await api.get('/org/departments/')).data
})
onBeforeUnmount(() => { clearTimeout(poll); clearTimeout(timer) })
</script>
