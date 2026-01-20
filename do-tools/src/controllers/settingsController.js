import { Settings } from '../models/index.js'

/**
 * 获取用户设置
 */
export async function getSettings(req, res) {
  try {
    const userId = req.user.id

    let settings = await Settings.findOne({
      where: { userId },
    })

    // 如果没有设置,创建默认设置
    if (!settings) {
      settings = await Settings.create({
        userId,
        aiModels: [],
        tavilyApiKey: '',
      })
    }

    res.json({
      settings: {
        id: settings.id,
        aiModels: settings.aiModels || [],
        activeModelIndex: settings.activeModelIndex || 0,
        tavilyApiKey: settings.tavilyApiKey || '',
      },
    })
  } catch (error) {
    console.error('Get settings error:', error)
    res.status(500).json({
      error: 'Internal Server Error',
      message: error.message,
    })
  }
}

/**
 * 更新用户设置
 */
export async function updateSettings(req, res) {
  try {
    const userId = req.user.id
    const { aiModels, activeModelIndex, tavilyApiKey } = req.body

    let settings = await Settings.findOne({
      where: { userId },
    })

    if (!settings) {
      // 创建新设置
      settings = await Settings.create({
        userId,
        aiModels: aiModels || [],
        activeModelIndex: activeModelIndex || 0,
        tavilyApiKey: tavilyApiKey || '',
      })
    } else {
      // 更新现有设置
      await settings.update({
        aiModels: aiModels || settings.aiModels,
        activeModelIndex:
          activeModelIndex !== undefined
            ? activeModelIndex
            : settings.activeModelIndex,
        tavilyApiKey:
          tavilyApiKey !== undefined ? tavilyApiKey : settings.tavilyApiKey,
      })
    }

    res.json({
      message: 'Settings updated successfully',
      settings: {
        id: settings.id,
        aiModels: settings.aiModels || [],
        activeModelIndex: settings.activeModelIndex || 0,
        tavilyApiKey: settings.tavilyApiKey || '',
      },
    })
  } catch (error) {
    console.error('Update settings error:', error)
    res.status(500).json({
      error: 'Internal Server Error',
      message: error.message,
    })
  }
}
