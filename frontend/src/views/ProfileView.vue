<template>
  <div class="h-full overflow-y-auto scroll-thin">
    <div class="mx-auto max-w-[720px] px-4 py-8 sm:px-6 lg:py-10">
      <PageHeader title="Profile" />

      <form v-if="me" class="panel mt-7 space-y-5 p-6" @submit.prevent="save">
        <div class="flex items-center gap-4">
          <img v-if="preview || me.avatar" :src="preview || me.avatar" alt="" class="h-16 w-16 rounded-full object-cover" />
          <div v-else aria-hidden="true" class="flex h-16 w-16 items-center justify-center rounded-full bg-[#E4E8FB] text-[#2A3A9C] text-xl font-bold">{{ me.full_name[0].toUpperCase() }}</div>
          <label class="btn-ghost cursor-pointer">Change photo<input type="file" accept="image/*" class="sr-only" @change="pickAvatar" /></label>
        </div>
        <div class="grid gap-3 sm:grid-cols-2">
          <div><label class="label" for="p-first">First name</label><input id="p-first" v-model="form.first_name" class="input" /></div>
          <div><label class="label" for="p-last">Last name</label><input id="p-last" v-model="form.last_name" class="input" /></div>
          <div><label class="label" for="p-email">Email</label><input id="p-email" v-model="form.email" type="email" class="input" /></div>
          <div><label class="label" for="p-job">Job title</label><input id="p-job" v-model="form.job_title" class="input" /></div>
        </div>
        <dl class="grid grid-cols-3 gap-3 rounded-[16px] bg-white/60 p-4 text-sm">
          <div><dt class="text-xs text-muted">Username</dt><dd class="mt-0.5 font-semibold">{{ me.username }}</dd></div>
          <div><dt class="text-xs text-muted">Role</dt><dd class="mt-0.5 font-semibold">{{ me.role_label }}</dd></div>
          <div><dt class="text-xs text-muted">Department</dt><dd class="mt-0.5 font-semibold">{{ me.department?.name || '—' }}</dd></div>
        </dl>
        <p v-if="msg" class="text-sm" :class="err ? 'text-bad' : 'text-ok'">{{ msg }}</p>
        <div class="flex justify-end"><button class="btn-primary" :disabled="busy">Save changes</button></div>
      </form>

      <section class="panel mt-5 p-6">
        <h2 class="text-[15px] font-semibold">Appearance</h2>
        <p class="mt-1 text-sm text-muted">The background behind the panels. Saved on this device only.</p>
        <Segmented class="mt-4" :model-value="prefs.backdrop" label="Background" @update:model-value="setBackdrop" :options="BACKDROPS" />
      </section>
    </div>
  </div>
</template>

<script setup>
import { computed, reactive, ref } from 'vue'
import api, { errorText } from '../api'
import PageHeader from '../components/PageHeader.vue'
import Segmented from '../components/Segmented.vue'
import { BACKDROPS, prefs, session, setBackdrop } from '../session'
import { toast } from '../toast'

const me = computed(() => session.me)
const form = reactive({ first_name: me.value.first_name, last_name: me.value.last_name, email: me.value.email, job_title: me.value.job_title })
const avatar = ref(null)
const preview = ref(null)
const msg = ref('')
const err = ref(false)
const busy = ref(false)

function pickAvatar(e) {
  avatar.value = e.target.files[0]
  if (avatar.value) preview.value = URL.createObjectURL(avatar.value)
}

async function save() {
  busy.value = true
  msg.value = ''
  const fd = new FormData()
  Object.entries(form).forEach(([k, v]) => fd.append(k, v ?? ''))
  if (avatar.value) fd.append('avatar', avatar.value)
  try {
    session.me = (await api.patch('/auth/me/', fd)).data
    err.value = false
    msg.value = ''
    toast('Profile saved')
  } catch (e) { err.value = true; msg.value = errorText(e) } finally { busy.value = false }
}
</script>
