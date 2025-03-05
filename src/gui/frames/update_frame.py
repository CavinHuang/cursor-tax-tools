import tkinter as tk
from tkinter import ttk
import logging
import queue
import threading
import asyncio
from src.core.scraper.uk_scraper import UKScraper
from src.core.scraper.ni_scraper import NIScraper
from src.core.db.tariff_db import TariffDB
import tkinter.messagebox as messagebox
from typing import List
from datetime import datetime
import os
import shutil

logger = logging.getLogger(__name__)

class UpdateFrame(ttk.Frame):
    def __init__(self, master):
        super().__init__(master)
        self.setup_ui()
        self.setup_queue()
        self.is_updating = False
        self.last_update = None  # 保存上次更新状态
        # 初始化数据库和爬虫实例
        self.db = TariffDB()
        self.uk_scraper = UKScraper()
        self.ni_scraper = NIScraper()

    def setup_ui(self):
        """设置UI界面"""
        # 选择框架
        select_frame = ttk.LabelFrame(self, text="选择更新内容")
        select_frame.pack(fill=tk.X, padx=5, pady=5)

        # 复选框
        self.uk_var = tk.BooleanVar(value=True)
        self.ni_var = tk.BooleanVar(value=True)

        ttk.Checkbutton(
            select_frame,
            text="英国关税数据",
            variable=self.uk_var
        ).pack(side=tk.LEFT, padx=5, pady=5)

        ttk.Checkbutton(
            select_frame,
            text="北爱尔兰关税数据",
            variable=self.ni_var
        ).pack(side=tk.LEFT, padx=5, pady=5)

        # 按钮框架
        button_frame = ttk.Frame(select_frame)
        button_frame.pack(side=tk.LEFT, padx=5, pady=5)

        # 更新按钮
        self.update_btn = ttk.Button(
            button_frame,
            text="开始更新",
            command=self.start_update
        )
        self.update_btn.pack(side=tk.LEFT, padx=2)

        # 停止按钮
        self.stop_btn = ttk.Button(
            button_frame,
            text="停止更新",
            command=self.stop_update,
            state='disabled'
        )
        self.stop_btn.pack(side=tk.LEFT, padx=2)

        # 进度框架
        progress_frame = ttk.LabelFrame(self, text="更新进度")
        progress_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # 进度条
        self.progress_var = tk.DoubleVar()
        self.progress = ttk.Progressbar(
            progress_frame,
            variable=self.progress_var,
            mode='determinate'
        )
        self.progress.pack(fill=tk.X, padx=5, pady=5)

        # 日志文本框
        self.log_text = tk.Text(progress_frame, height=10)
        self.log_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # 滚动条
        scrollbar = ttk.Scrollbar(progress_frame, command=self.log_text.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.log_text.configure(yscrollcommand=scrollbar.set)

        # 状态栏
        self.status_var = tk.StringVar(value="就绪")
        status_bar = ttk.Label(
            self,
            textvariable=self.status_var,
            relief=tk.SUNKEN,
            anchor=tk.W
        )
        status_bar.pack(fill=tk.X, padx=5, pady=2)

        # 失败列表框架
        failed_frame = ttk.LabelFrame(self, text="更新失败列表")
        failed_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # 创建失败列表
        columns = ('编码', '失败原因', '最后尝试时间')
        self.failed_tree = ttk.Treeview(
            failed_frame,
            columns=columns,
            show='headings',
            height=5
        )

        # 设置列
        column_widths = {
            '编码': 120,
            '失败原因': 300,
            '最后尝试时间': 150
        }

        for col in columns:
            self.failed_tree.heading(col, text=col)
            self.failed_tree.column(col, width=column_widths[col])

        # 添加滚动条
        scrollbar = ttk.Scrollbar(
            failed_frame,
            orient=tk.VERTICAL,
            command=self.failed_tree.yview
        )
        self.failed_tree.configure(yscrollcommand=scrollbar.set)

        # 布局
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.failed_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # 重试按钮框架
        retry_frame = ttk.Frame(failed_frame)
        retry_frame.pack(fill=tk.X, padx=5, pady=5)

        # 重试选中按钮
        self.retry_selected_btn = ttk.Button(
            retry_frame,
            text="重试选中",
            command=self.retry_selected,
            state='disabled'
        )
        self.retry_selected_btn.pack(side=tk.LEFT, padx=5)

        # 重试全部按钮
        self.retry_all_btn = ttk.Button(
            retry_frame,
            text="重试全部",
            command=self.retry_all,
            state='disabled'
        )
        self.retry_all_btn.pack(side=tk.LEFT, padx=5)

        # 清空列表按钮
        self.clear_failed_btn = ttk.Button(
            retry_frame,
            text="清空列表",
            command=self.clear_failed_list,
            state='disabled'
        )
        self.clear_failed_btn.pack(side=tk.LEFT, padx=5)

        # 绑定事件
        self.failed_tree.bind('<<TreeviewSelect>>', self.on_failed_select)

    def setup_queue(self):
        """设置消息队列"""
        self.queue = queue.Queue()
        self.after(100, self.process_queue)

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
            self.after(100, self.process_queue)

    def add_log(self, message: str):
        """添加日志"""
        self.log_text.insert(tk.END, f"{message}\n")
        self.log_text.see(tk.END)

    def start_update(self):
        """开始更新数据"""
        # 检查是否有上次未完成的更新
        if self.last_update:
            message = (
                "发现上次未完成的更新，是否继续？\n"
                f"上次更新到：{self.last_update['last_code']}\n"
                f"已完成：{self.last_update['progress']:.1f}%\n"
                "选择\"否\"开始新的更新"
            )
            answer = messagebox.askyesnocancel("继续更新", message)
            if answer is None:  # 用户点击取消
                return
            if not answer:  # 用户选择开始新的更新
                self.last_update = None

        # 检查是否选择了更新内容
        if not self.uk_var.get() and not self.ni_var.get():
            messagebox.showwarning("警告", "请至少选择一项要更新的内容")
            return

        # 禁用更新按钮，启用停止按钮
        self.update_btn.configure(state='disabled')
        self.stop_btn.configure(state='normal')
        self.status_var.set("正在更新数据...")
        self.progress_var.set(0)
        if not self.last_update:
            self.log_text.delete(1.0, tk.END)

        self.is_updating = True

        # 在后台线程中执行更新
        thread = threading.Thread(
            target=self._update_data,
            daemon=True
        )
        thread.start()

    def stop_update(self):
        """停止更新"""
        if not self.is_updating:
            return

        self.is_updating = False
        self.stop_btn.configure(state='disabled')
        self.status_var.set("正在停止更新...")
        self.add_log("正在停止更新...")

    async def _get_commodity_codes(self):
        """获取所有商品编码"""
        self.queue.put((
            self.add_log,
            ("开始获取所有商品编码...",),
            {}
        ))

        # 使用英国爬虫获取编码
        codes = await self.uk_scraper.get_all_commodity_codes()

        self.queue.put((
            self.add_log,
            (f"找到 {len(codes)} 个商品编码",),
            {}
        ))

        return codes

    def _update_data(self):
        """在后台线程中执行数据更新"""
        backup_path = None
        try:
            # 1. 备份当前数据库
            self.queue.put((
                self.add_log,
                ("开始备份当前数据库...",),
                {}
            ))

            db_path = self.db.db_path  # 使用 self.db 而不是 self.scraper.db
            backup_path = f"{db_path}.backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

            try:
                shutil.copy2(db_path, backup_path)
                self.queue.put((
                    self.add_log,
                    (f"数据库已备份到: {backup_path}",),
                    {}
                ))
            except Exception as e:
                logger.error(f"备份数据库失败: {str(e)}")
                self.queue.put((
                    self.add_log,
                    (f"备份数据库失败: {str(e)}",),
                    {}
                ))
                return

            # 2. 清空当前数据库
            self.queue.put((
                self.add_log,
                ("清空当前数据库...",),
                {}
            ))

            try:
                # 关闭当前连接
                self.db.close()
                # 删除数据库文件
                os.remove(db_path)
                # 重新创建数据库
                self.db = TariffDB()
                self.queue.put((
                    self.add_log,
                    ("数据库已清空，准备获取最新数据",),
                    {}
                ))
            except Exception as e:
                logger.error(f"清空数据库失败: {str(e)}")
                self.queue.put((
                    self.add_log,
                    (f"清空数据库失败: {str(e)}",),
                    {}
                ))
                return

            # 3. 从官网获取最新数据
            self.queue.put((
                self.add_log,
                ("开始从官网获取最新数据...",),
                {}
            ))

            # 创建异步事件循环
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            try:
                # 获取所有商品编码
                codes = loop.run_until_complete(self._get_commodity_codes())
                if not codes:
                    raise Exception("未找到任何商品编码")

                # 执行更新
                success = True
                if self.uk_var.get():
                    success &= loop.run_until_complete(self.uk_scraper.update_tariffs(codes))
                if self.ni_var.get():
                    success &= loop.run_until_complete(self.ni_scraper.update_tariffs(codes))

                if success:
                    self.queue.put((self._update_complete, (), {}))
                else:
                    raise Exception("更新失败")

            finally:
                loop.close()

        except Exception as e:
            logger.error(f"更新数据失败: {str(e)}")
            self.queue.put((
                self.status_var.set,
                (f"更新失败: {str(e)}",),
                {}
            ))
            # 如果更新失败且存在备份，尝试恢复
            if backup_path and os.path.exists(backup_path):
                try:
                    self.db.close()
                    shutil.copy2(backup_path, db_path)
                    self.db = TariffDB()
                    self.queue.put((
                        self.add_log,
                        ("更新失败，已恢复数据库备份",),
                        {}
                    ))
                except Exception as restore_error:
                    logger.error(f"恢复备份失败: {str(restore_error)}")
                    self.queue.put((
                        self.add_log,
                        (f"恢复备份失败: {str(restore_error)}",),
                        {}
                    ))
        finally:
            self.is_updating = False
            self.queue.put((self._reset_update_ui, (), {}))

    def _update_progress(self, progress: float, current_code: str = None):
        """更新进度"""
        self.progress_var.set(progress * 100)
        if current_code:
            self.status_var.set(f"正在更新: {current_code}")
            self.last_update = {
                'last_code': current_code,
                'progress': progress * 100,
                'uk_selected': self.uk_var.get(),
                'ni_selected': self.ni_var.get()
            }

    def _update_complete(self):
        """更新完成的处理"""
        self.status_var.set("数据更新完成")
        self.add_log("更新完成")
        messagebox.showinfo("成功", "数据更新完成")

    def _reset_update_ui(self):
        """重置更新UI状态"""
        self.update_btn.configure(state='normal')
        self.stop_btn.configure(state='disabled')

    def on_failed_select(self, event):
        """失败项选择事件处理"""
        if self.failed_tree.selection():
            self.retry_selected_btn.configure(state='normal')
        else:
            self.retry_selected_btn.configure(state='disabled')

    def add_failed_item(self, code: str, error: str):
        """添加失败项"""
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # 检查是否已存在
        for item in self.failed_tree.get_children():
            if self.failed_tree.item(item)['values'][0] == code:
                # 更新现有项
                self.failed_tree.item(item, values=(code, error, current_time))
                break
        else:
            # 添加新项
            self.failed_tree.insert('', 'end', values=(code, error, current_time))

        # 启用相关按钮
        self.retry_all_btn.configure(state='normal')
        self.clear_failed_btn.configure(state='normal')

    def clear_failed_list(self):
        """清空失败列表"""
        for item in self.failed_tree.get_children():
            self.failed_tree.delete(item)
        self.retry_all_btn.configure(state='disabled')
        self.retry_selected_btn.configure(state='disabled')
        self.clear_failed_btn.configure(state='disabled')

    async def retry_codes(self, codes: List[str]):
        """重试指定编码"""
        if not codes:
            return

        scraper = self.uk_scraper if self.uk_var.get() else self.ni_scraper

        # 设置回调函数
        scraper.set_progress_callback(lambda p, c: None)  # 不更新总进度
        scraper.set_log_callback(self.add_log)
        scraper.set_stop_check(lambda: not self.is_updating)

        self.add_log(f"开始重试 {len(codes)} 个失败项")

        for code in codes:
            if not self.is_updating:
                break

            self.add_log(f"重试商品 {code}")
            success = True

            if self.uk_var.get():
                success &= await scraper.update_tariffs([code])
            if self.ni_var.get():
                success &= await scraper.update_tariffs([code])

            if success:
                # 从失败列表中移除
                for item in self.failed_tree.get_children():
                    if self.failed_tree.item(item)['values'][0] == code:
                        self.failed_tree.delete(item)
                        break
            else:
                self.add_log(f"重试商品 {code} 失败")

        # 检查是否还有失败项
        if not self.failed_tree.get_children():
            self.retry_all_btn.configure(state='disabled')
            self.clear_failed_btn.configure(state='disabled')

    def retry_selected(self):
        """重试选中的失败项"""
        selected_items = self.failed_tree.selection()
        if not selected_items:
            return

        codes = [
            self.failed_tree.item(item)['values'][0]
            for item in selected_items
        ]

        # 在后台线程中执行重试
        thread = threading.Thread(
            target=self._retry_in_thread,
            args=(codes,),
            daemon=True
        )
        thread.start()

    def retry_all(self):
        """重试所有失败项"""
        codes = [
            self.failed_tree.item(item)['values'][0]
            for item in self.failed_tree.get_children()
        ]

        # 在后台线程中执行重试
        thread = threading.Thread(
            target=self._retry_in_thread,
            args=(codes,),
            daemon=True
        )
        thread.start()

    def _retry_in_thread(self, codes: List[str]):
        """在后台线程中执行重试"""
        self.is_updating = True
        self.update_btn.configure(state='disabled')
        self.stop_btn.configure(state='normal')
        self.retry_selected_btn.configure(state='disabled')
        self.retry_all_btn.configure(state='disabled')

        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(self.retry_codes(codes))
            loop.close()
        finally:
            self.is_updating = False
            self.queue.put((self._reset_update_ui, (), {}))