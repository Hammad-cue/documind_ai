<template>
  <div class="h-full overflow-y-auto scroll-thin">
    <div class="mx-auto max-w-[1180px] px-4 py-8 sm:px-6 lg:py-10">
      <PageHeader title="Team & access" subtitle="Roles decide what each person can do. Departments decide which documents they can see.">
        <button type="button" class="btn-primary" @click="showAdd = true"><UserPlus :size="17" aria-hidden="true" />Add a person</button>
      </PageHeader>

      <div class="mt-7 grid gap-5 2xl:grid-cols-[minmax(0,1fr)_320px]">
        <section class="panel overflow-hidden">
          <h2 class="border-b border-line px-6 py-4 text-[15px] font-semibold">People · {{ members.length }}</h2>
          <ul class="divide-y divide-line">
            <!-- The person block never shrinks below a readable width: when the row is too narrow, the controls
                 move to their own line instead of truncating the name. -->
            <li v-for="m in members" :key="m.id" class="flex flex-wrap items-center gap-x-4 gap-y-3 px-4 py-3.5 sm:px-6">
              <span class="flex min-w-[220px] flex-1 items-center gap-3">
                <img v-if="m.avatar" :src="m.avatar" alt="" class="h-10 w-10 shrink-0 rounded-full object-cover" />
                <span v-else aria-hidden="true" class="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-[#E4E8FB] text-[#2A3A9C] font-semibold">{{ initials(m) }}</span>
                <span class="min-w-0">
                  <span class="flex items-center gap-2">
                    <span class="truncate font-semibold" :class="!m.is_active && 'text-muted line-through'">{{ m.full_name }}</span>
                    <span v-if="isMe(m)" class="shrink-0 rounded-full bg-black/5 px-2 py-0.5 text-[11px] font-medium text-muted">You</span>
                    <span v-if="!m.is_active" class="shrink-0 rounded-full bg-bad-soft px-2 py-0.5 text-[11px] font-medium text-bad">Cannot sign in</span>
                  </span>
                  <span class="block truncate text-[13px] text-muted">@{{ m.username }}<span v-if="m.job_title"> · {{ m.job_title }}</span></span>
                </span>
              </span>
              <span class="ml-auto flex items-center gap-3">
                <label :for="`role-${m.id}`" class="sr-only">Role of {{ m.full_name }}</label>
                <select :id="`role-${m.id}`" :value="m.role" class="input w-[124px] min-h-10" @change="update(m, { role: $event.target.value })">
                  <option v-for="r in ROLES" :key="r.id" :value="r.id">{{ r.label }}</option>
                </select>
                <label :for="`dept-${m.id}`" class="sr-only">Department of {{ m.full_name }}</label>
                <select :id="`dept-${m.id}`" :value="m.department ?? ''" class="input w-[160px] min-h-10" @change="update(m, { department: $event.target.value ? +$event.target.value : null })">
                  <option value="">No department</option>
                  <option v-for="d in departments" :key="d.id" :value="d.id">{{ d.name }}</option>
                </select>
                <SwitchRoot :model-value="m.is_active" :disabled="isMe(m)" :aria-label="`${m.full_name} can sign in`"
                            :title="isMe(m) ? 'You cannot turn off your own access' : (m.is_active ? 'Can sign in — click to block' : 'Blocked — click to allow sign-in')"
                            class="relative h-6 w-11 shrink-0 rounded-full bg-black/15 transition data-[state=checked]:bg-ok disabled:cursor-not-allowed disabled:opacity-40"
                            @update:model-value="v => update(m, { is_active: v })">
                  <SwitchThumb class="block h-5 w-5 translate-x-0.5 rounded-full bg-white shadow transition data-[state=checked]:translate-x-[22px]" />
                </SwitchRoot>
              </span>
            </li>
          </ul>
          <p v-if="error" class="px-6 pb-4 text-sm text-bad">{{ error }}</p>
        </section>

        <div class="grid content-start gap-5 md:grid-cols-2 2xl:grid-cols-1">
          <section class="panel p-5">
            <h2 class="text-[15px] font-semibold">Departments</h2>
            <ul class="mt-3 space-y-1">
              <li v-for="d in departments" :key="d.id" class="group flex min-h-10 items-center justify-between rounded-[12px] px-3 hover:bg-white/60">
                <span class="text-sm">{{ d.name }} <span class="text-muted">· {{ d.member_count }}</span></span>
                <button type="button" :aria-label="`Delete ${d.name}`" class="flex h-9 w-9 items-center justify-center rounded-[10px] text-muted opacity-60 hover:bg-bad-soft hover:text-bad group-hover:opacity-100" @click="removeDept(d)"><Trash2 :size="15" /></button>
              </li>
            </ul>
            <form class="mt-3 flex gap-2" @submit.prevent="addDept">
              <label for="new-dept" class="sr-only">New department</label>
              <input id="new-dept" v-model="deptName" class="input" placeholder="New department" />
              <button class="btn-ghost w-11 shrink-0 px-0" aria-label="Add department" :disabled="!deptName"><Plus :size="17" /></button>
            </form>
          </section>
          <section class="panel p-5">
            <h2 class="text-[15px] font-semibold">What each role can do</h2>
            <dl class="mt-3 space-y-3 text-[13px]">
              <div v-for="r in ROLES" :key="r.id"><dt class="font-semibold">{{ r.label }}</dt><dd class="mt-0.5 text-muted">{{ r.desc }}</dd></div>
            </dl>
          </section>
        </div>
      </div>
    </div>

    <Modal :open="showAdd" title="Add a person" description="They can sign in with this username and temporary password." @close="showAdd = false">
      <form class="grid gap-3 sm:grid-cols-2" @submit.prevent="addMember">
        <div><label class="label" for="m-first">First name</label><input id="m-first" v-model="form.first_name" class="input" /></div>
        <div><label class="label" for="m-last">Last name</label><input id="m-last" v-model="form.last_name" class="input" /></div>
        <div><label class="label" for="m-user">Username</label><input id="m-user" v-model="form.username" class="input" required /></div>
        <div><label class="label" for="m-email">Email</label><input id="m-email" v-model="form.email" type="email" class="input" /></div>
        <div><label class="label" for="m-role">Role</label><select id="m-role" v-model="form.role" class="input"><option v-for="r in ROLES" :key="r.id" :value="r.id">{{ r.label }}</option></select></div>
        <div><label class="label" for="m-dept">Department</label><select id="m-dept" v-model="form.department" class="input"><option :value="null">None</option><option v-for="d in departments" :key="d.id" :value="d.id">{{ d.name }}</option></select></div>
        <div><label class="label" for="m-job">Job title</label><input id="m-job" v-model="form.job_title" class="input" /></div>
        <div><label class="label" for="m-pass">Temporary password</label><input id="m-pass" v-model="form.password" type="text" class="input" required autocomplete="off" /></div>
        <p v-if="addError" class="rounded-[14px] bg-bad-soft px-3.5 py-2.5 text-sm text-bad sm:col-span-2">{{ addError }}</p>
        <div class="flex justify-end gap-2 pt-1 sm:col-span-2"><button type="button" class="btn-ghost" @click="showAdd = false">Cancel</button><button class="btn-primary">Add person</button></div>
      </form>
    </Modal>
  </div>
</template>

<script setup>
import { Plus, Trash2, UserPlus } from '@lucide/vue'
import { SwitchRoot, SwitchThumb } from 'reka-ui'
import { onMounted, reactive, ref } from 'vue'
import api, { errorText } from '../api'
import Modal from '../components/Modal.vue'
import PageHeader from '../components/PageHeader.vue'
import { session } from '../session'
import { toast } from '../toast'

const ROLES = [
  { id: 'ADMIN', label: 'Admin', desc: 'Sees every document, manages people and departments, reads the activity log.' },
  { id: 'MANAGER', label: 'Manager', desc: 'Uploads documents and confirms or corrects extracted facts.' },
  { id: 'EMPLOYEE', label: 'Employee', desc: 'Uploads and asks about documents shared with everyone, their department, or them.' },
  { id: 'AUDITOR', label: 'Auditor', desc: 'Can read every document and the activity log, but cannot change anything.' },
]
const members = ref([])
const departments = ref([])
const showAdd = ref(false)
const form = reactive({ username: '', email: '', first_name: '', last_name: '', role: 'EMPLOYEE', department: null, job_title: '', password: '' })
const addError = ref('')
const error = ref('')
const deptName = ref('')

// session.me.id is a user id while member ids are membership ids, so compare usernames.
const isMe = m => m.username === session.me?.username
const initials = m => {
  const parts = (m.full_name || m.username || '?').trim().split(/\s+/)
  return ((parts[0]?.[0] || '') + (parts.length > 1 ? parts.at(-1)[0] : '')).toUpperCase() || '?'
}

async function load() {
  const [m, d] = await Promise.all([api.get('/org/members/'), api.get('/org/departments/')])
  members.value = m.data
  departments.value = d.data
}
async function addMember() {
  addError.value = ''
  try {
    await api.post('/org/members/', form)
    toast(`${form.first_name || form.username} added`, { detail: 'They can sign in with the temporary password.' })
    Object.assign(form, { username: '', email: '', first_name: '', last_name: '', password: '', job_title: '' })
    showAdd.value = false
    load()
  } catch (e) { addError.value = errorText(e) }
}
async function update(m, patch) {
  error.value = ''
  try { await api.patch(`/org/members/${m.id}/`, patch); toast(`${m.full_name} updated`) } catch (e) { error.value = errorText(e) }
  load()
}
async function addDept() { await api.post('/org/departments/', { name: deptName.value }); deptName.value = ''; load() }
async function removeDept(d) {
  if (!confirm(`Delete the ${d.name} department? Its people and documents will have no department.`)) return
  await api.delete(`/org/departments/${d.id}/`); load()
}
onMounted(load)
</script>
