<template>
  <div class="settings-container">
    <h1 class="page-title">通用设置</h1>

    <!-- Tavily API Key -->
    <div class="settings-section">
      <h2>Tavily 搜索配置</h2>
      <div class="form-field">
        <label>Tavily API Key</label>
        <input
          v-model="tavilyApiKey"
          type="password"
          placeholder="输入 Tavily API Key" />
        <p class="hint">用于网络搜索和情绪分析功能</p>
      </div>
      <button @click="saveSettings" class="save-btn" :disabled="saving">
        {{ saving ? '保存中...' : '保存设置' }}
      </button>
    </div>

    <!-- 成功/错误提示 -->
    <div v-if="showSuccess" class="success-message">✅ 设置保存成功!</div>

    <div v-if="error" class="error-message">❌ {{ error }}</div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import axios from 'axios'

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

    tavilyApiKey.value = response.data.settings.tavilyApiKey || ''
  } catch (err) {
    console.error('Load settings error:', err)
    error.value = '加载设置失败'
  }
}

const saveSettings = async () => {
  saving.value = true
  error.value = ''
  showSuccess.value = false

  try {
    const token = localStorage.getItem('token')
    await axios.put(
      '/api/settings',
      {
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
    console.error('Save settings error:', err)
    error.value = err.response?.data?.message || '保存设置失败'
  } finally {
    saving.value = false
  }
}
</script>

<style scoped>
.settings-container {
  max-width: 800px;
  margin: 0 auto;
}

.page-title {
  font-size: 32px;
  font-weight: 700;
  color: #333;
  margin-bottom: 32px;
  text-align: center;
}

.settings-section {
  background: white;
  border-radius: 16px;
  padding: 32px;
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.08);
  margin-bottom: 24px;
}

.settings-section h2 {
  font-size: 24px;
  font-weight: 700;
  color: #333;
  margin-bottom: 24px;
}

.form-field {
  display: flex;
  flex-direction: column;
  margin-bottom: 24px;
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

.save-btn {
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
</style>
