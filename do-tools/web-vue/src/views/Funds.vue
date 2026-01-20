<template>
  <div class="funds-container">
    <div class="funds-header">
      <div>
        <h1>基金宇宙</h1>
        <p class="subtitle">洞悉投资组合配置与情报</p>
      </div>
      <button @click="showAddDialog = true" class="add-btn">+ 添加标的</button>
    </div>

    <!-- 基金列表 -->
    <div v-if="loading" class="loading">加载中...</div>
    <div v-else-if="funds.length === 0" class="empty-state">
      <div class="empty-icon">📊</div>
      <p>还没有添加基金</p>
      <button @click="showAddDialog = true" class="add-btn-secondary">
        添加第一个基金
      </button>
    </div>
    <div v-else class="funds-list">
      <div v-for="fund in funds" :key="fund.id" class="fund-card">
        <div class="fund-header">
          <div class="fund-icon">基</div>
          <div class="fund-info">
            <h3>{{ fund.fundName }}</h3>
            <span class="fund-code">{{ fund.fundCode }}</span>
          </div>
          <button @click="deleteFund(fund.id)" class="delete-btn">⋮</button>
        </div>

        <div class="fund-meta">
          <div class="meta-item">
            <span class="label">类型</span>
            <span class="value">{{ fund.fundType || '未分类' }}</span>
          </div>
          <div class="meta-item">
            <span class="label">自动调度</span>
            <span
              :class="['status', fund.scheduleEnabled ? 'active' : 'inactive']">
              {{
                fund.scheduleEnabled
                  ? `每日 ${fund.scheduleTime || '09:15'}`
                  : '未启用'
              }}
            </span>
          </div>
        </div>
      </div>
    </div>

    <!-- 添加基金弹窗 -->
    <div v-if="showAddDialog" class="modal-mask" @click.self="closeAddDialog">
      <div class="modal-content">
        <h2>添加新标的</h2>

        <!-- 市场搜索 -->
        <div class="search-section">
          <h3>市场搜索</h3>
          <div class="search-box">
            <input
              v-model="searchKeyword"
              @input="handleSearch"
              placeholder="搜索基金代码或名称"
              class="search-input" />
            <span class="search-icon">🔍</span>
          </div>

          <!-- 搜索结果 -->
          <div v-if="searching" class="search-loading">搜索中...</div>
          <div v-else-if="searchResults.length > 0" class="search-results">
            <div
              v-for="result in searchResults"
              :key="result.code"
              @click="selectFund(result)"
              class="search-result-item">
              <div class="result-name">{{ result.name }}</div>
              <div class="result-meta">
                <span class="result-code">{{ result.code }}</span>
                <span class="result-type">{{ result.type }}</span>
              </div>
            </div>
          </div>
        </div>

        <!-- 资产身份 -->
        <div class="identity-section">
          <h3>资产身份</h3>
          <div class="identity-fields">
            <input
              v-model="newFund.fundCode"
              placeholder="基金代码"
              class="identity-input"
              readonly />
            <input
              v-model="newFund.fundName"
              placeholder="基金名称"
              class="identity-input"
              readonly />
          </div>
        </div>

        <!-- 策略配置 -->
        <div class="strategy-section">
          <h3>策略配置</h3>
          <div class="readonly-field">
            <label>投资风格</label>
            <div class="readonly-value">
              {{ newFund.style || '自动获取中...' }}
            </div>
          </div>
          <div class="form-field">
            <label>关注板块</label>
            <input
              v-model="focusBoardsInput"
              placeholder="例如: 半导体, 新能源, 医药"
              class="strategy-input" />
            <p class="field-hint">用逗号分隔多个板块</p>
          </div>
        </div>

        <!-- 情报调度 -->
        <div class="schedule-section">
          <h3>情报调度</h3>
          <select v-model="newFund.scheduleInterval" class="schedule-select">
            <option value="24H">🕐 情报调度（24H）</option>
            <option value="12H">🕐 情报调度（12H）</option>
            <option value="6H">🕐 情报调度（6H）</option>
          </select>
        </div>

        <!-- 操作按钮 -->
        <div class="modal-actions">
          <button @click="closeAddDialog" class="cancel-btn">取消</button>
          <button @click="confirmAdd" :disabled="!canAdd" class="confirm-btn">
            确认配置
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import axios from 'axios'

const funds = ref([])
const loading = ref(true)
const showAddDialog = ref(false)
const searchKeyword = ref('')
const searching = ref(false)
const searchResults = ref([])
const focusBoardsInput = ref('')

const newFund = ref({
  fundCode: '',
  fundName: '',
  fundType: '',
  style: '',
  scheduleInterval: '24H',
})

let searchTimeout = null

onMounted(async () => {
  await loadFunds()
})

const loadFunds = async () => {
  try {
    const token = localStorage.getItem('token')
    const response = await axios.get('/api/funds', {
      headers: { Authorization: `Bearer ${token}` },
    })
    funds.value = response.data.funds
  } catch (err) {
    console.error('Load funds error:', err)
  } finally {
    loading.value = false
  }
}

const handleSearch = () => {
  if (searchTimeout) clearTimeout(searchTimeout)

  if (!searchKeyword.value.trim()) {
    searchResults.value = []
    return
  }

  searchTimeout = setTimeout(async () => {
    searching.value = true
    try {
      const token = localStorage.getItem('token')
      const response = await axios.get('/api/funds/search', {
        params: { keyword: searchKeyword.value },
        headers: { Authorization: `Bearer ${token}` },
      })
      searchResults.value = response.data.results || []
    } catch (err) {
      console.error('Search error:', err)
      searchResults.value = []
    } finally {
      searching.value = false
    }
  }, 300)
}

const selectFund = async (fund) => {
  newFund.value.fundCode = fund.code
  newFund.value.fundName = fund.name
  newFund.value.fundType = fund.type

  // 自动获取基金风格（从基金类型推断或调用详情接口）
  // 简单映射：根据基金类型推断风格
  const styleMap = {
    股票型: '成长型',
    混合型: '平衡型',
    指数型: '被动型',
    债券型: '稳健型',
    QDII: '全球型',
  }

  newFund.value.style = styleMap[fund.type] || '混合型'

  searchResults.value = []
  searchKeyword.value = ''
}

const canAdd = computed(() => {
  return newFund.value.fundCode && newFund.value.fundName
})

const confirmAdd = async () => {
  if (!canAdd.value) return

  try {
    const token = localStorage.getItem('token')
    const focusBoards = focusBoardsInput.value
      .split(',')
      .map((b) => b.trim())
      .filter((b) => b)

    await axios.post(
      '/api/funds',
      {
        ...newFund.value,
        focusBoards,
        scheduleEnabled: true,
        scheduleTime: '09:15',
      },
      {
        headers: { Authorization: `Bearer ${token}` },
      },
    )

    await loadFunds()
    closeAddDialog()
  } catch (err) {
    console.error('Add fund error:', err)
    alert('添加失败: ' + (err.response?.data?.error || err.message))
  }
}

const deleteFund = async (id) => {
  if (!confirm('确定要删除这个基金吗？')) return

  try {
    const token = localStorage.getItem('token')
    await axios.delete(`/api/funds/${id}`, {
      headers: { Authorization: `Bearer ${token}` },
    })
    await loadFunds()
  } catch (err) {
    console.error('Delete fund error:', err)
    alert('删除失败')
  }
}

const closeAddDialog = () => {
  showAddDialog.value = false
  newFund.value = {
    fundCode: '',
    fundName: '',
    fundType: '',
    style: '',
    scheduleInterval: '24H',
  }
  focusBoardsInput.value = ''
  searchKeyword.value = ''
  searchResults.value = []
}
</script>

<style scoped>
.funds-container {
  max-width: 1200px;
  margin: 0 auto;
}

.funds-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 32px;
}

.funds-header h1 {
  font-size: 32px;
  font-weight: 700;
  color: #333;
  margin-bottom: 4px;
}

.subtitle {
  color: #666;
  font-size: 14px;
}

.add-btn {
  padding: 12px 24px;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
  border: none;
  border-radius: 12px;
  font-size: 15px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.3s;
  box-shadow: 0 4px 15px rgba(102, 126, 234, 0.4);
}

.add-btn:hover {
  transform: translateY(-2px);
  box-shadow: 0 8px 25px rgba(102, 126, 234, 0.5);
}

.loading {
  text-align: center;
  padding: 48px;
  color: #999;
}

.empty-state {
  text-align: center;
  padding: 64px 24px;
}

.empty-icon {
  font-size: 64px;
  margin-bottom: 16px;
}

.empty-state p {
  color: #999;
  margin-bottom: 24px;
}

.add-btn-secondary {
  padding: 10px 20px;
  background: white;
  color: #667eea;
  border: 2px solid #667eea;
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.3s;
}

.add-btn-secondary:hover {
  background: #667eea;
  color: white;
}

.funds-list {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
  gap: 24px;
}

.fund-card {
  background: white;
  border-radius: 16px;
  padding: 20px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
  transition: all 0.3s;
}

.fund-card:hover {
  transform: translateY(-4px);
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.12);
}

.fund-header {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 16px;
}

.fund-icon {
  width: 48px;
  height: 48px;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: 600;
  font-size: 18px;
  flex-shrink: 0;
}

.fund-info {
  flex: 1;
  min-width: 0;
}

.fund-info h3 {
  font-size: 16px;
  font-weight: 600;
  color: #333;
  margin-bottom: 4px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.fund-code {
  font-size: 13px;
  color: #999;
}

.delete-btn {
  background: none;
  border: none;
  color: #999;
  font-size: 20px;
  cursor: pointer;
  padding: 4px 8px;
  transition: color 0.3s;
}

.delete-btn:hover {
  color: #dc3545;
}

.fund-meta {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.meta-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.meta-item .label {
  font-size: 13px;
  color: #666;
}

.meta-item .value {
  font-size: 14px;
  color: #333;
  font-weight: 500;
}

.status {
  padding: 4px 12px;
  border-radius: 12px;
  font-size: 12px;
  font-weight: 600;
}

.status.active {
  background: #d4edda;
  color: #155724;
}

.status.inactive {
  background: #f8f9fa;
  color: #999;
}

/* 弹窗样式 */
.modal-mask {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
  animation: fadeIn 0.3s;
}

.modal-content {
  background: white;
  border-radius: 16px;
  padding: 32px;
  max-width: 600px;
  width: 90%;
  max-height: 90vh;
  overflow-y: auto;
  animation: slideUp 0.3s;
}

.modal-content h2 {
  font-size: 24px;
  font-weight: 700;
  color: #333;
  margin-bottom: 24px;
}

.modal-content h3 {
  font-size: 16px;
  font-weight: 600;
  color: #333;
  margin-bottom: 12px;
}

.search-section,
.identity-section,
.strategy-section,
.schedule-section {
  margin-bottom: 24px;
}

.search-box {
  position: relative;
}

.search-input {
  width: 100%;
  padding: 12px 40px 12px 16px;
  border: 2px solid #e0e0e0;
  border-radius: 12px;
  font-size: 15px;
  transition: all 0.3s;
  box-sizing: border-box;
}

.search-input:focus {
  outline: none;
  border-color: #667eea;
}

.search-icon {
  position: absolute;
  right: 12px;
  top: 50%;
  transform: translateY(-50%);
  font-size: 18px;
}

.search-loading {
  padding: 12px;
  text-align: center;
  color: #999;
}

.search-results {
  margin-top: 8px;
  border: 1px solid #e0e0e0;
  border-radius: 8px;
  max-height: 200px;
  overflow-y: auto;
}

.search-result-item {
  padding: 12px;
  cursor: pointer;
  transition: background 0.2s;
  border-bottom: 1px solid #f0f0f0;
}

.search-result-item:last-child {
  border-bottom: none;
}

.search-result-item:hover {
  background: #f8f9fa;
}

.result-name {
  font-weight: 500;
  color: #333;
  margin-bottom: 4px;
}

.result-meta {
  display: flex;
  gap: 12px;
  font-size: 13px;
}

.result-code {
  color: #667eea;
}

.result-type {
  color: #999;
}

.identity-fields {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
}

.identity-input,
.strategy-input,
.schedule-select {
  width: 100%;
  padding: 12px 16px;
  border: 2px solid #e0e0e0;
  border-radius: 12px;
  font-size: 15px;
  transition: all 0.3s;
  box-sizing: border-box;
}

.identity-input:focus,
.strategy-input:focus,
.schedule-select:focus {
  outline: none;
  border-color: #667eea;
}

.strategy-input {
  margin-bottom: 12px;
}

.readonly-field {
  margin-bottom: 16px;
}

.readonly-field label {
  display: block;
  font-size: 13px;
  color: #666;
  margin-bottom: 8px;
  font-weight: 500;
}

.readonly-value {
  padding: 12px 16px;
  background: #f8f9fa;
  border: 2px solid #e0e0e0;
  border-radius: 12px;
  color: #333;
  font-size: 15px;
}

.form-field {
  margin-bottom: 16px;
}

.form-field label {
  display: block;
  font-size: 13px;
  color: #666;
  margin-bottom: 8px;
  font-weight: 500;
}

.field-hint {
  font-size: 12px;
  color: #999;
  margin-top: 6px;
  margin-bottom: 0;
}

.modal-actions {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
  margin-top: 32px;
}

.cancel-btn,
.confirm-btn {
  padding: 10px 24px;
  border-radius: 8px;
  font-size: 15px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.3s;
}

.cancel-btn {
  background: white;
  color: #666;
  border: 1px solid #e0e0e0;
}

.cancel-btn:hover {
  background: #f8f9fa;
}

.confirm-btn {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
  border: none;
}

.confirm-btn:hover:not(:disabled) {
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(102, 126, 234, 0.4);
}

.confirm-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

@keyframes fadeIn {
  from {
    opacity: 0;
  }
  to {
    opacity: 1;
  }
}

@keyframes slideUp {
  from {
    opacity: 0;
    transform: translateY(20px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}
</style>
