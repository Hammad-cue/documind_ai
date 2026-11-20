<template>
  <div role="radiogroup" aria-label="Colour mode" class="glass-soft relative grid grid-cols-3 rounded-[13px] p-1">
    <!-- the raised thumb glides to the chosen mode -->
    <span aria-hidden="true" class="absolute top-1 bottom-1 left-1 rounded-[10px] bg-white shadow-[0_2px_8px_rgb(28_38_90/0.12)] transition-transform duration-300 ease-[var(--ease-spring)]"
          :style="{ width: 'calc((100% - 8px) / 3)', transform: `translateX(${index * 100}%)` }" />
    <button v-for="o in OPTIONS" :key="o.value" type="button" role="radio" :aria-checked="prefs.theme === o.value"
            :aria-label="o.long" :title="o.long" @click="setTheme(o.value)"
            :class="['relative z-10 flex min-h-8 items-center justify-center gap-1.5 rounded-[10px] text-xs font-medium transition-colors',
                     prefs.theme === o.value ? 'text-ink' : 'text-muted hover:text-ink', compact ? 'px-2.5' : 'px-1']">
      <component :is="o.icon" :size="14" aria-hidden="true" :class="prefs.theme === o.value && 'animate-pop'" />
      <span v-if="!compact">{{ o.label }}</span>
    </button>
  </div>
</template>

<script setup>
import { Monitor, Moon, Sun } from '@lucide/vue'
import { computed } from 'vue'
import { prefs, setTheme } from '../session'

defineProps({ compact: Boolean })
const OPTIONS = [
  { value: 'light', label: 'Light', long: 'Light mode', icon: Sun },
  { value: 'dark', label: 'Dark', long: 'Dark mode', icon: Moon },
  { value: 'system', label: 'Auto', long: 'Match my device', icon: Monitor },
]
const index = computed(() => Math.max(0, OPTIONS.findIndex(o => o.value === prefs.theme)))
</script>
