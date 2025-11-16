import sqlite3
import logging
import asyncio
from typing import List, Dict, Optional, AsyncIterator
import threading
from datetime import datetime
import json

logger = logging.getLogger(__name__)

class OptimizedTariffDB:
    """优化版关税数据库 - 支持批量操作、性能监控、索引优化"""

    def __init__(self, db_path: str = "tariffs.db"):
        self.db_path = db_path
        self._local = threading.local()
        self._batch_buffer = []
        self._batch_size = 1000
        self._create_tables_with_indexes()

    @property
    def conn(self) -> sqlite3.Connection:
        """获取当前线程的数据库连接（连接池优化）"""
        if not hasattr(self._local, "conn"):
            self._local.conn = sqlite3.connect(
                self.db_path,
                timeout=30.0,  # 30秒超时
                check_same_thread=False,
                isolation_level=None  # 自动提交模式
            )
            # 优化SQLite性能
            self._local.conn.execute("PRAGMA journal_mode=WAL")  # 写时日志模式
            self._local.conn.execute("PRAGMA synchronous=NORMAL")  # 平衡性能和安全
            self._local.conn.execute("PRAGMA cache_size=10000")  # 增大缓存
            self._local.conn.execute("PRAGMA temp_store=memory")  # 临时表存储在内存

        return self._local.conn

    def _create_tables_with_indexes(self):
        """创建数据表和性能优化索引"""
        try:
            with self.conn:
                # 主表
                self.conn.execute("""
                CREATE TABLE IF NOT EXISTS tariffs (
                    code TEXT PRIMARY KEY,
                    description TEXT,
                    rate TEXT,
                    url TEXT,
                    north_ireland_rate TEXT,
                    north_ireland_url TEXT,
                    other_rate TEXT,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    version INTEGER DEFAULT 1
                )
                """)

                # 错误记录表（优化版）
                self.conn.execute("""
                CREATE TABLE IF NOT EXISTS scrape_errors (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    code TEXT NOT NULL,
                    error_message TEXT,
                    error_type TEXT DEFAULT 'network',
                    retry_count INTEGER DEFAULT 0,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(code, timestamp)
                )
                """)

                # 更新历史表（新增）
                self.conn.execute("""
                CREATE TABLE IF NOT EXISTS update_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    code TEXT NOT NULL,
                    field_name TEXT NOT NULL,
                    old_value TEXT,
                    new_value TEXT,
                    update_type TEXT NOT NULL,  -- 'uk', 'ni', 'both'
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                )
                """)

                # 性能索引
                indexes = [
                    "CREATE INDEX IF NOT EXISTS idx_tariffs_code ON tariffs(code)",
                    "CREATE INDEX IF NOT EXISTS idx_tariffs_description ON tariffs(description)",
                    "CREATE INDEX IF NOT EXISTS idx_tariffs_rate ON tariffs(rate)",
                    "CREATE INDEX IF NOT EXISTS idx_tariffs_ni_rate ON tariffs(north_ireland_rate)",
                    "CREATE INDEX IF NOT EXISTS idx_tariffs_updated_at ON tariffs(updated_at)",
                    "CREATE INDEX IF NOT EXISTS idx_errors_code ON scrape_errors(code)",
                    "CREATE INDEX IF NOT EXISTS idx_errors_timestamp ON scrape_errors(timestamp)",
                    "CREATE INDEX IF NOT EXISTS idx_errors_type ON scrape_errors(error_type)",
                    "CREATE INDEX IF NOT EXISTS idx_history_code ON update_history(code)",
                    "CREATE INDEX IF NOT EXISTS idx_history_timestamp ON update_history(timestamp)",
                    "CREATE UNIQUE INDEX IF NOT EXISTS idx_errors_unique ON scrape_errors(code, timestamp)"
                ]

                for idx_sql in indexes:
                    self.conn.execute(idx_sql)

                logger.info("✅ 数据库表和索引创建完成")

        except Exception as e:
            logger.error(f"❌ 创建表和索引失败: {str(e)}")
            raise

    def add_tariff_with_history(self, code: str, description: str, rate: str,
                               url: str = None, other_rate: str = None,
                               north_ireland_rate: str = None, north_ireland_url: str = None,
                               update_type: str = 'uk'):
        """添加关税记录并记录历史变更"""
        try:
            # 获取旧数据用于历史记录
            old_data = self.get_tariff(code)

            with self.conn:
                # 更新主表
                self.conn.execute("""
                    INSERT OR REPLACE INTO tariffs
                    (code, description, rate, url, other_rate, north_ireland_rate, north_ireland_url, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (code, description, rate, url, other_rate, north_ireland_rate, north_ireland_url, datetime.now()))

                # 记录变更历史
                if old_data:
                    changes = []
                    if old_data['rate'] != rate:
                        changes.append(('rate', old_data['rate'], rate))
                    if old_data['description'] != description:
                        changes.append(('description', old_data['description'], description))
                    if old_data.get('north_ireland_rate') != north_ireland_rate:
                        changes.append(('north_ireland_rate', old_data.get('north_ireland_rate'), north_ireland_rate))

                    for field, old_val, new_val in changes:
                        self.conn.execute("""
                            INSERT INTO update_history (code, field_name, old_value, new_value, update_type)
                            VALUES (?, ?, ?, ?, ?)
                        """, (code, field, old_val, new_val, update_type))

        except Exception as e:
            logger.error(f"❌ 添加记录失败 {code}: {str(e)}")
            raise

    def add_tariffs_batch_optimized(self, tariffs: List[Dict], batch_size: int = 1000):
        """高性能批量添加关税记录"""
        try:
            total_added = 0

            for i in range(0, len(tariffs), batch_size):
                batch = tariffs[i:i + batch_size]

                with self.conn:
                    # 使用事务提高性能
                    self.conn.executemany("""
                        INSERT OR REPLACE INTO tariffs
                        (code, description, rate, url, other_rate, north_ireland_rate, north_ireland_url, updated_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """, [
                        (
                            t['code'], t['description'], t['rate'],
                            t.get('url'), t.get('other_rate'),
                            t.get('north_ireland_rate'), t.get('north_ireland_url'),
                            datetime.now()
                        ) for t in batch
                    ])

                total_added += len(batch)
                logger.info(f"✅ 批量添加完成 {total_added}/{len(tariffs)} 条记录")

        except Exception as e:
            logger.error(f"❌ 批量添加失败: {str(e)}")
            raise

    def get_tariffs_pagination(self, offset: int = 0, limit: int = 1000,
                              filter_by_rate: str = None) -> List[Dict]:
        """分页获取关税记录（支持筛选）"""
        try:
            sql = """
                SELECT code, description, rate, url, north_ireland_url, north_ireland_rate, updated_at
                FROM tariffs
            """
            params = []

            if filter_by_rate:
                sql += " WHERE rate = ?"
                params.append(filter_by_rate)

            sql += " ORDER BY updated_at DESC LIMIT ? OFFSET ?"
            params.extend([limit, offset])

            cur = self.conn.execute(sql, params)
            return [
                {
                    'code': row[0],
                    'description': row[1],
                    'rate': row[2],
                    'url': row[3],
                    'north_ireland_url': row[4],
                    'north_ireland_rate': row[5],
                    'updated_at': row[6]
                }
                for row in cur.fetchall()
            ]
        except Exception as e:
            logger.error(f"❌ 分页查询失败: {str(e)}")
            raise

    def get_statistics(self) -> Dict:
        """获取数据库统计信息"""
        try:
            stats = {}

            # 基本统计
            stats['total_records'] = self.conn.execute("SELECT COUNT(*) FROM tariffs").fetchone()[0]
            stats['unique_rates'] = self.conn.execute("SELECT COUNT(DISTINCT rate) FROM tariffs").fetchone()[0]
            stats['records_with_ni_rate'] = self.conn.execute(
                "SELECT COUNT(*) FROM tariffs WHERE north_ireland_rate IS NOT NULL AND north_ireland_rate != ''"
            ).fetchone()[0]

            # 最近更新
            stats['last_update'] = self.conn.execute(
                "SELECT MAX(updated_at) FROM tariffs"
            ).fetchone()[0]

            # 错误统计
            error_stats = self.conn.execute("""
                SELECT error_type, COUNT(*) as count
                FROM scrape_errors
                WHERE timestamp > datetime('now', '-7 days')
                GROUP BY error_type
            """).fetchall()

            stats['recent_errors'] = {row[0]: row[1] for row in error_stats}

            # 更新频率统计
            update_stats = self.conn.execute("""
                SELECT DATE(updated_at) as update_date, COUNT(*) as count
                FROM tariffs
                WHERE updated_at > datetime('now', '-30 days')
                GROUP BY DATE(updated_at)
                ORDER BY update_date DESC
                LIMIT 7
            """).fetchall()

            stats['recent_updates'] = {row[0]: row[1] for row in update_stats}

            return stats

        except Exception as e:
            logger.error(f"❌ 获取统计信息失败: {str(e)}")
            return {}

    def clean_old_errors(self, days: int = 30):
        """清理旧的错误记录"""
        try:
            with self.conn:
                result = self.conn.execute(
                    "DELETE FROM scrape_errors WHERE timestamp < datetime('now', '-{} days')".format(days)
                )
                deleted_count = result.rowcount
                logger.info(f"✅ 清理了 {deleted_count} 条旧错误记录")
                return deleted_count
        except Exception as e:
            logger.error(f"❌ 清理错误记录失败: {str(e)}")
            return 0

    def optimize_database(self):
        """优化数据库（VACUUM 和 ANALYZE）"""
        try:
            with self.conn:
                self.conn.execute("VACUUM")  # 重新组织数据库文件
                self.conn.execute("ANALYZE")  # 更新查询优化器统计信息
            logger.info("✅ 数据库优化完成")
        except Exception as e:
            logger.error(f"❌ 数据库优化失败: {str(e)}")

    def export_to_json(self, output_file: str, include_history: bool = False):
        """导出数据为JSON格式"""
        try:
            data = {
                'export_time': datetime.now().isoformat(),
                'statistics': self.get_statistics(),
                'tariffs': self.get_all_tariffs()
            }

            if include_history:
                # 导出更新历史
                cur = self.conn.execute("""
                    SELECT code, field_name, old_value, new_value, update_type, timestamp
                    FROM update_history
                    ORDER BY timestamp DESC
                    LIMIT 10000
                """)
                data['update_history'] = [
                    {
                        'code': row[0],
                        'field': row[1],
                        'old_value': row[2],
                        'new_value': row[3],
                        'type': row[4],
                        'timestamp': row[5]
                    }
                    for row in cur.fetchall()
                ]

            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

            logger.info(f"✅ 数据导出完成: {output_file}")

        except Exception as e:
            logger.error(f"❌ 数据导出失败: {str(e)}")
            raise

    # 兼容性方法（保持与原API一致）
    def add_tariff(self, code: str, description: str, rate: str, url: str = None, other_rate: str = None):
        """兼容性方法 - 添加关税记录"""
        self.add_tariff_with_history(code, description, rate, url, other_rate)

    def get_tariff(self, code: str) -> Optional[Dict]:
        """兼容性方法 - 获取单个关税记录"""
        try:
            cur = self.conn.execute("""
                SELECT code, description, rate, url, north_ireland_rate, north_ireland_url, other_rate, updated_at
                FROM tariffs WHERE code = ?
            """, (code,))
            row = cur.fetchone()
            if row:
                return {
                    'code': row[0],
                    'description': row[1],
                    'rate': row[2],
                    'url': row[3],
                    'north_ireland_rate': row[4],
                    'north_ireland_url': row[5],
                    'other_rate': row[6],
                    'updated_at': row[7]
                }
            return None
        except Exception as e:
            logger.error(f"❌ 查询记录失败: {str(e)}")
            raise

    def get_all_tariffs(self) -> List[Dict]:
        """兼容性方法 - 获取所有关税记录"""
        try:
            cur = self.conn.execute("""
                SELECT code, description, rate, url, north_ireland_url, north_ireland_rate, other_rate
                FROM tariffs
            """)
            return [
                {
                    'code': row[0],
                    'description': row[1],
                    'rate': row[2],
                    'url': row[3],
                    'north_ireland_url': row[4],
                    'north_ireland_rate': row[5],
                    'other_rate': row[6]
                }
                for row in cur.fetchall()
            ]
        except Exception as e:
            logger.error(f"❌ 获取所有记录失败: {str(e)}")
            raise

    def add_tariffs_batch(self, tariffs: List[Dict]):
        """兼容性方法 - 批量添加关税记录"""
        self.add_tariffs_batch_optimized(tariffs)

    def get_record_count(self) -> int:
        """兼容性方法 - 获取记录数"""
        try:
            cur = self.conn.execute("SELECT COUNT(*) FROM tariffs")
            return cur.fetchone()[0]
        except Exception as e:
            logger.error(f"❌ 获取记录数失败: {str(e)}")
            raise