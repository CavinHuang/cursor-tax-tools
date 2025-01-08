#!/bin/bash

# 安装打包工具
py310/bin/pip install pyinstaller pillow

# 创建模板文件
py310/bin/python create_template.py

# 创建图标
py310/bin/python create_icon.py

# 打包应用
py310/bin/pyinstaller --clean build_win.spec

echo "打包完成，请查看 dist 目录"
