import { DataTypes } from 'sequelize'

/**
 * 基金模型
 */
export default function defineFund(sequelize) {
  const Fund = sequelize.define(
    'Fund',
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
      fundCode: {
        type: DataTypes.STRING,
        allowNull: false,
        comment: '基金代码',
      },
      fundName: {
        type: DataTypes.STRING,
        allowNull: false,
        comment: '基金名称',
      },
      fundType: {
        type: DataTypes.STRING,
        allowNull: true,
        comment: '基金类型（股票型、混合型等）',
      },
      style: {
        type: DataTypes.STRING,
        allowNull: true,
        comment: '风格标签',
      },
      focusBoards: {
        type: DataTypes.TEXT,
        allowNull: true,
        comment: '关注板块（JSON 数组）',
      },
      scheduleEnabled: {
        type: DataTypes.BOOLEAN,
        defaultValue: false,
        comment: '是否启用自动调度',
      },
      scheduleTime: {
        type: DataTypes.STRING,
        allowNull: true,
        comment: '调度时间',
      },
      scheduleInterval: {
        type: DataTypes.STRING,
        defaultValue: '24H',
        comment: '调度频率',
      },
    },
    {
      tableName: 'funds',
      timestamps: true,
    },
  )

  return Fund
}
