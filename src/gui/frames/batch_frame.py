import os
import logging
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from typing import Dict, List
from ...core.db.tariff_db import TariffDB
import queue
import threading
from datetime import datetime
import pandas as pd

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
        self.db = TariffDB()  # 使用默认的数据库路径

        # 初始化状态
        self.process_btn.configure(state='disabled')  # 初始时禁用处理按钮
        self.export_btn.configure(state='disabled')   # 初始时禁用导出按钮

    def setup_ui(self):
        """设置UI界面"""
        # 主布局使用三个框架：顶部、中部和底部
        top_frame = ttk.Frame(self)
        top_frame.pack(fill=tk.X, padx=10, pady=5)

        middle_frame = ttk.Frame(self)
        middle_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        bottom_frame = ttk.Frame(self)
        bottom_frame.pack(fill=tk.X, padx=10, pady=5)

        # 顶部框架：文件选择和操作按钮
        file_frame = ttk.LabelFrame(top_frame, text="文件操作")
        file_frame.pack(fill=tk.X, pady=5)

        # 第一行：模板和文件选择
        button_frame = ttk.Frame(file_frame)
        button_frame.pack(fill=tk.X, padx=5, pady=5)

        self.template_btn = ttk.Button(
            button_frame,
            text="下载模板",
            width=15,
            command=self.download_template
        )
        self.template_btn.pack(side=tk.LEFT, padx=5)

        self.select_btn = ttk.Button(
            button_frame,
            text="选择文件",
            width=15,
            command=self.select_file
        )
        self.select_btn.pack(side=tk.LEFT, padx=5)

        # 第二行：文件路径和处理按钮
        path_frame = ttk.Frame(file_frame)
        path_frame.pack(fill=tk.X, padx=5, pady=5)

        ttk.Label(path_frame, text="文件路径:").pack(side=tk.LEFT, padx=(0,5))

        self.file_path = tk.StringVar()
        path_entry = ttk.Entry(
            path_frame,
            textvariable=self.file_path,
            width=50
        )
        path_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)

        self.process_btn = ttk.Button(
            path_frame,
            text="开始处理",
            width=15,
            command=self.start_process
        )
        self.process_btn.pack(side=tk.LEFT, padx=5)

        self.export_btn = ttk.Button(
            path_frame,
            text="导出结果",
            width=15,
            command=self.export_results,
            state='disabled'
        )
        self.export_btn.pack(side=tk.LEFT, padx=5)

        # 中部框架：进度和日志
        progress_frame = ttk.LabelFrame(middle_frame, text="处理进度")
        progress_frame.pack(fill=tk.BOTH, expand=True, pady=5)

        # 进度条和状态
        status_frame = ttk.Frame(progress_frame)
        status_frame.pack(fill=tk.X, padx=5, pady=5)

        self.progress_var = tk.DoubleVar()
        self.progress = ttk.Progressbar(
            status_frame,
            variable=self.progress_var,
            mode='determinate'
        )
        self.progress.pack(fill=tk.X, side=tk.LEFT, expand=True, padx=(0,5))

        self.status_var = tk.StringVar(value="就绪")
        status_label = ttk.Label(
            status_frame,
            textvariable=self.status_var,
            width=20
        )
        status_label.pack(side=tk.LEFT)

        # 日志区域
        log_frame = ttk.Frame(progress_frame)
        log_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        self.log_text = tk.Text(log_frame, height=10)
        self.log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        scrollbar = ttk.Scrollbar(log_frame, command=self.log_text.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.log_text.configure(yscrollcommand=scrollbar.set)

        # 底部框架：历史记录
        history_frame = ttk.LabelFrame(bottom_frame, text="历史记录")
        history_frame.pack(fill=tk.BOTH, expand=True)

        # 历史记录表格
        columns = ('文件名', '处理时间', '状态', '记录数')
        self.history_tree = ttk.Treeview(
            history_frame,
            columns=columns,
            show='headings',
            height=5
        )

        # 设置列
        column_widths = {
            '文件名': 300,
            '处理时间': 150,
            '状态': 100,
            '记录数': 100
        }

        for col in columns:
            self.history_tree.heading(col, text=col)
            self.history_tree.column(col, width=column_widths.get(col, 100))

        # 添加滚动条
        tree_scroll = ttk.Scrollbar(
            history_frame,
            orient=tk.VERTICAL,
            command=self.history_tree.yview
        )
        self.history_tree.configure(yscrollcommand=tree_scroll.set)

        tree_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.history_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5, pady=5)

        # 添加说明文本
        info_frame = ttk.LabelFrame(bottom_frame, text="使用说明")
        info_frame.pack(fill=tk.X, pady=5)

        info_text = """
1. 点击"下载模板"获取标准Excel模板文件
2. 在模板中填入要查询的商品编码（必填）和描述（可选）
3. 点击"选择文件"导入填写好的Excel文件
4. 点击"开始处理"执行批量查询
5. 处理完成后可点击"导出结果"保存查询结果
        """

        ttk.Label(
            info_frame,
            text=info_text,
            justify=tk.LEFT,
            wraplength=600
        ).pack(padx=10, pady=5)

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

    def select_file(self):
        """选择要导入的文件"""
        filename = filedialog.askopenfilename(
            filetypes=[
                ("Excel 文件", "*.xlsx"),
                ("所有文件", "*.*")
            ],
            title="选择要导入的文件"
        )

        if filename:
            # 清除历史记录中的"待处理"项
            for item in self.history_tree.get_children():
                if self.history_tree.item(item)['values'][2] == '待处理':
                    self.history_tree.delete(item)

            self.file_path.set(filename)
            # 更新文件信息
            self.update_file_info(filename)

    def start_process(self):
        """开始处理"""
        if not self.file_path.get():
            self.add_log("请先选择要处理的文件")
            return

        # 禁用按钮
        self.process_btn.configure(state='disabled')
        self.select_btn.configure(state='disabled')
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

            # 更新历史记录状态
            for item in self.history_tree.get_children():
                if self.history_tree.item(item)['values'][0] == os.path.basename(self.file_path.get()):
                    self.history_tree.item(item, values=(
                        self.history_tree.item(item)['values'][0],
                        self.history_tree.item(item)['values'][1],
                        '处理中',
                        self.history_tree.item(item)['values'][3]
                    ))
                    break

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
                input_code = str(row['code']).strip()
                result = self.db.search_tariffs(input_code, fuzzy=True)  # 启用模糊匹配

                if result:
                    # 取相似度最高的结果（第一个）
                    results.append({
                        'input_code': input_code,  # 输入的编码
                        'matched_code': result[0]['code'],  # 匹配到的编码
                        'uk_rate': result[0]['rate'],  # 英国税率
                        'ni_rate': result[0]['north_ireland_rate']  # 北爱税率
                    })
                else:
                    results.append({
                        'input_code': input_code,
                        'matched_code': '未找到',
                        'uk_rate': '',
                        'ni_rate': ''
                    })

                self.queue.put((self.add_log, (f"处理完成: {input_code}",), {}))

            # 保存结果
            result_df = pd.DataFrame(results)
            # 设置列名
            result_df.columns = ['输入编码', '匹配编码', '英国税率', '北爱税率']
            os.makedirs(os.path.dirname(output_file), exist_ok=True)
            result_df.to_excel(output_file, index=False)

            # 更新历史记录状态
            for item in self.history_tree.get_children():
                if self.history_tree.item(item)['values'][0] == os.path.basename(self.file_path.get()):
                    self.history_tree.item(item, values=(
                        self.history_tree.item(item)['values'][0],
                        self.history_tree.item(item)['values'][1],
                        '已完成',
                        self.history_tree.item(item)['values'][3]
                    ))
                    break

            # 更新界面
            self.queue.put((self.status_var.set, ("处理完成",), {}))
            self.queue.put((self.add_log, (f"结果已保存到: {output_file}",), {}))
            self.queue.put((self.process_btn.configure, (), {'state': 'normal'}))
            self.queue.put((self.select_btn.configure, (), {'state': 'normal'}))
            self.queue.put((self.export_btn.configure, (), {'state': 'normal'}))

        except Exception as e:
            error_msg = f"处理文件失败: {str(e)}"
            logger.error(error_msg)
            self.queue.put((self.add_log, (error_msg,), {}))
            self.queue.put((self.status_var.set, ("处理失败",), {}))
            self.queue.put((self.process_btn.configure, (), {'state': 'normal'}))
            self.queue.put((self.select_btn.configure, (), {'state': 'normal'}))

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
                for item in self.history_tree.get_children():
                    values = self.history_tree.item(item)['values']
                    results.append({
                        '文件名': values[0],
                        '处理时间': values[1],
                        '文件大小': values[2]
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
        """下载模板文件"""
        try:
            # 打开文件选择对话框
            filename = filedialog.asksaveasfilename(
                defaultextension=".xlsx",
                filetypes=[("Excel 文件", "*.xlsx")],
                initialfile="批量查询模板.xlsx",
                title="保存模板文件"
            )

            if filename:
                # 复制模板文件到选择的位置
                template_path = os.path.join(self.template_dir, 'batch_rate_template.xlsx')

                # 如果模板不存在，先创建
                if not os.path.exists(template_path):
                    from scripts.create_template import create_template
                    if not create_template():
                        raise Exception("创建默认模板失败")

                import shutil
                shutil.copy2(template_path, filename)
                messagebox.showinfo(
                    "成功",
                    f"模板文件已保存到:\n{filename}\n\n请在模板中填入商品编码后再进行批量查询。"
                )
                self.add_log(f"模板已下载到: {filename}")

        except Exception as e:
            error_msg = f"下载模板失败: {str(e)}"
            logger.error(error_msg)
            messagebox.showerror("错误", error_msg)
            self.add_log(error_msg)

    def update_file_info(self, filename: str):
        """更新文件信息到历史记录"""
        try:
            # 获取文件信息
            file_stats = os.stat(filename)
            file_time = datetime.fromtimestamp(file_stats.st_mtime).strftime('%Y-%m-%d %H:%M:%S')

            # 读取Excel文件获取记录数
            df = pd.read_excel(filename, dtype={'code': str})
            record_count = len(df)

            # 添加到历史记录
            self.history_tree.insert(
                '',
                0,  # 插入到最前面
                values=(
                    os.path.basename(filename),
                    file_time,
                    '待处理',
                    f"{record_count}条"
                )
            )

            # 更新状态
            self.status_var.set(f"已选择文件: {os.path.basename(filename)}")
            self.process_btn.configure(state='normal')

        except Exception as e:
            logger.error(f"更新文件信息失败: {str(e)}")
            messagebox.showerror("错误", f"读取文件失败: {str(e)}")
            self.status_var.set("文件读取失败")
            self.process_btn.configure(state='disabled')