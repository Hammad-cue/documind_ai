<template>
  <div class="min-h-full">
    <header class="glass sticky top-4 z-10 mx-4 flex items-center justify-between rounded-[22px] px-5 py-2.5 sm:mx-auto sm:max-w-[1120px]">
      <Logo />
      <nav class="flex items-center gap-2" aria-label="Account">
        <router-link to="/login" class="btn text-ink-2 hover:bg-white/70">Sign in</router-link>
        <router-link to="/register" class="btn-dark">Get started</router-link>
      </nav>
    </header>

    <main class="mx-auto max-w-[1120px] px-4 pt-20 pb-24 sm:px-6">
      <section class="stagger mx-auto max-w-3xl text-center">
        <span class="chip glass-soft py-1 text-ink-2"><span class="h-1.5 w-1.5 rounded-full bg-ok" aria-hidden="true" />Records intelligence for legal teams</span>
        <h1 class="mt-6 text-[44px] leading-[1.02] font-extrabold tracking-[-0.045em] sm:text-[64px]">Every contract your team holds. Answered in seconds.</h1>
        <p class="mx-auto mt-6 max-w-2xl text-[18px] leading-relaxed text-muted">
          Upload printed, scanned or handwritten documents. DocuMind reads them, keeps their key facts in one register,
          and answers questions with the exact page — only from what each person is allowed to see.
        </p>
        <div class="mt-9 flex flex-wrap justify-center gap-3">
          <router-link to="/register" class="btn-primary min-h-12 px-6 text-[15px]">Create your organization<ArrowRight :size="17" /></router-link>
          <router-link to="/login" class="btn-ghost min-h-12 px-6 text-[15px]">Sign in</router-link>
        </div>
      </section>

      <!-- self-playing demo -->
      <section aria-label="How it works, shown as a short looping example" class="mx-auto mt-16 max-w-[760px]">
        <div class="relative min-h-[250px]" aria-hidden="true">
          <Transition name="rise" mode="out-in">
            <div v-if="phase === 'thinking'" key="t" class="panel p-6">
              <p class="text-[20px] font-semibold tracking-[-0.02em]">{{ demo.q }}</p>
              <div class="mt-4 flex items-center gap-3 text-sm text-ink-2">
                <span class="h-4 w-4 animate-spin rounded-full border-2 border-accent border-t-transparent" />Reading the documents you can access…
              </div>
              <div class="mt-5 space-y-2"><div class="shimmer h-3.5 w-full rounded-md" /><div class="shimmer h-3.5 w-3/4 rounded-md" /></div>
            </div>

            <div v-else-if="phase === 'answer'" :key="`a${index}`" class="panel p-6 sm:p-7">
              <div class="flex items-center gap-2 text-[13px] font-medium text-muted"><span class="h-2 w-2 rounded-full" :class="demo.dot" />{{ demo.kind }} · {{ demo.time }}</div>
              <p class="mt-2 text-[20px] font-semibold tracking-[-0.02em]">{{ demo.q }}</p>

              <div v-if="demo.fact" class="mt-4 flex flex-wrap items-end justify-between gap-4 rounded-[20px] bg-white/75 p-5">
                <div><div class="text-[13px] text-muted">{{ demo.fact.label }}</div><div class="animate-pop mt-1 text-[32px] leading-none font-bold tracking-[-0.03em]">{{ demo.fact.value }}</div></div>
                <span class="chip animate-stamp bg-ok-soft text-ok"><span class="h-1.5 w-1.5 rounded-full bg-ok" />Verified · page {{ demo.fact.page }}</span>
              </div>
              <template v-else>
                <p class="mt-3 text-[16px] leading-[1.7] text-ink-2"><template v-for="(w, i) in demo.words" :key="i"><span class="reveal-word" :style="{ animationDelay: `${i * 35}ms` }">{{ w }}</span>{{ ' ' }}</template></p>
                <div class="mt-4 flex items-center gap-3.5 rounded-[18px] bg-white/70 p-3">
                  <PageThumb />
                  <span><span class="block text-[14px] font-semibold">{{ demo.source.title }}</span><span class="block text-[13px] text-muted">{{ demo.source.where }}</span></span>
                </div>
              </template>
            </div>
            <div v-else key="idle" class="flex h-[250px] items-center justify-center text-sm text-muted">Ask anything about your records…</div>
          </Transition>
        </div>

        <div class="glass-strong mx-auto mt-4 flex max-w-[680px] items-center gap-3 rounded-[30px] py-2 pr-2 pl-5" aria-hidden="true">
          <Search :size="19" class="shrink-0 text-muted" />
          <span class="min-w-0 flex-1 truncate text-[16px]" :class="typed ? 'text-ink' : 'text-muted'">{{ typed || 'Ask about a contract, a date or a clause…' }}<span v-if="phase === 'typing'" class="ml-px inline-block h-5 w-[2px] translate-y-1 animate-pulse bg-accent" /></span>
          <span class="flex h-11 w-11 shrink-0 items-center justify-center rounded-full text-white transition" :class="phase === 'typing' && typed.length === demo.q.length ? 'scale-110 bg-accent-hover' : 'bg-accent'"><ArrowUp :size="19" /></span>
        </div>
        <p class="sr-only">Example: asking “When was the NDA with Acme signed?” returns 12 March 2025 from page 3 of the agreement.</p>
      </section>

      <section class="stagger mt-24 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <div v-for="f in features" :key="f.title" class="panel lift p-5">
          <span class="flex h-10 w-10 items-center justify-center rounded-[12px] bg-white text-accent shadow-[0_4px_12px_rgb(28_38_90/0.08)]"><component :is="f.icon" :size="19" aria-hidden="true" /></span>
          <h2 class="mt-4 font-semibold">{{ f.title }}</h2>
          <p class="mt-1.5 text-sm leading-relaxed text-muted">{{ f.body }}</p>
        </div>
      </section>
    </main>
  </div>
</template>

<script setup>
import { ArrowRight, ArrowUp, BookOpen, Lock, PenLine, Search, Table2 } from '@lucide/vue'
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import Logo from '../components/Logo.vue'
import PageThumb from '../components/PageThumb.vue'

const features = [
  { icon: Table2, title: 'A register of facts', body: 'Parties, dates, terms and values pulled from every agreement — each linked to the page it came from.' },
  { icon: PenLine, title: 'Reads handwriting', body: 'Handwritten deeds and receipts are transcribed, and anything uncertain goes to a person to confirm.' },
  { icon: BookOpen, title: 'Knows the law book', body: 'Long reference documents are indexed by chapter and section, so answers cite exactly where they stand.' },
  { icon: Lock, title: 'Access and history', body: 'Roles, departments and private documents — plus versions, edits and a log of everything that happens.' },
]

// Real answers from the demo organization, replayed on a loop.
const DEMOS = [
  { q: 'When was the NDA with Acme signed?', kind: 'From the records register', time: '1.4 s', dot: 'bg-[#7C5CFF]',
    fact: { label: 'Signing date · NDA — Acme Corp', value: '12 March 2025', page: 3 } },
  { q: 'Is an agreement without consideration valid?', kind: 'Answered from documents', time: '2.1 s', dot: 'bg-accent',
    words: 'No. Every agreement must be supported by consideration. Without it the agreement is void, unless it is in writing, registered, and made out of natural love and affection between near relatives.'.split(' '),
    source: { title: 'Contracts Handbook', where: 'Chapter I › 2. Consideration · page 1' } },
  { q: 'When does the Acme NDA expire?', kind: 'From the records register', time: '1.2 s', dot: 'bg-[#7C5CFF]',
    fact: { label: 'Expiry date · NDA — Acme Corp (version 2)', value: '31 March 2028', page: 2 } },
]

const index = ref(0)
const phase = ref('idle')
const typed = ref('')
const demo = computed(() => DEMOS[index.value])
let timers = []
const later = (fn, ms) => timers.push(setTimeout(fn, ms))

function play() {
  const reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches
  const q = demo.value.q
  if (reduce) { typed.value = q; phase.value = 'answer'; return }
  phase.value = 'typing'
  typed.value = ''
  for (let i = 1; i <= q.length; i++) later(() => { typed.value = q.slice(0, i) }, 300 + i * 38)
  const typedAt = 300 + q.length * 38
  later(() => { phase.value = 'thinking'; typed.value = '' }, typedAt + 450)
  later(() => { phase.value = 'answer' }, typedAt + 1700)
  later(() => { index.value = (index.value + 1) % DEMOS.length; play() }, typedAt + 6800)
}

onMounted(() => later(play, 600))
onBeforeUnmount(() => timers.forEach(clearTimeout))
</script>
