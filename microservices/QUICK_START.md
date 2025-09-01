# CopyWriter 微服务快速启动指南

## 🚀 快速开始

### 1. 启动所有服务

**使用NVIDIA NGC优化镜像 (CUDA 12.8高性能):**
```bash
cd microservices
docker-compose up --build
# 或使用Makefile
make up-build
```

**要求:**
- NVIDIA GPU (支持CUDA 12.8+)  
- nvidia-docker支持
- 至少8GB显存 (推荐12GB+)

### 2. 验证服务状态

```bash
# 方法一：使用测试脚本
python run_tests.py

# 方法二：使用Make命令
make test

# 方法三：手动检查
curl http://localhost:8000/health
```

### 3. 处理视频

```bash
# 提交处理任务
curl -X POST "http://localhost:8000/api/process-video" \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://www.bilibili.com/video/BV1xx411c7mu", 
    "chat_id": "test_user",
    "quality": "4"
  }'

# 返回结果示例
{
  "task_id": "abc-123-def",
  "status": "queued",
  "message": "任务已加入队列，开始处理"
}
```

### 4. 查看任务进度

```bash
# 查看特定任务状态
curl http://localhost:8000/api/task/abc-123-def

# 返回结果示例
{
  "task_id": "abc-123-def",
  "status": "completed",
  "current_step": "finished", 
  "progress": 100,
  "result": {
    "video_path": "/app/media/raw/abc-123-def.mp4",
    "audio_path": "/app/media/audio/abc-123-def.mp3", 
    "text_path": "/app/media/text/abc-123-def.txt",
    "text": "识别出的文字内容..."
  }
}
```

## 📋 服务端口

- **主API网关**: http://localhost:8000 ([文档](http://localhost:8000/docs)) - 包含FFmpeg转换
- **视频服务**: http://localhost:8080 ([文档](http://localhost:8080/docs))
- **ASR服务**: http://localhost:8082 ([文档](http://localhost:8082/docs)) - GPU加速
- **Redis**: localhost:6379

## 🛠️ 开发模式

### 启动开发环境

```bash
# 启动开发环境（支持热重载）
docker-compose -f docker-compose.dev.yml up --build

# 或者只启动部分服务
docker-compose -f docker-compose.dev.yml up redis ffmpeg-service asr-service
```

### 独立测试各服务

```bash
# 测试FFmpeg转换
curl -X POST http://localhost:8081/convert \
  -H "Content-Type: application/json" \
  -d '{"input_path": "/app/media/raw/test.mp4", "quality": "4"}'

# 测试ASR识别
curl -X POST http://localhost:8082/transcribe \
  -H "Content-Type: application/json" \
  -d '{"audio_path": "/app/media/audio/test.mp3"}'

# 查看支持的格式
curl http://localhost:8081/formats
curl http://localhost:8082/models
```

## 📊 监控和管理

### 查看服务状态

```bash
# 查看容器状态
docker-compose ps

# 查看所有服务健康状态
curl http://localhost:8000/api/services/status
```

### 查看日志

```bash
# 查看所有日志
docker-compose logs -f

# 查看特定服务日志
docker-compose logs -f orchestrator-service
docker-compose logs -f ffmpeg-service
docker-compose logs -f asr-service
```

### 重启服务

```bash
# 重启所有服务
docker-compose restart

# 重启特定服务
docker-compose restart orchestrator-service
```

## 🔧 常见问题

### Q: 服务启动失败？
A: 检查端口是否被占用，查看详细错误日志：
```bash
docker-compose logs [service-name]
```

### Q: ASR服务启动很慢？
A: 首次启动需要下载模型，请耐心等待。可以查看日志进度：
```bash
docker-compose logs -f asr-service
```

### Q: 视频下载失败？
A: 请确保网络连接正常，并且视频URL有效。某些平台可能需要更新cookie配置。

### Q: 如何添加新的视频平台支持？
A: 修改你已经改造的Douyin_TikTok_Download_API，添加新的平台解析逻辑。

## 🗂️ 文件结构

```
microservices/
├── docker-compose.yml          # 生产环境配置
├── docker-compose.dev.yml      # 开发环境配置
├── services/                   # 各微服务代码
│   ├── ffmpeg-service/         # FFmpeg转换服务
│   ├── asr-service/           # ASR识别服务
│   └── orchestrator/          # 任务编排服务
├── shared/                    # 共享数据目录
│   └── media/                 # 媒体文件存储
│       ├── raw/               # 原始视频文件
│       ├── audio/             # 转换后音频文件
│       └── text/              # 识别后文本文件
├── test_integration.py        # 集成测试脚本
├── run_tests.py              # 快速测试脚本
└── Makefile                  # 管理命令
```

## 🎯 下一步

1. **集成Telegram Bot**: 将现有的telegram_bot集成到微服务架构中
2. **添加监控**: 集成Prometheus和Grafana进行系统监控
3. **负载均衡**: 使用nginx进行负载均衡和反向代理
4. **持续集成**: 设置CI/CD管道自动化部署

## 📞 获取帮助

- 查看API文档: http://localhost:8000/docs
- 运行健康检查: `python run_tests.py`
- 查看容器日志: `docker-compose logs -f`

🎉 享受你的CopyWriter微服务系统！