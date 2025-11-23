#!/usr/bin/env python3
"""
增强版智能哈希检查器
演示如何优化大文件哈希检测的性能
"""

import hashlib
import os
import time
from typing import Dict, Optional, Tuple

class EnhancedHashChecker:
    """增强版哈希检查器"""

    def __init__(self, db_path: str):
        self.db_path = db_path

    def smart_file_check(self, strategy: str = 'auto') -> Dict:
        """智能文件检查"""
        result = {
            'exists': False,
            'size': 0,
            'quick_hash': None,
            'full_hash': None,
            'check_time': 0,
            'strategy': strategy
        }

        if not os.path.exists(self.db_path):
            return result

        start_time = time.time()
        file_size = os.path.getsize(self.db_path)

        result['exists'] = True
        result['size'] = file_size

        # 根据策略选择检查方式
        if strategy == 'size_only':
            result['quick_hash'] = f"size_{file_size}"

        elif strategy == 'partial' and file_size > 50 * 1024 * 1024:  # 50MB+
            result['quick_hash'] = self._partial_hash()

        elif strategy == 'full' or strategy == 'auto':
            result['full_hash'] = self._full_hash()

        result['check_time'] = time.time() - start_time
        return result

    def _partial_hash(self) -> str:
        """部分哈希 - 只哈希文件的开头、中间、结尾"""
        hash_obj = hashlib.sha256()
        file_size = os.path.getsize(self.db_path)
        sample_size = 1024 * 1024  # 1MB

        with open(self.db_path, 'rb') as f:
            # 开头1MB
            hash_obj.update(f.read(sample_size))

            # 跳到中间读1MB
            f.seek(file_size // 2)
            hash_obj.update(f.read(sample_size))

            # 结尾1MB
            f.seek(max(0, file_size - sample_size))
            hash_obj.update(f.read(sample_size))

        return f"partial_{hash_obj.hexdigest()}"

    def _full_hash(self) -> str:
        """完整哈希 - 当前实现的方式"""
        hash_obj = hashlib.sha256()

        with open(self.db_path, 'rb') as f:
            while chunk := f.read(8192):
                hash_obj.update(chunk)

        return hash_obj.hexdigest()

    def compare_strategies(self) -> Dict:
        """对比不同策略的性能"""
        if not os.path.exists(self.db_path):
            return {'error': 'File not found'}

        file_size = os.path.getsize(self.db_path) / (1024 * 1024)  # MB
        print(f"文件大小: {file_size:.1f}MB")
        print("-" * 50)

        strategies = ['size_only', 'partial', 'full']
        results = {}

        for strategy in strategies:
            result = self.smart_file_check(strategy=strategy)
            results[strategy] = result

            hash_type = 'Quick' if strategy != 'full' else 'Full'
            print(f"{hash_type} {strategy:12s}: {result['check_time']:.3f}s")

        return results

def demo_performance():
    """演示性能对比"""
    print("=" * 60)
    print("智能哈希检查器演示")
    print("=" * 60)

    # 检查当前数据库文件
    db_path = "tariffs.db"
    if not os.path.exists(db_path):
        print("未找到 tariffs.db 文件，创建测试文件...")
        # 创建测试文件
        with open(db_path, 'wb') as f:
            f.write(b'0' * (10 * 1024 * 1024))  # 10MB测试文件
        print("已创建10MB测试文件")

    checker = EnhancedHashChecker(db_path)
    results = checker.compare_strategies()

    print("\n策略建议:")
    file_size = os.path.getsize(db_path) / (1024 * 1024)

    if file_size < 10:
        print("小文件(<10MB): 推荐使用完整哈希")
    elif file_size < 100:
        print("中等文件(10-100MB): 可以使用大小+时间预检")
    else:
        print("大文件(>100MB): 推荐使用部分哈希")

    print("\n当前实现(完整哈希)的内存使用:")
    print("- 固定8KB，与文件大小无关")
    print("- 不会因为文件大而爆内存")

if __name__ == "__main__":
    demo_performance()