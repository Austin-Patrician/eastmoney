import express from 'express'
import {
  register,
  login,
  getCurrentUser,
} from '../controllers/authController.js'
import { authMiddleware } from '../middleware/auth.js'

const router = express.Router()

// 公开路由
router.post('/register', register)
router.post('/login', login)

// 受保护路由
router.get('/me', authMiddleware, getCurrentUser)

export default router
