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
                    url TEXT
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
                "SELECT code, description, rate, url FROM tariffs WHERE code = ?",
                (code,)
            )
            row = cur.fetchone()
            if row:
                return {
                    'code': row[0],
                    'description': row[1],
                    'rate': row[2],
                    'url': row[3]
                }
            return None
        except Exception as e:
            logger.error(f"查询记录失败: {str(e)}")
            raise

    def get_all_tariffs(self) -> List[Dict]:
        """获取所有关税记录"""
        try:
            cur = self.conn.execute("SELECT code, description, rate, url FROM tariffs")
            return [
                {
                    'code': row[0],
                    'description': row[1],
                    'rate': row[2],
                    'url': row[3]
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