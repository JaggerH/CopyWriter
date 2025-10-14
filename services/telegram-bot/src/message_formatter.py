"""
消息格式化器 - 将回调数据转换为用户友好的消息
"""
from typing import Dict, Any
from .callback_models import CallbackMessageType


class TelegramMessageFormatter:
    """Telegram 消息格式化器"""
    
    @staticmethod
    def format_message(message_type: CallbackMessageType, task_id: str, task_data: Dict[str, Any]) -> str:
        """格式化消息内容"""
        
        if message_type == CallbackMessageType.TASK_CREATED:
            return TelegramMessageFormatter._format_task_created(task_id, task_data)
        elif message_type == CallbackMessageType.TASK_UPDATE:
            return TelegramMessageFormatter._format_task_update(task_id, task_data)
        elif message_type == CallbackMessageType.TASK_COMPLETED:
            return TelegramMessageFormatter._format_task_completed(task_id, task_data)
        elif message_type == CallbackMessageType.TASK_FAILED:
            return TelegramMessageFormatter._format_task_failed(task_id, task_data)
        elif message_type == CallbackMessageType.TASK_TITLE_UPDATED:
            return TelegramMessageFormatter._format_task_title_updated(task_id, task_data)
        else:
            return f"📬 任务 `{task_id}` 状态更新: {message_type.value}"
    
    @staticmethod
    def _format_task_created(task_id: str, data: Dict[str, Any]) -> str:
        """格式化任务创建消息"""
        title = data.get('title', 'Unknown')
        url = data.get('url', 'N/A')
        created_time = data.get('created_time', 'N/A')
        
        # 截取URL显示
        display_url = url[:50] + "..." if len(url) > 50 else url
        
        return f"""
🎬 *任务已创建*

🆔 *任务ID*: `{task_id}`
🎯 *标题*: {title}
🔗 *链接*: {display_url}
⏳ *状态*: 队列中

⏱️ *创建时间*: {created_time}

🔔 *处理完成后将自动发送转录结果*
        """.strip()
    
    @staticmethod
    def _format_task_update(task_id: str, data: Dict[str, Any]) -> str:
        """格式化任务更新消息（简洁版，用于实时更新）"""
        progress = data.get('progress', 0)
        current_step = data.get('current_step', 'processing')
        title = data.get('title', 'Unknown')
        status = data.get('status', 'queued')

        status_emoji = {
            'queued': '📋',
            'downloading': '⬇️',
            'converting': '🔄',
            'transcribing': '🎙️',
            'completed': '✅',
            'failed': '❌'
        }

        step_text = {
            'queued': '队列中',
            'downloading': '下载视频',
            'converting': '转换音频',
            'transcribing': '语音识别',
            'completed': '已完成',
            'failed': '处理失败',
            'initialized': '初始化',
            'finished': '已完成'
        }

        emoji = status_emoji.get(status, '🔄')
        step = step_text.get(current_step, current_step)

        # 进度条可视化
        bar_length = 10
        filled = int(progress / 10)
        bar = '█' * filled + '░' * (bar_length - filled)

        return f"""
{emoji} *处理中...*

🎯 {title}

📊 进度: {bar} {progress}%
🔄 {step}

🆔 `{task_id}`
        """.strip()
    
    @staticmethod
    def _format_task_completed(task_id: str, data: Dict[str, Any]) -> str:
        """格式化任务完成消息"""
        title = data.get('title', 'Unknown')
        result = data.get('result', {})
        text_content = result.get('text', 'N/A') if result else 'N/A'
        updated_time = data.get('updated_time', 'N/A')

        # Telegram 消息长度限制为 4096 字符
        # 预留空间给格式化内容，文本内容限制为 3000 字符
        MAX_TEXT_LENGTH = 3000
        PREVIEW_LENGTH = 500

        # 判断文本长度
        if len(text_content) > MAX_TEXT_LENGTH:
            # 长文本：只显示预览
            display_text = text_content[:PREVIEW_LENGTH] + "\n\n...[文本较长，完整内容已作为文件发送]"
            file_hint = "\n\n📎 *完整转录文本已作为文件发送，请查看附件*"
        else:
            # 短文本：完整显示
            display_text = text_content
            file_hint = ""

        return f"""
✅ *转录任务完成*

🆔 *任务ID*: `{task_id}`
🎯 *标题*: {title}

📝 *转录结果*:
```
{display_text}
```

⏱️ *完成时间*: {updated_time}{file_hint}
        """.strip()
    
    @staticmethod
    def _format_task_failed(task_id: str, data: Dict[str, Any]) -> str:
        """格式化任务失败消息"""
        title = data.get('title', 'Unknown')
        error = data.get('error', 'Unknown error')
        updated_time = data.get('updated_time', 'N/A')
        progress = data.get('progress', 0)
        
        return f"""
❌ *任务处理失败*

🆔 *任务ID*: `{task_id}`
🎯 *标题*: {title}
📊 *失败时进度*: {progress}%
🚨 *错误信息*: {error}

⏱️ *失败时间*: {updated_time}

💡 *可能的解决方案*:
• 检查视频链接是否有效
• 稍后重试
• 联系管理员获取帮助
        """.strip()
    
    @staticmethod
    def _format_task_title_updated(task_id: str, data: Dict[str, Any]) -> str:
        """格式化标题更新消息"""
        new_title = data.get('new_title', 'Unknown')
        updated_time = data.get('updated_time', 'N/A')
        
        return f"""
📝 *任务标题已更新*

🆔 *任务ID*: `{task_id}`
🎯 *新标题*: {new_title}

⏱️ *更新时间*: {updated_time}
        """.strip()