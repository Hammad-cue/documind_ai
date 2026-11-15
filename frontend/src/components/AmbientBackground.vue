<template>
  <!-- Neutral page background. No colour washes: paper grain (default), a faint dot grid, or plain. -->
  <div aria-hidden="true" class="pointer-events-none fixed inset-0 -z-10 bg-canvas" :style="STYLES[prefs.backdrop] || STYLES.grain" />
</template>

<script setup>
import { prefs } from '../session'

const STYLES = {
  plain: {},
  dots: {
    backgroundImage: 'radial-gradient(rgb(11 18 32 / 0.13) 1px, transparent 1.3px)',
    backgroundSize: '22px 22px',
    backgroundPosition: '-11px -11px',
  },
  grain: { backgroundImage: 'var(--grain)', backgroundSize: '160px 160px' },
}
</script>
