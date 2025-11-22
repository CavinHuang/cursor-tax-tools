# 🔧 数据库修复指南

## 问题描述
当您看到以下错误时，说明数据库表结构存在问题：
```
ERROR:tariff_db:创建表失败: duplicate column name: other_rate
sqlite3.OperationalError: duplicate column name: other_rate
```

## 🔧 解决方案

### 方案1: 自动修复（推荐）
浮浮酱已经修复了 `tariff_db.py` 中的问题，现在程序会自动处理这种情况：

1. **重新启动程序**
   ```bash
   python tariff_gui.py
   ```
   或者
   ```bash
   python launch_gui.py
   ```

2. **观察日志输出**
   - 如果看到 `✅ other_rate列已存在，跳过` 说明正常
   - 如果看到 `✅ 成功添加other_rate列` 说明修复成功

### 方案2: 使用修复脚本
如果自动修复失败，可以使用专门的修复脚本：

```bash
# 验证数据库状态
python database_fix.py --validate-only

# 执行修复
python database_fix.py

# 详细模式
python database_fix.py --verbose
```

### 方案3: 手动修复
如果上述方法都失败，可以手动修复：

1. **备份现有数据库**
   ```bash
   cp tariffs.db tariffs.db.backup
   ```

2. **检查表结构**
   ```bash
   sqlite3 tariffs.db "PRAGMA table_info(tariffs);"
   ```

3. **手动添加缺失列（如果需要）**
   ```sql
   sqlite3 tariffs.db "ALTER TABLE tariffs ADD COLUMN other_rate TEXT;"
   ```

## 🎯 修复后验证

修复完成后，您可以：

1. **检查数据库连接**
   ```python
   from tariff_db import TariffDB
   db = TariffDB()
   print("数据库连接成功！")
   ```

2. **查看记录数量**
   ```python
   record_count = db.conn.execute("SELECT COUNT(*) FROM tariffs").fetchone()[0]
   print(f"数据库中有 {record_count} 条记录")
   ```

3. **启动GUI测试**
   ```bash
   python launch_gui.py
   ```

## 📊 常见问题

### Q1: 修复后还是报错怎么办？
**A**:
1. 删除 `tariffs.db` 文件，程序会重新创建
2. 检查是否有其他程序占用数据库文件
3. 确保有足够的磁盘空间

### Q2: 数据会丢失吗？
**A**: 不会！
- 修复过程只是修改表结构，不会删除数据
- 如果担心，可以先备份 `tariffs.db` 文件

### Q3: 如何避免这个问题？
**A**:
- 使用最新的代码版本
- 不要手动修改数据库文件结构
- 定期备份数据库文件

## 🚀 最佳实践

### 日常使用建议
1. **定期备份数据库**
   ```bash
   cp tariffs.db backups/tariffs_$(date +%Y%m%d).db
   ```

2. **使用启动器**
   ```bash
   python launch_gui.py  # 推荐使用
   ```

3. **遇到问题先看日志**
   - 检查控制台输出的错误信息
   - 查看日志文件（如果有的话）

### 开发者注意事项
1. **修改表结构时要小心**
   - 使用 `ALTER TABLE ADD COLUMN` 时要检查列是否存在
   - 使用 `CREATE TABLE IF NOT EXISTS` 避免重复创建

2. **向后兼容性**
   - 考虑旧版本数据库的升级路径
   - 提供数据库迁移脚本

## 📞 技术支持

如果问题仍然存在：
1. 检查Python版本（建议3.8+）
2. 确认所有依赖已安装：`pip install -r requirements.txt`
3. 查看完整的错误堆栈信息
4. 提供操作系统和Python环境信息

---

> 🐾 **猫娘工程师浮浮酱提示**: 这个问题是因为数据库表结构升级导致的，现在已经修复了！如果还有问题，运行数据库修复脚本就能解决喵～ (๑•̀ㅂ•́) ✧