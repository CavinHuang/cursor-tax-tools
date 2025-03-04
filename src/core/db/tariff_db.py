import sqlite3
import logging
from typing import List, Dict, Optional
import threading
from datetime import datetime

logger = logging.getLogger(__name__)

class TariffDB:
    def __init__(self, db_path: str = "tariffs.db"):
        self.db_path = db_path
        self._local = threading.local()
        self._create_tables()

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