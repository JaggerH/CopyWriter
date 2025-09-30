"""
Microservices Telegram Bot
简化版本，只负责接收用户输入并调用orchestrator API
"""
import asyncio
import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from loguru import logger

from .config import Config
from .orchestrator_client import OrchestratorClient


class MicroservicesTelegramBot:
    """Microservices版本的Telegram Bot"""
    
    def __init__(self):
        self.config = Config.from_env()
        self.orchestrator_client = OrchestratorClient(self.config.orchestrator)
        self.application = None
    
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command"""
        welcome_message = """
🎬 *欢迎使用 CopyWriter 视频转录 Bot！*

📝 *支持平台：*
🔸 Bilibili (哔哩哔哩) - 视频、番剧、直播回放
🎵 Douyin (抖音) - 视频和图片内容  
🎬 TikTok - 国际版抖音内容

🔧 *命令：*
/start - 显示欢迎信息
/status - 查看服务状态
/help - 获取帮助
/platforms - 查看支持的平台

💡 *使用方法：*
直接发送视频链接即可自动下载并转录为文字！

✨ *新特性：*
• 自动语音识别转录
• 高质量下载
• 实时处理进度通知
        """
        await update.message.reply_text(welcome_message, parse_mode='Markdown')
    
    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /help command"""
        help_text = """
📖 *帮助信息*

🎯 *支持的链接格式：*

🔸 *Bilibili:*
• `https://www.bilibili.com/video/BVxxxxxxx`
• `https://www.bilibili.com/video/avxxxxxxx`  
• `https://b23.tv/xxxxxxx`
• 支持带查询参数的链接

🎵 *抖音 (Douyin):*
• `https://v.douyin.com/xxxxxxx`
• `https://www.douyin.com/video/xxxxxxx`

🎬 *TikTok:*
• `https://www.tiktok.com/@user/video/xxxxxxx`
• `https://vm.tiktok.com/xxxxxxx`

⚡ *功能特性：*
• 🎙️ 自动语音识别转录
• 📥 高质量视频下载
• 🔄 实时处理进度推送
• 📱 多平台链接自动识别

❓ *问题反馈：*
如有问题，请联系管理员
        """
        await update.message.reply_text(help_text, parse_mode='Markdown')
    
    async def status_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /status command"""
        # 检查orchestrator服务状态
        is_healthy = await self.orchestrator_client.health_check()
        
        if is_healthy:
            status_text = """
📊 *服务状态*

🟢 *Orchestrator服务*: 正常运行
🤖 *Bot状态*: 运行中
⚡ *功能*: 全部可用

✅ 可以正常处理视频转录任务
            """
        else:
            status_text = """
📊 *服务状态*

🔴 *Orchestrator服务*: 连接失败
🤖 *Bot状态*: 运行中
⚡ *功能*: 部分不可用

❌ 暂时无法处理视频任务，请稍后重试
            """
        
        await update.message.reply_text(status_text, parse_mode='Markdown')
    
    async def platforms_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /platforms command"""
        platforms_text = """
🌍 *支持的平台详情*

🔸 *Bilibili (哔哩哔哩)*
• 支持视频、番剧、直播回放
• 支持格式：
  - `https://www.bilibili.com/video/BVxxxxxxx`
  - `https://www.bilibili.com/video/avxxxxxxx`
  - `https://b23.tv/xxxxxxx` (短链接)
  - `https://m.bilibili.com/video/BVxxxxxxx` (手机版)
• 支持带查询参数的链接

🎵 *Douyin (抖音)*
• 支持视频和图片内容
• 支持格式：
  - `https://v.douyin.com/xxxxxxx`
  - `https://www.douyin.com/video/xxxxxxx`
  - `https://www.iesdouyin.com/share/video/xxxxxxx`

🎬 *TikTok (国际版抖音)*
• 支持视频和图片内容
• 支持格式：
  - `https://www.tiktok.com/@user/video/xxxxxxx`
  - `https://www.tiktok.com/@user/photo/xxxxxxx`
  - `https://vm.tiktok.com/xxxxxxx` (短链接)
  - `https://m.tiktok.com/v/xxxxxxx.html`

✨ *处理流程*
1. 🔗 发送视频链接
2. ⬇️ 自动下载视频
3. 🎙️ 语音识别转录
4. 📝 返回文字内容
        """
        await update.message.reply_text(platforms_text, parse_mode='Markdown')
    
    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle regular messages (URLs and text containing URLs)"""
        message_text = update.message.text.strip()
        user_id = str(update.effective_user.id)
        chat_id = str(update.effective_chat.id)
        message_id = str(update.message.message_id)
        
        # 简单检查是否包含URL
        if not ("http://" in message_text or "https://" in message_text):
            await update.message.reply_text(
                "❌ 请发送视频链接\n\n"
                "支持的平台：\n"
                "🔸 **Bilibili (哔哩哔哩)**\n"
                "🎵 **Douyin (抖音)**\n"
                "🎬 **TikTok**\n\n"
                "💡 请发送完整的视频链接，系统会自动识别平台"
            )
            return
        
        # 检查orchestrator服务状态
        if not await self.orchestrator_client.health_check():
            await update.message.reply_text(
                "❌ 转录服务暂时不可用，请稍后重试\n\n"
                "🔧 您可以使用 /status 命令查看服务状态"
            )
            return
        
        # 创建任务 - 让 orchestrator 处理URL验证和解析
        response = await self.orchestrator_client.create_task(
            url=message_text,  # 直接传递原始消息，让orchestrator处理
            chat_id=chat_id,
            user_id=user_id,
            message_id=message_id
        )
        
        if response:
            success_message = f"""
✅ *任务创建成功！*

🆔 *任务ID*: `{response.task_id}`
🎯 *标题*: {response.title}
🔗 *链接*: {message_text[:50]}{'...' if len(message_text) > 50 else ''}

⏳ *状态*: {response.status}
🔔 *处理完成后将自动发送转录结果*

💡 您可以继续发送其他视频链接
            """
            
            await update.message.reply_text(success_message, parse_mode='Markdown')
            
            logger.info(f"Created task {response.task_id} for user {user_id}")
        else:
            await update.message.reply_text(
                "❌ 创建转录任务失败\n\n"
                "可能原因：\n"
                "• 链接格式不正确或不支持该平台\n"
                "• 服务暂时繁忙\n"
                "• 网络连接问题\n\n"
                "请检查链接格式并稍后重试"
            )
    
    async def error_handler(self, update: object, context: ContextTypes.DEFAULT_TYPE):
        """Handle errors"""
        logger.error(f"Exception while handling an update: {context.error}")
        
        if isinstance(update, Update) and update.message:
            await update.message.reply_text(
                "❌ 处理请求时发生错误，请稍后重试\n\n"
                "如果问题持续存在，请联系管理员"
            )
    
    def setup_application(self):
        """Setup Telegram application"""
        # Create application
        self.application = Application.builder().token(self.config.telegram.token).build()
        
        # Add handlers
        self.application.add_handler(CommandHandler("start", self.start_command))
        self.application.add_handler(CommandHandler("help", self.help_command))
        self.application.add_handler(CommandHandler("status", self.status_command))
        self.application.add_handler(CommandHandler("platforms", self.platforms_command))
        self.application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message))
        
        # Add error handler
        self.application.add_error_handler(self.error_handler)
        
        logger.info("Telegram bot handlers registered")
    
    async def start(self):
        """Start the bot"""
        # Validate orchestrator connection
        if not await self.orchestrator_client.health_check():
            logger.warning("Cannot connect to orchestrator service, bot will start but may not function properly")
        
        # Setup application
        self.setup_application()
        
        logger.info("Starting Telegram bot...")
        
        # Start the bot
        await self.application.initialize()
        await self.application.start()
        
        # Get bot info
        bot_info = await self.application.bot.get_me()
        logger.info(f"Microservices bot started successfully: @{bot_info.username}")
        
        # Start polling
        await self.application.updater.start_polling(
            drop_pending_updates=True,
            allowed_updates=Update.ALL_TYPES
        )
        
        # Keep the bot running  
        await asyncio.Event().wait()
    
    async def stop(self):
        """Stop the bot"""
        if self.application:
            logger.info("Stopping Telegram bot...")
            await self.application.updater.stop()
            await self.application.stop()
            await self.application.shutdown()
            logger.info("Bot stopped")


async def main():
    """Main function"""
    # Setup logging
    logging.basicConfig(
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        level=logging.INFO
    )
    
    # Disable some noisy loggers
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("telegram").setLevel(logging.INFO)
    
    # Create and start bot
    bot = MicroservicesTelegramBot()
    
    try:
        await bot.start()
    except KeyboardInterrupt:
        logger.info("Received interrupt signal")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
    finally:
        await bot.stop()


if __name__ == "__main__":
    asyncio.run(main())