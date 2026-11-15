<template>
  <div class="min-h-[calc(100vh-4rem)] flex items-center justify-center py-12 px-4 sm:px-6 lg:px-8 bg-gray-50">
    <div class="max-w-md w-full space-y-8 bg-white p-10 rounded-2xl shadow-xl border border-gray-100">
      
      <div class="text-center">
        <div class="mx-auto w-12 h-12 bg-indigo-600 rounded-xl flex items-center justify-center shadow-lg shadow-indigo-600/30 mb-4">
          <svg class="w-7 h-7 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10" /></svg>
        </div>
        <h2 class="text-3xl font-extrabold text-gray-900 tracking-tight">Welcome back</h2>
        <p class="mt-2 text-sm text-gray-500">Sign in to access your secure vault.</p>
      </div>

      <form class="mt-8 space-y-6" @submit.prevent="handleLogin">
        <div class="space-y-4">
          <div>
            <label for="username" class="block text-sm font-semibold text-gray-700 mb-1">Username</label>
            <input id="username" v-model="username" type="text" required class="appearance-none relative block w-full px-4 py-3 border border-gray-300 placeholder-gray-400 text-gray-900 rounded-xl focus:outline-none focus:ring-2 focus:ring-indigo-600 focus:border-transparent sm:text-sm transition-all" placeholder="Enter your username" :disabled="isLoading" />
          </div>
          <div>
            <label for="password" class="block text-sm font-semibold text-gray-700 mb-1">Password</label>
            <input id="password" v-model="password" type="password" required class="appearance-none relative block w-full px-4 py-3 border border-gray-300 placeholder-gray-400 text-gray-900 rounded-xl focus:outline-none focus:ring-2 focus:ring-indigo-600 focus:border-transparent sm:text-sm transition-all" placeholder="••••••••" :disabled="isLoading" />
          </div>
        </div>

        <div v-if="errorMessage" class="bg-red-50 border-l-4 border-red-500 p-4 rounded-md">
          <p class="text-sm text-red-700 font-medium">{{ errorMessage }}</p>
        </div>

        <button type="submit" :disabled="isLoading" class="group relative w-full flex justify-center py-3.5 px-4 border border-transparent text-sm font-bold rounded-xl text-white bg-gray-900 hover:bg-black focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-gray-900 transition-all shadow-md disabled:opacity-70">
          <span v-if="isLoading">Authenticating...</span>
          <span v-else>Sign In</span>
        </button>
      </form>

      <div class="text-center mt-6">
        <p class="text-sm text-gray-600">
          Don't have an account? 
          <router-link to="/register" class="font-bold text-indigo-600 hover:text-indigo-500 transition-colors">Create one now</router-link>
        </p>
      </div>

    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import axios from 'axios'

const router = useRouter()
const username = ref('')
const password = ref('')
const errorMessage = ref('')
const isLoading = ref(false)

const handleLogin = async () => {
  isLoading.value = true
  errorMessage.value = ''
  try {
    const response = await axios.post('http://127.0.0.1:8000/api/token/', {
      username: username.value,
      password: password.value
    })
    localStorage.setItem('access_token', response.data.access)
    localStorage.setItem('refresh_token', response.data.refresh)
    
    // Force Vue to recognize the state change, then route
    window.dispatchEvent(new Event('storage'))
    router.push('/dashboard')
  } catch (error) {
    errorMessage.value = "Invalid credentials. Please try again."
  } finally {
    isLoading.value = false
  }
}
</script>