"""
Tests for content detection functionality
"""
import pytest
from unittest.mock import AsyncMock, patch
import httpx
from main import detect_content_info


class TestDetectContentInfo:
    """测试内容识别功能"""

    @pytest.mark.asyncio
    async def test_detect_douyin_image_success(self, mocker):
        """测试成功识别抖音图片"""
        # Mock httpx.AsyncClient
        mock_response = mocker.Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "code": 200,
            "data": {
                "platform": "douyin",
                "type": "image",
                "aweme_type": 68,
                "desc": "测试图片",
            }
        }

        mock_client = mocker.Mock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.get = AsyncMock(return_value=mock_response)

        mocker.patch('httpx.AsyncClient', return_value=mock_client)

        # 执行测试
        result = await detect_content_info("https://v.douyin.com/xxx")

        # 验证结果
        assert result["platform"] == "douyin"
        assert result["content_type"] == "image"
        assert result["aweme_type"] == 68
        assert result["error"] is None

    @pytest.mark.asyncio
    async def test_detect_timeout_error(self, mocker):
        """测试超时错误处理"""
        mock_client = mocker.Mock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.get = AsyncMock(side_effect=httpx.TimeoutException("Timeout"))

        mocker.patch('httpx.AsyncClient', return_value=mock_client)

        # 应该抛出 HTTPException
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc_info:
            await detect_content_info("https://v.douyin.com/xxx")

        assert exc_info.value.status_code == 504
        assert "超时" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_detect_connection_error(self, mocker):
        """测试连接失败"""
        mock_client = mocker.Mock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.get = AsyncMock(
            side_effect=httpx.ConnectError("Connection refused")
        )

        mocker.patch('httpx.AsyncClient', return_value=mock_client)

        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc_info:
            await detect_content_info("https://v.douyin.com/xxx")

        assert exc_info.value.status_code == 503
        assert "无法连接" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_detect_video_type(self, mocker):
        """测试识别视频类型"""
        mock_response = mocker.Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "code": 200,
            "data": {
                "platform": "tiktok",
                "type": "video",
                "aweme_type": 0,
                "desc": "测试视频",
            }
        }

        mock_client = mocker.Mock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.get = AsyncMock(return_value=mock_response)

        mocker.patch('httpx.AsyncClient', return_value=mock_client)

        result = await detect_content_info("https://www.tiktok.com/@user/video/123")

        assert result["platform"] == "tiktok"
        assert result["content_type"] == "video"

    @pytest.mark.asyncio
    async def test_detect_bilibili_video(self, mocker):
        """测试识别B站视频"""
        mock_response = mocker.Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "code": 200,
            "data": {
                "platform": "bilibili",
                "type": "video",
                "aweme_type": 0,
                "desc": "B站视频测试",
            }
        }

        mock_client = mocker.Mock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.get = AsyncMock(return_value=mock_response)

        mocker.patch('httpx.AsyncClient', return_value=mock_client)

        result = await detect_content_info("https://www.bilibili.com/video/BV1xx411c7mD")

        assert result["platform"] == "bilibili"
        assert result["content_type"] == "video"

    @pytest.mark.asyncio
    async def test_detect_http_error_response(self, mocker):
        """测试HTTP错误响应"""
        mock_response = mocker.Mock()
        mock_response.status_code = 404

        mock_client = mocker.Mock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.get = AsyncMock(return_value=mock_response)

        mocker.patch('httpx.AsyncClient', return_value=mock_client)

        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc_info:
            await detect_content_info("https://v.douyin.com/invalid")

        assert exc_info.value.status_code == 400
        assert "无法识别链接类型" in exc_info.value.detail
