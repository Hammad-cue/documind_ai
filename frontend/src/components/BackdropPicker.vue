<template>
  <div role="radiogroup" :aria-label="label" class="grid grid-cols-2 gap-3 sm:grid-cols-3">
    <button v-for="o in options" :key="o.value" type="button" role="radio" :aria-checked="modelValue === o.value"
            @click="emit('update:modelValue', o.value)"
            :class="['group lift relative overflow-hidden rounded-[18px] border bg-white/60 p-1.5 text-left transition',
                     modelValue === o.value ? 'border-accent/50 ring-4 ring-accent/10' : 'border-white hover:bg-white/80']">
      <div class="relative h-24 overflow-hidden rounded-[13px] bg-canvas" :style="STILL[o.value] || {}">
        <canvas v-if="o.moving" :key="o.value + prefs.mode" :ref="el => paint(el, o.value)" class="absolute inset-0 h-full w-full" />
        <span v-if="modelValue === o.value" class="animate-pop absolute top-2 right-2 flex h-6 w-6 items-center justify-center rounded-full bg-accent text-on-accent shadow-[0_4px_12px_rgb(47_75_224/0.35)]">
          <Check :size="14" :stroke-width="2.6" aria-hidden="true" />
        </span>
      </div>
      <div class="px-1.5 pt-2 pb-1">
        <div class="flex items-center gap-1.5 text-sm font-semibold">
          {{ o.label }}
          <span v-if="o.moving" class="chip bg-accent-soft px-1.5 py-0 text-[10px] text-accent">Moves</span>
        </div>
        <div class="mt-0.5 text-xs leading-snug text-muted">{{ o.note }}</div>
      </div>
    </button>
  </div>
</template>

<script setup>
import { Check } from '@lucide/vue'
import { drawStill, readSceneColors } from '../backdrops'
import { prefs } from '../session'

defineProps({ modelValue: String, options: Array, label: String })
const emit = defineEmits(['update:modelValue'])

const STILL = {
  dots: { backgroundImage: 'radial-gradient(var(--dot) 1px, transparent 1.3px)', backgroundSize: '22px 22px' },
  grain: { backgroundImage: 'var(--grain)', backgroundSize: '160px 160px' },
}

// how much of the page each tile shows: patterns with large features need more of it to read
const ZOOM = { contours: 3, constellation: 1.6, grid: 1, flow: 2 }

/** Each tile shows one still frame of its background. */
function paint(el, kind) {
  if (!el || el.dataset.done) return
  requestAnimationFrame(() => {
    const dpr = Math.min(window.devicePixelRatio || 1, 2)
    el.width = el.clientWidth * dpr
    el.height = el.clientHeight * dpr
    readSceneColors()
    drawStill(el, kind, dpr, ZOOM[kind] || 1)
    el.dataset.done = '1'
  })
}
</script>
