# CopyWriter 微服务架构

## 架构概述

CopyWriter 微服务版本包含4个核心服务：

- **video-service** (8080): 视频解析和下载服务
- **asr-service** (8082): GPU加速语音识别服务
- **orchestrator-service** (8081): 任务编排、API网关和FFmpeg转换
- **telegram-bot**: Telegram Bot接口服务
- **redis** (6379): 任务队列和缓存

## 快速开始

### 1. 构建和启动所有服务

**需要NVIDIA GPU和nvidia-docker支持:**
```bash
cd microservices
docker-compose up --build
```

### 2. 配置环境变量

```bash
# 复制环境变量配置模板
cp .env.example .env

# 编辑配置文件，设置你的Telegram Bot Token
# TELEGRAM_BOT_TOKEN=your_bot_token_here
```

### 3. 访问服务

- **主API入口**: http://localhost:8081
- **Web Dashboard**: http://localhost:8081 (实时任务监控)
- **API文档**: http://localhost:8081/docs
- **视频服务**: http://localhost:8080
- **Redis管理**: http://localhost:6379

### 4. 使用示例

#### 通过 Telegram Bot
1. 在 Telegram 中找到你的 bot
2. 发送 `/start` 开始使用
3. 直接发送视频链接进行转录

#### 通过 API
```bash
# 创建新任务（推荐方式）
curl -X POST "http://localhost:8081/api/tasks" \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://www.bilibili.com/video/BV1xx411c7mu",
    "notification": {
      "callback_type": "telegram",
      "chat_id": "123",
      "user_id": "456"
    }
  }'

# 查看任务状态
curl "http://localhost:8081/api/tasks/{task_id}"

# 获取任务列表
curl "http://localhost:8081/api/tasks?page=1&page_size=20"
```

## 目录结构

```
microservices/
├── docker-compose.yml          # 服务编排配置
├── .env.example               # 环境变量模板
├── .env                       # 环境变量（需要创建）
├── services/                  # 各服务实现
│   ├── Douyin_TikTok_Download_API/  # 视频下载服务
│   ├── asr-service/           # ASR识别服务
│   ├── orchestrator/          # 任务编排服务
│   └── telegram-bot/          # Telegram Bot服务
└── shared/                    # 共享存储
    └── media/                 # 媒体文件存储
        ├── audio/             # 转换后的音频
        └── text/              # 识别后的文本
```

## 工作流程

### Telegram Bot 集成流程
1. **用户输入**: 用户在 Telegram 中发送视频链接
2. **任务创建**: telegram-bot 调用 orchestrator API 创建任务
3. **自动处理**: orchestrator 自动执行完整 pipeline
4. **结果回调**: 完成后通过 Telegram API 直接发送转录结果给用户

### API 直接调用流程
1. **接收请求**: 客户端发送视频URL到orchestrator-service
2. **视频下载**: 调用video-service解析和下载视频
3. **格式转换**: orchestrator内置FFmpeg将视频转为MP3
4. **语音识别**: 调用asr-service将MP3转为文本
5. **通知回调**: 根据配置发送 WebSocket/Telegram/Notion 通知

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
- 支持新的音频格式：扩展orchestrator的FFmpeg集成
- 添加多语言ASR：扩展asr-service
- 添加新的通知方式：扩展orchestrator的notification_manager
- 支持新的Bot平台：参考telegram-bot创建新服务

## 监控和维护

```bash
# 查看服务状态
docker-compose ps

# 查看特定服务日志
docker-compose logs -f telegram-bot
docker-compose logs -f orchestrator-service

# 重启特定服务  
docker-compose restart telegram-bot

# 清理和重建
docker-compose down && docker-compose up --build
```

## 新功能特性

### 统一通知系统
- **多平台支持**: WebSocket (实时Web界面) + Telegram (Bot回调) + 未来Notion集成
- **灵活配置**: 可为每个任务配置不同的回调方式
- **自动重试**: 通知失败时自动重试机制

### Telegram Bot 集成
- **简化架构**: 不再需要复杂的Worker和队列管理
- **即时响应**: 利用orchestrator的实时处理能力
- **用户友好**: 完整的命令支持和进度通知

### 扩展性设计
- **模块化回调**: 易于添加新的通知平台（Notion、邮件等）
- **服务解耦**: 各服务独立部署和扩展
- **配置灵活**: 通过环境变量灵活配置各种选项