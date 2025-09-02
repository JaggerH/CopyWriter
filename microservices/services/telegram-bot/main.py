"""
Microservices Telegram Bot Entry Point
现在运行混合服务：Bot + 回调 API 服务器
"""
import asyncio
import sys
import os

# Add src directory to Python path
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from src.hybrid_service import main

if __name__ == "__main__":
    asyncio.run(main())