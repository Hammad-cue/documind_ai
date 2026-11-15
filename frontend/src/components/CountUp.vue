<template>
  <span class="tabular-nums">{{ shown }}</span>
</template>

<script setup>
import { onBeforeUnmount, ref, watch } from 'vue'

const props = defineProps({ value: { type: Number, default: 0 }, ms: { type: Number, default: 800 } })
const shown = ref(0)
let raf = null

function animate(from, to) {
  cancelAnimationFrame(raf)
  if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) { shown.value = to; return }
  const start = performance.now()
  const step = now => {
    const t = Math.min(1, (now - start) / props.ms)
    const eased = 1 - Math.pow(1 - t, 3)
    shown.value = Math.round(from + (to - from) * eased)
    if (t < 1) raf = requestAnimationFrame(step)
  }
  raf = requestAnimationFrame(step)
}

watch(() => props.value, (to, from) => animate(from ?? 0, to), { immediate: true })
onBeforeUnmount(() => cancelAnimationFrame(raf))
</script>
