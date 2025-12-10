"""
集成测试 - 测试视频和图片下载功能

运行方式:
    pytest test_integration_download.py -v -s
    pytest test_integration_download.py::test_download_douyin_video -v -s
"""

import pytest
import asyncio
import httpx
import time
from pathlib import Path
from typing import Dict

# 配置
ORCHESTRATOR_URL = "http://localhost:8081"
MEDIA_PATH = Path("../../../shared/media")
POLL_INTERVAL = 2
MAX_WAIT_TIME = 300


# ==================== Fixtures ====================

@pytest.fixture
def orchestrator_client():
    """Orchestrator API 客户端"""
    class OrchestratorClient:
        async def submit_task(self, url: str) -> Dict:
            """提交下载任务"""
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{ORCHESTRATOR_URL}/api/process-media",
                    json={"url": url}
                )
                response.raise_for_status()
                return response.json()

        async def get_task_status(self, task_id: str) -> Dict:
            """获取任务状态"""
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(
                    f"{ORCHESTRATOR_URL}/api/tasks/{task_id}"
                )
                response.raise_for_status()
                return response.json()

        async def wait_for_completion(self, task_id: str) -> Dict:
            """轮询等待任务完成"""
            start_time = time.time()
            last_step = None

            while time.time() - start_time < MAX_WAIT_TIME:
                status = await self.get_task_status(task_id)

                current_step = status.get('current_step', 'unknown')
                current_status = status.get('status', 'unknown')
                progress = status.get('progress', 0)

                # 打印进度（只在步骤变化时）
                if current_step != last_step:
                    print(f"  [{current_step}] {current_status} - {progress}%")
                    last_step = current_step

                if current_status == 'completed':
                    return status
                elif current_status == 'failed':
                    error_msg = status.get('error', 'Unknown error')
                    failed_step = status.get('failed_step', 'unknown')
                    pytest.fail(f"任务失败于步骤 [{failed_step}]: {error_msg}")

                await asyncio.sleep(POLL_INTERVAL)

            pytest.fail(f"任务超时 (>{MAX_WAIT_TIME}秒)")

    return OrchestratorClient()


@pytest.fixture
def file_verifier():
    """文件验证器"""
    class FileVerifier:
        def __init__(self):
            self.created_files = []  # 跟踪本次测试创建的文件

        def verify_files(self, task_data: Dict) -> bool:
            """验证文件是否存在，并记录文件路径"""
            result = task_data.get('result')

            assert result is not None, "任务结果为空"

            # 解析 result（可能是字符串）
            if isinstance(result, str):
                import json
                result = json.loads(result)

            content_type = result.get('data_type')
            assert content_type in ['video', 'image'], f"未知内容类型: {content_type}"

            if content_type == 'video':
                files = {
                    'video': result.get('video_file'),
                    'audio': result.get('audio_file'),
                    'transcript': result.get('text_file')
                }
            else:  # image
                image_files = result.get('image_files', [])
                assert len(image_files) > 0, "图片列表为空"
                files = {f'image_{i+1}': path for i, path in enumerate(image_files)}

            # 验证文件存在
            missing_files = []
            for file_type, file_path in files.items():
                if not file_path:
                    continue

                # 路径转换：容器路径 → Host路径
                rel_path = file_path.replace('/app/media/', '')
                full_path = MEDIA_PATH / rel_path

                if not full_path.exists():
                    missing_files.append(str(full_path))
                else:
                    size = full_path.stat().st_size
                    size_mb = size / (1024 * 1024)
                    size_str = f"{size_mb:.2f} MB" if size_mb >= 1 else f"{size} bytes"
                    print(f"  ✅ {full_path.name} ({size_str})")

                    # 记录文件路径，用于可选的清理
                    self.created_files.append(full_path)

            if missing_files:
                pytest.fail(f"文件不存在: {', '.join(missing_files)}")

            print(f"\n  ℹ️  本次测试创建了 {len(self.created_files)} 个文件")
            return True

        def cleanup(self):
            """清理本次测试创建的文件（可选）"""
            import os

            if not self.created_files:
                return

            print(f"\n  🗑️  清理 {len(self.created_files)} 个测试文件...")

            for file_path in self.created_files:
                try:
                    if file_path.exists():
                        os.remove(file_path)
                        print(f"  ✅ 已删除: {file_path.name}")
                except Exception as e:
                    print(f"  ⚠️  删除失败: {file_path.name} - {str(e)}")

            self.created_files.clear()

    verifier = FileVerifier()
    yield verifier

    # 测试结束后可选清理（默认注释，按需启用）
    # verifier.cleanup()


# ==================== 测试用例 ====================

@pytest.mark.asyncio
@pytest.mark.integration
@pytest.mark.slow
async def test_download_douyin_video(orchestrator_client, file_verifier):
    """测试抖音视频下载"""
    # 完整的抖音分享文本（测试 URL 提取功能）
    test_url = "8.71 03/07 ATy:/ n@q.Rx 不卡特效 # 于瑜伽服  https://v.douyin.com/T9jM81pDtLQ/ 复制此链接，打开Dou音搜索，直接观看视频！"

    if "USER_PROVIDED" in test_url:
        pytest.skip("需要提供真实的抖音视频链接")

    print(f"\n测试抖音视频下载: {test_url}")

    # 1. 提交任务
    print("\n[1/4] 提交任务...")
    result = await orchestrator_client.submit_task(test_url)

    task_id = result.get('task_id')
    platform = result.get('platform')
    content_type = result.get('content_type')

    assert task_id is not None, "任务ID为空"
    assert platform == 'douyin', f"平台识别错误: {platform}"
    assert content_type == 'video', f"类型识别错误: {content_type}"

    print(f"  ✅ 任务已创建: {task_id}")
    print(f"  平台: {platform}, 类型: {content_type}")

    # 2. 等待完成
    print(f"\n[2/4] 等待任务完成...")
    task_data = await orchestrator_client.wait_for_completion(task_id)
    print(f"  ✅ 任务完成")

    # 3. 验证结果
    assert task_data.get('status') == 'completed', "任务状态不是completed"

    # 4. 验证文件
    print(f"\n[3/4] 验证下载文件...")
    file_verifier.verify_files(task_data)
    print(f"  ✅ 所有文件验证通过")


@pytest.mark.asyncio
@pytest.mark.integration
@pytest.mark.slow
async def test_download_douyin_image(orchestrator_client, file_verifier):
    """测试抖音图片下载"""
    # 完整的抖音分享文本（测试 URL 提取功能）
    test_url = "3.56 u@S.LJ 01/10 rrE:/ 登陆我的视角。14天，5000公里# 旅行 # 摄影 # 西藏  https://v.douyin.com/XtlU7xaa3nc/ 复制此链接，打开Dou音搜索，直接观看视频！"

    if "USER_PROVIDED" in test_url:
        pytest.skip("需要提供真实的抖音图片链接")

    print(f"\n测试抖音图片下载: {test_url}")

    # 1. 提交任务
    print("\n[1/4] 提交任务...")
    result = await orchestrator_client.submit_task(test_url)

    task_id = result.get('task_id')
    platform = result.get('platform')
    content_type = result.get('content_type')

    assert task_id is not None, "任务ID为空"
    assert platform == 'douyin', f"平台识别错误: {platform}"
    assert content_type == 'image', f"类型识别错误: {content_type}"

    print(f"  ✅ 任务已创建: {task_id}")
    print(f"  平台: {platform}, 类型: {content_type}")

    # 2. 等待完成
    print(f"\n[2/4] 等待任务完成...")
    task_data = await orchestrator_client.wait_for_completion(task_id)
    print(f"  ✅ 任务完成")

    # 3. 验证结果
    assert task_data.get('status') == 'completed', "任务状态不是completed"

    # 验证图片数量
    result = task_data.get('result')
    if isinstance(result, str):
        import json
        result = json.loads(result)

    image_files = result.get('image_files', [])
    assert len(image_files) > 0, "没有下载到图片"
    print(f"  ℹ️  下载了 {len(image_files)} 张图片")

    # 4. 验证文件
    print(f"\n[3/4] 验证下载文件...")
    file_verifier.verify_files(task_data)
    print(f"  ✅ 所有文件验证通过")


@pytest.mark.asyncio
@pytest.mark.integration
async def test_orchestrator_health(orchestrator_client):
    """测试 Orchestrator 服务健康状态"""
    print("\n测试服务健康状态...")

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(f"{ORCHESTRATOR_URL}/health")
            response.raise_for_status()

        print(f"  ✅ Orchestrator 服务正常")
        assert True

    except httpx.ConnectError:
        pytest.fail(f"无法连接到 Orchestrator ({ORCHESTRATOR_URL})")
    except Exception as e:
        pytest.fail(f"健康检查失败: {str(e)}")


@pytest.mark.asyncio
@pytest.mark.integration
async def test_detect_type_endpoint():
    """测试内容类型检测端点"""
    test_url = "https://v.douyin.com/test"  # 示例URL

    print(f"\n测试类型检测: {test_url}")

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                f"{ORCHESTRATOR_URL}/api/detect-type",
                params={"url": test_url}
            )

            # 可能返回400（无效链接）或200（成功检测）
            if response.status_code == 400:
                print(f"  ℹ️  预期的错误响应（无效链接）")
                assert True
            elif response.status_code == 200:
                data = response.json()
                assert 'platform' in data
                assert 'content_type' in data
                print(f"  ✅ 检测成功: {data['platform']} - {data['content_type']}")
            else:
                pytest.fail(f"意外的状态码: {response.status_code}")

    except httpx.ConnectError:
        pytest.fail(f"无法连接到 Orchestrator ({ORCHESTRATOR_URL})")


# ==================== 辅助测试 ====================

@pytest.mark.unit
def test_media_path_exists():
    """测试媒体目录是否存在"""
    print(f"\n检查媒体目录: {MEDIA_PATH.absolute()}")

    if not MEDIA_PATH.exists():
        pytest.skip(f"媒体目录不存在: {MEDIA_PATH.absolute()}")

    print(f"  ✅ 媒体目录存在")

    # 检查子目录
    subdirs = ['raw', 'audio', 'text']
    for subdir in subdirs:
        path = MEDIA_PATH / subdir
        if path.exists():
            print(f"  ✅ {subdir}/ 存在")
        else:
            print(f"  ⚠️  {subdir}/ 不存在")
