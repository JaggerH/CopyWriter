# CopyWriter 微服务架构

## 架构概述

CopyWriter 微服务版本包含3个核心服务：

- **video-service** (8080): 视频解析和下载服务
- **asr-service** (8082): GPU加速语音识别服务
- **orchestrator-service** (8000): 任务编排、API网关和FFmpeg转换
- **redis** (6379): 任务队列和缓存

## 快速开始

### 1. 构建和启动所有服务

**需要NVIDIA GPU和nvidia-docker支持:**
```bash
cd microservices
docker-compose up --build
```

### 2. 访问服务

- **主API入口**: http://localhost:8000
- **API文档**: http://localhost:8000/docs
- **视频服务**: http://localhost:8080
- **Redis管理**: http://localhost:6379

### 3. 使用示例

```bash
# 处理Bilibili视频
curl -X POST "http://localhost:8000/api/process-video" \
  -H "Content-Type: application/json" \
  -d '{"url": "https://www.bilibili.com/video/BV1xx411c7mu", "chat_id": "123"}'

# 处理抖音视频
curl -X POST "http://localhost:8000/api/process-video" \
  -H "Content-Type: application/json" \
  -d '{"url": "https://v.douyin.com/xxx", "chat_id": "456"}'
```

## 目录结构

```
microservices/
├── docker-compose.yml          # 服务编排配置
├── .env                       # 环境变量
├── services/                  # 各服务实现
│   ├── ffmpeg-service/        # FFmpeg转换服务
│   ├── asr-service/           # ASR识别服务
│   └── orchestrator/          # 任务编排服务
└── shared/                    # 共享存储
    └── media/                 # 媒体文件存储
        ├── raw/               # 原始下载文件
        ├── audio/             # 转换后的音频
        └── text/              # 识别后的文本
```

## 工作流程

1. **接收请求**: 客户端发送视频URL到orchestrator-service
2. **视频下载**: 调用video-service解析和下载视频
3. **格式转换**: 调用ffmpeg-service将MP4转为MP3
4. **语音识别**: 调用asr-service将MP3转为文本
5. **返回结果**: 返回处理结果和文件路径

## 开发指南

### 本地开发
```bash
# 单独启动某个服务进行调试
docker-compose up video-service redis

# 查看服务日志
docker-compose logs -f orchestrator-service
```

### 扩展服务
- 添加新的下载平台：修改video-service
- 支持新的音频格式：扩展ffmpeg-service
- 添加多语言ASR：扩展asr-service

## 监控和维护

```bash
# 查看服务状态
docker-compose ps

# 重启特定服务  
docker-compose restart video-service

# 清理和重建
docker-compose down && docker-compose up --build
```