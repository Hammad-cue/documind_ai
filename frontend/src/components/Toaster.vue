<template>
  <div class="pointer-events-none fixed top-4 right-4 z-[60] flex w-[min(360px,calc(100%-32px))] flex-col gap-2" role="status" aria-live="polite">
    <TransitionGroup name="toast">
      <div v-for="t in toasts" :key="t.id" class="glass-strong pointer-events-auto flex items-start gap-3 rounded-[18px] p-3.5 pr-2">
        <span :class="['animate-pop mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-full', TONE[t.tone].cls]" aria-hidden="true">
          <component :is="TONE[t.tone].icon" :size="15" :stroke-width="2.4" />
        </span>
        <div class="min-w-0 flex-1 pt-0.5">
          <p class="text-sm font-semibold text-ink">{{ t.message }}</p>
          <p v-if="t.detail" class="mt-0.5 text-[13px] text-muted">{{ t.detail }}</p>
        </div>
        <button type="button" aria-label="Dismiss" class="flex h-8 w-8 items-center justify-center rounded-full text-muted hover:bg-black/5" @click="dismiss(t.id)"><X :size="15" /></button>
      </div>
    </TransitionGroup>
  </div>
</template>

<script setup>
import { Check, Info, TriangleAlert, X } from '@lucide/vue'
import { dismiss, toasts } from '../toast'

const TONE = {
  ok: { icon: Check, cls: 'bg-ok-soft text-ok' },
  info: { icon: Info, cls: 'bg-accent-soft text-accent' },
  bad: { icon: TriangleAlert, cls: 'bg-bad-soft text-bad' },
}
</script>
