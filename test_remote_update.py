#!/usr/bin/env python3
"""
远程更新功能测试脚本
"""

import sys
import os

def test_imports():
    """测试所有必要的导入"""
    print("🔍 测试导入...")

    try:
        from smart_update_client import SmartUpdateChecker
        print("✅ SmartUpdateChecker 导入成功")
    except Exception as e:
        print(f"❌ SmartUpdateChecker 导入失败: {e}")
        return False

    try:
        from tariff_gui import TariffGUI
        print("✅ TariffGUI 导入成功")
    except Exception as e:
        print(f"❌ TariffGUI 导入失败: {e}")
        return False

    return True

def test_methods():
    """测试新增的方法"""
    print("\n🔍 测试新增方法...")

    try:
        from tariff_gui import TariffGUI

        # 检查远程更新相关方法
        remote_methods = [
            'setup_remote_update',
            'check_remote_update',
            'force_remote_update',
            'refresh_remote_status',
            'browse_remote_database',
            'add_remote_log',
            'set_remote_ui_state'
        ]

        for method in remote_methods:
            if hasattr(TariffGUI, method):
                print(f"✅ {method} 方法存在")
            else:
                print(f"❌ {method} 方法缺失")
                return False

        return True
    except Exception as e:
        print(f"❌ 方法检查失败: {e}")
        return False

def test_smart_update_client():
    """测试智能更新客户端"""
    print("\n🔍 测试SmartUpdateChecker...")

    try:
        from smart_update_client import SmartUpdateChecker

        # 创建测试实例
        checker = SmartUpdateChecker(
            "https://github.com/LiaoFeng/cursor-tax-tools/releases/download/latest-data/metadata.json",
            "test_tariffs.db"
        )

        print("✅ SmartUpdateChecker 实例创建成功")

        # 测试基本方法
        local_metadata = checker.load_local_metadata()
        print(f"✅ load_local_metadata 执行成功: {local_metadata is not None}")

        db_info = checker.get_local_db_info()
        print(f"✅ get_local_db_info 执行成功: {db_info is not None}")

        return True
    except Exception as e:
        print(f"❌ SmartUpdateChecker 测试失败: {e}")
        return False

def main():
    """主函数"""
    print("🧪 远程更新功能测试")
    print("=" * 50)

    all_passed = True

    # 测试导入
    if not test_imports():
        all_passed = False

    # 测试方法
    if not test_methods():
        all_passed = False

    # 测试智能更新客户端
    if not test_smart_update_client():
        all_passed = False

    print("\n" + "=" * 50)
    if all_passed:
        print("🎉 所有测试通过！远程更新功能已成功集成到GUI中！")
        print("\n📋 使用方法:")
        print("1. 运行: python tariff_gui.py")
        print("2. 点击 '远程数据更新' 标签页")
        print("3. 使用 '🔍 检查更新' 或 '🔄 强制更新' 功能")
        return 0
    else:
        print("❌ 部分测试失败，请检查错误信息")
        return 1

if __name__ == "__main__":
    sys.exit(main())