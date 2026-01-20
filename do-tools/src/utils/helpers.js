/**
 * 工具函数集合
 */

/**
 * 格式化日期
 * @param {Date} date - 日期对象
 * @param {string} format - 格式 (YYYY-MM-DD, YYYY-MM-DD HH:mm:ss)
 * @returns {string} 格式化后的日期字符串
 */
export function formatDate(date = new Date(), format = 'YYYY-MM-DD') {
  const d = new Date(date)
  const year = d.getFullYear()
  const month = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  const hours = String(d.getHours()).padStart(2, '0')
  const minutes = String(d.getMinutes()).padStart(2, '0')
  const seconds = String(d.getSeconds()).padStart(2, '0')

  if (format === 'YYYY-MM-DD HH:mm:ss') {
    return `${year}-${month}-${day} ${hours}:${minutes}:${seconds}`
  }
  return `${year}-${month}-${day}`
}

/**
 * 生成报告文件名
 * @param {string} mode - 模式 (pre/post)
 * @param {string} code - 基金/股票代码
 * @param {string} name - 名称
 * @returns {string} 文件名
 */
export function generateReportFilename(mode, code, name) {
  const date = formatDate(new Date(), 'YYYY-MM-DD')
  const time = new Date().toTimeString().slice(0, 8).replace(/:/g, '')
  return `${date}_${mode}_${code}_${name}.md`
}

/**
 * 延迟函数
 * @param {number} ms - 毫秒数
 * @returns {Promise}
 */
export function delay(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms))
}

/**
 * 安全的 JSON 解析
 * @param {string} str - JSON 字符串
 * @param {*} defaultValue - 默认值
 * @returns {*} 解析结果或默认值
 */
export function safeJsonParse(str, defaultValue = null) {
  try {
    return JSON.parse(str)
  } catch (error) {
    return defaultValue
  }
}

/**
 * 验证邮箱格式
 * @param {string} email - 邮箱地址
 * @returns {boolean} 是否有效
 */
export function isValidEmail(email) {
  const regex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/
  return regex.test(email)
}

/**
 * 生成随机字符串
 * @param {number} length - 长度
 * @returns {string} 随机字符串
 */
export function generateRandomString(length = 32) {
  const chars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789'
  let result = ''
  for (let i = 0; i < length; i++) {
    result += chars.charAt(Math.floor(Math.random() * chars.length))
  }
  return result
}
