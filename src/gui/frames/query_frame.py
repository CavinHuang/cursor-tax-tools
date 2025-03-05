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
import datetime

logger = logging.getLogger(__name__)

class QueryFrame(ttk.Frame):
    def __init__(self, master):
        super().__init__(master)
        self.db = TariffDB()  # 使用默认的数据库路径
        self.setup_ui()
        self.is_updating = False

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
        columns = ('编码', '英国税率', '北爱税率', '更新时间', '操作')
        self.result_tree = ttk.Treeview(
            result_frame,
            columns=columns,
            show='headings',
            height=10,
            style='Custom.Treeview'
        )

        # 创建自定义样式
        style = ttk.Style()
        style.configure(
            'Custom.Treeview',
            rowheight=30,  # 设置行高
            font=('微软雅黑', 10)
        )

        # 添加操作列的文字样式
        self.result_tree.tag_configure('link', foreground='blue')
        self.result_tree.tag_configure('link_hover', foreground='#0066cc')
        self.result_tree.tag_configure('disabled', foreground='gray')

        # 设置列
        column_widths = {
            '编码': 150,
            '英国税率': 150,
            '北爱税率': 150,
            '更新时间': 150,
            '操作': 200
        }

        for col in columns:
            self.result_tree.heading(
                col,
                text=col,
                anchor=tk.CENTER
            )
            self.result_tree.column(
                col,
                width=column_widths[col],
                anchor=tk.CENTER,
                stretch=tk.NO if col == '操作' else tk.YES  # 操作列不拉伸
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

        # 绑定单元格点击事件
        self.result_tree.bind('<Button-1>', self.on_cell_click)

        # 绑定鼠标移动事件
        self.result_tree.bind('<Motion>', self.on_tree_motion)

        # 绑定鼠标离开事件
        self.result_tree.bind('<Leave>', self.on_tree_leave)

        # 状态标签
        self.status_var = tk.StringVar()
        self.status_label = ttk.Label(
            self,
            textvariable=self.status_var
        )
        self.status_label.pack(fill=tk.X, padx=5)

        # 添加进度条框架
        progress_frame = ttk.Frame(self)
        progress_frame.pack(fill=tk.X, padx=5, pady=2)

        # 进度条
        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(
            progress_frame,
            mode='determinate',
            variable=self.progress_var
        )

        # 进度标签
        self.progress_label = ttk.Label(
            progress_frame,
            text=""
        )

        # 初始时不显示进度条和标签
        self.show_progress(False)

    def search(self):
        """执行搜索"""
        query = self.search_var.get().strip()
        if not query:
            messagebox.showwarning("警告", "请输入关税编码")
            return

        try:
            # 禁用搜索按钮
            self.search_btn.configure(state='disabled')

            # 清空结果列表
            for item in self.result_tree.get_children():
                self.result_tree.delete(item)

            # 执行查询
            results = self.db.search_tariffs(
                query,
                fuzzy=self.search_mode.get() == "fuzzy"
            )

            if not results:
                self.status_var.set("未找到匹配的关税编码")
                return

            # 显示结果时添加交替行颜色
            for i, result in enumerate(results):
                item_id = self.result_tree.insert('', 'end', values=(
                    str(result['code']).zfill(10),
                    result['rate'],
                    result['north_ireland_rate'],
                    self.format_datetime(result['updated_at']),
                    "更新英国 | 更新北爱"  # 直接显示文本
                ))

                # 设置交替行颜色
                tag = 'oddrow' if i % 2 else 'evenrow'
                self.result_tree.tag_configure(tag, background='#f5f5f5' if i % 2 else 'white')

                # 添加链接样式
                if self.is_updating:
                    self.result_tree.item(item_id, tags=(tag, 'disabled'))
                else:
                    self.result_tree.item(item_id, tags=(tag, 'link'))

            self.status_var.set(f"找到 {len(results)} 条结果")

        except Exception as e:
            logger.error(f"查询失败: {str(e)}")
            messagebox.showerror("错误", f"查询失败: {str(e)}")
        finally:
            # 启用搜索按钮
            self.search_btn.configure(state='normal')

    def on_cell_click(self, event):
        """处理单元格点击事件"""
        # 获取点击的单元格信息
        region = self.result_tree.identify_region(event.x, event.y)
        if region != "cell":
            return

        item = self.result_tree.identify_row(event.y)
        column = self.result_tree.identify_column(event.x)

        # 如果点击的是操作列
        if column == '#5' and not self.is_updating:  # 操作列是第5列
            # 获取点击位置相对于单元格的偏移
            cell_box = self.result_tree.bbox(item, column)
            if not cell_box:
                return

            x = event.x - cell_box[0]
            width = cell_box[2]

            # 根据点击位置判断点击了哪个按钮
            if x < width // 2:
                self.update_uk_rate(item)
            else:
                self.update_ni_rate(item)

    def on_tree_motion(self, event):
        """处理鼠标移动事件"""
        item = self.result_tree.identify_row(event.y)
        column = self.result_tree.identify_column(event.x)

        # 如果是操作列
        if column == '#5' and item and not self.is_updating:
            # 获取单元格区域
            cell_box = self.result_tree.bbox(item, column)
            if not cell_box:
                return

            # 更新鼠标样式
            self.result_tree.configure(cursor='hand2')

            # 更新文字样式
            current_tags = list(self.result_tree.item(item)['tags'])
            # 保留背景色标签
            bg_tag = [tag for tag in current_tags if tag in ('oddrow', 'evenrow')]
            self.result_tree.item(item, tags=bg_tag + ['link_hover'])
        else:
            # 恢复默认样式
            self.result_tree.configure(cursor='')
            if item:
                current_tags = list(self.result_tree.item(item)['tags'])
                # 保留背景色标签
                bg_tag = [tag for tag in current_tags if tag in ('oddrow', 'evenrow')]
                if not self.is_updating:
                    self.result_tree.item(item, tags=bg_tag + ['link'])
                else:
                    self.result_tree.item(item, tags=bg_tag + ['disabled'])

    def on_tree_leave(self, event):
        """处理鼠标离开事件"""
        # 恢复所有行的默认样式
        for item in self.result_tree.get_children():
            current_tags = list(self.result_tree.item(item)['tags'])
            # 保留背景色标签
            bg_tag = [tag for tag in current_tags if tag in ('oddrow', 'evenrow')]
            if not self.is_updating:
                self.result_tree.item(item, tags=bg_tag + ['link'])
            else:
                self.result_tree.item(item, tags=bg_tag + ['disabled'])
        self.result_tree.configure(cursor='')

    def disable_update_buttons(self):
        """禁用所有更新按钮"""
        self.is_updating = True
        for item in self.result_tree.get_children():
            current_tags = list(self.result_tree.item(item)['tags'])
            bg_tag = [tag for tag in current_tags if tag in ('oddrow', 'evenrow')]
            self.result_tree.item(item, tags=bg_tag + ['disabled'])

    def enable_update_buttons(self):
        """启用所有更新按钮"""
        self.is_updating = False
        for item in self.result_tree.get_children():
            current_tags = list(self.result_tree.item(item)['tags'])
            bg_tag = [tag for tag in current_tags if tag in ('oddrow', 'evenrow')]
            self.result_tree.item(item, tags=bg_tag + ['link'])

    def format_datetime(self, datetime_str: str) -> str:
        """格式化日期时间字符串"""
        if not datetime_str:
            return "未更新"
        try:
            dt = datetime.strptime(datetime_str, "%Y-%m-%d %H:%M:%S.%f")
            return dt.strftime("%Y-%m-%d %H:%M")
        except Exception:
            return datetime_str

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

    def _update_in_thread(self, code: str, update_func):
        """在后台线程中执行更新"""
        if self.is_updating:
            messagebox.showwarning("警告", "正在更新中，请稍候...")
            return

        self.is_updating = True
        error_msg = None  # 添加局部变量存储错误信息

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
            error_msg = str(e)  # 保存错误信息
            logger.error(f"更新失败: {error_msg}")
            self.after(0, lambda: messagebox.showerror("错误", f"更新失败: {error_msg}"))
        finally:
            self.is_updating = False
            # 启用所有更新按钮
            self.after(0, self.enable_update_buttons)
            # 隐藏进度条
            self.after(0, lambda: self.show_progress(False))

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
                        self.format_datetime(results[0]['updated_at']),  # 格式化更新时间
                        ""
                    ))
                    break
        except Exception as e:
            logger.error(f"刷新数据失败: {str(e)}")

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

# https://www.trade-tariff.service.gov.uk/commodities/0101210000
# https://www.trade-tariff.service.gov.uk/commodities/0101210000