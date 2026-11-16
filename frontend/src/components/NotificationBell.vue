<template>
  <PopoverRoot v-model:open="open">
    <PopoverTrigger :aria-label="unread ? `Notifications, ${unread} unread` : 'Notifications'"
      class="relative flex h-10 w-10 items-center justify-center rounded-[12px] text-ink-2 transition hover:bg-white/70 hover:text-ink">
      <Bell :size="18" :class="ring && 'animate-[ring_0.8s_ease]'" />
      <span v-if="unread" :key="unread" class="animate-pop absolute top-1.5 right-1.5 flex h-[17px] min-w-[17px] items-center justify-center rounded-full bg-bad px-1 text-[10px] font-bold text-white ring-2 ring-white">{{ unread > 9 ? '9+' : unread }}</span>
    </PopoverTrigger>
    <PopoverPortal>
      <PopoverContent side="right" align="start" :side-offset="12" :collision-padding="16"
        class="glass-strong z-50 flex max-h-[min(560px,80vh)] w-[min(380px,calc(100vw-32px))] flex-col overflow-hidden rounded-[22px] outline-none">
        <div class="flex items-center justify-between border-b border-line px-4 py-3">
          <h2 class="text-[15px] font-semibold">Notifications</h2>
          <button v-if="unread" type="button" class="rounded-lg px-2 py-1 text-[13px] font-medium text-accent hover:bg-accent-soft" @click="markAll">Mark all read</button>
        </div>
        <ul class="min-h-0 flex-1 overflow-y-auto p-2 scroll-thin">
          <li v-for="n in items" :key="n.id">
            <button type="button" @click="openItem(n)"
              :class="['flex w-full gap-3 rounded-[14px] p-3 text-left transition hover:bg-white', !n.read && 'bg-white/60']">
              <span :class="['flex h-9 w-9 shrink-0 items-center justify-center rounded-[11px]', KIND[n.kind]?.cls]" aria-hidden="true">
                <component :is="KIND[n.kind]?.icon" :size="16" />
              </span>
              <span class="min-w-0 flex-1">
                <span class="flex items-start gap-2">
                  <span class="flex-1 text-[13.5px] leading-snug font-semibold text-ink">{{ n.title }}</span>
                  <span v-if="!n.read" class="mt-1.5 h-2 w-2 shrink-0 rounded-full bg-accent" aria-label="unread" />
                </span>
                <span v-if="n.body" class="mt-0.5 block text-[12.5px] leading-snug text-muted">{{ n.body }}</span>
                <span class="mt-1 block text-[11.5px] text-muted">{{ ago(n.created_at) }}</span>
              </span>
            </button>
          </li>
          <li v-if="!items.length" class="flex flex-col items-center px-6 py-10 text-center">
            <span class="flex h-11 w-11 items-center justify-center rounded-full bg-white shadow-[0_4px_12px_rgb(28_38_90/0.08)]"><BellOff :size="18" class="text-muted" /></span>
            <p class="mt-3 text-sm font-semibold">You're all caught up</p>
            <p class="mt-1 text-[13px] text-muted">Expiry reminders, notice deadlines and finished uploads show up here.</p>
          </li>
        </ul>
      </PopoverContent>
    </PopoverPortal>
  </PopoverRoot>
</template>

<script setup>
import { Bell, BellOff, CalendarClock, CircleCheck, FileCheck, Hourglass, TriangleAlert } from '@lucide/vue'
import { PopoverContent, PopoverPortal, PopoverRoot, PopoverTrigger } from 'reka-ui'
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import api from '../api'

const KIND = {
  EXPIRY: { icon: CalendarClock, cls: 'bg-warn-soft text-warn' },
  NOTICE: { icon: Hourglass, cls: 'bg-bad-soft text-bad' },
  PROCESSED: { icon: FileCheck, cls: 'bg-ok-soft text-ok' },
  FAILED: { icon: TriangleAlert, cls: 'bg-bad-soft text-bad' },
  REVIEW: { icon: CircleCheck, cls: 'bg-accent-soft text-accent' },
}
const router = useRouter()
const open = ref(false)
const items = ref([])
const unread = ref(0)
const ring = ref(false)
let timer = null

async function load() {
  try {
    const { data } = await api.get('/notifications/')
    if (data.unread > unread.value && unread.value !== 0) { ring.value = true; setTimeout(() => (ring.value = false), 900) }
    items.value = data.results
    unread.value = data.unread
  } catch { /* offline: try again next tick */ }
}

async function markAll() {
  await api.post('/notifications/read/', {})
  items.value.forEach(n => (n.read = true))
  unread.value = 0
}

async function openItem(n) {
  if (!n.read) {
    n.read = true
    unread.value = Math.max(0, unread.value - 1)
    api.post('/notifications/read/', { ids: [n.id] })
  }
  open.value = false
  if (n.link) router.push(n.link)
}

function ago(iso) {
  const s = (Date.now() - new Date(iso)) / 1000
  if (s < 60) return 'just now'
  if (s < 3600) return `${Math.floor(s / 60)} min ago`
  if (s < 86400) return `${Math.floor(s / 3600)} h ago`
  return new Date(iso).toLocaleDateString('en-GB', { day: 'numeric', month: 'short' })
}

watch(open, o => o && load())
onMounted(() => { load(); timer = setInterval(load, 45000) })
onBeforeUnmount(() => clearInterval(timer))
</script>
