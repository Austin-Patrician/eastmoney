import jwt from 'jsonwebtoken'
import config from '../config/index.js'

/**
 * 生成 JWT Token
 * @param {Object} payload - Token 载荷
 * @returns {string} JWT Token
 */
export function generateToken(payload) {
  return jwt.sign(payload, config.jwt.secret, {
    expiresIn: config.jwt.expiresIn,
  })
}

/**
 * 验证 JWT Token
 * @param {string} token - JWT Token
 * @returns {Object|null} 解码后的载荷或 null
 */
export function verifyToken(token) {
  try {
    return jwt.verify(token, config.jwt.secret)
  } catch (error) {
    return null
  }
}

/**
 * JWT 认证中间件
 */
export function authMiddleware(req, res, next) {
  // 从 Authorization header 获取 token
  const authHeader = req.headers.authorization

  if (!authHeader || !authHeader.startsWith('Bearer ')) {
    return res.status(401).json({
      error: 'Unauthorized',
      message: 'No token provided',
    })
  }

  const token = authHeader.substring(7) // 移除 'Bearer ' 前缀
  const decoded = verifyToken(token)

  if (!decoded) {
    return res.status(401).json({
      error: 'Unauthorized',
      message: 'Invalid or expired token',
    })
  }

  // 将用户信息附加到请求对象
  req.user = decoded
  next()
}
