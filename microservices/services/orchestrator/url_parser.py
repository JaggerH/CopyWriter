"""
URL解析工具模块
用于从各种格式的文本中提取视频平台链接并识别平台类型
"""
import re
from typing import Optional, Tuple, Dict, List
from urllib.parse import urlparse
from dataclasses import dataclass

@dataclass
class VideoLinkInfo:
    """视频链接信息"""
    url: str
    platform: str
    platform_name: str
    video_id: Optional[str] = None
    title: Optional[str] = None

class VideoURLParser:
    """视频URL解析器"""
    
    # 平台识别规则
    PLATFORM_PATTERNS = {
        'douyin': {
            'name': '抖音',
            'domains': ['douyin.com', 'iesdouyin.com', 'v.douyin.com'],
            'url_patterns': [
                r'https?://v\.douyin\.com/[A-Za-z0-9_-]+/?',
                r'https?://www\.douyin\.com/video/\d+',
                r'https?://www\.iesdouyin\.com/share/video/\d+',
            ]
        },
        'tiktok': {
            'name': 'TikTok',
            'domains': ['tiktok.com', 'vm.tiktok.com'],
            'url_patterns': [
                r'https?://(?:www\.)?tiktok\.com/@[^/]+/video/\d+',
                r'https?://vm\.tiktok\.com/[A-Za-z0-9]+/?',
                r'https?://(?:www\.)?tiktok\.com/t/[A-Za-z0-9]+/?',
            ]
        },
        'bilibili': {
            'name': 'Bilibili',
            'domains': ['bilibili.com', 'b23.tv'],
            'url_patterns': [
                r'https?://www\.bilibili\.com/video/[A-Za-z0-9]+/?',
                r'https?://b23\.tv/[A-Za-z0-9]+/?',
                r'https?://(?:www\.)?bilibili\.com/video/av\d+/?',
                r'https?://(?:www\.)?bilibili\.com/video/BV[A-Za-z0-9]+/?',
            ]
        },
        'youtube': {
            'name': 'YouTube',
            'domains': ['youtube.com', 'youtu.be', 'www.youtube.com'],
            'url_patterns': [
                r'https?://(?:www\.)?youtube\.com/watch\?v=[A-Za-z0-9_-]+',
                r'https?://youtu\.be/[A-Za-z0-9_-]+',
                r'https?://(?:www\.)?youtube\.com/embed/[A-Za-z0-9_-]+',
            ]
        },
        'xiaohongshu': {
            'name': '小红书',
            'domains': ['xiaohongshu.com', 'xhslink.com'],
            'url_patterns': [
                r'https?://(?:www\.)?xiaohongshu\.com/explore/[A-Za-z0-9]+/?',
                r'https?://xhslink\.com/[A-Za-z0-9]+/?',
            ]
        },
        'kuaishou': {
            'name': '快手',
            'domains': ['kuaishou.com', 'chenzhongtech.com'],
            'url_patterns': [
                r'https?://(?:www\.)?kuaishou\.com/short-video/[A-Za-z0-9]+',
                r'https?://v\.chenzhongtech\.com/[A-Za-z0-9]+/?',
            ]
        }
    }
    
    def extract_urls_from_text(self, text: str) -> List[str]:
        """从文本中提取所有URL"""
        # 通用URL匹配模式
        url_pattern = r'https?://[^\s\u4e00-\u9fff]+'
        urls = re.findall(url_pattern, text)
        
        # 清理URL末尾可能的标点符号
        cleaned_urls = []
        for url in urls:
            # 移除末尾的标点符号
            url = re.sub(r'[,.;:!?。，；：！？]+$', '', url)
            cleaned_urls.append(url)
        
        return cleaned_urls
    
    def identify_platform(self, url: str) -> Tuple[Optional[str], Optional[str]]:
        """识别URL所属的平台"""
        try:
            parsed = urlparse(url)
            domain = parsed.netloc.lower()
            
            # 移除www前缀进行匹配
            clean_domain = domain.replace('www.', '')
            
            for platform_id, platform_info in self.PLATFORM_PATTERNS.items():
                # 检查域名匹配
                for platform_domain in platform_info['domains']:
                    if clean_domain == platform_domain or clean_domain.endswith('.' + platform_domain):
                        return platform_id, platform_info['name']
                
                # 检查URL模式匹配
                for pattern in platform_info['url_patterns']:
                    if re.match(pattern, url, re.IGNORECASE):
                        return platform_id, platform_info['name']
            
            return None, None
            
        except Exception:
            return None, None
    
    def extract_video_id(self, url: str, platform: str) -> Optional[str]:
        """从URL中提取视频ID"""
        try:
            if platform == 'douyin':
                # 抖音短链接：v.douyin.com/ZvKW-34Weos/
                match = re.search(r'v\.douyin\.com/([A-Za-z0-9_-]+)', url)
                if match:
                    return match.group(1)
                # 抖音长链接：www.douyin.com/video/1234567890
                match = re.search(r'/video/(\d+)', url)
                if match:
                    return match.group(1)
            
            elif platform == 'tiktok':
                # TikTok视频ID
                match = re.search(r'/video/(\d+)', url)
                if match:
                    return match.group(1)
                # TikTok短链接
                match = re.search(r'vm\.tiktok\.com/([A-Za-z0-9]+)', url)
                if match:
                    return match.group(1)
            
            elif platform == 'bilibili':
                # B站BV号
                match = re.search(r'/video/(BV[A-Za-z0-9]+)', url)
                if match:
                    return match.group(1)
                # B站av号
                match = re.search(r'/video/av(\d+)', url)
                if match:
                    return f"av{match.group(1)}"
                # B站短链接
                match = re.search(r'b23\.tv/([A-Za-z0-9]+)', url)
                if match:
                    return match.group(1)
            
            elif platform == 'youtube':
                # YouTube watch URL
                match = re.search(r'[?&]v=([A-Za-z0-9_-]+)', url)
                if match:
                    return match.group(1)
                # YouTube短链接
                match = re.search(r'youtu\.be/([A-Za-z0-9_-]+)', url)
                if match:
                    return match.group(1)
            
            return None
            
        except Exception:
            return None
    
    def extract_title_from_text(self, text: str) -> Optional[str]:
        """从文本中提取可能的视频标题"""
        # 查找被《》包围的标题
        title_match = re.search(r'《([^》]+)》', text)
        if title_match:
            return title_match.group(1)
        
        # 查找被""包围的标题
        title_match = re.search(r'"([^"]+)"', text)
        if title_match:
            return title_match.group(1)
        
        # 查找被【】包围的标题
        title_match = re.search(r'【([^】]+)】', text)
        if title_match:
            return title_match.group(1)
        
        return None
    
    def parse_video_links(self, text: str) -> List[VideoLinkInfo]:
        """解析文本中的视频链接信息"""
        results = []
        
        # 提取所有URL
        urls = self.extract_urls_from_text(text)
        
        # 提取可能的标题
        extracted_title = self.extract_title_from_text(text)
        
        for url in urls:
            # 识别平台
            platform_id, platform_name = self.identify_platform(url)
            
            if platform_id and platform_name:
                # 提取视频ID
                video_id = self.extract_video_id(url, platform_id)
                
                # 创建视频链接信息
                link_info = VideoLinkInfo(
                    url=url,
                    platform=platform_id,
                    platform_name=platform_name,
                    video_id=video_id,
                    title=extracted_title
                )
                
                results.append(link_info)
        
        return results
    
    def get_clean_url(self, text: str) -> Optional[str]:
        """从文本中获取第一个有效的视频URL"""
        video_links = self.parse_video_links(text)
        if video_links:
            return video_links[0].url
        return None
    
    def generate_task_title(self, text: str) -> str:
        """为任务生成合适的标题"""
        video_links = self.parse_video_links(text)
        
        if not video_links:
            return "视频任务"
        
        link_info = video_links[0]
        
        # 优先使用提取的标题
        if link_info.title:
            return f"{link_info.platform_name} - {link_info.title}"
        
        # 使用视频ID
        if link_info.video_id:
            return f"{link_info.platform_name}视频 - {link_info.video_id}"
        
        # 使用URL的一部分
        return f"{link_info.platform_name}视频 - {link_info.url[-12:]}"