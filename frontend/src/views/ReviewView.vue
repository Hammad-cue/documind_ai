<template>
  <div class="h-full overflow-y-auto scroll-thin">
    <div class="mx-auto max-w-[920px] px-4 py-8 sm:px-6 lg:py-10">
      <PageHeader title="Review" subtitle="Facts the system isn't sure about — read from handwriting or a scan, low confidence, or the quote wasn't found on the page. Confirm or correct each one." />

      <div v-if="items.length" class="mt-6 flex items-center gap-3">
        <div class="h-1.5 flex-1 overflow-hidden rounded-full bg-black/5" aria-hidden="true">
          <div class="h-full rounded-full bg-accent transition-all duration-500" :style="{ width: `${progress}%` }" />
        </div>
        <span class="text-[13px] font-medium text-muted tabular-nums">{{ done }} of {{ total }} done</span>
      </div>

      <TransitionGroup name="rise" tag="div" class="mt-5 space-y-3">
        <article v-for="f in items" :key="f.id" class="panel p-5 sm:p-6">
          <div class="flex flex-wrap items-start justify-between gap-4">
            <div class="min-w-0 flex-1 basis-[260px]">
              <router-link :to="{ path: `/app/documents/${f.document_id}`, query: { page: f.source_page || 1, hl: f.source_quote } }"
                           class="inline-flex items-center gap-1.5 text-[13px] font-semibold text-accent hover:text-accent-hover">
                <FileText :size="14" aria-hidden="true" />{{ f.document_title }}<span class="font-normal text-muted"> · page {{ f.source_page || '–' }}</span>
              </router-link>
              <div class="mt-3 text-xs font-medium text-muted">{{ f.label }}</div>
              <div class="mt-0.5 text-[24px] leading-tight font-bold tracking-[-0.02em]">{{ fmtValue(f.value_text) }}</div>
              <p v-if="f.source_quote" class="mt-3 rounded-[12px] bg-mark/40 px-3 py-2 text-[13px] leading-relaxed text-ink-2">“{{ f.source_quote }}”</p>
              <p v-if="f.review_reason && /^(Calculated|Second check)/.test(f.review_reason)" class="mt-2 rounded-[12px] bg-warn-soft/60 px-3 py-2 text-[13px] leading-relaxed text-ink-2">{{ f.review_reason }}</p>
              <div class="mt-3 flex flex-wrap gap-1.5">
                <span class="chip bg-black/5 text-ink-2">{{ Math.round(f.confidence * 100) }}% confidence</span>
                <span v-if="f.page_source === 'HANDWRITING'" class="chip bg-pink-soft text-pink">Read from handwriting</span>
                <span v-if="f.page_source === 'OCR'" class="chip bg-warn-soft text-warn">Read from a scan</span>
                <span v-if="!f.grounded" class="chip bg-bad-soft text-bad">Quote not found on the page</span>
                <span v-if="f.review_reason?.startsWith('Calculated')" class="chip bg-accent-soft text-accent">Calculated date</span>
                <span v-if="f.review_reason?.startsWith('Second check')" class="chip bg-warn-soft text-warn">Failed second check</span>
              </div>
            </div>
            <div class="flex shrink-0 gap-2">
              <button type="button" class="btn-ghost" @click="f._edit = !f._edit; f._value = f.value_text"><Pencil :size="15" aria-hidden="true" />Correct</button>
              <button type="button" class="btn-primary" @click="act(f, 'verify')"><Check :size="16" aria-hidden="true" />It's right</button>
            </div>
          </div>
          <form v-if="f._edit" class="mt-4 flex flex-wrap gap-2 rounded-[16px] bg-white/60 p-3" @submit.prevent="act(f, 'correct')">
            <label :for="`rv-${f.id}`" class="sr-only">Correct value</label>
            <input :id="`rv-${f.id}`" v-model="f._value" class="input max-w-xs flex-1" />
            <label :for="`rr-${f.id}`" class="sr-only">Reason</label>
            <input :id="`rr-${f.id}`" v-model="f._reason" class="input max-w-xs flex-1" placeholder="Reason (optional)" />
            <button class="btn-dark">Save correction</button>
          </form>
          <p v-if="f._error" class="mt-3 rounded-[12px] bg-bad-soft px-3 py-2 text-sm text-bad">{{ f._error }}</p>
        </article>
      </TransitionGroup>

      <div v-if="!loading && !items.length" class="panel mt-6 flex flex-col items-center px-6 py-16 text-center">
        <span class="flex h-14 w-14 items-center justify-center rounded-full bg-ok-soft text-ok"><Check :size="24" :stroke-width="2.4" /></span>
        <p class="mt-4 text-lg font-semibold">All caught up</p>
        <p class="mt-1 text-sm text-muted">New facts that need a human check will appear here.</p>
      </div>
    </div>
  </div>
</template>

<script setup>
import { Check, FileText, Pencil } from '@lucide/vue'
import { computed, onMounted, ref } from 'vue'
import api, { errorText } from '../api'
import PageHeader from '../components/PageHeader.vue'
import { fmtValue } from '../format'
import { loadReviewCount } from '../session'
import { toast } from '../toast'

const items = ref([])
const loading = ref(true)
const total = ref(0)
const done = computed(() => total.value - items.value.length)
const progress = computed(() => (total.value ? (done.value / total.value) * 100 : 0))

async function load() {
  items.value = (await api.get('/records/review-queue/')).data
  total.value = items.value.length
  loading.value = false
}

async function act(f, action) {
  f._error = ''
  try {
    await api.patch(`/records/fields/${f.id}/`, { action, value: f._value, reason: f._reason || '' })
    items.value = items.value.filter(x => x.id !== f.id)
    loadReviewCount()
    toast(action === 'verify' ? `${f.label} confirmed` : `${f.label} corrected`, { detail: f.document_title })
  } catch (e) { f._error = errorText(e) }
}
onMounted(load)
</script>
