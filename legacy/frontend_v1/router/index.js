import { createRouter, createWebHistory } from 'vue-router'
import DashboardView from '../views/DashboardView.vue'  
import WorkspaceView from '../views/WorkspaceView.vue'
import LoginView from '../views/LoginView.vue'
import RegisterView from '../views/RegisterView.vue'
import LandingView from '../views/LandingView.vue' 

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    // PUBLIC ROUTES
    { path: '/', name: 'landing', component: LandingView }, // The new front door
    { path: '/login', name: 'login', component: LoginView },
    { path: '/register', name: 'register', component: RegisterView },

    // SECURE/APP ROUTES (Moved from / to /dashboard)
    { path: '/document/:id', name: 'DocumentDetail', component: () => import('../views/DocumentDetailView.vue'), meta: { requiresAuth: true}},
    { path: '/dashboard', name: 'dashboard', component: DashboardView, meta: { requiresAuth: true } },
    { path: '/workspace', name: 'workspace', component: WorkspaceView, meta: { requiresAuth: true } },
    { path: '/profile', name: 'profile', component: () => import('../views/ProfileView.vue'), meta: { requiresAuth: true } },
  ]
})

router.beforeEach((to, from, next) => {
  const loggedIn = localStorage.getItem('access_token')
  
  if (to.meta.requiresAuth && !loggedIn) {
    next('/login')
  } else {
    next()
  }
})

export default router