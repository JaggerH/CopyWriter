#!/usr/bin/env python3
"""
临时脚本：清除下载队列信息
清除Redis中的所有Telegram Bot队列数据
"""

import redis
import sys
import logging
from typing import Optional

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class QueueCleaner:
    """队列清理器"""
    
    def __init__(self, redis_host: str = "localhost", redis_port: int = 6379, 
                 redis_db: int = 0, redis_password: Optional[str] = None):
        """初始化Redis连接"""
        self.redis_config = {
            'host': redis_host,
            'port': redis_port,
            'db': redis_db,
            'decode_responses': True,
            'socket_connect_timeout': 5,
            'socket_timeout': 5
        }
        
        if redis_password:
            self.redis_config['password'] = redis_password
            
        self.redis_client: Optional[redis.Redis] = None
        
        # 队列名称
        self.queue_names = [
            "telegram_bot:download_queue",
            "telegram_bot:processing",
            "telegram_bot:completed",
            "telegram_bot:failed"
        ]
        
        # 任务状态前缀
        self.task_prefixes = [
            "telegram_bot:task_status:*",
            "telegram_bot:task_progress:*",
            "telegram_bot:task_platform:*"
        ]
        
    def connect(self) -> bool:
        """连接到Redis"""
        try:
            self.redis_client = redis.Redis(**self.redis_config)
            self.redis_client.ping()
            logger.info("✓ 成功连接到Redis")
            return True
        except redis.ConnectionError as e:
            logger.error(f"✗ 连接Redis失败: {e}")
            return False
        except Exception as e:
            logger.error(f"✗ Redis连接异常: {e}")
            return False
    
    def get_queue_stats(self) -> dict:
        """获取队列统计信息"""
        if not self.redis_client:
            return {}
            
        stats = {}
        try:
            for queue_name in self.queue_names:
                length = self.redis_client.llen(queue_name)
                stats[queue_name] = length
                
            # 统计任务状态键
            for prefix in self.task_prefixes:
                keys = self.redis_client.keys(prefix)
                stats[prefix.replace('*', 'keys')] = len(keys)
                
        except Exception as e:
            logger.error(f"获取队列统计失败: {e}")
            
        return stats
    
    def clear_all_queues(self) -> bool:
        """清除所有队列和相关数据"""
        if not self.redis_client:
            logger.error("Redis未连接")
            return False
            
        try:
            # 清除队列
            for queue_name in self.queue_names:
                length = self.redis_client.llen(queue_name)
                if length > 0:
                    self.redis_client.delete(queue_name)
                    logger.info(f"✓ 清除队列 {queue_name} (包含 {length} 个任务)")
                else:
                    logger.info(f"○ 队列 {queue_name} 已为空")
            
            # 清除任务状态键
            for prefix in self.task_prefixes:
                keys = self.redis_client.keys(prefix)
                if keys:
                    self.redis_client.delete(*keys)
                    logger.info(f"✓ 清除 {len(keys)} 个任务状态键 ({prefix})")
                else:
                    logger.info(f"○ 未找到任务状态键 ({prefix})")
            
            logger.info("✓ 所有队列信息清除完成")
            return True
            
        except Exception as e:
            logger.error(f"✗ 清除队列失败: {e}")
            return False
    
    def clear_specific_queue(self, queue_name: str) -> bool:
        """清除指定队列"""
        if not self.redis_client:
            logger.error("Redis未连接")
            return False
            
        try:
            if queue_name not in self.queue_names:
                logger.warning(f"未知队列名称: {queue_name}")
                return False
                
            length = self.redis_client.llen(queue_name)
            if length > 0:
                self.redis_client.delete(queue_name)
                logger.info(f"✓ 清除队列 {queue_name} (包含 {length} 个任务)")
            else:
                logger.info(f"○ 队列 {queue_name} 已为空")
            
            return True
            
        except Exception as e:
            logger.error(f"✗ 清除队列失败: {e}")
            return False

def main():
    """主函数"""
    cleaner = QueueCleaner()
    
    # 连接Redis
    if not cleaner.connect():
        sys.exit(1)
    
    # 显示当前队列状态
    print("\n=== 当前队列状态 ===")
    stats = cleaner.get_queue_stats()
    for key, value in stats.items():
        print(f"{key}: {value}")
    
    # 询问用户确认
    print("\n=== 清除选项 ===")
    print("1. 清除所有队列和任务数据")
    print("2. 清除指定队列")
    print("3. 仅查看状态，不清除")
    print("0. 退出")
    
    try:
        choice = input("\n请选择操作 (0-3): ").strip()
        
        if choice == "1":
            confirm = input("确认清除所有队列信息？这将删除所有任务数据！(y/N): ").strip().lower()
            if confirm in ['y', 'yes']:
                cleaner.clear_all_queues()
            else:
                print("操作已取消")
        
        elif choice == "2":
            print("\n可用队列:")
            for i, queue_name in enumerate(cleaner.queue_names, 1):
                print(f"{i}. {queue_name}")
            
            try:
                queue_idx = int(input("请选择队列编号: ").strip()) - 1
                if 0 <= queue_idx < len(cleaner.queue_names):
                    queue_name = cleaner.queue_names[queue_idx]
                    confirm = input(f"确认清除队列 {queue_name}？(y/N): ").strip().lower()
                    if confirm in ['y', 'yes']:
                        cleaner.clear_specific_queue(queue_name)
                    else:
                        print("操作已取消")
                else:
                    print("无效的队列编号")
            except ValueError:
                print("请输入有效的数字")
        
        elif choice == "3":
            print("仅查看状态，未进行任何清除操作")
        
        elif choice == "0":
            print("退出")
        
        else:
            print("无效的选择")
            
    except KeyboardInterrupt:
        print("\n操作已中断")
        sys.exit(1)
    except Exception as e:
        logger.error(f"执行失败: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()