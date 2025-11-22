#!/usr/bin/env python3
"""
简单测试原版爬虫导入
"""

import os
import sys

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'scripts', 'actions'))

def test_original_scraper():
    print("Testing original scraper...")

    try:
        from scraper import BatchUpdateManager
        print("✓ BatchUpdateManager imported successfully")

        # 测试创建实例
        manager = BatchUpdateManager()
        print("✓ BatchUpdateManager instance created successfully")

        return True

    except Exception as e:
        print(f"✗ Original scraper failed: {e}")
        return False

def test_web_scraper():
    print("Testing web_scraper...")

    try:
        from tools.web_scraper import scrape_urls
        print("✓ scrape_urls imported successfully")
        return True

    except Exception as e:
        print(f"✗ web_scraper failed: {e}")
        return False

def main():
    print("Simple scraper import test")
    print("=" * 30)

    original_ok = test_original_scraper()
    web_ok = test_web_scraper()

    print("=" * 30)
    if original_ok and web_ok:
        print("✓ All scraper imports OK")
        return 0
    else:
        print("✗ Some imports failed")
        return 1

if __name__ == "__main__":
    sys.exit(main())