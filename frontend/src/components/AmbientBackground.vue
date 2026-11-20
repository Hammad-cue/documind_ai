<template>
  <!-- Page background: neutral, no colour washes. Still styles are CSS; the moving ones are drawn on a canvas. -->
  <div aria-hidden="true" class="pointer-events-none fixed inset-0 -z-10 bg-canvas" :style="STILL[prefs.backdrop] || {}">
    <canvas v-if="animated" ref="canvas" class="absolute inset-0 h-full w-full" />
  </div>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { readSceneColors, SCENES } from '../backdrops'
import { prefs } from '../session'

const STILL = {
  plain: {},
  dots: {
    backgroundImage: 'radial-gradient(var(--dot) 1px, transparent 1.3px)',
    backgroundSize: '22px 22px',
    backgroundPosition: '-11px -11px',
  },
  grain: { backgroundImage: 'var(--grain)', backgroundSize: '160px 160px' },
}

const canvas = ref(null)
const animated = computed(() => !!SCENES[prefs.backdrop])
const FRAME_MS = 1000 / 30          // 30 frames a second is plenty for slow motion
let raf = 0, last = 0, pointer = null, state = {}, ctx = null, w = 0, h = 0
const reduced = window.matchMedia?.('(prefers-reduced-motion: reduce)')

function size() {
  const el = canvas.value
  if (!el) return
  const dpr = Math.min(window.devicePixelRatio || 1, 2)
  w = window.innerWidth; h = window.innerHeight
  el.width = Math.round(w * dpr); el.height = Math.round(h * dpr)
  ctx = el.getContext('2d')
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0)
  state = {}
}

function draw(t) {
  if (!ctx) return
  ctx.clearRect(0, 0, w, h)
  SCENES[prefs.backdrop]?.(ctx, w, h, t, pointer, state)
}

function loop(now) {
  raf = requestAnimationFrame(loop)
  if (document.hidden || now - last < FRAME_MS) return
  last = now
  draw(now)
}

function start() {
  stop()
  if (!animated.value) return
  readSceneColors()
  size()
  if (reduced?.matches) { draw(20000); return }    // a still frame, no motion
  raf = requestAnimationFrame(loop)
}
function stop() { cancelAnimationFrame(raf); raf = 0 }

function onResize() { if (animated.value) { size(); if (!raf) draw(20000) } }
function onPointer(e) { pointer = { x: e.clientX, y: e.clientY } }
function onLeave() { pointer = null }

watch(() => [prefs.backdrop, prefs.mode], async () => { await nextTick(); start() })
onMounted(() => {
  start()
  window.addEventListener('resize', onResize)
  window.addEventListener('pointermove', onPointer, { passive: true })
  document.addEventListener('pointerleave', onLeave)
  reduced?.addEventListener?.('change', start)
})
onBeforeUnmount(() => {
  stop()
  window.removeEventListener('resize', onResize)
  window.removeEventListener('pointermove', onPointer)
  document.removeEventListener('pointerleave', onLeave)
  reduced?.removeEventListener?.('change', start)
})
</script>
