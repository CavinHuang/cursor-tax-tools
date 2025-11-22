import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import threading
import queue
import logging
from batch_processor import BatchProcessor
from smart_update_client import SmartUpdateChecker
import os
import webbrowser
from datetime import datetime

logger = logging.getLogger(__name__)

class EnhancedBatchProcessFrame(ttk.Frame):
    def __init__(self, master):
        super().__init__(master)
        self.processor = BatchProcessor()
        self.update_checker = None
        self.update_queue = queue.Queue()
        self.create_widgets()
        self.layout_widgets()
        self.setup_periodic_updates()

    def create_widgets(self):
        # 创建主要的notebook来组织界面
        self.notebook = ttk.Notebook(self)

        # 本地处理选项卡
        self.local_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.local_frame, text="本地数据处理")

        # 远程更新选项卡
        self.remote_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.remote_frame, text="远程数据更新")

        # 创建本地处理界面
        self.create_local_widgets()

        # 创建远程更新界面
        self.create_remote_widgets()

    def create_local_widgets(self):
        # 文件选择部分
        self.file_frame = ttk.LabelFrame(self.local_frame, text="文件选择")
        self.file_path_var = tk.StringVar()
        self.file_entry = ttk.Entry(
            self.file_frame,
            textvariable=self.file_path_var,
            width=50
        )
        self.browse_btn = ttk.Button(
            self.file_frame,
            text="浏览",
            command=self.browse_file
        )
        self.process_btn = ttk.Button(
            self.file_frame,
            text="开始处理",
            command=self.start_processing
        )
        # 添加下载模板按钮
        self.template_btn = ttk.Button(
            self.file_frame,
            text="下载模板",
            command=self.download_template
        )

        # 进度显示部分
        self.progress_frame = ttk.LabelFrame(self.local_frame, text="处理进度")
        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(
            self.progress_frame,
            variable=self.progress_var,
            maximum=100,
            mode='determinate'
        )
        self.status_label = ttk.Label(self.progress_frame, text="就绪")

        # 结果显示部分
        self.result_frame = ttk.LabelFrame(self.local_frame, text="处理结果")
        self.result_text = tk.Text(self.result_frame, height=10, width=60)
        self.result_scrollbar = ttk.Scrollbar(self.result_frame, command=self.result_text.yview)
        self.result_text.config(yscrollcommand=self.result_scrollbar.set)

        # 操作按钮部分
        self.action_frame = ttk.Frame(self.local_frame)
        self.download_btn = ttk.Button(
            self.action_frame,
            text="下载结果",
            command=self.download_selected_file,
            state='disabled'
        )
        self.clear_btn = ttk.Button(
            self.action_frame,
            text="清除结果",
            command=self.clear_results
        )

    def create_remote_widgets(self):
        # 远程更新配置部分
        self.config_frame = ttk.LabelFrame(self.remote_frame, text="更新配置")

        # 元数据URL配置
        ttk.Label(self.config_frame, text="元数据URL:").grid(row=0, column=0, sticky='w', padx=5, pady=5)
        self.metadata_url_var = tk.StringVar(value="https://github.com/LiaoFeng/cursor-tax-tools/releases/download/latest-data/metadata.json")
        self.metadata_url_entry = ttk.Entry(self.config_frame, textvariable=self.metadata_url_var, width=60)
        self.metadata_url_entry.grid(row=0, column=1, padx=5, pady=5)

        # 数据库路径配置
        ttk.Label(self.config_frame, text="数据库路径:").grid(row=1, column=0, sticky='w', padx=5, pady=5)
        self.db_path_var = tk.StringVar(value="tariffs.db")
        self.db_path_entry = ttk.Entry(self.config_frame, textvariable=self.db_path_var, width=60)
        self.db_path_entry.grid(row=1, column=1, padx=5, pady=5)

        # 浏览数据库路径按钮
        self.browse_db_btn = ttk.Button(
            self.config_frame,
            text="浏览",
            command=self.browse_database
        )
        self.browse_db_btn.grid(row=1, column=2, padx=5, pady=5)

        # 状态显示部分
        self.status_frame = ttk.LabelFrame(self.remote_frame, text="当前状态")

        # 本地版本信息
        ttk.Label(self.status_frame, text="本地版本:").grid(row=0, column=0, sticky='w', padx=5, pady=3)
        self.local_version_label = ttk.Label(self.status_frame, text="未知")
        self.local_version_label.grid(row=0, column=1, sticky='w', padx=5, pady=3)

        # 远程版本信息
        ttk.Label(self.status_frame, text="远程版本:").grid(row=1, column=0, sticky='w', padx=5, pady=3)
        self.remote_version_label = ttk.Label(self.status_frame, text="未检查")
        self.remote_version_label.grid(row=1, column=1, sticky='w', padx=5, pady=3)

        # 本地记录数
        ttk.Label(self.status_frame, text="本地记录数:").grid(row=2, column=0, sticky='w', padx=5, pady=3)
        self.local_records_label = ttk.Label(self.status_frame, text="0")
        self.local_records_label.grid(row=2, column=1, sticky='w', padx=5, pady=3)

        # 更新状态
        ttk.Label(self.status_frame, text="更新状态:").grid(row=3, column=0, sticky='w', padx=5, pady=3)
        self.update_status_label = ttk.Label(self.status_frame, text="未检查", foreground="gray")
        self.update_status_label.grid(row=3, column=1, sticky='w', padx=5, pady=3)

        # 操作按钮部分
        self.remote_action_frame = ttk.LabelFrame(self.remote_frame, text="操作")

        # 检查更新按钮
        self.check_update_btn = ttk.Button(
            self.remote_action_frame,
            text="🔍 检查更新",
            command=self.check_for_updates
        )
        self.check_update_btn.pack(side=tk.LEFT, padx=5, pady=5)

        # 强制更新按钮
        self.force_update_btn = ttk.Button(
            self.remote_action_frame,
            text="🔄 强制更新",
            command=self.force_update
        )
        self.force_update_btn.pack(side=tk.LEFT, padx=5, pady=5)

        # 刷新状态按钮
        self.refresh_status_btn = ttk.Button(
            self.remote_action_frame,
            text="♻️ 刷新状态",
            command=self.refresh_status
        )
        self.refresh_status_btn.pack(side=tk.LEFT, padx=5, pady=5)

        # 日志显示部分
        self.log_frame = ttk.LabelFrame(self.remote_frame, text="更新日志")
        self.log_text = tk.Text(self.log_frame, height=15, width=70)
        self.log_scrollbar = ttk.Scrollbar(self.log_frame, command=self.log_text.yview)
        self.log_text.config(yscrollcommand=self.log_scrollbar.set)

        # 进度条
        self.remote_progress_var = tk.DoubleVar()
        self.remote_progress_bar = ttk.Progressbar(
            self.remote_frame,
            variable=self.remote_progress_var,
            maximum=100,
            mode='indeterminate'
        )

    def layout_widgets(self):
        # notebook布局
        self.notebook.pack(fill='both', expand=True, padx=10, pady=10)

        # 本地处理布局
        self.layout_local_widgets()

        # 远程更新布局
        self.layout_remote_widgets()

    def layout_local_widgets(self):
        # 文件选择布局
        self.file_frame.pack(fill='x', padx=5, pady=5)
        self.file_entry.pack(side='left', fill='x', expand=True, padx=5)
        self.browse_btn.pack(side='left', padx=5)
        self.process_btn.pack(side='left', padx=5)
        self.template_btn.pack(side='left', padx=5)

        # 进度显示布局
        self.progress_frame.pack(fill='x', padx=5, pady=5)
        self.progress_bar.pack(fill='x', padx=5, pady=5)
        self.status_label.pack(padx=5)

        # 结果显示布局
        self.result_frame.pack(fill='both', expand=True, padx=5, pady=5)
        self.result_text.pack(side='left', fill='both', expand=True)
        self.result_scrollbar.pack(side='right', fill='y')

        # 操作按钮布局
        self.action_frame.pack(fill='x', padx=5, pady=5)
        self.download_btn.pack(side='left', padx=5)
        self.clear_btn.pack(side='left', padx=5)

    def layout_remote_widgets(self):
        # 配置布局
        self.config_frame.pack(fill='x', padx=5, pady=5)

        # 状态显示布局
        self.status_frame.pack(fill='x', padx=5, pady=5)

        # 操作按钮布局
        self.remote_action_frame.pack(fill='x', padx=5, pady=5)

        # 进度条布局
        self.remote_progress_bar.pack(fill='x', padx=5, pady=5)

        # 日志显示布局
        self.log_frame.pack(fill='both', expand=True, padx=5, pady=5)
        self.log_text.pack(side='left', fill='both', expand=True)
        self.log_scrollbar.pack(side='right', fill='y')

    def browse_database(self):
        """浏览数据库文件"""
        filename = filedialog.askopenfilename(
            title="选择数据库文件",
            filetypes=[("SQLite数据库", "*.db"), ("所有文件", "*.*")]
        )
        if filename:
            self.db_path_var.set(filename)

    def refresh_status(self):
        """刷新状态信息"""
        def refresh_task():
            try:
                db_path = self.db_path_var.get()
                if not os.path.exists(db_path):
                    self.local_version_label.config(text="数据库文件不存在")
                    self.local_records_label.config(text="0")
                    self.update_status_label.config(text="需要创建", foreground="orange")
                    return

                # 获取本地数据库信息
                if self.update_checker is None:
                    self.update_checker = SmartUpdateChecker(self.metadata_url_var.get(), db_path)
                else:
                    self.update_checker.db_path = db_path
                    self.update_checker.local_metadata_path = f"{db_path}.metadata.json"

                local_metadata = self.update_checker.load_local_metadata()
                local_db_info = self.update_checker.get_local_db_info()

                if local_metadata:
                    self.local_version_label.config(text=local_metadata.get('version', '未知'))
                    self.local_records_label.config(text=str(local_db_info.get('record_count', 0)))
                else:
                    self.local_version_label.config(text="无元数据")
                    self.local_records_label.config(text=str(local_db_info.get('record_count', 0)))

                self.update_status_label.config(text="已检查", foreground="green")
                self.log_message("✅ 状态已刷新")

            except Exception as e:
                self.log_message(f"❌ 刷新状态失败: {str(e)}")
                self.update_status_label.config(text="检查失败", foreground="red")

        threading.Thread(target=refresh_task, daemon=True).start()

    def check_for_updates(self):
        """检查更新"""
        def check_task():
            try:
                self.set_remote_ui_state(False)
                self.log_message("🔍 开始检查远程更新...")

                # 初始化更新检查器
                db_path = self.db_path_var.get()
                metadata_url = self.metadata_url_var.get()

                self.update_checker = SmartUpdateChecker(metadata_url, db_path)

                # 下载远程元数据
                remote_metadata = self.update_checker.download_metadata()
                if not remote_metadata:
                    self.log_message("❌ 无法下载远程元数据")
                    self.remote_version_label.config(text="获取失败", foreground="red")
                    return

                # 更新远程版本信息
                remote_version = remote_metadata.get('version', '未知')
                remote_records = remote_metadata.get('record_count', 0)
                self.remote_version_label.config(text=f"{remote_version} ({remote_records}条记录)")

                # 获取本地信息
                local_metadata = self.update_checker.load_local_metadata()
                local_db_info = self.update_checker.get_local_db_info()

                # 更新本地版本信息
                if local_metadata:
                    local_version = local_metadata.get('version', '未知')
                    self.local_version_label.config(text=local_version)
                self.local_records_label.config(text=str(local_db_info.get('record_count', 0)))

                # 检查是否需要更新
                update_needed, reason, details = self.update_checker.check_update_needed(
                    remote_metadata, local_db_info, local_metadata
                )

                if update_needed:
                    self.update_status_label.config(text=f"需要更新: {reason}", foreground="orange")
                    self.log_message(f"🔄 需要更新: {reason}")

                    priority = details.get('priority', 'medium')
                    if priority == 'high':
                        self.log_message("🔥 高优先级更新建议")
                    elif priority == 'medium':
                        self.log_message("⚠️ 中优先级更新建议")
                    else:
                        self.log_message("💡 低优先级更新建议")
                else:
                    self.update_status_label.config(text="已是最新", foreground="green")
                    self.log_message("✅ 数据库已是最新版本")

            except Exception as e:
                self.log_message(f"❌ 检查更新失败: {str(e)}")
                self.update_status_label.config(text="检查失败", foreground="red")
            finally:
                self.set_remote_ui_state(True)

        threading.Thread(target=check_task, daemon=True).start()

    def force_update(self):
        """强制更新"""
        def update_task():
            try:
                self.set_remote_ui_state(False)
                self.remote_progress_bar.start()
                self.log_message("🔄 开始强制更新...")

                # 初始化更新检查器
                db_path = self.db_path_var.get()
                metadata_url = self.metadata_url_var.get()

                self.update_checker = SmartUpdateChecker(metadata_url, db_path)

                # 执行强制更新
                result = self.update_checker.check_and_update(force_update=True)

                if result['status'] == 'success':
                    self.log_message(f"✅ 更新成功: {result['message']}")
                    self.update_status_label.config(text="更新成功", foreground="green")

                    # 刷新状态信息
                    self.refresh_status()
                else:
                    self.log_message(f"❌ 更新失败: {result['message']}")
                    self.update_status_label.config(text="更新失败", foreground="red")

            except Exception as e:
                self.log_message(f"❌ 强制更新异常: {str(e)}")
                self.update_status_label.config(text="更新异常", foreground="red")
            finally:
                self.remote_progress_bar.stop()
                self.set_remote_ui_state(True)

        threading.Thread(target=update_task, daemon=True).start()

    def set_remote_ui_state(self, enabled):
        """设置远程更新UI状态"""
        state = 'normal' if enabled else 'disabled'
        self.check_update_btn.config(state=state)
        self.force_update_btn.config(state=state)
        self.refresh_status_btn.config(state=state)

    def log_message(self, message):
        """添加日志消息"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_text.insert('end', f"[{timestamp}] {message}\n")
        self.log_text.see('end')

    # 保留原有的本地处理方法
    def browse_file(self):
        filename = filedialog.askopenfilename(
            title="选择Excel文件",
            filetypes=[("Excel files", "*.xlsx"), ("All files", "*.*")]
        )
        if filename:
            self.file_path_var.set(filename)

    def start_processing(self):
        file_path = self.file_path_var.get()
        if not file_path:
            messagebox.showerror("错误", "请先选择文件")
            return

        self.process_btn.config(state='disabled')
        self.progress_var.set(0)
        self.status_label.config(text="处理中...")
        self.result_text.delete(1.0, tk.END)

        def process_task():
            try:
                self.processor.process_file(file_path, self.update_queue)
            except Exception as e:
                self.update_queue.put(('error', str(e)))

        threading.Thread(target=process_task, daemon=True).start()

    def setup_periodic_updates(self):
        self.after(100, self.update_ui)

    def update_ui(self):
        try:
            while not self.update_queue.empty():
                msg_type, data = self.update_queue.get_nowait()

                if msg_type == 'progress':
                    self.progress_var.set(data)
                    if data == 100:
                        self.status_label.config(text="处理完成")
                        self.process_btn.config(state='normal')
                        self.download_btn.config(state='normal')
                    else:
                        self.status_label.config(text=f"处理中... {data}%")

                elif msg_type == 'result':
                    self.result_text.insert(tk.END, data)
                    self.result_text.see(tk.END)

                elif msg_type == 'error':
                    self.status_label.config(text="处理出错")
                    self.process_btn.config(state='normal')
                    messagebox.showerror("错误", data)

        except queue.Empty:
            pass

        self.after(100, self.update_ui)

    def download_selected_file(self):
        save_path = filedialog.asksaveasfilename(
            defaultextension=".xlsx",
            filetypes=[("Excel files", "*.xlsx"), ("All files", "*.*")]
        )
        if save_path:
            try:
                self.processor.save_results(save_path)
                messagebox.showinfo("成功", f"结果已保存到: {save_path}")
            except Exception as e:
                messagebox.showerror("错误", f"保存失败: {str(e)}")

    def download_template(self):
        template_path = "template.xlsx"
        try:
            self.processor.create_template(template_path)
            webbrowser.open(f'file://{os.path.abspath(template_path)}')
            messagebox.showinfo("成功", "模板文件已打开")
        except Exception as e:
            messagebox.showerror("错误", f"创建模板失败: {str(e)}")

    def clear_results(self):
        self.result_text.delete(1.0, tk.END)
        self.download_btn.config(state='disabled')
        self.progress_var.set(0)
        self.status_label.config(text="就绪")

def main():
    root = tk.Tk()
    root.title("关税数据处理工具 - 增强版")
    root.geometry("800x600")

    # 设置窗口图标（如果有的话）
    try:
        root.iconbitmap("icon.ico")
    except:
        pass

    app = EnhancedBatchProcessFrame(root)
    app.pack(fill='both', expand=True)

    # 设置窗口关闭事件
    def on_closing():
        if messagebox.askokcancel("退出", "确定要退出吗？"):
            root.destroy()

    root.protocol("WM_DELETE_WINDOW", on_closing)
    root.mainloop()

if __name__ == "__main__":
    main()