<template>
  <div class="h-full overflow-y-auto scroll-thin">
    <div class="mx-auto max-w-[1180px] px-4 py-8 sm:px-6 lg:py-10">
      <PageHeader title="Activity log" subtitle="Every sign-in, upload, view, download, search and change. Entries can't be edited or deleted." />

      <div class="mt-7 flex flex-wrap items-center gap-3">
        <label for="a-action" class="sr-only">Action</label>
        <select id="a-action" v-model="filters.action" class="input w-auto min-w-[170px] bg-white/60" @change="reset">
          <option value="">All actions</option><option v-for="a in actions" :key="a" :value="a">{{ ACTION_LABEL[a] || a }}</option>
        </select>
        <div class="glass-soft flex min-h-11 w-48 items-center gap-2 rounded-[14px] px-3.5">
          <UserRound :size="16" class="text-muted" aria-hidden="true" />
          <label for="a-actor" class="sr-only">Person</label>
          <input id="a-actor" v-model="filters.actor" placeholder="Person" class="min-w-0 flex-1 bg-transparent text-sm outline-none" @input="debounced" />
        </div>
        <label for="a-from" class="sr-only">From date</label>
        <input id="a-from" v-model="filters.date_from" type="date" class="input w-auto bg-white/60" @change="reset" />
        <label for="a-to" class="sr-only">To date</label>
        <input id="a-to" v-model="filters.date_to" type="date" class="input w-auto bg-white/60" @change="reset" />
      </div>

      <div class="panel mt-4 overflow-hidden">
        <ol class="stagger divide-y divide-line">
          <li v-for="e in rows" :key="e.id" class="grid grid-cols-[auto_minmax(0,1fr)] gap-x-4 gap-y-1 px-4 py-3.5 sm:grid-cols-[150px_auto_minmax(0,1fr)] sm:px-6">
            <span class="hidden text-[13px] text-muted tabular-nums sm:block">{{ fmtDateTime(e.created_at) }}</span>
            <span :class="['flex h-8 w-8 items-center justify-center rounded-[10px]', TONE[e.action] || 'bg-black/5 text-ink-2']" aria-hidden="true">
              <component :is="ICON[e.action] || Activity" :size="15" />
            </span>
            <span class="min-w-0 text-sm">
              <b>{{ e.actor }}</b>
              <span class="ml-1 text-ink-2">{{ (ACTION_LABEL[e.action] || e.action).toLowerCase() }}</span>
              <router-link v-if="e.target_type === 'Document'" :to="`/app/documents/${e.target_id}`" class="link ml-1">{{ e.target_label }}</router-link>
              <span v-else-if="e.action === 'SEARCH'" class="ml-1 font-medium">“{{ e.target_label }}”</span>
              <span v-else-if="e.target_label && e.action !== 'LOGIN'" class="ml-1 font-medium">{{ e.target_label }}</span>
              <span v-if="details(e)" class="mt-0.5 block truncate text-[13px] text-muted">{{ details(e) }}</span>
              <span class="mt-0.5 block text-xs text-muted sm:hidden">{{ fmtDateTime(e.created_at) }}</span>
            </span>
          </li>
          <li v-if="!rows.length" class="px-6 py-14 text-center text-sm text-muted">No events match.</li>
        </ol>
      </div>

      <div class="mt-4 flex items-center justify-between text-sm text-muted">
        <span>{{ count }} event{{ count === 1 ? '' : 's' }}</span>
        <div class="flex gap-2">
          <button type="button" class="btn-ghost" :disabled="offset === 0" @click="offset -= limit; load()"><ChevronLeft :size="16" />Newer</button>
          <button type="button" class="btn-ghost" :disabled="offset + limit >= count" @click="offset += limit; load()">Older<ChevronRight :size="16" /></button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { Activity, Archive, Check, ChevronLeft, ChevronRight, Download, Eye, FilePlus, Layers, LogIn, Lock, Pencil, RotateCw, Search, UserPlus, UserRound, Users } from '@lucide/vue'
import { onMounted, reactive, ref } from 'vue'
import api from '../api'
import PageHeader from '../components/PageHeader.vue'
import { fmtDateTime, fmtValue } from '../format'

const ACTION_LABEL = { LOGIN: 'Signed in', UPLOAD: 'Uploaded', NEW_VERSION: 'Uploaded a new version of', VIEW: 'Opened', DOWNLOAD: 'Downloaded',
  SEARCH: 'Asked', FIELD_EDIT: 'Corrected a fact in', FIELD_VERIFY: 'Verified a fact in', UPDATE_DOCUMENT: 'Edited', ACCESS_CHANGE: 'Changed access to',
  ARCHIVE: 'Archived', REPROCESS: 'Reprocessed', MEMBER_ADD: 'Added', MEMBER_UPDATE: 'Updated', DEPARTMENT_CHANGE: 'Changed department' }
const ICON = { LOGIN: LogIn, UPLOAD: FilePlus, NEW_VERSION: Layers, VIEW: Eye, DOWNLOAD: Download, SEARCH: Search, FIELD_EDIT: Pencil,
  FIELD_VERIFY: Check, ACCESS_CHANGE: Lock, ARCHIVE: Archive, REPROCESS: RotateCw, MEMBER_ADD: UserPlus, MEMBER_UPDATE: Users }
const TONE = { ACCESS_CHANGE: 'bg-bad-soft text-bad', ARCHIVE: 'bg-bad-soft text-bad', DOWNLOAD: 'bg-warn-soft text-warn',
  FIELD_VERIFY: 'bg-ok-soft text-ok', FIELD_EDIT: 'bg-accent-soft text-accent', SEARCH: 'bg-accent-soft text-accent', UPLOAD: 'bg-violet-soft text-violet', NEW_VERSION: 'bg-violet-soft text-violet' }

const rows = ref([])
const actions = ref([])
const count = ref(0)
const offset = ref(0)
const limit = 50
const filters = reactive({ action: '', actor: '', date_from: '', date_to: '' })
let timer = null

function details(e) {
  const m = e.metadata || {}
  if (m.field) return `${m.field.replace('_', ' ')}: ${fmtValue(m.old) || '—'} → ${fmtValue(m.new)}${m.reason ? ` (${m.reason})` : ''}`
  if (m.intent) return `${m.intent.toLowerCase()} · ${m.results} result${m.results === 1 ? '' : 's'} · ${(m.latency_ms / 1000).toFixed(1)} s`
  if (m.before && m.after) return Object.keys(m.after).filter(k => JSON.stringify(m.before[k]) !== JSON.stringify(m.after[k])).map(k => `${k.replace('_', ' ')} changed`).join(', ')
  if (m.version) return `version ${m.version}`
  return ''
}

async function load() {
  const params = { limit, offset: offset.value }
  Object.entries(filters).forEach(([k, v]) => v && (params[k] = v))
  const { data } = await api.get('/audit/', { params })
  rows.value = data.results
  count.value = data.count
  actions.value = data.actions
}
const reset = () => { offset.value = 0; load() }
const debounced = () => { clearTimeout(timer); timer = setTimeout(reset, 300) }
onMounted(load)
</script>
