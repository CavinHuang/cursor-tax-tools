# 📁 Scripts目录说明

这个目录包含了GitHub Actions工作流和智能更新系统所需的所有脚本文件。

## 📂 目录结构

```
scripts/
├── actions/                 # GitHub Actions专用脚本
│   ├── generate_metadata.py # 生成数据库元数据
│   └── run_scraper.py      # 执行数据爬取
├── clients/                 # 客户端工具
│   └── smart_update_client.py # 智能更新客户端
├── monitoring/              # 监控工具
│   └── performance_monitor.py  # 性能监控
├── tools/                   # 工具脚本
│   ├── cleanup_releases.py # Release清理工具
│   └── scraper_config.json  # 配置文件
└── README.md               # 本说明文件
```

## 🚀 核心脚本说明

### 1. actions/generate_metadata.py
**用途**: 生成数据库元数据文件，供客户端判断是否需要更新

```bash
# 基本用法
python scripts/actions/generate_metadata.py tariffs.db data-123 update_results.json metadata.json

# 输出环境变量供GitHub Actions使用
python scripts/actions/generate_metadata.py tariffs.db "$VERSION" update_results.json
```

**功能**:
- 计算数据库文件哈希值
- 统计记录数量和数据质量
- 生成版本信息
- 输出客户端配置建议

### 2. actions/run_scraper.py
**用途**: 执行关税数据爬取，支持原版和优化版

```bash
# 环境变量控制
USE_OPTIMIZED=true
INPUT_UPDATE_UK=true
INPUT_UPDATE_NI=true
INPUT_BATCH_SIZE=100
INPUT_DELAY=0.2

python scripts/actions/run_scraper.py
```

**功能**:
- 支持原版和优化版爬虫
- 自动选择合适的爬虫版本
- 输出详细的统计信息
- 保存结果到JSON文件

### 3. clients/smart_update_client.py
**用途**: 客户端智能更新工具

```bash
# 基本用法
python scripts/clients/smart_update_client.py https://github.com/owner/repo/releases/download/latest-data/metadata.json

# 高级用法
python scripts/clients/smart_update_client.py \
  --metadata-url "https://github.com/owner/repo/releases/download/latest-data/metadata.json" \
  --db-path "tariffs.db" \
  --verbose \
  --dry-run
```

**功能**:
- 仅下载几KB的元数据进行判断
- 智能比较版本、哈希、时间戳
- 支持强制更新和模拟运行
- 自动备份和完整性验证

### 4. monitoring/performance_monitor.py
**用途**: 系统性能监控工具

```bash
# 监控60秒
python scripts/monitoring/performance_monitor.py --duration 60

# 检查系统要求
python scripts/monitoring/performance_monitor.py --check

# 自定义输出文件和间隔
python scripts/monitoring/performance_monitor.py --duration 120 --interval 10 --output metrics.json
```

**功能**:
- 监控CPU、内存、磁盘、网络使用
- 进程级别的资源统计
- 输出性能指标JSON文件
- 系统要求检查

### 5. tools/cleanup_releases.py
**用途**: GitHub Release清理工具

```bash
# 清理旧Release（保留最新30个）
python scripts/tools/cleanup_releases.py --repo owner/repo --keep 30

# 分析Release情况
python scripts/tools/cleanup_releases.py --repo owner/repo --analyze

# 模拟运行
python scripts/tools/cleanup_releases.py --repo owner/repo --keep 30 --dry-run
```

**功能**:
- 清理指定数量的旧Release
- 分析Release存储使用情况
- 支持标签前缀过滤
- 模拟运行预览效果

## ⚙️ 配置文件

### tools/scraper_config.json
全局配置文件，包含：
- 爬虫设置（并发数、批量大小等）
- 性能配置（内存阈值、监控开关等）
- 更新策略（阈值、备份设置等）
- 数据库配置（优化、清理设置等）

## 🚀 智能更新流程

### 服务端（GitHub Actions - 精简版）
```yaml
# 当前使用的精简版工作流
.github/workflows/scrape-tariff.yml

# 1. 爬取数据（支持原版和优化版）
python scripts/actions/run_scraper.py

# 2. 基本统计检查
sqlite3 tariffs.db "SELECT COUNT(*) FROM tariffs;"

# 3. 生成元数据
python scripts/actions/generate_metadata.py tariffs.db data-${{ github.run_number }} update_results.json

# 4. 发布到Release（仅当有足够变更时）
# - metadata.json (几KB)
# - tariffs.db (完整数据库)
```

## 🚀 智能更新流程

### 服务端（GitHub Actions）
```yaml
# 1. 爬取数据
python scripts/actions/run_scraper.py

# 2. 生成元数据
python scripts/actions/generate_metadata.py tariffs.db data-${{ github.run_number }} update_results.json

# 3. 发布到Release（仅当有足够变更时）
# - metadata.json (几KB)
# - tariffs.db (完整数据库)
```

### 客户端使用
```python
from scripts.clients.smart_update_client import SmartUpdateChecker

checker = SmartUpdateChecker(
    metadata_url="https://github.com/owner/repo/releases/download/latest-data/metadata.json"
)
result = checker.check_and_update()

if result['status'] == 'updated':
    print("✅ 数据库已更新")
elif result['status'] == 'up_to_date':
    print("✨ 数据库已是最新版本")
```

## 📊 性能优化效果

| 指标 | 传统方式 | 智能更新方式 |
|------|----------|--------------|
| **检查速度** | 下载7MB+数据库 | 下载几KB元数据 |
| **网络流量** | 每次检查7MB+ | 仅需时7MB+ |
| **响应时间** | 数十秒 | 毫秒级 |
| **用户体验** | 慢速等待 | 即时响应 |

## 🛠️ 故障排除

### 常见问题

1. **元数据下载失败**
   ```bash
   curl -I "https://github.com/owner/repo/releases/download/latest-data/metadata.json"
   ```

2. **爬虫执行失败**
   ```bash
   # 检查依赖
   pip install -r requirements.txt
   pip install backoff psutil prometheus-client structlog
   ```

3. **权限问题**
   ```bash
   chmod +x scripts/**/*.py
   ```

4. **GitHub CLI认证**
   ```bash
   gh auth login
   ```

### 调试技巧

1. **启用详细输出**
   ```bash
   python scripts/clients/smart_update_client.py --verbose --metadata-url "..."
   ```

2. **模拟运行**
   ```bash
   python scripts/clients/smart_update_client.py --dry-run --metadata-url "..."
   ```

3. **检查系统资源**
   ```bash
   python scripts/monitoring/performance_monitor.py --check
   ```

## 📞 技术支持

如有问题，请：
1. 查看 [GitHub Issues](https://github.com/your-repo/issues)
2. 检查 [Wiki文档](https://github.com/your-repo/wiki)
3. 提交新的Issue并提供详细的错误信息

---

**🚀 智能更新系统** - 高效、可靠、资源友好的数据更新解决方案