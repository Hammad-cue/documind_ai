<template>
  <div class="flex min-h-full items-center justify-center px-4 py-12">
    <Transition name="rise" appear>
      <div class="w-full max-w-[400px]">
        <router-link to="/" class="mb-8 flex justify-center"><Logo /></router-link>
        <form class="glass-strong space-y-4 rounded-[28px] p-7" @submit.prevent="submit">
          <div>
            <h1 class="text-[24px] font-bold tracking-[-0.03em]">Welcome back</h1>
            <p class="mt-1 text-sm text-muted">Sign in to your organization's records.</p>
          </div>
          <div><label class="label" for="u">Username</label><input id="u" v-model="username" class="input" autocomplete="username" required /></div>
          <div><label class="label" for="p">Password</label><input id="p" v-model="password" type="password" class="input" autocomplete="current-password" required /></div>
          <p v-if="error" class="rounded-[14px] bg-bad-soft px-3.5 py-2.5 text-sm text-bad">{{ error }}</p>
          <button class="btn-primary w-full" :disabled="busy">{{ busy ? 'Signing in…' : 'Sign in' }}</button>
          <p class="text-center text-sm text-muted">New organization? <router-link to="/register" class="link">Create one</router-link></p>
        </form>
      </div>
    </Transition>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import api, { errorText } from '../api'
import Logo from '../components/Logo.vue'
import { loadMe } from '../session'

const router = useRouter()
const route = useRoute()
const username = ref('')
const password = ref('')
const error = ref('')
const busy = ref(false)

async function submit() {
  busy.value = true
  error.value = ''
  try {
    const { data } = await api.post('/auth/token/', { username: username.value, password: password.value })
    localStorage.setItem('access_token', data.access)
    localStorage.setItem('refresh_token', data.refresh)
    await loadMe(true)
    router.push(route.query.next || '/app/ask')
  } catch (e) {
    error.value = e.response?.status === 401 ? 'That username and password don’t match.' : errorText(e)
  } finally {
    busy.value = false
  }
}
</script>
