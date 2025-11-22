#!/usr/bin/env python3
"""
测试爬虫模块导入
"""

import os
import sys

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'scripts', 'actions'))

def test_imports():
    print("Testing scraper imports...")

    try:
        from scraper_optimized import OptimizedBatchUpdateManager
        print("✓ OptimizedBatchUpdateManager imported successfully")
    except Exception as e:
        print(f"✗ OptimizedBatchUpdateManager import failed: {e}")

    try:
        from scraper import BatchUpdateManager
        print("✓ BatchUpdateManager imported successfully")
    except Exception as e:
        print(f"✗ BatchUpdateManager import failed: {e}")

    try:
        from tariff_db_optimized import OptimizedTariffDB
        print("✓ OptimizedTariffDB imported successfully")
    except Exception as e:
        print(f"✗ OptimizedTariffDB import failed: {e}")

    print("\nTesting execute_scraping script...")

    try:
        from execute_scraping import run_optimized_scraper, run_original_scraper
        print("✓ execute_scraping functions imported successfully")
    except Exception as e:
        print(f"✗ execute_scraping import failed: {e}")

if __name__ == "__main__":
    test_imports()