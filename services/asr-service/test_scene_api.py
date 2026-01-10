#!/usr/bin/env python3
"""
场景热词管理 API 接口测试脚本

测试内容：
1. GET /scene-hotwords/list - 获取所有场景热词
2. GET /scene-hotwords/scenes - 获取所有场景
3. GET /scene-hotwords/{scene} - 获取指定场景热词
4. POST /scene-hotwords/{scene}/add - 添加热词
5. DELETE /scene-hotwords/{scene}/{word} - 删除热词
6. GET /scene-hotwords/check-duplicate/{word} - 检查重复
7. GET /scene-hotwords/stats - 获取统计信息
"""

import requests
import sys


BASE_URL = "http://localhost:8082"


def test_get_all_hotwords():
    """测试获取所有场景热词"""
    print("=" * 60)
    print("测试 1: GET /scene-hotwords/list")
    print("=" * 60)

    try:
        response = requests.get(f"{BASE_URL}/scene-hotwords/list", timeout=5)
        if response.status_code == 200:
            data = response.json()
            print(f"\n✓ 成功获取场景热词列表")
            print(f"  总场景数: {data['total_scenes']}")

            for scene, info in list(data['scenes'].items())[:3]:  # 显示前3个场景
                print(f"\n  场景: {scene}")
                print(f"    描述: {info['description']}")
                print(f"    热词数: {info['count']}")
                print(f"    前5个: {', '.join(info['hotwords'][:5])}")

            return True
        else:
            print(f"\n❌ 请求失败: HTTP {response.status_code}")
            print(f"   响应: {response.text}")
            return False

    except Exception as e:
        print(f"\n❌ 请求失败: {e}")
        return False


def test_get_scenes():
    """测试获取所有场景"""
    print("\n" + "=" * 60)
    print("测试 2: GET /scene-hotwords/scenes")
    print("=" * 60)

    try:
        response = requests.get(f"{BASE_URL}/scene-hotwords/scenes", timeout=5)
        if response.status_code == 200:
            data = response.json()
            print(f"\n✓ 成功获取场景列表")
            print(f"  总场景数: {data['total']}")

            for scene in data['scenes']:
                print(f"\n  - {scene['code']:12s}: {scene['description']} ({scene['count']} 个热词)")

            return True
        else:
            print(f"\n❌ 请求失败: HTTP {response.status_code}")
            print(f"   响应: {response.text}")
            return False

    except Exception as e:
        print(f"\n❌ 请求失败: {e}")
        return False


def test_get_scene_hotwords():
    """测试获取指定场景热词"""
    print("\n" + "=" * 60)
    print("测试 3: GET /scene-hotwords/tech")
    print("=" * 60)

    try:
        response = requests.get(f"{BASE_URL}/scene-hotwords/tech", timeout=5)
        if response.status_code == 200:
            data = response.json()
            print(f"\n✓ 成功获取 tech 场景热词")
            print(f"  场景: {data['scene']}")
            print(f"  描述: {data['description']}")
            print(f"  热词数: {data['count']}")
            print(f"  前10个: {', '.join(data['hotwords'][:10])}")

            return True
        else:
            print(f"\n❌ 请求失败: HTTP {response.status_code}")
            print(f"   响应: {response.text}")
            return False

    except Exception as e:
        print(f"\n❌ 请求失败: {e}")
        return False


def test_check_duplicate():
    """测试检查重复"""
    print("\n" + "=" * 60)
    print("测试 4: GET /scene-hotwords/check-duplicate/GitHub")
    print("=" * 60)

    try:
        response = requests.get(f"{BASE_URL}/scene-hotwords/check-duplicate/GitHub", timeout=5)
        if response.status_code == 200:
            data = response.json()
            print(f"\n✓ 检查成功")
            print(f"  热词: {data['word']}")
            print(f"  是否存在: {data['exists']}")
            print(f"  重复位置: {list(data['duplicates'].keys())}")

            return True
        else:
            print(f"\n❌ 请求失败: HTTP {response.status_code}")
            print(f"   响应: {response.text}")
            return False

    except Exception as e:
        print(f"\n❌ 请求失败: {e}")
        return False


def test_add_hotword():
    """测试添加热词"""
    print("\n" + "=" * 60)
    print("测试 5: POST /scene-hotwords/tech/add")
    print("=" * 60)

    try:
        # 添加新热词
        response = requests.post(
            f"{BASE_URL}/scene-hotwords/tech/add",
            params={"word": "Claude", "force": False},
            timeout=5
        )

        if response.status_code == 200:
            data = response.json()
            print(f"\n✓ 添加成功")
            print(f"  消息: {data['message']}")
            print(f"  场景: {data['scene']}")
            print(f"  热词: {data['word']}")
            print(f"  总数: {data['total_count']}")
            return True
        else:
            print(f"\n❌ 请求失败: HTTP {response.status_code}")
            print(f"   响应: {response.text}")
            return False

    except Exception as e:
        print(f"\n❌ 请求失败: {e}")
        return False


def test_delete_hotword():
    """测试删除热词"""
    print("\n" + "=" * 60)
    print("测试 6: DELETE /scene-hotwords/tech/Claude")
    print("=" * 60)

    try:
        response = requests.delete(f"{BASE_URL}/scene-hotwords/tech/Claude", timeout=5)

        if response.status_code == 200:
            data = response.json()
            print(f"\n✓ 删除成功")
            print(f"  消息: {data['message']}")
            print(f"  场景: {data['scene']}")
            print(f"  热词: {data['word']}")
            print(f"  剩余: {data['total_count']}")
            return True
        else:
            print(f"\n❌ 请求失败: HTTP {response.status_code}")
            print(f"   响应: {response.text}")
            return False

    except Exception as e:
        print(f"\n❌ 请求失败: {e}")
        return False


def test_get_stats():
    """测试获取统计信息"""
    print("\n" + "=" * 60)
    print("测试 7: GET /scene-hotwords/stats")
    print("=" * 60)

    try:
        response = requests.get(f"{BASE_URL}/scene-hotwords/stats", timeout=5)
        if response.status_code == 200:
            data = response.json()
            print(f"\n✓ 成功获取统计信息")
            print(f"  总场景数: {data['total_scenes']}")
            print(f"  总热词数: {data['total_hotwords']}")
            print(f"\n  各场景热词数:")

            for scene, count in data['stats'].items():
                print(f"    - {scene:12s}: {count:3d}")

            return True
        else:
            print(f"\n❌ 请求失败: HTTP {response.status_code}")
            print(f"   响应: {response.text}")
            return False

    except Exception as e:
        print(f"\n❌ 请求失败: {e}")
        return False


def main():
    """主测试函数"""
    print("\n" + "=" * 60)
    print("场景热词管理 API 接口测试")
    print("=" * 60)

    # 检查服务是否运行
    try:
        response = requests.get(f"{BASE_URL}/health", timeout=5)
        if response.status_code != 200:
            print(f"\n❌ ASR 服务未运行或异常")
            print(f"   请确保服务运行在 {BASE_URL}")
            return 1
    except Exception as e:
        print(f"\n❌ 无法连接到 ASR 服务: {e}")
        print(f"   请确保服务运行在 {BASE_URL}")
        return 1

    results = []

    # 执行测试
    results.append(("获取所有场景热词", test_get_all_hotwords()))
    results.append(("获取场景列表", test_get_scenes()))
    results.append(("获取指定场景热词", test_get_scene_hotwords()))
    results.append(("检查热词重复", test_check_duplicate()))
    results.append(("添加热词", test_add_hotword()))
    results.append(("删除热词", test_delete_hotword()))
    results.append(("获取统计信息", test_get_stats()))

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
        print("\n✓ 所有接口测试通过！")
        print("\nAPI 接口列表:")
        print("  GET    /scene-hotwords/list           - 获取所有场景热词")
        print("  GET    /scene-hotwords/scenes         - 获取所有场景")
        print("  GET    /scene-hotwords/{scene}        - 获取指定场景热词")
        print("  POST   /scene-hotwords/{scene}/add    - 添加热词")
        print("  DELETE /scene-hotwords/{scene}/{word} - 删除热词")
        print("  GET    /scene-hotwords/check-duplicate/{word} - 检查重复")
        print("  GET    /scene-hotwords/stats          - 获取统计信息")
        return 0
    else:
        print(f"\n❌ 有 {total - passed} 个测试失败")
        return 1


if __name__ == "__main__":
    sys.exit(main())
