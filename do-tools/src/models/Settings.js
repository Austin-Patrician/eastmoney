import { DataTypes } from 'sequelize'

/**
 * 系统设置模型
 */
export default function defineSettings(sequelize) {
  const Settings = sequelize.define(
    'Settings',
    {
      id: {
        type: DataTypes.INTEGER,
        primaryKey: true,
        autoIncrement: true,
      },
      userId: {
        type: DataTypes.INTEGER,
        allowNull: false,
        references: {
          model: 'users',
          key: 'id',
        },
      },
      // AI 模型配置
      aiModels: {
        type: DataTypes.JSON,
        allowNull: true,
        defaultValue: [],
        comment: 'AI 模型配置列表',
      },
      // 激活的模型索引
      activeModelIndex: {
        type: DataTypes.INTEGER,
        allowNull: true,
        defaultValue: 0,
        comment: '当前激活的模型索引',
      },
      // Tavily API Key
      tavilyApiKey: {
        type: DataTypes.STRING(255),
        allowNull: true,
      },
    },
    {
      tableName: 'settings',
      timestamps: true,
    },
  )

  return Settings
}
