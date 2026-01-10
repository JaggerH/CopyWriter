#!/usr/bin/env python3
"""
热词管理功能测试脚本

测试内容：
1. check_duplicate() - 重复检测
2. add_hotword() - 添加热词（带防重检测）
3. remove_hotword() - 删除热词
4. list_all_hotwords() - 列出所有热词
"""

import sys
from pathlib import Path

# 添加当前目录到路径
sys.path.insert(0, str(Path(__file__).parent))

from scene_hotwords import (
    check_duplicate,
    add_hotword,
    remove_hotword,
    list_all_hotwords,
    get_scene_hotwords,
)


def test_check_duplicate():
    """测试重复检测功能"""
    print("=" * 60)
    print("测试 1: 重复检测功能 (check_duplicate)")
    print("=" * 60)

    # 测试已存在的热词
    print("\n【1.1】检测已存在的热词")
    result = check_duplicate("GitHub")
    if result:
        print(f"✓ 检测到 'GitHub' 存在于: {list(result.keys())}")
    else:
        print(f"❌ 'GitHub' 应该存在但未检测到")
        return False

    # 测试不存在的热词
    print("\n【1.2】检测不存在的热词")
    result = check_duplicate("这是一个新热词")
    if not result:
        print(f"✓ '这是一个新热词' 不存在（正确）")
    else:
        print(f"❌ '这是一个新热词' 不应该存在: {result}")
        return False

    # 测试指定场景检测
    print("\n【1.3】检测指定场景")
    result = check_duplicate("GitHub", scene="tech")
    if result and "tech" in result:
        print(f"✓ 'GitHub' 存在于 tech 场景")
    else:
        print(f"❌ 'GitHub' 应该存在于 tech 场景")
        return False

    return True


def test_add_hotword():
    """测试添加热词功能"""
    print("\n" + "=" * 60)
    print("测试 2: 添加热词功能 (add_hotword)")
    print("=" * 60)

    # 测试添加新热词
    print("\n【2.1】添加新热词到 tech 场景")
    result = add_hotword("OpenAI", "tech")
    if result["success"]:
        print(f"✓ 成功添加: {result['message']}")
        print(f"  场景热词数: {result['total_count']}")
    else:
        print(f"❌ 添加失败: {result['message']}")
        return False

    # 测试重复添加（应该失败）
    print("\n【2.2】尝试重复添加相同热词（应该失败）")
    result = add_hotword("OpenAI", "tech")
    if not result["success"]:
        print(f"✓ 正确阻止重复: {result['message']}")
    else:
        print(f"❌ 应该阻止重复添加")
        return False

    # 测试添加已存在于其他场景的热词（应该失败）
    print("\n【2.3】尝试添加已存在于其他场景的热词（应该失败）")
    result = add_hotword("GitHub", "medical")
    if not result["success"]:
        print(f"✓ 正确阻止跨场景重复: {result['message']}")
        if "duplicates" in result:
            print(f"  重复位置: {list(result['duplicates'].keys())}")
    else:
        print(f"❌ 应该阻止跨场景重复添加")
        return False

    # 测试强制添加
    print("\n【2.4】强制添加已存在的热词")
    result = add_hotword("GitHub", "medical", force=True)
    if result["success"]:
        print(f"✓ 强制添加成功: {result['message']}")
    else:
        print(f"❌ 强制添加应该成功: {result['message']}")
        return False

    # 测试添加到无效场景（应该失败）
    print("\n【2.5】尝试添加到无效场景（应该失败）")
    result = add_hotword("测试词", "invalid_scene")
    if not result["success"]:
        print(f"✓ 正确拒绝无效场景: {result['message']}")
    else:
        print(f"❌ 应该拒绝无效场景")
        return False

    # 测试添加到 general 场景（应该失败）
    print("\n【2.6】尝试添加到 general 场景（应该失败）")
    result = add_hotword("测试词", "general")
    if not result["success"]:
        print(f"✓ 正确拒绝 general 场景: {result['message']}")
    else:
        print(f"❌ 应该拒绝 general 场景")
        return False

    return True


def test_remove_hotword():
    """测试删除热词功能"""
    print("\n" + "=" * 60)
    print("测试 3: 删除热词功能 (remove_hotword)")
    print("=" * 60)

    # 先添加一个测试热词
    add_hotword("临时测试词", "tech")

    # 测试删除热词
    print("\n【3.1】删除已存在的热词")
    result = remove_hotword("临时测试词", "tech")
    if result["success"]:
        print(f"✓ 成功删除: {result['message']}")
        print(f"  剩余热词数: {result['total_count']}")
    else:
        print(f"❌ 删除失败: {result['message']}")
        return False

    # 测试删除不存在的热词（应该失败）
    print("\n【3.2】尝试删除不存在的热词（应该失败）")
    result = remove_hotword("不存在的词", "tech")
    if not result["success"]:
        print(f"✓ 正确拒绝删除不存在的词: {result['message']}")
    else:
        print(f"❌ 应该拒绝删除不存在的词")
        return False

    # 测试从无效场景删除（应该失败）
    print("\n【3.3】尝试从无效场景删除（应该失败）")
    result = remove_hotword("GitHub", "invalid_scene")
    if not result["success"]:
        print(f"✓ 正确拒绝无效场景: {result['message']}")
    else:
        print(f"❌ 应该拒绝无效场景")
        return False

    return True


def test_list_all_hotwords():
    """测试列出所有热词功能"""
    print("\n" + "=" * 60)
    print("测试 4: 列出所有热词功能 (list_all_hotwords)")
    print("=" * 60)

    result = list_all_hotwords()

    print(f"\n✓ 成功获取所有场景热词")
    for scene, hotwords in result.items():
        print(f"  - {scene:12s}: {len(hotwords):3d} 个热词")

    # 验证返回的是副本（修改不影响原始数据）
    print("\n【4.1】验证返回副本（不影响原始数据）")
    result["tech"].append("测试不应影响原始数据")
    original = get_scene_hotwords("tech")
    if "测试不应影响原始数据" not in original:
        print(f"✓ 返回的是副本，修改不影响原始数据")
        return True
    else:
        print(f"❌ 返回的不是副本，修改影响了原始数据")
        return False


def cleanup():
    """清理测试数据"""
    print("\n" + "=" * 60)
    print("清理测试数据")
    print("=" * 60)

    # 删除测试中添加的热词
    test_words = ["OpenAI", "临时测试词"]
    for word in test_words:
        for scene in ["tech", "medical", "finance", "education", "ecommerce"]:
            result = remove_hotword(word, scene)
            if result["success"]:
                print(f"✓ 清理: {word} from {scene}")


def main():
    """主测试函数"""
    print("\n" + "=" * 60)
    print("热词管理功能 - 完整测试")
    print("=" * 60)

    results = []

    # 执行测试
    results.append(("重复检测", test_check_duplicate()))
    results.append(("添加热词", test_add_hotword()))
    results.append(("删除热词", test_remove_hotword()))
    results.append(("列出热词", test_list_all_hotwords()))

    # 清理
    cleanup()

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
        print("\n✓ 所有测试通过！热词管理功能正常。")
        print("\n功能说明:")
        print("  1. check_duplicate(word, scene) - 检测热词重复")
        print("  2. add_hotword(word, scene, force) - 添加热词（带防重检测）")
        print("  3. remove_hotword(word, scene) - 删除热词")
        print("  4. list_all_hotwords() - 列出所有场景热词")
        return 0
    else:
        print(f"\n❌ 有 {total - passed} 个测试失败，请检查日志。")
        return 1


if __name__ == "__main__":
    sys.exit(main())
