import express from 'express'
import {
  getFunds,
  searchFunds,
  addFund,
  updateFund,
  deleteFund,
} from '../controllers/fundController.js'
import { authMiddleware } from '../middleware/auth.js'

const router = express.Router()

// 所有基金路由都需要认证
router.use(authMiddleware)

router.get('/', getFunds)
router.get('/search', searchFunds)
router.post('/', addFund)
router.put('/:id', updateFund)
router.delete('/:id', deleteFund)

export default router
