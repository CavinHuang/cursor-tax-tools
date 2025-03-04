import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import logging
from typing import Dict, List
from ...core.db.tariff_db import TariffDB
import queue
import threading
from datetime import datetime
import pandas as pd
import os

logger = logging.getLogger(__name__)

class BatchFrame(ttk.Frame):
    def __init__(self, master):
        super().__init__(master)
        # 确保输出目录存在
        self.output_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))), "datas", "output")
        self.template_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))), "datas", "templates")
        os.makedirs(self.output_dir, exist_ok=True)
        os.makedirs(self.template_dir, exist_ok=True)

        self.setup_ui()
        self.setup_queue()
        self.db = TariffDB()

    def setup_ui(self):
        """设置UI界面"""
        # 文件选择框架
        file_frame = ttk.LabelFrame(self, text="文件选择")
        file_frame.pack(fill=tk.X, padx=5, pady=5)

        # 文件路径输入框
        self.file_path = tk.StringVar()
        path_entry = ttk.Entry(
            file_frame,
            textvariable=self.file_path,
            width=50
        )
        path_entry.pack(side=tk.LEFT, padx=5, pady=5)

        # 浏览按钮
        self.browse_btn = ttk.Button(
            file_frame,
            text="浏览",
            command=self.browse_file
        )
        self.browse_btn.pack(side=tk.LEFT, padx=5, pady=5)

        # 处理按钮
        self.process_btn = ttk.Button(
            file_frame,
            text="开始处理",
            command=self.start_process
        )
        self.process_btn.pack(side=tk.LEFT, padx=5, pady=5)

        # 添加导出按钮
        self.export_btn = ttk.Button(
            file_frame,
            text="导出结果",
            command=self.export_results,
            state='disabled'
        )
        self.export_btn.pack(side=tk.LEFT, padx=5, pady=5)

        # 添加下载模板按钮
        self.template_btn = ttk.Button(
            file_frame,
            text="下载模板",
            command=self.download_template
        )
        self.template_btn.pack(side=tk.LEFT, padx=5, pady=5)

        # 进度框架
        progress_frame = ttk.LabelFrame(self, text="处理进度")
        progress_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # 进度条
        self.progress_var = tk.DoubleVar()
        self.progress = ttk.Progressbar(
            progress_frame,
            variable=self.progress_var,
            mode='determinate'
        )
        self.progress.pack(fill=tk.X, padx=5, pady=5)

        # 状态标签
        self.status_var = tk.StringVar(value="就绪")
        status_label = ttk.Label(
            progress_frame,
            textvariable=self.status_var
        )
        status_label.pack(fill=tk.X, padx=5)

        # 日志文本框
        self.log_text = tk.Text(progress_frame, height=10)
        self.log_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # 滚动条
        scrollbar = ttk.Scrollbar(progress_frame, command=self.log_text.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.log_text.configure(yscrollcommand=scrollbar.set)

        # 历史记录框架
        history_frame = ttk.LabelFrame(self, text="历史记录")
        history_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # 历史记录列表
        columns = ('文件名', '处理时间', '文件大小')
        self.history_tree = ttk.Treeview(
            history_frame,
            columns=columns,
            show='headings',
            height=5
        )

        # 设置列
        for col in columns:
            self.history_tree.heading(col, text=col)
            self.history_tree.column(col, width=100)

        # 添加滚动条
        scrollbar = ttk.Scrollbar(
            history_frame,
            orient=tk.VERTICAL,
            command=self.history_tree.yview
        )
        self.history_tree.configure(yscrollcommand=scrollbar.set)

        # 布局
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.history_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

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

    def browse_file(self):
        """浏览文件"""
        filename = filedialog.askopenfilename(
            title="选择Excel文件",
            filetypes=[
                ("Excel文件", "*.xlsx;*.xls"),
                ("所有文件", "*.*")
            ],
            initialdir=os.path.expanduser("~")  # 从用户主目录开始
        )
        if filename:
            self.file_path.set(filename)
            self.add_log(f"已选择文件: {filename}")

    def start_process(self):
        """开始处理"""
        if not self.file_path.get():
            self.add_log("请先选择要处理的文件")
            return

        # 禁用按钮
        self.process_btn.configure(state='disabled')
        self.browse_btn.configure(state='disabled')
        self.status_var.set("正在处理...")
        self.progress_var.set(0)
        self.log_text.delete(1.0, tk.END)

        # 在后台线程中处理
        thread = threading.Thread(
            target=self._process_file,
            daemon=True
        )
        thread.start()

    def _process_file(self):
        """在后台线程中处理文件"""
        try:
            # 读取Excel文件
            df = pd.read_excel(self.file_path.get(), dtype={'code': str})
            total = len(df)

            # 创建输出文件名
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            output_file = os.path.join(
                self.output_dir,
                f"processed_{timestamp}_{os.path.basename(self.file_path.get())}"
            )

            # 处理每一行
            results = []
            for index, row in df.iterrows():
                # 更新进度
                progress = (index + 1) / total * 100
                self.queue.put((self.progress_var.set, (progress,), {}))
                self.queue.put((self.status_var.set, (f"正在处理: {index+1}/{total}",), {}))

                # 查询数据
                code = str(row['code']).strip()
                result = self.db.search_tariffs(code)

                if result:
                    results.append({
                        'code': code,
                        'description': result[0]['description'],
                        'rate': result[0]['rate'],
                        'north_ireland_rate': result[0]['north_ireland_rate']
                    })
                else:
                    results.append({
                        'code': code,
                        'description': '未找到',
                        'rate': '',
                        'north_ireland_rate': ''
                    })

                self.queue.put((self.add_log, (f"处理完成: {code}",), {}))

            # 保存结果
            result_df = pd.DataFrame(results)
            os.makedirs(os.path.dirname(output_file), exist_ok=True)  # 确保输出目录存在
            result_df.to_excel(output_file, index=False)

            # 更新界面
            self.queue.put((self.status_var.set, ("处理完成",), {}))
            self.queue.put((self.add_log, (f"结果已保存到: {output_file}",), {}))
            self.queue.put((self.process_btn.configure, (), {'state': 'normal'}))
            self.queue.put((self.browse_btn.configure, (), {'state': 'normal'}))
            self.queue.put((self.export_btn.configure, (), {'state': 'normal'}))  # 启用导出按钮

        except Exception as e:
            error_msg = f"处理文件失败: {str(e)}"
            logger.error(error_msg)
            self.queue.put((self.add_log, (error_msg,), {}))
            self.queue.put((self.status_var.set, ("处理失败",), {}))
            self.queue.put((self.process_btn.configure, (), {'state': 'normal'}))
            self.queue.put((self.browse_btn.configure, (), {'state': 'normal'}))

    def add_log(self, message: str):
        """添加日志"""
        self.log_text.insert(tk.END, f"{message}\n")
        self.log_text.see(tk.END)

    def export_results(self):
        """导出查询结果"""
        filename = filedialog.asksaveasfilename(
            title="保存结果",
            filetypes=[
                ("Excel文件", "*.xlsx"),
                ("所有文件", "*.*")
            ],
            defaultextension=".xlsx"
        )
        if filename:
            try:
                # 获取所有结果
                results = []
                for item in self.result_tree.get_children():
                    values = self.result_tree.item(item)['values']
                    results.append({
                        '商品编码': values[0],
                        '商品描述': values[1],
                        '英国税率': values[2],
                        '北爱税率': values[3]
                    })

                # 创建DataFrame并保存
                df = pd.DataFrame(results)
                df.to_excel(filename, index=False)
                self.add_log(f"结果已导出到: {filename}")

            except Exception as e:
                logger.error(f"导出失败: {str(e)}")
                self.add_log(f"导出失败: {str(e)}")
                messagebox.showerror("错误", f"导出失败: {str(e)}")

    def download_template(self):
        """下载Excel模板文件"""
        template_path = os.path.join(self.template_dir, "batch_rate_template.xlsx")

        try:
            # 打开文件保存对话框
            save_path = filedialog.asksaveasfilename(
                defaultextension=".xlsx",
                filetypes=[("Excel files", "*.xlsx")],
                initialfile="batch_rate_template.xlsx"
            )

            if save_path:
                if not os.path.exists(template_path):
                    # 如果模板不存在，创建新的模板
                    df = pd.DataFrame(columns=['code', 'description'])
                    df.to_excel(template_path, index=False)
                    logger.info(f"创建新的模板文件: {template_path}")

                # 复制模板文件到选择的位置
                import shutil
                shutil.copy2(template_path, save_path)
                messagebox.showinfo("成功", f"模板已保存到: {save_path}")
                self.add_log(f"模板已下载到: {save_path}")
        except Exception as e:
            error_msg = f"下载模板失败: {str(e)}"
            logger.error(error_msg)
            messagebox.showerror("错误", error_msg)
            self.add_log(error_msg)