<template>
  <div class="flex h-[calc(100vh-4rem)] bg-gray-50 overflow-hidden">
    
    <div class="w-64 bg-white border-r border-gray-200 flex flex-col flex-shrink-0">
      <div class="p-6">
        <h2 class="text-xs font-bold text-gray-400 uppercase tracking-wider mb-4">Main Menu</h2>
        <nav class="space-y-1.5">
          <router-link to="/dashboard" class="flex items-center gap-3 px-3 py-2.5 text-gray-600 hover:bg-gray-50 hover:text-gray-900 rounded-lg font-medium transition-colors">
            <svg class="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10" /></svg>
            Document Vault
          </router-link>
          
          <router-link to="/workspace" class="flex items-center gap-3 px-3 py-2.5 text-gray-600 hover:bg-gray-50 hover:text-gray-900 rounded-lg font-medium transition-colors">
            <svg class="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 10V3L4 14h7v7l9-11h-7z" /></svg>
            AI Workspace
          </router-link>

          <router-link to="/profile" class="flex items-center gap-3 px-3 py-2.5 bg-indigo-50 text-indigo-700 rounded-lg font-semibold transition-colors mt-4">
             <svg class="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" /></svg>
            Profile Settings
          </router-link>
        </nav>
      </div>
    </div>

    <div class="flex-1 overflow-y-auto p-8 relative">
      <div class="max-w-3xl mx-auto space-y-6">
        
        <div class="mb-8">
          <h1 class="text-2xl font-bold text-gray-900">Profile Settings</h1>
          <p class="text-sm text-gray-500 mt-1">Manage your personal information and avatar.</p>
        </div>

        <div class="bg-white rounded-2xl shadow-sm border border-gray-200 overflow-hidden">
          <form @submit.prevent="saveProfile" class="p-8">
            
            <div class="flex items-center gap-6 mb-8 pb-8 border-b border-gray-100">
              <div class="relative group">
                <img :src="avatarPreview || profile.avatar || defaultAvatar" class="w-24 h-24 rounded-full object-cover border-4 border-gray-50 shadow-sm" alt="Avatar">
                <div @click="$refs.fileInput.click()" class="absolute inset-0 bg-black bg-opacity-40 rounded-full flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity cursor-pointer">
                  <svg class="w-6 h-6 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 9a2 2 0 012-2h.93a2 2 0 001.664-.89l.812-1.22A2 2 0 0110.07 4h3.86a2 2 0 011.664.89l.812 1.22A2 2 0 0018.07 7H19a2 2 0 012 2v9a2 2 0 01-2 2H5a2 2 0 01-2-2V9z" /><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 13a3 3 0 11-6 0 3 3 0 016 0z" /></svg>
                </div>
              </div>
              <div>
                <h3 class="text-sm font-bold text-gray-900">Profile Photo</h3>
                <p class="text-xs text-gray-500 mb-3">JPG, GIF or PNG. 1MB max.</p>
                <input type="file" ref="fileInput" accept="image/*" @change="handleFileChange" class="hidden" />
                <button type="button" @click="$refs.fileInput.click()" class="text-sm font-semibold text-indigo-600 bg-indigo-50 hover:bg-indigo-100 px-4 py-2 rounded-lg transition-colors">Change Photo</button>
              </div>
            </div>

            <div class="grid grid-cols-1 sm:grid-cols-2 gap-6 mb-6">
              <div>
                <label class="block text-sm font-semibold text-gray-700 mb-1">Username</label>
                <input type="text" v-model="profile.username" disabled class="block w-full px-4 py-2.5 bg-gray-100 border border-gray-200 text-gray-500 rounded-lg sm:text-sm cursor-not-allowed" />
              </div>
              <div>
                <label class="block text-sm font-semibold text-gray-700 mb-1">Email Address</label>
                <input type="email" v-model="profile.email" required class="block w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-600 focus:border-transparent sm:text-sm transition-all" />
              </div>
              <div>
                <label class="block text-sm font-semibold text-gray-700 mb-1">First Name</label>
                <input type="text" v-model="profile.first_name" class="block w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-600 focus:border-transparent sm:text-sm transition-all" />
              </div>
              <div>
                <label class="block text-sm font-semibold text-gray-700 mb-1">Last Name</label>
                <input type="text" v-model="profile.last_name" class="block w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-600 focus:border-transparent sm:text-sm transition-all" />
              </div>
              <div class="sm:col-span-2">
                <label class="block text-sm font-semibold text-gray-700 mb-1">Job Title</label>
                <input type="text" v-model="profile.job_title" placeholder="e.g. Senior Data Analyst" class="block w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-600 focus:border-transparent sm:text-sm transition-all" />
              </div>
            </div>

            <div class="flex items-center justify-end gap-3 pt-6 border-t border-gray-100">
              <span v-if="successMessage" class="text-sm font-medium text-green-600 mr-auto flex items-center gap-1">
                <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7" /></svg>
                {{ successMessage }}
              </span>
              <button type="submit" :disabled="isSaving" class="bg-indigo-600 hover:bg-indigo-700 text-white px-6 py-2.5 rounded-lg text-sm font-bold shadow-sm transition-all disabled:opacity-50">
                {{ isSaving ? 'Saving...' : 'Save Changes' }}
              </button>
            </div>

          </form>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import axios from 'axios'

const profile = ref({
  username: '',
  email: '',
  first_name: '',
  last_name: '',
  job_title: '',
  avatar: null
})

const defaultAvatar = 'https://ui-avatars.com/api/?name=User&background=EEF2FF&color=4F46E5'
const avatarPreview = ref(null)
const selectedFile = ref(null)
const isSaving = ref(false)
const successMessage = ref('')

const getHeaders = () => ({ headers: { Authorization: `Bearer ${localStorage.getItem('access_token')}` } })

// Load Profile Data
onMounted(async () => {
  try {
    const response = await axios.get('http://127.0.0.1:8000/api/profile/', getHeaders())
    profile.value = response.data
    
    // CRITICAL FIX: Only add the base URL if it's not already there!
    if (profile.value.avatar && !profile.value.avatar.startsWith('http')) {
      profile.value.avatar = `http://127.0.0.1:8000${profile.value.avatar}` 
    }
  } catch (error) {
    console.error("Failed to load profile", error)
  }
})

// Handle Avatar Image Selection
const handleFileChange = (event) => {
  const file = event.target.files[0]
  if (file) {
    selectedFile.value = file
    avatarPreview.value = URL.createObjectURL(file)
  }
}

// Save Changes
const saveProfile = async () => {
  isSaving.value = true
  successMessage.value = ''
  
  // We use FormData because we are sending a file alongside text
  const formData = new FormData()
  formData.append('email', profile.value.email)
  formData.append('first_name', profile.value.first_name)
  formData.append('last_name', profile.value.last_name)
  formData.append('job_title', profile.value.job_title || '')
  
  if (selectedFile.value) {
    formData.append('avatar', selectedFile.value)
  }

  try {
    const response = await axios.patch('http://127.0.0.1:8000/api/profile/', formData, {
      headers: {
        ...getHeaders().headers,
        'Content-Type': 'multipart/form-data'
      }
    })
    
    // Update local state with the new data
    profile.value = response.data
    if (profile.value.avatar && !profile.value.avatar.startsWith('http')) {
       profile.value.avatar = `http://127.0.0.1:8000${profile.value.avatar}`
    }
    selectedFile.value = null
    
    successMessage.value = "Profile updated successfully!"
    setTimeout(() => successMessage.value = '', 3000)
    
  } catch (error) {
    alert("Failed to update profile. Please try again.")
  } finally {
    isSaving.value = false
  }
}
</script>