"""
智能更新客户端
基于元数据文件判断是否需要更新数据库
"""

import requests
import json
import os
import hashlib
import sqlite3
from datetime import datetime, timezone
from typing import Dict, Optional, Tuple
import logging

logger = logging.getLogger(__name__)

class SmartUpdateChecker:
    """智能更新检查器"""

    def __init__(self, metadata_url: str, db_path: str = 'tariffs.db'):
        self.metadata_url = metadata_url
        self.db_path = db_path
        self.local_metadata_path = f"{db_path}.metadata.json"

    def download_metadata(self, timeout: int = 30) -> Optional[Dict]:
        """下载远程元数据"""
        try:
            logger.info(f"📡 下载元数据: {self.metadata_url}")
            response = requests.get(self.metadata_url, timeout=timeout)
            response.raise_for_status()

            metadata = response.json()
            logger.info(f"✅ 元数据下载成功: 版本 {metadata.get('version')}")
            return metadata

        except requests.RequestException as e:
            logger.error(f"❌ 元数据下载失败: {str(e)}")
            return None
        except json.JSONDecodeError as e:
            logger.error(f"❌ 元数据解析失败: {str(e)}")
            return None

    def load_local_metadata(self) -> Optional[Dict]:
        """加载本地元数据"""
        try:
            if os.path.exists(self.local_metadata_path):
                with open(self.local_metadata_path, 'r', encoding='utf-8') as f:
                    metadata = json.load(f)
                logger.info(f"📂 加载本地元数据: 版本 {metadata.get('version')}")
                return metadata
        except Exception as e:
            logger.error(f"❌ 加载本地元数据失败: {str(e)}")

        return None

    def save_local_metadata(self, metadata: Dict):
        """保存本地元数据"""
        try:
            with open(self.local_metadata_path, 'w', encoding='utf-8') as f:
                json.dump(metadata, f, indent=2, ensure_ascii=False)
            logger.info(f"💾 保存本地元数据: 版本 {metadata.get('version')}")
        except Exception as e:
            logger.error(f"❌ 保存本地元数据失败: {str(e)}")

    def get_local_db_info(self) -> Dict:
        """获取本地数据库信息"""
        if not os.path.exists(self.db_path):
            return {'exists': False}

        try:
            stat_info = os.stat(self.db_path)

            # 计算本地文件哈希
            hash_sha256 = hashlib.sha256()
            with open(self.db_path, 'rb') as f:
                while chunk := f.read(8192):
                    hash_sha256.update(chunk)

            # 获取数据库记录数
            try:
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()
                record_count = cursor.execute("SELECT COUNT(*) FROM tariffs").fetchone()[0]
                conn.close()
            except:
                record_count = 0

            return {
                'exists': True,
                'file_size': stat_info.st_size,
                'file_hash': f"sha256:{hash_sha256.hexdigest()}",
                'last_modified': datetime.fromtimestamp(stat_info.st_mtime, tz=timezone.utc).isoformat(),
                'record_count': record_count
            }

        except Exception as e:
            logger.error(f"❌ 获取本地数据库信息失败: {str(e)}")
            return {'exists': False, 'error': str(e)}

    def check_update_needed(self, remote_metadata: Dict, local_db_info: Dict, local_metadata: Dict = None) -> Tuple[bool, str, Dict]:
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

        # 4. 检查更新时间
        remote_time = remote_metadata.get('timestamp')
        local_time = local_db_info.get('last_modified')

        if remote_time and local_time:
            try:
                remote_dt = datetime.fromisoformat(remote_time.replace('Z', '+00:00'))
                local_dt = datetime.fromisoformat(local_time.replace('Z', '+00:00'))

                if remote_dt > local_dt:
                    reasons.append(f"远程数据更新时间更新: {remote_time} > {local_time}")
                    # 如果时间更新但哈希相同，可能是元数据更新，不强制数据库更新
                    if not update_needed:
                        reasons.append("仅元数据更新，数据库文件无需更新")
                        return False, " | ".join(reasons), {'priority': 'low'}
            except ValueError:
                logger.warning("⚠️ 时间戳解析失败")

        # 5. 检查变更数量阈值
        changes_summary = remote_metadata.get('changes_summary', {})
        min_threshold = remote_metadata.get('client_instructions', {}).get('min_change_threshold', 10)
        total_changes = changes_summary.get('total_updates', 0)

        if total_changes < min_threshold and update_needed:
            reasons.append(f"变更数量({total_changes})少于阈值({min_threshold})，可跳过更新")
            update_needed = False

        # 6. 检查数据完整性
        if local_db_info.get('record_count', 0) != remote_metadata.get('record_count', 0):
            update_needed = True
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

    def download_database(self, download_url: str, verify_checksum: bool = True) -> bool:
        """下载数据库文件"""
        try:
            logger.info(f"📥 开始下载数据库: {download_url}")

            # 备份现有文件
            if os.path.exists(self.db_path):
                backup_path = f"{self.db_path}.backup"
                os.replace(self.db_path, backup_path)
                logger.info(f"💾 创建备份: {backup_path}")

            # 下载文件
            response = requests.get(download_url, stream=True, timeout=300)  # 5分钟超时
            response.raise_for_status()

            total_size = int(response.headers.get('content-length', 0))
            downloaded_size = 0

            with open(self.db_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        downloaded_size += len(chunk)

                        # 显示下载进度
                        if total_size > 0:
                            progress = (downloaded_size / total_size) * 100
                            print(f"\r📥 下载进度: {progress:.1f}%", end="", flush=True)

            print()  # 换行
            logger.info(f"✅ 数据库下载完成: {downloaded_size / 1024 / 1024:.1f}MB")

            # 验证文件完整性
            if verify_checksum:
                logger.info("🔒 验证文件完整性...")
                remote_metadata = self.download_metadata()
                if remote_metadata:
                    local_info = self.get_local_db_info()
                    if local_info.get('file_hash') != remote_metadata.get('file_hash'):
                        logger.error("❌ 文件完整性验证失败")
                        if os.path.exists(backup_path):
                            os.replace(backup_path, self.db_path)
                        return False

            logger.info("✅ 数据库更新完成")
            return True

        except Exception as e:
            logger.error(f"❌ 数据库下载失败: {str(e)}")
            # 恢复备份
            if os.path.exists(f"{self.db_path}.backup"):
                os.replace(f"{self.db_path}.backup", self.db_path)
            return False

    def check_and_update(self, force_update: bool = False) -> Dict:
        """检查并执行更新"""
        result = {
            'status': 'unknown',
            'message': '',
            'details': {}
        }

        try:
            # 下载远程元数据
            remote_metadata = self.download_metadata()
            if not remote_metadata:
                result['status'] = 'error'
                result['message'] = '无法下载远程元数据'
                return result

            # 获取本地信息
            local_db_info = self.get_local_db_info()
            local_metadata = self.load_local_metadata()

            # 检查是否需要更新
            if not force_update:
                update_needed, reason, check_details = self.check_update_needed(
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
            logger.info(f"🔄 检测到需要更新: {reason}")
            download_urls = remote_metadata.get('download_urls', {})
            download_url = download_urls.get('primary')

            if not download_url:
                result['status'] = 'error'
                result['message'] = '无法获取下载链接'
                return result

            # 下载数据库
            if self.download_database(download_url):
                # 保存新的元数据
                self.save_local_metadata(remote_metadata)

                result['status'] = 'updated'
                result['message'] = f"更新完成: {reason}"
                result['details']['new_version'] = remote_metadata.get('version')
                return result
            else:
                result['status'] = 'error'
                result['message'] = '数据库下载失败'
                return result

        except Exception as e:
            logger.error(f"❌ 检查更新失败: {str(e)}")
            result['status'] = 'error'
            result['message'] = f'检查更新失败: {str(e)}'
            return result

# 使用示例
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

    # 配置元数据URL（实际使用时替换为真实的GitHub Release URL）
    METADATA_URL = "https://github.com/owner/repo/releases/download/latest-data/metadata.json"

    # 创建更新检查器
    checker = SmartUpdateChecker(METADATA_URL)

    # 检查并更新
    result = checker.check_and_update()

    print(f"\n🎯 更新结果: {result['status']}")
    print(f"📝 消息: {result['message']}")

    if result['details']:
        print(f"\n📊 详细信息:")
        for key, value in result['details'].items():
            print(f"  {key}: {value}")