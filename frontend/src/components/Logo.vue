<template>
  <div class="flex items-center gap-2.5">
    <div class="flex h-8 w-8 items-center justify-center rounded-[10px] bg-ink text-white shadow-[0_4px_12px_rgb(11_18_32/0.2)]" aria-hidden="true">
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round">
        <path d="M6 4h7a6 6 0 010 12H6z" /><path d="M6 20h12" /><circle cx="18" cy="20" r="0.6" fill="currentColor" />
      </svg>
    </div>
    <span v-if="!compact" class="text-[17px] font-bold tracking-[-0.02em]">DocuMind</span>
  </div>
</template>

<script setup>
defineProps({ compact: Boolean })
</script>
