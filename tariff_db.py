import sqlite3
import logging
from typing import List, Dict, Optional
import threading

logger = logging.getLogger(__name__)

class TariffDB:
    def __init__(self, db_path: str = "tariffs.db"):
        self.db_path = db_path
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
                    north_ireland_url TEXT
                )
                """)
                # 添加错误记录表
                self.conn.execute("""
                CREATE TABLE IF NOT EXISTS scrape_errors (
                    code TEXT PRIMARY KEY,
                    error_message TEXT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                )
                """)
                # 添加索引
                self.conn.execute("CREATE INDEX IF NOT EXISTS idx_code ON tariffs(code)")
        except Exception as e:
            logger.error(f"创建表失败: {str(e)}")
            raise

    def add_tariff(self, code: str, description: str, rate: str, url: str = None):
        """添加关税记录"""
        if url is None:
            url = f"https://www.trade-tariff.service.gov.uk/commodities/{code}"
        try:
            with self.conn:
                self.conn.execute(
                    "INSERT OR REPLACE INTO tariffs (code, description, rate, url) VALUES (?, ?, ?, ?)",
                    (code, description, rate, url)
                )
        except Exception as e:
            logger.error(f"添加记录失败: {str(e)}")
            raise

    def get_tariff(self, code: str) -> Optional[Dict]:
        """精确查询关税记录"""
        try:
            cur = self.conn.execute(
                "SELECT code, description, rate, url, north_ireland_rate, north_ireland_url FROM tariffs WHERE code = ?",
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
                    'north_ireland_url': row[5]
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
                    "INSERT OR REPLACE INTO tariffs (code, description, rate, url) VALUES (?, ?, ?, ?)",
                    [(t['code'], t['description'], t['rate'], t.get('url')) for t in tariffs]
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

    def update_north_ireland_tariff(self, code: str, rate: str, url: str):
        """更新北爱尔兰关税信息"""
        try:
            with self.conn:
                self.conn.execute("""
                    UPDATE tariffs
                    SET north_ireland_rate = ?, north_ireland_url = ?
                    WHERE code = ?
                """, (rate, url, code))
        except Exception as e:
            logger.error(f"更新北爱尔兰关税失败: {str(e)}")

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

    def get_scrape_errors(self) -> List[Dict]:
        """获取所有抓取错误记录"""
        try:
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

    def get_all_codes(self) -> List[str]:
        """获取所有商品编码"""
        try:
            with self.conn:
                cursor = self.conn.execute("SELECT code FROM tariffs")
                return [row[0] for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"获取商品编码失败: {str(e)}")
            return []

    def update_uk_tariff(self, code: str, description: str, rate: str, url: str):
        """更新英国关税信息"""
        try:
            with self.conn:
                self.conn.execute("""
                    UPDATE tariffs
                    SET description = ?, rate = ?, url = ?
                    WHERE code = ?
                """, (description, rate, url, code))
        except Exception as e:
            logger.error(f"更新英国关税失败: {str(e)}")