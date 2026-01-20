import { DataTypes } from 'sequelize'
import bcrypt from 'bcrypt'

/**
 * 用户模型定义
 * @param {Sequelize} sequelize - Sequelize 实例
 * @returns {Model} User 模型
 */
export default function defineUser(sequelize) {
  const User = sequelize.define(
    'User',
    {
      id: {
        type: DataTypes.INTEGER,
        primaryKey: true,
        autoIncrement: true,
      },
      username: {
        type: DataTypes.STRING(50),
        allowNull: false,
        unique: true,
        validate: {
          len: [3, 50],
        },
      },
      email: {
        type: DataTypes.STRING(100),
        allowNull: false,
        unique: true,
        validate: {
          isEmail: true,
        },
      },
      password: {
        type: DataTypes.STRING(255),
        allowNull: false,
      },
    },
    {
      tableName: 'users',
      timestamps: true,
      hooks: {
        // 保存前自动加密密码
        beforeCreate: async (user) => {
          if (user.password) {
            const salt = await bcrypt.genSalt(10)
            user.password = await bcrypt.hash(user.password, salt)
          }
        },
        beforeUpdate: async (user) => {
          if (user.changed('password')) {
            const salt = await bcrypt.genSalt(10)
            user.password = await bcrypt.hash(user.password, salt)
          }
        },
      },
    },
  )

  // 实例方法:验证密码
  User.prototype.validatePassword = async function (password) {
    return await bcrypt.compare(password, this.password)
  }

  // 实例方法:获取安全的用户信息(不包含密码)
  User.prototype.toSafeObject = function () {
    return {
      id: this.id,
      username: this.username,
      email: this.email,
      createdAt: this.createdAt,
      updatedAt: this.updatedAt,
    }
  }

  return User
}
