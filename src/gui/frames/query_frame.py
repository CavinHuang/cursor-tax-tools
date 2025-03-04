import tkinter as tk
from tkinter import ttk
import logging
from ...core.db.tariff_db import TariffDB
import webbrowser
import tkinter.messagebox as messagebox

logger = logging.getLogger(__name__)

class QueryFrame(ttk.Frame):
    def __init__(self, master):
        super().__init__(master)
        self.db = TariffDB()
        self.setup_ui()

    def setup_ui(self):
        """设置UI界面"""
        # 搜索框架
        search_frame = ttk.LabelFrame(self, text="商品编码查询")
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
        columns = ('编码', '描述', '英国税率', '北爱税率')
        self.result_tree = ttk.Treeview(
            result_frame,
            columns=columns,
            show='headings',
            height=10
        )

        # 设置列
        column_widths = {
            '编码': 100,
            '描述': 300,
            '英国税率': 100,
            '北爱税率': 100
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

        # 状态栏
        self.status_var = tk.StringVar(value="就绪")
        status_bar = ttk.Label(
            self,
            textvariable=self.status_var,
            relief=tk.SUNKEN,
            anchor=tk.W
        )
        status_bar.pack(fill=tk.X, padx=5, pady=2)

        # 添加右键菜单
        self.context_menu = tk.Menu(self, tearoff=0)
        self.context_menu.add_command(label="复制编码", command=self.copy_code)
        self.context_menu.add_command(label="复制税率", command=self.copy_rate)
        self.context_menu.add_command(label="复制描述", command=self.copy_description)

        # 绑定右键菜单
        self.result_tree.bind('<Button-3>', self.show_context_menu)

        # 绑定事件
        self.result_tree.bind('<Double-1>', self.on_double_click)
        search_entry.bind('<Return>', lambda e: self.search())

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

            # 显示结果
            for result in results:
                self.result_tree.insert('', 'end', values=(
                    result['code'],
                    result['description'],
                    result['rate'],
                    result['north_ireland_rate']
                ))

            self.status_var.set(f"找到 {len(results)} 条结果")

        except Exception as e:
            logger.error(f"查询失败: {str(e)}")
            self.status_var.set(f"查询失败: {str(e)}")

    def on_double_click(self, event):
        """双击处理"""
        item = self.result_tree.selection()[0]
        code = self.result_tree.item(item)['values'][0]

        # 打开浏览器访问对应的URL
        try:
            url = f"https://www.trade-tariff.service.gov.uk/commodities/{code}"
            webbrowser.open(url)
        except Exception as e:
            logger.error(f"打开URL失败: {str(e)}")
            messagebox.showerror("错误", f"打开URL失败: {str(e)}")

    def show_context_menu(self, event):
        """显示右键菜单"""
        try:
            item = self.result_tree.identify_row(event.y)
            if item:
                self.result_tree.selection_set(item)
                self.context_menu.post(event.x_root, event.y_root)
        finally:
            self.context_menu.grab_release()

    def copy_code(self):
        """复制商品编码"""
        if selected := self.result_tree.selection():
            code = self.result_tree.item(selected[0])['values'][0]
            self.clipboard_clear()
            self.clipboard_append(code)
            self.status_var.set("已复制商品编码")

    def copy_rate(self):
        """复制税率"""
        if selected := self.result_tree.selection():
            values = self.result_tree.item(selected[0])['values']
            rate = f"英国: {values[2]}, 北爱: {values[3]}"
            self.clipboard_clear()
            self.clipboard_append(rate)
            self.status_var.set("已复制税率")

    def copy_description(self):
        """复制商品描述"""
        if selected := self.result_tree.selection():
            desc = self.result_tree.item(selected[0])['values'][1]
            self.clipboard_clear()
            self.clipboard_append(desc)
            self.status_var.set("已复制商品描述")