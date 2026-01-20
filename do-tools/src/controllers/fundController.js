import { Fund } from '../models/index.js'
import axios from 'axios'

// Python 服务地址
const PYTHON_SERVICE_URL =
  process.env.PYTHON_SERVICE_URL || 'http://localhost:8001'

/**
 * 获取用户的基金列表
 */
export async function getFunds(req, res) {
  try {
    const userId = req.user.id

    const funds = await Fund.findAll({
      where: { userId },
      order: [['createdAt', 'DESC']],
    })

    res.json({
      funds: funds.map((f) => ({
        id: f.id,
        fundCode: f.fundCode,
        fundName: f.fundName,
        fundType: f.fundType,
        style: f.style,
        focusBoards: f.focusBoards ? JSON.parse(f.focusBoards) : [],
        scheduleEnabled: f.scheduleEnabled,
        scheduleTime: f.scheduleTime,
        scheduleInterval: f.scheduleInterval,
        createdAt: f.createdAt,
      })),
    })
  } catch (error) {
    console.error('Get funds error:', error)
    res.status(500).json({ error: 'Failed to retrieve funds' })
  }
}

/**
 * 搜索基金（调用 Python 服务）
 */
export async function searchFunds(req, res) {
  try {
    const { keyword } = req.query

    if (!keyword) {
      return res.status(400).json({ error: 'Keyword is required' })
    }

    // 调用 Python 服务的搜索接口
    const response = await axios.get(`${PYTHON_SERVICE_URL}/api/market/funds`, {
      params: { q: keyword },
      timeout: 10000,
    })

    // Python 服务返回的是数组，需要包装成对象
    res.json({
      results: Array.isArray(response.data) ? response.data : [],
    })
  } catch (error) {
    console.error('Search funds error:', error)
    const errorMsg = error.response?.data?.detail || error.message
    res.status(500).json({ error: `Search failed: ${errorMsg}` })
  }
}

/**
 * 添加基金
 */
export async function addFund(req, res) {
  try {
    const userId = req.user.id
    const {
      fundCode,
      fundName,
      fundType,
      style,
      focusBoards,
      scheduleEnabled,
      scheduleTime,
      scheduleInterval,
    } = req.body

    if (!fundCode || !fundName) {
      return res.status(400).json({ error: 'Fund code and name are required' })
    }

    // 检查是否已存在
    const existing = await Fund.findOne({
      where: { userId, fundCode },
    })

    if (existing) {
      return res.status(400).json({ error: 'Fund already exists' })
    }

    const fund = await Fund.create({
      userId,
      fundCode,
      fundName,
      fundType: fundType || '',
      style: style || '',
      focusBoards: focusBoards ? JSON.stringify(focusBoards) : '[]',
      scheduleEnabled: scheduleEnabled || false,
      scheduleTime: scheduleTime || '',
      scheduleInterval: scheduleInterval || '24H',
    })

    res.json({
      message: 'Fund added successfully',
      fund: {
        id: fund.id,
        fundCode: fund.fundCode,
        fundName: fund.fundName,
        fundType: fund.fundType,
        style: fund.style,
        focusBoards: JSON.parse(fund.focusBoards),
        scheduleEnabled: fund.scheduleEnabled,
        scheduleTime: fund.scheduleTime,
        scheduleInterval: fund.scheduleInterval,
      },
    })
  } catch (error) {
    console.error('Add fund error:', error)
    res.status(500).json({ error: 'Failed to add fund' })
  }
}

/**
 * 更新基金
 */
export async function updateFund(req, res) {
  try {
    const userId = req.user.id
    const { id } = req.params
    const {
      style,
      focusBoards,
      scheduleEnabled,
      scheduleTime,
      scheduleInterval,
    } = req.body

    const fund = await Fund.findOne({
      where: { id, userId },
    })

    if (!fund) {
      return res.status(404).json({ error: 'Fund not found' })
    }

    if (style !== undefined) fund.style = style
    if (focusBoards !== undefined)
      fund.focusBoards = JSON.stringify(focusBoards)
    if (scheduleEnabled !== undefined) fund.scheduleEnabled = scheduleEnabled
    if (scheduleTime !== undefined) fund.scheduleTime = scheduleTime
    if (scheduleInterval !== undefined) fund.scheduleInterval = scheduleInterval

    await fund.save()

    res.json({
      message: 'Fund updated successfully',
      fund: {
        id: fund.id,
        fundCode: fund.fundCode,
        fundName: fund.fundName,
        fundType: fund.fundType,
        style: fund.style,
        focusBoards: JSON.parse(fund.focusBoards),
        scheduleEnabled: fund.scheduleEnabled,
        scheduleTime: fund.scheduleTime,
        scheduleInterval: fund.scheduleInterval,
      },
    })
  } catch (error) {
    console.error('Update fund error:', error)
    res.status(500).json({ error: 'Failed to update fund' })
  }
}

/**
 * 删除基金
 */
export async function deleteFund(req, res) {
  try {
    const userId = req.user.id
    const { id } = req.params

    const fund = await Fund.findOne({
      where: { id, userId },
    })

    if (!fund) {
      return res.status(404).json({ error: 'Fund not found' })
    }

    await fund.destroy()

    res.json({ message: 'Fund deleted successfully' })
  } catch (error) {
    console.error('Delete fund error:', error)
    res.status(500).json({ error: 'Failed to delete fund' })
  }
}
