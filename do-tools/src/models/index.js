import { Sequelize } from 'sequelize'
import config from '../config/index.js'
import defineUser from './User.js'
import defineSettings from './Settings.js'

// 创建 Sequelize 实例
const sequelize = new Sequelize({
  dialect: config.database.type,
  storage: config.database.path,
  logging: false, // 关闭 SQL 日志
})

// 定义模型
const User = defineUser(sequelize)
const Settings = defineSettings(sequelize)

// 定义关联
User.hasOne(Settings, { foreignKey: 'userId' })
Settings.belongsTo(User, { foreignKey: 'userId' })

// 同步数据库 (开发环境)
if (config.env === 'development') {
  sequelize
    .sync({ alter: true })
    .then(() => {
      console.log('✅ Database synced')
    })
    .catch((err) => {
      console.error('❌ Database sync error:', err)
    })
}

// 导出
export { sequelize, User, Settings }
