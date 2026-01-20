import express from 'express'
import {
  getSettings,
  updateSettings,
} from '../controllers/settingsController.js'
import { authMiddleware } from '../middleware/auth.js'

const router = express.Router()

// 所有路由都需要认证
router.get('/', authMiddleware, getSettings)
router.put('/', authMiddleware, updateSettings)

export default router
