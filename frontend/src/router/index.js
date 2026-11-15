import { createRouter, createWebHistory } from 'vue-router'
import { loadMe, session } from '../session'
import AppLayout from '../layouts/AppLayout.vue'

const routes = [
  { path: '/', name: 'landing', component: () => import('../views/LandingView.vue') },
  { path: '/login', name: 'login', component: () => import('../views/LoginView.vue') },
  { path: '/register', name: 'register', component: () => import('../views/RegisterView.vue') },
  {
    path: '/app',
    component: AppLayout,
    meta: { requiresAuth: true },
    children: [
      { path: '', redirect: '/app/ask' },
      { path: 'ask', name: 'ask', component: () => import('../views/AssistantView.vue') },
      { path: 'ask/:conversationId', name: 'conversation', component: () => import('../views/AssistantView.vue') },
      { path: 'documents', name: 'documents', component: () => import('../views/DocumentsView.vue') },
      { path: 'documents/:id', name: 'document', component: () => import('../views/DocumentDetailView.vue') },
      { path: 'records', name: 'records', component: () => import('../views/RecordsView.vue') },
      { path: 'review', name: 'review', component: () => import('../views/ReviewView.vue'), meta: { perm: 'verify' } },
      { path: 'team', name: 'team', component: () => import('../views/TeamView.vue'), meta: { perm: 'manage_team' } },
      { path: 'audit', name: 'audit', component: () => import('../views/AuditView.vue'), meta: { perm: 'view_audit' } },
      { path: 'profile', name: 'profile', component: () => import('../views/ProfileView.vue') },
    ],
  },
  { path: '/:pathMatch(.*)*', redirect: '/' },
]

const router = createRouter({ history: createWebHistory(import.meta.env.BASE_URL), routes })

router.beforeEach(async to => {
  const loggedIn = !!localStorage.getItem('access_token')
  if (to.matched.some(r => r.meta.requiresAuth)) {
    if (!loggedIn) return { name: 'login', query: { next: to.fullPath } }
    const me = await loadMe()
    if (!me) return { name: 'login' }
    if (to.meta.perm && !session.me.can[to.meta.perm]) return { name: 'ask' }
  }
  if ((to.name === 'login' || to.name === 'register') && loggedIn && (await loadMe())) return { name: 'ask' }
})

export default router
