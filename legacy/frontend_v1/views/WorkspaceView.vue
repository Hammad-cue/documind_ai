<template>
  <div class="flex h-screen w-full fixed top-0 left-0 bg-white z-50 overflow-hidden">
    
    <!-- PANEL 1: Collapsible Navy Sidebar -->
    <div 
      :class="['bg-gray-900 text-white flex flex-col flex-shrink-0 transition-all duration-300 ease-in-out relative z-20 shadow-xl overflow-hidden', isSidebarOpen ? 'w-[260px]' : 'w-0']"
    >
      <!-- CRITICAL FIX: Fixed-width inner container prevents text from squishing during animation -->
      <div class="w-[260px] h-full flex flex-col">
        
        <!-- Sidebar Header -->
        <div class="px-4 border-b border-gray-800 flex items-center justify-between h-14">
          <div class="flex items-center gap-3">
            <!-- Hamburger Toggle (Inside) -->
            <button @click="isSidebarOpen = false" class="text-gray-400 hover:text-white transition-colors p-1 rounded-md hover:bg-gray-800" title="Close Sidebar">
              <svg class="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 6h16M4 12h16M4 18h16" /></svg>
            </button>
            <span class="font-bold text-lg tracking-tight">DocuMind</span>
          </div>
          <button @click="startNewChat" class="text-gray-400 hover:text-white transition-colors p-1 rounded-md hover:bg-gray-800" title="New Chat">
            <svg class="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4" /></svg>
          </button>
        </div>
        
        <!-- Conversation List -->
        <div class="flex-1 overflow-y-auto p-3 space-y-1 dark-scrollbar">
          <div class="text-xs font-semibold text-gray-500 mb-3 px-2 mt-3 uppercase tracking-wider">Chat History</div>
          <div 
            v-for="conv in conversations" 
            :key="conv.id"
            class="group flex items-center justify-between px-3 py-2.5 rounded-lg text-sm cursor-pointer transition-all duration-200"
            :class="activeConversationId === conv.id ? 'bg-gray-800 text-white shadow-sm' : 'text-gray-400 hover:bg-gray-800/50 hover:text-gray-200'"
            @click="loadConversation(conv.id)"
          >
            <div class="truncate pr-2 flex items-center">
              <svg class="w-4 h-4 inline mr-2.5 opacity-70 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 10h.01M12 10h.01M16 10h.01M9 16H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-5l-5 5v-5z" /></svg>
              <span class="truncate font-medium">{{ conv.title || 'Analysis Session' }}</span>
            </div>
            <button @click.stop="deleteChat(conv.id)" class="text-gray-500 hover:text-red-400 opacity-0 group-hover:opacity-100 transition-opacity p-1 rounded hover:bg-gray-700">
              <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" /></svg>
            </button>
          </div>
        </div>

        <div class="p-4 border-t border-gray-800">
          <router-link to="/dashboard" class="flex items-center text-sm font-medium text-gray-400 hover:text-white transition-colors">
            <svg class="w-5 h-5 mr-3 opacity-70" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 001 1m-6 0h6" /></svg>
            Return to Vault
          </router-link>
        </div>
      </div>
    </div>

    <!-- Floating Re-Open Button -->
    <button 
      v-if="!isSidebarOpen"
      @click="isSidebarOpen = true" 
      class="absolute top-2.5 left-3 z-30 p-2 bg-white border border-gray-200 rounded-md shadow-sm text-gray-600 hover:text-gray-900 hover:bg-gray-50 transition-all"
    >
      <svg class="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 6h16M4 12h16M4 18h16" /></svg>
    </button>

      <!-- PANEL 2: Document Viewer (Left Half) -->
      <div class="w-[55%] border-r border-gray-200 bg-white flex flex-col">
        <!-- Unified Header -->
       <div class="bg-gray-50 border-b border-gray-200 flex items-end justify-between px-2 h-14" :class="!isSidebarOpen ? 'pl-14' : ''">
          <div class="flex overflow-x-auto h-full items-end light-scrollbar px-1">
            
            <div 
              v-for="doc in documents" 
              :key="doc.id"
              @click="activeTabId = doc.id"
              :class="['group flex items-center gap-2 px-5 py-2.5 text-sm font-semibold border-b-2 cursor-pointer whitespace-nowrap transition-colors max-w-[200px] rounded-t-lg', activeTabId === doc.id ? 'border-indigo-600 text-indigo-700 bg-white shadow-sm' : 'border-transparent text-gray-500 hover:text-gray-700 hover:bg-gray-100']"
            >
              <span class="truncate">{{ doc.title }}</span>
              
              <button 
                @click.stop="removeDocumentTab(doc.id)"
                class="p-0.5 rounded-md text-gray-400 hover:text-red-600 hover:bg-red-50 opacity-0 group-hover:opacity-100 transition-all flex-shrink-0"
                title="Remove from workspace"
              >
                <svg class="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" /></svg>
              </button>
            </div>

            <div v-if="documents.length === 0" class="px-4 py-2.5 text-sm text-gray-400">No context loaded</div>
          </div>
          
          <button @click="openVaultModal" class="mb-2 mr-2 flex items-center text-xs font-bold text-indigo-600 hover:text-indigo-800 bg-indigo-50 hover:bg-indigo-100 px-3 py-1.5 rounded-md transition-colors">
            <svg class="w-3.5 h-3.5 mr-1.5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4" /></svg>
            Add Doc
          </button>
        </div>
        
        <!-- Viewer Body Context Wrapper -->
        <div class="flex-1 bg-gray-100 overflow-hidden relative">
          
          <div v-for="doc in documents" :key="'viewer-'+doc.id" v-show="activeTabId === doc.id" class="absolute inset-0 p-3">
            <iframe v-if="doc.file_type === 'PDF'" :src="doc.file + '#toolbar=0&navpanes=0'" class="w-full h-full rounded-lg shadow-sm border border-gray-200 bg-white"></iframe>
            <img v-else-if="doc.file_type === 'IMAGE'" :src="doc.file" class="w-full h-full object-contain rounded-lg shadow-sm border border-gray-200 bg-white" />
            <div v-else-if="doc.file_type === 'DOCX'" class="w-full h-full bg-white rounded-lg shadow-sm border border-gray-200 overflow-y-auto p-10 light-scrollbar">
              <div v-if="docxHtml[doc.id]" class="prose max-w-none" v-html="docxHtml[doc.id]"></div>
              <div v-else class="flex items-center justify-center h-full text-gray-400">Loading Word Document...</div>
            </div>
          </div>

          <!-- Empty State View Overlay (Moved INSIDE the relative container) -->
          <div v-if="documents.length === 0" class="absolute inset-0 flex items-center justify-center text-gray-400 bg-gray-50 z-10">
            <div class="text-center">
              <svg class="mx-auto h-12 w-12 text-gray-300 mb-3" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M19.5 14.25v-2.625a3.375 3.375 0 00-3.375-3.375h-1.5A1.125 1.125 0 0113.5 7.125v-1.5a3.375 3.375 0 00-3.375-3.375H8.25m0 12.75h7.5m-7.5 3H12M10.5 2.25H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 00-9-9z" /></svg>
              <p>Click "Add Doc" to load files into this workspace.</p>
            </div>
          </div>
          
        </div>
      </div> 
  



      <!-- PANEL 3: AI Chat (Right Half) -->
      <div class="w-[45%] bg-white flex flex-col">
        <!-- Unified Header -->
        <div class="px-6 border-b border-gray-200 bg-white flex items-center justify-between h-14">
          <h2 class="text-sm font-bold text-gray-800 tracking-wide">AI Assistant</h2>
          <div class="flex space-x-1">
             <div class="w-2 h-2 rounded-full bg-green-500"></div>
          </div>
        </div>

        <div ref="chatContainer" class="flex-1 overflow-y-auto p-6 space-y-6 bg-gray-50/30 light-scrollbar">
          <div v-if="chatHistory.length === 0" class="flex flex-col items-center justify-center h-full text-center text-gray-400">
            <div class="bg-indigo-50 p-4 rounded-full mb-4">
              <svg class="w-8 h-8 text-indigo-500" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M8 10h.01M12 10h.01M16 10h.01M9 16H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-5l-5 5v-5z" /></svg>
            </div>
            <p class="text-sm">Ask a question to begin analyzing your documents.</p>
          </div>
          
          <div v-for="(msg, index) in chatHistory" :key="index" class="space-y-4">
            <div class="flex justify-end">
              <div class="bg-gray-800 text-white rounded-2xl rounded-tr-sm px-5 py-3 max-w-[85%] text-sm shadow-sm">{{ msg.user }}</div>
            </div>
            <div class="flex justify-start">
              <div class="bg-white border border-gray-200 text-gray-800 rounded-2xl rounded-tl-sm px-6 py-5 max-w-[95%] text-sm shadow-sm">
                <div class="prose prose-sm prose-indigo max-w-none" v-html="renderMarkdown(msg.ai)"></div>
              </div>
            </div>
          </div>
        </div>

        <div class="p-5 bg-white border-t border-gray-200">
          <form @submit.prevent="sendMessage" class="relative">
            <input 
              v-model="userQuery" 
              type="text" 
              placeholder="Ask DocuMind..." 
              class="w-full border border-gray-300 rounded-xl pl-5 pr-14 py-3.5 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 shadow-sm transition-shadow"
              :disabled="isLoading"
            />
            <button 
              type="submit" 
              :disabled="isLoading || !userQuery"
              class="absolute right-2 top-2 p-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 disabled:opacity-50 transition-colors shadow-sm"
            >
              <svg class="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M14 5l7 7m0 0l-7 7m7-7H3" /></svg>
            </button>
          </form>
        </div>
      </div>
    

    <!-- ADD DOCUMENT MODAL -->
    <div v-if="isModalOpen" class="fixed inset-0 bg-gray-900 bg-opacity-40 backdrop-blur-sm z-[100] flex items-center justify-center p-4 transition-opacity">
      <div class="bg-white rounded-2xl shadow-2xl max-w-lg w-full overflow-hidden border border-gray-100">
        <div class="p-5 border-b border-gray-100 flex justify-between items-center bg-white">
          <h3 class="font-bold text-gray-900 text-lg">Add Context</h3>
          <button @click="isModalOpen = false" class="text-gray-400 hover:text-gray-600 p-1 rounded-md hover:bg-gray-100 transition-colors">
            <svg class="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" /></svg>
          </button>
        </div>
        <div class="p-2 max-h-72 overflow-y-auto light-scrollbar bg-gray-50">
          <div v-if="vaultDocs.length === 0" class="text-center text-sm text-gray-500 py-8">Your vault is empty.</div>
          <div 
            v-for="doc in vaultDocs" :key="doc.id" 
            @click="toggleDocSelection(doc.id)"
            class="flex items-center p-3 m-2 hover:bg-white bg-transparent cursor-pointer rounded-lg border border-transparent hover:border-gray-200 hover:shadow-sm transition-all"
          >
            <input type="checkbox" :checked="selectedDocIds.includes(doc.id)" class="mr-4 h-4.5 w-4.5 text-indigo-600 rounded border-gray-300 focus:ring-indigo-600 pointer-events-none">
            <div class="flex flex-col">
              <span class="text-sm font-semibold text-gray-800">{{ doc.title }}</span>
              <span class="text-xs text-gray-500 mt-0.5">{{ doc.file_type }} • Uploaded {{ new Date(doc.uploaded_at).toLocaleDateString() }}</span>
            </div>
          </div>
        </div>
        <div class="p-4 border-t border-gray-100 bg-white flex justify-end">
          <button @click="confirmAddDocs" class="bg-gray-900 text-white px-5 py-2.5 rounded-lg text-sm font-bold shadow-sm hover:bg-gray-800 transition-colors">Apply Changes</button>
        </div>
      </div>
    </div>
  </div>

</template>

<script setup>
// *** KEEP YOUR EXACT SAME SCRIPT BLOCK HERE. DO NOT CHANGE THE LOGIC. ***
import { ref, onMounted, nextTick } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import axios from 'axios'
import { marked } from 'marked'
import DOMPurify from 'dompurify'
import * as mammoth from 'mammoth'

const route = useRoute()
const router = useRouter()

const isSidebarOpen = ref(true)
const isModalOpen = ref(false)

const documents = ref([])
const activeTabId = ref(null)
const selectedDocIds = ref([])
const docxHtml = ref({})
const vaultDocs = ref([]) 

const conversations = ref([])
const activeConversationId = ref(null)
const chatHistory = ref([])
const userQuery = ref('')
const isLoading = ref(false)
const chatContainer = ref(null)

const getHeaders = () => ({ headers: { Authorization: `Bearer ${localStorage.getItem('access_token')}` } })
const renderMarkdown = (text) => DOMPurify.sanitize(marked.parse(text || ''))

const renderDocx = async (doc) => {
  try {
    const response = await axios.get(doc.file, { responseType: 'arraybuffer' })
    const result = await mammoth.convertToHtml({ arrayBuffer: response.data })
    docxHtml.value[doc.id] = result.value
  } catch (error) {
    docxHtml.value[doc.id] = "<p class='text-red-500'>Failed to load preview.</p>"
  }
}

const removeDocumentTab = (idToRemove) => {
  // 1. Remove the document from the visual tabs
  documents.value = documents.value.filter(doc => doc.id !== idToRemove)
  
  // 2. CRITICAL FIX: Remove the ID from the selected arrays so the AI stops using it
  selectedDocIds.value = selectedDocIds.value.filter(id => id !== idToRemove)
  
  // 3. If they closed the active tab, switch to the first remaining one
  if (activeTabId.value === idToRemove) {
    activeTabId.value = documents.value.length > 0 ? documents.value[0].id : null
  }
}

const loadDocumentsIntoViewer = async () => {
  documents.value = []
  for (const id of selectedDocIds.value) {
    try {
      const response = await axios.get(`http://127.0.0.1:8000/api/upload/${id}/`, getHeaders())
      const doc = response.data
      documents.value.push(doc)
      if (doc.file_type === 'DOCX') renderDocx(doc)
    } catch (error) { console.error("Failed to load document", id) }
  }
  if (documents.value.length > 0) activeTabId.value = documents.value[0].id
  else activeTabId.value = null
}

const fetchConversations = async () => {
  try {
    const response = await axios.get('http://127.0.0.1:8000/api/conversations/', getHeaders())
    conversations.value = response.data
  } catch (error) { console.error("Failed to load conversations") }
}

const loadConversation = async (id) => {
  activeConversationId.value = id
  chatHistory.value = [] 
  try {
    const response = await axios.get(`http://127.0.0.1:8000/api/chat/?conversation_id=${id}`, getHeaders())
    chatHistory.value = response.data.messages
    selectedDocIds.value = response.data.document_ids || []
    await loadDocumentsIntoViewer()
    scrollToBottom()
  } catch (error) { console.error("Failed to load chat history") }
}

const startNewChat = () => {
  activeConversationId.value = null
  chatHistory.value = []
  documents.value = []
  selectedDocIds.value = []
  activeTabId.value = null
  router.replace({ path: '/workspace' }) 
}

const deleteChat = async (id) => {
  if (!confirm("Are you sure you want to delete this conversation?")) return
  try {
    await axios.delete(`http://127.0.0.1:8000/api/conversations/${id}/`, getHeaders())
    if (activeConversationId.value === id) startNewChat()
    await fetchConversations()
  } catch (error) { alert("Failed to delete chat.") }
}

const openVaultModal = async () => {
  try {
    const response = await axios.get('http://127.0.0.1:8000/api/upload/', getHeaders())
    vaultDocs.value = response.data
    isModalOpen.value = true
  } catch (error) { alert("Failed to open vault.") }
}

const toggleDocSelection = (id) => {
  const index = selectedDocIds.value.indexOf(id)
  if (index === -1) selectedDocIds.value.push(id)
  else selectedDocIds.value.splice(index, 1)
}

const confirmAddDocs = async () => {
  isModalOpen.value = false
  await loadDocumentsIntoViewer()
}

const sendMessage = async () => {
  if (!userQuery.value.trim()) return
  const query = userQuery.value
  userQuery.value = '' 
  isLoading.value = true

  chatHistory.value.push({ user: query, ai: 'Analyzing context...' })
  scrollToBottom()

  try {
    const payload = {
      user_query: query,
      document_ids: selectedDocIds.value,
      conversation_id: activeConversationId.value
    }
    const response = await axios.post('http://127.0.0.1:8000/api/chat/', payload, getHeaders())
    
    if (!activeConversationId.value) {
      activeConversationId.value = response.data.conversation_id
      await fetchConversations()
    }
    
    chatHistory.value[chatHistory.value.length - 1].ai = response.data.response_text
  } catch (error) {
    chatHistory.value[chatHistory.value.length - 1].ai = "Error connecting to AI."
  } finally {
    isLoading.value = false
    scrollToBottom()
  }
}

const scrollToBottom = async () => {
  await nextTick()
  if (chatContainer.value) chatContainer.value.scrollTop = chatContainer.value.scrollHeight
}

onMounted(async () => {
  await fetchConversations()
  const docsParam = route.query.docs
  if (docsParam) {
    selectedDocIds.value = docsParam.split(',').map(id => parseInt(id))
    await loadDocumentsIntoViewer()
  } 
  else if (conversations.value.length > 0) {
    await loadConversation(conversations.value[0].id)
  }
})
</script>

<style scoped>
/* Minimal Dark Scrollbar for the Navy Sidebar */
.dark-scrollbar::-webkit-scrollbar {
  width: 5px;
}
.dark-scrollbar::-webkit-scrollbar-track {
  background: transparent;
}
.dark-scrollbar::-webkit-scrollbar-thumb {
  background-color: #374151; /* Tailwind gray-700 */
  border-radius: 10px;
}
.dark-scrollbar::-webkit-scrollbar-thumb:hover {
  background-color: #4b5563; /* Tailwind gray-600 */
}

/* Minimal Light Scrollbar for Document/Chat Windows */
.light-scrollbar::-webkit-scrollbar {
  width: 6px;
  height: 6px; /* for horizontal scrolling on tabs */
}
.light-scrollbar::-webkit-scrollbar-track {
  background: transparent;
}
.light-scrollbar::-webkit-scrollbar-thumb {
  background-color: #cbd5e1; /* Tailwind slate-300 */
  border-radius: 10px;
}
.light-scrollbar::-webkit-scrollbar-thumb:hover {
  background-color: #94a3b8; /* Tailwind slate-400 */
}
</style>