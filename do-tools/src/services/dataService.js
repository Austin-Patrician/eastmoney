import axios from 'axios'
import config from '../config/index.js'

/**
 * 数据服务客户端
 * 用于调用 Python 数据服务的 API
 */
class DataServiceClient {
  constructor() {
    this.baseURL = config.dataServiceUrl
    this.client = axios.create({
      baseURL: this.baseURL,
      timeout: 30000, // 30秒超时
    })
  }

  /**
   * 搜索基金
   * @param {string} query - 搜索关键词
   * @returns {Promise<Array>} 基金列表
   */
  async searchFunds(query) {
    try {
      const response = await this.client.get('/api/data/funds/search', {
        params: { q: query },
      })
      return response.data
    } catch (error) {
      console.error('Error searching funds:', error.message)
      throw new Error('Failed to search funds from data service')
    }
  }

  /**
   * 获取基金列表
   * @returns {Promise<Array>} 基金列表
   */
  async getFundsList() {
    try {
      const response = await this.client.get('/api/data/funds/list')
      return response.data
    } catch (error) {
      console.error('Error getting funds list:', error.message)
      throw new Error('Failed to get funds list from data service')
    }
  }

  /**
   * 获取股票实时行情
   * @param {string} code - 股票代码
   * @returns {Promise<Object>} 股票行情数据
   */
  async getStockQuote(code) {
    try {
      const response = await this.client.get(`/api/data/stocks/quote/${code}`)
      return response.data
    } catch (error) {
      console.error(`Error getting stock quote for ${code}:`, error.message)
      throw new Error('Failed to get stock quote from data service')
    }
  }

  /**
   * 获取股票历史数据
   * @param {string} code - 股票代码
   * @param {number} days - 天数
   * @returns {Promise<Array>} 历史数据
   */
  async getStockHistory(code, days = 100) {
    try {
      const response = await this.client.get(
        `/api/data/stocks/history/${code}`,
        {
          params: { days },
        },
      )
      return response.data
    } catch (error) {
      console.error(`Error getting stock history for ${code}:`, error.message)
      throw new Error('Failed to get stock history from data service')
    }
  }

  /**
   * 获取市场指数
   * @returns {Promise<Array>} 市场指数数据
   */
  async getMarketIndices() {
    try {
      const response = await this.client.get('/api/data/market/indices')
      return response.data
    } catch (error) {
      console.error('Error getting market indices:', error.message)
      throw new Error('Failed to get market indices from data service')
    }
  }

  /**
   * 检查数据服务健康状态
   * @returns {Promise<boolean>} 是否健康
   */
  async checkHealth() {
    try {
      const response = await this.client.get('/health', { timeout: 5000 })
      return response.status === 200
    } catch (error) {
      console.error('Data service health check failed:', error.message)
      return false
    }
  }
}

// 导出单例
export default new DataServiceClient()
