"""
生成数据库元数据文件的脚本
用于客户端智能判断是否需要更新数据库
"""

import hashlib
import json
import os
import sqlite3
from datetime import datetime, timezone
from typing import Dict, Optional
import gzip

def calculate_file_hash(file_path: str, algorithm: str = 'sha256') -> str:
    """计算文件哈希值"""
    hash_func = getattr(hashlib, algorithm)()

    with open(file_path, 'rb') as f:
        while chunk := f.read(8192):
            hash_func.update(chunk)

    return f"{algorithm}:{hash_func.hexdigest()}"

def get_database_stats(db_path: str) -> Dict:
    """获取数据库统计信息"""
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        stats = {}

        # 基本统计
        stats['record_count'] = cursor.execute("SELECT COUNT(*) FROM tariffs").fetchone()[0]

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

        # 税率分布统计
        rate_dist = cursor.execute("""
            SELECT rate, COUNT(*) as count
            FROM tariffs
            WHERE rate IS NOT NULL AND rate != ''
            GROUP BY rate
            ORDER BY count DESC
            LIMIT 10
        """).fetchall()

        stats['common_rates'] = [rate for rate, count in rate_dist]

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

        # 分类统计（如果有分类信息）
        try:
            stats['categories_count'] = cursor.execute("""
                SELECT COUNT(DISTINCT SUBSTR(code, 1, 2)) FROM tariffs
            """).fetchone()[0]
        except:
            stats['categories_count'] = 0

        # 更新历史统计（如果有历史表）
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
            error_count = cursor.execute("SELECT COUNT(*) FROM scrape_errors").fetchone()[0]
            stats['active_errors'] = error_count
        except:
            stats['active_errors'] = 0

        conn.close()
        return stats

    except Exception as e:
        print(f"❌ 获取数据库统计失败: {str(e)}")
        return {}

def get_file_info(file_path: str) -> Dict:
    """获取文件基本信息"""
    if not os.path.exists(file_path):
        return {}

    stat_info = os.stat(file_path)

    return {
        'file_size': stat_info.st_size,
        'file_hash': calculate_file_hash(file_path),
        'last_modified': datetime.fromtimestamp(stat_info.st_mtime, tz=timezone.utc).isoformat(),
    }

def load_update_results(results_path: str = 'update_results.json') -> Dict:
    """加载更新结果"""
    try:
        if os.path.exists(results_path):
            with open(results_path, 'r', encoding='utf-8') as f:
                return json.load(f)
    except Exception as e:
        print(f"⚠️ 无法加载更新结果: {str(e)}")

    return {}

def generate_metadata(db_path: str = 'tariffs.db',
                     version: str = None,
                     results_path: str = 'update_results.json',
                     output_path: str = 'metadata.json',
                     repo_info: Dict = None) -> Dict:
    """生成数据库元数据"""

    print("🔍 生成数据库元数据...")

    # 基本文件信息
    file_info = get_file_info(db_path)
    if not file_info:
        raise FileNotFoundError(f"数据库文件不存在: {db_path}")

    # 数据库统计信息
    db_stats = get_database_stats(db_path)

    # 更新结果信息
    update_results = load_update_results(results_path)

    # 生成时间戳
    timestamp = datetime.now(timezone.utc).isoformat()

    # 构建元数据
    metadata = {
        # 版本信息
        'version': version or f"data-{int(datetime.now().timestamp())}",
        'timestamp': timestamp,
        'last_modified': file_info.get('last_modified', timestamp),

        # 文件信息
        'file_size': file_info['file_size'],
        'file_hash': file_info['file_hash'],

        # 数据库统计
        'record_count': db_stats.get('record_count', 0),

        # 更新统计
        'changes_summary': {
            'total_updates': update_results.get('successful', 0),
            'uk_updated': update_results.get('uk_updated', 0),
            'ni_updated': update_results.get('ni_updated', 0),
            'new_records': 0,  # 需要对比历史数据计算
            'deleted_records': 0,  # 需要对比历史数据计算
            'modified_records': update_results.get('uk_updated', 0) + update_results.get('ni_updated', 0)
        },

        'update_statistics': {
            'success_rate': update_results.get('successful', 0) / max(update_results.get('total', 1), 1),
            'processing_time_minutes': update_results.get('processing_time_minutes', 0),
            'errors_count': update_results.get('failed', 0),
            'retry_count': update_results.get('retry_count', 0)
        },

        # 数据质量指标
        'quality_metrics': {
            'records_with_description': db_stats.get('records_with_description', 0),
            'records_with_uk_rate': db_stats.get('records_with_uk_rate', 0),
            'records_with_ni_rate': db_stats.get('records_with_ni_rate', 0),
            'completeness_score': db_stats.get('records_with_description', 0) / max(db_stats.get('record_count', 1), 1)
        },

        # 数据分布信息
        'data_ranges': {
            'uk_rate_min': db_stats.get('uk_rate_min', '0%'),
            'uk_rate_max': db_stats.get('uk_rate_max', '0%'),
            'common_rates': db_stats.get('common_rates', []),
            'categories_count': db_stats.get('categories_count', 0)
        },

        # 客户端配置建议
        'client_instructions': {
            'check_interval_hours': 24,
            'auto_download_enabled': True,
            'backup_before_update': True,
            'verify_checksum': True,
            'min_change_threshold': 10  # 少于10条变更可跳过更新
        }
    }

    # 添加仓库信息
    if repo_info:
        owner = repo_info.get('owner', 'unknown')
        repo = repo_info.get('repo', 'unknown')

        metadata['download_urls'] = {
            'primary': f"https://github.com/{owner}/{repo}/releases/download/latest-data/tariffs.db",
            'metadata': f"https://github.com/{owner}/{repo}/releases/download/latest-data/metadata.json",
            'mirror': []  # 可以添加CDN镜像地址
        }

    # 保存元数据文件
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(metadata, f, indent=2, ensure_ascii=False)

    print(f"✅ 元数据生成完成: {output_path}")
    print(f"📊 数据库大小: {file_info['file_size'] / 1024 / 1024:.1f}MB")
    print(f"📝 记录数量: {db_stats.get('record_count', 0):,}")
    print(f"🔒 文件哈希: {file_info['file_hash'][:20]}...")

    return metadata

def compress_file(input_path: str, output_path: str = None) -> str:
    """压缩文件"""
    if output_path is None:
        output_path = f"{input_path}.gz"

    with open(input_path, 'rb') as f_in:
        with gzip.open(output_path, 'wb') as f_out:
            f_out.writelines(f_in)

    original_size = os.path.getsize(input_path)
    compressed_size = os.path.getsize(output_path)
    ratio = (1 - compressed_size / original_size) * 100

    print(f"🗜️ 文件压缩完成: {output_path}")
    print(f"📊 压缩率: {ratio:.1f}% ({original_size / 1024 / 1024:.1f}MB → {compressed_size / 1024 / 1024:.1f}MB)")

    return output_path

if __name__ == "__main__":
    # 示例用法
    repo_info = {
        'owner': os.getenv('GITHUB_REPOSITORY_OWNER', 'your-username'),
        'repo': os.getenv('GITHUB_REPOSITORY_NAME', 'your-repo')
    }

    # 从环境变量获取版本信息
    version = os.getenv('VERSION', f"data-{int(datetime.now().timestamp())}")

    # 生成元数据
    metadata = generate_metadata(
        db_path='tariffs.db',
        version=version,
        repo_info=repo_info
    )

    # 可选：压缩元数据（如果需要更小的文件）
    # compress_file('metadata.json', 'metadata.json.gz')