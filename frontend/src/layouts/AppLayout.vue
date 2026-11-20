<template>
  <div class="flex h-full gap-4 lg:p-4">
    <!-- floating glass sidebar -->
    <aside :class="['glass fixed inset-y-3 left-3 z-40 flex w-[248px] flex-col rounded-[26px] px-3.5 py-5 transition-transform duration-300 lg:static lg:inset-auto lg:translate-x-0',
                    open ? 'translate-x-0' : '-translate-x-[110%]']">
      <div class="flex items-center justify-between pr-0.5 pl-2">
        <router-link to="/app/ask" @click="open = false"><Logo /></router-link>
        <NotificationBell />
      </div>

      <button type="button" class="glass-soft mt-6 flex min-h-10 items-center gap-2.5 rounded-[12px] px-3 text-left text-[13px] text-muted transition hover:bg-white/80 hover:text-ink"
              @click="paletteOpen = true; open = false">
        <Search :size="15" aria-hidden="true" /><span class="flex-1 truncate">Search</span>
        <kbd class="rounded-md border border-line bg-white/70 px-1.5 py-px text-[11px]">{{ modKey }} K</kbd>
      </button>

      <nav aria-label="Main" class="relative mt-4 flex flex-col gap-0.5 text-sm font-medium">
        <!-- the white pill glides to the active page -->
        <span v-if="activeIndex >= 0" aria-hidden="true"
              class="absolute inset-x-0 top-0 h-[42px] rounded-[12px] bg-white shadow-[0_2px_10px_rgb(28_38_90/0.08),inset_0_1px_0_var(--glass-hi)] transition-transform duration-[400ms] ease-[var(--ease-spring)]"
              :style="{ transform: `translateY(${activeIndex * 44}px)` }" />
        <router-link v-for="(item, i) in nav" :key="item.to" :to="item.to" @click="open = false"
          :aria-current="i === activeIndex ? 'page' : undefined"
          :class="['relative z-10 flex min-h-[42px] items-center gap-3 rounded-[12px] px-3 transition-colors',
                   i === activeIndex ? 'text-ink' : 'text-ink-2 hover:bg-white/50 hover:text-ink']">
          <component :is="item.icon" :size="18" :stroke-width="i === activeIndex ? 2.1 : 1.8" aria-hidden="true" />
          <span class="flex-1">{{ item.label }}</span>
          <span v-if="item.badge" :key="item.badge" class="animate-pop flex h-[22px] min-w-[22px] items-center justify-center rounded-full bg-accent px-1.5 text-xs font-semibold text-on-accent">{{ item.badge }}</span>
        </router-link>
      </nav>

      <!-- earlier questions live on the Ask screen (History), where they are not squeezed out by the menu -->
      <div class="flex-1" />

      <ThemeSwitch />

      <div class="mt-3 flex items-center gap-2 rounded-[18px] bg-white/50 p-2">
        <router-link to="/app/profile" class="flex min-w-0 flex-1 items-center gap-2.5 rounded-[12px] p-1 hover:bg-white/60" @click="open = false">
          <img v-if="me?.avatar" :src="me.avatar" alt="" class="h-9 w-9 rounded-full object-cover" />
          <div v-else aria-hidden="true" class="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-avatar text-sm font-semibold text-avatar-ink">
            {{ (me?.full_name || '?')[0].toUpperCase() }}
          </div>
          <div class="min-w-0 text-[13px] leading-tight">
            <div class="truncate font-semibold">{{ me?.full_name }}</div>
            <div class="truncate text-muted">{{ me?.role_label }}<span v-if="me?.department"> · {{ me.department.name }}</span></div>
          </div>
        </router-link>
        <button type="button" aria-label="Sign out" title="Sign out" @click="signOut"
                class="flex h-10 w-10 shrink-0 items-center justify-center rounded-[12px] text-muted hover:bg-white hover:text-ink">
          <LogOut :size="17" />
        </button>
      </div>
    </aside>
    <Transition name="fade"><div v-if="open" class="fixed inset-0 z-30 bg-scrim lg:hidden" @click="open = false" /></Transition>

    <!-- content -->
    <div class="flex min-w-0 flex-1 flex-col">
      <header class="flex h-14 shrink-0 items-center gap-3 px-4 lg:hidden">
        <button type="button" aria-label="Open menu" class="glass-soft flex h-11 w-11 items-center justify-center rounded-[12px]" @click="open = true"><Menu :size="20" /></button>
        <Logo />
      </header>
      <main class="relative min-h-0 flex-1">
        <router-view v-slot="{ Component, route }">
          <Transition name="page" mode="out-in">
            <component :is="Component" :key="route.name === 'conversation' || route.name === 'ask' ? 'ask' : route.path" />
          </Transition>
        </router-view>
      </main>
    </div>
    <CommandPalette v-model:open="paletteOpen" />
  </div>
</template>

<script setup>
import { CircleCheck, FileText, History, LogOut, Menu, Search, Table2, Users } from '@lucide/vue'
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import CommandPalette from '../components/CommandPalette.vue'
import Logo from '../components/Logo.vue'
import NotificationBell from '../components/NotificationBell.vue'
import ThemeSwitch from '../components/ThemeSwitch.vue'
import { loadRecent, loadReviewCount, logout, session } from '../session'

const router = useRouter()
const route = useRoute()
const open = ref(false)
const paletteOpen = ref(false)
const me = computed(() => session.me)
const modKey = /Mac|iPhone|iPad/.test(navigator.platform) ? '⌘' : 'Ctrl'
const activeIndex = computed(() => nav.value.findIndex(item => route.path.startsWith(item.to)))

function onKey(e) {
  if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'k') {
    e.preventDefault()
    paletteOpen.value = !paletteOpen.value
  }
}
onMounted(() => window.addEventListener('keydown', onKey))
onBeforeUnmount(() => window.removeEventListener('keydown', onKey))

const nav = computed(() => [
  { to: '/app/ask', label: 'Ask', icon: Search },
  { to: '/app/documents', label: 'Documents', icon: FileText },
  { to: '/app/records', label: 'Records', icon: Table2 },
  me.value?.can.verify && { to: '/app/review', label: 'Review', icon: CircleCheck, badge: session.reviewCount || null },
  me.value?.can.manage_team && { to: '/app/team', label: 'Team & access', icon: Users },
  me.value?.can.view_audit && { to: '/app/audit', label: 'Activity log', icon: History },
].filter(Boolean))

function signOut() {
  logout()
  router.push('/login')
}

onMounted(() => { loadRecent(); loadReviewCount() })
</script>
