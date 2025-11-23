[根目录](../CLAUDE.md) > [scripts](./) > **自动化脚本模块**

# Scripts 自动化脚本模块

## 📍 路径面包屑
[根目录](../CLAUDE.md) > [scripts](./) > **自动化脚本模块**

## 🎯 模块职责

Scripts模块是项目的自动化核心，负责：
- GitHub Actions工作流支持
- 智能数据更新系统
- 系统性能监控
- 运维工具和配置管理

## 🚀 入口与启动

### 主要入口脚本
```bash
# GitHub Actions工作流
python scripts/actions/run_scraper.py
python scripts/actions/generate_metadata.py

# 智能更新客户端
python scripts/clients/smart_update_client.py

# 性能监控
python scripts/monitoring/performance_monitor.py
```

### 配置驱动启动
大部分脚本支持配置文件驱动：
- `tools/scraper_config.json` - 全局配置
- 环境变量控制 - GitHub Actions集成
- 命令行参数 - 灵活运行

## 🔌 对外接口

### GitHub Actions接口
- **actions/run_scraper.py**: 执行数据爬取的主要入口
- **actions/generate_metadata.py**: 生成数据库元数据
- **actions/validate_database.py**: 数据库完整性验证
- **actions/execute_scraping.py**: 爬虫执行包装器

### 客户端接口
- **clients/smart_update_client.py**: 智能更新客户端主类
  ```python
  from scripts.clients.smart_update_client import SmartUpdateChecker

  checker = SmartUpdateChecker(metadata_url, db_path)
  result = checker.check_and_update()
  ```

### 监控接口
- **monitoring/performance_monitor.py**: 性能监控主程序
- **monitoring/simple_monitor.py**: 轻量级监控工具

## 🔗 关键依赖与配置

### 外部依赖
```python
# 核心依赖
import aiohttp, asyncio, requests
import pandas, numpy
import sqlite3, hashlib, json
import psutil, prometheus_client
import backoff, structlog
```

### 配置文件结构
```json
{
  "scraper": {
    "batch_size": 100,
    "delay_between_batches": 0.2,
    "max_retries": 3
  },
  "performance": {
    "memory_threshold": "2GB",
    "cpu_threshold": 80
  },
  "update": {
    "force_update_threshold": 100,
    "backup_enabled": true
  }
}
```

### GitHub Actions集成
- 支持环境变量配置
- 自动输出状态变量
- 与Release系统集成
- 支持条件执行

## 🗄️ 数据模型

### 元数据结构
```json
{
  "version": "data-123",
  "timestamp": "2025-11-23T17:38:51Z",
  "record_count": 50000,
  "hash": "sha256:...",
  "size_mb": 45.2,
  "quality_score": 98.5,
  "regions": ["uk", "northern_ireland"],
  "update_priority": "medium"
}
```

### 监控数据结构
```json
{
  "timestamp": "2025-11-23T17:38:51Z",
  "cpu_percent": 45.2,
  "memory_mb": 1024,
  "disk_usage": 67.8,
  "network_io": {
    "bytes_sent": 1048576,
    "bytes_recv": 2097152
  },
  "processes": [
    {
      "name": "scraper.py",
      "cpu_percent": 12.3,
      "memory_mb": 256
    }
  ]
}
```

## 🧪 测试与质量

### 测试覆盖
- **单元测试**: 每个独立函数
- **集成测试**: 端到端流程
- **性能测试**: 监控工具精度
- **模拟测试**: GitHub Actions环境

### 质量保证
- 错误处理和重试机制
- 数据完整性验证
- 性能阈值监控
- 日志记录和审计

## ❓ 常见问题 (FAQ)

### Q1: 智能更新失败怎么办？
```bash
# 检查网络连接
curl -I "https://github.com/owner/repo/releases/download/latest-data/metadata.json"

# 强制更新
python scripts/clients/smart_update_client.py --force-update --verbose

# 检查权限
gh auth status
```

### Q2: 爬虫性能优化建议？
- 调整`batch_size`配置
- 使用优化版爬虫 `scraper_optimized.py`
- 启用并发处理
- 监控系统资源使用

### Q3: GitHub Actions调试？
- 查看Actions日志输出
- 检查环境变量设置
- 验证GitHub token权限
- 模拟本地运行

## 📁 相关文件清单

### actions/
- `run_scraper.py` - 爬虫执行主程序
- `generate_metadata.py` - 元数据生成器
- `validate_database.py` - 数据库验证
- `execute_scraping.py` - 爬虫包装器

### clients/
- `smart_update_client.py` - 智能更新客户端

### monitoring/
- `performance_monitor.py` - 性能监控主程序
- `simple_monitor.py` - 轻量级监控

### tools/
- `cleanup_releases.py` - GitHub Release清理工具
- `scraper_config.json` - 全局配置文件

## 📅 变更记录 (Changelog)

### 2025-11-23 17:38:51
- ✨ 创建Scripts模块文档
- 🏗️ 完善模块架构说明
- 📋 添加配置和使用指南
- 🔧 集成FAQ和故障排除

### 近期更新
- 添加智能更新客户端
- 优化GitHub Actions集成
- 增强性能监控功能
- 完善配置管理系统

---

**模块负责人**: 自动化系统
**技术重点**: GitHub Actions + Python自动化 + 监控运维
**运行环境**: CI/CD + 生产服务器 + 开发环境 🚀🔧