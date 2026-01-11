#!/bin/bash

# 颜色定义
GREEN='\033[0;32m'
NC='\033[0m' # No Color

echo -e "${GREEN}=== 开始部署 EastMoney 智能终端 ===${NC}"

# 1. 检查 Docker 是否安装
if ! command -v docker &> /dev/null; then
    echo "Docker 未安装，请先安装 Docker。"
    exit 1
fi

if ! command -v docker-compose &> /dev/null && ! docker compose version &> /dev/null; then
    echo "Docker Compose 未安装，请先安装。"
    exit 1
fi

# 2. 确保必要的目录和文件存在
echo -e "${GREEN}--> 检查目录结构...${NC}"
mkdir -p reports/commodities
mkdir -p reports/sentiment
mkdir -p config

# 关键修复：如果 funds.db 是目录，先删除；确保它是一个文件
if [ -d "funds.db" ]; then
    echo "Warning: funds.db is a directory, removing it..."
    rm -rf funds.db
fi

if [ ! -f "funds.db" ]; then
    echo "Creating empty funds.db file..."
    touch funds.db
fi

# 3. 构建并启动容器
echo -e "${GREEN}--> 构建并启动容器...${NC}"
# 使用 docker compose (新版) 或 docker-compose (旧版)
if docker compose version &> /dev/null; then
    docker compose up -d --build
else
    docker-compose up -d --build
fi

# 4. 显示状态
echo -e "${GREEN}--> 部署完成！容器状态：${NC}"
if docker compose version &> /dev/null; then
    docker compose ps
else
    docker-compose ps
fi

echo -e "${GREEN}=== 服务已在端口 80 上线 ===${NC}"
echo "访问地址: http://localhost (或服务器 IP)"