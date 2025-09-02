"""
混合服务 - 同时运行 Telegram Bot 和回调 API 服务器
"""
import asyncio
import logging
import signal
import sys
from typing import List
from loguru import logger

from .bot import MicroservicesTelegramBot
from .callback_api import CallbackAPIServer


class HybridTelegramService:
    """混合 Telegram 服务 - Bot + API 服务器"""
    
    def __init__(self):
        self.bot_service = MicroservicesTelegramBot()
        self.api_server = CallbackAPIServer()
        self.running = True
        self.tasks: List[asyncio.Task] = []
    
    async def start(self):
        """启动所有服务"""
        logger.info("Starting Hybrid Telegram Service...")
        
        try:
            # 创建并启动所有服务任务
            tasks = [
                asyncio.create_task(self.run_bot_service(), name="telegram_bot"),
                asyncio.create_task(self.run_api_server(), name="callback_api"),
            ]
            self.tasks = tasks
            
            # 等待所有任务完成或其中一个失败
            done, pending = await asyncio.wait(
                tasks, 
                return_when=asyncio.FIRST_EXCEPTION
            )
            
            # 检查是否有任务异常退出
            for task in done:
                if task.exception():
                    logger.error(f"Task {task.get_name()} failed with exception: {task.exception()}")
                    raise task.exception()
            
        except KeyboardInterrupt:
            logger.info("Received interrupt signal, shutting down...")
        except Exception as e:
            logger.error(f"Service failed: {e}")
            raise
        finally:
            await self.stop()
    
    async def run_bot_service(self):
        """运行 Telegram Bot 服务"""
        try:
            logger.info("Starting Telegram Bot service...")
            await self.bot_service.start()
        except Exception as e:
            logger.error(f"Bot service failed: {e}")
            raise
    
    async def run_api_server(self):
        """运行回调 API 服务器"""
        try:
            logger.info("Starting callback API server...")
            await self.api_server.start_server(host="0.0.0.0", port=8000)
        except Exception as e:
            logger.error(f"API server failed: {e}")
            raise
    
    async def stop(self):
        """停止所有服务"""
        logger.info("Stopping Hybrid Telegram Service...")
        self.running = False
        
        # 取消所有正在运行的任务
        for task in self.tasks:
            if not task.done():
                task.cancel()
        
        # 等待所有任务完成取消
        if self.tasks:
            await asyncio.gather(*self.tasks, return_exceptions=True)
        
        # 停止 bot 服务
        try:
            await self.bot_service.stop()
        except Exception as e:
            logger.error(f"Error stopping bot service: {e}")
        
        logger.info("All services stopped")


def setup_signal_handlers(service: HybridTelegramService):
    """设置信号处理器"""
    def signal_handler(signum, frame):
        logger.info(f"Received signal {signum}")
        # 创建一个新的事件循环来处理停止逻辑
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(service.stop())
        finally:
            loop.close()
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)


async def main():
    """主函数"""
    # 设置日志
    logging.basicConfig(
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        level=logging.INFO
    )
    
    # 减少一些组件的日志噪音
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("telegram").setLevel(logging.INFO)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    
    # 创建混合服务
    service = HybridTelegramService()
    
    # 设置信号处理
    setup_signal_handlers(service)
    
    try:
        await service.start()
    except KeyboardInterrupt:
        logger.info("Service interrupted")
    except Exception as e:
        logger.error(f"Service failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())