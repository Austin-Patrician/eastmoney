import express from 'express'
import cors from 'cors'
import helmet from 'helmet'
import morgan from 'morgan'
import config from './config/index.js'
import './models/index.js' // 初始化数据库
import authRoutes from './routes/auth.js'
import settingsRoutes from './routes/settings.js'
import aiRoutes from './routes/ai.js'
import fundRoutes from './routes/funds.js'

const app = express()

// 中间件
app.use(helmet()) // 安全头
app.use(cors()) // 跨域
app.use(express.json()) // JSON 解析
app.use(express.urlencoded({ extended: true })) // URL 编码解析
app.use(morgan('dev')) // 日志

// 健康检查
app.get('/api/health', (req, res) => {
  res.json({
    status: 'ok',
    timestamp: new Date().toISOString(),
    service: 'do-tools',
    version: '1.0.0',
  })
})

// 根路由
app.get('/', (req, res) => {
  res.json({
    message: 'do-tools - 金融数据分析工具',
    version: '1.0.0',
    docs: '/api/health',
  })
})

// 认证路由
app.use('/api/auth', authRoutes)

// 设置路由
app.use('/api/settings', settingsRoutes)

// AI 路由
app.use('/api/ai', aiRoutes)

// 基金路由
app.use('/api/funds', fundRoutes)

// 404 处理
app.use((req, res) => {
  res.status(404).json({
    error: 'Not Found',
    message: `Cannot ${req.method} ${req.path}`,
  })
})

// 错误处理
app.use((err, req, res, next) => {
  console.error('Error:', err)
  res.status(err.status || 500).json({
    error: err.message || 'Internal Server Error',
    ...(config.env === 'development' && { stack: err.stack }),
  })
})

// 启动服务器
const PORT = config.port
app.listen(PORT, () => {
  console.log(`
╔═══════════════════════════════════════════════════════╗
║                                                       ║
║   🚀 do-tools                                         ║
║                                                       ║
║   📡 Server: http://localhost:${PORT}                 ║
║   🌍 Environment: ${config.env}                       ║
║   📊 Data Service: ${config.dataServiceUrl}           ║
║                                                       ║
╚═══════════════════════════════════════════════════════╝
  `)
})

export default app
