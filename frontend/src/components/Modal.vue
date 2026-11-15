<template>
  <DialogRoot :open="open" @update:open="v => !v && emit('close')">
    <DialogPortal>
      <Transition name="fade">
        <DialogOverlay v-if="open" class="fixed inset-0 z-50 bg-ink/25 backdrop-blur-[3px]" />
      </Transition>
      <Transition name="rise">
        <DialogContent v-if="open"
          class="glass-strong fixed top-1/2 left-1/2 z-50 max-h-[90vh] w-[calc(100%-32px)] -translate-x-1/2 -translate-y-1/2 overflow-y-auto rounded-[26px] p-6 outline-none scroll-thin"
          :class="wide ? 'max-w-2xl' : 'max-w-lg'">
          <div class="mb-5 pr-10">
            <DialogTitle class="text-lg font-bold tracking-[-0.01em]">{{ title }}</DialogTitle>
            <DialogDescription v-if="description" class="mt-1 text-sm text-muted">{{ description }}</DialogDescription>
          </div>
          <slot />
          <DialogClose aria-label="Close" class="absolute top-4 right-4 flex h-10 w-10 items-center justify-center rounded-full text-muted hover:bg-black/5 hover:text-ink">
            <X :size="18" />
          </DialogClose>
        </DialogContent>
      </Transition>
    </DialogPortal>
  </DialogRoot>
</template>

<script setup>
import { X } from '@lucide/vue'
import { DialogClose, DialogContent, DialogDescription, DialogOverlay, DialogPortal, DialogRoot, DialogTitle } from 'reka-ui'

defineProps({ open: Boolean, title: String, description: String, wide: Boolean })
const emit = defineEmits(['close'])
</script>
