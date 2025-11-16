#!/usr/bin/env python3
"""
智能更新客户端脚本
基于元数据文件判断是否需要更新数据库
"""

import argparse
import json
import logging
import os
import sys
from datetime import datetime

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

try:
    import requests
    import sqlite3
    import hashlib
    from typing import Dict, Optional, Tuple
except ImportError as e:
    print(f"❌ 缺少依赖: {e}", file=sys.stderr)
    print("💡 请安装: pip install requests", file=sys.stderr)
    sys.exit(1)


def setup_logging(verbose: bool = False):
    """设置日志"""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )


def download_metadata(metadata_url: str, timeout: int = 30) -> Optional[Dict]:
    """下载远程元数据"""
    try:
        logging.info(f"📡 下载元数据: {metadata_url}")
        response = requests.get(metadata_url, timeout=timeout)
        response.raise_for_status()

        metadata = response.json()
        logging.info(f"✅ 元数据下载成功: 版本 {metadata.get('version')}")
        return metadata

    except requests.RequestException as e:
        logging.error(f"❌ 元数据下载失败: {str(e)}")
        return None
    except json.JSONDecodeError as e:
        logging.error(f"❌ 元数据解析失败: {str(e)}")
        return None


def load_local_metadata(local_metadata_path: str) -> Optional[Dict]:
    """加载本地元数据"""
    try:
        if os.path.exists(local_metadata_path):
            with open(local_metadata_path, 'r', encoding='utf-8') as f:
                metadata = json.load(f)
            logging.info(f"📂 加载本地元数据: 版本 {metadata.get('version')}")
            return metadata
    except Exception as e:
        logging.error(f"❌ 加载本地元数据失败: {str(e)}")

    return None


def save_local_metadata(metadata: Dict, local_metadata_path: str):
    """保存本地元数据"""
    try:
        with open(local_metadata_path, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False)
        logging.info(f"💾 保存本地元数据: 版本 {metadata.get('version')}")
    except Exception as e:
        logging.error(f"❌ 保存本地元数据失败: {str(e)}")


def calculate_file_hash(file_path: str) -> str:
    """计算文件哈希值"""
    hash_sha256 = hashlib.sha256()
    try:
        with open(file_path, 'rb') as f:
            while chunk := f.read(8192):
                hash_sha256.update(chunk)
        return f"sha256:{hash_sha256.hexdigest()}"
    except FileNotFoundError:
        return "sha256:unknown"
    except Exception as e:
        logging.error(f"计算文件哈希失败: {e}")
        return "sha256:error"


def get_local_db_info(db_path: str) -> Dict:
    """获取本地数据库信息"""
    if not os.path.exists(db_path):
        return {'exists': False}

    try:
        stat_info = os.stat(db_path)

        # 计算本地文件哈希
        local_hash = calculate_file_hash(db_path)

        # 获取数据库记录数
        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            record_count = cursor.execute("SELECT COUNT(*) FROM tariffs").fetchone()[0]
            conn.close()
        except:
            record_count = 0

        return {
            'exists': True,
            'file_size': stat_info.st_size,
            'file_hash': local_hash,
            'last_modified': datetime.fromtimestamp(stat_info.st_mtime).isoformat(),
            'record_count': record_count
        }

    except Exception as e:
        logging.error(f"获取本地数据库信息失败: {e}")
        return {'exists': False, 'error': str(e)}


def check_update_needed(remote_metadata: Dict, local_db_info: Dict, local_metadata: Dict = None) -> Tuple[bool, str, Dict]:
    """检查是否需要更新"""
    reasons = []
    update_needed = False

    # 1. 检查文件是否存在
    if not local_db_info.get('exists'):
        update_needed = True
        reasons.append("本地数据库文件不存在")
        return True, " | ".join(reasons), {'priority': 'high'}

    # 2. 检查版本号
    remote_version = remote_metadata.get('version')
    local_version = local_metadata.get('version') if local_metadata else None

    if remote_version != local_version:
        update_needed = True
        reasons.append(f"版本不匹配: {local_version} → {remote_version}")

    # 3. 检查文件哈希
    remote_hash = remote_metadata.get('file_hash')
    local_hash = local_db_info.get('file_hash')

    if remote_hash != local_hash:
        update_needed = True
        reasons.append("文件内容已变更")

    # 4. 检查变更数量阈值
    changes_summary = remote_metadata.get('changes_summary', {})
    min_threshold = remote_metadata.get('client_instructions', {}).get('min_change_threshold', 10)
    total_changes = changes_summary.get('total_updates', 0)

    if total_changes < min_threshold and update_needed and reasons == ["文件内容已变更"]:
        reasons.append(f"变更数量({total_changes})少于阈值({min_threshold})，可跳过更新")
        update_needed = False

    # 5. 检查记录数量
    if local_db_info.get('record_count', 0) != remote_metadata.get('record_count', 0):
        update_needed = True
        if not any("记录数量" in reason for reason in reasons):
            reasons.append(f"记录数量不匹配: {local_db_info.get('record_count')} → {remote_metadata.get('record_count')}")

    # 确定更新优先级
    priority = 'medium'
    if update_needed:
        if any("不存在" in reason or "不匹配" in reason for reason in reasons):
            priority = 'high'
        elif total_changes > 100:
            priority = 'high'
        elif total_changes > 50:
            priority = 'medium'
        else:
            priority = 'low'

    return update_needed, " | ".join(reasons) if reasons else "无需更新", {'priority': priority}


def download_database(download_url: str, db_path: str, verify_checksum: bool = True, backup: bool = True) -> bool:
    """下载数据库文件"""
    try:
        logging.info(f"📥 开始下载数据库: {download_url}")

        # 备份现有文件
        if backup and os.path.exists(db_path):
            backup_path = f"{db_path}.backup.{int(datetime.now().timestamp())}"
            os.replace(db_path, backup_path)
            logging.info(f"💾 创建备份: {backup_path}")

        # 下载文件
        response = requests.get(download_url, stream=True, timeout=300)
        response.raise_for_status()

        total_size = int(response.headers.get('content-length', 0))
        downloaded_size = 0

        with open(db_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
                    downloaded_size += len(chunk)

                    # 显示下载进度
                    if total_size > 0:
                        progress = (downloaded_size / total_size) * 100
                        print(f"\r📥 下载进度: {progress:.1f}%", end="", flush=True)

        print()  # 换行
        logging.info(f"✅ 数据库下载完成: {downloaded_size / 1024 / 1024:.1f}MB")

        return True

    except Exception as e:
        logging.error(f"❌ 数据库下载失败: {str(e)}")
        return False


def check_and_update(metadata_url: str, db_path: str = 'tariffs.db', force_update: bool = False,
                   dry_run: bool = False, verbose: bool = False) -> Dict:
    """检查并执行更新"""
    setup_logging(verbose)

    local_metadata_path = f"{db_path}.metadata.json"
    result = {
        'status': 'unknown',
        'message': '',
        'details': {}
    }

    try:
        # 下载远程元数据
        remote_metadata = download_metadata(metadata_url)
        if not remote_metadata:
            result['status'] = 'error'
            result['message'] = '无法下载远程元数据'
            return result

        # 获取本地信息
        local_db_info = get_local_db_info(db_path)
        local_metadata = load_local_metadata(local_metadata_path)

        # 检查是否需要更新
        if not force_update:
            update_needed, reason, check_details = check_update_needed(
                remote_metadata, local_db_info, local_metadata
            )
        else:
            update_needed = True
            reason = "强制更新"
            check_details = {'priority': 'high'}

        result['details'] = {
            'remote_version': remote_metadata.get('version'),
            'local_version': local_metadata.get('version') if local_metadata else None,
            'remote_record_count': remote_metadata.get('record_count'),
            'local_record_count': local_db_info.get('record_count'),
            'remote_file_size': remote_metadata.get('file_size'),
            'local_file_size': local_db_info.get('file_size'),
            'changes_summary': remote_metadata.get('changes_summary'),
            'priority': check_details.get('priority')
        }

        if not update_needed:
            result['status'] = 'up_to_date'
            result['message'] = reason
            return result

        # 需要更新
        logging.info(f"🔄 检测到需要更新: {reason}")

        if dry_run:
            result['status'] = 'dry_run_update_needed'
            result['message'] = f"[DRY RUN] 需要更新: {reason}"
            return result

        download_urls = remote_metadata.get('download_urls', {})
        download_url = download_urls.get('primary')

        if not download_url:
            result['status'] = 'error'
            result['message'] = '无法获取下载链接'
            return result

        # 下载数据库
        if download_database(download_url, db_path):
            # 保存新的元数据
            save_local_metadata(remote_metadata, local_metadata_path)

            result['status'] = 'updated'
            result['message'] = f"更新完成: {reason}"
            result['details']['new_version'] = remote_metadata.get('version')
            return result
        else:
            result['status'] = 'error'
            result['message'] = '数据库下载失败'
            return result

    except Exception as e:
        logging.error(f"❌ 检查更新失败: {str(e)}")
        result['status'] = 'error'
        result['message'] = f'检查更新失败: {str(e)}'
        return result


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description='智能更新客户端 - 关税数据库更新工具')
    parser.add_argument('metadata_url', nargs='?',
                       default='https://github.com/owner/repo/releases/download/latest-data/metadata.json',
                       help='元数据文件URL')
    parser.add_argument('--db-path', '-d', default='tariffs.db',
                       help='本地数据库文件路径 (默认: tariffs.db)')
    parser.add_argument('--force', '-f', action='store_true',
                       help='强制更新，忽略检查')
    parser.add_argument('--dry-run', '-n', action='store_true',
                       help='模拟运行，只检查不更新')
    parser.add_argument('--verbose', '-v', action='store_true',
                       help='详细输出')
    parser.add_argument('--version', action='version', version='%(prog)s 1.0.0')

    args = parser.parse_args()

    # 检查并更新
    result = check_and_update(
        metadata_url=args.metadata_url,
        db_path=args.db_path,
        force_update=args.force,
        dry_run=args.dry_run,
        verbose=args.verbose
    )

    # 输出结果
    print(f"\n🎯 更新结果: {result['status']}")
    print(f"📝 消息: {result['message']}")

    if result['details'] and args.verbose:
        print(f"\n📊 详细信息:")
        for key, value in result['details'].items():
            if isinstance(value, dict):
                print(f"  {key}:")
                for sub_key, sub_value in value.items():
                    print(f"    {sub_key}: {sub_value}")
            else:
                print(f"  {key}: {value}")

    # 设置退出码
    if result['status'] == 'error':
        sys.exit(1)
    elif result['status'] == 'updated':
        sys.exit(0)
    elif result['status'] == 'dry_run_update_needed':
        sys.exit(2)  # 特殊退出码表示需要更新
    else:
        sys.exit(0)


if __name__ == "__main__":
    main()