import tkinter as tk
from tkinter import ttk
import logging
from tariff_api import TariffAPI
import queue
import threading
from batch_gui import BatchProcessFrame
import asyncio
import tkinter.messagebox as messagebox
from update_gui import UpdateFrame

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

class TariffGUI:
    def __init__(self):
        # 添加必要的导入
        import asyncio

        self.root = tk.Tk()
        self.root.title("关税查询工具")
        self.setup_ui()
        self.setup_api()
        self.setup_queue()

    def setup_ui(self):
        """设置UI界面"""
        # 创建工具栏框架
        toolbar_frame = ttk.Frame(self.root)
        toolbar_frame.pack(fill=tk.X, padx=5, pady=2)

        # 添加更新按钮
        self.update_btn = ttk.Button(
            toolbar_frame,
            text="更新数据",
            command=self.start_update
        )
        self.update_btn.pack(side=tk.LEFT, padx=5)

        # 添加更新进度条
        self.update_progress_var = tk.DoubleVar()
        self.update_progress = ttk.Progressbar(
            toolbar_frame,
            variable=self.update_progress_var,
            mode='determinate',
            length=200
        )
        self.update_progress.pack(side=tk.LEFT, padx=5)
        self.update_progress.pack_forget()  # 初始时隐藏进度条

        # 创建标签页
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # 单个查询标签页
        self.single_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.single_frame, text="单个查询")
        self.setup_single_search()

        # 批量查询标签页
        self.batch_frame = BatchProcessFrame(self.notebook)
        self.notebook.add(self.batch_frame, text="批量查询")

        # 数据更新标签页
        self.update_frame = UpdateFrame(self.notebook)
        self.notebook.add(self.update_frame, text="数据更新")

    def setup_single_search(self):
        """设置单个查询界面"""
        # 搜索框架
        search_frame = ttk.LabelFrame(self.single_frame, text="搜索")
        search_frame.pack(fill=tk.X, padx=5, pady=5)

        # 搜索输入
        self.search_var = tk.StringVar()
        search_entry = ttk.Entry(
            search_frame,
            textvariable=self.search_var,
            width=40
        )
        search_entry.pack(side=tk.LEFT, padx=5, pady=5)
        search_entry.bind('<Return>', lambda e: self.search())

        # 模糊匹配选项
        self.fuzzy_var = tk.BooleanVar(value=True)
        fuzzy_check = ttk.Checkbutton(
            search_frame,
            text="模糊匹配",
            variable=self.fuzzy_var,
            command=self.on_fuzzy_changed
        )
        fuzzy_check.pack(side=tk.LEFT, padx=5, pady=5)

        # 搜索按钮
        self.search_btn = ttk.Button(
            search_frame,
            text="搜索",
            command=self.search
        )
        self.search_btn.pack(side=tk.LEFT, padx=5, pady=5)

        # 结果显示
        result_frame = ttk.LabelFrame(self.single_frame, text="搜索结果")
        result_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # 创建表格
        columns = ('编码', '税率', '网址', '北爱尔兰税率', '北爱尔兰网址', '相似度')
        self.result_tree = ttk.Treeview(
            result_frame,
            columns=columns,
            show='headings',
            height=10
        )

        # 设置列
        column_widths = {
            '编码': 120,
            '税率': 100,
            '网址': 150,
            '北爱尔兰税率': 100,
            '北爱尔兰网址': 150,
            '相似度': 80
        }

        for col in columns:
            self.result_tree.heading(col, text=col)
            self.result_tree.column(col, width=column_widths[col])

        # 添加滚动条
        scrollbar = ttk.Scrollbar(
            result_frame,
            orient=tk.VERTICAL,
            command=self.result_tree.yview
        )
        self.result_tree.configure(yscrollcommand=scrollbar.set)

        # 布局
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.result_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # 绑定双击事件
        self.result_tree.bind('<Double-1>', self.on_result_double_click)

        # 创建右键菜单
        self.context_menu = tk.Menu(self.root, tearoff=0)
        self.context_menu.add_command(label="复制英国税率", command=self.copy_uk_rate)
        self.context_menu.add_command(label="打开英国税率网址", command=self.open_uk_url)
        self.context_menu.add_separator()
        self.context_menu.add_command(label="复制北爱尔兰税率", command=self.copy_ni_rate)
        self.context_menu.add_command(label="打开北爱尔兰税率网址", command=self.open_ni_url)

        # 绑定右键事件（同时支持 Windows 和 macOS）
        self.result_tree.bind('<Button-2>', self.show_context_menu)  # macOS 右键
        self.result_tree.bind('<Button-3>', self.show_context_menu)  # Windows 右键
        if self.root.tk.call('tk', 'windowingsystem') == 'aqua':  # macOS
            self.result_tree.bind('<Control-1>', self.show_context_menu)  # macOS Control+左键

        # 状态栏
        self.status_var = tk.StringVar(value="就绪")
        status_bar = ttk.Label(
            self.single_frame,
            textvariable=self.status_var,
            relief=tk.SUNKEN,
            anchor=tk.W
        )
        status_bar.pack(fill=tk.X, padx=5, pady=2)

    def setup_api(self):
        """设置API"""
        self.api = TariffAPI()

    def setup_queue(self):
        """设置消息队列和更新任务"""
        self.queue = queue.Queue()
        self.root.after(100, self.process_queue)

    def process_queue(self):
        """处理消息队列"""
        try:
            while True:
                func, args, kwargs = self.queue.get_nowait()
                func(*args, **kwargs)
                self.queue.task_done()
        except queue.Empty:
            pass
        finally:
            self.root.after(100, self.process_queue)

    def search(self):
        """执行搜索"""
        query = self.search_var.get().strip()
        if not query:
            return

        # 禁用搜索按钮
        self.search_btn.configure(state='disabled')
        self.status_var.set("搜索中...")

        # 清空现有结果
        for item in self.result_tree.get_children():
            self.result_tree.delete(item)

        # 在后台线程中执行搜索
        thread = threading.Thread(
            target=self._search,
            args=(query,),
            daemon=True
        )
        thread.start()

    def _search(self, query: str):
        """在后台线程中执行搜索"""
        try:
            if self.fuzzy_var.get():
                results = self.api.fuzzy_search(query)
                if results:
                    # 在主线程中更新UI
                    self.queue.put((self._update_results, (results,), {}))
                else:
                    self.queue.put((
                        self.status_var.set,
                        ("未找到匹配结果",),
                        {}
                    ))
            else:
                result = self.api.exact_search(query)
                if result:
                    # 在主线程中更新UI
                    self.queue.put((self._update_results, ([result],), {}))
                else:
                    self.queue.put((
                        self.status_var.set,
                        ("未找到匹配结果",),
                        {}
                    ))
        except Exception as e:
            logger.error(f"搜索失败: {str(e)}")
            self.queue.put((
                self.status_var.set,
                (f"搜索失败: {str(e)}",),
                {}
            ))
        finally:
            # 恢复搜索按钮
            self.queue.put((
                self.search_btn.configure,
                (),
                {'state': 'normal'}
            ))

    def _update_results(self, results: list):
        """更新搜索结果显示"""
        # 清空现有结果
        for item in self.result_tree.get_children():
            self.result_tree.delete(item)

        # 添加新结果
        for result in results:
            similarity = result.get('similarity', 1.0)
            self.result_tree.insert(
                '',
                'end',
                values=(
                    result['code'],
                    result.get('rate', ''),
                    result.get('url', ''),
                    result.get('north_ireland_rate', ''),
                    result.get('north_ireland_url', ''),
                    f"{similarity*100:.1f}%"
                )
            )

        self.status_var.set(f"找到 {len(results)} 条结果")

    def on_result_double_click(self, event):
        """处理结果双击事件"""
        # 获取点击的项目和列
        item = self.result_tree.selection()[0]
        column = self.result_tree.identify_column(event.x)
        col_num = int(column.replace('#', ''))

        # 获取值
        values = self.result_tree.item(item)['values']

        # 根据列号确定URL
        url = None
        if col_num == 3:  # 英国网址列
            url = values[2]  # 因为values是从0开始索引
        elif col_num == 5:  # 北爱尔兰网址列
            url = values[4]

        # 如果点击的是URL列且URL不为空，则打开浏览器
        if url and url.strip():
            import webbrowser
            webbrowser.open(url)

    def on_fuzzy_changed(self):
        """处理模糊匹配状态改变"""
        is_fuzzy = self.fuzzy_var.get()
        logger.debug(f"模糊匹配状态改变: {is_fuzzy}")

    def show_context_menu(self, event):
        """显示右键菜单"""
        # 获取点击的项目
        item = self.result_tree.identify_row(event.y)
        if item:
            # 选中该项
            self.result_tree.selection_set(item)
            # 显示菜单
            try:
                self.context_menu.tk_popup(event.x_root, event.y_root)
            finally:
                self.context_menu.grab_release()  # 释放菜单的事件捕获

    def copy_to_clipboard(self, text):
        """复制文本到剪贴板"""
        self.root.clipboard_clear()
        self.root.clipboard_append(text)
        self.status_var.set("已复制到剪贴板")

    def copy_uk_rate(self):
        """复制英国税率"""
        item = self.result_tree.selection()[0]
        values = self.result_tree.item(item)['values']
        rate = values[1]  # 英国税率在第2列
        if rate:
            self.copy_to_clipboard(rate)

    def copy_ni_rate(self):
        """复制北爱尔兰税率"""
        item = self.result_tree.selection()[0]
        values = self.result_tree.item(item)['values']
        rate = values[3]  # 北爱尔兰税率在第4列
        if rate:
            self.copy_to_clipboard(rate)

    def open_uk_url(self):
        """打开英国税率网址"""
        item = self.result_tree.selection()[0]
        values = self.result_tree.item(item)['values']
        url = values[2]  # 英国网址在第3列
        if url and url.strip():
            import webbrowser
            webbrowser.open(url)

    def open_ni_url(self):
        """打开北爱尔兰税率网址"""
        item = self.result_tree.selection()[0]
        values = self.result_tree.item(item)['values']
        url = values[4]  # 北爱尔兰网址在第5列
        if url and url.strip():
            import webbrowser
            webbrowser.open(url)

    def start_update(self):
        """开始更新数据"""
        # 禁用更新按钮
        self.update_btn.configure(state='disabled')
        self.status_var.set("正在更新数据...")
        self.update_progress.pack(side=tk.LEFT, padx=5)  # 显示进度条
        self.update_progress_var.set(0)

        # 在后台线程中执行更新
        thread = threading.Thread(
            target=self._update_data,
            daemon=True
        )
        thread.start()

    def _update_data(self):
        """在后台线程中执行数据更新"""
        try:
            from update_tariffs import TariffScraper
            scraper = TariffScraper()

            # 设置进度回调
            def update_progress(progress):
                self.queue.put((
                    self.update_progress_var.set,
                    (progress * 100,),
                    {}
                ))
            scraper.set_progress_callback(update_progress)

            # 创建异步事件循环
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            # 执行更新
            success = loop.run_until_complete(scraper.scrape_tariffs())
            loop.close()

            if success:
                # 更新完成
                self.queue.put((self._update_complete, (), {}))
            else:
                raise Exception("更新失败")

        except Exception as e:
            logger.error(f"更新数据失败: {str(e)}")
            self.queue.put((
                self.status_var.set,
                (f"更新失败: {str(e)}",),
                {}
            ))
        finally:
            # 恢复按钮状态和隐藏进度条
            self.queue.put((self._reset_update_ui, (), {}))

    def _update_complete(self):
        """更新完成的处理"""
        self.status_var.set("数据更新完成")
        messagebox.showinfo("成功", "数据更新完成")

    def _reset_update_ui(self):
        """重置更新UI状态"""
        self.update_btn.configure(state='normal')
        self.update_progress.pack_forget()
        self.update_progress_var.set(0)

    def run(self):
        """运行GUI"""
        self.root.mainloop()

if __name__ == "__main__":
    gui = TariffGUI()
    gui.run()