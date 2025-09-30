#!/bin/bash

# CopyWriter 微服务部署脚本

set -e

echo "🚀 开始部署 CopyWriter 微服务系统"
echo "=================================="

# 检查Docker和Docker Compose是否安装
if ! command -v docker &> /dev/null; then
    echo "❌ Docker 未安装，请先安装 Docker"
    exit 1
fi

if ! command -v docker-compose &> /dev/null; then
    echo "❌ Docker Compose 未安装，请先安装 Docker Compose"
    exit 1
fi

# 创建必要的目录
echo "📁 创建必要的目录..."
mkdir -p shared/media/{raw,audio,text}
mkdir -p logs

# 检查环境文件
if [ ! -f ".env" ]; then
    echo "⚠️  .env 文件不存在，使用默认配置"
    cp .env.example .env 2>/dev/null || echo "请确保 .env 文件已正确配置"
fi

# 停止现有容器（如果存在）
echo "🛑 停止现有容器..."
docker-compose down --remove-orphans || true

# 清理旧镜像（可选）
read -p "是否清理旧的Docker镜像？[y/N]: " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "🧹 清理旧镜像..."
    docker system prune -f
fi

# 构建镜像
echo "🔨 构建所有服务镜像..."
docker-compose build --no-cache

# 启动服务
echo "🎯 启动所有服务..."
docker-compose up -d

# 等待服务启动
echo "⏳ 等待服务启动完成..."
sleep 30

# 检查服务状态
echo "📊 检查服务状态..."
docker-compose ps

# 显示服务URL
echo ""
echo "✅ 部署完成！服务访问地址："
echo "=================================="
echo "🎛️  API网关(主入口):    http://localhost:8000"
echo "📚 API文档:             http://localhost:8000/docs"
echo "🎥 视频服务:             http://localhost:8080"
echo "🎵 FFmpeg服务:          http://localhost:8081"
echo "🎤 ASR服务:             http://localhost:8082"
echo "📊 Redis:               localhost:6379"
echo ""

# 运行健康检查
echo "🔍 运行健康检查..."
python3 test_integration.py

echo ""
echo "📋 常用管理命令："
echo "- 查看日志: docker-compose logs -f [service_name]"
echo "- 重启服务: docker-compose restart [service_name]"
echo "- 停止服务: docker-compose down"
echo "- 查看状态: docker-compose ps"
echo ""
echo "🎉 CopyWriter 微服务系统部署完成！"