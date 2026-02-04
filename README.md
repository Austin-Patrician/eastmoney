# VAlpha Terminal

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.10+-blue.svg" alt="Python">
  <img src="https://img.shields.io/badge/React-19-61dafb.svg" alt="React">
  <img src="https://img.shields.io/badge/FastAPI-0.100+-009688.svg" alt="FastAPI">
  <img src="https://img.shields.io/badge/TypeScript-5.9-3178c6.svg" alt="TypeScript">
  <img src="https://img.shields.io/badge/License-Non--Commercial-red.svg" alt="License">
</p>

<p align="center">
  <b>智能金融情报终端 | AI-Powered Financial Intelligence Platform</b>
</p>

---

## 简介

**VAlpha Terminal** 是一个专注于中国 A 股市场的智能金融分析平台，集成了投资组合管理、基金分析、股票监控、AI 智能推荐、新闻资讯和市场情绪分析等功能。通过 AI 大语言模型自动生成专业的盘前/盘后分析报告，帮助投资者做出更明智的决策。

### 核心特性

- **投资组合** - 多组合管理、收益分析、压力测试、AI 诊断
- **基金分析** - 管理基金池，自动生成盘前策略和盘后复盘报告
- **股票监控** - 自选股追踪，支持基本面+技术面综合分析
- **AI 智能推荐** - 量化因子模型 + LLM 深度分析，智能选股选基
- **新闻资讯** - 多源财经新闻聚合，AI 情绪分析
- **商品情报** - 黄金、白银等贵金属实时分析
- **市场情绪** - 基于多维度指标的情绪分析
- **邮件通知** - 报告生成、异常提醒自动推送
- **定时任务** - 支持自动化报告生成调度
- **多语言支持** - 中文/英文界面切换
- **多 LLM 支持** - 支持 Gemini、OpenAI、自定义兼容接口

---

## 技术栈

### 后端
| 技术 | 说明 |
|------|------|
| **Python 3.10+** | 主要开发语言 |
| **FastAPI** | 高性能 Web 框架 |
| **AkShare / TuShare** | A 股市场数据源 |
| **APScheduler** | 定时任务调度 |
| **SQLite** | 轻量级数据库 |
| **Redis** | 缓存（可选） |
| **Gemini / OpenAI** | AI 报告生成 |
| **Tavily** | 实时网络搜索 |

### 前端
| 技术 | 说明 |
|------|------|
| **React 19** | UI 框架 |
| **TypeScript** | 类型安全 |
| **Vite 7** | 构建工具 |
| **Material-UI 7** | 组件库 |
| **Tailwind CSS** | 样式框架 |
| **i18next** | 国际化 |

---

## 项目结构

```
valpha-terminal/
├── api_server.py          # FastAPI 后端入口
├── main.py                # 命令行入口
├── requirements.txt       # Python 依赖
├── funds.db              # SQLite 数据库
│
├── src/                  # 后端源码
│   ├── analysis/         # 分析模块
│   │   └── strategies/   # 策略模式实现
│   ├── data_sources/     # 数据源接口 (AkShare/TuShare)
│   ├── llm/              # LLM 集成 (Gemini/OpenAI)
│   ├── scheduler/        # 定时任务
│   ├── storage/          # 数据库操作
│   ├── auth.py           # JWT 认证
│   └── report_gen.py     # 报告生成
│
├── web/                  # React 前端
│   ├── src/
│   │   ├── pages/        # 页面组件
│   │   ├── components/   # 通用组件
│   │   ├── widgets/      # 仪表盘组件
│   │   ├── locales/      # 国际化文件
│   │   └── api.ts        # API 客户端
│   └── package.json
│
├── reports/              # 生成的分析报告
├── config/               # 配置文件
└── docker/               # Docker 部署文件
```

---

## 快速开始

### 环境要求

- Python 3.10+
- Node.js 18+
- npm 或 yarn

### 1. 克隆仓库

```bash
git clone https://github.com/AustinDeng/VAlpha-Terminal.git
cd VAlpha-Terminal
```

### 2. 后端安装

```bash
# 创建虚拟环境
python -m venv venv

# 激活虚拟环境
# Windows
venv\Scripts\activate
# Linux/Mac
source venv/bin/activate

# 安装依赖
pip install -r requirements.txt
```

### 3. 前端安装

```bash
cd web
npm install
```

### 4. 配置环境变量

在项目根目录创建 `.env` 文件（可参考 `.env.example`）：

```env
# ==============================================================================
# LLM 配置 (至少配置一个)
# ==============================================================================

# LLM 提供商选择: gemini, openai
LLM_PROVIDER=gemini

# Gemini 配置
GEMINI_API_KEY=your_gemini_api_key
GEMINI_API_ENDPOINT=                    # 可选：自定义端点

# OpenAI 配置
OPENAI_API_KEY=your_openai_api_key
OPENAI_BASE_URL=https://api.openai.com/v1  # 可选：自定义端点（支持 DeepSeek 等兼容接口）
OPENAI_MODEL=gpt-4o                     # 模型名称

# ==============================================================================
# 数据源配置
# ==============================================================================

# 数据源策略: hybrid (推荐), tushare, akshare
DATA_SOURCE_PROVIDER=hybrid

# TuShare Pro Token (推荐配置，提高数据稳定性)
# 免费注册: https://tushare.pro/register
TUSHARE_API_TOKEN=your_tushare_token

# 数据缓存 TTL (秒)
DATA_SOURCE_CACHE_TTL=60

# ==============================================================================
# 可选配置
# ==============================================================================

# Tavily API (网络搜索，情绪分析需要)
TAVILY_API_KEY=your_tavily_api_key

# Redis 缓存 (可选，提高性能)
REDIS_URL=redis://localhost:6379/0
```

### 5. 启动服务

```bash
# 启动后端 (端口 8000)
uvicorn app.main:app --host 0.0.0.0 --port 8000

# 新终端，启动前端 (端口 5173)
cd web
npm run dev
```

访问 http://localhost:5173 即可使用。

---

## 环境变量说明

### LLM 配置

| 变量名 | 必填 | 说明 |
|--------|------|------|
| `LLM_PROVIDER` | 是 | LLM 提供商：`gemini` 或 `openai` |
| `GEMINI_API_KEY` | 条件 | Gemini API 密钥（使用 Gemini 时必填） |
| `GEMINI_API_ENDPOINT` | 否 | Gemini 自定义端点 |
| `OPENAI_API_KEY` | 条件 | OpenAI API 密钥（使用 OpenAI 时必填） |
| `OPENAI_BASE_URL` | 否 | OpenAI 兼容端点（支持 DeepSeek、本地 LLM 等） |
| `OPENAI_MODEL` | 否 | 模型名称，默认 `gpt-4o` |

### 数据源配置

| 变量名 | 必填 | 说明 |
|--------|------|------|
| `DATA_SOURCE_PROVIDER` | 否 | 数据源策略：`hybrid`(推荐)、`tushare`、`akshare` |
| `TUSHARE_API_TOKEN` | 推荐 | TuShare Pro Token，提高数据稳定性 |
| `DATA_SOURCE_CACHE_TTL` | 否 | 数据缓存时间（秒），默认 60 |

### 可选配置

| 变量名 | 必填 | 说明 |
|--------|------|------|
| `TAVILY_API_KEY` | 否 | Tavily API 密钥，用于网络搜索和情绪分析 |
| `REDIS_URL` | 否 | Redis 连接地址，用于缓存加速 |

---

## 功能截图

| 仪表盘 | 基金分析 |
|--------|----------|
| ![Dashboard](docs/screenshots/dashboard.png) | ![Funds](docs/screenshots/funds.png) |

| 股票监控 | 情报报告 |
|----------|----------|
| ![Stocks](docs/screenshots/sentiments.png) | ![Reports](docs/screenshots/reports.png) |


| 情绪分析报告 |
|----------|
![Reports](docs/screenshots/sentiment_output.png)

---

## API 文档

启动后端后，访问以下地址查看 API 文档：

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

### 主要 API 端点

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/auth/token` | POST | 用户登录 |
| `/api/funds` | GET/PUT/DELETE | 基金管理 |
| `/api/stocks` | GET/PUT/DELETE | 股票管理 |
| `/api/portfolios` | GET/POST/PUT/DELETE | 投资组合管理 |
| `/api/generate/{mode}` | POST | 生成报告 |
| `/api/reports` | GET | 获取报告列表 |
| `/api/recommendations/v2` | POST | AI 智能推荐 |
| `/api/sentiment/analyze` | POST | 情绪分析 |
| `/api/news` | GET | 新闻资讯 |
| `/api/dashboard/overview` | GET | 仪表盘数据 |
| `/api/settings` | GET/POST | 系统设置 |

---

## 配置说明

### LLM 提供商

在系统设置页面可以切换 AI 模型：

- **Gemini** (推荐) - Google 的 Gemini Pro 模型，有免费额度
- **OpenAI** - GPT-4o 系列模型
- **OpenAI 兼容** - 支持 DeepSeek、本地 LLM 等兼容接口

### 定时任务

支持为每个基金/股票配置独立的分析时间：

- **盘前分析**: 默认 08:30 (开盘前)
- **盘后分析**: 默认 15:30 (收盘后)

---

## 开发指南

### 代码规范

```bash
# 前端 lint
cd web && npm run lint

# 前端构建
cd web && npm run build
```

### 添加新的分析策略

1. 在 `src/analysis/strategies/` 创建新策略类
2. 继承 `AnalysisStrategy` 基类
3. 实现 `collect_data()` 和 `generate_report()` 方法
4. 在 `factory.py` 中注册新策略

---

## 部署

### Docker 一体化部署（推荐）

使用 Docker 可以一键部署前后端整合的应用，无需分别配置。

#### 1. 配置环境变量

在项目根目录创建 `.env` 文件（参考上方环境变量说明）。

#### 2. 使用 Docker Compose 启动

```bash
# 构建并启动服务
docker-compose up -d --build

# 查看日志
docker-compose logs -f

# 查看服务状态
docker-compose ps
```

#### 3. 访问应用

打开浏览器访问: http://localhost:9000

#### 4. 常用命令

```bash
# 停止服务
docker-compose down

# 重启服务
docker-compose restart

# 查看实时日志
docker-compose logs -f app

# 进入容器
docker-compose exec app bash
```

#### 5. 使用部署脚本（可选）

**Windows PowerShell:**
```powershell
.\deploy.ps1
```

**Linux/Mac:**
```bash
chmod +x deploy.sh
./deploy.sh
```

#### 6. 数据持久化

Docker 部署会自动挂载以下目录：
- `./data` - 数据库文件
- `./reports` - 生成的报告
- `./config` - 配置文件

更多 Docker 部署细节请参考 [DOCKER_DEPLOY.md](DOCKER_DEPLOY.md)

---

### 传统部署方式

#### 后端 Docker 部署（仅后端）

```bash
# 构建镜像 根目录执行
./run_docker.sh
```

#### 前端 Nginx 部署

建议使用 Nginx 反向代理部署前端：

```nginx
server {
    listen 80;
    listen [::]:80;
    server_name xxxxx.cn;  #替换成你的域名

    # React应用的根目录
    root /upload/valpha/frontend/dist;   #配置成你打包上传的npm 包路径
    index index.html;

    # 访问日志和错误日志
    access_log /var/log/nginx/valpha_access.log;
    error_log /var/log/nginx/valpha_error.log;

    # Gzip压缩配置（提高加载速度）
    gzip on;
    gzip_vary on;
    gzip_min_length 1024;
    gzip_types text/plain text/css text/xml text/javascript application/x-javascript application/xml+rss application/json application/javascript;

    # 处理React Router（重要！）
    location / {
        try_files $uri $uri/ /index.html;
    }

    location /api/ {
           proxy_pass http://127.0.0.1:9000/api/;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
           }
    # 静态资源缓存
    location ~* \.(jpg|jpeg|png|gif|ico|css|js|svg|woff|woff2|ttf|eot)$ {
        expires 1y;
        add_header Cache-Control "public, immutable";
    }


    # 禁止访问隐藏文件
    location ~ /\. {
        deny all;
        access_log off;
        log_not_found off;
    }
}
```

---

## 贡献指南

欢迎提交 Issue 和 Pull Request！

1. Fork 本仓库
2. 创建特性分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 提交 Pull Request

---

## 许可证

本项目采用 **非商业使用许可证** - 详见 [LICENSE](LICENSE) 文件

### 许可说明

- ✅ **允许**：个人使用、学习研究、修改代码、非商业分发
- ❌ **禁止**：商业使用、销售软件、提供付费服务、商业产品集成

如需商业授权，请联系作者。

---

## 致谢

- [AkShare](https://github.com/akfamily/akshare) - 优秀的 A 股数据接口
- [TuShare](https://tushare.pro/) - 专业的金融数据服务
- [Material-UI](https://mui.com/) - React 组件库
- [FastAPI](https://fastapi.tiangolo.com/) - 现代 Python Web 框架

---

## Star History

[![Star History Chart](https://api.star-history.com/svg?repos=Austin-Patrician/eastmoney&type=Date)](https://star-history.com/#Austin-Patrician/eastmoney&Date)

---

<p align="center">
  Made with ❤️ for Chinese Market Investors
</p>
