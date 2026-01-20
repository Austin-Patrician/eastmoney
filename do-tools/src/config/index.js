import dotenv from 'dotenv'
import path from 'path'
import { fileURLToPath } from 'url'

// 获取当前文件的目录路径 (ES Module)
const __filename = fileURLToPath(import.meta.url)
const __dirname = path.dirname(__filename)

// 加载环境变量
dotenv.config({ path: path.join(__dirname, '../../.env') })

export default {
  // 服务配置 (硬编码)
  port: 8000,
  env: 'development',

  // Python 数据服务地址
  dataServiceUrl: 'http://localhost:8001',

  // 数据库配置 (SQLite)
  database: {
    type: 'sqlite',
    path: path.join(__dirname, '../../data/do-tools.db'),
  },

  // JWT 配置
  jwt: {
    secret: 'do-tools-secret-key-2026',
    expiresIn: '7d',
  },

  // LLM 配置 (从环境变量读取)
  llm: {
    provider: 'gemini', // 默认使用 Gemini
    geminiApiKey: process.env.GEMINI_API_KEY || '',
    openaiApiKey: process.env.OPENAI_API_KEY || '',
  },

  // 搜索配置 (从环境变量读取)
  tavily: {
    apiKey: process.env.TAVILY_API_KEY || '',
  },

  // 报告目录
  reportsDir: path.join(__dirname, '../../reports'),
}
