<template>
  <div class="flex min-h-full items-center justify-center px-4 py-12">
    <Transition name="rise" appear>
      <div class="w-full max-w-[460px]">
        <router-link to="/" class="mb-8 flex justify-center"><Logo /></router-link>
        <form class="glass-strong space-y-4 rounded-[28px] p-7" @submit.prevent="submit">
          <div>
            <h1 class="text-[24px] font-bold tracking-[-0.03em]">Create your organization</h1>
            <p class="mt-1 text-sm text-muted">You'll be its first admin and can add your team afterwards.</p>
          </div>
          <div><label class="label" for="r-org">Organization name</label><input id="r-org" v-model="form.organization_name" class="input" placeholder="e.g. Khan & Associates" required /></div>
          <div class="grid grid-cols-2 gap-3">
            <div><label class="label" for="r-first">First name</label><input id="r-first" v-model="form.first_name" class="input" /></div>
            <div><label class="label" for="r-last">Last name</label><input id="r-last" v-model="form.last_name" class="input" /></div>
          </div>
          <div><label class="label" for="r-user">Username</label><input id="r-user" v-model="form.username" class="input" autocomplete="username" required /></div>
          <div><label class="label" for="r-email">Email</label><input id="r-email" v-model="form.email" type="email" class="input" required /></div>
          <div>
            <label class="label" for="r-pass">Password</label>
            <input id="r-pass" v-model="form.password" type="password" class="input" autocomplete="new-password" required />
            <p class="mt-1.5 text-xs text-muted">At least 8 characters and not a common password.</p>
          </div>
          <p v-if="error" class="rounded-[14px] bg-bad-soft px-3.5 py-2.5 text-sm text-bad">{{ error }}</p>
          <p v-if="done" class="rounded-[14px] bg-ok-soft px-3.5 py-2.5 text-sm text-ok">Organization created. Taking you to sign in…</p>
          <button class="btn-primary w-full" :disabled="busy">{{ busy ? 'Creating…' : 'Create organization' }}</button>
          <p class="text-center text-sm text-muted">Already have an account? <router-link to="/login" class="link">Sign in</router-link></p>
        </form>
      </div>
    </Transition>
  </div>
</template>

<script setup>
import { reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import api, { errorText } from '../api'
import Logo from '../components/Logo.vue'

const router = useRouter()
const form = reactive({ organization_name: '', first_name: '', last_name: '', username: '', email: '', password: '' })
const error = ref('')
const busy = ref(false)
const done = ref(false)

async function submit() {
  busy.value = true
  error.value = ''
  try {
    await api.post('/auth/register-organization/', form)
    done.value = true
    setTimeout(() => router.push('/login'), 1200)
  } catch (e) {
    error.value = errorText(e)
  } finally {
    busy.value = false
  }
}
</script>
