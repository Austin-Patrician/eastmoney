<template>
  <div class="layout-container">
    <!-- 移动端遮罩 -->
    <div
      v-if="isMobileMenuOpen"
      class="mobile-overlay"
      @click="toggleMobileMenu"></div>

    <!-- 左侧菜单 - 占满高度 -->
    <aside :class="['sidebar', { 'mobile-open': isMobileMenuOpen }]">
      <div class="logo-area">
        <h1 class="logo">do-tools</h1>
        <button class="mobile-close-btn" @click="toggleMobileMenu">✕</button>
      </div>

      <!-- <nav class="menu"> -->
      <nav class="menu">
        <div v-for="item in menuItems" :key="item.path">
          <!-- 一级菜单 -->
          <div
            :class="[
              'menu-item',
              {
                active: !item.children && currentPath === item.path,
                'has-children': item.children,
                expanded: isExpanded(item.path),
              },
            ]"
            @click="handleMenuClick(item)">
            <span class="menu-icon">{{ item.icon }}</span>
            <span class="menu-title">{{ item.title }}</span>
            <span
              v-if="item.children"
              :class="['menu-arrow', { rotated: isExpanded(item.path) }]">
              ›
            </span>
          </div>

          <!-- 二级菜单 -->
          <div v-if="item.children && isExpanded(item.path)" class="submenu">
            <div
              v-for="child in item.children"
              :key="child.path"
              :class="[
                'menu-item',
                'sub-item',
                { active: currentPath === child.path },
              ]"
              @click="handleSubMenuClick(child.path)">
              <span class="menu-title">{{ child.title }}</span>
            </div>
          </div>
        </div>
      </nav>
    </aside>

    <!-- 右侧内容区 -->
    <div class="right-container">
      <!-- 顶部导航栏 - 只在右侧 -->
      <header class="top-navbar">
        <div class="navbar-content">
          <div class="navbar-left">
            <button class="mobile-menu-btn" @click="toggleMobileMenu">
              ☰
            </button>
            <h2 class="page-name">{{ currentPageName }}</h2>
          </div>
          <div class="navbar-right">
            <span class="user-name">{{ user?.username }}</span>
            <button @click="handleLogout" class="logout-btn">退出</button>
          </div>
        </div>
      </header>

      <!-- 主内容区 -->
      <main class="content-area">
        <router-view />
      </main>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, computed } from 'vue'
import { useRouter, useRoute } from 'vue-router'

const router = useRouter()
const route = useRoute()
const user = ref(null)
const isMobileMenuOpen = ref(false)
const expandedMenus = ref([])

const menuItems = [
  { path: '/home/dashboard', icon: '📊', title: '仪表盘' },
  { path: '/home/funds', icon: '💰', title: '基金管理' },
  { path: '/home/stocks', icon: '📈', title: '股票管理' },
  { path: '/home/reports', icon: '📄', title: '报告中心' },
  {
    path: '/home/settings',
    icon: '⚙️',
    title: '系统设置',
    children: [
      { path: '/home/settings/general', title: '通用设置' },
      { path: '/home/settings/ai-models', title: 'AI 模型' },
    ],
  },
]

const currentPath = computed(() => route.path)

const currentPageName = computed(() => {
  // 查找当前路径对应的页面名称
  for (const item of menuItems) {
    if (item.path === route.path) return item.title
    if (item.children) {
      const child = item.children.find((c) => c.path === route.path)
      if (child) return child.title
    }
  }
  return 'do-tools'
})

const isExpanded = (path) => expandedMenus.value.includes(path)

onMounted(() => {
  const userStr = localStorage.getItem('user')
  if (userStr) {
    user.value = JSON.parse(userStr)
  }

  // 默认跳转到仪表盘
  if (route.path === '/home') {
    router.push('/home/dashboard')
  }

  // 初始化展开状态
  menuItems.forEach((item) => {
    if (item.children) {
      // 如果当前路径包含父菜单路径，或者是父菜单的子菜单，则展开
      const isActive = item.children.some((child) => child.path === route.path)
      if (isActive) {
        if (!expandedMenus.value.includes(item.path)) {
          expandedMenus.value.push(item.path)
        }
      }
    }
  })
})

const toggleMobileMenu = () => {
  isMobileMenuOpen.value = !isMobileMenuOpen.value
}

const handleMenuClick = (item) => {
  if (item.children) {
    // 切换展开状态
    const index = expandedMenus.value.indexOf(item.path)
    if (index > -1) {
      expandedMenus.value.splice(index, 1)
    } else {
      expandedMenus.value.push(item.path)
    }
  } else {
    // 导航
    router.push(item.path)
    if (window.innerWidth <= 768) {
      isMobileMenuOpen.value = false
    }
  }
}

const handleSubMenuClick = (path) => {
  router.push(path)
  if (window.innerWidth <= 768) {
    isMobileMenuOpen.value = false
  }
}

const handleLogout = () => {
  localStorage.removeItem('token')
  localStorage.removeItem('user')
  router.push('/login')
}
</script>

<style scoped>
.layout-container {
  display: flex;
  height: 100vh;
  background: #f0f2f5;
  overflow: hidden;
}

/* 移动端遮罩 */
.mobile-overlay {
  display: none;
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.5);
  z-index: 99;
}

/* 左侧菜单 - 占满高度 */
.sidebar {
  width: 240px;
  background: white;
  display: flex;
  flex-direction: column;
  box-shadow: 2px 0 8px rgba(0, 0, 0, 0.08);
  z-index: 100;
  transition: transform 0.3s;
}

.logo-area {
  height: 64px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-bottom: 1px solid #f0f0f0;
  position: relative;
}

.logo {
  margin: 0;
  font-size: 24px;
  font-weight: 700;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
}

.mobile-close-btn {
  display: none;
  position: absolute;
  right: 16px;
  background: transparent;
  border: none;
  color: #333;
  font-size: 24px;
  cursor: pointer;
  padding: 4px 8px;
}

.menu {
  flex: 1;
  padding: 16px 0;
  overflow-y: auto;
}

.menu-item {
  display: flex;
  align-items: center;
  padding: 14px 24px;
  cursor: pointer;
  transition: all 0.3s;
  color: rgb(100, 116, 139);
  border-left: 3px solid transparent;
}

.menu-item:hover {
  background: #f8f9fa;
  color: #333;
}

.menu-item.active {
  background: #f0f5ff;
  color: #667eea;
  border-left-color: #667eea;
}

.menu-icon {
  font-size: 20px;
  margin-right: 12px;
}

.menu-title {
  font-size: 15px;
  font-weight: 500;
}

/* 菜单箭头 */
.menu-arrow {
  margin-left: auto;
  font-size: 18px;
  color: #999;
  transition: transform 0.3s ease;
  transform: rotate(0deg);
}

.menu-arrow.rotated {
  transform: rotate(90deg);
}

/* 二级菜单容器 */
.submenu {
  background: #f8f9fa;
  overflow: hidden;
  transition: all 0.3s ease-in-out;
}

/* 二级菜单项 */
.sub-item {
  padding-left: 56px !important; /* 增加左侧缩进 */
  font-size: 14px;
  height: 48px;
}

.sub-item:hover {
  background: #f0f0f0;
}

.sub-item.active {
  background: #e6f7ff;
  color: #1890ff;
  border-left: 3px solid #1890ff;
}

/* 右侧容器 */
.right-container {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

/* 顶部导航栏 - 只在右侧 */
.top-navbar {
  height: 64px;
  background: white;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
  z-index: 10;
}

.navbar-content {
  height: 100%;
  padding: 0 24px;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.navbar-left {
  flex: 1;
  display: flex;
  align-items: center;
  gap: 16px;
}

.mobile-menu-btn {
  display: none;
  background: transparent;
  border: none;
  font-size: 24px;
  cursor: pointer;
  padding: 4px 8px;
  color: #333;
}

.page-name {
  margin: 0;
  font-size: 20px;
  font-weight: 600;
  color: #333;
}

.navbar-right {
  display: flex;
  align-items: center;
  gap: 16px;
}

.user-name {
  color: #666;
  font-weight: 500;
  font-size: 14px;
}

.logout-btn {
  padding: 8px 16px;
  background: #f5f5f5;
  border: none;
  border-radius: 6px;
  color: #666;
  cursor: pointer;
  transition: all 0.3s;
  font-size: 14px;
}

.logout-btn:hover {
  background: #e8e8e8;
  color: #333;
}

/* 主内容区 */
.content-area {
  flex: 1;
  overflow-y: auto;
  padding: 24px;
  background: #f0f2f5;
}

/* 响应式设计 - 平板 */
@media (max-width: 1024px) {
  .sidebar {
    width: 200px;
  }

  .menu-item {
    padding: 12px 16px;
  }

  .content-area {
    padding: 16px;
  }
}

/* 响应式设计 - 手机 */
@media (max-width: 768px) {
  .mobile-overlay {
    display: block;
  }

  .sidebar {
    position: fixed;
    left: 0;
    top: 0;
    bottom: 0;
    transform: translateX(-100%);
    width: 280px;
  }

  .sidebar.mobile-open {
    transform: translateX(0);
  }

  .mobile-close-btn {
    display: block;
  }

  .mobile-menu-btn {
    display: block;
  }

  .page-name {
    font-size: 18px;
  }

  .navbar-content {
    padding: 0 16px;
  }

  .user-name {
    display: none;
  }

  .content-area {
    padding: 12px;
  }
}

/* 响应式设计 - 小屏手机 */
@media (max-width: 480px) {
  .page-name {
    font-size: 16px;
  }

  .logout-btn {
    padding: 6px 12px;
    font-size: 13px;
  }
}
</style>
