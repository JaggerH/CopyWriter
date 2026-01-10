#!/usr/bin/env python3
"""
场景热词系统测试脚本

测试内容：
1. 场景热词模块功能
2. API 场景参数验证
3. 不同场景的热词加载
"""

import sys
import requests
from pathlib import Path

# 添加当前目录到路径
sys.path.insert(0, str(Path(__file__).parent))

from scene_hotwords import (
    get_scene_hotwords,
    get_available_scenes,
    get_scene_description,
    get_scene_stats
)


def test_scene_hotwords_module():
    """测试场景热词模块"""
    print("=" * 60)
    print("测试 1: 场景热词模块功能")
    print("=" * 60)

    # 测试可用场景
    scenes = get_available_scenes()
    print(f"\n✓ 可用场景: {', '.join(scenes)}")

    # 测试每个场景
    stats = get_scene_stats()
    print(f"\n✓ 场景热词统计:")
    for scene, count in stats.items():
        desc = get_scene_description(scene)
        print(f"  - {scene:12s}: {count:3d} 个热词 ({desc})")

    # 测试技术场景
    print(f"\n✓ 技术场景热词示例:")
    tech_words = get_scene_hotwords("tech")
    print(f"  总数: {len(tech_words)}")
    print(f"  前 20 个: {', '.join(tech_words[:20])}")

    # 验证关键词存在
    critical_words = ["GitHub", "Docker", "Python", "Kubernetes"]
    missing = [w for w in critical_words if w not in tech_words]
    if missing:
        print(f"\n❌ 缺少关键词: {missing}")
        return False
    else:
        print(f"\n✓ 关键词验证通过: {', '.join(critical_words)}")

    return True


def test_api_health():
    """测试 API 健康状态"""
    print("\n" + "=" * 60)
    print("测试 2: API 服务健康状态")
    print("=" * 60)

    try:
        response = requests.get("http://localhost:8082/health", timeout=5)
        if response.status_code == 200:
            data = response.json()
            print(f"\n✓ 服务状态: {data['status']}")
            print(f"✓ 模型已加载: {data['model_loaded']}")
            return True
        else:
            print(f"\n❌ 服务异常: HTTP {response.status_code}")
            return False
    except Exception as e:
        print(f"\n❌ 无法连接服务: {e}")
        return False


def test_api_model_info():
    """测试模型信息接口"""
    print("\n" + "=" * 60)
    print("测试 3: 模型信息接口")
    print("=" * 60)

    try:
        response = requests.get("http://localhost:8082/models", timeout=5)
        if response.status_code == 200:
            data = response.json()
            print(f"\n✓ 模型类型: {data['model_type']}")
            print(f"✓ 模型已加载: {data['model_loaded']}")

            features = data.get('features', {})
            print(f"\n✓ 功能特性:")
            print(f"  - RAG 热词: {features.get('rag_hotwords', False)}")
            print(f"  - 智能分句: {features.get('smart_segmentation', False)}")
            print(f"  - 流式识别: {features.get('streaming', False)}")

            model_info = data.get('model_info', {})
            if 'vram_allocated_gb' in model_info:
                print(f"\n✓ GPU 显存: {model_info['vram_allocated_gb']:.2f} GB")
                print(f"✓ 设备: {model_info.get('device', 'Unknown')}")

            return True
        else:
            print(f"\n❌ 获取模型信息失败: HTTP {response.status_code}")
            return False
    except Exception as e:
        print(f"\n❌ 无法获取模型信息: {e}")
        return False


def test_scene_parameter():
    """测试场景参数（不需要实际音频文件）"""
    print("\n" + "=" * 60)
    print("测试 4: 场景参数验证")
    print("=" * 60)

    scenes_to_test = ["tech", "medical", "finance", "general"]

    print(f"\n✓ 场景参数说明:")
    print(f"  API 端点: POST /transcribe")
    print(f"  参数: scene (可选, 默认 'tech')")
    print(f"  可用值: {', '.join(scenes_to_test)}")

    print(f"\n✓ 使用示例:")
    print(f"  curl -X POST http://localhost:8082/transcribe \\")
    print(f"       -F 'file=@audio.mp3' \\")
    print(f"       -F 'scene=tech'")

    print(f"\n✓ 不同场景的热词数量:")
    for scene in scenes_to_test:
        hotwords = get_scene_hotwords(scene)
        desc = get_scene_description(scene)
        print(f"  - scene={scene:8s}: {len(hotwords):3d} 个热词 ({desc})")

    return True


def main():
    """主测试函数"""
    print("\n" + "=" * 60)
    print("场景热词系统 - 完整测试")
    print("=" * 60)

    results = []

    # 测试 1: 场景热词模块
    results.append(("场景热词模块", test_scene_hotwords_module()))

    # 测试 2: API 健康状态
    results.append(("API 健康状态", test_api_health()))

    # 测试 3: 模型信息
    results.append(("模型信息接口", test_api_model_info()))

    # 测试 4: 场景参数
    results.append(("场景参数验证", test_scene_parameter()))

    # 总结
    print("\n" + "=" * 60)
    print("测试总结")
    print("=" * 60)

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for test_name, result in results:
        status = "✓ 通过" if result else "✗ 失败"
        print(f"{status:8s} - {test_name}")

    print(f"\n通过率: {passed}/{total} ({passed*100//total}%)")

    if passed == total:
        print("\n✓ 所有测试通过！场景热词系统已成功部署。")
        print("\n下一步:")
        print("  1. 准备包含技术术语的测试音频文件")
        print("  2. 使用不同 scene 参数测试识别效果")
        print("  3. 对比 scene=tech 和 scene=general 的准确率差异")
        return 0
    else:
        print(f"\n❌ 有 {total - passed} 个测试失败，请检查日志。")
        return 1


if __name__ == "__main__":
    sys.exit(main())
