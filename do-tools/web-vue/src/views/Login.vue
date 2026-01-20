<template>
  <div class="auth-container">
    <div class="auth-card">
      <h1>{{ isLogin ? '登录' : '注册' }}</h1>

      <form @submit.prevent="handleSubmit">
        <div class="form-group">
          <label>邮箱</label>
          <input
            v-model="form.email"
            type="email"
            placeholder="请输入邮箱"
            required />
        </div>

        <div v-if="!isLogin" class="form-group">
          <label>用户名</label>
          <input
            v-model="form.username"
            type="text"
            placeholder="请输入用户名 (至少3个字符)"
            :required="!isLogin"
            minlength="3"
            maxlength="50" />
        </div>

        <div class="form-group">
          <label>密码</label>
          <input
            v-model="form.password"
            type="password"
            placeholder="请输入密码 (至少6个字符)"
            required
            minlength="6" />
        </div>

        <div v-if="error" class="error-message">
          {{ error }}
        </div>

        <button type="submit" class="submit-btn" :disabled="loading">
          {{ loading ? '处理中...' : isLogin ? '登录' : '注册' }}
        </button>
      </form>

      <div class="switch-mode">
        <span v-if="isLogin">
          还没有账号?
          <a @click="isLogin = false">立即注册</a>
        </span>
        <span v-else>
          已有账号?
          <a @click="isLogin = true">立即登录</a>
        </span>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { authAPI } from '../api/index.js'

const router = useRouter()
const isLogin = ref(true)
const loading = ref(false)
const error = ref('')

const form = ref({
  email: '',
  username: '',
  password: '',
})

const handleSubmit = async () => {
  loading.value = true
  error.value = ''

  try {
    const data = isLogin.value
      ? { email: form.value.email, password: form.value.password }
      : form.value

    const response = isLogin.value
      ? await authAPI.login(data)
      : await authAPI.register(data)

    // 保存 token 和用户信息
    localStorage.setItem('token', response.token)
    localStorage.setItem('user', JSON.stringify(response.user))

    // 跳转到 Home 页
    router.push('/home')
  } catch (err) {
    error.value = err.response?.data?.message || '操作失败,请重试'
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.auth-container {
  min-height: 100vh;
  width: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  overflow: auto;
}

.auth-card {
  background: white;
  padding: 60px;
  border-radius: 16px;
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.15);
  width: 100%;
  max-width: 500px;
}

h1 {
  text-align: center;
  margin-bottom: 40px;
  color: #333;
  font-size: 36px;
  font-weight: 700;
}

.form-group {
  margin-bottom: 24px;
}

label {
  display: block;
  margin-bottom: 10px;
  color: #555;
  font-weight: 600;
  font-size: 15px;
}

input {
  width: 100%;
  padding: 14px 16px;
  border: 2px solid #e0e0e0;
  border-radius: 8px;
  font-size: 15px;
  transition: all 0.3s;
  box-sizing: border-box;
}

input:focus {
  outline: none;
  border-color: #667eea;
  box-shadow: 0 0 0 3px rgba(102, 126, 234, 0.1);
}

.error-message {
  color: #e74c3c;
  background: #fee;
  padding: 10px;
  border-radius: 6px;
  margin-bottom: 15px;
  font-size: 14px;
}

.submit-btn {
  width: 100%;
  padding: 16px;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
  border: none;
  border-radius: 8px;
  font-size: 17px;
  font-weight: 700;
  cursor: pointer;
  transition: all 0.3s;
  box-shadow: 0 4px 15px rgba(102, 126, 234, 0.4);
}

.submit-btn:hover:not(:disabled) {
  transform: translateY(-2px);
  box-shadow: 0 6px 20px rgba(102, 126, 234, 0.5);
}

.submit-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.switch-mode {
  text-align: center;
  margin-top: 24px;
  color: #666;
  font-size: 15px;
}

.switch-mode a {
  color: #667eea;
  cursor: pointer;
  text-decoration: none;
  font-weight: 500;
}

.switch-mode a:hover {
  text-decoration: underline;
}
</style>
