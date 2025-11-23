[根目录](./CLAUDE.md) > **tariff_gui.py 主界面模块**

# Tariff GUI 主界面模块

## 📍 路径面包屑
[根目录](./CLAUDE.md) > **tariff_gui.py 主界面模块**

## 🎯 模块职责

Tariff GUI是项目的主要用户界面模块，提供：
- 多标签页统一界面设计
- 单个编码快速查询功能
- 批量文件处理集成
- 实时数据更新和管理
- 右键菜单和快捷操作

## 🚀 入口与启动

### 启动方式
```python
# 直接启动
python tariff_gui.py

# 通过启动器启动（推荐）
python launch_gui.py

# 编程式启动
from tariff_gui import TariffGUI
gui = TariffGUI()
gui.run()
```

### 界面结构
1. **启动器选择** - 原始版本 vs 增强版本
2. **主界面** - 多标签页设计
3. **查询标签页** - 单个/批量查询
4. **更新标签页** - 批量更新管理
5. **远程更新标签页** - 智能数据同步

## 🔌 对外接口

### 主要GUI类
```python
class TariffGUI:
    """主GUI应用程序类"""

    def __init__(self):
        """初始化GUI"""
        self.root = tk.Tk()
        self.setup_ui()
        self.setup_api()
        self.setup_queue()

    def run(self):
        """运行GUI应用程序"""
        self.root.mainloop()
```

### 核心界面组件
```python
class UpdateDialog:
    """数据更新对话框"""
    def __init__(self, parent, tariff_data: dict, on_save_callback=None):
        # 模态对话框，支持数据编辑和保存

class BatchProcessFrame:
    """批量处理框架（从batch_gui.py集成）"""
    def __init__(self, master):
        # Excel文件处理和批量查询
```

## 🔗 关键依赖与配置

### GUI框架依赖
```python
import tkinter as tk                      # 核心GUI框架
from tkinter import ttk, messagebox      # 增强组件和对话框
from tkinter import filedialog           # 文件选择对话框
import threading                          # 多线程支持
import queue                             # 线程间通信
```

### 业务逻辑依赖
```python
from tariff_api import TariffAPI         # 关税查询API
from tariff_db import TariffDB           # 数据库操作
from scraper import BatchUpdateManager   # 批量更新管理
from smart_update_client import SmartUpdateChecker  # 智能更新
```

### 配置参数
- **界面尺寸**: 900x700 (主窗口)
- **更新URL**: GitHub远程数据源
- **数据库路径**: 默认"tariffs.db"
- **批量大小**: 可配置10-200

## 🗄️ 数据模型

### 查询结果显示模型
```python
# 树形视图显示列
columns = ('编码', '税率', '网址', '北爱尔兰税率', '北爱尔兰网址', '相似度')

# 隐藏数据列（不显示但存储）
hidden_data = {
    'description': '完整商品描述',
    'original_code': '原始编码',
    'scrape_status': '抓取状态'
}
```

### 批量更新配置模型
```python
update_config = {
    'update_uk': True,                    # 更新英国税率
    'update_ni': True,                    # 更新北爱尔兰税率
    'update_errors_only': False,          # 仅更新错误记录
    'batch_size': 100,                    # 批量大小
    'delay': 0.2                          # 批次间延迟（秒）
}
```

## 🧪 测试与质量

### UI组件测试
```python
# 测试GUI初始化
def test_gui_initialization():
    gui = TariffGUI()
    assert gui.root is not None
    assert hasattr(gui, 'notebook')
    assert hasattr(gui, 'api')

# 测试搜索功能
def test_search_functionality():
    # 模拟用户输入和点击
    # 验证搜索结果显示
    pass
```

### 用户体验指标
- **启动时间**: < 3秒
- **搜索响应**: < 1秒
- **界面流畅度**: 60fps
- **内存占用**: < 150MB

### 交互设计验证
- 键盘快捷键支持
- 右键菜单完整
- 错误提示友好
- 进度反馈及时

## ❓ 常见问题 (FAQ)

### Q1: GUI启动失败？
```bash
# 检查tkinter安装
python -c "import tkinter; print('OK')"

# 检查依赖模块
python -c "from tariff_api import TariffAPI; print('OK')"

# 检查数据库文件
ls -la tariffs.db
```

### Q2: 搜索结果显示异常？
- 验证数据库连接
- 检查编码格式
- 确认API返回格式
- 查看控制台错误日志

### Q3: 批量处理卡顿？
- 调整批量大小配置
- 检查系统资源使用
- 启用多线程处理
- 优化数据库查询

## 📁 相关文件清单

### 核心GUI文件
- `tariff_gui.py` - 主GUI实现 (1620行)
- `batch_gui.py` - 批量处理GUI
- `enhanced_gui.py` - 增强版GUI
- `launch_gui.py` - 启动器选择

### 资源文件
- `templates/` - Excel模板文件
- `datas/tariffs.db` - 数据库文件
- `build_*.spec` - 打包配置文件

### 关联模块
- `tariff_api.py` - 查询API
- `batch_processor.py` - 批量处理器
- `scraper.py` - 数据爬虫

## 📅 变更记录 (Changelog)

### 2025-11-23 17:38:51
- ✨ 创建GUI模块文档
- 🎨 完善界面结构说明
- 🔧 添加使用示例和配置指南
- ⚡ 整合性能优化建议

### 近期更新
- 添加智能更新标签页
- 优化批量更新界面
- 增强右键菜单功能
- 改进错误处理显示

---

**模块负责人**: 用户界面设计
**技术重点**: Tkinter GUI + 多线程 + 用户体验
**运行环境**: Windows桌面应用 🖥️🎨