<template>
  <!-- `key` re-mounts the pill when the status changes, so the change lands with a small stamp animation -->
  <span :key="status" class="chip" :class="[s.cls, changed && (status === 'VERIFIED' || status === 'CORRECTED' ? 'animate-stamp' : 'animate-pop')]">
    <span class="h-1.5 w-1.5 rounded-full" :class="s.dot" aria-hidden="true" />{{ s.label }}
  </span>
</template>

<script setup>
import { computed, ref, watch } from 'vue'

const props = defineProps({ status: String })
const MAP = {
  // document processing
  READY: { label: 'Ready', cls: 'bg-ok-soft text-ok', dot: 'bg-ok' },
  QUEUED: { label: 'Queued', cls: 'bg-black/5 text-ink-2', dot: 'bg-muted animate-pulse' },
  PROCESSING: { label: 'Reading…', cls: 'bg-accent-soft text-accent', dot: 'bg-accent animate-pulse' },
  FAILED: { label: 'Failed', cls: 'bg-bad-soft text-bad', dot: 'bg-bad' },
  // record fields
  AUTO: { label: 'Auto', cls: 'bg-black/5 text-ink-2', dot: 'bg-muted' },
  NEEDS_REVIEW: { label: 'Needs review', cls: 'bg-warn-soft text-warn', dot: 'bg-[#D98B00]' },
  VERIFIED: { label: 'Verified', cls: 'bg-ok-soft text-ok', dot: 'bg-ok' },
  CORRECTED: { label: 'Corrected', cls: 'bg-accent-soft text-accent', dot: 'bg-accent' },
}
const s = computed(() => MAP[props.status] || { label: props.status || '—', cls: 'bg-black/5 text-ink-2', dot: 'bg-muted' })
const changed = ref(false)
watch(() => props.status, (now, before) => { changed.value = !!before && now !== before })
</script>
