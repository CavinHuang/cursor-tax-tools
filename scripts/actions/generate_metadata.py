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

        # 常见税率
        rate_dist = cursor.execute("""
            SELECT rate, COUNT(*) as count
            FROM tariffs
            WHERE rate IS NOT NULL AND rate != ''
            GROUP BY rate
            ORDER BY count DESC
            LIMIT 5
        """).fetchall()

        stats['common_rates'] = [rate for rate, count in rate_dist]

        # 分类统计
        try:
            stats['categories_count'] = cursor.execute("""
                SELECT COUNT(DISTINCT SUBSTR(code, 1, 2)) FROM tariffs
            """).fetchone()[0]
        except:
            pass

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


def generate_metadata(db_path: str = 'tariffs.db',
                     version: str = None,
                     results_path: str = 'update_results.json',
                     output_path: str = 'metadata.json') -> Dict:
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

    # 更新结果
    update_results = load_update_results(results_path)

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

        'changes_summary': {
            'total_updates': update_results.get('successful', 0),
            'uk_updated': update_results.get('uk_updated', 0),
            'ni_updated': update_results.get('ni_updated', 0),
            'new_records': 0,
            'deleted_records': 0,
            'modified_records': update_results.get('uk_updated', 0) + update_results.get('ni_updated', 0)
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
        }
    }

    # 保存元数据
    try:
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False)

        print(f"✅ 元数据生成完成: {output_path}")
        print(f"📊 版本: {metadata['version']}")
        print(f"📝 记录数: {metadata['record_count']:,}")
        print(f"💾 大小: {metadata['file_size'] / 1024 / 1024:.1f}MB")
        print(f"🔒 哈希: {metadata['file_hash'][:32]}...")

        return metadata

    except Exception as e:
        print(f"保存元数据失败: {e}", file=sys.stderr)
        return {}


if __name__ == "__main__":
    # 解析命令行参数
    db_path = sys.argv[1] if len(sys.argv) > 1 else 'tariffs.db'
    version = sys.argv[2] if len(sys.argv) > 2 else os.getenv('VERSION', f"data-{int(datetime.now().timestamp())}")
    results_path = sys.argv[3] if len(sys.argv) > 3 else 'update_results.json'
    output_path = sys.argv[4] if len(sys.argv) > 4 else 'metadata.json'

    # 生成元数据
    metadata = generate_metadata(
        db_path=db_path,
        version=version,
        results_path=results_path,
        output_path=output_path
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