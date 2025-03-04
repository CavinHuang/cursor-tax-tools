#!/usr/bin/env python
import os
import sys

# 将项目根目录添加到 Python 路径
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from src.gui.main_window import TariffGUI

def main():
    gui = TariffGUI()
    gui.run()

if __name__ == "__main__":
    main()