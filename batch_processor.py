import pandas as pd
import logging
from datetime import datetime
import os
from typing import List, Dict, Optional
from tariff_api import TariffAPI
import queue
import threading

logger = logging.getLogger(__name__)

class BatchProcessor:
    def __init__(self, output_dir: str = "output"):
        self.api = TariffAPI()
        self.output_dir = output_dir
        self.progress = 0
        self.total = 0
        self.status = "idle"
        self.log_queue = queue.Queue()
        self.current_file = None

        # 创建输出目录
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)

    def process_file(self, file_path: str) -> Optional[str]:
        """处理Excel文件

        Args:
            file_path: Excel文件路径

        Returns:
            输出文件路径，处理失败返回None
        """
        try:
            # 读取Excel文件
            df = pd.read_excel(file_path)
            if 'code' not in df.columns:
                self.log_queue.put("错误：Excel文件必须包含'code'列")
                return None

            self.total = len(df)
            self.progress = 0
            self.status = "processing"
            self.current_file = os.path.basename(file_path)

            # 处理每一行
            results = []
            for index, row in df.iterrows():
                code = str(row['code']).strip()
                # 使用模糊搜索找到最佳匹配
                matches = self.api.fuzzy_search(code, limit=1)
                if matches:
                    best_match = matches[0]
                    results.append({
                        'code': code,
                        'rate': best_match['rate'],
                        '相似度': f"{best_match['similarity']*100:.1f}%"
                    })
                else:
                    results.append({
                        'code': code,
                        'rate': '',
                        '相似度': "0.0%"
                    })

                self.progress = (index + 1) / self.total
                self.log_queue.put(f"处理进度: {self.progress*100:.1f}% - 正在处理: {code}")

            # 创建结果DataFrame
            result_df = pd.DataFrame(results)

            # 生成输出文件名
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            output_file = os.path.join(
                self.output_dir,
                f"processed_{timestamp}_{os.path.basename(file_path)}"
            )

            # 保存结果
            result_df.to_excel(output_file, index=False)

            self.status = "completed"
            self.log_queue.put(f"处理完成，结果已保存到: {output_file}")

            return output_file

        except Exception as e:
            self.status = "error"
            error_msg = f"处理文件失败: {str(e)}"
            logger.error(error_msg)
            self.log_queue.put(error_msg)
            return None

    def get_history_files(self) -> List[Dict]:
        """获取历史处理文件列表"""
        try:
            files = []
            for file in os.listdir(self.output_dir):
                if file.startswith("processed_"):
                    file_path = os.path.join(self.output_dir, file)
                    files.append({
                        'filename': file,
                        'path': file_path,
                        'time': datetime.fromtimestamp(
                            os.path.getctime(file_path)
                        ).strftime('%Y-%m-%d %H:%M:%S'),
                        'size': f"{os.path.getsize(file_path)/1024:.1f}KB"
                    })
            return sorted(files, key=lambda x: x['time'], reverse=True)
        except Exception as e:
            logger.error(f"获取历史文件失败: {str(e)}")
            return []

    def get_progress(self) -> Dict:
        """获取当前处理进度"""
        return {
            'progress': self.progress,
            'status': self.status,
            'current_file': self.current_file
        }

    def get_logs(self) -> List[str]:
        """获取所有待处理的日志"""
        logs = []
        while not self.log_queue.empty():
            logs.append(self.log_queue.get())
        return logs