#!/usr/bin/env python
import os
import sys

# 将项目根目录添加到 Python 路径
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from src.gui.main_window import TariffGUI
from src.utils.path_utils import ensure_app_directories

def main():
    # 确保目录结构存在
    ensure_app_directories()

    # 创建并运行GUI
    gui = TariffGUI()
    gui.run()

if __name__ == "__main__":
    main()