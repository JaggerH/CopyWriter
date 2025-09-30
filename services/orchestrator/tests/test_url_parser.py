"""
URL解析器单元测试 - 简化版
只测试从复制文本中提取链接和平台信息的功能
"""
import unittest
import sys
import os

# 添加上级目录到Python路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from url_parser import VideoURLParser, VideoLinkInfo

class TestVideoURLParser(unittest.TestCase):
    """视频URL解析器测试类"""
    
    def setUp(self):
        """测试前准备"""
        self.parser = VideoURLParser()
    
    def test_douyin_text_parsing(self):
        """测试抖音链接解析 - 用户提供的实际文本"""
        text = '1.53 10/01 P@K.jP hBt:/ 《千盘试炼17》 这期不搞抽象，沉浸式交易技术干货分享# 股票 # 交易 # 技术分析 # 股市 # A股  https://v.douyin.com/ZvKW-34Weos/ 复制此链接，打开Dou音搜索，直接观看视频！'
        
        # 测试提取链接
        clean_url = self.parser.get_clean_url(text)
        self.assertEqual(clean_url, 'https://v.douyin.com/ZvKW-34Weos/')
        
        # 测试平台识别
        video_links = self.parser.parse_video_links(text)
        self.assertEqual(len(video_links), 1)
        
        link_info = video_links[0]
        self.assertEqual(link_info.platform, 'douyin')
        self.assertEqual(link_info.platform_name, '抖音')
        self.assertEqual(link_info.url, 'https://v.douyin.com/ZvKW-34Weos/')
        self.assertEqual(link_info.video_id, 'ZvKW-34Weos')
        self.assertEqual(link_info.title, '千盘试炼17')
        
        # 测试任务标题生成
        task_title = self.parser.generate_task_title(text)
        self.assertEqual(task_title, '抖音 - 千盘试炼17')

if __name__ == '__main__':
    unittest.main()