import { createRouter, createWebHistory } from 'vue-router'
import Landing from '../views/Landing.vue'
import Login from '../views/Login.vue'
import Home from '../views/Home.vue'
import Dashboard from '../views/dashboard/index.vue'

const routes = [
  {
    path: '/',
    name: 'Landing',
    component: Landing,
  },
  {
    path: '/login',
    name: 'Login',
    component: Login,
  },
  {
    path: '/home',
    name: 'Home',
    component: Home,
    meta: { requiresAuth: true },
    children: [
      {
        path: 'dashboard',
        name: 'Dashboard',
        component: Dashboard,
      },
      {
        path: 'funds',
        name: 'Funds',
        component: () => import('../views/funds/index.vue'),
      },
      {
        path: 'stocks',
        name: 'Stocks',
        component: () => import('../views/stocks/index.vue'),
      },
      {
        path: 'reports',
        name: 'Reports',
        component: () => import('../views/reports/index.vue'),
      },
      {
        path: 'settings',
        redirect: '/home/settings/general',
        children: [
          {
            path: 'general',
            name: 'SettingsGeneral',
            component: () => import('../views/settings/general.vue'),
          },
          {
            path: 'ai-models',
            name: 'SettingsAIModels',
            component: () => import('../views/settings/ai-models.vue'),
          },
        ],
      },
    ],
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

// 路由守卫 - 检查登录状态
router.beforeEach((to, from, next) => {
  const token = localStorage.getItem('token')

  if (to.meta.requiresAuth && !token) {
    // 需要登录但未登录,跳转到登录页
    next('/login')
  } else if (to.path === '/login' && token) {
    // 已登录访问登录页,跳转到 Home 页
    next('/home')
  } else if (to.path === '/' && token) {
    // 已登录访问根路径,跳转到 Home 页
    next('/home')
  } else {
    next()
  }
})

export default router
