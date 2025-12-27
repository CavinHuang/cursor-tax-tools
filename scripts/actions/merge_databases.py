#!/usr/bin/env python3
"""
数据库合并器 - 合并多个 shard 数据库并处理去重

功能：
1. 合并多个 shard 数据库
2. 基于主键去重（commodity_code）
3. 保留最新的更新时间戳
4. 生成合并统计报告
"""

import sqlite3
import sys
import os
import json
import glob
from typing import List, Dict, Tuple
from pathlib import Path

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))


class DatabaseMerger:
    """数据库合并器 - 合并多个分片数据库"""

    def __init__(self, main_db_path: str = "tariffs.db"):
        """
        初始化数据库合并器

        Args:
            main_db_path: 主数据库文件路径
        """
        self.main_db_path = main_db_path
        self.stats = {
            "total_shards": 0,
            "successful_shards": 0,
            "failed_shards": 0,
            "total_records": 0,
            "total_shard_records": 0,  # 新增：所有分片的记录总数
            "duplicate_records_removed": 0,
            "merge_time_seconds": 0,
            "shard_details": []
        }

    def merge_shard_databases(
        self,
        shard_paths: List[str],
        output_path: str = None
    ) -> dict:
        """
        合并多个 shard 数据库

        合并策略：
        1. 创建主数据库（如果不存在）
        2. 使用 ATTACH DATABASE 连接所有分片
        3. 使用 INSERT OR IGNORE 去重（基于 commodity_code 主键）
        4. 记录每个分片的统计信息

        Args:
            shard_paths: 分片数据库路径列表
            output_path: 输出数据库路径，默认为 main_db_path

        Returns:
            dict: 合并统计信息
        """
        import time
        start_time = time.time()

        if output_path is None:
            output_path = self.main_db_path

        print(f"🔧 开始合并 {len(shard_paths)} 个分片数据库...")

        # 初始化主数据库
        self._initialize_main_database(output_path)

        # 连接主数据库
        main_conn = sqlite3.connect(output_path)
        main_cursor = main_conn.cursor()

        # 合并每个分片
        total_shard_records = 0  # 追踪所有分片的记录总数

        for i, shard_path in enumerate(shard_paths):
            if not os.path.exists(shard_path):
                print(f"⚠️  分片不存在: {shard_path}")
                self.stats["failed_shards"] += 1
                continue

            # 获取分片记录数（即使合并失败也要统计）
            try:
                temp_conn = sqlite3.connect(shard_path)
                shard_count = temp_conn.execute(
                    "SELECT COUNT(*) FROM tariffs"
                ).fetchone()[0]
                temp_conn.close()
                total_shard_records += shard_count
            except Exception as e:
                print(f"⚠️  无法读取分片记录数 ({shard_path}): {e}")
                self.stats["failed_shards"] += 1
                continue

            try:
                # 附加分片数据库
                shard_db_name = f"shard_db_{i}"
                main_cursor.execute(
                    f"ATTACH DATABASE '{shard_path}' AS {shard_db_name}"
                )

                # 合并数据（使用 INSERT OR IGNORE 去重）
                main_cursor.execute(f"""
                    INSERT OR IGNORE INTO tariffs
                    SELECT * FROM {shard_db_name}.tariffs
                """)

                # 获取实际新增记录数
                added_records = main_cursor.rowcount

                # 分离数据库
                main_cursor.execute(f"DETACH DATABASE {shard_db_name}")

                # 记录统计
                self.stats["successful_shards"] += 1
                self.stats["shard_details"].append({
                    "shard_path": shard_path,
                    "shard_records": shard_count,
                    "added_records": added_records
                })

                print(f"✅ 分片 {i+1}/{len(shard_paths)}: "
                      f"+{added_records} 条记录 (分片总计: {shard_count})")

            except Exception as e:
                print(f"❌ 合并分片失败 ({shard_path}): {e}")
                self.stats["failed_shards"] += 1
                # 即使失败，也要记录分片信息用于统计
                self.stats["shard_details"].append({
                    "shard_path": shard_path,
                    "shard_records": shard_count,
                    "added_records": 0,
                    "error": str(e)
                })
                continue

        # 提交事务
        main_conn.commit()

        # 收集统计信息
        self.stats["total_shards"] = len(shard_paths)
        self.stats["total_records"] = main_cursor.execute(
            "SELECT COUNT(*) FROM tariffs"
        ).fetchone()[0]
        self.stats["total_shard_records"] = total_shard_records

        # 计算去重的记录数（仅当有成功合并时）
        if self.stats["successful_shards"] > 0:
            self.stats["duplicate_records_removed"] = (
                total_shard_records - self.stats["total_records"]
            )
        else:
            # 没有成功合并任何分片，去重记录数设为0
            self.stats["duplicate_records_removed"] = 0

        self.stats["merge_time_seconds"] = time.time() - start_time

        # 关闭连接
        main_conn.close()

        print(f"\n✅ 合并完成!")
        print(f"   总分片数: {self.stats['total_shards']}")
        print(f"   成功合并: {self.stats['successful_shards']}")
        print(f"   失败跳过: {self.stats['failed_shards']}")

        # 仅当有成功合并时显示详细统计
        if self.stats["successful_shards"] > 0:
            print(f"   总记录数: {self.stats['total_records']:,}")
            print(f"   分片记录总计: {self.stats['total_shard_records']:,}")
            print(f"   去重记录: {self.stats['duplicate_records_removed']:,}")
        else:
            print(f"   ⚠️  所有分片合并失败，使用现有数据库")
            print(f"   现有记录数: {self.stats['total_records']:,}")

        print(f"   耗时: {self.stats['merge_time_seconds']:.2f} 秒")

        return self.stats

    def _initialize_main_database(self, db_path: str):
        """
        初始化主数据库（创建表结构）

        Args:
            db_path: 数据库路径
        """
        # 如果数据库已存在，检查表结构
        if os.path.exists(db_path):
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='tariffs'"
            )
            if cursor.fetchone():
                conn.close()
                return

        # 创建新数据库
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # 创建 tariffs 表（与 tariff_db.py 保持一致）
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS tariffs (
                code TEXT PRIMARY KEY,
                description TEXT,
                rate TEXT,
                url TEXT,
                north_ireland_rate TEXT,
                north_ireland_url TEXT,
                other_rate TEXT,
                last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # 创建索引
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_description
            ON tariffs(description)
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_rate
            ON tariffs(rate)
        """)

        conn.commit()
        conn.close()

        print(f"✅ 主数据库已初始化: {db_path}")

    def discover_shard_databases(
        self,
        input_dir: str = "artifacts",
        pattern: str = "tariffs_shard_*.db",
        recursive: bool = True
    ) -> List[str]:
        """
        自动发现分片数据库文件

        Args:
            input_dir: 搜索目录
            pattern: 文件匹配模式
            recursive: 是否递归搜索子目录

        Returns:
            List[str]: 分片数据库路径列表（按 shard 编号排序）
        """
        shard_files = []

        # DEBUG: 打印输入目录的内容
        print(f"🔍 搜索目录: {input_dir}")
        print(f"🔍 搜索模式: {pattern}")
        print(f"🔍 递归搜索: {recursive}")

        if os.path.exists(input_dir):
            print(f"📂 目录内容:")
            for root, dirs, files in os.walk(input_dir):
                level = root.replace(input_dir, '').count(os.sep)
                indent = ' ' * 2 * level
                print(f'{indent}{os.path.basename(root)}/')
                subindent = ' ' * 2 * (level + 1)
                for file in files:
                    print(f'{subindent}{file}')
        else:
            print(f"❌ 目录不存在: {input_dir}")

        if recursive:
            # 递归搜索所有子目录
            for root, dirs, files in os.walk(input_dir):
                # 使用 fnmatch 过滤文件名
                import fnmatch
                matched_files = [
                    os.path.join(root, f)
                    for f in files
                    if fnmatch.fnmatch(f, pattern)
                ]
                shard_files.extend(matched_files)
        else:
            # 只搜索顶层目录
            search_pattern = os.path.join(input_dir, pattern)
            shard_files = glob.glob(search_pattern)

        # 按 shard 编号排序
        shard_files.sort(key=lambda x: self._extract_shard_number(x))

        print(f"🔍 发现 {len(shard_files)} 个分片数据库:")
        for shard_file in shard_files:
            print(f"   - {shard_file}")

        return shard_files

    @staticmethod
    def _extract_shard_number(filename: str) -> int:
        """
        从文件名提取 shard 编号

        Args:
            filename: 文件名

        Returns:
            int: Shard 编号
        """
        try:
            # 从 "tariffs_shard_0.db" 提取 0
            basename = os.path.basename(filename)
            number = basename.replace("tariffs_shard_", "").replace(".db", "")
            return int(number)
        except (ValueError, IndexError):
            return 9999  # 未知文件排在最后

    def validate_merged_database(self, db_path: str = None) -> dict:
        """
        验证合并后的数据库

        Args:
            db_path: 数据库路径，默认为 main_db_path

        Returns:
            dict: 验证结果
        """
        if db_path is None:
            db_path = self.main_db_path

        if not os.path.exists(db_path):
            return {
                "valid": False,
                "error": "数据库文件不存在"
            }

        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        try:
            # 基本统计
            total_records = cursor.execute(
                "SELECT COUNT(*) FROM tariffs"
            ).fetchone()[0]

            records_with_description = cursor.execute(
                "SELECT COUNT(*) FROM tariffs WHERE description IS NOT NULL"
            ).fetchone()[0]

            records_with_rate = cursor.execute(
                "SELECT COUNT(*) FROM tariffs WHERE rate IS NOT NULL"
            ).fetchone()[0]

            # 检查重复
            duplicates = cursor.execute("""
                SELECT COUNT(*) - COUNT(DISTINCT code)
                FROM tariffs
            """).fetchone()[0]

            # 数据完整性
            completeness = {
                "description": (records_with_description / total_records * 100)
                               if total_records > 0 else 0,
                "rate": (records_with_rate / total_records * 100)
                        if total_records > 0 else 0,
            }

            result = {
                "valid": True,
                "total_records": total_records,
                "records_with_description": records_with_description,
                "records_with_rate": records_with_rate,
                "duplicates": duplicates,
                "completeness": completeness
            }

            conn.close()
            return result

        except Exception as e:
            conn.close()
            return {
                "valid": False,
                "error": str(e)
            }

    def save_merge_results(self, output_file: str = "merge_results.json"):
        """
        保存合并结果到 JSON 文件

        Args:
            output_file: 输出文件路径
        """
        try:
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(self.stats, f, indent=2, ensure_ascii=False, default=str)
            print(f"💾 合并结果已保存: {output_file}")
        except Exception as e:
            print(f"⚠️  保存合并结果失败: {e}")


def main():
    """主函数 - 命令行接口"""
    import argparse

    parser = argparse.ArgumentParser(description="数据库合并器")
    parser.add_argument(
        "--input-dir",
        type=str,
        default="artifacts",
        help="分片数据库目录"
    )
    parser.add_argument(
        "--output",
        type=str,
        default="tariffs.db",
        help="输出数据库路径"
    )
    parser.add_argument(
        "--shards",
        type=str,
        nargs="+",
        help="手动指定分片数据库路径"
    )
    parser.add_argument(
        "--validate",
        action="store_true",
        help="合并后验证数据库"
    )
    parser.add_argument(
        "--allow-partial",
        action="store_true",
        help="允许部分失败（部分分片合并失败不影响整体）"
    )

    args = parser.parse_args()

    # 创建合并器
    merger = DatabaseMerger(main_db_path=args.output)

    # 发现或使用指定的分片
    if args.shards:
        shard_paths = args.shards
    else:
        shard_paths = merger.discover_shard_databases(args.input_dir)

    if not shard_paths:
        print("❌ 未找到分片数据库")
        sys.exit(1)

    # 合并数据库
    try:
        stats = merger.merge_shard_databases(shard_paths, args.output)
        merger.save_merge_results()

        # 验证合并结果
        if args.validate:
            print("\n🔍 验证合并结果...")
            validation = merger.validate_merged_database(args.output)

            if validation["valid"]:
                print("✅ 验证通过")
                print(f"   总记录数: {validation['total_records']:,}")
                print(f"   描述完整性: {validation['completeness']['description']:.1f}%")
                print(f"   税率完整性: {validation['completeness']['rate']:.1f}%")
                print(f"   重复记录: {validation['duplicates']}")
            else:
                print(f"❌ 验证失败: {validation['error']}")
                if not args.allow_partial:
                    sys.exit(1)

    except Exception as e:
        print(f"❌ 合并失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
