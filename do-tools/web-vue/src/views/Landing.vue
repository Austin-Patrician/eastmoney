<template>
  <div class="landing-container">
    <nav class="navbar">
      <div class="nav-content">
        <h1 class="logo">do-tools</h1>
        <button @click="goToLogin" class="login-btn">登录</button>
      </div>
    </nav>

    <main class="hero-section">
      <div class="hero-content">
        <h1 class="hero-title">do-tools</h1>
        <p class="hero-subtitle">金融数据分析工具</p>
        <p class="hero-description">强大的金融数据分析平台,助您洞察市场先机</p>
        <button @click="goToLogin" class="cta-button">立即开始 →</button>
      </div>
    </main>

    <section class="features-section">
      <div class="features-container">
        <h2 class="section-title">核心功能</h2>
        <div class="features-grid">
          <div class="feature-card">
            <div class="feature-icon">📊</div>
            <h3>数据分析</h3>
            <p>强大的金融数据分析功能,实时追踪市场动态</p>
          </div>
          <div class="feature-card">
            <div class="feature-icon">📈</div>
            <h3>实时监控</h3>
            <p>7x24小时实时监控,第一时间掌握市场变化</p>
          </div>
          <div class="feature-card">
            <div class="feature-icon">🤖</div>
            <h3>AI 分析</h3>
            <p>AI 驱动的智能分析,提供专业投资建议</p>
          </div>
        </div>
      </div>
    </section>

    <footer class="footer">
      <p>&copy; 2026 do-tools. All rights reserved.</p>
    </footer>
  </div>
</template>

<script setup>
import { useRouter } from 'vue-router'

const router = useRouter()

const goToLogin = () => {
  router.push('/login')
}
</script>

<style scoped>
.landing-container {
  min-height: 100vh;
  background: #f8f9fa;
}

.navbar {
  background: white;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
  position: sticky;
  top: 0;
  z-index: 100;
}

.nav-content {
  max-width: 1200px;
  margin: 0 auto;
  padding: 0 20px;
  height: 70px;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.logo {
  font-size: 28px;
  font-weight: 700;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  margin: 0;
}

.login-btn {
  padding: 10px 24px;
  background: transparent;
  border: 2px solid #667eea;
  color: #667eea;
  border-radius: 8px;
  font-size: 16px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.3s;
}

.login-btn:hover {
  background: #667eea;
  color: white;
  transform: translateY(-2px);
}

.hero-section {
  max-width: 1200px;
  margin: 0 auto;
  padding: 100px 20px;
  text-align: center;
}

.hero-content {
  max-width: 800px;
  margin: 0 auto;
}

.hero-title {
  font-size: 72px;
  font-weight: 800;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  margin-bottom: 20px;
  line-height: 1.2;
}

.hero-subtitle {
  font-size: 32px;
  color: #333;
  margin-bottom: 20px;
  font-weight: 600;
}

.hero-description {
  font-size: 20px;
  color: #666;
  margin-bottom: 40px;
  line-height: 1.6;
}

.cta-button {
  padding: 18px 48px;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
  border: none;
  border-radius: 12px;
  font-size: 20px;
  font-weight: 700;
  cursor: pointer;
  transition: all 0.3s;
  box-shadow: 0 8px 24px rgba(102, 126, 234, 0.4);
}

.cta-button:hover {
  transform: translateY(-3px);
  box-shadow: 0 12px 32px rgba(102, 126, 234, 0.5);
}

.features-section {
  background: white;
  padding: 80px 20px;
}

.features-container {
  max-width: 1200px;
  margin: 0 auto;
}

.section-title {
  text-align: center;
  font-size: 42px;
  font-weight: 700;
  color: #333;
  margin-bottom: 60px;
}

.features-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
  gap: 40px;
}

.feature-card {
  padding: 40px;
  background: #f8f9fa;
  border-radius: 16px;
  text-align: center;
  transition: all 0.3s;
}

.feature-card:hover {
  transform: translateY(-8px);
  box-shadow: 0 12px 32px rgba(0, 0, 0, 0.1);
}

.feature-icon {
  font-size: 64px;
  margin-bottom: 20px;
}

.feature-card h3 {
  font-size: 24px;
  color: #333;
  margin-bottom: 12px;
  font-weight: 700;
}

.feature-card p {
  font-size: 16px;
  color: #666;
  line-height: 1.6;
}

.footer {
  background: #2c3e50;
  color: white;
  text-align: center;
  padding: 30px 20px;
}

.footer p {
  margin: 0;
  font-size: 14px;
}
</style>
