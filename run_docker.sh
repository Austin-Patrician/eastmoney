#!/bin/bash

# 颜色定义
GREEN='\033[0;32m'
NC='\033[0m' # No Color

echo -e "${GREEN}=== 开始部署 EastMoney 后端服务 (Docker) ===${NC}"

# 1. 检查 Docker 是否安装
if ! command -v docker &> /dev/null; then
    echo "Docker 未安装，请先安装 Docker。"
    exit 1
fi

if ! command -v docker-compose &> /dev/null && ! docker compose version &> /dev/null; then
    echo "Docker Compose 未安装，请先安装。"
    exit 1
fi

# 2. 确保必要的目录结构存在
echo -e "${GREEN}--> 检查并创建目录结构...${NC}"
mkdir -p reports/commodities
mkdir -p reports/sentiment
mkdir -p config
mkdir -p data

# 3. 初始化数据库文件
if [ ! -f "data/funds.db" ]; then
    if [ -d "data/funds.db" ]; then
        echo "Removing erroneous directory 'data/funds.db'..."
        rm -rf data/funds.db
    fi
    echo "Creating empty database file in data/funds.db..."
    touch data/funds.db
fi

# 4. 构建并启动容器
echo -e "${GREEN}--> 构建并启动后端容器...${NC}"
if docker compose version &> /dev/null; then
    docker compose up -d --build
else
    docker-compose up -d --build
fi

# 5. 显示状态
echo -e "${GREEN}--> 部署完成！容器状态：${NC}"
if docker compose version &> /dev/null; then
    docker compose ps
else
    docker-compose ps
fi

echo -e "${GREEN}=== 后端服务已在端口 9000 上线 ===${NC}"
echo "请确保宿主机 Nginx 配置了反向代理指向 http://localhost:9000"