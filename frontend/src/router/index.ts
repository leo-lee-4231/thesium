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
      path: '/products/:symbol',
      name: 'product',
      component: () => import('@/views/ProductView.vue'),
    },
    {
      path: '/:pathMatch(.*)*',
      redirect: '/',
    },
  ],
})

export default router