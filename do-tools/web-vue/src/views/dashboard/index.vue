<template>
  <div class="dashboard-container">
    <h1 class="page-title">仪表盘</h1>

    <!-- 统计卡片 -->
    <div class="stats-grid">
      <div class="stat-card">
        <div class="stat-icon">💰</div>
        <div class="stat-info">
          <div class="stat-value">0</div>
          <div class="stat-label">基金总数</div>
        </div>
      </div>

      <div class="stat-card">
        <div class="stat-icon">📈</div>
        <div class="stat-info">
          <div class="stat-value">0</div>
          <div class="stat-label">股票总数</div>
        </div>
      </div>

      <div class="stat-card">
        <div class="stat-icon">📄</div>
        <div class="stat-info">
          <div class="stat-value">0</div>
          <div class="stat-label">报告总数</div>
        </div>
      </div>

      <div class="stat-card">
        <div class="stat-icon">🤖</div>
        <div class="stat-info">
          <div class="stat-value">AI</div>
          <div class="stat-label">智能分析</div>
        </div>
      </div>
    </div>

    <!-- 欢迎卡片 -->
    <!-- <div class="welcome-card">
      <h2>🎉 欢迎使用 do-tools</h2>
      <p>金融数据分析工具 - 助您洞察市场先机</p>

      <div class="features-grid">
        <div class="feature-item">
          <span class="feature-icon">📊</span>
          <div>
            <h3>数据分析</h3>
            <p>强大的金融数据分析功能</p>
          </div>
        </div>

        <div class="feature-item">
          <span class="feature-icon">📈</span>
          <div>
            <h3>实时监控</h3>
            <p>实时监控市场动态</p>
          </div>
        </div>

        <div class="feature-item">
          <span class="feature-icon">🤖</span>
          <div>
            <h3>AI 分析</h3>
            <p>AI 驱动的智能分析</p>
          </div>
        </div>
      </div>
    </div> -->
  </div>
</template>

<script setup></script>

<style scoped>
.dashboard-container {
  max-width: 1400px;
}

.page-title {
  font-size: 28px;
  font-weight: 700;
  color: #333;
  margin-bottom: 24px;
}

/* 统计卡片 */
.stats-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
  gap: 20px;
  margin-bottom: 24px;
}

.stat-card {
  background: white;
  padding: 24px;
  border-radius: 12px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
  display: flex;
  align-items: center;
  gap: 16px;
  transition: all 0.3s;
}

.stat-card:hover {
  transform: translateY(-4px);
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.1);
}

.stat-icon {
  font-size: 48px;
}

.stat-info {
  flex: 1;
}

.stat-value {
  font-size: 32px;
  font-weight: 700;
  color: #333;
  margin-bottom: 4px;
}

.stat-label {
  font-size: 14px;
  color: #999;
}

/* 欢迎卡片 */
.welcome-card {
  background: white;
  padding: 40px;
  border-radius: 12px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
}

.welcome-card h2 {
  font-size: 28px;
  color: #333;
  margin-bottom: 12px;
}

.welcome-card > p {
  font-size: 16px;
  color: #666;
  margin-bottom: 32px;
}

.features-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
  gap: 24px;
}

.feature-item {
  display: flex;
  align-items: flex-start;
  gap: 16px;
  padding: 20px;
  background: #f8f9fa;
  border-radius: 8px;
  transition: all 0.3s;
}

.feature-item:hover {
  background: #f0f5ff;
}

.feature-icon {
  font-size: 36px;
}

.feature-item h3 {
  font-size: 18px;
  color: #333;
  margin-bottom: 6px;
}

.feature-item p {
  font-size: 14px;
  color: #666;
  margin: 0;
}
</style>
