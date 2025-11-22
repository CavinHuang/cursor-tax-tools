#!/usr/bin/env python3
"""
关税数据处理工具启动器
提供多个GUI选项供用户选择
"""

import tkinter as tk
from tkinter import ttk, messagebox
import sys
import os

def launch_original_gui():
    """启动原始GUI"""
    try:
        from batch_gui import BatchProcessFrame
        root = tk.Toplevel()
        root.title("关税数据处理工具 - 原始版")
        root.geometry("700x500")

        app = BatchProcessFrame(root)
        app.pack(fill='both', expand=True)
        root.mainloop()
    except ImportError as e:
        messagebox.showerror("错误", f"无法启动原始GUI: {str(e)}")

def launch_enhanced_gui():
    """启动增强版GUI"""
    try:
        from enhanced_gui import EnhancedBatchProcessFrame
        root = tk.Toplevel()
        root.title("关税数据处理工具 - 增强版")
        root.geometry("900x700")

        app = EnhancedBatchProcessFrame(root)
        app.pack(fill='both', expand=True)
        root.mainloop()
    except ImportError as e:
        messagebox.showerror("错误", f"无法启动增强版GUI: {str(e)}")

def main():
    root = tk.Tk()
    root.title("关税数据处理工具 - 启动器")
    root.geometry("400x300")
    root.resizable(False, False)

    # 居中窗口
    root.update_idletasks()
    width = root.winfo_width()
    height = root.winfo_height()
    x = (root.winfo_screenwidth() // 2) - (width // 2)
    y = (root.winfo_screenheight() // 2) - (height // 2)
    root.geometry(f'{width}x{height}+{x}+{y}')

    # 主框架
    main_frame = ttk.Frame(root, padding="20")
    main_frame.pack(fill='both', expand=True)

    # 标题
    title_label = ttk.Label(
        main_frame,
        text="🏷️ 关税数据处理工具",
        font=('Arial', 16, 'bold')
    )
    title_label.pack(pady=(0, 20))

    # 版本选择
    version_frame = ttk.LabelFrame(main_frame, text="选择界面版本", padding="15")
    version_frame.pack(fill='both', expand=True)

    # 原始版本按钮
    original_btn = ttk.Button(
        version_frame,
        text="📄 原始版本\n(本地数据处理)",
        command=launch_original_gui,
        width=30
    )
    original_btn.pack(pady=10)

    # 增强版本按钮
    enhanced_btn = ttk.Button(
        version_frame,
        text="🚀 增强版本\n(本地+远程数据更新)",
        command=launch_enhanced_gui,
        width=30
    )
    enhanced_btn.pack(pady=10)

    # 说明文字
    info_frame = ttk.LabelFrame(main_frame, text="功能说明", padding="10")
    info_frame.pack(fill='x', pady=(20, 0))

    info_text = """
• 原始版本：专注于本地Excel文件的处理和查询
• 增强版本：包含本地处理 + 远程数据自动更新功能
• 建议使用增强版本，可以获得最新的关税数据
    """

    info_label = ttk.Label(info_frame, text=info_text.strip(), justify='left')
    info_label.pack()

    # 底部按钮
    bottom_frame = ttk.Frame(main_frame)
    bottom_frame.pack(fill='x', pady=(10, 0))

    # 退出按钮
    exit_btn = ttk.Button(bottom_frame, text="退出", command=root.destroy)
    exit_btn.pack(side='right')

    # 关于按钮
    def show_about():
        about_text = """
关税数据处理工具 v2.0

功能特性:
• 支持Excel文件批量处理
• 智能关税编码匹配
• 远程数据自动更新
• 数据质量验证
• 详细的处理报告

作者: 猫娘 幽浮喵 (浮浮酱)
技术栈: Python + Tkinter + SQLite

🐾 专业、严谨、可爱！
        """
        messagebox.showinfo("关于", about_text.strip())

    about_btn = ttk.Button(bottom_frame, text="关于", command=show_about)
    about_btn.pack(side='left')

    # 检查依赖
    def check_dependencies():
        missing_deps = []

        try:
            import tkinter
        except ImportError:
            missing_deps.append("tkinter")

        try:
            import pandas
        except ImportError:
            missing_deps.append("pandas")

        try:
            import requests
        except ImportError:
            missing_deps.append("requests")

        if missing_deps:
            messagebox.showwarning(
                "依赖检查",
                f"缺少以下依赖包: {', '.join(missing_deps)}\n\n"
                "请运行: pip install -r requirements.txt"
            )
        else:
            messagebox.showinfo("依赖检查", "✅ 所有依赖包都已安装")

    # 启动时检查依赖
    root.after(100, check_dependencies)

    root.mainloop()

if __name__ == "__main__":
    main()