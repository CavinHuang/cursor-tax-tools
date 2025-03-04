import os
import sqlite3
import logging
from typing import List, Dict, Optional
import threading
from datetime import datetime

logger = logging.getLogger(__name__)

class TariffDB:
    def __init__(self, db_name: str = "tariffs.db"):
        # 确保 datas 目录存在
        self.data_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))), "datas")
        os.makedirs(self.data_dir, exist_ok=True)

        # 设置数据库文件路径
        self.db_path = os.path.join(self.data_dir, db_name)
        self._local = threading.local()
        self._create_tables()

        logger.info(f"数据库路径: {self.db_path}")

    @property
    def conn(self):
        """获取当前线程的数据库连接"""
        if not hasattr(self._local, 'conn'):
            self._local.conn = sqlite3.connect(self.db_path)
        return self._local.conn

    def _create_tables(self):
        """创建数据表"""
        try:
            with self.conn:
                # 商品表
                self.conn.execute("""
                    CREATE TABLE IF NOT EXISTS tariffs (
                        code TEXT PRIMARY KEY,
                        description TEXT,
                        rate TEXT,
                        url TEXT,
                        north_ireland_rate TEXT,
                        north_ireland_url TEXT,
                        updated_at TIMESTAMP
                    )
                """)

                # 抓取错误记录表
                self.conn.execute("""
                    CREATE TABLE IF NOT EXISTS scrape_errors (
                        code TEXT PRIMARY KEY,
                        error_message TEXT,
                        last_attempt TIMESTAMP
                    )
                """)

                # 配置表
                self.conn.execute("""
                    CREATE TABLE IF NOT EXISTS config (
                        key TEXT PRIMARY KEY,
                        value TEXT
                    )
                """)

                # 创建索引
                self.conn.execute("CREATE INDEX IF NOT EXISTS idx_code ON tariffs(code)")
                self.conn.execute("CREATE INDEX IF NOT EXISTS idx_error_code ON scrape_errors(code)")

        except Exception as e:
            logger.error(f"创建数据表失败: {str(e)}")
            raise

    def update_uk_tariff(self, code: str, description: str, rate: str, url: str):
        """更新英国关税信息"""
        try:
            with self.conn:
                self.conn.execute("""
                    INSERT OR REPLACE INTO tariffs
                    (code, description, rate, url, updated_at)
                    VALUES (?, ?, ?, ?, ?)
                """, (code, description, rate, url, datetime.now()))
        except Exception as e:
            logger.error(f"更新英国关税失败: {str(e)}")

    def update_north_ireland_tariff(self, code: str, rate: str, url: str):
        """更新北爱尔兰关税信息"""
        try:
            with self.conn:
                self.conn.execute("""
                    UPDATE tariffs
                    SET north_ireland_rate = ?,
                        north_ireland_url = ?,
                        updated_at = ?
                    WHERE code = ?
                """, (rate, url, datetime.now(), code))
        except Exception as e:
            logger.error(f"更新北爱尔兰关税失败: {str(e)}")

    def get_all_codes(self) -> List[str]:
        """获取所有商品编码"""
        try:
            with self.conn:
                cursor = self.conn.execute("SELECT code FROM tariffs")
                return [row[0] for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"获取商品编码失败: {str(e)}")
            return []

    def add_scrape_error(self, code: str, error_message: str):
        """添加抓取错误记录"""
        try:
            with self.conn:
                self.conn.execute("""
                    INSERT OR REPLACE INTO scrape_errors
                    (code, error_message, last_attempt)
                    VALUES (?, ?, ?)
                """, (code, error_message, datetime.now()))
        except Exception as e:
            logger.error(f"添加错误记录失败: {str(e)}")

    def get_scrape_errors(self) -> List[Dict]:
        """获取所有抓取错误记录"""
        try:
            with self.conn:
                cursor = self.conn.execute("""
                    SELECT code, error_message, last_attempt
                    FROM scrape_errors
                    ORDER BY last_attempt DESC
                """)
                return [
                    {
                        'code': row[0],
                        'error_message': row[1],
                        'last_attempt': row[2]
                    }
                    for row in cursor.fetchall()
                ]
        except Exception as e:
            logger.error(f"获取错误记录失败: {str(e)}")
            return []

    def clear_scrape_error(self, code: str):
        """清除指定编码的抓取错误记录"""
        try:
            with self.conn:
                self.conn.execute("DELETE FROM scrape_errors WHERE code = ?", (code,))
        except Exception as e:
            logger.error(f"清除错误记录失败: {str(e)}")

    def close(self):
        """关闭数据库连接"""
        if hasattr(self._local, 'conn'):
            self._local.conn.close()
            del self._local.conn

    def search_tariffs(self, code: str, fuzzy: bool = False) -> List[Dict]:
        """搜索关税信息"""
        try:
            with self.conn:
                if fuzzy:
                    # 模糊搜索
                    cursor = self.conn.execute("""
                        SELECT code, description, rate, north_ireland_rate
                        FROM tariffs
                        WHERE code LIKE ?
                        OR description LIKE ?
                        ORDER BY code
                    """, (f"%{code}%", f"%{code}%"))
                else:
                    # 精确搜索
                    cursor = self.conn.execute("""
                        SELECT code, description, rate, north_ireland_rate
                        FROM tariffs
                        WHERE code = ?
                    """, (code,))

                return [
                    {
                        'code': row[0],
                        'description': row[1],
                        'rate': row[2],
                        'north_ireland_rate': row[3]
                    }
                    for row in cursor.fetchall()
                ]
        except Exception as e:
            logger.error(f"搜索关税信息失败: {str(e)}")
            return []

    def save_config(self, key: str, value: str):
        """保存配置"""
        try:
            with self.conn:
                self.conn.execute("""
                    INSERT OR REPLACE INTO config (key, value)
                    VALUES (?, ?)
                """, (key, value))
        except Exception as e:
            logger.error(f"保存配置失败: {str(e)}")

    def get_config(self, key: str, default: str = "") -> str:
        """获取配置"""
        try:
            with self.conn:
                cursor = self.conn.execute(
                    "SELECT value FROM config WHERE key = ?",
                    (key,)
                )
                if row := cursor.fetchone():
                    return row[0]
                return default
        except Exception as e:
            logger.error(f"获取配置失败: {str(e)}")
            return default