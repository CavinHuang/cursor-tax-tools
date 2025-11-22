#!/usr/bin/env python3
"""
数据库修复工具
用于修复数据库表结构问题
"""

import sqlite3
import os
import sys
import logging

# 设置日志
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

def fix_database_schema(db_path: str = "tariffs.db"):
    """修复数据库表结构"""

    if not os.path.exists(db_path):
        logger.info(f"数据库文件不存在: {db_path}")
        logger.info("将创建新的数据库...")

    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # 检查表结构
        cursor.execute("PRAGMA table_info(tariffs)")
        columns = [row[1] for row in cursor.fetchall()]

        logger.info(f"当前表结构: {columns}")

        # 检查是否需要修复表结构
        needed_columns = ['code', 'description', 'rate', 'url', 'north_ireland_rate', 'north_ireland_url', 'other_rate']
        missing_columns = [col for col in needed_columns if col not in columns]

        if missing_columns:
            logger.info(f"发现缺失的列: {missing_columns}")

            # 添加缺失的列
            for col in missing_columns:
                try:
                    cursor.execute(f"ALTER TABLE tariffs ADD COLUMN {col} TEXT")
                    logger.info(f"✅ 成功添加列: {col}")
                except sqlite3.OperationalError as e:
                    if "duplicate column name" in str(e).lower():
                        logger.info(f"ℹ️ 列 {col} 已存在，跳过")
                    else:
                        logger.error(f"❌ 添加列 {col} 失败: {e}")
                        raise
        else:
            logger.info("✅ 表结构完整，无需修复")

        # 确保索引存在
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_code ON tariffs(code)")
        logger.info("✅ 索引检查完成")

        # 检查错误记录表
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS scrape_errors (
            code TEXT PRIMARY KEY,
            error_message TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
        """)
        logger.info("✅ 错误记录表检查完成")

        # 提交更改
        conn.commit()

        # 显示最终的表结构
        cursor.execute("PRAGMA table_info(tariffs)")
        final_columns = [row[1] for row in cursor.fetchall()]
        logger.info(f"最终表结构: {final_columns}")

        # 显示记录数量
        cursor.execute("SELECT COUNT(*) FROM tariffs")
        record_count = cursor.fetchone()[0]
        logger.info(f"数据库记录数: {record_count}")

        conn.close()
        logger.info("🎉 数据库修复完成！")

        return True

    except Exception as e:
        logger.error(f"❌ 数据库修复失败: {e}")
        return False

def backup_database(db_path: str):
    """备份数据库"""
    if not os.path.exists(db_path):
        logger.info("数据库文件不存在，无需备份")
        return False

    backup_path = f"{db_path}.backup.{int(time.time())}"

    try:
        import shutil
        shutil.copy2(db_path, backup_path)
        logger.info(f"✅ 数据库已备份到: {backup_path}")
        return backup_path
    except Exception as e:
        logger.error(f"❌ 备份失败: {e}")
        return False

def main():
    import time

    print("🔧 关税数据库修复工具")
    print("=" * 40)

    db_path = "tariffs.db"

    if len(sys.argv) > 1:
        db_path = sys.argv[1]

    print(f"数据库路径: {db_path}")
    print()

    # 询问是否备份
    if os.path.exists(db_path):
        response = input("是否要备份数据库？(y/n): ").lower().strip()
        if response in ['y', 'yes', '是']:
            backup_database(db_path)
            print()

    # 执行修复
    print("开始修复数据库...")
    success = fix_database_schema(db_path)

    if success:
        print("\n🎉 数据库修复成功！")
        print("现在可以正常启动GUI了。")
    else:
        print("\n❌ 数据库修复失败，请检查错误信息。")
        return 1

    return 0

if __name__ == "__main__":
    sys.exit(main())