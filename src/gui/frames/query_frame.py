import tkinter as tk
from tkinter import ttk
import logging
from ...core.db.tariff_db import TariffDB
import webbrowser
import tkinter.messagebox as messagebox
import asyncio
import threading
from ...core.scraper.uk_scraper import UKScraper
from ...core.scraper.ni_scraper import NIScraper

logger = logging.getLogger(__name__)

class QueryFrame(ttk.Frame):
    def __init__(self, master):
        super().__init__(master)
        self.db = TariffDB()  # 使用默认的数据库路径
        self.setup_ui()
        self.is_updating = False

    def render_buttons(self, item_id):
        """创建操作链接框架"""
        frame = ttk.Frame(self.result_tree)

        # 创建链接样式的标签
        style = ttk.Style()
        style.configure(
            'Link.TLabel',
            foreground='blue',
            font=('微软雅黑', 9, 'underline')
        )
        style.configure(
            'Disabled.Link.TLabel',
            foreground='gray',
            font=('微软雅黑', 9)
        )

        # 更新英国关税链接
        self.uk_link = ttk.Label(
            frame,
            text="更新英国",
            style='Link.TLabel',
            cursor='hand2'
        )
        self.uk_link.pack(side=tk.LEFT, padx=10)

        # 分隔符
        ttk.Label(frame, text="|").pack(side=tk.LEFT)

        # 更新北爱关税链接
        self.ni_link = ttk.Label(
            frame,
            text="更新北爱",
            style='Link.TLabel',
            cursor='hand2'
        )
        self.ni_link.pack(side=tk.LEFT, padx=10)

        # 绑定点击事件
        self.uk_link.bind('<Button-1>', lambda e, iid=item_id: self.on_update_click(e, iid, self.update_uk_rate))
        self.ni_link.bind('<Button-1>', lambda e, iid=item_id: self.on_update_click(e, iid, self.update_ni_rate))

        # 绑定鼠标悬停事件
        def on_enter(event, label):
            if not self.is_updating:
                label.configure(foreground='#0066cc', cursor='hand2')

        def on_leave(event, label):
            if not self.is_updating:
                label.configure(foreground='blue', cursor='hand2')

        self.uk_link.bind('<Enter>', lambda e: on_enter(e, self.uk_link))
        self.uk_link.bind('<Leave>', lambda e: on_leave(e, self.uk_link))
        self.ni_link.bind('<Enter>', lambda e: on_enter(e, self.ni_link))
        self.ni_link.bind('<Leave>', lambda e: on_leave(e, self.ni_link))

        return frame

    def setup_ui(self):
        """设置UI界面"""
        # 搜索框架
        search_frame = ttk.LabelFrame(self, text="关税编码查询")
        search_frame.pack(fill=tk.X, padx=5, pady=5)

        # 搜索输入框
        self.search_var = tk.StringVar()
        search_entry = ttk.Entry(
            search_frame,
            textvariable=self.search_var,
            width=20
        )
        search_entry.pack(side=tk.LEFT, padx=5, pady=5)

        # 搜索模式
        self.search_mode = tk.StringVar(value="exact")
        ttk.Radiobutton(
            search_frame,
            text="精确匹配",
            variable=self.search_mode,
            value="exact"
        ).pack(side=tk.LEFT, padx=5)

        ttk.Radiobutton(
            search_frame,
            text="模糊匹配",
            variable=self.search_mode,
            value="fuzzy"
        ).pack(side=tk.LEFT, padx=5)

        # 搜索按钮
        self.search_btn = ttk.Button(
            search_frame,
            text="查询",
            command=self.search
        )
        self.search_btn.pack(side=tk.LEFT, padx=5, pady=5)

        # 结果框架
        result_frame = ttk.LabelFrame(self, text="查询结果")
        result_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # 结果列表
        columns = ('编码', '英国税率', '北爱税率', '操作')
        self.result_tree = ttk.Treeview(
            result_frame,
            columns=columns,
            show='headings',
            height=10,
            style='Custom.Treeview'  # 使用自定义样式
        )

        # 创建自定义样式
        style = ttk.Style()
        style.configure(
            'Custom.Treeview',
            rowheight=30,  # 设置行高
            font=('微软雅黑', 10),  # 设置字体
            background='#ffffff',  # 设置背景色
        )
        style.configure(
            'Custom.Treeview.Heading',
            font=('微软雅黑', 10, 'bold'),  # 设置表头字体
            padding=5  # 设置表头内边距
        )

        # 设置列
        column_widths = {
            '编码': 150,
            '英国税率': 150,
            '北爱税率': 150,
            '操作': 200
        }

        for col in columns:
            self.result_tree.heading(
                col,
                text=col,
                anchor=tk.CENTER  # 表头文字居中
            )
            self.result_tree.column(
                col,
                width=column_widths[col],
                anchor=tk.CENTER  # 单元格文字居中
            )

        # 设置选中行的样式
        style.map(
            'Custom.Treeview',
            background=[('selected', '#e7f3ff')],  # 选中行的背景色
            foreground=[('selected', '#000000')]   # 选中行的文字颜色
        )

        def fixed_map(option):
            """修复选中行背景色在 Windows 上的显示问题"""
            return [elm for elm in style.map('Treeview', query_opt=option)
                    if elm[:2] != ('!disabled', '!selected')]

        style.map('Treeview',
            foreground=fixed_map('foreground'),
            background=fixed_map('background')
        )

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

        # 添加进度条框架
        self.progress_frame = ttk.Frame(self)
        self.progress_frame.pack(fill=tk.X, padx=5, pady=5)

        # 进度条
        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(
            self.progress_frame,
            mode='determinate',
            variable=self.progress_var
        )

        # 进度标签
        self.progress_label = ttk.Label(self.progress_frame, text="")

        # 状态标签
        self.status_var = tk.StringVar()
        self.status_label = ttk.Label(
            self,
            textvariable=self.status_var
        )
        self.status_label.pack(fill=tk.X, padx=5)

        # 修改右键菜单
        self.context_menu = tk.Menu(self, tearoff=0)
        self.context_menu.add_command(label="复制编码", command=self.copy_code)
        self.context_menu.add_separator()
        self.context_menu.add_command(label="复制英国关税", command=self.copy_uk_rate)
        self.context_menu.add_command(label="复制北爱尔兰关税", command=self.copy_ni_rate)
        self.context_menu.add_separator()
        self.context_menu.add_command(label="打开英国关税网址", command=self.open_uk_url)
        self.context_menu.add_command(label="打开北爱尔兰关税网址", command=self.open_ni_url)
        self.context_menu.add_separator()
        self.context_menu.add_command(label="更新英国关税", command=self.update_uk_rate)
        self.context_menu.add_command(label="更新北爱关税", command=self.update_ni_rate)

        # 绑定右键菜单
        self.result_tree.bind('<Button-3>', self.show_context_menu)  # Windows/Linux右键
        self.result_tree.bind('<Button-2>', self.show_context_menu)  # macOS右键

        # 绑定事件
        self.result_tree.bind('<Double-1>', self.on_double_click)
        search_entry.bind('<Return>', lambda e: self.search())

    def show_progress(self, show: bool = True):
        """显示/隐藏进度条"""
        if show:
            self.progress_bar.pack(fill=tk.X, padx=5, pady=2)
            self.progress_label.pack(fill=tk.X, padx=5)
            self.progress_var.set(0)
        else:
            self.progress_bar.pack_forget()
            self.progress_label.pack_forget()

    def update_progress(self, progress: float, message: str = ""):
        """更新进度条"""
        self.progress_var.set(progress * 100)
        if message:
            self.progress_label.config(text=message)

    def search(self):
        """执行搜索"""
        code = self.search_var.get().strip()
        if not code:
            messagebox.showwarning("警告", "请输入商品编码")
            return

        # 清空结果列表
        for item in self.result_tree.get_children():
            self.result_tree.delete(item)

        try:
            # 从数据库查询
            results = self.db.search_tariffs(
                code,
                fuzzy=(self.search_mode.get() == "fuzzy")
            )

            if not results:
                self.status_var.set("未找到匹配的商品")
                return

            # 显示结果时添加交替行颜色
            for i, result in enumerate(results):
                item_id = self.result_tree.insert('', 'end', values=(
                    str(result['code']).zfill(10),  # 确保显示10位编码
                    result['rate'],
                    result['north_ireland_rate'],
                    ""  # 操作列留空
                ))

                # 设置交替行颜色
                if i % 2:
                    self.result_tree.tag_configure('oddrow', background='#f5f5f5')
                    self.result_tree.item(item_id, tags=('oddrow',))

                # 创建按钮框架
                button_frame = self.render_buttons(item_id)

                # 获取行的位置
                bbox = self.result_tree.bbox(item_id, column='操作')
                if bbox:  # 确保行可见
                    # 放置按钮框架，调整位置使按钮垂直居中
                    button_frame.place(
                        x=bbox[0] + 2,
                        y=bbox[1] + (bbox[3] - 26) // 2,  # 26是按钮的高度
                        width=bbox[2] - 4,
                        height=26
                    )

            self.status_var.set(f"找到 {len(results)} 条结果")

        except Exception as e:
            logger.error(f"查询失败: {str(e)}")
            self.status_var.set(f"查询失败: {str(e)}")

    def on_double_click(self, event):
        """双击处理"""
        if not self.result_tree.selection():
            return

        # 获取点击的列和位置
        column = self.result_tree.identify_column(event.x)
        item = self.result_tree.selection()[0]
        values = self.result_tree.item(item)['values']

        if column == '#4':  # 操作列
            # 获取点击的x坐标
            x = event.x - self.result_tree.winfo_x()
            # 操作列的中点
            mid = self.result_tree.column('操作')['width'] / 2

            if x < mid:
                self.update_uk_rate()  # 点击左半部分更新英国关税
            else:
                self.update_ni_rate()  # 点击右半部分更新北爱关税
        elif column == '#2':  # 英国税率列
            self.open_uk_url()
        elif column == '#3':  # 北爱税率列
            self.open_ni_url()

    def show_context_menu(self, event):
        """显示右键菜单"""
        # 获取点击位置的项
        item = self.result_tree.identify_row(event.y)
        if item:
            # 选中该项
            self.result_tree.selection_set(item)
            # 显示菜单
            try:
                self.context_menu.tk_popup(event.x_root, event.y_root)
            finally:
                self.context_menu.grab_release()

    def copy_code(self):
        """复制商品编码"""
        if selected := self.result_tree.selection():
            code = self.result_tree.item(selected[0])['values'][0]
            self.clipboard_clear()
            self.clipboard_append(code)
            self.status_var.set("已复制商品编码")

    def copy_uk_rate(self):
        """复制英国关税"""
        if selected := self.result_tree.selection():
            rate = self.result_tree.item(selected[0])['values'][1]
            self.clipboard_clear()
            self.clipboard_append(rate)
            self.status_var.set("已复制英国关税")

    def copy_ni_rate(self):
        """复制北爱尔兰关税"""
        if selected := self.result_tree.selection():
            rate = self.result_tree.item(selected[0])['values'][2]
            self.clipboard_clear()
            self.clipboard_append(rate)
            self.status_var.set("已复制北爱尔兰关税")

    def open_uk_url(self):
        """打开英国关税网址"""
        if selected := self.result_tree.selection():
            code = self.result_tree.item(selected[0])['values'][0]
            try:
                url = f"https://www.trade-tariff.service.gov.uk/commodities/{code}"
                webbrowser.open(url)
                self.status_var.set(f"已在浏览器中打开英国关税网址")
            except Exception as e:
                logger.error(f"打开英国关税网址失败: {str(e)}")
                messagebox.showerror("错误", f"打开网址失败: {str(e)}")

    def open_ni_url(self):
        """打开北爱尔兰关税网址"""
        if selected := self.result_tree.selection():
            code = self.result_tree.item(selected[0])['values'][0]
            try:
                url = f"https://www.trade-tariff.service.gov.uk/xi/commodities/{code}"
                webbrowser.open(url)
                self.status_var.set(f"已在浏览器中打开北爱尔兰关税网址")
            except Exception as e:
                logger.error(f"打开北爱尔兰关税网址失败: {str(e)}")
                messagebox.showerror("错误", f"打开网址失败: {str(e)}")

    async def _do_update_uk_rate(self, code: str) -> bool:
        """执行英国关税更新"""
        scraper = UKScraper()
        scraper.set_progress_callback(self.update_progress)
        scraper.set_log_callback(lambda m: self.status_var.set(m))
        return await scraper.update_tariffs([code])

    async def _do_update_ni_rate(self, code: str) -> bool:
        """执行北爱关税更新"""
        scraper = NIScraper()
        scraper.set_progress_callback(self.update_progress)
        scraper.set_log_callback(lambda m: self.status_var.set(m))
        return await scraper.update_tariffs([code])

    def on_update_click(self, event, item_id, update_func):
        """处理更新点击事件"""
        if self.is_updating:
            messagebox.showwarning("警告", "正在更新中，请稍候...")
            return
        update_func(item_id)

    def disable_update_buttons(self):
        """禁用所有更新按钮"""
        for item in self.result_tree.get_children():
            button_frame = self.result_tree.winfo_children()[int(item)]
            for widget in button_frame.winfo_children():
                if isinstance(widget, ttk.Label) and widget['text'] in ["更新英国", "更新北爱"]:
                    widget.configure(style='Disabled.Link.TLabel', cursor='arrow')

    def enable_update_buttons(self):
        """启用所有更新按钮"""
        for item in self.result_tree.get_children():
            button_frame = self.result_tree.winfo_children()[int(item)]
            for widget in button_frame.winfo_children():
                if isinstance(widget, ttk.Label) and widget['text'] in ["更新英国", "更新北爱"]:
                    widget.configure(style='Link.TLabel', cursor='hand2')

    def _update_in_thread(self, code: str, update_func):
        """在后台线程中执行更新"""
        if self.is_updating:
            messagebox.showwarning("警告", "正在更新中，请稍候...")
            return

        self.is_updating = True
        try:
            # 禁用所有更新按钮
            self.after(0, self.disable_update_buttons)
            # 显示进度条
            self.after(0, lambda: self.show_progress(True))

            # 创建新的事件循环
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            # 执行更新
            success = loop.run_until_complete(update_func(code))
            loop.close()

            if success:
                self.after(0, lambda: self.status_var.set("更新成功"))
                # 只更新当前编码的数据
                self.after(0, lambda: self.refresh_item(code))
            else:
                self.after(0, lambda: messagebox.showerror("错误", "更新失败"))
        except Exception as e:
            logger.error(f"更新失败: {str(e)}")
            self.after(0, lambda: messagebox.showerror("错误", f"更新失败: {str(e)}"))
        finally:
            self.is_updating = False
            # 启用所有更新按钮
            self.after(0, self.enable_update_buttons)
            # 隐藏进度条
            self.after(0, lambda: self.show_progress(False))

    def update_uk_rate(self, item_id):
        """更新英国关税"""
        values = self.result_tree.item(item_id)['values']
        if not values:
            return

        code = str(values[0]).zfill(10)  # 确保是10位字符串
        # 在后台线程中执行更新
        thread = threading.Thread(
            target=self._update_in_thread,
            args=(code, self._do_update_uk_rate),
            daemon=True
        )
        thread.start()

    def update_ni_rate(self, item_id):
        """更新北爱关税"""
        values = self.result_tree.item(item_id)['values']
        if not values:
            return

        code = str(values[0]).zfill(10)  # 确保编码是字符串
        # 在后台线程中执行更新
        thread = threading.Thread(
            target=self._update_in_thread,
            args=(code, self._do_update_ni_rate),
            daemon=True
        )
        thread.start()

    def refresh_item(self, code: str):
        """刷新单个项目的数据"""
        try:
            # 查询最新数据
            results = self.db.search_tariffs(code, fuzzy=False)
            if not results:
                return

            # 查找并更新对应的项
            for item in self.result_tree.get_children():
                values = self.result_tree.item(item)['values']
                if values and values[0] == code:
                    self.result_tree.item(item, values=(
                        str(results[0]['code']).zfill(10),
                        results[0]['rate'],
                        results[0]['north_ireland_rate'],
                        ""
                    ))
                    break
        except Exception as e:
            logger.error(f"刷新数据失败: {str(e)}")

# https://www.trade-tariff.service.gov.uk/commodities/0101210000
# https://www.trade-tariff.service.gov.uk/commodities/0101210000