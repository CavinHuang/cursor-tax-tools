import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from typing import Dict
import logging
from tariff_api import TariffAPI
from tariff_db import TariffDB
from scraper import BatchUpdateManager
from smart_update_client import SmartUpdateChecker
import queue
import threading
import asyncio
import os
from datetime import datetime
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

        # 批量更新标签页
        self.update_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.update_frame, text="批量更新")
        self.setup_batch_update()

        # 远程数据更新标签页
        self.remote_update_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.remote_update_frame, text="远程数据更新")
        self.setup_remote_update()

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

            # 验证URL有效性
            if not uk_url or not uk_url.strip():
                messagebox.showwarning("警告", "该记录没有英国税率网址，无法进行自动更新")
                return

            # 构建确认消息
            confirm_msg = f"将自动抓取商品编码 {code} 的最新税率数据并与当前数据对比：\n\n"
            confirm_msg += f"• 英国税率网址: {uk_url[:60]}{'...' if len(uk_url) > 60 else ''}\n"

            if ni_url and ni_url.strip():
                confirm_msg += f"• 北爱尔兰税率网址: {ni_url[:60]}{'...' if len(ni_url) > 60 else ''}\n"
            else:
                confirm_msg += f"• 北爱尔兰税率网址: 未提供\n"

            confirm_msg += f"\n如有变化则自动更新。确认继续吗？"

            # 确认对话框
            if not messagebox.askyesno("确认自动更新", confirm_msg):
                return

            # 在后台线程中执行自动更新
            thread = threading.Thread(
                target=self._do_auto_update,
                args=(code, uk_url, ni_url),
                daemon=True
            )
            thread.start()

            # 显示详细状态
            regions = ["英国"]
            if ni_url and ni_url.strip():
                regions.append("北爱尔兰")
            self.status_var.set(f"正在自动更新{', '.join(regions)}税率数据...")

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
        """处理自动更新结果（支持独立地区更新）"""
        try:
            # 获取新的状态字段（兼容新旧格式）
            overall_success = result.get('overall_success', result.get('success', False))
            uk_success = result.get('uk_success', False)
            ni_success = result.get('ni_success', False)
            uk_updated = result.get('uk_updated', False)
            ni_updated = result.get('ni_updated', False)
            any_updated = result.get('updated', uk_updated or ni_updated)

            if overall_success:
                if any_updated:
                    # 实际更新了数据
                    self.status_var.set(f"自动更新成功: {result['message']}")

                    # 刷新搜索结果
                    self._refresh_results()

                    # 显示详细信息对话框
                    self._show_detailed_update_dialog(code, result, uk_success, ni_success)

                else:
                    # 没有变化，不需要更新
                    self.status_var.set("自动更新完成: " + result['message'])

                    # 根据成功状态选择不同的消息框类型
                    if uk_success and ni_success:
                        messagebox.showinfo("自动更新完成", result['message'])
                    elif uk_success or ni_success:
                        messagebox.showinfo("部分更新完成", result['message'])
                    else:
                        messagebox.showwarning("更新无变化", result['message'])
            else:
                # 完全失败（两个地区都失败）
                self.status_var.set("自动更新失败")

                # 构建详细错误信息
                error_msg = result['message']

                # 根据失败情况显示不同类型的对话框
                if not uk_success and not ni_success:
                    messagebox.showerror("自动更新失败", error_msg)
                else:
                    # 部分失败，但仍显示为警告而不是错误
                    messagebox.showwarning("部分更新失败", error_msg)

        except Exception as e:
            logger.error(f"处理自动更新结果失败: {str(e)}")
            self.status_var.set("处理自动更新结果时出错")
            messagebox.showerror("错误", f"处理自动更新结果失败: {str(e)}")

    def _show_detailed_update_dialog(self, code: str, result: Dict, uk_success: bool, ni_success: bool):
        """显示详细的更新结果对话框"""
        try:
            old_data = result['old_data']
            new_data = result['new_data']

            # 创建详细信息对话框
            dialog = tk.Toplevel(self.root)
            dialog.title("自动更新详情")
            dialog.geometry("600x500")
            dialog.resizable(True, True)

            # 设置模态
            dialog.transient(self.root)
            dialog.grab_set()

            # 主框架
            main_frame = ttk.Frame(dialog, padding="20")
            main_frame.pack(fill=tk.BOTH, expand=True)

            # 商品编码
            code_frame = ttk.Frame(main_frame)
            code_frame.pack(fill=tk.X, pady=(0, 10))
            ttk.Label(code_frame, text="商品编码:", font=('TkDefaultFont', 10, 'bold')).pack(side=tk.LEFT)
            ttk.Label(code_frame, text=code, font=('TkDefaultFont', 10)).pack(side=tk.LEFT, padx=(5, 0))

            # 状态指示器
            status_frame = ttk.Frame(main_frame)
            status_frame.pack(fill=tk.X, pady=(0, 15))

            ttk.Label(status_frame, text="更新状态:", font=('TkDefaultFont', 10, 'bold')).pack(side=tk.LEFT)

            # 获取更新状态
            uk_updated = result.get('uk_updated', False)
            ni_updated = result.get('ni_updated', False)

            # 英国状态
            if uk_success:
                if uk_updated:
                    uk_status = "✅ 已更新"
                    uk_color = "green"
                else:
                    uk_status = "✅ 无变化"
                    uk_color = "blue"
            else:
                uk_status = "❌ 失败"
                uk_color = "red"

            uk_label = ttk.Label(status_frame, text=f"英国 {uk_status}", foreground=uk_color)
            uk_label.pack(side=tk.LEFT, padx=(10, 20))

            # 北爱尔兰状态
            if ni_success:
                if ni_updated:
                    ni_status = "✅ 已更新"
                    ni_color = "green"
                else:
                    ni_status = "✅ 无变化"
                    ni_color = "blue"
            else:
                ni_status = "❌ 失败"
                ni_color = "red"

            ni_label = ttk.Label(status_frame, text=f"北爱尔兰 {ni_status}", foreground=ni_color)
            ni_label.pack(side=tk.LEFT, padx=(0, 10))

            # 总体状态
            overall_success = result.get('overall_success', result.get('success', uk_success or ni_success))
            if overall_success:
                if uk_updated or ni_updated:
                    overall_status = "✅ 部分更新成功"
                    overall_color = "green"
                else:
                    overall_status = "ℹ️ 数据无变化"
                    overall_color = "blue"
            else:
                overall_status = "❌ 更新失败"
                overall_color = "red"

            overall_label = ttk.Label(status_frame, text=f"总体 {overall_status}", foreground=overall_color, font=('TkDefaultFont', 9, 'bold'))
            overall_label.pack(side=tk.LEFT, padx=(20, 0))

            # 创建笔记本用于分组显示
            notebook = ttk.Notebook(main_frame)
            notebook.pack(fill=tk.BOTH, expand=True, pady=(10, 0))

            # 数据对比标签页
            comparison_frame = ttk.Frame(notebook, padding="10")
            notebook.add(comparison_frame, text="数据对比")

            # 创建对比表格
            columns = ('字段', '更新前', '更新后', '状态')
            comparison_tree = ttk.Treeview(comparison_frame, columns=columns, show='headings', height=8)

            # 设置列标题和宽度
            column_widths = {'字段': 120, '更新前': 150, '更新后': 150, '状态': 100}
            for col in columns:
                comparison_tree.heading(col, text=col)
                comparison_tree.column(col, width=column_widths[col])

            # 添加滚动条
            comp_scrollbar = ttk.Scrollbar(comparison_frame, orient=tk.VERTICAL, command=comparison_tree.yview)
            comparison_tree.configure(yscrollcommand=comp_scrollbar.set)

            # 布局对比表格
            comp_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
            comparison_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

            # 填充对比数据
            self._fill_comparison_data(comparison_tree, old_data, new_data)

            # 原始数据标签页
            raw_frame = ttk.Frame(notebook, padding="10")
            notebook.add(raw_frame, text="原始数据")

            # 创建文本框显示原始数据
            raw_text = tk.Text(raw_frame, wrap=tk.WORD, height=15, font=('Consolas', 9))
            raw_scrollbar = ttk.Scrollbar(raw_frame, orient=tk.VERTICAL, command=raw_text.yview)
            raw_text.configure(yscrollcommand=raw_scrollbar.set)

            # 布局原始数据
            raw_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
            raw_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

            # 填充原始数据
            raw_content = self._format_raw_data(old_data, new_data, uk_success, ni_success)
            raw_text.insert('1.0', raw_content)
            raw_text.configure(state='disabled')

            # 按钮框架
            button_frame = ttk.Frame(main_frame)
            button_frame.pack(fill=tk.X, pady=(15, 0))

            # 关闭按钮
            close_btn = ttk.Button(button_frame, text="关闭", command=dialog.destroy)
            close_btn.pack(side=tk.RIGHT)

            # 居中显示对话框
            dialog.geometry("+%d+%d" % (
                self.root.winfo_rootx() + 100,
                self.root.winfo_rooty() + 50
            ))

        except Exception as e:
            logger.error(f"显示详细更新对话框失败: {str(e)}")
            # 如果详细对话框失败，回退到简单对话框
            messagebox.showinfo("自动更新成功", result['message'])

    def _fill_comparison_data(self, tree, old_data: Dict, new_data: Dict):
        """填充数据对比表格"""
        try:
            # 定义要对比的字段
            fields = [
                ('描述', 'description'),
                ('英国税率', 'rate'),
                ('北爱尔兰税率', 'north_ireland_rate'),
                ('英国网址', 'url'),
                ('北爱尔兰网址', 'north_ireland_url')
            ]

            for display_name, field_name in fields:
                old_value = old_data.get(field_name, '') or '(无)'
                new_value = new_data.get(field_name, '') or '(无)'

                # 确定状态
                if old_value == new_value:
                    status = "无变化"
                else:
                    status = "已更新"

                # 插入数据
                tree.insert('', 'end', values=(display_name, old_value[:50] + '...' if len(old_value) > 50 else old_value,
                                             new_value[:50] + '...' if len(new_value) > 50 else new_value, status))

        except Exception as e:
            logger.error(f"填充对比数据失败: {str(e)}")

    def _format_raw_data(self, old_data: Dict, new_data: Dict, uk_success: bool, ni_success: bool) -> str:
        """格式化原始数据用于显示"""
        try:
            content = []
            content.append("=" * 50)
            content.append("自动更新结果详情")
            content.append("=" * 50)
            content.append(f"更新时间: {self._get_current_time()}")
            content.append(f"英国数据获取: {'成功' if uk_success else '失败'}")
            content.append(f"北爱尔兰数据获取: {'成功' if ni_success else '失败'}")
            content.append("")

            content.append("-" * 30)
            content.append("更新前数据:")
            content.append("-" * 30)
            for key, value in old_data.items():
                content.append(f"{key}: {value}")

            content.append("")
            content.append("-" * 30)
            content.append("更新后数据:")
            content.append("-" * 30)
            for key, value in new_data.items():
                content.append(f"{key}: {value}")

            return "\n".join(content)

        except Exception as e:
            logger.error(f"格式化原始数据失败: {str(e)}")
            return f"格式化数据失败: {str(e)}"

    def setup_remote_update(self):
        """设置远程数据更新界面"""
        # 配置区域
        config_frame = ttk.LabelFrame(self.remote_update_frame, text="更新配置")
        config_frame.pack(fill='x', padx=10, pady=10)

        # 元数据URL
        ttk.Label(config_frame, text="元数据URL:").grid(row=0, column=0, sticky='w', padx=5, pady=5)
        self.metadata_url_var = tk.StringVar(
            value="https://github.com/CavinHuang/cursor-tax-tools/releases/download/latest-data/metadata.json"
        )
        ttk.Entry(config_frame, textvariable=self.metadata_url_var, width=70).grid(row=0, column=1, padx=5, pady=5)

        # 数据库路径
        ttk.Label(config_frame, text="数据库路径:").grid(row=1, column=0, sticky='w', padx=5, pady=5)
        self.db_path_var = tk.StringVar(value="tariffs.db")
        db_entry = ttk.Entry(config_frame, textvariable=self.db_path_var, width=70)
        db_entry.grid(row=1, column=1, padx=5, pady=5)

        # 浏览按钮
        ttk.Button(config_frame, text="浏览", command=self.browse_remote_database).grid(row=1, column=2, padx=5, pady=5)

        # 状态显示区域
        status_frame = ttk.LabelFrame(self.remote_update_frame, text="当前状态")
        status_frame.pack(fill='x', padx=10, pady=10)

        # 本地信息
        local_frame = ttk.Frame(status_frame)
        local_frame.pack(fill='x', padx=5, pady=5)
        ttk.Label(local_frame, text="本地版本:").pack(side='left')
        self.local_version_label = ttk.Label(local_frame, text="未知", foreground="blue")
        self.local_version_label.pack(side='left', padx=(10, 20))

        ttk.Label(local_frame, text="本地记录数:").pack(side='left')
        self.local_records_label = ttk.Label(local_frame, text="0", foreground="blue")
        self.local_records_label.pack(side='left', padx=10)

        # 远程信息
        remote_frame = ttk.Frame(status_frame)
        remote_frame.pack(fill='x', padx=5, pady=5)
        ttk.Label(remote_frame, text="远程版本:").pack(side='left')
        self.remote_version_label = ttk.Label(remote_frame, text="未检查", foreground="green")
        self.remote_version_label.pack(side='left', padx=(10, 20))

        ttk.Label(remote_frame, text="远程记录数:").pack(side='left')
        self.remote_records_label = ttk.Label(remote_frame, text="未检查", foreground="green")
        self.remote_records_label.pack(side='left', padx=10)

        # 更新状态
        update_frame = ttk.Frame(status_frame)
        update_frame.pack(fill='x', padx=5, pady=5)
        ttk.Label(update_frame, text="更新状态:").pack(side='left')
        self.update_status_label = ttk.Label(update_frame, text="未检查", foreground="gray")
        self.update_status_label.pack(side='left', padx=10)

        # 操作按钮区域
        action_frame = ttk.LabelFrame(self.remote_update_frame, text="操作")
        action_frame.pack(fill='x', padx=10, pady=10)

        button_frame = ttk.Frame(action_frame)
        button_frame.pack(pady=10)

        # 检查更新按钮
        self.check_remote_update_btn = ttk.Button(
            button_frame,
            text="🔍 检查更新",
            command=self.check_remote_update,
            width=15
        )
        self.check_remote_update_btn.pack(side='left', padx=5)

        # 强制更新按钮
        self.force_remote_update_btn = ttk.Button(
            button_frame,
            text="🔄 强制更新",
            command=self.force_remote_update,
            width=15
        )
        self.force_remote_update_btn.pack(side='left', padx=5)

        # 刷新状态按钮
        self.refresh_status_btn = ttk.Button(
            button_frame,
            text="♻️ 刷新状态",
            command=self.refresh_remote_status,
            width=15
        )
        self.refresh_status_btn.pack(side='left', padx=5)

        # 日志显示区域
        log_frame = ttk.LabelFrame(self.remote_update_frame, text="更新日志")
        log_frame.pack(fill='both', expand=True, padx=10, pady=10)

        # 创建日志文本框
        self.remote_log_text = tk.Text(log_frame, height=15, width=100)
        self.remote_log_scrollbar = ttk.Scrollbar(log_frame, command=self.remote_log_text.yview)
        self.remote_log_text.config(yscrollcommand=self.remote_log_scrollbar.set)

        self.remote_log_text.pack(side='left', fill='both', expand=True, padx=5, pady=5)
        self.remote_log_scrollbar.pack(side='right', fill='y', pady=5)

        # 进度条
        self.remote_progress_var = tk.DoubleVar()
        self.remote_progress_bar = ttk.Progressbar(
            self.remote_update_frame,
            variable=self.remote_progress_var,
            mode='indeterminate',
            length=400
        )
        self.remote_progress_bar.pack(fill='x', padx=10, pady=5)

        # 初始化远程更新检查器
        self.smart_update_checker = None

    def browse_remote_database(self):
        """浏览数据库文件"""
        filename = filedialog.askopenfilename(
            title="选择数据库文件",
            filetypes=[("SQLite数据库", "*.db"), ("所有文件", "*.*")]
        )
        if filename:
            self.db_path_var.set(filename)

    def refresh_remote_status(self):
        """刷新远程状态"""
        def refresh_task():
            try:
                db_path = self.db_path_var.get()
                if not os.path.exists(db_path):
                    # ✅ 使用队列更新UI
                    self.queue.put((self.local_version_label.config, (), {'text': "数据库文件不存在"}))
                    self.queue.put((self.local_records_label.config, (), {'text': "0"}))
                    self.queue.put((self.update_status_label.config, (), {'text': "需要创建", 'foreground': "orange"}))
                    self.queue.put((self.add_remote_log, ("❌ 数据库文件不存在",), {}))
                    return

                # 初始化更新检查器
                metadata_url = self.metadata_url_var.get()
                self.smart_update_checker = SmartUpdateChecker(metadata_url, db_path)

                # 获取本地信息
                local_metadata = self.smart_update_checker.load_local_metadata()
                local_db_info = self.smart_update_checker.get_local_db_info()

                # ✅ 使用队列更新UI
                if local_metadata:
                    self.queue.put((self.local_version_label.config, (), {'text': local_metadata.get('version', '未知')}))
                else:
                    self.queue.put((self.local_version_label.config, (), {'text': "无元数据"}))

                self.queue.put((self.local_records_label.config, (), {'text': str(local_db_info.get('record_count', 0))}))
                self.queue.put((self.update_status_label.config, (), {'text': "已检查", 'foreground': "green"}))
                self.queue.put((self.add_remote_log, ("✅ 本地状态已刷新",), {}))

            except Exception as e:
                # ✅ 使用队列更新UI
                self.queue.put((self.add_remote_log, (f"❌ 刷新状态失败: {str(e)}",), {}))
                self.queue.put((self.update_status_label.config, (), {'text': "检查失败", 'foreground': "red"}))

        threading.Thread(target=refresh_task, daemon=True).start()

    def check_remote_update(self):
        """检查远程更新"""
        def check_task():
            try:
                # ✅ 使用队列更新UI
                self.queue.put((self.set_remote_ui_state, (False,), {}))
                self.queue.put((self.remote_progress_bar.start, (), {}))
                self.queue.put((self.add_remote_log, ("🔍 开始检查远程更新...",), {}))

                # 初始化更新检查器
                db_path = self.db_path_var.get()
                metadata_url = self.metadata_url_var.get()
                self.smart_update_checker = SmartUpdateChecker(metadata_url, db_path)

                # 下载远程元数据
                remote_metadata = self.smart_update_checker.download_metadata()
                if not remote_metadata:
                    # ✅ 使用队列更新UI
                    self.queue.put((self.add_remote_log, ("❌ 无法下载远程元数据",), {}))
                    self.queue.put((self.remote_version_label.config, (), {'text': "获取失败", 'foreground': "red"}))
                    return

                # 更新远程版本信息
                remote_version = remote_metadata.get('version', '未知')
                remote_records = remote_metadata.get('record_count', 0)
                # ✅ 使用队列更新UI
                self.queue.put((self.remote_version_label.config, (), {'text': remote_version, 'foreground': "green"}))
                self.queue.put((self.remote_records_label.config, (), {'text': str(remote_records), 'foreground': "green"}))

                # 获取本地信息
                local_metadata = self.smart_update_checker.load_local_metadata()
                local_db_info = self.smart_update_checker.get_local_db_info()

                # 更新本地版本信息
                # ✅ 使用队列更新UI
                if local_metadata:
                    local_version = local_metadata.get('version', '未知')
                    self.queue.put((self.local_version_label.config, (), {'text': local_version}))
                else:
                    self.queue.put((self.local_version_label.config, (), {'text': "无元数据"}))

                self.queue.put((self.local_records_label.config, (), {'text': str(local_db_info.get('record_count', 0))}))

                # 检查是否需要更新
                update_needed, reason, details = self.smart_update_checker.check_update_needed(
                    remote_metadata, local_db_info, local_metadata
                )

                # ✅ 使用队列更新UI
                if update_needed:
                    self.queue.put((self.update_status_label.config, (), {'text': f"需要更新: {reason}", 'foreground': "orange"}))
                    self.queue.put((self.add_remote_log, (f"🔄 需要更新: {reason}",), {}))

                    priority = details.get('priority', 'medium')
                    if priority == 'high':
                        self.queue.put((self.add_remote_log, ("🔥 高优先级更新建议",), {}))
                    elif priority == 'medium':
                        self.queue.put((self.add_remote_log, ("⚠️ 中优先级更新建议",), {}))
                    else:
                        self.queue.put((self.add_remote_log, ("💡 低优先级更新建议",), {}))
                else:
                    self.queue.put((self.update_status_label.config, (), {'text': "已是最新", 'foreground': "green"}))
                    self.queue.put((self.add_remote_log, ("✅ 数据库已是最新版本",), {}))

            except Exception as e:
                # ✅ 使用队列更新UI
                self.queue.put((self.add_remote_log, (f"❌ 检查更新失败: {str(e)}",), {}))
                self.queue.put((self.update_status_label.config, (), {'text': "检查失败", 'foreground': "red"}))
            finally:
                # ✅ 使用队列更新UI
                self.queue.put((self.remote_progress_bar.stop, (), {}))
                self.queue.put((self.set_remote_ui_state, (True,), {}))

        threading.Thread(target=check_task, daemon=True).start()

    def force_remote_update(self):
        """强制更新"""
        def update_task():
            try:
                # ✅ 使用队列更新UI
                self.queue.put((self.set_remote_ui_state, (False,), {}))
                self.queue.put((self.remote_progress_bar.start, (), {}))
                self.queue.put((self.add_remote_log, ("🔄 开始强制更新...",), {}))

                # 初始化更新检查器
                db_path = self.db_path_var.get()
                metadata_url = self.metadata_url_var.get()
                self.smart_update_checker = SmartUpdateChecker(metadata_url, db_path)

                # 执行强制更新
                result = self.smart_update_checker.check_and_update(force_update=True)

                # ✅ 使用队列更新UI
                if result['status'] == 'success':
                    self.queue.put((self.add_remote_log, (f"✅ 更新成功: {result['message']}",), {}))
                    self.queue.put((self.update_status_label.config, (), {'text': "更新成功", 'foreground': "green"}))

                    # 刷新状态信息
                    self.queue.put((self.refresh_remote_status, (), {}))
                else:
                    self.queue.put((self.add_remote_log, (f"❌ 更新失败: {result['message']}",), {}))
                    self.queue.put((self.update_status_label.config, (), {'text': "更新失败", 'foreground': "red"}))

            except Exception as e:
                # ✅ 使用队列更新UI
                self.queue.put((self.add_remote_log, (f"❌ 强制更新异常: {str(e)}",), {}))
                self.queue.put((self.update_status_label.config, (), {'text': "更新异常", 'foreground': "red"}))
            finally:
                # ✅ 使用队列更新UI
                self.queue.put((self.remote_progress_bar.stop, (), {}))
                self.queue.put((self.set_remote_ui_state, (True,), {}))

        threading.Thread(target=update_task, daemon=True).start()

    def set_remote_ui_state(self, enabled):
        """设置远程更新UI状态"""
        state = 'normal' if enabled else 'disabled'
        self.check_remote_update_btn.config(state=state)
        self.force_remote_update_btn.config(state=state)
        self.refresh_status_btn.config(state=state)

    def add_remote_log(self, message):
        """添加远程更新日志"""
        timestamp = self._get_current_time()
        self.remote_log_text.insert('end', f"[{timestamp}] {message}\n")
        self.remote_log_text.see('end')

    def _get_current_time(self) -> str:
        """获取当前时间字符串"""
        from datetime import datetime
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    def setup_batch_update(self):
        """设置批量更新界面"""
        # 配置框架
        config_frame = ttk.LabelFrame(self.update_frame, text="更新配置")
        config_frame.pack(fill=tk.X, padx=5, pady=5)

        # 更新选项
        options_frame = ttk.Frame(config_frame)
        options_frame.pack(fill=tk.X, padx=5, pady=5)

        # 英国税率更新选项
        self.update_uk_var = tk.BooleanVar(value=True)
        uk_check = ttk.Checkbutton(
            options_frame,
            text="更新英国税率",
            variable=self.update_uk_var
        )
        uk_check.pack(side=tk.LEFT, padx=(0, 20))

        # 北爱尔兰税率更新选项
        self.update_ni_var = tk.BooleanVar(value=True)
        ni_check = ttk.Checkbutton(
            options_frame,
            text="更新北爱尔兰税率",
            variable=self.update_ni_var
        )
        ni_check.pack(side=tk.LEFT, padx=(0, 20))

        # 仅更新错误记录选项
        self.update_errors_only_var = tk.BooleanVar(value=False)
        errors_check = ttk.Checkbutton(
            options_frame,
            text="仅更新有错误的记录",
            variable=self.update_errors_only_var
        )
        errors_check.pack(side=tk.LEFT)

        # 高级设置框架
        advanced_frame = ttk.LabelFrame(config_frame, text="高级设置")
        advanced_frame.pack(fill=tk.X, padx=5, pady=5)

        # 批量大小
        batch_size_frame = ttk.Frame(advanced_frame)
        batch_size_frame.pack(fill=tk.X, padx=5, pady=2)
        ttk.Label(batch_size_frame, text="批量大小:").pack(side=tk.LEFT)
        self.batch_size_var = tk.StringVar(value="100")
        batch_size_spin = ttk.Spinbox(
            batch_size_frame,
            from_=10,
            to=200,
            textvariable=self.batch_size_var,
            width=10
        )
        batch_size_spin.pack(side=tk.LEFT, padx=(5, 20))

        # 批次延迟
        delay_frame = ttk.Frame(advanced_frame)
        delay_frame.pack(fill=tk.X, padx=5, pady=2)
        ttk.Label(delay_frame, text="批次间延迟(秒):").pack(side=tk.LEFT)
        self.delay_var = tk.StringVar(value="0.2")
        delay_spin = ttk.Spinbox(
            delay_frame,
            from_=0.1,
            to=10.0,
            increment=0.1,
            textvariable=self.delay_var,
            width=10
        )
        delay_spin.pack(side=tk.LEFT, padx=(5, 20))

        # 控制按钮框架
        control_frame = ttk.Frame(config_frame)
        control_frame.pack(fill=tk.X, padx=5, pady=10)

        # 开始更新按钮
        self.start_update_btn = ttk.Button(
            control_frame,
            text="开始批量更新",
            command=self.start_batch_update
        )
        self.start_update_btn.pack(side=tk.LEFT, padx=5)

        # 暂停按钮
        self.pause_update_btn = ttk.Button(
            control_frame,
            text="暂停",
            command=self.pause_batch_update,
            state='disabled'
        )
        self.pause_update_btn.pack(side=tk.LEFT, padx=5)

        # 停止按钮
        self.stop_update_btn = ttk.Button(
            control_frame,
            text="停止",
            command=self.stop_batch_update,
            state='disabled'
        )
        self.stop_update_btn.pack(side=tk.LEFT, padx=5)

        # 导出错误报告按钮
        self.export_errors_btn = ttk.Button(
            control_frame,
            text="导出错误报告",
            command=self.export_error_report
        )
        self.export_errors_btn.pack(side=tk.RIGHT, padx=5)

        # 进度显示框架
        progress_frame = ttk.LabelFrame(self.update_frame, text="更新进度")
        progress_frame.pack(fill=tk.X, padx=5, pady=5)

        # 总体进度条
        overall_progress_frame = ttk.Frame(progress_frame)
        overall_progress_frame.pack(fill=tk.X, padx=5, pady=5)
        ttk.Label(overall_progress_frame, text="总体进度:").pack(side=tk.LEFT)
        self.overall_progress_var = tk.DoubleVar()
        self.overall_progress_bar = ttk.Progressbar(
            overall_progress_frame,
            variable=self.overall_progress_var,
            maximum=100,
            length=300
        )
        self.overall_progress_bar.pack(side=tk.LEFT, padx=(5, 10))

        self.progress_label = ttk.Label(overall_progress_frame, text="0/0 (0.0%)")
        self.progress_label.pack(side=tk.LEFT)

        # 状态标签
        self.update_status_var = tk.StringVar(value="就绪")
        status_label = ttk.Label(progress_frame, textvariable=self.update_status_var)
        status_label.pack(padx=5, pady=2)

        # 统计信息框架
        stats_frame = ttk.LabelFrame(self.update_frame, text="统计信息")
        stats_frame.pack(fill=tk.X, padx=5, pady=5)

        # 创建统计信息显示
        stats_grid = ttk.Frame(stats_frame)
        stats_grid.pack(fill=tk.X, padx=5, pady=5)

        # 第一行统计
        ttk.Label(stats_grid, text="成功:").grid(row=0, column=0, sticky=tk.W, padx=5)
        self.success_count_label = ttk.Label(stats_grid, text="0", foreground="green")
        self.success_count_label.grid(row=0, column=1, sticky=tk.W, padx=5)

        ttk.Label(stats_grid, text="失败:").grid(row=0, column=2, sticky=tk.W, padx=5)
        self.failed_count_label = ttk.Label(stats_grid, text="0", foreground="red")
        self.failed_count_label.grid(row=0, column=3, sticky=tk.W, padx=5)

        ttk.Label(stats_grid, text="跳过:").grid(row=0, column=4, sticky=tk.W, padx=5)
        self.skipped_count_label = ttk.Label(stats_grid, text="0", foreground="orange")
        self.skipped_count_label.grid(row=0, column=5, sticky=tk.W, padx=5)

        # 第二行统计
        ttk.Label(stats_grid, text="英国更新:").grid(row=1, column=0, sticky=tk.W, padx=5)
        self.uk_updated_label = ttk.Label(stats_grid, text="0", foreground="blue")
        self.uk_updated_label.grid(row=1, column=1, sticky=tk.W, padx=5)

        ttk.Label(stats_grid, text="北爱尔兰更新:").grid(row=1, column=2, sticky=tk.W, padx=5)
        self.ni_updated_label = ttk.Label(stats_grid, text="0", foreground="purple")
        self.ni_updated_label.grid(row=1, column=3, sticky=tk.W, padx=5)

        ttk.Label(stats_grid, text="处理速度:").grid(row=1, column=4, sticky=tk.W, padx=5)
        self.speed_label = ttk.Label(stats_grid, text="0条/分钟")
        self.speed_label.grid(row=1, column=5, sticky=tk.W, padx=5)

        # 日志显示框架
        log_frame = ttk.LabelFrame(self.update_frame, text="更新日志")
        log_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # 日志文本框
        self.update_log_text = tk.Text(
            log_frame,
            height=15,
            wrap=tk.WORD,
            font=('Consolas', 9)
        )
        log_scroll = ttk.Scrollbar(
            log_frame,
            command=self.update_log_text.yview
        )
        self.update_log_text.configure(yscrollcommand=log_scroll.set)

        log_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.update_log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # 初始化批量更新管理器
        self.batch_update_manager = None
        self.update_thread = None

    def start_batch_update(self):
        """开始批量更新"""
        try:
            # 验证配置
            batch_size = int(self.batch_size_var.get())
            delay = float(self.delay_var.get())

            if batch_size < 1 or batch_size > 200:
                messagebox.showerror("错误", "批量大小必须在1-200之间")
                return

            if delay < 0.1 or delay > 10.0:
                messagebox.showerror("错误", "批次间延迟必须在0.1-10秒之间")
                return

            # 确认对话框
            update_uk = self.update_uk_var.get()
            update_ni = self.update_ni_var.get()
            errors_only = self.update_errors_only_var.get()

            # 如果只选择"仅更新错误记录"，自动勾选更新选项
            if errors_only and not update_uk and not update_ni:
                update_uk = True
                update_ni = True
                self.update_uk_var.set(True)
                self.update_ni_var.set(True)

            if not update_uk and not update_ni:
                messagebox.showwarning("警告", "请至少选择一个更新选项")
                return

            # 构建确认消息
            confirm_msg = f"即将开始批量更新，配置如下：\n\n"
            confirm_msg += f"• 更新英国税率: {'是' if update_uk else '否'}\n"
            confirm_msg += f"• 更新北爱尔兰税率: {'是' if update_ni else '否'}\n"
            confirm_msg += f"• 仅更新错误记录: {'是' if errors_only else '否'}\n"
            confirm_msg += f"• 批量大小: {batch_size}\n"
            confirm_msg += f"• 批次间延迟: {delay}秒\n"
            confirm_msg += f"\n注意：批量更新可能需要数小时完成，确定要开始吗？"

            if not messagebox.askyesno("确认批量更新", confirm_msg):
                return

            # 清空日志
            self.update_log_text.delete('1.0', tk.END)
            self.add_update_log("开始批量更新...")
            # 更新按钮状态
            self.start_update_btn.configure(state='disabled')
            self.pause_update_btn.configure(state='normal')
            self.stop_update_btn.configure(state='normal')

            # 创建批量更新管理器
            self.batch_update_manager = BatchUpdateManager(
                progress_callback=self.update_progress_callback,
                status_callback=self.update_status_callback,

            )

            # 创建过滤器函数
            filter_func = None
            if errors_only:
                filter_func = lambda tariff: self._has_error_record(tariff['code'])

            # 在后台线程中运行批量更新
            self.update_thread = threading.Thread(
                target=self._run_batch_update,
                args=(update_uk, update_ni, batch_size, delay, filter_func),
                daemon=True
            )
            self.update_thread.start()

        except ValueError as e:
            messagebox.showerror("错误", f"配置参数错误: {str(e)}")
        except Exception as e:
            logger.error(f"启动批量更新失败: {str(e)}")
            messagebox.showerror("错误", f"启动批量更新失败: {str(e)}")

    def _run_batch_update(self, update_uk, update_ni, batch_size, delay, filter_func):
        """在后台线程中运行批量更新"""
        try:
            # 运行异步批量更新
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            stats = loop.run_until_complete(
                self.batch_update_manager.update_all_tariffs(
                    update_uk=update_uk,
                    update_ni=update_ni,
                    batch_size=batch_size,
                    delay_between_batches=delay,
                    filter_func=filter_func
                )
            )

            # 在主线程中显示完成消息
            self.root.after(0, self._show_batch_update_complete, stats)

        except InterruptedError:
            self.root.after(0, self._show_batch_update_cancelled)
        except Exception as e:
            logger.error(f"批量更新执行失败: {str(e)}")
            self.root.after(0, self._show_batch_update_error, str(e))
        finally:
            # 恢复按钮状态
            self.root.after(0, self._reset_update_buttons)

    def update_progress_callback(self, completed, total, message=""):
        """进度回调函数"""
        def update_ui():
            # 更新进度条
            if total > 0:
                progress_percent = (completed / total) * 100
                self.overall_progress_var.set(progress_percent)
                self.progress_label.configure(text=f"{completed}/{total} ({progress_percent:.1f}%)")

            # 更新统计信息
            stats = self.batch_update_manager.get_stats()
            self.success_count_label.configure(text=str(stats['successful']))
            self.failed_count_label.configure(text=str(stats['failed']))
            self.skipped_count_label.configure(text=str(stats['skipped']))
            self.uk_updated_label.configure(text=str(stats['uk_updated']))
            self.ni_updated_label.configure(text=str(stats['ni_updated']))

            # 更新速度显示
            if 'rate' in stats:
                self.speed_label.configure(text=f"{stats['rate']:.1f}条/分钟")

            # 更新状态
            if message:
                self.update_status_var.set(message)

        # 在主线程中更新UI
        self.root.after(0, update_ui)

    def update_status_callback(self, message):
        """状态回调函数"""
        def update_ui():
            self.update_status_var.set(message)
            self.add_update_log(f"[{self._get_current_time()}] {message}")

        # 在主线程中更新UI
        self.root.after(0, update_ui)

    def add_update_log(self, message):
        """添加更新日志"""
        self.update_log_text.insert(tk.END, message + "\n")
        self.update_log_text.see(tk.END)
        self.update_log_text.update_idletasks()

    def pause_batch_update(self):
        """暂停批量更新"""
        if self.batch_update_manager:
            if self.batch_update_manager.is_paused:
                self.batch_update_manager.resume()
                self.pause_update_btn.configure(text="暂停")
                self.add_update_log("批量更新已恢复")
            else:
                self.batch_update_manager.pause()
                self.pause_update_btn.configure(text="恢复")
                self.add_update_log("批量更新已暂停")

    def stop_batch_update(self):
        """停止批量更新"""
        if self.batch_update_manager:
            if messagebox.askyesno("确认停止", "确定要停止批量更新吗？已处理的进度将会保存。"):
                self.batch_update_manager.cancel()
                self.add_update_log("正在停止批量更新...")

    def _has_error_record(self, code):
        """检查是否有错误记录"""
        try:
            # 获取指定编码的错误记录
            errors = self.db.get_scrape_errors(code)
            return len(errors) > 0
        except Exception:
            return False

    def _show_batch_update_complete(self, stats):
        """显示批量更新完成"""
        total_time = stats.get('elapsed_time', 0)
        total_minutes = total_time / 60 if total_time > 0 else 0

        message = f"批量更新完成！\n\n"
        message += f"总用时: {total_minutes:.1f}分钟\n"
        message += f"成功: {stats['successful']}\n"
        message += f"失败: {stats['failed']}\n"
        message += f"跳过: {stats['skipped']}\n"
        message += f"英国更新: {stats['uk_updated']}\n"
        message += f"北爱尔兰更新: {stats['ni_updated']}\n"

        if stats['errors']:
            message += f"\n错误数量: {len(stats['errors'])}"

        messagebox.showinfo("批量更新完成", message)
        self.add_update_log("="*50)
        self.add_update_log("批量更新完成！")
        self.add_update_log(f"总用时: {total_minutes:.1f}分钟")
        self.add_update_log(f"成功: {stats['successful']}, 失败: {stats['failed']}, 跳过: {stats['skipped']}")
        self.add_update_log("="*50)

    def _show_batch_update_cancelled(self):
        """显示批量更新取消"""
        messagebox.showinfo("批量更新已取消", "批量更新已被用户取消")
        self.add_update_log("批量更新已取消")

    def _show_batch_update_error(self, error_msg):
        """显示批量更新错误"""
        messagebox.showerror("批量更新失败", f"批量更新过程中发生错误：\n{error_msg}")
        self.add_update_log(f"错误: {error_msg}")

    def _reset_update_buttons(self):
        """重置更新按钮状态"""
        self.start_update_btn.configure(state='normal')
        self.pause_update_btn.configure(state='disabled', text="暂停")
        self.stop_update_btn.configure(state='disabled')
        self.overall_progress_var.set(0)
        self.progress_label.configure(text="0/0 (0.0%)")

    def export_error_report(self):
        """导出错误报告"""
        if not self.batch_update_manager:
            messagebox.showwarning("警告", "没有可用的批量更新数据")
            return

        stats = self.batch_update_manager.get_stats()
        if not stats['errors']:
            messagebox.showinfo("提示", "没有错误记录可导出")
            return

        # 选择保存位置
        file_path = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("文本文件", "*.txt"), ("所有文件", "*.*")],
            initialfile=f"batch_update_errors_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        )

        if file_path:
            try:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write("="*60 + "\n")
                    f.write("批量更新错误报告\n")
                    f.write(f"生成时间: {self._get_current_time()}\n")
                    f.write("="*60 + "\n\n")

                    f.write("统计信息:\n")
                    f.write(f"  总数: {stats['total']}\n")
                    f.write(f"  成功: {stats['successful']}\n")
                    f.write(f"  失败: {stats['failed']}\n")
                    f.write(f"  跳过: {stats['skipped']}\n")
                    f.write(f"  英国更新: {stats['uk_updated']}\n")
                    f.write(f"  北爱尔兰更新: {stats['ni_updated']}\n")
                    f.write(f"  错误数量: {len(stats['errors'])}\n\n")

                    f.write("错误详情:\n")
                    f.write("-"*60 + "\n")
                    for i, error in enumerate(stats['errors'], 1):
                        f.write(f"{i}. {error}\n")

                messagebox.showinfo("导出成功", f"错误报告已保存到:\n{file_path}")
                self.add_update_log(f"错误报告已导出到: {file_path}")

            except Exception as e:
                logger.error(f"导出错误报告失败: {str(e)}")
                messagebox.showerror("导出失败", f"导出错误报告失败: {str(e)}")

    def run(self):
        """运行GUI"""
        self.root.mainloop()

if __name__ == "__main__":
    gui = TariffGUI()
    gui.run()