import tkinter as tk
from tkinter import ttk
import logging
from .frames.update_frame import UpdateFrame
from .frames.batch_frame import BatchFrame

logger = logging.getLogger(__name__)

class TariffGUI:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("关税查询工具")
        self.setup_ui()

    def setup_ui(self):
        """设置UI界面"""
        # 创建标签页
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # 更新数据标签页
        self.update_frame = UpdateFrame(self.notebook)
        self.notebook.add(self.update_frame, text="数据更新")

        # 批量查询标签页
        self.batch_frame = BatchFrame(self.notebook)
        self.notebook.add(self.batch_frame, text="批量查询")

        # 设置窗口大小和位置
        self.root.geometry("800x600")
        self.root.minsize(800, 600)

        # 设置窗口图标
        try:
            self.root.iconbitmap("assets/icon.ico")
        except Exception:
            logger.warning("无法加载窗口图标")

    def run(self):
        """运行程序"""
        self.root.mainloop()

    # ... 其他代码 ...