<template>
  <div class="settings-container">
    <!-- 成功/错误提示 - 放在顶部 -->
    <div v-if="showSuccess" class="success-message">✅ 设置保存成功!</div>

    <div v-if="error" class="error-message">❌ {{ error }}</div>

    <h1 class="page-title">AI 模型配置</h1>

    <!-- AI 模型列表 -->
    <div class="models-grid">
      <!-- 添加新模型卡片 -->
      <div class="add-model-card" @click="addModel">
        <div class="add-icon">+</div>
        <p>添加 AI 模型</p>
      </div>

      <!-- 模型卡片 -->
      <div v-for="(model, index) in aiModels" :key="index" class="model-card">
        <div class="card-header">
          <h3>{{ model.name || '未命名模型' }}</h3>
          <div class="card-actions">
            <button
              v-if="editingIndex === index"
              @click="saveModel(index)"
              class="save-icon-btn"
              title="保存">
              ✓
            </button>
            <button
              v-if="editingIndex === index"
              @click="cancelEdit(index)"
              class="cancel-icon-btn"
              title="取消">
              ✕
            </button>
            <button
              v-else
              @click="editModel(index)"
              class="edit-icon-btn"
              title="编辑">
              ✎
            </button>
            <button
              v-if="model.id"
              @click="deleteModel(index)"
              class="delete-icon-btn"
              title="删除">
              🗑
            </button>
          </div>
        </div>

        <!-- 编辑模式 -->
        <div v-if="editingIndex === index" class="card-form">
          <div class="form-field">
            <label>模型名称</label>
            <input
              v-model="model.name"
              type="text"
              placeholder="例如: Gemini Pro" />
          </div>

          <div class="form-field">
            <label>API Key</label>
            <input
              v-model="model.apiKey"
              type="password"
              placeholder="输入 API Key" />
          </div>

          <div class="form-field">
            <label>Base URL</label>
            <input
              v-model="model.baseUrl"
              type="text"
              placeholder="https://api.openai.com/v1 (可选)" />
          </div>
        </div>

        <!-- 查看模式 -->
        <div v-else class="card-content">
          <div class="info-row">
            <span class="label">API Key:</span>
            <span class="value">{{ maskApiKey(model.apiKey) }}</span>
          </div>
          <div v-if="model.baseUrl" class="info-row">
            <span class="label">Base URL:</span>
            <span class="value">{{ model.baseUrl }}</span>
          </div>
        </div>
      </div>
    </div>

    <!-- Tavily API Key -->
    <div class="tavily-section">
      <h2>Tavily 搜索配置</h2>
      <div class="form-field">
        <label>Tavily API Key</label>
        <input
          v-model="tavilyApiKey"
          type="password"
          placeholder="输入 Tavily API Key" />
        <p class="hint">用于网络搜索和情绪分析功能</p>
      </div>
      <button @click="saveTavily" class="save-btn" :disabled="saving">
        {{ saving ? '保存中...' : '保存' }}
      </button>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import axios from 'axios'

const aiModels = ref([])
const editingIndex = ref(null)
const tavilyApiKey = ref('')
const saving = ref(false)
const showSuccess = ref(false)
const error = ref('')

onMounted(async () => {
  await loadSettings()
})

const loadSettings = async () => {
  try {
    const token = localStorage.getItem('token')
    const response = await axios.get('/api/settings', {
      headers: {
        Authorization: `Bearer ${token}`,
      },
    })

    aiModels.value = response.data.settings.aiModels || []
    tavilyApiKey.value = response.data.settings.tavilyApiKey || ''
  } catch (err) {
    console.error('Load settings error:', err)
    error.value = '加载设置失败'
  }
}

const addModel = () => {
  aiModels.value.push({
    name: '',
    apiKey: '',
    baseUrl: '',
  })
  editingIndex.value = aiModels.value.length - 1
}

const editModel = (index) => {
  editingIndex.value = index
}

const cancelEdit = (index) => {
  const model = aiModels.value[index]
  // 如果是新添加的空模型,取消时删除
  if (!model.id && !model.name && !model.apiKey) {
    aiModels.value.splice(index, 1)
  }
  editingIndex.value = null
}

const saveModel = async (index) => {
  saving.value = true
  error.value = ''
  showSuccess.value = false

  try {
    const token = localStorage.getItem('token')
    const response = await axios.put(
      '/api/settings',
      {
        aiModels: aiModels.value,
        tavilyApiKey: tavilyApiKey.value,
      },
      {
        headers: {
          Authorization: `Bearer ${token}`,
        },
      },
    )

    // 更新模型 ID
    aiModels.value = response.data.settings.aiModels
    editingIndex.value = null

    showSuccess.value = true
    setTimeout(() => {
      showSuccess.value = false
    }, 3000)

    window.scrollTo({ top: 0, behavior: 'smooth' })
  } catch (err) {
    console.error('Save model error:', err)
    error.value = err.response?.data?.message || '保存失败'
    window.scrollTo({ top: 0, behavior: 'smooth' })
  } finally {
    saving.value = false
  }
}

const deleteModel = async (index) => {
  if (!confirm('确定要删除这个模型配置吗?')) return

  aiModels.value.splice(index, 1)

  // 立即保存
  try {
    const token = localStorage.getItem('token')
    await axios.put(
      '/api/settings',
      {
        aiModels: aiModels.value,
        tavilyApiKey: tavilyApiKey.value,
      },
      {
        headers: {
          Authorization: `Bearer ${token}`,
        },
      },
    )

    showSuccess.value = true
    setTimeout(() => {
      showSuccess.value = false
    }, 3000)
  } catch (err) {
    error.value = '删除失败'
  }
}

const saveTavily = async () => {
  saving.value = true
  error.value = ''
  showSuccess.value = false

  try {
    const token = localStorage.getItem('token')
    await axios.put(
      '/api/settings',
      {
        aiModels: aiModels.value,
        tavilyApiKey: tavilyApiKey.value,
      },
      {
        headers: {
          Authorization: `Bearer ${token}`,
        },
      },
    )

    showSuccess.value = true
    setTimeout(() => {
      showSuccess.value = false
    }, 3000)

    window.scrollTo({ top: 0, behavior: 'smooth' })
  } catch (err) {
    console.error('Save Tavily error:', err)
    error.value = err.response?.data?.message || '保存失败'
    window.scrollTo({ top: 0, behavior: 'smooth' })
  } finally {
    saving.value = false
  }
}

const maskApiKey = (key) => {
  if (!key) return '未设置'
  if (key.length <= 8) return '••••••••'
  return key.substring(0, 4) + '••••••••' + key.substring(key.length - 4)
}
</script>

<style scoped>
.settings-container {
  max-width: 1200px;
}

/* 提示信息 - 固定悬浮 */
.success-message,
.error-message {
  position: fixed;
  top: 24px;
  left: 50%;
  transform: translateX(-50%);
  padding: 16px 32px;
  border-radius: 12px;
  font-weight: 600;
  animation: slideDown 0.3s;
  z-index: 1000;
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.15);
  min-width: 300px;
  text-align: center;
}

.success-message {
  background: linear-gradient(135deg, #d4edda 0%, #c3e6cb 100%);
  color: #155724;
  border: 2px solid #28a745;
}

.error-message {
  background: linear-gradient(135deg, #f8d7da 0%, #f5c6cb 100%);
  color: #721c24;
  border: 2px solid #dc3545;
}

.page-title {
  font-size: 32px;
  font-weight: 700;
  color: #333;
  margin-bottom: 32px;
}

/* 模型网格 */
.models-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
  gap: 24px;
  margin-bottom: 48px;
}

/* 添加模型卡片 */
.add-model-card {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  border-radius: 16px;
  padding: 48px 24px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: all 0.3s;
  min-height: 200px;
  box-shadow: 0 4px 20px rgba(102, 126, 234, 0.3);
}

.add-model-card:hover {
  transform: translateY(-8px);
  box-shadow: 0 8px 30px rgba(102, 126, 234, 0.4);
}

.add-icon {
  font-size: 64px;
  color: white;
  margin-bottom: 16px;
  font-weight: 300;
}

.add-model-card p {
  color: white;
  font-size: 18px;
  font-weight: 600;
  margin: 0;
}

/* 模型卡片 */
.model-card {
  background: white;
  border-radius: 16px;
  padding: 24px;
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.08);
  transition: all 0.3s;
  border: 2px solid transparent;
}

.model-card:hover {
  transform: translateY(-4px);
  box-shadow: 0 8px 30px rgba(0, 0, 0, 0.12);
  border-color: #667eea;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
  padding-bottom: 16px;
  border-bottom: 2px solid #f0f0f0;
}

.card-header h3 {
  font-size: 20px;
  font-weight: 700;
  color: #333;
  margin: 0;
}

.card-actions {
  display: flex;
  gap: 8px;
}

.save-icon-btn,
.cancel-icon-btn,
.edit-icon-btn,
.delete-icon-btn {
  width: 36px;
  height: 36px;
  border: none;
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.3s;
  font-size: 18px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.save-icon-btn {
  background: #d4edda;
  color: #28a745;
}

.save-icon-btn:hover {
  background: #c3e6cb;
  transform: scale(1.1);
}

.cancel-icon-btn {
  background: #f8f9fa;
  color: #6c757d;
}

.cancel-icon-btn:hover {
  background: #e9ecef;
}

.edit-icon-btn {
  background: #e3f2fd;
  color: #1976d2;
}

.edit-icon-btn:hover {
  background: #bbdefb;
  transform: scale(1.1);
}

.delete-icon-btn {
  background: #f8d7da;
  color: #dc3545;
}

.delete-icon-btn:hover {
  background: #f5c6cb;
  transform: scale(1.1);
}

/* 表单 */
.card-form {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.form-field {
  display: flex;
  flex-direction: column;
}

.form-field label {
  font-size: 14px;
  font-weight: 600;
  color: #555;
  margin-bottom: 8px;
}

.form-field input {
  padding: 12px 16px;
  border: 2px solid #e0e0e0;
  border-radius: 8px;
  font-size: 14px;
  transition: all 0.3s;
}

.form-field input:focus {
  outline: none;
  border-color: #667eea;
  box-shadow: 0 0 0 3px rgba(102, 126, 234, 0.1);
}

.hint {
  font-size: 13px;
  color: #999;
  margin-top: 6px;
}

/* 卡片内容 */
.card-content {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.info-row {
  display: flex;
  align-items: center;
  gap: 12px;
}

.info-row .label {
  font-size: 14px;
  font-weight: 600;
  color: #666;
  min-width: 80px;
}

.info-row .value {
  font-size: 14px;
  color: #333;
  font-family: 'Courier New', monospace;
}

/* Tavily 配置 */
.tavily-section {
  background: white;
  border-radius: 16px;
  padding: 32px;
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.08);
}

.tavily-section h2 {
  font-size: 24px;
  font-weight: 700;
  color: #333;
  margin-bottom: 24px;
}

.save-btn {
  margin-top: 24px;
  padding: 14px 32px;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
  border: none;
  border-radius: 8px;
  font-size: 16px;
  font-weight: 700;
  cursor: pointer;
  transition: all 0.3s;
  box-shadow: 0 4px 15px rgba(102, 126, 234, 0.4);
}

.save-btn:hover:not(:disabled) {
  transform: translateY(-2px);
  box-shadow: 0 6px 20px rgba(102, 126, 234, 0.5);
}

.save-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

@keyframes slideDown {
  from {
    opacity: 0;
    transform: translate(-50%, -20px);
  }
  to {
    opacity: 1;
    transform: translate(-50%, 0);
  }
}

/* 响应式 */
@media (max-width: 768px) {
  .models-grid {
    grid-template-columns: 1fr;
  }

  .page-title {
    font-size: 24px;
  }
}
</style>
