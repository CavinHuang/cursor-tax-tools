#!/usr/bin/env python3

import os
import sys
import subprocess
import json

def test_optimized_scraper():
    """测试优化版爬虫"""
    print("Testing optimized scraper...")

    # 设置环境变量强制使用优化版
    env = os.environ.copy()
    env['USE_OPTIMIZED'] = 'true'
    env['INPUT_UPDATE_UK'] = 'true'
    env['INPUT_UPDATE_NI'] = 'false'
    env['INPUT_BATCH_SIZE'] = '5'
    env['INPUT_DELAY'] = '0.1'

    try:
        # 执行脚本
        script_path = os.path.join(os.path.dirname(__file__), 'scripts', 'actions', 'execute_scraping.py')
        result = subprocess.run(
            [sys.executable, script_path],
            capture_output=True,
            text=True,
            env=env,
            timeout=60
        )

        print("STDOUT:")
        print(result.stdout)

        if result.stderr:
            print("STDERR:")
            print(result.stderr)

        print(f"Return code: {result.returncode}")

        # 检查是否有结果文件
        if os.path.exists('update_results.json'):
            with open('update_results.json', 'r', encoding='utf-8') as f:
                results = json.load(f)
            print(f"Results: {results}")

        return result.returncode == 0

    except Exception as e:
        print(f"Test failed: {e}")
        return False

def main():
    print("Fixed Scraper Test")
    print("=" * 30)

    success = test_optimized_scraper()

    if success:
        print("Test PASSED")
        print("Optimized scraper should now work in GitHub Actions!")
    else:
        print("Test FAILED")
        print("Will fall back to original scraper if needed")

    return success

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)