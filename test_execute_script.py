#!/usr/bin/env python3
"""
测试execute_scraping.py脚本
"""

import os
import sys
import subprocess
import json

def test_execute_script():
    """测试execute_scraping.py脚本"""
    print("Testing execute_scraping.py...")

    # 设置环境变量
    env = os.environ.copy()
    env['USE_OPTIMIZED'] = 'false'  # 先测试原版
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
            timeout=30
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

if __name__ == "__main__":
    success = test_execute_script()
    if success:
        print("Test PASSED")
    else:
        print("Test FAILED")
    sys.exit(0 if success else 1)