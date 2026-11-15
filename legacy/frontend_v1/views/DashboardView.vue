<template>
  <div class="flex h-[calc(100vh-4rem)] bg-gray-50 overflow-hidden">
    
    <div class="w-64 bg-white border-r border-gray-200 flex flex-col flex-shrink-0">
      <div class="p-6">
        <h2 class="text-xs font-bold text-gray-400 uppercase tracking-wider mb-4">Main Menu</h2>
        <nav class="space-y-1.5">
          <router-link to="/dashboard" class="flex items-center gap-3 px-3 py-2.5 bg-indigo-50 text-indigo-700 rounded-lg font-semibold transition-colors">
            <svg class="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10" /></svg>
            Document Vault
          </router-link>
          
          <router-link to="/workspace" class="flex items-center gap-3 px-3 py-2.5 text-gray-600 hover:bg-gray-50 hover:text-gray-900 rounded-lg font-medium transition-colors">
            <svg class="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 10V3L4 14h7v7l9-11h-7z" /></svg>
            AI Workspace
          </router-link>

          <router-link to="/profile" class="flex items-center gap-3 px-3 py-2.5 text-gray-600 hover:bg-gray-50 hover:text-gray-900 rounded-lg font-medium transition-colors mt-4">
             <svg class="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" /></svg>
            Profile Settings
          </router-link>
        </nav>
      </div>
    </div>

    <div class="flex-1 overflow-y-auto p-8 relative">
      <div class="max-w-7xl mx-auto">
        
        <div class="flex justify-between items-center mb-8">
          <div>
            <h1 class="text-2xl font-bold text-gray-900">Document Vault</h1>
            <p class="text-sm text-gray-500 mt-1">Manage and analyze your files.</p>
          </div>
          <button @click="isUploadModalOpen = true" class="bg-indigo-600 hover:bg-indigo-700 text-white px-4 py-2.5 rounded-lg text-sm font-bold shadow-sm transition-colors flex items-center gap-2">
            <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4" /></svg>
            Upload Files
          </button>
        </div>

        <div class="mb-6 flex flex-col sm:flex-row justify-between items-center gap-4 bg-white p-4 rounded-xl shadow-sm border border-gray-200">
          <div class="relative w-full sm:w-96">
            <div class="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
              <svg class="h-5 w-5 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" /></svg>
            </div>
            <input v-model="searchQuery" type="text" placeholder="Search your vault..." class="block w-full pl-10 pr-3 py-2.5 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-600 sm:text-sm" />
          </div>
          <div class="flex items-center gap-3 w-full sm:w-auto">
            <span class="text-sm font-semibold text-gray-700">Filter:</span>
            <select v-model="filterType" class="block w-full sm:w-48 pl-3 pr-8 py-2.5 border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-600 sm:text-sm bg-gray-50 cursor-pointer">
              <option v-for="type in uniqueDocumentTypes" :key="type" :value="type">{{ type }}</option>
            </select>
          </div>
        </div>

        <div v-if="filteredDocuments.length === 0" class="text-center py-20 bg-white rounded-xl border border-gray-200 border-dashed">
          <svg class="mx-auto h-12 w-12 text-gray-300" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M19.5 14.25v-2.625a3.375 3.375 0 00-3.375-3.375h-1.5A1.125 1.125 0 0113.5 7.125v-1.5a3.375 3.375 0 00-3.375-3.375H8.25m0 12.75h7.5m-7.5 3H12M10.5 2.25H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 00-9-9z" /></svg>
          <h3 class="mt-2 text-sm font-semibold text-gray-900">No documents found</h3>
        </div>

        <div v-else class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6 pb-10">
          <div v-for="doc in paginatedDocuments" :key="doc.id" @click="$router.push(`/document/${doc.id}`)" class="bg-white rounded-xl border border-gray-200 shadow-sm hover:shadow-md hover:border-indigo-300 transition-all cursor-pointer flex flex-col h-56 relative group">
            <div class="p-4 border-b border-gray-100 flex items-start justify-between flex-shrink-0">
              <div class="flex items-center gap-2 overflow-hidden">
                <svg class="w-6 h-6 text-indigo-500 flex-shrink-0" fill="currentColor" viewBox="0 0 20 20"><path fill-rule="evenodd" d="M4 4a2 2 0 012-2h4.586A2 2 0 0112 2.586L15.414 6A2 2 0 0116 7.414V16a2 2 0 01-2 2H6a2 2 0 01-2-2V4z" clip-rule="evenodd" /></svg>
                <h3 class="text-sm font-bold text-gray-900 truncate" :title="doc.title">{{ doc.title }}</h3>
              </div>
              <button @click.stop="deleteDocument(doc.id)" class="opacity-0 group-hover:opacity-100 text-gray-400 hover:text-red-500 transition-opacity p-1">
                <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" /></svg>
              </button>
            </div>
            <div class="p-4 flex-1 overflow-hidden">
              <p class="text-xs text-gray-500 line-clamp-3 leading-relaxed">{{ doc.extracted_summary || 'No summary available.' }}</p>
            </div>
            <div class="p-4 bg-gray-50 rounded-b-xl flex justify-between items-center flex-shrink-0 border-t border-gray-100">
              <span class="inline-flex items-center rounded-full bg-indigo-100 px-2.5 py-0.5 text-[10px] font-semibold text-indigo-800">{{ doc.extracted_type || doc.file_type }}</span>
              <span class="text-[11px] font-medium text-gray-400">{{ new Date(doc.uploaded_at).toLocaleDateString() }}</span>
            </div>
          </div>
        </div>

        <div v-if="totalPages > 1" class="flex justify-center items-center gap-4 pb-10">
          <button @click="currentPage--" :disabled="currentPage === 1" class="px-4 py-2 border border-gray-300 rounded-lg text-sm font-medium text-gray-700 hover:bg-gray-50 disabled:opacity-50 transition-colors">Previous</button>
          <span class="text-sm text-gray-600">Page <span class="font-bold">{{ currentPage }}</span> of {{ totalPages }}</span>
          <button @click="currentPage++" :disabled="currentPage === totalPages" class="px-4 py-2 border border-gray-300 rounded-lg text-sm font-medium text-gray-700 hover:bg-gray-50 disabled:opacity-50 transition-colors">Next</button>
        </div>
      </div>
    </div>

    <div v-if="isUploadModalOpen" class="fixed inset-0 bg-gray-900 bg-opacity-50 z-[100] flex items-center justify-center p-4">
      <div class="bg-white rounded-2xl shadow-2xl max-w-2xl w-full overflow-hidden flex flex-col max-h-[90vh]">
        
        <div class="p-5 border-b border-gray-100 flex justify-between items-center bg-gray-50">
          <h3 class="font-bold text-gray-900 text-lg">Upload Documents</h3>
          <button @click="closeModal" class="text-gray-400 hover:text-gray-600 p-1 rounded-md hover:bg-gray-200 transition-colors">
            <svg class="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" /></svg>
          </button>
        </div>

        <div class="p-6 overflow-y-auto">
          <div 
            @dragover.prevent="isDragging = true" 
            @dragleave.prevent="isDragging = false" 
            @drop.prevent="handleDrop"
            :class="['border-2 border-dashed rounded-xl p-10 flex flex-col items-center justify-center transition-colors cursor-pointer', isDragging ? 'border-indigo-500 bg-indigo-50' : 'border-gray-300 hover:bg-gray-50']"
            @click="$refs.hiddenFileInput.click()"
          >
            <input type="file" ref="hiddenFileInput" multiple accept=".pdf,.docx,.png,.jpg,.jpeg" @change="handleFileSelect" class="hidden" />
            <svg class="w-12 h-12 text-gray-400 mb-3" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" /></svg>
            <p class="text-sm font-medium text-gray-900">Click or drag files to this area to upload</p>
            <p class="text-xs text-gray-500 mt-1">PDF, DOCX, PNG, JPG up to 10MB</p>
          </div>

          <div v-if="stagedFiles.length > 0" class="mt-6 space-y-4">
            <h4 class="text-sm font-bold text-gray-700 uppercase tracking-wider">Configure Files</h4>
            <div v-for="(file, index) in stagedFiles" :key="index" class="bg-gray-50 p-4 rounded-lg border border-gray-200 relative">
              <button @click="removeStagedFile(index)" class="absolute top-3 right-3 text-gray-400 hover:text-red-500"><svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" /></svg></button>
              
              <div class="grid grid-cols-1 sm:grid-cols-2 gap-4 mr-6">
                <div>
                  <label class="block text-xs font-semibold text-gray-600 mb-1">Document Name</label>
                  <input v-model="file.customTitle" type="text" class="w-full border border-gray-300 rounded-md px-3 py-2 text-sm focus:ring-indigo-500 focus:border-indigo-500" />
                </div>
                <div>
                  <label class="block text-xs font-semibold text-gray-600 mb-1">Custom Tag <span class="text-gray-400 font-normal">(Optional)</span></label>
                  <input v-model="file.customTag" type="text" placeholder="Leave blank for AI auto-tag" class="w-full border border-gray-300 rounded-md px-3 py-2 text-sm focus:ring-indigo-500 focus:border-indigo-500" />
                </div>
              </div>
            </div>
          </div>
        </div>

        <div class="p-5 border-t border-gray-100 bg-white flex justify-end gap-3">
          <button @click="closeModal" class="px-4 py-2 text-sm font-bold text-gray-600 hover:bg-gray-100 rounded-lg transition-colors">Cancel</button>
          <button 
            @click="uploadStagedFiles" 
            :disabled="stagedFiles.length === 0 || isUploading"
            class="bg-indigo-600 hover:bg-indigo-700 text-white px-6 py-2 rounded-lg text-sm font-bold shadow-sm transition-colors disabled:opacity-50 flex items-center gap-2"
          >
            <span v-if="isUploading">Uploading...</span>
            <span v-else>Confirm Upload</span>
          </button>
        </div>
      </div>
    </div>

  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted } from 'vue'
import axios from 'axios'
import { useRouter } from 'vue-router'

const router = useRouter()
const documents = ref([])
const searchQuery = ref('')
const filterType = ref('All')

// Modal & Staging State
const isUploadModalOpen = ref(false)
const isDragging = ref(false)
const isUploading = ref(false)
const stagedFiles = ref([])

const currentPage = ref(1)
const itemsPerPage = 12

const getHeaders = () => ({ headers: { Authorization: `Bearer ${localStorage.getItem('access_token')}` } })

const uniqueDocumentTypes = computed(() => {
  const types = new Set()
  documents.value.forEach(doc => {
    types.add(doc.extracted_type && doc.extracted_type !== 'Unknown' ? doc.extracted_type : doc.file_type)
  })
  return ['All', ...Array.from(types).sort()]
})

const filteredDocuments = computed(() => {
  return documents.value.filter(doc => {
    const searchLower = searchQuery.value.toLowerCase()
    const matchesSearch = doc.title.toLowerCase().includes(searchLower) || (doc.extracted_summary && doc.extracted_summary.toLowerCase().includes(searchLower))
    const docType = doc.extracted_type && doc.extracted_type !== 'Unknown' ? doc.extracted_type : doc.file_type
    const matchesType = filterType.value === 'All' || docType === filterType.value
    return matchesSearch && matchesType
  })
})

const totalPages = computed(() => Math.ceil(filteredDocuments.value.length / itemsPerPage) || 1)
const paginatedDocuments = computed(() => filteredDocuments.value.slice((currentPage.value - 1) * itemsPerPage, currentPage.value * itemsPerPage))

watch([searchQuery, filterType], () => { currentPage.value = 1 })

const fetchDocuments = async () => {
  try {
    const response = await axios.get('http://127.0.0.1:8000/api/upload/', getHeaders())
   documents.value = response.data.sort((a, b) => new Date(b.uploaded_at) - new Date(a.uploaded_at))
  } catch (error) { console.error("Failed to fetch documents") }
}

// Staging Logic
const addFilesToStage = (files) => {
  const allowedExtensions = ['pdf', 'docx', 'png', 'jpg', 'jpeg']
  for (let i = 0; i < files.length; i++) {
    const file = files[i]
    const ext = file.name.split('.').pop().toLowerCase()
    if (!allowedExtensions.includes(ext)) {
      alert(`Upload Blocked: ".${ext}" files are not supported.`)
      continue
    }
    stagedFiles.value.push({
      file: file,
      customTitle: file.name,
      customTag: ''
    })
  }
}

const handleFileSelect = (event) => {
  addFilesToStage(event.target.files)
  event.target.value = '' 
}

const handleDrop = (event) => {
  isDragging.value = false
  addFilesToStage(event.dataTransfer.files)
}

const removeStagedFile = (index) => { stagedFiles.value.splice(index, 1) }
const closeModal = () => {
  isUploadModalOpen.value = false
  stagedFiles.value = []
}

// Upload Logic
// Upload Logic
const uploadStagedFiles = async () => {
  if (stagedFiles.value.length === 0) return
  isUploading.value = true

  for (const item of stagedFiles.value) {
    const formData = new FormData()
    formData.append('file', item.file)
    formData.append('title', item.customTitle)
    if (item.customTag.trim() !== '') formData.append('custom_tag', item.customTag)

    // CRITICAL FIX: Figure out the file type and append it for Django!
    const ext = item.file.name.split('.').pop().toLowerCase()
    if (ext === 'pdf') formData.append('file_type', 'PDF')
    else if (ext === 'docx') formData.append('file_type', 'DOCX')
    else formData.append('file_type', 'IMAGE')

    try {
      await axios.post('http://127.0.0.1:8000/api/upload/', formData, getHeaders())
    } catch (error) { 
      alert(error.response?.data?.detail || `Upload failed for ${item.customTitle}`) 
    }
  }
  
  await fetchDocuments()
  isUploading.value = false
  closeModal()
}
const deleteDocument = async (id) => {
  if (confirm("Delete this document?")) {
    try {
      await axios.delete(`http://127.0.0.1:8000/api/upload/${id}/`, getHeaders())
      fetchDocuments()
    } catch (error) { alert("Failed to delete.") }
  }
}

onMounted(fetchDocuments)
</script>