import sqlite3
import logging
import os
import sys
import shutil
from typing import List, Dict, Optional
import threading

logger = logging.getLogger(__name__)


def get_writable_db_path(db_path: str = "tariffs.db") -> str:
    """获取可写的数据库文件路径

    路径优先级：
    1. 绝对路径 → 直接使用
    2. 当前目录的数据库文件（如果存在）
    3. 当前目录（作为默认写入位置）
    4. 打包资源（仅用于初始化，复制到当前目录）

    Args:
        db_path: 数据库文件路径（相对或绝对）

    Returns:
        str: 可写的数据库文件绝对路径
    """
    # 1. 如果是绝对路径，直接返回
    if os.path.isabs(db_path):
        return db_path

    # 2. 检查当前目录是否已有数据库文件
    current_dir_db = os.path.abspath(db_path)
    if os.path.exists(current_dir_db):
        logger.info(f"✅ 使用当前目录的数据库: {current_dir_db}")
        return current_dir_db

    # 3. 检查是否在打包环境中，且当前目录没有数据库
    #    如果是，尝试从打包资源复制到当前目录（一次性初始化）
    if hasattr(sys, '_MEIPASS'):
        resource_db = os.path.join(sys._MEIPASS, os.path.basename(db_path))
        if os.path.exists(resource_db):
            try:
                # 复制到当前目录（而不是用户目录）
                shutil.copy2(resource_db, current_dir_db)
                logger.info(f"✅ 从打包资源初始化数据库到当前目录: {current_dir_db}")
                return current_dir_db
            except Exception as e:
                logger.warning(f"⚠️ 无法从打包资源复制数据库: {e}")

    # 4. 默认使用当前目录（不再强制使用用户目录）
    #    这确保所有脚本统一使用当前目录的数据库
    logger.info(f"ℹ️ 使用当前目录作为数据库路径: {current_dir_db}")
    return current_dir_db


class TariffDB:
    def __init__(self, db_path: str = "tariffs.db"):
        # 确保使用可写的数据库路径
        self.db_path = get_writable_db_path(db_path)
        self._local = threading.local()
        self._create_tables()

    @property
    def conn(self) -> sqlite3.Connection:
        """获取当前线程的数据库连接"""
        if not hasattr(self._local, "conn"):
            self._local.conn = sqlite3.connect(self.db_path)
        return self._local.conn

    def _create_tables(self):
        """创建数据表"""
        try:
            with self.conn:
                self.conn.execute("""
                CREATE TABLE IF NOT EXISTS tariffs (
                    code TEXT PRIMARY KEY,
                    description TEXT,
                    rate TEXT,
                    url TEXT,
                    north_ireland_rate TEXT,
                    north_ireland_url TEXT,
                    other_rate TEXT
                )
                """)

                # 检查是否需要添加other_rate字段（为了向后兼容旧版本数据库）
                try:
                    self.conn.execute("ALTER TABLE tariffs ADD COLUMN other_rate TEXT")
                    logger.info("✅ 成功添加other_rate列")
                except sqlite3.OperationalError as e:
                    if "duplicate column name" in str(e).lower():
                        logger.debug("ℹ️ other_rate列已存在，跳过")
                    else:
                        raise e

                # 创建索引
                self.conn.execute("CREATE INDEX IF NOT EXISTS idx_code ON tariffs(code)")

                # 添加错误记录表
                self.conn.execute("""
                CREATE TABLE IF NOT EXISTS scrape_errors (
                    code TEXT PRIMARY KEY,
                    error_message TEXT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                )
                """)

                logger.info("✅ 数据库表结构创建完成")
        except Exception as e:
            logger.error(f"创建表失败: {str(e)}")
            raise

    def add_tariff(self, code: str, description: str, rate: str, url: str = None, other_rate: str = None):
        """添加关税记录"""
        if url is None:
            url = f"https://www.trade-tariff.service.gov.uk/commodities/{code}"
        try:
            with self.conn:
                self.conn.execute(
                    "INSERT OR REPLACE INTO tariffs (code, description, rate, url, other_rate) VALUES (?, ?, ?, ?, ?)",
                    (code, description, rate, url, other_rate)
                )
        except Exception as e:
            logger.error(f"添加记录失败: {str(e)}")
            raise

    def get_tariff(self, code: str) -> Optional[Dict]:
        """精确查询关税记录"""
        try:
            cur = self.conn.execute(
                "SELECT code, description, rate, url, north_ireland_rate, north_ireland_url, other_rate FROM tariffs WHERE code = ?",
                (code,)
            )
            row = cur.fetchone()
            if row:
                return {
                    'code': row[0],
                    'description': row[1],
                    'rate': row[2],
                    'url': row[3],
                    'north_ireland_rate': row[4],
                    'north_ireland_url': row[5],
                    'other_rate': row[6]
                }
            return None
        except Exception as e:
            logger.error(f"查询记录失败: {str(e)}")
            raise

    def get_all_tariffs(self) -> List[Dict]:
        """获取所有关税记录"""
        try:
            cur = self.conn.execute("SELECT code, description, rate, url, north_ireland_url, north_ireland_rate FROM tariffs")
            return [
                {
                    'code': row[0],
                    'description': row[1],
                    'rate': row[2],
                    'url': row[3],
                    'north_ireland_url': row[4],
                    'north_ireland_rate': row[5]
                }
                for row in cur.fetchall()
            ]
        except Exception as e:
            logger.error(f"获取所有记录失败: {str(e)}")
            raise

    def get_record_count(self) -> int:
        """获取数据库中的记录数"""
        try:
            cur = self.conn.execute("SELECT COUNT(*) FROM tariffs")
            return cur.fetchone()[0]
        except Exception as e:
            logger.error(f"获取记录数失败: {str(e)}")
            raise

    def add_tariffs_batch(self, tariffs: List[Dict]):
        """批量添加关税记录"""
        try:
            with self.conn:
                self.conn.executemany(
                    "INSERT OR REPLACE INTO tariffs (code, description, rate, url, other_rate) VALUES (?, ?, ?, ?, ?)",
                    [(t['code'], t['description'], t['rate'], t.get('url'), t.get('other_rate')) for t in tariffs]
                )
        except Exception as e:
            logger.error(f"批量添加记录失败: {str(e)}")
            raise

    def save_to_db(self, tariffs: List[Dict]):
        """保存到数据库"""
        from tariff_db import TariffDB
        db = TariffDB()
        try:
            db.add_tariffs_batch(tariffs)
            logger.info(f"成功保存 {len(tariffs)} 条记录")
        except Exception as e:
            logger.error(f"保存记录失败: {str(e)}")

    def get_existing_codes(self) -> set:
        """获取已存在的所有商品编码"""
        try:
            cur = self.conn.execute("SELECT code FROM tariffs")
            return set(row[0] for row in cur.fetchall())
        except Exception as e:
            logger.error(f"获取已存在编码失败: {str(e)}")
            return set()
    def get_existing_codes_north_ireland(self) -> set:
        """获取已存在的所有北爱尔兰商品编码"""
        try:
            cur = self.conn.execute("SELECT code FROM tariffs WHERE north_ireland_rate IS NOT NULL")
            return set(row[0] for row in cur.fetchall())
        except Exception as e:
            logger.error(f"获取已存在北爱尔兰编码失败: {str(e)}")
            return set()

    def get_north_ireland_count(self) -> int:
        """获取有北爱尔兰数据的记录数量"""
        try:
            cur = self.conn.execute(
                "SELECT COUNT(*) FROM tariffs WHERE north_ireland_rate IS NOT NULL AND north_ireland_rate != ''"
            )
            return cur.fetchone()[0]
        except Exception as e:
            logger.error(f"获取北爱尔兰记录数量失败: {str(e)}")
            return 0

    def update_north_ireland_tariff(self, code: str, north_ireland_rate: str, north_ireland_url: str):
        try:
            with self.conn:
                self.conn.execute("UPDATE tariffs SET north_ireland_rate = ?, north_ireland_url = ? WHERE code = ?", (north_ireland_rate, north_ireland_url, code))
        except Exception as e:
            logger.error(f"更新北爱尔兰关税记录失败: {str(e)}")
            raise

    def update_tariff(self, code: str, description: str = None, rate: str = None, url: str = None,
                      north_ireland_rate: str = None, north_ireland_url: str = None, other_rate: str = None):
        """更新关税记录（支持部分字段更新）"""
        try:
            # 构建动态更新SQL
            updates = []
            params = []

            if description is not None:
                updates.append("description = ?")
                params.append(description)
            if rate is not None:
                updates.append("rate = ?")
                params.append(rate)
            if url is not None:
                updates.append("url = ?")
                params.append(url)
            if north_ireland_rate is not None:
                updates.append("north_ireland_rate = ?")
                params.append(north_ireland_rate)
            if north_ireland_url is not None:
                updates.append("north_ireland_url = ?")
                params.append(north_ireland_url)
            if other_rate is not None:
                updates.append("other_rate = ?")
                params.append(other_rate)

            if not updates:
                logger.warning("没有提供任何要更新的字段")
                return

            params.append(code)  # WHERE条件

            sql = f"UPDATE tariffs SET {', '.join(updates)} WHERE code = ?"
            with self.conn:
                self.conn.execute(sql, params)
            logger.info(f"成功更新商品编码 {code} 的记录")
        except Exception as e:
            logger.error(f"更新关税记录失败: {str(e)}")
            raise

    def delete_tariff(self, code: str):
        """删除关税记录"""
        try:
            with self.conn:
                # 删除tariffs表中的记录
                self.conn.execute("DELETE FROM tariffs WHERE code = ?", (code,))
                # 同时删除scrape_errors表中的错误记录
                self.conn.execute("DELETE FROM scrape_errors WHERE code = ?", (code,))
            logger.info(f"已删除商品编码 {code} 的记录")
        except Exception as e:
            logger.error(f"删除关税记录失败: {str(e)}")
            raise

    def add_scrape_error(self, code: str, error_message: str):
        """记录抓取错误"""
        try:
            with self.conn:
                self.conn.execute(
                    "INSERT OR REPLACE INTO scrape_errors (code, error_message) VALUES (?, ?)",
                    (code, error_message)
                )
        except Exception as e:
            logger.error(f"记录抓取错误失败: {str(e)}")

    def get_scrape_errors(self, code: str = None) -> List[Dict]:
        """获取抓取错误记录"""
        try:
            if code:
                # 获取指定编码的错误记录
                cur = self.conn.execute(
                    "SELECT code, error_message, timestamp FROM scrape_errors WHERE code = ?",
                    (code,)
                )
            else:
                # 获取所有错误记录
                cur = self.conn.execute(
                    "SELECT code, error_message, timestamp FROM scrape_errors"
                )

            return [
                {
                    'code': row[0],
                    'error_message': row[1],
                    'timestamp': row[2]
                }
                for row in cur.fetchall()
            ]
        except Exception as e:
            logger.error(f"获取抓取错误记录失败: {str(e)}")
            return []

    def clear_scrape_error(self, code: str):
        """清除指定编码的抓取错误记录"""
        try:
            with self.conn:
                self.conn.execute("DELETE FROM scrape_errors WHERE code = ?", (code,))
        except Exception as e:
            logger.error(f"清除抓取错误记录失败: {str(e)}")