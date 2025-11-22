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

    def _has_column(self, table_name: str, column_name: str) -> bool:
        """检查表是否包含指定列"""
        try:
            cursor = self.conn.cursor()
            cursor.execute(f"PRAGMA table_info({table_name})")
            columns = cursor.fetchall()
            return any(col[1] == column_name for col in columns)
        except Exception:
            return False

    def _create_tables_with_indexes(self):
        """创建数据表和性能优化索引"""
        try:
            with self.conn:
                # 主表 - 兼容现有数据库
                self.conn.execute("""
                CREATE TABLE IF NOT EXISTS tariffs (
                    code TEXT PRIMARY KEY,
                    description TEXT,
                    rate TEXT,
                    url TEXT,
                    north_ireland_rate TEXT,
                    north_ireland_url TEXT,
                    other_rate TEXT,
                    version INTEGER DEFAULT 1
                )
                """)

                # 检查并添加 updated_at 列
                try:
                    self.conn.execute("ALTER TABLE tariffs ADD COLUMN updated_at DATETIME DEFAULT CURRENT_TIMESTAMP")
                    logger.info("Added updated_at column to tariffs table")
                except sqlite3.OperationalError as e:
                    if "duplicate column name" in str(e).lower():
                        logger.debug("updated_at column already exists, skipping")
                    else:
                        logger.error(f"Error adding updated_at column: {e}")

                # 错误记录表（优化版）
                self.conn.execute("""
                CREATE TABLE IF NOT EXISTS scrape_errors (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    code TEXT NOT NULL,
                    error_message TEXT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    retry_count INTEGER DEFAULT 0
                )
                """)

                # 更新历史表
                self.conn.execute("""
                CREATE TABLE IF NOT EXISTS update_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    update_type TEXT,
                    total_records INTEGER,
                    successful_records INTEGER,
                    failed_records INTEGER,
                    start_time DATETIME,
                    end_time DATETIME,
                    metadata TEXT
                )
                """)

                # 性能索引
                self._create_performance_indexes()

                logger.info("Optimized database tables and indexes created successfully")

        except Exception as e:
            logger.error(f"Failed to create tables and indexes: {str(e)}")
            raise

    def _create_performance_indexes(self):
        """创建性能优化索引"""
        indexes = [
            # 基础索引
            ("idx_tariffs_code", "CREATE INDEX IF NOT EXISTS idx_tariffs_code ON tariffs(code)"),

            # 查询优化索引
            ("idx_tariffs_rate", "CREATE INDEX IF NOT EXISTS idx_tariffs_rate ON tariffs(rate)"),
            ("idx_tariffs_ni_rate", "CREATE INDEX IF NOT EXISTS idx_tariffs_ni_rate ON tariffs(north_ireland_rate)"),

            # 错误处理索引
            ("idx_errors_code", "CREATE INDEX IF NOT EXISTS idx_errors_code ON scrape_errors(code)"),
            ("idx_errors_timestamp", "CREATE INDEX IF NOT EXISTS idx_errors_timestamp ON scrape_errors(timestamp)"),

            # 历史记录索引
            ("idx_history_type", "CREATE INDEX IF NOT EXISTS idx_history_type ON update_history(update_type)"),
            ("idx_history_start_time", "CREATE INDEX IF NOT EXISTS idx_history_start_time ON update_history(start_time)"),
        ]

        # 只有当 updated_at 列存在时才创建相关索引
        if self._has_column('tariffs', 'updated_at'):
            indexes.extend([
                ("idx_tariffs_updated_at", "CREATE INDEX IF NOT EXISTS idx_tariffs_updated_at ON tariffs(updated_at)"),
                ("idx_tariffs_updated_desc", "CREATE INDEX IF NOT EXISTS idx_tariffs_updated_desc ON tariffs(updated_at DESC)"),
            ])

        for index_name, sql in indexes:
            try:
                self.conn.execute(sql)
                logger.debug(f"Created index: {index_name}")
            except Exception as e:
                logger.warning(f"Failed to create index {index_name}: {e}")

    def get_tariffs_pagination(self, offset: int = 0, limit: int = 1000,
                              filter_by_rate: str = None) -> List[Dict]:
        """分页获取关税记录（支持筛选）"""
        try:
            # 动态构建SQL，根据列是否存在选择字段
            has_updated_at = self._has_column('tariffs', 'updated_at')

            if has_updated_at:
                sql = """
                    SELECT code, description, rate, url, north_ireland_url, north_ireland_rate, updated_at
                    FROM tariffs
                """
                order_by = " ORDER BY updated_at DESC"
            else:
                sql = """
                    SELECT code, description, rate, url, north_ireland_url, north_ireland_rate
                    FROM tariffs
                """
                order_by = " ORDER BY code"

            params = []

            if filter_by_rate:
                sql += " WHERE rate = ?"
                params.append(filter_by_rate)

            sql += f"{order_by} LIMIT ? OFFSET ?"
            params.extend([limit, offset])

            cursor = self.conn.execute(sql, params)
            rows = cursor.fetchall()

            results = []
            for row in rows:
                result = {
                    'code': row[0],
                    'description': row[1],
                    'rate': row[2],
                    'url': row[3],
                    'north_ireland_url': row[4],
                    'north_ireland_rate': row[5]
                }
                if has_updated_at and len(row) > 6:
                    result['updated_at'] = row[6]
                results.append(result)

            return results

        except Exception as e:
            logger.error(f"分页查询失败: {str(e)}")
            return []

    def get_statistics(self) -> Dict:
        """获取数据库统计信息"""
        try:
            stats = {}

            # 基础统计
            cursor = self.conn.cursor()
            stats['total_records'] = cursor.execute("SELECT COUNT(*) FROM tariffs").fetchone()[0]
            stats['records_with_description'] = cursor.execute(
                "SELECT COUNT(*) FROM tariffs WHERE description IS NOT NULL AND description != ''"
            ).fetchone()[0]
            stats['records_with_uk_rate'] = cursor.execute(
                "SELECT COUNT(*) FROM tariffs WHERE rate IS NOT NULL AND rate != ''"
            ).fetchone()[0]
            stats['records_with_ni_rate'] = cursor.execute(
                "SELECT COUNT(*) FROM tariffs WHERE north_ireland_rate IS NOT NULL AND north_ireland_rate != ''"
            ).fetchone()[0]

            # 错误统计
            stats['active_errors'] = cursor.execute("SELECT COUNT(*) FROM scrape_errors").fetchone()[0]

            # 如果有 updated_at 列，添加时间相关统计
            if self._has_column('tariffs', 'updated_at'):
                stats['last_update'] = cursor.execute(
                    "SELECT MAX(updated_at) FROM tariffs"
                ).fetchone()[0] or None

                # 更新频率统计
                update_stats = cursor.execute("""
                    SELECT DATE(updated_at) as update_date, COUNT(*) as count
                    FROM tariffs
                    WHERE updated_at > datetime('now', '-30 days')
                    GROUP BY DATE(updated_at)
                    ORDER BY update_date DESC
                """).fetchall()
                stats['recent_updates'] = [
                    {'date': row[0], 'count': row[1]} for row in update_stats
                ]
            else:
                stats['last_update'] = None
                stats['recent_updates'] = []

            logger.debug(f"Database statistics: {stats}")
            return stats

        except Exception as e:
            logger.error(f"获取统计信息失败: {str(e)}")
            return {}

    def optimize_database(self):
        """优化数据库性能"""
        try:
            with self.conn:
                # 分析表统计信息
                self.conn.execute("ANALYZE")

                # 清理碎片
                self.conn.execute("VACUUM")

                # 重建索引
                self._create_performance_indexes()

            logger.info("Database optimization completed")

        except Exception as e:
            logger.error(f"数据库优化失败: {str(e)}")

    def close(self):
        """关闭数据库连接"""
        if hasattr(self._local, "conn"):
            self._local.conn.close()
            del self._local.conn

    def __del__(self):
        """析构函数 - 自动关闭连接"""
        try:
            self.close()
        except:
            pass

# 兼容性别名
OptimizedBatchUpdateManager = None  # 这个类在scraper_optimized.py中定义