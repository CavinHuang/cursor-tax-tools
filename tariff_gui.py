import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
from tariff_api import TariffAPI
from scraper import TariffScraper
from web_search import WebSearchUI, WebSearchAPI
import asyncio
import logging
import threading
import queue
import json
import requests
import time
import sys

# 配置日志
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

# 创建控制台处理器
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setLevel(logging.DEBUG)

# 设置日志格式
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
console_handler.setFormatter(formatter)

# 添加处理器到logger
logger.addHandler(console_handler)

class TariffGUI:
    def __init__(self):
        self.window = tk.Tk()
        self.window.title("关税查询系统")
        self.window.geometry("800x600")

        # 初始化API和结果队列
        self.api = TariffAPI()
        self.result_queue = queue.Queue()
        # self.web_api = WebSearchAPI()  # 暂时注释掉

        # 创建状态栏
        self.status_var = tk.StringVar()
        self.status_bar = ttk.Label(
            self.window,
            textvariable=self.status_var,
            relief=tk.SUNKEN,
            anchor=tk.W
        )

        # 检查数据库状态并初始化UI组件
        self.need_init = self._need_initialization()
        self.setup_ui()
        self._setup_tree_events()
        self._layout_widgets()

        # 根据数据库状态设置UI
        if self.need_init:
            # 数据库为空，禁用查询按钮
            self.search_btn.config(state=tk.DISABLED)
            self.status_var.set("数据库为空，请点击初始化按钮")
        else:
            # 数据库已有数据，启用查询按钮
            self.search_btn.config(state=tk.NORMAL)
            self.status_var.set("就绪")

        # 启动队列检查
        self._check_queue()

    def _need_initialization(self) -> bool:
        """检查数据库是否需要初始化"""
        try:
            # 直接检查数据库中的记录数
            count = self.api.get_record_count()
            return count == 0
        except Exception as e:
            logger.error(f"检查数据库失败: {str(e)}")
            return True  # 出错时假定需要初始化

    def _init_database(self):
        """初始化数据库"""
        self.status_var.set("正在初始化数据...")
        self.init_btn.config(state=tk.DISABLED)
        self.search_btn.config(state=tk.DISABLED)

        # 在新线程中执行初始化
        thread = threading.Thread(target=self._do_init)
        thread.daemon = True
        thread.start()

    def _do_init(self):
        """执行数据初始化"""
        try:
            scraper = TariffScraper()
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            tariffs = loop.run_until_complete(scraper.scrape_tariffs())
            loop.close()

            # 保存数据
            scraper.save_to_db(tariffs)

            self.result_queue.put(("init_success", len(tariffs)))
        except Exception as e:
            logger.error(f"初始化数据失败: {str(e)}")
            self.result_queue.put(("init_error", str(e)))

    def setup_ui(self):
        """创建GUI组件"""
        # 创建主框架
        self.main_frame = ttk.Frame(self.window)
        self.main_frame.pack(fill=tk.BOTH, expand=True)

        # 设置本地搜索页面
        self._setup_local_search()

    def _setup_local_search(self):
        """设置本地搜索页面"""
        # 搜索框区域
        self.search_frame = ttk.LabelFrame(self.main_frame, text="搜索", padding="5")
        self.code_var = tk.StringVar()
        self.code_entry = ttk.Entry(
            self.search_frame,
            textvariable=self.code_var,
            width=40
        )

        # 修改模糊匹配复选框
        self.fuzzy_var = tk.BooleanVar(value=True)  # 默认启用模糊匹配
        self.fuzzy_check = ttk.Checkbutton(
            self.search_frame,
            text="模糊匹配",
            variable=self.fuzzy_var,
            command=self._on_fuzzy_changed
        )

        self.search_btn = ttk.Button(
            self.search_frame,
            text="查询",
            command=self._search
        )

        # 只在需要初始化时创建初始化按钮
        if self.need_init:
            self.init_btn = ttk.Button(
                self.search_frame,
                text="初始化数据",
                command=self._init_database
            )

        # 布局搜索框区域
        self.search_frame.pack(fill=tk.X, padx=5, pady=5)
        self.code_entry.pack(side=tk.LEFT, padx=5)
        self.fuzzy_check.pack(side=tk.LEFT, padx=5)
        self.search_btn.pack(side=tk.LEFT, padx=5)
        if self.need_init:
            self.init_btn.pack(side=tk.LEFT, padx=5)

        # 结果显示区域
        self.result_frame = ttk.LabelFrame(self.main_frame, text="查询结果", padding="5")
        self.result_tree = ttk.Treeview(
            self.result_frame,
            columns=("code", "url", "rate", "similarity"),
            show="headings"
        )

        # 设置列
        self.result_tree.heading("code", text="编码")
        self.result_tree.heading("url", text="链接")
        self.result_tree.heading("rate", text="税率")
        self.result_tree.heading("similarity", text="相似度")

        # 调整列宽
        self.result_tree.column("code", width=120)
        self.result_tree.column("url", width=450)
        self.result_tree.column("rate", width=120)
        self.result_tree.column("similarity", width=80)

        # 创建滚动条
        self.scrollbar = ttk.Scrollbar(
            self.result_frame,
            orient="vertical",
            command=self.result_tree.yview
        )
        self.result_tree.configure(yscrollcommand=self.scrollbar.set)

        # 创建右键菜单
        self.context_menu = tk.Menu(self.window, tearoff=0)
        self.context_menu.add_command(label="复制税率", command=self._copy_rate)
        self.context_menu.add_command(label="打开链接", command=self._open_url)

        # 绑定右键菜单到树形视图
        self.result_tree.bind('<Button-3>', self._show_context_menu)  # Windows/Linux
        self.result_tree.bind('<Button-2>', self._show_context_menu)  # macOS

        # 也可以绑定到 Control+Click (macOS)
        self.result_tree.bind('<Control-Button-1>', self._show_context_menu)

        # 创建状态栏
        self.status_var = tk.StringVar()
        self.status_bar = ttk.Label(
            self.window,
            textvariable=self.status_var,
            relief=tk.SUNKEN,
            anchor=tk.W
        )

        # 布局结果显示区域
        self.result_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.result_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

    def _setup_web_search(self):
        """设置官网搜索页面"""
        self.web_search_ui = WebSearchUI(self.web_frame, self.status_var)

    def _on_fuzzy_changed(self):
        """处理模糊匹配状态改变"""
        is_fuzzy = self.fuzzy_var.get()
        logger.debug(f"模糊匹配状态改变: {is_fuzzy}")
        # 可以在这里添加其他逻辑

    def _copy_rate(self):
        """复制选中行的税率"""
        selection = self.result_tree.selection()
        if selection:
            item = selection[0]
            rate = self.result_tree.item(item)['values'][3]
            self.window.clipboard_clear()
            self.window.clipboard_append(rate)
            self.status_var.set(f"已复制税率: {rate}")

    def _open_url(self):
        """打开选中行的链接"""
        selection = self.result_tree.selection()
        if selection:
            item = selection[0]
            url = self.result_tree.item(item)['values'][1]
            import webbrowser
            webbrowser.open(url)
            self.status_var.set("正在打开链接...")

    def _show_context_menu(self, event):
        """显示右键菜单"""
        # 先获取点击的位置
        item = self.result_tree.identify("item", event.x, event.y)
        if not item:
            return

        # 选中当前行
        self.result_tree.selection_set(item)

        try:
            # 显示右键菜单
            self.context_menu.tk_popup(event.x_root, event.y_root)
        finally:
            # 释放菜单
            self.context_menu.grab_release()

    def _setup_tree_events(self):
        """设置树形视图的事件绑定"""
        # 移除这个方法，因为我们已经在 setup_ui 中绑定了事件
        pass

    def run(self):
        """运行GUI"""
        self.window.mainloop()

    def _search(self):
        """执行搜索"""
        code = self.code_var.get().strip()
        if not code:
            messagebox.showwarning("警告", "请输入海关编码")
            return

        # 禁用搜索按钮
        self.search_btn.config(state=tk.DISABLED)
        self.status_var.set("正在搜索...")

        # 清空现有结果
        for item in self.result_tree.get_children():
            self.result_tree.delete(item)

        # 在新线程中执行搜索
        thread = threading.Thread(target=self._do_search, args=(code,))
        thread.daemon = True
        thread.start()

    def _do_search(self, code):
        """执行实际的搜索操作"""
        try:
            # 根据模糊匹配状态选择搜索方法
            is_fuzzy = self.fuzzy_var.get()
            if is_fuzzy:
                results = self.api.fuzzy_search(code)
            else:
                result = self.api.exact_search(code)
                results = [result] if result else []

            # 将结果放入队列
            self.result_queue.put(("search_success", results))

        except Exception as e:
            logger.error(f"搜索失败: {str(e)}")
            self.result_queue.put(("search_error", str(e)))

        finally:
            # 恢复搜索按钮状态
            self.window.after(0, lambda: self.search_btn.config(state=tk.NORMAL))

    def _display_results(self, results):
        """显示搜索结果"""
        if not results:
            self.status_var.set("未找到匹配的记录")
            return

        if isinstance(results, dict):
            # 精确匹配结果
            self.result_tree.insert(
                "",
                "end",
                values=(
                    results['code'],
                    results.get('url', f"https://www.trade-tariff.service.gov.uk/commodities/{results['code']}"),
                    results['rate'],
                    "100%"
                )
            )
        else:
            # 模糊匹配结果
            for result in results:
                self.result_tree.insert(
                    "",
                    "end",
                    values=(
                        result['code'],
                        result.get('url', f"https://www.trade-tariff.service.gov.uk/commodities/{result['code']}"),
                        result['rate'],
                        f"{result['similarity']*100:.1f}%"
                    )
                )

        self.status_var.set("搜索完成")

    def _check_queue(self):
        """检查结果队列"""
        try:
            while True:
                action, data = self.result_queue.get_nowait()

                if action == "search_success":
                    self._display_results(data)
                elif action == "search_error":
                    self.status_var.set(f"搜索失败: {data}")
                elif action == "init_success":
                    self.status_var.set(f"初始化完成，共导入 {data} 条记录")
                    self.init_btn.config(state=tk.DISABLED)
                    self.search_btn.config(state=tk.NORMAL)
                elif action == "init_error":
                    self.status_var.set(f"初始化失败: {data}")
                    self.init_btn.config(state=tk.NORMAL)
                    self.search_btn.config(state=tk.DISABLED)

        except queue.Empty:
            pass

        # 每100ms检查一次队列
        self.window.after(100, self._check_queue)

    def _layout_widgets(self):
        """布局GUI组件"""
        # 主框架占据整个窗口
        self.main_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # 状态栏
        self.status_bar.pack(side=tk.BOTTOM, fill=tk.X)

def main():
    app = TariffGUI()
    app.run()

if __name__ == "__main__":
    main()