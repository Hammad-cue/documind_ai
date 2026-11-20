<template>
  <div class="h-full overflow-y-auto scroll-thin">
    <div class="mx-auto max-w-[1180px] px-4 py-8 sm:px-6 lg:py-10">
      <PageHeader title="Records" subtitle="The facts pulled out of every contract, NDA and agreement you can open." />

      <div class="stagger mt-7 grid gap-3 sm:grid-cols-3">
        <button v-for="s in stats" :key="s.key" type="button" @click="setView(s.key)"
                :class="['lift rounded-[22px] p-5 text-left', view === s.key ? 'glass-strong ring-2 ring-accent/25' : 'glass']">
          <div class="flex items-center gap-2 text-[13px] font-medium text-muted"><component :is="s.icon" :size="15" aria-hidden="true" />{{ s.label }}</div>
          <div class="mt-2 text-[34px] leading-none font-bold tracking-[-0.03em]"><CountUp :value="s.value" /></div>
        </button>
      </div>

      <div class="mt-6 flex flex-wrap items-center gap-3">
        <div class="glass-soft flex min-h-11 min-w-[240px] flex-1 items-center gap-2 rounded-[14px] px-3.5 sm:max-w-sm">
          <Search :size="17" class="text-muted" aria-hidden="true" />
          <label for="rec-filter" class="sr-only">Search records</label>
          <input id="rec-filter" v-model="q" placeholder="Search records" class="min-w-0 flex-1 bg-transparent text-sm outline-none placeholder:text-muted/80" @input="debounced" />
        </div>
        <span class="text-[13px] text-muted">{{ rows.length }} record{{ rows.length === 1 ? '' : 's' }}</span>
      </div>

      <div class="panel mt-4 overflow-x-auto">
        <table class="w-full min-w-[760px] text-sm">
          <thead>
            <tr class="border-b border-line text-left text-xs font-semibold text-muted">
              <th class="px-6 py-3 font-semibold">Record</th><th class="px-3 py-3 font-semibold">Parties</th>
              <th class="px-3 py-3 font-semibold">Signed</th><th class="px-3 py-3 font-semibold">Expires</th>
              <th class="px-3 py-3 font-semibold">Value</th><th class="px-6 py-3"><span class="sr-only">Status</span></th>
            </tr>
          </thead>
          <tbody class="stagger divide-y divide-line">
            <tr v-for="r in rows" :key="r.id" class="cursor-pointer transition hover:bg-white/70" @click="$router.push(`/app/documents/${r.id}`)">
              <td class="px-6 py-3.5">
                <router-link :to="`/app/documents/${r.id}`" class="font-semibold text-ink hover:text-accent" @click.stop>{{ r.title }}</router-link>
                <div class="text-[13px] text-muted">{{ r.doc_type }}<span v-if="r.department"> · {{ r.department }}</span></div>
              </td>
              <td class="max-w-[220px] px-3 py-3.5 text-ink-2">{{ r.fields.parties?.value || '—' }}</td>
              <td class="px-3 py-3.5 whitespace-nowrap tabular-nums">{{ fmtValue(r.fields.signed_date?.value) || '—' }}</td>
              <td class="px-3 py-3.5 whitespace-nowrap tabular-nums">
                <span :class="soon(r.fields.expiry_date?.value) ? 'font-semibold text-warn' : ''">{{ fmtValue(r.fields.expiry_date?.value) || '—' }}</span>
                <div v-if="soon(r.fields.expiry_date?.value)" class="text-xs text-warn">in {{ daysLeft(r.fields.expiry_date.value) }} days</div>
              </td>
              <td class="px-3 py-3.5 text-ink-2">{{ r.fields.contract_value?.value || '—' }}</td>
              <td class="px-6 py-3.5 text-right">
                <span v-if="r.needs_review" class="chip bg-warn-soft text-warn">{{ r.needs_review }} to review</span>
                <span v-if="r.policy_issues" class="chip bg-bad-soft text-bad">{{ r.policy_issues }} policy issue{{ r.policy_issues > 1 ? 's' : '' }}</span>
                <StatusPill v-else-if="!r.ready" status="PROCESSING" />
              </td>
            </tr>
          </tbody>
        </table>
        <div v-if="!loading && !rows.length" class="px-6 py-14 text-center">
          <p class="font-semibold">No records here</p>
          <p class="mt-1 text-sm text-muted">{{ view === 'all' && !q ? 'Upload a contract or agreement and its facts will appear here.' : 'Nothing matches this view.' }}</p>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { CalendarClock, CircleCheck, Search, Table2 } from '@lucide/vue'
import { computed, onMounted, ref } from 'vue'
import api from '../api'
import CountUp from '../components/CountUp.vue'
import PageHeader from '../components/PageHeader.vue'
import StatusPill from '../components/StatusPill.vue'
import { fmtValue } from '../format'

const rows = ref([])
const all = ref([])
const q = ref('')
const view = ref('all')
const loading = ref(true)
let timer = null

const daysLeft = v => Math.ceil((new Date(v) - new Date()) / 86400000)
const soon = v => v && daysLeft(v) >= 0 && daysLeft(v) <= 180
const stats = computed(() => [
  { key: 'all', label: 'All records', icon: Table2, value: all.value.length },
  { key: 'expiring', label: 'Expiring in 6 months', icon: CalendarClock, value: all.value.filter(r => soon(r.fields.expiry_date?.value)).length },
  { key: 'review', label: 'Facts waiting for review', icon: CircleCheck, value: all.value.reduce((n, r) => n + r.needs_review, 0) },
])

function setView(v) { view.value = v; load() }

async function load() {
  const params = {}
  if (q.value) params.q = q.value
  if (view.value === 'expiring') params.expiring_within = 180
  if (view.value === 'review') params.needs_review = 1
  rows.value = (await api.get('/records/', { params })).data
  loading.value = false
}
const debounced = () => { clearTimeout(timer); timer = setTimeout(load, 300) }
onMounted(async () => { all.value = (await api.get('/records/')).data; load() })
</script>
