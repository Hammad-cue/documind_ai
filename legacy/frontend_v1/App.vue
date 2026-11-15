<template>
  <div class="min-h-screen bg-gray-50 font-sans text-gray-900">
    
    <!-- Persistent Top Navigation (Hides completely on auth screens for Focus) -->
    <nav v-if="!['/login', '/register'].includes($route.path)" class="bg-gray-900 text-white border-b border-gray-800 relative z-40 shadow-md">
      <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div class="flex justify-between h-16">
          
          <!-- Left side: Logo & Main Links -->
          <div class="flex items-center">
            <div class="flex-shrink-0 flex items-center gap-2 cursor-pointer" @click="$router.push('/dashboard')">
              <div class="bg-indigo-500 p-1.5 rounded-lg">
                <svg class="w-6 h-6 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10" /></svg>
              </div>
              <span class="font-bold text-xl tracking-tight ml-2 text-white">DocuMind</span>
            </div>
            
          </div>

          <!-- Right side: Dynamic Auth State -->
          <div class="flex items-center gap-4 sm:gap-6">
            
            <!-- LOGGED IN VIEW -->
            <template v-if="isLoggedIn">
              <button @click="$router.push('/workspace')" class="hidden md:flex items-center gap-2 bg-indigo-600 hover:bg-indigo-500 text-white px-4 py-2 rounded-lg text-sm font-bold transition-all shadow-sm shadow-indigo-900/50">
                <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 10V3L4 14h7v7l9-11h-7z" /></svg>
                Launch Workspace
              </button>
              
              <button @click="logout" class="text-sm font-medium text-gray-400 hover:text-white transition-colors">
                Sign Out
              </button>
            </template>

            <!-- LOGGED OUT VIEW (Failsafe) -->
            <template v-else>
              <router-link to="/login" class="text-sm font-medium text-gray-300 hover:text-white transition-colors">
                Login
              </router-link>
              <router-link to="/register" class="bg-white text-gray-900 hover:bg-gray-100 px-4 py-2 rounded-lg text-sm font-bold transition-colors shadow-sm">
                Sign Up
              </router-link>
            </template>

          </div>

        </div>
      </div>
    </nav>

    <!-- The actual page content loads here -->
    <router-view />
    
  </div>
</template>

<script setup>
import { ref, watch } from 'vue'
import { useRouter, useRoute } from 'vue-router'

const router = useRouter()
const route = useRoute()
const isLoggedIn = ref(false)

// YOUR LOGIC RESTORED: Actively monitor route changes to ensure UI matches auth state
watch(
  () => route.path,
  () => {
    isLoggedIn.value = !!localStorage.getItem('access_token')
  },
  { immediate: true }
)

const logout = () => {
  localStorage.removeItem('access_token')
  localStorage.removeItem('refresh_token')
  isLoggedIn.value = false
  router.push('/')
}
</script>