<template>
  <header class="flex flex-wrap items-end justify-between gap-4">
    <div class="min-w-0">
      <p v-if="eyebrow" class="text-[13px] font-medium text-muted">{{ eyebrow }}</p>
      <h1 class="mt-1 text-[30px] leading-tight font-bold tracking-[-0.03em] sm:text-[34px]">{{ title }}</h1>
      <p v-if="subtitle" class="mt-1.5 max-w-2xl text-[15px] text-muted">{{ subtitle }}</p>
    </div>
    <div v-if="$slots.default" class="flex flex-wrap items-center gap-2"><slot /></div>
  </header>
</template>

<script setup>
defineProps({ title: String, subtitle: String, eyebrow: String })
</script>
