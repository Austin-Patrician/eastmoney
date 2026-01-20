<template>
  <div class="page-container">
    <h1 class="page-title">报告中心</h1>
    <p class="page-desc">查看和管理分析报告</p>
    <div class="empty-state">
      <div class="empty-icon">📄</div>
      <p>功能开发中...</p>
    </div>
  </div>
</template>

<style scoped>
.page-container {
  max-width: 1400px;
}

.page-title {
  font-size: 28px;
  font-weight: 700;
  color: #333;
  margin-bottom: 8px;
}

.page-desc {
  color: #666;
  margin-bottom: 24px;
}

.empty-state {
  background: white;
  padding: 80px;
  border-radius: 12px;
  text-align: center;
}

.empty-icon {
  font-size: 64px;
  margin-bottom: 16px;
}

.empty-state p {
  color: #999;
  font-size: 16px;
}
</style>
