#!/usr/bin/env python3
"""
GitHub Actions脚本: 生成数据库元数据文件
用于智能更新客户端判断是否需要下载数据库
"""

import hashlib
import json
import os
import sqlite3
import sys
from datetime import datetime, timezone
from typing import Dict, Optional

# 添加项目根目录到 Python 路径（便于直接脚本执行 + 作为模块导入）
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from src.actions.generate_changelog import generate_changelog


def calculate_file_hash(file_path: str, algorithm: str = 'sha256') -> str:
    """计算文件哈希值"""
    hash_func = getattr(hashlib, algorithm)()

    try:
        with open(file_path, 'rb') as f:
            while chunk := f.read(8192):
                hash_func.update(chunk)
        return f"{algorithm}:{hash_func.hexdigest()}"
    except FileNotFoundError:
        return f"{algorithm}:unknown"
    except Exception as e:
        print(f"计算哈希失败: {e}", file=sys.stderr)
        return f"{algorithm}:error"


def get_database_stats(db_path: str) -> Dict:
    """获取数据库统计信息"""
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        stats = {
            'record_count': cursor.execute("SELECT COUNT(*) FROM tariffs").fetchone()[0],
            'records_with_description': 0,
            'records_with_uk_rate': 0,
            'records_with_ni_rate': 0,
            'common_rates': [],
            'categories_count': 0,
            'active_errors': 0
        }

        # 质量指标
        stats['records_with_description'] = cursor.execute(
            "SELECT COUNT(*) FROM tariffs WHERE description IS NOT NULL AND description != ''"
        ).fetchone()[0]

        stats['records_with_uk_rate'] = cursor.execute(
            "SELECT COUNT(*) FROM tariffs WHERE rate IS NOT NULL AND rate != ''"
        ).fetchone()[0]

        stats['records_with_ni_rate'] = cursor.execute(
            "SELECT COUNT(*) FROM tariffs WHERE north_ireland_rate IS NOT NULL AND north_ireland_rate != ''"
        ).fetchone()[0]

        # 常见税率（增加到10条，与根目录版本一致）
        rate_dist = cursor.execute("""
            SELECT rate, COUNT(*) as count
            FROM tariffs
            WHERE rate IS NOT NULL AND rate != ''
            GROUP BY rate
            ORDER BY count DESC
            LIMIT 10
        """).fetchall()

        stats['common_rates'] = [rate for rate, count in rate_dist]

        # ✅ 动态计算税率范围（从根目录版本合并）
        if rate_dist:
            numeric_rates = []
            for rate, count in rate_dist:
                try:
                    # 提取数字部分
                    rate_value = float(rate.replace('%', ''))
                    numeric_rates.append(rate_value)
                except ValueError:
                    continue

            if numeric_rates:
                stats['uk_rate_min'] = f"{min(numeric_rates)}%"
                stats['uk_rate_max'] = f"{max(numeric_rates)}%"

        # 分类统计
        try:
            stats['categories_count'] = cursor.execute("""
                SELECT COUNT(DISTINCT SUBSTR(code, 1, 2)) FROM tariffs
            """).fetchone()[0]
        except:
            pass

        # ✅ 更新历史统计（从根目录版本合并）
        try:
            recent_updates = cursor.execute("""
                SELECT COUNT(*) FROM update_history
                WHERE timestamp > datetime('now', '-1 day')
            """).fetchone()[0]
            stats['recent_updates_24h'] = recent_updates
        except:
            stats['recent_updates_24h'] = 0

        # 错误统计
        try:
            stats['active_errors'] = cursor.execute("SELECT COUNT(*) FROM scrape_errors").fetchone()[0]
        except:
            pass

        conn.close()
        return stats

    except Exception as e:
        print(f"获取数据库统计失败: {e}", file=sys.stderr)
        return {}


def load_update_results(results_path: str) -> Dict:
    """加载更新结果"""
    try:
        if os.path.exists(results_path):
            with open(results_path, 'r', encoding='utf-8') as f:
                return json.load(f)
    except Exception as e:
        print(f"加载更新结果失败: {e}", file=sys.stderr)

    return {}


def analyze_coverage(merge_results: Dict, task_file: str = None) -> Dict:
    """分析数据覆盖率和缺失信息"""
    coverage_info = {
        'total_chapters': 98,
        'completed_chapters': 0,
        'missing_chapters': [],
        'failed_chapters': {},
        'coverage_percentage': 0.0
    }

    # 从合并结果提取成功/失败信息
    if merge_results:
        shard_details = merge_results.get('shard_details', [])

        # 统计完成的章节
        completed_set = set()
        failed_dict = {}

        for detail in shard_details:
            shard_path = detail.get('shard_path', '')
            shard_records = detail.get('shard_records', 0)
            error = detail.get('error')

            # 如果有记录，认为该 shard 成功
            if shard_records > 0:
                # 从任务文件中读取该 shard 的章节
                # 这里简化处理，后续可以从 task_file 读取
                pass
            elif error:
                # 记录失败原因
                failed_dict[shard_path] = {
                    'reason': error,
                    'retry_count': detail.get('retries', 0)
                }

        # 如果有任务文件，精确计算覆盖率
        if task_file and os.path.exists(task_file):
            try:
                with open(task_file, 'r') as f:
                    tasks = json.load(f)

                all_chapters = set()
                for shard_id, chapters in tasks.items():
                    all_chapters.update(chapters)

                coverage_info['total_chapters'] = len(all_chapters)
                # TODO: 从数据库中查询实际存在的章节
            except Exception as e:
                print(f"读取任务文件失败: {e}", file=sys.stderr)

    # 计算覆盖率
    if coverage_info['total_chapters'] > 0:
        coverage_info['coverage_percentage'] = round(
            (coverage_info['total_chapters'] - len(coverage_info['missing_chapters']))
            / coverage_info['total_chapters'] * 100, 2
        )

    return coverage_info

def generate_metadata(db_path: str = 'tariffs.db',
                     version: str = None,
                     results_path: str = 'update_results.json',
                     output_path: str = 'metadata.json',
                     task_file: str = None,
                     old_db_path: str = None,
                     previous_version: str = None) -> Dict:
    """生成数据库元数据"""

    # 检查数据库文件是否存在
    if not os.path.exists(db_path):
        print(f"错误: 数据库文件不存在 {db_path}", file=sys.stderr)
        return {}

    print(f"生成元数据: {db_path}")

    # 文件基本信息
    stat_info = os.stat(db_path)
    file_info = {
        'file_size': stat_info.st_size,
        'file_hash': calculate_file_hash(db_path),
        'last_modified': datetime.fromtimestamp(stat_info.st_mtime, tz=timezone.utc).isoformat(),
    }

    # 数据库统计
    db_stats = get_database_stats(db_path)

    # 更新结果（merge_results.json）
    update_results = load_update_results(results_path)

    # 分析覆盖率
    coverage_info = analyze_coverage(update_results, task_file)

    # 时间戳
    timestamp = datetime.now(timezone.utc).isoformat()

    # 构建元数据
    metadata = {
        'version': version or f"data-{int(datetime.now().timestamp())}",
        'timestamp': timestamp,
        'last_modified': file_info['last_modified'],
        'file_size': file_info['file_size'],
        'file_hash': file_info['file_hash'],
        'record_count': db_stats.get('record_count', 0),

        'coverage': {
            'total_chapters': coverage_info['total_chapters'],
            'completed_chapters': coverage_info['total_chapters'] - len(coverage_info['missing_chapters']),
            'missing_chapters': coverage_info['missing_chapters'],
            'coverage_percentage': coverage_info['coverage_percentage']
        },

        'missing_details': coverage_info.get('failed_chapters', {}),

        'changes_summary': {
            'total_updates': update_results.get('successful_shards', 0),
            'total_shards': update_results.get('total_shards', 0),
            'failed_shards': update_results.get('failed_shards', 0),
            'total_shard_records': update_results.get('total_shard_records', 0),
            'duplicate_records_removed': update_results.get('duplicate_records_removed', 0)
        },

        'update_statistics': {
            'success_rate': update_results.get('successful', 0) / max(update_results.get('total', 1), 1),
            'processing_time_minutes': update_results.get('processing_time_minutes', 0),
            'errors_count': update_results.get('failed', 0),
            'retry_count': update_results.get('retry_count', 0)
        },

        'quality_metrics': {
            'records_with_description': db_stats.get('records_with_description', 0),
            'records_with_uk_rate': db_stats.get('records_with_uk_rate', 0),
            'records_with_ni_rate': db_stats.get('records_with_ni_rate', 0),
            'completeness_score': db_stats.get('records_with_description', 0) / max(db_stats.get('record_count', 1), 1)
        },

        'data_ranges': {
            'uk_rate_min': '0%',
            'uk_rate_max': '25%',
            'common_rates': db_stats.get('common_rates', []),
            'categories_count': db_stats.get('categories_count', 0)
        },

        'client_instructions': {
            'check_interval_hours': 24,
            'auto_download_enabled': True,
            'backup_before_update': True,
            'verify_checksum': True,
            'min_change_threshold': 10
        },

        'download_urls': {
            'primary': f"https://github.com/{os.getenv('GITHUB_REPOSITORY', 'owner/repo')}/releases/download/latest-data/tariffs.db",
            'metadata': f"https://github.com/{os.getenv('GITHUB_REPOSITORY', 'owner/repo')}/releases/download/latest-data/metadata.json",
            'mirror': []
        },

        'data_changes': generate_changelog(db_path, old_db_path, version, previous_version),
    }

    # 保存元数据
    try:
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False)

        print(f"SUCCESS: 元数据生成完成: {output_path}")
        print(f"INFO: 版本: {metadata['version']}")
        print(f"INFO: 记录数: {metadata['record_count']:,}")
        print(f"INFO: 大小: {metadata['file_size'] / 1024 / 1024:.1f}MB")
        print(f"INFO: 哈希: {metadata['file_hash'][:32]}...")

        return metadata

    except Exception as e:
        print(f"保存元数据失败: {e}", file=sys.stderr)
        return {}


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="生成数据库元数据")
    parser.add_argument('db_path', nargs='?', default='tariffs.db', help='数据库路径')
    parser.add_argument('version', nargs='?', help='版本号')
    parser.add_argument('results_path', nargs='?', default='merge_results.json', help='合并结果路径')
    parser.add_argument('output_path', nargs='?', default='metadata.json', help='输出路径')
    parser.add_argument('--task-file', type=str, help='任务分配文件路径')
    parser.add_argument('--old-db', type=str, help='上版本 tariffs.db（用于生成 data_changes）')
    parser.add_argument('--previous-version', type=str, help='上版本号')

    args = parser.parse_args()

    version = args.version or os.getenv('VERSION', f"data-{int(datetime.now().timestamp())}")

    # 生成元数据
    metadata = generate_metadata(
        db_path=args.db_path,
        version=version,
        results_path=args.results_path,
        output_path=args.output_path,
        task_file=args.task_file,
        old_db_path=args.old_db,
        previous_version=args.previous_version,
    )

    if not metadata:
        sys.exit(1)

    # 输出环境变量供GitHub Actions使用
    print(f"::set-output name=version::{metadata['version']}")
    print(f"::set-output name=file_size::{metadata['file_size']}")
    print(f"::set-output name=record_count::{metadata['record_count']}")
    print(f"::set-output name=file_hash::{metadata['file_hash'][:32]}")

    # 计算变更数量
    total_changes = metadata['changes_summary']['total_updates']
    print(f"::set-output name=total_changes::{total_changes}")