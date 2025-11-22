#!/usr/bin/env python3

import os
import sys

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'scripts', 'actions'))

def main():
    try:
        from scraper import BatchUpdateManager
        print("BatchUpdateManager: OK")
        return 0
    except Exception as e:
        print(f"BatchUpdateManager: FAILED - {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())