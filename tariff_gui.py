import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
from tariff_api import TariffAPI
from scraper import TariffScraper
import asyncio
import logging
import threading
import queue
import json

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class TariffGUI:
    def __init__(self):
        self.window = tk.Tk()
        self.window.title("关税查询系统")
        self.window.geometry("800x600")

        # 初始化API和结果队列
        self.api = TariffAPI()
        self.result_queue = queue.Queue()

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
        # 搜索框区域
        self.search_frame = ttk.LabelFrame(self.window, text="搜索", padding="5")
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

        # 结果显示区域
        self.result_frame = ttk.LabelFrame(self.window, text="查询结果", padding="5")
        self.result_tree = ttk.Treeview(
            self.result_frame,
            columns=("code", "url", "description", "rate", "similarity"),
            show="headings"
        )

        # 设置列
        self.result_tree.heading("code", text="编码")
        self.result_tree.heading("url", text="链接")
        self.result_tree.heading("description", text="描述")
        self.result_tree.heading("rate", text="税率")
        self.result_tree.heading("similarity", text="相似度")

        self.result_tree.column("code", width=100)
        self.result_tree.column("url", width=200)
        self.result_tree.column("description", width=300)
        self.result_tree.column("rate", width=100)
        self.result_tree.column("similarity", width=100)

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

    def _layout_widgets(self):
        """布局GUI组件"""
        # 搜索框区域
        self.search_frame.pack(fill=tk.X, padx=5, pady=5)
        self.code_entry.pack(side=tk.LEFT, padx=5)
        self.fuzzy_check.pack(side=tk.LEFT, padx=5)
        self.search_btn.pack(side=tk.LEFT, padx=5)
        if self.need_init:
            self.init_btn.pack(side=tk.LEFT, padx=5)

        # 结果显示区域
        self.result_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.result_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # 状态栏
        self.status_bar.pack(side=tk.BOTTOM, fill=tk.X)

    def _search(self):
        """执行搜索"""
        code = self.code_var.get().strip()
        if not code:
            messagebox.showwarning("警告", "请输入海关编码")
            return

        # 清空现有结果
        for item in self.result_tree.get_children():
            self.result_tree.delete(item)

        # 获取模糊匹配状态
        is_fuzzy = self.fuzzy_var.get()
        logger.debug(f"执行{'模糊' if is_fuzzy else '精确'}查询: {code}")

        self.status_var.set("正在查询...")
        self.search_btn.config(state=tk.DISABLED)  # 使用 config 而不是 state

        # 在新线程中执行查询
        thread = threading.Thread(
            target=self._do_search,
            args=(code, is_fuzzy)
        )
        thread.daemon = True
        thread.start()

        # 定期检查结果
        self.window.after(100, self._check_result)

    def _do_search(self, code: str, fuzzy: bool):
        """在新线程中执行查询"""
        try:
            # 使用数据库API进行查询
            results = self.api.search_tariff(code, fuzzy)
            self.result_queue.put(("success", results))
        except Exception as e:
            logger.error(f"查询失败: {str(e)}")
            self.result_queue.put(("error", str(e)))

    def _check_result(self):
        """检查查询结果"""
        try:
            status, data = self.result_queue.get_nowait()
            if status == "success":
                self._display_results(data)
                self.status_var.set("查询完成")
                self.search_btn.config(state=tk.NORMAL)
            elif status == "init_success":
                # 初始化成功
                self.status_var.set(f"数据初始化完成，共导入 {data} 条记录")
                messagebox.showinfo("成功", f"数据初始化完成，共导入 {data} 条记录")
                # 启用查询按钮，禁用初始化按钮
                self.search_btn.config(state=tk.NORMAL)
                self.init_btn.config(state=tk.DISABLED)
            elif status == "init_error":
                # 初始化失败
                messagebox.showerror("错误", f"初始化数据失败: {data}")
                self.status_var.set("初始化数据失败")
                # 恢复按钮状态
                self.search_btn.config(state=tk.DISABLED)
                self.init_btn.config(state=tk.NORMAL)
            else:
                messagebox.showerror("错误", f"查询失败: {data}")
                self.status_var.set("查询失败")
                self.search_btn.config(state=tk.NORMAL)

        except queue.Empty:
            # 继续检查结果
            self.window.after(100, self._check_result)

    def _display_results(self, results):
        """显示查询结果"""
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
                    results['description'],
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
                        result['description'],
                        result['rate'],
                        f"{result['similarity']*100:.1f}%"
                    )
                )

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

def main():
    app = TariffGUI()
    app.run()

if __name__ == "__main__":
    main()