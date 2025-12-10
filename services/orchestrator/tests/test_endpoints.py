"""
Tests for API endpoints
"""
import pytest
from httpx import AsyncClient
from unittest.mock import AsyncMock, patch


@pytest.mark.asyncio
async def test_detect_type_endpoint_success(mocker):
    """测试 /api/detect-type 端点成功情况"""
    # Mock detect_content_info
    mock_detect = AsyncMock(return_value={
        "platform": "douyin",
        "content_type": "image",
        "aweme_type": 68,
        "clean_url": "https://v.douyin.com/xxx",
        "title": "测试",
        "error": None
    })

    with patch('main.detect_content_info', mock_detect):
        from main import app
        async with AsyncClient(app=app, base_url="http://test") as client:
            response = await client.get(
                "/api/detect-type",
                params={"url": "https://v.douyin.com/xxx"}
            )

    assert response.status_code == 200
    data = response.json()
    assert data["platform"] == "douyin"
    assert data["content_type"] == "image"


@pytest.mark.asyncio
async def test_detect_type_endpoint_video(mocker):
    """测试 /api/detect-type 端点识别视频"""
    # Mock detect_content_info
    mock_detect = AsyncMock(return_value={
        "platform": "tiktok",
        "content_type": "video",
        "aweme_type": 0,
        "clean_url": "https://www.tiktok.com/@user/video/123",
        "title": "测试视频",
        "error": None
    })

    with patch('main.detect_content_info', mock_detect):
        from main import app
        async with AsyncClient(app=app, base_url="http://test") as client:
            response = await client.get(
                "/api/detect-type",
                params={"url": "https://www.tiktok.com/@user/video/123"}
            )

    assert response.status_code == 200
    data = response.json()
    assert data["platform"] == "tiktok"
    assert data["content_type"] == "video"


@pytest.mark.asyncio
async def test_process_media_endpoint_image(mocker):
    """测试 /api/process-media 处理图片"""
    # Mock detect_content_info
    mock_detect = AsyncMock(return_value={
        "platform": "douyin",
        "content_type": "image",
        "aweme_type": 68,
        "clean_url": "https://v.douyin.com/xxx",
        "title": "测试图片",
        "error": None
    })

    # Mock Redis
    mock_redis = mocker.AsyncMock()
    mock_redis.hset = AsyncMock()

    with patch('main.detect_content_info', mock_detect), \
         patch('main.get_redis', AsyncMock(return_value=mock_redis)):

        from main import app
        async with AsyncClient(app=app, base_url="http://test") as client:
            response = await client.post(
                "/api/process-media",
                json={"url": "https://v.douyin.com/xxx"}
            )

    assert response.status_code == 200
    data = response.json()
    assert data["platform"] == "douyin"
    assert data["content_type"] == "image"
    assert "图片下载任务已创建" in data["message"]
    assert data["status"] == "queued"
    assert "task_id" in data


@pytest.mark.asyncio
async def test_process_media_endpoint_video(mocker):
    """测试 /api/process-media 处理视频"""
    # Mock detect_content_info
    mock_detect = AsyncMock(return_value={
        "platform": "tiktok",
        "content_type": "video",
        "aweme_type": 0,
        "clean_url": "https://www.tiktok.com/@user/video/123",
        "title": "测试视频",
        "error": None
    })

    # Mock Redis
    mock_redis = mocker.AsyncMock()
    mock_redis.hset = AsyncMock()

    with patch('main.detect_content_info', mock_detect), \
         patch('main.get_redis', AsyncMock(return_value=mock_redis)):

        from main import app
        async with AsyncClient(app=app, base_url="http://test") as client:
            response = await client.post(
                "/api/process-media",
                json={"url": "https://www.tiktok.com/@user/video/123"}
            )

    assert response.status_code == 200
    data = response.json()
    assert data["platform"] == "tiktok"
    assert data["content_type"] == "video"
    assert "视频处理任务已创建" in data["message"]
    assert data["status"] == "queued"
    assert "task_id" in data


@pytest.mark.asyncio
async def test_health_endpoint():
    """测试健康检查端点"""
    from main import app
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.get("/health")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"


@pytest.mark.asyncio
async def test_process_media_with_notification_config(mocker):
    """测试带通知配置的媒体处理"""
    # Mock detect_content_info
    mock_detect = AsyncMock(return_value={
        "platform": "douyin",
        "content_type": "video",
        "aweme_type": 0,
        "clean_url": "https://v.douyin.com/xxx",
        "title": "测试视频",
        "error": None
    })

    # Mock Redis
    mock_redis = mocker.AsyncMock()
    mock_redis.hset = AsyncMock()

    with patch('main.detect_content_info', mock_detect), \
         patch('main.get_redis', AsyncMock(return_value=mock_redis)):

        from main import app
        async with AsyncClient(app=app, base_url="http://test") as client:
            response = await client.post(
                "/api/process-media",
                json={
                    "url": "https://v.douyin.com/xxx",
                    "notification": {
                        "callback_type": "telegram",
                        "chat_id": "123456",
                        "user_id": "user123",
                        "message_id": "msg456"
                    }
                }
            )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "queued"
    # Verify Redis was called with notification config
    mock_redis.hset.assert_called_once()
