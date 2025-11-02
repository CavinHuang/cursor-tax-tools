import tkinter as tk
from tkinter import ttk, messagebox
from typing import Dict
import logging
from tariff_api import TariffAPI
from tariff_db import TariffDB
import queue
import threading
from batch_gui import BatchProcessFrame

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)


class UpdateDialog:
    """数据更新对话框"""

    def __init__(self, parent, tariff_data: dict, on_save_callback=None):
        self.parent = parent
        self.tariff_data = tariff_data
        self.on_save_callback = on_save_callback
        self.result = None

        # 创建对话框窗口
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("更新关税数据")
        self.dialog.geometry("500x400")
        self.dialog.resizable(False, False)

        # 设置模态
        self.dialog.transient(parent)
        self.dialog.grab_set()

        # 居中显示
        self.dialog.geometry("+%d+%d" % (
            parent.winfo_rootx() + 50,
            parent.winfo_rooty() + 50
        ))

        self.setup_ui()

    def setup_ui(self):
        """设置对话框UI"""
        # 主框架
        main_frame = ttk.Frame(self.dialog, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # 商品编码（只读）
        ttk.Label(main_frame, text="商品编码:").grid(row=0, column=0, sticky=tk.W, pady=5)
        code_label = ttk.Label(main_frame, text=self.tariff_data['code'], font=('TkDefaultFont', 9, 'bold'))
        code_label.grid(row=0, column=1, sticky=tk.W, padx=10, pady=5)

        # 商品描述
        ttk.Label(main_frame, text="商品描述:").grid(row=1, column=0, sticky=tk.NW, pady=5)
        self.description_text = tk.Text(main_frame, width=40, height=4)
        self.description_text.grid(row=1, column=1, sticky=tk.W, padx=10, pady=5)
        self.description_text.insert('1.0', self.tariff_data.get('description', ''))

        # 英国税率
        ttk.Label(main_frame, text="英国税率:").grid(row=2, column=0, sticky=tk.W, pady=5)
        self.rate_var = tk.StringVar(value=self.tariff_data.get('rate', ''))
        rate_entry = ttk.Entry(main_frame, textvariable=self.rate_var, width=30)
        rate_entry.grid(row=2, column=1, sticky=tk.W, padx=10, pady=5)

        # 英国税率网址
        ttk.Label(main_frame, text="英国税率网址:").grid(row=3, column=0, sticky=tk.W, pady=5)
        self.url_var = tk.StringVar(value=self.tariff_data.get('url', ''))
        url_entry = ttk.Entry(main_frame, textvariable=self.url_var, width=30)
        url_entry.grid(row=3, column=1, sticky=tk.W, padx=10, pady=5)

        # 北爱尔兰税率
        ttk.Label(main_frame, text="北爱尔兰税率:").grid(row=4, column=0, sticky=tk.W, pady=5)
        self.ni_rate_var = tk.StringVar(value=self.tariff_data.get('north_ireland_rate', ''))
        ni_rate_entry = ttk.Entry(main_frame, textvariable=self.ni_rate_var, width=30)
        ni_rate_entry.grid(row=4, column=1, sticky=tk.W, padx=10, pady=5)

        # 北爱尔兰税率网址
        ttk.Label(main_frame, text="北爱尔兰税率网址:").grid(row=5, column=0, sticky=tk.W, pady=5)
        self.ni_url_var = tk.StringVar(value=self.tariff_data.get('north_ireland_url', ''))
        ni_url_entry = ttk.Entry(main_frame, textvariable=self.ni_url_var, width=30)
        ni_url_entry.grid(row=5, column=1, sticky=tk.W, padx=10, pady=5)

        # 按钮框架
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=6, column=0, columnspan=2, pady=20)

        # 保存按钮
        save_btn = ttk.Button(button_frame, text="保存", command=self.save)
        save_btn.pack(side=tk.LEFT, padx=5)

        # 取消按钮
        cancel_btn = ttk.Button(button_frame, text="取消", command=self.cancel)
        cancel_btn.pack(side=tk.LEFT, padx=5)

    def save(self):
        """保存更新"""
        try:
            # 获取输入值
            description = self.description_text.get('1.0', tk.END).strip()
            rate = self.rate_var.get().strip()
            url = self.url_var.get().strip()
            ni_rate = self.ni_rate_var.get().strip()
            ni_url = self.ni_url_var.get().strip()

            # 构建结果
            self.result = {
                'code': self.tariff_data['code'],
                'description': description if description else None,
                'rate': rate if rate else None,
                'url': url if url else None,
                'north_ireland_rate': ni_rate if ni_rate else None,
                'north_ireland_url': ni_url if ni_url else None
            }

            # 关闭对话框
            self.dialog.destroy()

            # 触发回调
            if self.on_save_callback:
                self.on_save_callback(self.result)

        except Exception as e:
            logger.error(f"保存更新失败: {str(e)}")
            messagebox.showerror("错误", f"保存失败: {str(e)}")

    def cancel(self):
        """取消更新"""
        self.dialog.destroy()


class TariffGUI:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("关税查询工具")
        self.setup_ui()
        self.setup_api()
        self.setup_queue()

    def setup_ui(self):
        """设置UI界面"""
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

        # 创建表格（注意：表格不显示description，但数据中包含它）
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
        self.context_menu.add_separator()
        self.context_menu.add_command(label="更新数据", command=self.update_data)
        self.context_menu.add_command(label="自动更新", command=self.auto_update)

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
        self.db = TariffDB()

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

    def update_data(self):
        """更新选中行的数据"""
        try:
            # 获取选中的项目
            selected_items = self.result_tree.selection()
            if not selected_items:
                messagebox.showwarning("警告", "请先选择要更新的数据")
                return

            item = selected_items[0]
            values = self.result_tree.item(item)['values']

            # 构建tariff数据
            tariff_data = {
                'code': values[0],
                'description': '',  # 表格中不显示description，从数据库获取
                'rate': values[1] if values[1] else None,
                'url': values[2] if values[2] else None,
                'north_ireland_rate': values[3] if values[3] else None,
                'north_ireland_url': values[4] if values[4] else None
            }

            # 从数据库获取完整数据（包括description）
            full_data = self.db.get_tariff(tariff_data['code'])
            if full_data:
                tariff_data.update(full_data)

            # 显示更新对话框
            dialog = UpdateDialog(self.root, tariff_data, on_save_callback=self._handle_update)

        except IndexError:
            messagebox.showwarning("警告", "请先选择要更新的数据")
        except Exception as e:
            logger.error(f"打开更新对话框失败: {str(e)}")
            messagebox.showerror("错误", f"打开更新对话框失败: {str(e)}")

    def _handle_update(self, updated_data):
        """处理更新结果（在对话框关闭后调用）"""
        def do_update():
            try:
                # 执行数据库更新
                self.db.update_tariff(
                    code=updated_data['code'],
                    description=updated_data['description'],
                    rate=updated_data['rate'],
                    url=updated_data['url'],
                    north_ireland_rate=updated_data['north_ireland_rate'],
                    north_ireland_url=updated_data['north_ireland_url']
                )

                # 更新UI
                self.queue.put((self._refresh_results, (), {}))

                # 显示成功消息
                self.queue.put((
                    lambda: self.status_var.set(f"已更新商品编码 {updated_data['code']} 的数据"),
                    (),
                    {}
                ))

            except Exception as e:
                logger.error(f"更新数据失败: {str(e)}")
                self.queue.put((
                    lambda: messagebox.showerror("错误", f"更新失败: {str(e)}"),
                    (),
                    {}
                ))

        # 在后台线程中执行更新
        thread = threading.Thread(target=do_update, daemon=True)
        thread.start()

    def _refresh_results(self):
        """刷新当前搜索结果"""
        # 保持当前搜索查询
        current_query = self.search_var.get().strip()
        if current_query:
            # 重新执行搜索
            self._search(current_query)
        else:
            # 如果没有搜索查询，清空结果
            for item in self.result_tree.get_children():
                self.result_tree.delete(item)

    def auto_update(self):
        """自动更新选中行的数据"""
        try:
            # 获取选中的项目
            selected_items = self.result_tree.selection()
            if not selected_items:
                messagebox.showwarning("警告", "请先选择要自动更新的数据")
                return

            item = selected_items[0]
            values = self.result_tree.item(item)['values']

            # 获取商品编码和税率网址
            code = values[0]
            uk_url = values[2]  # 英国网址在第3列
            ni_url = values[4] if len(values) > 4 and values[4] else None  # 北爱尔兰网址在第5列

            if not uk_url or not uk_url.strip():
                messagebox.showwarning("警告", "该记录没有英国税率网址，无法进行自动更新")
                return

            # 确认对话框
            if not messagebox.askyesno("确认自动更新",
                                       f"将自动抓取商品编码 {code} 的最新税率数据并与当前数据对比，\n"
                                       f"如有变化则更新。\n\n"
                                       f"确认继续吗？"):
                return

            # 在后台线程中执行自动更新
            thread = threading.Thread(
                target=self._do_auto_update,
                args=(code, uk_url, ni_url),
                daemon=True
            )
            thread.start()

            # 显示状态
            self.status_var.set("正在自动更新...")

        except IndexError:
            messagebox.showwarning("警告", "请先选择要自动更新的数据")
        except Exception as e:
            logger.error(f"自动更新失败: {str(e)}")
            messagebox.showerror("错误", f"自动更新失败: {str(e)}")

    def _do_auto_update(self, code: str, uk_url: str, ni_url: str = None):
        """在后台线程中执行自动更新"""
        try:
            # 执行自动更新
            result = self.api.auto_update(code, uk_url, ni_url)

            # 在主线程中处理结果
            self.queue.put((self._handle_auto_update_result, (result, code), {}))

        except Exception as e:
            logger.error(f"后台自动更新失败: {str(e)}")
            self.queue.put((
                lambda: (self.status_var.set("自动更新失败"),
                         messagebox.showerror("错误", f"自动更新失败: {str(e)}")),
                (),
                {}
            ))

    def _handle_auto_update_result(self, result: Dict, code: str):
        """处理自动更新结果"""
        try:
            if result['success']:
                if result['updated']:
                    # 实际更新了数据
                    self.status_var.set(f"自动更新成功: {result['message']}")

                    # 刷新搜索结果
                    self._refresh_results()

                    # 显示详细信息对话框
                    old_data = result['old_data']
                    new_data = result['new_data']

                    # 构建比较信息
                    old_rate = old_data.get('rate', '(无)')
                    new_rate = new_data.get('rate', '(无)')

                    detail_msg = (f"商品编码: {code}\n"
                                 f"\n"
                                 f"原税率: {old_rate}\n"
                                 f"新税率: {new_rate}\n"
                                 f"\n"
                                 f"{result['message']}")

                    messagebox.showinfo("自动更新成功", detail_msg)

                else:
                    # 没有变化，不需要更新
                    self.status_var.set("自动更新完成: " + result['message'])
                    messagebox.showinfo("自动更新完成", result['message'])
            else:
                # 自动更新失败
                self.status_var.set("自动更新失败")
                messagebox.showerror("自动更新失败", result['message'])

        except Exception as e:
            logger.error(f"处理自动更新结果失败: {str(e)}")
            self.status_var.set("处理自动更新结果时出错")
            messagebox.showerror("错误", f"处理自动更新结果失败: {str(e)}")

    def run(self):
        """运行GUI"""
        self.root.mainloop()

if __name__ == "__main__":
    gui = TariffGUI()
    gui.run()