# Microservices Telegram Bot

这是 CopyWriter 项目的微服务版本 Telegram Bot，与原始的独立 telegram_bot 相比进行了重大简化。

## 主要变化

### 架构简化
- **移除** 复杂的 Worker 和 Queue 管理逻辑
- **移除** 本地下载和处理功能
- **简化** 为纯 Bot 接口，只负责：
  1. 接收用户消息
  2. 调用 orchestrator API 创建任务
  3. 依赖 orchestrator 的通知系统回调结果

### 新的工作流程
1. 用户发送视频链接到 Bot
2. Bot 解析链接并调用 `/api/tasks` 创建任务
3. Orchestrator 自动处理整个 pipeline（下载+转换+转录）
4. 处理完成后，orchestrator 通过 Telegram API 直接发送结果给用户

### 配置需求

**重要**: 所有配置在**项目根目录**的 `.env` 文件中（不是本目录）。

```bash
# 在项目根目录创建 .env 文件
cp .env.example .env

# 编辑配置，填入你的 Telegram Bot Token
# TELEGRAM_BOT_TOKEN=your_bot_token_here
```

必需配置：
- `TELEGRAM_BOT_TOKEN`: Telegram Bot token (从 @BotFather 获取)

可选配置（有默认值）：
- `ORCHESTRATOR_URL`: orchestrator 服务地址 (默认: http://orchestrator-service:8000)
- `ORCHESTRATOR_TIMEOUT`: API 调用超时时间 (默认: 30秒)
- `TELEGRAM_WEBHOOK_ENABLED`: 是否启用 Webhook (默认: false, 使用 polling)

## 与原版本的对比

| 功能 | 原版本 (telegram_bot/) | 微服务版本 |
|------|----------------------|-----------|
| 消息处理 | ✅ 完整的命令和消息处理 | ✅ 简化的命令和消息处理 |
| URL 解析 | ✅ 多平台 URL 解析 | ✅ 复用 orchestrator 的解析逻辑 |
| 任务队列 | ✅ Redis 队列管理 | ❌ 调用 API 创建任务 |
| Worker 处理 | ✅ 独立的下载 worker | ❌ 依赖 orchestrator pipeline |
| 进度通知 | ✅ 复杂的通知管理器 | ✅ orchestrator 回调通知 |
| 文件管理 | ✅ 本地文件处理 | ❌ 无文件处理 |
| 配置复杂度 | 🔴 高 (Redis + Worker + 多个配置文件) | 🟢 低 (只需 Bot token) |

## 优势

1. **简化部署**: 无需复杂的 Worker 配置
2. **更好的扩展性**: 利用 orchestrator 的统一处理能力
3. **减少重复代码**: 不重复实现下载和转录逻辑
4. **统一回调**: 通过 orchestrator 支持 WebSocket、Telegram、未来的 Notion 等
5. **容器化友好**: 更小的镜像，更少的依赖

## 使用方式

用户体验与原版本基本一致：
- 发送 `/start` 查看欢迎信息
- 发送视频链接进行转录
- 自动接收处理完成的结果

## 后续扩展

这个架构为未来的扩展提供了良好基础：
- 可以轻松添加其他平台的 Bot (Discord, Slack 等)
- 通过 orchestrator 的通知系统支持 Notion、邮件等回调
- 无需修改核心处理逻辑即可支持新平台