<template>
  <Modal :open="true" :title="documentId ? 'Upload a new version' : 'Add a document'"
         :description="documentId ? 'The previous version is kept in the history.' : 'PDF, Word or a photo — printed, scanned or handwritten. Up to 25 MB.'"
         @close="emit('close')">
    <form class="space-y-4" @submit.prevent="submit">
      <label @dragover.prevent="drag = true" @dragleave="drag = false" @drop.prevent="drag = false; pick($event.dataTransfer.files[0])"
             :class="['flex cursor-pointer flex-col items-center justify-center rounded-[20px] border-2 border-dashed px-4 py-6 text-center transition',
                      drag ? 'border-accent bg-accent-soft' : 'border-black/10 bg-white/50 hover:border-accent/40 hover:bg-white/80']">
        <span class="flex h-12 w-12 items-center justify-center rounded-full bg-white shadow-[0_6px_16px_rgb(28_38_90/0.1)]"><Upload :size="20" class="text-accent" /></span>
        <span v-if="!file" class="mt-3 text-sm text-ink-2"><b class="text-accent">Choose a file</b> or drop it here</span>
        <span v-else class="mt-3 text-sm font-semibold text-ink">{{ file.name }} <span class="font-normal text-muted">· {{ fmtSize(file.size) }}</span></span>
        <input type="file" class="sr-only" accept=".pdf,.docx,.png,.jpg,.jpeg,.tif,.tiff,.webp" @change="pick($event.target.files[0])" />
      </label>

      <template v-if="!documentId">
        <div><label class="label" for="up-title">Title</label><input id="up-title" v-model="title" class="input" required placeholder="e.g. NDA with Acme Corp" /></div>
        <div class="grid gap-3 sm:grid-cols-2">
          <div>
            <label class="label" for="up-kind">Type</label>
            <select id="up-kind" v-model="kind" class="input">
              <option value="">Detect automatically</option>
              <option value="RECORD">Record — contract, NDA, deed</option>
              <option value="REFERENCE">Reference — law, policy, manual</option>
            </select>
          </div>
          <div>
            <label class="label" for="up-dept">Department</label>
            <select id="up-dept" v-model="department" class="input">
              <option :value="null">None</option>
              <option v-for="d in departments" :key="d.id" :value="d.id">{{ d.name }}</option>
            </select>
          </div>
        </div>
        <fieldset>
          <legend class="label">Who can see it</legend>
          <div class="grid gap-2 sm:grid-cols-3">
            <label v-for="a in ACCESS" :key="a.value" :class="['flex cursor-pointer flex-col gap-1 rounded-[14px] border p-3 text-sm transition',
                     access === a.value ? 'border-accent bg-accent-soft' : 'border-black/10 bg-white/60 hover:bg-white']">
              <input v-model="access" type="radio" :value="a.value" class="sr-only" />
              <component :is="a.icon" :size="16" :class="access === a.value ? 'text-accent' : 'text-muted'" aria-hidden="true" />
              <span class="font-semibold">{{ a.label }}</span>
            </label>
          </div>
        </fieldset>
        <div v-if="access === 'RESTRICTED'">
          <div class="label">People with access</div>
          <div class="max-h-40 space-y-0.5 overflow-y-auto rounded-[14px] border border-black/10 bg-white/60 p-2 scroll-thin">
            <label v-for="m in members" :key="m.id" class="flex min-h-10 items-center gap-2.5 rounded-lg px-2 text-sm hover:bg-white">
              <input type="checkbox" :value="m.id" v-model="allowed" class="h-4 w-4 accent-accent" /> {{ m.full_name }}
              <span class="ml-auto text-xs text-muted">{{ m.role.toLowerCase() }}</span>
            </label>
          </div>
        </div>
      </template>
      <div v-else><label class="label" for="up-note">What changed?</label><input id="up-note" v-model="changeNote" class="input" placeholder="e.g. Renewed for two more years" /></div>

      <label class="flex min-h-10 items-center gap-2.5 text-sm text-ink-2">
        <input type="checkbox" v-model="handwritten" class="h-4 w-4 accent-accent" /> It's handwritten — read it with the handwriting model
      </label>

      <p v-if="error" class="rounded-[14px] bg-bad-soft px-3.5 py-2.5 text-sm text-bad">{{ error }}</p>
      <!-- stays visible on short screens while the form scrolls -->
      <div class="sticky -bottom-6 -mx-6 -mb-6 flex justify-end gap-2 rounded-b-[26px] border-t border-line bg-white/90 px-6 py-4 backdrop-blur">
        <button type="button" class="btn-ghost" @click="emit('close')">Cancel</button>
        <button class="btn-primary" :disabled="!file || busy">{{ busy ? 'Uploading…' : 'Upload' }}</button>
      </div>
    </form>
  </Modal>
</template>

<script setup>
import { Building2, Globe, Lock, Upload } from '@lucide/vue'
import { onMounted, ref } from 'vue'
import api, { errorText } from '../api'
import { fmtSize } from '../format'
import { session } from '../session'
import Modal from './Modal.vue'

const props = defineProps({ documentId: { type: Number, default: null } })
const emit = defineEmits(['close', 'uploaded'])

const ACCESS = [
  { value: 'ORG', label: 'Everyone', icon: Globe },
  { value: 'DEPARTMENT', label: 'Department', icon: Building2 },
  { value: 'RESTRICTED', label: 'Chosen people', icon: Lock },
]
const file = ref(null)
const drag = ref(false)
const title = ref('')
const kind = ref('')
const department = ref(session.me?.department?.id ?? null)
const access = ref('ORG')
const allowed = ref([])
const handwritten = ref(false)
const changeNote = ref('')
const departments = ref([])
const members = ref([])
const error = ref('')
const busy = ref(false)

onMounted(async () => {
  if (props.documentId) return
  const [d, m] = await Promise.all([api.get('/org/departments/'), api.get('/org/members/')])
  departments.value = d.data
  members.value = m.data.filter(x => x.id !== session.me.id)
})

function pick(f) {
  if (!f) return
  file.value = f
  if (!title.value) title.value = f.name.replace(/\.[^.]+$/, '').replace(/[_-]+/g, ' ')
}

async function submit() {
  busy.value = true
  error.value = ''
  const fd = new FormData()
  fd.append('file', file.value)
  fd.append('marked_handwritten', handwritten.value ? '1' : '0')
  try {
    let data
    if (props.documentId) {
      fd.append('change_note', changeNote.value)
      ;({ data } = await api.post(`/documents/${props.documentId}/versions/`, fd))
    } else {
      fd.append('title', title.value)
      fd.append('access_level', access.value)
      fd.append('department', department.value ?? '')
      if (kind.value) fd.append('kind', kind.value)
      if (access.value === 'RESTRICTED') fd.append('allowed_user_ids', allowed.value.join(','))
      ;({ data } = await api.post('/documents/', fd))
    }
    emit('uploaded', data)
  } catch (e) {
    error.value = errorText(e)
  } finally {
    busy.value = false
  }
}
</script>
