[根目录](./CLAUDE.md) > **tariff_api.py 关税API模块**

# Tariff API 关税查询核心模块

## 📍 路径面包屑
[根目录](./CLAUDE.md) > **tariff_api.py 关税API模块**

## 🎯 模块职责

Tariff API是项目的核心业务逻辑模块，负责：
- 关税编码的精确和模糊查询
- 相似度计算和匹配算法
- 数据验证和自动更新功能
- 与数据库层的交互封装

## 🚀 入口与启动

### 主要接口类
```python
from tariff_api import TariffAPI

# 初始化API
api = TariffAPI()

# 精确查询
result = api.exact_search("8703239010")

# 模糊搜索
results = api.fuzzy_search("8703")

# 自动更新
update_result = api.auto_update("8703239010", uk_url, ni_url)
```

### 启动流程
1. 自动初始化数据库连接
2. 加载现有编码缓存
3. 准备搜索引擎
4. 配置更新机制

## 🔌 对外接口

### 核心查询接口
```python
def exact_search(self, code: str) -> Optional[Dict]:
    """精确查询关税信息
    Args:
        code: 完整的商品编码
    Returns:
        关税数据字典或None
    """

def fuzzy_search(self, query: str, limit: int = 50) -> List[Dict]:
    """模糊搜索关税信息
    Args:
        query: 搜索关键词
        limit: 返回结果数量限制
    Returns:
        匹配的关税数据列表
    """
```

### 数据更新接口
```python
def auto_update(self, code: str, uk_url: str, ni_url: str = None) -> Dict:
    """自动更新关税数据
    Args:
        code: 商品编码
        uk_url: 英国税率网址
        ni_url: 北爱尔兰税率网址（可选）
    Returns:
        更新结果详情
    """
```

## 🔗 关键依赖与配置

### 内部依赖
```python
from tariff_db import TariffDB          # 数据库操作
from scraper import TariffScraper       # 数据爬虫
from Levenshtein import ratio          # 字符串相似度
import re                              # 正则表达式
import logging                         # 日志记录
```

### 配置参数
- **相似度算法**: 前缀匹配权重0.7，编辑距离权重0.3
- **查询限制**: 默认返回前50个结果
- **编码标准化**: 只保留数字字符
- **缓存策略**: 内存缓存常用编码

## 🗄️ 数据模型

### 查询结果数据结构
```python
{
    'code': '8703239010',                    # 商品编码
    'description': '电动汽车描述',           # 商品描述
    'rate': '10%',                           # 英国税率
    'url': 'https://...',                   # 英国税率网址
    'north_ireland_rate': '0%',             # 北爱尔兰税率
    'north_ireland_url': 'https://...',     # 北爱尔兰税率网址
    'similarity': 1.0                       # 搜索相似度（模糊查询）
}
```

### 自动更新结果结构
```python
{
    'overall_success': True,                 # 总体成功状态
    'uk_success': True,                      # 英国数据更新成功
    'ni_success': True,                      # 北爱尔兰数据更新成功
    'uk_updated': True,                      # 英国数据有变化
    'ni_updated': False,                     # 北爱尔兰数据无变化
    'message': '更新完成',                  # 详细消息
    'old_data': {...},                       # 更新前数据
    'new_data': {...}                        # 更新后数据
}
```

## 🧪 测试与质量

### 核心算法测试
```python
# 编码标准化测试
assert api._normalize_code("8703-2390-10") == "8703239010"

# 相似度计算测试
similarity = api._calculate_similarity("8703239", "8703239010")
assert 0.8 <= similarity <= 1.0

# 精确查询测试
result = api.exact_search("8703239010")
assert result is not None
assert result['code'] == "8703239010"
```

### 性能指标
- **精确查询**: < 50ms
- **模糊搜索**: < 200ms (50条结果)
- **自动更新**: < 30s (包含网络请求)
- **内存使用**: < 100MB (正常负载)

## ❓ 常见问题 (FAQ)

### Q1: 模糊搜索结果不准确？
- 检查搜索关键词格式
- 调整相似度权重配置
- 验证编码标准化逻辑
- 增加查询结果限制

### Q2: 自动更新失败？
- 验证URL有效性
- 检查网络连接
- 确认爬虫权限
- 查看详细错误日志

### Q3: 性能优化建议？
- 启用数据库索引
- 使用查询缓存
- 批量处理操作
- 异步网络请求

## 📁 相关文件清单

### 直接依赖
- `tariff_db.py` - 数据库操作封装
- `scraper.py` - 网络数据爬取
- 数据库文件: `datas/tariffs.db`

### 关联文件
- `tariff_gui.py` - GUI界面调用
- `batch_processor.py` - 批量处理使用
- `smart_update_client.py` - 自动更新客户端

## 📅 变更记录 (Changelog)

### 2025-11-23 17:38:51
- ✨ 创建API模块文档
- 🔧 完善接口说明和使用示例
- 📋 添加数据模型和测试指南
- ⚡ 整合性能优化建议

### 近期更新
- 优化相似度计算算法
- 增强自动更新功能
- 添加并发查询支持
- 改进错误处理机制

---

**模块负责人**: 核心业务逻辑
**技术重点**: 搜索算法 + 数据匹配 + 自动更新
**运行环境**: 桌面应用 + 后台服务 🔍📊