<template>
  <DialogRoot :open="open" @update:open="v => !v && emit('close')">
    <DialogPortal>
      <Transition name="fade">
        <DialogOverlay v-if="open" class="fixed inset-0 z-50 bg-scrim backdrop-blur-[2px]" />
      </Transition>
      <Transition name="drawer">
        <DialogContent v-if="open"
          class="glass-strong fixed inset-y-3 right-3 z-50 flex w-[min(400px,calc(100%-24px))] flex-col rounded-[26px] p-5 outline-none">
          <div class="flex items-start justify-between gap-3 pr-1">
            <div>
              <DialogTitle class="text-lg font-bold tracking-[-0.01em]">Your questions</DialogTitle>
              <DialogDescription class="mt-0.5 text-sm text-muted">Only you can see these conversations.</DialogDescription>
            </div>
            <DialogClose aria-label="Close" class="flex h-10 w-10 shrink-0 items-center justify-center rounded-full text-muted hover:bg-black/5 hover:text-ink">
              <X :size="18" />
            </DialogClose>
          </div>

          <div class="glass-soft mt-4 flex min-h-11 items-center gap-2 rounded-[14px] px-3.5">
            <Search :size="16" class="text-muted" aria-hidden="true" />
            <label for="history-filter" class="sr-only">Search your questions</label>
            <input id="history-filter" v-model="filter" placeholder="Search your questions" autocomplete="off"
                   class="min-w-0 flex-1 bg-transparent text-sm outline-none" />
          </div>

          <div class="-mx-2 mt-3 min-h-0 flex-1 overflow-y-auto px-2 scroll-thin">
            <p v-if="!session.conversations.length" class="py-10 text-center text-sm text-muted">No questions yet. Ask one and it appears here.</p>
            <p v-else-if="!groups.length" class="py-10 text-center text-sm text-muted">Nothing matches “{{ filter }}”.</p>
            <section v-for="g in groups" :key="g.name" class="mb-3">
              <h3 class="px-2 pt-1 pb-1.5 text-xs font-semibold text-muted">{{ g.name }}</h3>
              <ul class="stagger">
                <li v-for="c in g.items" :key="c.id" class="group relative">
                  <router-link :to="`/app/ask/${c.id}`" @click="emit('close')"
                    :class="['flex items-center gap-3 rounded-[12px] px-2 py-2.5 pr-11 transition-colors',
                             c.id === currentId ? 'bg-accent-soft text-accent' : 'hover:bg-white/80']">
                    <MessageSquare :size="16" class="shrink-0 opacity-60" aria-hidden="true" />
                    <span class="min-w-0 flex-1">
                      <span class="block truncate text-[14px] font-medium">{{ c.title || 'Untitled question' }}</span>
                      <span class="block text-xs text-muted">{{ fmtAgo(c.updated_at) }}</span>
                    </span>
                  </router-link>
                  <button type="button" :aria-label="confirmId === c.id ? `Confirm delete ${c.title}` : `Delete ${c.title}`"
                          :class="['absolute top-1/2 right-1.5 flex h-8 -translate-y-1/2 items-center justify-center rounded-[10px] transition',
                                   confirmId === c.id ? 'w-auto bg-bad px-2.5 text-xs font-semibold text-on-accent' : 'w-8 text-muted opacity-0 group-hover:opacity-100 focus-visible:opacity-100 hover:bg-bad-soft hover:text-bad']"
                          @click="remove(c)" @blur="confirmId = null">
                    <template v-if="confirmId === c.id">Delete</template>
                    <Trash2 v-else :size="15" />
                  </button>
                </li>
              </ul>
            </section>
          </div>
        </DialogContent>
      </Transition>
    </DialogPortal>
  </DialogRoot>
</template>

<script setup>
import { MessageSquare, Search, Trash2, X } from '@lucide/vue'
import { DialogClose, DialogContent, DialogDescription, DialogOverlay, DialogPortal, DialogRoot, DialogTitle } from 'reka-ui'
import { computed, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import api, { errorText } from '../api'
import { fmtAgo, groupByDay } from '../format'
import { loadRecent, session } from '../session'
import { toast } from '../toast'

const props = defineProps({ open: Boolean, currentId: Number })
const emit = defineEmits(['close'])
const router = useRouter()
const filter = ref('')
const confirmId = ref(null)

watch(() => props.open, v => { if (v) { filter.value = ''; confirmId.value = null; loadRecent() } })

const groups = computed(() => {
  const f = filter.value.trim().toLowerCase()
  return groupByDay(session.conversations.filter(c => !f || (c.title || '').toLowerCase().includes(f)))
})

/** First click arms the button, second click deletes. */
async function remove(c) {
  if (confirmId.value !== c.id) { confirmId.value = c.id; return }
  try {
    await api.delete(`/assistant/conversations/${c.id}/`)
    confirmId.value = null
    await loadRecent()
    if (c.id === props.currentId) router.push('/app/ask')
    toast('Conversation deleted')
  } catch (e) { toast(errorText(e), { tone: 'bad' }) }
}
</script>
