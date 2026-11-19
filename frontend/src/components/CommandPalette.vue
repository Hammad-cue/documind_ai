<template>
  <DialogRoot :open="open" @update:open="v => emit('update:open', v)">
    <DialogPortal>
      <Transition name="fade">
        <DialogOverlay v-if="open" class="fixed inset-0 z-50 bg-ink/20 backdrop-blur-[2px]" />
      </Transition>
      <Transition name="rise">
        <DialogContent v-if="open"
          class="glass-strong fixed top-[12vh] left-1/2 z-50 flex max-h-[70vh] w-[calc(100%-32px)] max-w-[620px] -translate-x-1/2 flex-col overflow-hidden rounded-[24px] outline-none"
          @keydown="onKey">
          <DialogTitle class="sr-only">Search or jump to</DialogTitle>
          <DialogDescription class="sr-only">Type to search documents, pages and past questions, or ask the assistant. Use the arrow keys and Enter to open a result.</DialogDescription>
          <div class="flex items-center gap-3 border-b border-line px-5">
            <Search :size="19" class="shrink-0 text-muted" aria-hidden="true" />
            <input ref="inputEl" v-model="q" role="combobox" aria-autocomplete="list" aria-controls="palette-list"
                   :aria-activedescendant="flat[active] ? `pal-${active}` : undefined" aria-label="Search documents, pages and past questions"
                   placeholder="Search documents, pages, past questions… or ask anything"
                   class="min-h-[60px] flex-1 bg-transparent text-[16px] text-ink outline-none placeholder:text-muted/80" />
            <kbd class="hidden rounded-md border border-line bg-white/70 px-1.5 py-px text-[11px] text-muted sm:block">Esc</kbd>
          </div>

          <ul id="palette-list" role="listbox" class="min-h-0 flex-1 overflow-y-auto p-2 scroll-thin">
            <template v-for="g in groups" :key="g.name">
              <li v-if="g.items.length" role="presentation" class="px-3 pt-3 pb-1.5 text-xs font-semibold text-muted">{{ g.name }}</li>
              <li v-for="item in g.items" :key="item.key" :id="`pal-${item.index}`" role="option" :aria-selected="item.index === active"
                  @mousemove="active = item.index" @click="run(item)"
                  :class="['flex min-h-12 cursor-pointer items-center gap-3 rounded-[14px] px-3 transition-colors', item.index === active ? 'bg-white shadow-[0_2px_10px_rgb(28_38_90/0.08)]' : '']">
                <span :class="['flex h-8 w-8 shrink-0 items-center justify-center rounded-[10px]', item.tint || 'bg-black/5 text-ink-2']" aria-hidden="true">
                  <component :is="item.icon" :size="16" />
                </span>
                <span class="min-w-0 flex-1">
                  <span class="block truncate text-[14px] font-medium text-ink">{{ item.label }}</span>
                  <span v-if="item.hint" class="block truncate text-xs text-muted">{{ item.hint }}</span>
                </span>
                <CornerDownLeft v-if="item.index === active" :size="15" class="shrink-0 text-muted" aria-hidden="true" />
              </li>
            </template>
            <li v-if="!flat.length" class="px-3 py-10 text-center text-sm text-muted">Nothing found.</li>
          </ul>

          <div id="palette-hint" class="flex items-center gap-4 border-t border-line px-5 py-2.5 text-xs text-muted">
            <span><kbd class="rounded border border-line bg-white/70 px-1">↑</kbd> <kbd class="rounded border border-line bg-white/70 px-1">↓</kbd> to move</span>
            <span><kbd class="rounded border border-line bg-white/70 px-1">Enter</kbd> to open</span>
          </div>
        </DialogContent>
      </Transition>
    </DialogPortal>
  </DialogRoot>
</template>

<script setup>
import { BookOpen, CircleCheck, CornerDownLeft, FilePlus, FileText, History, MessageSquare, PenLine, Search, Sparkles, Table2, UserRound, Users } from '@lucide/vue'
import { DialogContent, DialogDescription, DialogOverlay, DialogPortal, DialogRoot, DialogTitle } from 'reka-ui'
import { computed, nextTick, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import api from '../api'
import { can, session } from '../session'

const props = defineProps({ open: Boolean })
const emit = defineEmits(['update:open'])
const router = useRouter()
const q = ref('')
const active = ref(0)
const docs = ref([])
const inputEl = ref(null)

const match = (text, query) => (text || '').toLowerCase().includes(query)

const groups = computed(() => {
  const query = q.value.trim().toLowerCase()
  const pages = [
    { key: 'p-ask', label: 'Ask', icon: Search, to: '/app/ask' },
    { key: 'p-docs', label: 'Documents', icon: FileText, to: '/app/documents' },
    { key: 'p-add', label: 'Add a document', icon: FilePlus, to: '/app/documents?upload=1', hint: 'Upload a PDF, Word file or photo', show: can('upload') },
    { key: 'p-rec', label: 'Records', icon: Table2, to: '/app/records' },
    { key: 'p-rev', label: 'Review', icon: CircleCheck, to: '/app/review', show: can('verify') },
    { key: 'p-team', label: 'Team & access', icon: Users, to: '/app/team', show: can('manage_team') },
    { key: 'p-audit', label: 'Activity log', icon: History, to: '/app/audit', show: can('view_audit') },
    { key: 'p-prof', label: 'Profile & appearance', icon: UserRound, to: '/app/profile' },
  ].filter(p => p.show !== false && (!query || match(p.label, query)))

  const documents = docs.value
    .filter(d => !query || match(d.title, query) || match(d.doc_type, query))
    .slice(0, query ? 8 : 5)
    .map(d => ({
      key: `d-${d.id}`, label: d.title, hint: d.doc_type, to: `/app/documents/${d.id}`,
      icon: d.kind === 'REFERENCE' ? BookOpen : d.file_type === 'IMAGE' ? PenLine : FileText,
      tint: d.kind === 'RECORD' ? 'bg-[#EEEAFF] text-[#5B3FD9]' : 'bg-accent-soft text-accent',
    }))

  const recent = session.recent
    .filter(c => !query || match(c.title, query))
    .slice(0, query ? 5 : 3)
    .map(c => ({ key: `c-${c.id}`, label: c.title, icon: MessageSquare, to: `/app/ask/${c.id}`, hint: 'Earlier question' }))

  const ask = q.value.trim()
    ? [{ key: 'ask', label: `Ask “${q.value.trim()}”`, hint: 'Answer from the documents you can access', icon: Sparkles, tint: 'bg-accent text-white',
         to: { path: '/app/ask', query: { q: q.value.trim() } } }]
    : []

  let index = 0
  const tag = list => list.map(item => ({ ...item, index: index++ }))
  return [
    { name: 'Ask', items: tag(ask) },
    { name: 'Documents', items: tag(documents) },
    { name: 'Go to', items: tag(pages) },
    { name: 'Earlier questions', items: tag(recent) },
  ]
})
const flat = computed(() => groups.value.flatMap(g => g.items))

function run(item) {
  emit('update:open', false)
  router.push(item.to)
}

function onKey(e) {
  if (e.key === 'ArrowDown') { e.preventDefault(); active.value = (active.value + 1) % Math.max(1, flat.value.length); scrollActive() }
  else if (e.key === 'ArrowUp') { e.preventDefault(); active.value = (active.value - 1 + flat.value.length) % Math.max(1, flat.value.length); scrollActive() }
  else if (e.key === 'Enter' && flat.value[active.value]) { e.preventDefault(); run(flat.value[active.value]) }
}
function scrollActive() { nextTick(() => document.getElementById(`pal-${active.value}`)?.scrollIntoView({ block: 'nearest' })) }

watch(q, () => { active.value = 0 })
watch(() => props.open, async isOpen => {
  if (!isOpen) return
  q.value = ''
  active.value = 0
  await nextTick()
  inputEl.value?.focus()
  try { docs.value = (await api.get('/documents/')).data } catch { /* palette still works for pages */ }
})
</script>
