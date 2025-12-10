"""
pytest configuration and shared fixtures
"""
import pytest
from httpx import AsyncClient
from fastapi.testclient import TestClient
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))


@pytest.fixture
def mock_video_service_response():
    """Mock video-service 的标准响应"""
    return {
        "code": 200,
        "data": {
            "platform": "douyin",
            "type": "image",
            "aweme_type": 68,
            "desc": "测试图片",
            "video_id": "123456"
        }
    }


@pytest.fixture
def mock_video_service_video_response():
    """Mock video-service 的视频响应"""
    return {
        "code": 200,
        "data": {
            "platform": "tiktok",
            "type": "video",
            "aweme_type": 0,
            "desc": "测试视频",
            "video_id": "789012"
        }
    }


@pytest.fixture
def mock_httpx_client(mocker, mock_video_service_response):
    """Mock httpx.AsyncClient"""
    mock_response = mocker.Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = mock_video_service_response

    mock_client = mocker.Mock()
    mock_client.get = mocker.AsyncMock(return_value=mock_response)

    return mock_client


@pytest.fixture
async def app_client():
    """FastAPI测试客户端"""
    from main import app
    async with AsyncClient(app=app, base_url="http://test") as client:
        yield client


@pytest.fixture
def mock_redis(mocker):
    """Mock Redis client"""
    mock_r = mocker.AsyncMock()
    mock_r.hset = mocker.AsyncMock()
    mock_r.hget = mocker.AsyncMock()
    mock_r.hgetall = mocker.AsyncMock()
    mock_r.delete = mocker.AsyncMock()
    return mock_r
