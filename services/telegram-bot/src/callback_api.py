"""
回调 API 服务
接收来自 orchestrator 的回调请求并发送 Telegram 消息
"""
import asyncio
import logging
from fastapi import FastAPI, HTTPException
from telegram import Bot
from telegram.error import TelegramError
from loguru import logger

from .config import Config
from .callback_models import TelegramCallbackData, CallbackResponse, CallbackMessageType
from .message_formatter import TelegramMessageFormatter


class CallbackAPIServer:
    """回调 API 服务器"""

    def __init__(self):
        self.config = Config.from_env()
        self.bot = Bot(token=self.config.telegram.token)
        self.formatter = TelegramMessageFormatter()
        self.status_messages = {}  # task_id -> status_message_id 映射
        self.app = self.create_app()
    
    def create_app(self) -> FastAPI:
        """创建 FastAPI 应用"""
        app = FastAPI(
            title="Telegram Bot Callback API",
            description="接收 orchestrator 回调并发送 Telegram 消息",
            version="1.0.0"
        )
        
        # 健康检查
        @app.get("/health")
        async def health_check():
            try:
                # 测试 Telegram Bot API 连接
                bot_info = await self.bot.get_me()
                return {
                    "status": "healthy",
                    "service": "telegram-bot-callback-api",
                    "bot_username": bot_info.username,
                    "bot_id": bot_info.id
                }
            except Exception as e:
                return {
                    "status": "unhealthy",
                    "service": "telegram-bot-callback-api",
                    "error": str(e)
                }
        
        # 通用回调端点
        @app.post("/api/callback", response_model=CallbackResponse)
        async def handle_callback(callback_data: TelegramCallbackData):
            return await self.process_callback(callback_data)
        
        # 特定消息类型的回调端点
        @app.post("/api/callback/task_created", response_model=CallbackResponse)
        async def handle_task_created(callback_data: TelegramCallbackData):
            callback_data.message_type = CallbackMessageType.TASK_CREATED
            return await self.process_callback(callback_data)
        
        @app.post("/api/callback/task_update", response_model=CallbackResponse)
        async def handle_task_update(callback_data: TelegramCallbackData):
            callback_data.message_type = CallbackMessageType.TASK_UPDATE
            return await self.process_callback(callback_data)
        
        @app.post("/api/callback/task_completed", response_model=CallbackResponse)
        async def handle_task_completed(callback_data: TelegramCallbackData):
            callback_data.message_type = CallbackMessageType.TASK_COMPLETED
            return await self.process_callback(callback_data)
        
        @app.post("/api/callback/task_failed", response_model=CallbackResponse)
        async def handle_task_failed(callback_data: TelegramCallbackData):
            callback_data.message_type = CallbackMessageType.TASK_FAILED
            return await self.process_callback(callback_data)
        
        @app.post("/api/callback/task_title_updated", response_model=CallbackResponse)
        async def handle_task_title_updated(callback_data: TelegramCallbackData):
            callback_data.message_type = CallbackMessageType.TASK_TITLE_UPDATED
            return await self.process_callback(callback_data)
        
        return app
    
    async def process_callback(self, callback_data: TelegramCallbackData) -> CallbackResponse:
        """处理回调请求"""
        try:
            # 格式化消息
            message_text = self.formatter.format_message(
                callback_data.message_type,
                callback_data.task_id,
                callback_data.task_data
            )

            task_id = callback_data.task_id

            # 忽略 TASK_CREATED（bot.py 已经发送了创建成功消息）
            if callback_data.message_type == CallbackMessageType.TASK_CREATED:
                logger.debug(f"Skipping TASK_CREATED notification (already sent by bot)")
                return CallbackResponse(
                    success=True,
                    message="Skipped duplicate task creation notification",
                    telegram_message_id=None
                )

            # 查找是否已有状态消息
            status_message_id = self.status_messages.get(task_id)

            # 检查是否需要发送文本文件（仅用于完成消息）
            should_send_file = False
            text_content = None
            title = "transcript"

            if callback_data.message_type == CallbackMessageType.TASK_COMPLETED:
                result = callback_data.task_data.get('result', {})
                text_content = result.get('text', '') if result else ''
                title = callback_data.task_data.get('title', 'transcript')

                # 如果文本超过 3000 字符，需要发送文件
                if len(text_content) > 3000:
                    should_send_file = True

            # 所有消息类型都尝试编辑现有消息（如果存在）
            if status_message_id:
                # 编辑现有状态消息
                try:
                    await self.bot.edit_message_text(
                        chat_id=callback_data.chat_id,
                        message_id=int(status_message_id),
                        text=message_text,
                        parse_mode='Markdown',
                        disable_web_page_preview=True
                    )

                    logger.info(
                        f"Updated status message {status_message_id} for task {task_id} "
                        f"({callback_data.message_type.value})"
                    )

                    # 如果需要发送文件（长文本），在编辑消息后发送
                    if should_send_file and text_content:
                        from io import BytesIO

                        # 创建文本文件
                        text_file = BytesIO(text_content.encode('utf-8'))
                        text_file.name = f"{title[:50]}.txt"  # 限制文件名长度

                        try:
                            await self.bot.send_document(
                                chat_id=callback_data.chat_id,
                                document=text_file,
                                filename=text_file.name,
                                caption=f"📝 完整转录文本 - {title}"
                            )
                            logger.info(f"Sent text file for task {task_id} ({len(text_content)} chars)")
                        except TelegramError as e:
                            logger.error(f"Failed to send text file for task {task_id}: {e}")

                    # 完成/失败后清理映射
                    if callback_data.message_type in [CallbackMessageType.TASK_COMPLETED, CallbackMessageType.TASK_FAILED]:
                        del self.status_messages[task_id]
                        logger.debug(f"Cleared status message mapping for {callback_data.message_type.value} task {task_id}")

                    return CallbackResponse(
                        success=True,
                        message="Status message updated successfully",
                        telegram_message_id=status_message_id
                    )
                except TelegramError as e:
                    # 如果编辑失败（消息太旧或已删除），发送新消息
                    logger.warning(f"Failed to edit message {status_message_id}: {e}, sending new message")
                    if task_id in self.status_messages:
                        del self.status_messages[task_id]

            # 首次消息或编辑失败后，发送新消息
            message = await self.bot.send_message(
                chat_id=callback_data.chat_id,
                text=message_text,
                parse_mode='Markdown',
                disable_web_page_preview=True
            )

            # 只为非完成状态保存映射
            if callback_data.message_type not in [CallbackMessageType.TASK_COMPLETED, CallbackMessageType.TASK_FAILED]:
                self.status_messages[task_id] = str(message.message_id)
                logger.info(f"Sent initial status message {message.message_id} for task {task_id}")
            else:
                logger.info(f"Sent {callback_data.message_type.value} message for task {task_id}")

            return CallbackResponse(
                success=True,
                message="Notification sent successfully",
                telegram_message_id=str(message.message_id)
            )
            
        except TelegramError as e:
            logger.error(f"Telegram API error: {e}")
            
            # 根据错误类型返回不同的响应
            if "chat not found" in str(e).lower():
                return CallbackResponse(
                    success=False,
                    message=f"Chat not found: {callback_data.chat_id}"
                )
            elif "bot was blocked" in str(e).lower():
                return CallbackResponse(
                    success=False,
                    message=f"Bot was blocked by user: {callback_data.chat_id}"
                )
            else:
                raise HTTPException(status_code=500, detail=f"Telegram API error: {str(e)}")
        
        except Exception as e:
            logger.error(f"Unexpected error processing callback: {e}")
            raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")
    
    async def start_server(self, host: str = "0.0.0.0", port: int = 8000):
        """启动服务器"""
        import uvicorn
        
        logger.info(f"Starting callback API server on {host}:{port}")
        
        # 验证 bot token
        try:
            bot_info = await self.bot.get_me()
            logger.info(f"Bot connected successfully: @{bot_info.username}")
        except Exception as e:
            logger.error(f"Failed to connect to Telegram Bot API: {e}")
            raise
        
        # 启动服务器
        config = uvicorn.Config(
            app=self.app,
            host=host,
            port=port,
            log_level="info"
        )
        server = uvicorn.Server(config)
        await server.serve()