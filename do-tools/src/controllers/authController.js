import { User } from '../models/index.js'
import { generateToken } from '../middleware/auth.js'

/**
 * 用户注册
 */
export async function register(req, res) {
  try {
    const { username, email, password } = req.body

    // 验证必填字段
    if (!username || !email || !password) {
      return res.status(400).json({
        error: 'Validation Error',
        message: 'Username, email, and password are required',
      })
    }

    // 检查用户名是否已存在
    const existingUser = await User.findOne({
      where: { username },
    })

    if (existingUser) {
      return res.status(400).json({
        error: 'Validation Error',
        message: 'Username already exists',
      })
    }

    // 检查邮箱是否已存在
    const existingEmail = await User.findOne({
      where: { email },
    })

    if (existingEmail) {
      return res.status(400).json({
        error: 'Validation Error',
        message: 'Email already exists',
      })
    }

    // 创建用户
    const user = await User.create({
      username,
      email,
      password,
    })

    // 生成 token
    const token = generateToken({
      id: user.id,
      username: user.username,
    })

    res.status(201).json({
      message: 'User registered successfully',
      token,
      user: user.toSafeObject(),
    })
  } catch (error) {
    console.error('Register error:', error)
    res.status(500).json({
      error: 'Internal Server Error',
      message: error.message,
    })
  }
}

/**
 * 用户登录
 */
export async function login(req, res) {
  try {
    const { email, password } = req.body

    // 验证必填字段
    if (!email || !password) {
      return res.status(400).json({
        error: 'Validation Error',
        message: 'Email and password are required',
      })
    }

    // 查找用户 (使用邮箱)
    const user = await User.findOne({
      where: { email },
    })

    if (!user) {
      return res.status(401).json({
        error: 'Authentication Failed',
        message: 'Invalid email or password',
      })
    }

    // 验证密码
    const isValidPassword = await user.validatePassword(password)

    if (!isValidPassword) {
      return res.status(401).json({
        error: 'Authentication Failed',
        message: 'Invalid email or password',
      })
    }

    // 生成 token
    const token = generateToken({
      id: user.id,
      username: user.username,
      email: user.email,
    })

    res.json({
      message: 'Login successful',
      token,
      user: user.toSafeObject(),
    })
  } catch (error) {
    console.error('Login error:', error)
    res.status(500).json({
      error: 'Internal Server Error',
      message: error.message,
    })
  }
}

/**
 * 获取当前用户信息
 */
export async function getCurrentUser(req, res) {
  try {
    const user = await User.findByPk(req.user.id)

    if (!user) {
      return res.status(404).json({
        error: 'Not Found',
        message: 'User not found',
      })
    }

    res.json({
      user: user.toSafeObject(),
    })
  } catch (error) {
    console.error('Get current user error:', error)
    res.status(500).json({
      error: 'Internal Server Error',
      message: error.message,
    })
  }
}
