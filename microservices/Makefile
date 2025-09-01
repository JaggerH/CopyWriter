# CopyWriter 微服务管理 Makefile

.PHONY: help build up down restart logs clean test

# 默认目标
help:
	@echo "CopyWriter 微服务管理命令:"
	@echo ""
	@echo "  make build     - 构建所有服务镜像"
	@echo "  make up        - 启动所有服务 (GPU加速)"
	@echo "  make down      - 停止所有服务"
	@echo "  make restart   - 重启所有服务"
	@echo "  make logs      - 查看所有服务日志"
	@echo "  make clean     - 清理镜像和容器"
	@echo "  make test      - 运行集成测试"
	@echo ""
	@echo "单独服务操作:"
	@echo "  make video-logs    - 查看视频服务日志"
	@echo "  make asr-logs      - 查看ASR服务日志"
	@echo "  make orchestrator-logs - 查看编排服务日志 (含FFmpeg)"

# 构建所有服务
build:
	docker-compose build

# 启动所有服务 (GPU加速)
up:
	docker-compose up -d

# 启动并构建 (GPU加速)
up-build:
	docker-compose up --build -d

# 停止所有服务
down:
	docker-compose down

# 重启所有服务
restart:
	docker-compose restart

# 查看所有日志
logs:
	docker-compose logs -f

# 单独服务日志
video-logs:
	docker-compose logs -f video-service

asr-logs:
	docker-compose logs -f asr-service

orchestrator-logs:
	docker-compose logs -f orchestrator-service

# 查看服务状态
status:
	docker-compose ps

# 清理
clean:
	docker-compose down -v --rmi all --remove-orphans
	docker system prune -f

# 清理媒体文件
clean-media:
	rm -rf shared/media/raw/* shared/media/audio/* shared/media/text/*

# 重建并启动
rebuild: down build up

# 集成测试
test:
	@echo "运行集成测试..."
	@echo "测试视频服务健康检查..."
	curl -f http://localhost:8080/health || echo "视频服务未就绪"
	@echo "测试ASR服务健康检查..."
	curl -f http://localhost:8082/health || echo "ASR服务未就绪"
	@echo "测试编排服务健康检查 (含FFmpeg)..."
	curl -f http://localhost:8000/health || echo "编排服务未就绪"

# 开发模式 (显示日志)
dev:
	docker-compose up --build

# 生产模式部署
deploy:
	docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d

# 备份数据
backup:
	mkdir -p backups/$(shell date +%Y%m%d_%H%M%S)
	docker run --rm -v copywriter_redis-data:/data -v $(PWD)/backups:/backup alpine tar czf /backup/$(shell date +%Y%m%d_%H%M%S)/redis-backup.tar.gz -C /data .
	cp -r shared/media backups/$(shell date +%Y%m%d_%H%M%S)/media

# 监控
monitor:
	watch docker-compose ps