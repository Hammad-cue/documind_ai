<template>
  <div class="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-10" v-if="doc">
    
    <button @click="$router.push('/dashboard')" class="text-sm font-medium text-gray-500 hover:text-indigo-600 mb-6 flex items-center transition-colors">
      <svg class="w-4 h-4 mr-1" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 19l-7-7m0 0l7-7m-7 7h18" /></svg>
      Back to Vault
    </button>

    <div class="bg-white rounded-2xl shadow-sm border border-gray-200 overflow-hidden">
      
      <!-- Updated Header Section -->
      <div class="p-8 border-b border-gray-100 flex flex-col sm:flex-row justify-between items-start gap-4">
        <div class="min-w-0 flex-1">
          <div class="flex items-center gap-3 mb-2 flex-wrap">
            <span class="inline-flex items-center rounded-full bg-indigo-50 px-3 py-1 text-xs font-bold text-indigo-700 border border-indigo-100">
              {{ doc.extracted_type || doc.file_type }}
            </span>
            <span class="text-xs font-medium text-gray-400">Uploaded {{ new Date(doc.uploaded_at).toLocaleDateString() }}</span>
          </div>
          <h1 class="text-2xl font-extrabold text-gray-900 break-words break-all">{{ doc.title }}</h1>
        </div>

        <div class="flex gap-3 flex-shrink-0">
          <button @click="openMergeModal" class="bg-white border border-gray-300 hover:bg-gray-50 text-gray-700 px-4 py-2.5 rounded-lg text-sm font-bold shadow-sm transition-all flex items-center gap-2 whitespace-nowrap">
            <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 7v8a2 2 0 002 2h6M8 7V5a2 2 0 012-2h4.586a1 1 0 01.707.293l4.414 4.414a1 1 0 01.293.707V15a2 2 0 01-2 2h-2M8 7H6a2 2 0 00-2 2v10a2 2 0 002 2h8a2 2 0 002-2v-2" /></svg>
            Merge Context
          </button>
          <button @click="startChat" class="bg-gray-900 hover:bg-black text-white px-6 py-2.5 rounded-lg text-sm font-bold shadow-md transition-all flex items-center gap-2 whitespace-nowrap">
            <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 10h.01M12 10h.01M16 10h.01M9 16H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-5l-5 5v-5z" /></svg>
            Chat
          </button>
        </div>
      </div>

      <div class="p-8 bg-gray-50/50">
        <h3 class="text-sm font-bold text-gray-900 uppercase tracking-wider mb-3">AI Summary</h3>
        <p class="text-gray-700 leading-relaxed mb-8 bg-white p-4 rounded-xl border border-gray-100 shadow-sm">
          {{ doc.extracted_summary || 'No summary available. Start a chat to generate insights.' }}
        </p>

        <!-- <h3 class="text-sm font-bold text-gray-900 uppercase tracking-wider mb-4">Extracted Timeline</h3>
        <div v-if="doc.extracted_dates && doc.extracted_dates.length > 0" class="bg-white rounded-xl border border-gray-100 shadow-sm overflow-hidden">
          <ul class="divide-y divide-gray-100">
            <li v-for="(dateObj, index) in doc.extracted_dates" :key="index" class="p-4 flex items-center">
              <div class="w-32 flex-shrink-0 text-sm font-bold text-indigo-600">{{ dateObj.date }}</div>
              <div class="text-sm text-gray-700">{{ dateObj.context }}</div>
            </li>
          </ul>
        </div>
        <div v-else class="text-sm text-gray-500 italic bg-white p-4 rounded-xl border border-gray-100 shadow-sm">
          No dates detected in this document.
        </div> -->
      </div>
    </div>

    <div v-if="isMergeModalOpen" class="fixed inset-0 bg-gray-900 bg-opacity-50 z-[100] flex items-center justify-center p-4">
      <div class="bg-white rounded-2xl shadow-2xl max-w-lg w-full overflow-hidden flex flex-col max-h-[80vh]">
        <div class="p-5 border-b border-gray-100 flex justify-between items-center bg-gray-50">
          <h3 class="font-bold text-gray-900 text-lg">Select Documents to Merge</h3>
          <button @click="isMergeModalOpen = false" class="text-gray-400 hover:text-gray-600 p-1 rounded-md hover:bg-gray-200 transition-colors">
            <svg class="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" /></svg>
          </button>
        </div>
        
        <div class="p-4 overflow-y-auto flex-1">
          <p class="text-sm text-gray-500 mb-4">Select additional documents to analyze alongside <span class="font-bold text-gray-800">{{ doc.title }}</span>.</p>
          <div v-if="availableDocs.length === 0" class="text-center text-sm text-gray-500 py-4">No other documents available in your vault.</div>
          
          <div v-for="vaultDoc in availableDocs" :key="vaultDoc.id" @click="toggleMergeSelection(vaultDoc.id)" class="flex items-center p-3 mb-2 hover:bg-indigo-50 cursor-pointer rounded-lg border border-transparent hover:border-indigo-100 transition-colors">
            <input type="checkbox" :checked="selectedMergeIds.includes(vaultDoc.id)" class="mr-4 h-4 w-4 text-indigo-600 rounded border-gray-300 pointer-events-none">
            <div class="flex flex-col">
              <span class="text-sm font-semibold text-gray-800">{{ vaultDoc.title }}</span>
              <span class="text-xs text-gray-500">{{ vaultDoc.extracted_type || vaultDoc.file_type }}</span>
            </div>
          </div>
        </div>

        <div class="p-5 border-t border-gray-100 bg-white flex justify-end">
          <button @click="startMergedChat" class="bg-indigo-600 hover:bg-indigo-700 text-white px-6 py-2.5 rounded-lg text-sm font-bold shadow-sm transition-colors flex items-center gap-2">
            Start Analysis with {{ selectedMergeIds.length + 1 }} Docs
          </button>
        </div>
      </div>
    </div>

  </div>
  
  <div v-else class="flex justify-center items-center h-screen">
    <div class="animate-pulse text-gray-400 font-medium">Loading document data...</div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import axios from 'axios'

const route = useRoute()
const router = useRouter()
const doc = ref(null)

// Merge Modal State
const isMergeModalOpen = ref(false)
const availableDocs = ref([])
const selectedMergeIds = ref([])

const getHeaders = () => ({ headers: { Authorization: `Bearer ${localStorage.getItem('access_token')}` } })

onMounted(async () => {
  try {
    const response = await axios.get(`http://127.0.0.1:8000/api/upload/${route.params.id}/`, getHeaders())
    doc.value = response.data
  } catch (error) {
    console.error("Failed to fetch document details")
    router.push('/dashboard')
  }
})

// Merge Logic
const openMergeModal = async () => {
  try {
    const response = await axios.get('http://127.0.0.1:8000/api/upload/', getHeaders())
    // Filter out the current document from the list
    availableDocs.value = response.data.filter(d => d.id !== doc.value.id)
    selectedMergeIds.value = [] // Reset selection
    isMergeModalOpen.value = true
  } catch (error) {
    alert("Failed to load vault documents.")
  }
}

const toggleMergeSelection = (id) => {
  const index = selectedMergeIds.value.indexOf(id)
  if (index === -1) selectedMergeIds.value.push(id)
  else selectedMergeIds.value.splice(index, 1)
}

const startChat = () => {
  router.push({ path: '/workspace', query: { docs: doc.value.id } })
}

const startMergedChat = () => {
  // Combine the current document ID with the selected merge IDs
  const allDocIds = [doc.value.id, ...selectedMergeIds.value]
  router.push({ path: '/workspace', query: { docs: allDocIds.join(',') } })
}
</script>