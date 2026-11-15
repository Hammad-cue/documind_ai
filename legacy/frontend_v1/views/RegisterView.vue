<template>
  <div class="min-h-[calc(100vh-4rem)] flex items-center justify-center py-12 px-4 sm:px-6 lg:px-8 bg-gray-50">
    <div class="max-w-md w-full space-y-8 bg-white p-10 rounded-2xl shadow-xl border border-gray-100">
      
      <div class="text-center">
        <h2 class="text-3xl font-extrabold text-gray-900 tracking-tight">Create an account</h2>
        <p class="mt-2 text-sm text-gray-500">Join DocuMind to start analyzing your documents.</p>
      </div>

      <form class="mt-8 space-y-6" @submit.prevent="handleRegister">
        <div class="space-y-4">
          <div>
            <label for="username" class="block text-sm font-semibold text-gray-700 mb-1">Username</label>
            <input id="username" v-model="username" type="text" required class="appearance-none relative block w-full px-4 py-3 border border-gray-300 placeholder-gray-400 text-gray-900 rounded-xl focus:outline-none focus:ring-2 focus:ring-indigo-600 focus:border-transparent sm:text-sm transition-all" placeholder="Choose a username" :disabled="isLoading" />
          </div>
          <div>
            <label for="password" class="block text-sm font-semibold text-gray-700 mb-1">Password</label>
            <input id="password" v-model="password" type="password" required class="appearance-none relative block w-full px-4 py-3 border border-gray-300 placeholder-gray-400 text-gray-900 rounded-xl focus:outline-none focus:ring-2 focus:ring-indigo-600 focus:border-transparent sm:text-sm transition-all" placeholder="Create a strong password" :disabled="isLoading" />
          </div>
        </div>

        <div v-if="errorMessage" class="bg-red-50 border-l-4 border-red-500 p-4 rounded-md">
          <p class="text-sm text-red-700 font-medium">{{ errorMessage }}</p>
        </div>

        <button type="submit" :disabled="isLoading" class="group relative w-full flex justify-center py-3.5 px-4 border border-transparent text-sm font-bold rounded-xl text-white bg-indigo-600 hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-600 transition-all shadow-md disabled:opacity-70">
          <span v-if="isLoading">Creating account...</span>
          <span v-else>Sign Up</span>
        </button>
      </form>

      <div class="text-center mt-6">
        <p class="text-sm text-gray-600">
          Already have an account? 
          <router-link to="/login" class="font-bold text-gray-900 hover:text-indigo-600 transition-colors">Sign in here</router-link>
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

const handleRegister = async () => {
  isLoading.value = true
  errorMessage.value = ''
  try {
    // 1. Send ONLY username and password
    await axios.post('http://127.0.0.1:8000/api/register/', {
      username: username.value,
      password: password.value
    })
    
    // 2. Auto-login with the exact same credentials
    const loginResponse = await axios.post('http://127.0.0.1:8000/api/token/', {
      username: username.value,
      password: password.value
    })
    
    localStorage.setItem('access_token', loginResponse.data.access)
    localStorage.setItem('refresh_token', loginResponse.data.refresh)
    window.dispatchEvent(new Event('storage'))
    
    router.push('/dashboard')
  } catch (error) {
    if (error.response && error.response.data) {
      const errors = Object.values(error.response.data).flat()
      errorMessage.value = errors[0] || "Registration failed. Username may be taken."
    } else {
      errorMessage.value = "Registration failed. Please check your backend connection."
    }
  } finally {
    isLoading.value = false
  }
}
</script>