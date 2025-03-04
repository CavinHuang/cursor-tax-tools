#!/usr/bin/env python
import os
import sys
import logging

# 将项目根目录添加到 Python 路径
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from src.utils.dependency_check import check_dependencies
from src.utils.path_utils import ensure_app_directories
from src.gui.main_window import TariffGUI

def main():
    try:
        # 检查依赖
        check_dependencies()

        # 确保目录结构存在
        ensure_app_directories()

        # 创建并运行GUI
        gui = TariffGUI()
        gui.run()
    except ImportError as e:
        print(f"错误: {str(e)}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"程序启动失败: {str(e)}", file=sys.stderr)
        logging.exception("程序启动失败")
        sys.exit(1)

if __name__ == "__main__":
    main()