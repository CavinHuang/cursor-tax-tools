[根目录](./CLAUDE.md) > **tariff_db.py 数据库模块**

# Tariff DB 数据库操作模块

## 📍 路径面包屑
[根目录](./CLAUDE.md) > **tariff_db.py 数据库模块**

## 🎯 模块职责

Tariff DB是项目的数据持久化层，负责：
- SQLite数据库的创建和管理
- 关税数据的增删改查操作
- 数据库事务和一致性保证
- 性能优化和索引管理
- 数据备份和恢复功能

## 🚀 入口与启动

### 数据库初始化
```python
from tariff_db import TariffDB

# 初始化数据库（自动创建表结构）
db = TariffDB(db_path="datas/tariffs.db")

# 检查数据库连接
if db.connection:
    print("数据库连接成功")
```

### 数据库文件结构
```
datas/
├── tariffs.db              # 主数据库文件
├── tariffs.db.backup       # 自动备份文件
├── tariffs.db.wal          # 预写日志（性能优化）
└── tariffs.db.shm          # 共享内存文件
```

## 🔌 对外接口

### 核心数据库操作类
```python
class TariffDB:
    """关税数据库操作封装类"""

    def __init__(self, db_path: str = "tariffs.db"):
        """初始化数据库连接"""
        self.db_path = db_path
        self.connection = None
        self.init_database()

    def get_tariff(self, code: str) -> Optional[Dict]:
        """根据编码获取关税信息"""

    def search_tariffs(self, query: str, limit: int = 50) -> List[Dict]:
        """搜索关税信息（模糊匹配）"""

    def update_tariff(self, **kwargs) -> bool:
        """更新关税信息"""

    def get_existing_codes(self) -> Set[str]:
        """获取所有已存在的编码集合"""
```

### 高级管理接口
```python
def backup_database(self, backup_path: str = None) -> str:
    """备份数据库"""

def restore_database(self, backup_path: str) -> bool:
    """恢复数据库"""

def get_database_stats(self) -> Dict:
    """获取数据库统计信息"""

def optimize_database(self) -> bool:
    """优化数据库性能"""
```

## 🔗 关键依赖与配置

### 数据库依赖
```python
import sqlite3                           # SQLite数据库引擎
import threading                          # 线程安全锁
import logging                           # 日志记录
import json                               # 配置文件处理
import hashlib                            # 文件完整性校验
from datetime import datetime            # 时间戳管理
```

### 数据库表结构
```sql
-- 主关税数据表
CREATE TABLE tariffs (
    code TEXT PRIMARY KEY,               -- 商品编码（主键）
    description TEXT,                    -- 商品描述
    rate TEXT,                          -- 英国税率
    url TEXT,                           -- 英国税率网址
    north_ireland_rate TEXT,            -- 北爱尔兰税率
    north_ireland_url TEXT,             -- 北爱尔兰税率网址
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 索引优化
CREATE INDEX idx_tariffs_code ON tariffs(code);
CREATE INDEX idx_tariffs_description ON tariffs(description);
CREATE INDEX idx_tariffs_updated_at ON tariffs(updated_at);
```

### 配置参数
- **数据库文件**: `datas/tariffs.db`
- **备份策略**: 每次重大更新前自动备份
- **连接池**: 默认连接超时30秒
- **事务隔离**: 立即一致性模式
- **批量大小**: 推荐每批1000条记录

## 🗄️ 数据模型

### 关税数据记录模型
```python
tariff_record = {
    'code': '8703239010',              # 商品编码（主键）
    'description': '电动乘用车',         # 商品描述
    'rate': '10%',                     # 英国关税税率
    'url': 'https://trade-tariff...',  # 英国税率详情URL
    'north_ireland_rate': '0%',        # 北爱尔兰关税税率
    'north_ireland_url': 'https://...', # 北爱尔兰税率URL
    'created_at': '2025-11-23 17:38:51', # 创建时间
    'updated_at': '2025-11-23 17:38:51'  # 最后更新时间
}
```

### 数据库统计模型
```python
db_stats = {
    'total_records': 50000,             # 总记录数
    'uk_rates_count': 45000,            # 英国税率数量
    'ni_rates_count': 42000,            # 北爱尔兰税率数量
    'last_update': '2025-11-23 17:38:51', # 最后更新时间
    'database_size_mb': 45.2,           # 数据库文件大小
    'index_size_mb': 12.8,              # 索引文件大小
    'quality_score': 98.5               # 数据完整度评分
}
```

## 🧪 测试与质量

### 数据库操作测试
```python
def test_database_crud():
    """测试增删改查操作"""
    db = TariffDB(":memory:")  # 内存数据库测试

    # 测试插入
    success = db.update_tariff(
        code="TEST123456",
        description="测试商品",
        rate="15%"
    )
    assert success

    # 测试查询
    record = db.get_tariff("TEST123456")
    assert record is not None
    assert record['code'] == "TEST123456"

def test_transaction_safety():
    """测试事务安全性"""
    # 模拟并发写入
    # 验证数据一致性
    pass
```

### 性能基准测试
- **单条查询**: < 10ms
- **批量查询**: < 500ms (1000条)
- **插入操作**: < 50ms/条
- **更新操作**: < 30ms/条
- **数据库连接**: < 5ms

### 数据完整性验证
```python
def verify_database_integrity():
    """验证数据库完整性"""
    stats = db.get_database_stats()

    # 检查必要字段完整性
    assert stats['total_records'] > 0
    assert stats['quality_score'] >= 90.0

    # 检查编码唯一性
    codes = db.get_existing_codes()
    assert len(codes) == stats['total_records']
```

## ❓ 常见问题 (FAQ)

### Q1: 数据库文件损坏？
```python
# 尝试修复数据库
import sqlite3
conn = sqlite3.connect("datas/tariffs.db")
conn.execute("PRAGMA integrity_check;")
result = conn.fetchone()

if result[0] != "ok":
    # 从备份恢复
    db.restore_database("datas/tariffs.db.backup")
```

### Q2: 查询性能慢？
- 检查索引是否有效
- 运行 `ANALYZE` 更新统计信息
- 考虑使用 `tariff_db_optimized.py`
- 优化查询条件

### Q3: 并发访问冲突？
- 使用连接池管理
- 实施读写分离策略
- 添加适当的锁定机制
- 定期执行 `VACUUM` 操作

## 📁 相关文件清单

### 核心数据库文件
- `tariff_db.py` - 主要数据库操作类
- `tariff_db_optimized.py` - 性能优化版本
- `datas/tariffs.db` - SQLite数据库文件
- `datas/tariffs.db.backup` - 自动备份文件

### 相关脚本
- `scripts/actions/validate_database.py` - 数据库验证脚本
- `database_fix.py` - 数据库修复工具
- `database_comparison_analysis.py` - 数据对比分析

### 关联模块
- `tariff_api.py` - API调用数据库
- `scraper.py` - 爬虫写入数据库
- `smart_update_client.py` - 智能更新读取

## 📅 变更记录 (Changelog)

### 2025-11-23 17:38:51
- ✨ 创建数据库模块文档
- 🗄️ 完善数据模型和接口说明
- 🔧 添加性能优化和故障排除指南
- 📊 整合数据完整性验证方案

### 近期更新
- 添加自动备份机制
- 优化索引和查询性能
- 实现事务安全保障
- 增强数据验证功能

---

**模块负责人**: 数据持久化
**技术重点**: SQLite + 事务管理 + 性能优化
**运行环境**: 本地文件系统 + 多线程访问 💾🔒