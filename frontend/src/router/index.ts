import { createRouter, createWebHistory } from 'vue-router'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/',
      name: 'dashboard',
      component: () => import('@/views/DashboardView.vue'),
    },
    {
      path: '/products/new',
      name: 'product-create',
      component: () => import('@/views/ProductCreateView.vue'),
    },
    {
      path: '/products/:symbol/thesis',
      name: 'thesis',
      component: () => import('@/views/ThesisEditorView.vue'),
    },
    {
      path: '/products/:symbol/chat',
      name: 'chat',
      component: () => import('@/views/ChatView.vue'),
    },
    {
      path: '/runs/:runId',
      name: 'run-detail',
      component: () => import('@/views/RunDetailView.vue'),
    },
    {
      path: '/products/:symbol',
      name: 'product',
      component: () => import('@/views/ProductView.vue'),
    },
    {
      path: '/system',
      name: 'system',
      component: () => import('@/views/SystemView.vue'),
    },
    {
      path: '/settings',
      name: 'settings',
      component: () => import('@/views/SettingsView.vue'),
    },
    {
      path: '/:pathMatch(.*)*',
      redirect: '/',
    },
  ],
})

export default router