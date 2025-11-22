#!/usr/bin/env python3
"""
数据库修复脚本
用于解决tariff_db.py中的表结构冲突问题
"""

import sqlite3
import logging
import os
from datetime import datetime

# 设置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def backup_database(db_path: str) -> str:
    """备份数据库文件"""
    backup_path = f"{db_path}.backup.{datetime.now().strftime('%Y%m%d_%H%M%S')}"

    if os.path.exists(db_path):
        import shutil
        shutil.copy2(db_path, backup_path)
        logger.info(f"✅ 数据库备份已创建: {backup_path}")
    else:
        logger.info("ℹ️ 数据库文件不存在，跳过备份")

    return backup_path

def check_table_structure(conn: sqlite3.Connection) -> dict:
    """检查当前表结构"""
    cursor = conn.cursor()

    # 获取tariffs表的列信息
    cursor.execute("PRAGMA table_info(tariffs)")
    columns = cursor.fetchall()

    column_names = [col[1] for col in columns]

    return {
        'columns': column_names,
        'column_count': len(columns),
        'details': columns
    }

def fix_table_structure(db_path: str) -> bool:
    """修复表结构"""
    try:
        logger.info(f"🔧 开始修复数据库: {db_path}")

        # 备份数据库
        backup_path = backup_database(db_path)

        # 连接数据库
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # 检查当前表结构
        current_structure = check_table_structure(conn)
        logger.info(f"📊 当前表结构: {current_structure['columns']}")

        # 检查是否需要添加other_rate列
        if 'other_rate' in current_structure['columns']:
            logger.info("✅ other_rate列已存在，无需修复")
            conn.close()
            return True

        # 添加缺失的other_rate列
        logger.info("🔧 添加other_rate列...")

        cursor.execute("ALTER TABLE tariffs ADD COLUMN other_rate TEXT")
        conn.commit()

        # 验证修复结果
        new_structure = check_table_structure(conn)
        if 'other_rate' in new_structure['columns']:
            logger.info("✅ other_rate列添加成功")
            logger.info(f"📊 修复后表结构: {new_structure['columns']}")

            # 检查错误记录表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS scrape_errors (
                    code TEXT PRIMARY KEY,
                    error_message TEXT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.commit()

            logger.info("✅ scrape_errors表检查完成")

            conn.close()
            return True
        else:
            logger.error("❌ other_rate列添加失败")
            conn.close()
            return False

    except Exception as e:
        logger.error(f"❌ 修复数据库失败: {str(e)}")
        if 'conn' in locals():
            conn.close()
        return False

def validate_database(db_path: str) -> dict:
    """验证数据库完整性"""
    try:
        if not os.path.exists(db_path):
            return {
                'valid': False,
                'error': '数据库文件不存在',
                'record_count': 0
            }

        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # 检查表是否存在
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='tariffs'")
        if not cursor.fetchone():
            conn.close()
            return {
                'valid': False,
                'error': 'tariffs表不存在',
                'record_count': 0
            }

        # 检查列结构
        cursor.execute("PRAGMA table_info(tariffs)")
        columns = cursor.fetchall()
        column_names = [col[1] for col in columns]

        required_columns = ['code', 'description', 'rate', 'north_ireland_rate', 'other_rate']
        missing_columns = [col for col in required_columns if col not in column_names]

        if missing_columns:
            conn.close()
            return {
                'valid': False,
                'error': f'缺少必要列: {missing_columns}',
                'missing_columns': missing_columns,
                'record_count': 0
            }

        # 获取记录数量
        cursor.execute("SELECT COUNT(*) FROM tariffs")
        record_count = cursor.fetchone()[0]

        # 检查索引
        cursor.execute("PRAGMA index_list(tariffs)")
        indexes = cursor.fetchall()

        conn.close()

        return {
            'valid': True,
            'record_count': record_count,
            'column_count': len(columns),
            'index_count': len(indexes),
            'columns': column_names
        }

    except Exception as e:
        return {
            'valid': False,
            'error': str(e),
            'record_count': 0
        }

def main():
    """主函数"""
    import argparse

    parser = argparse.ArgumentParser(description='修复关税数据库结构问题')
    parser.add_argument('--db-path', default='tariffs.db', help='数据库文件路径')
    parser.add_argument('--validate-only', action='store_true', help='仅验证不修复')
    parser.add_argument('--force', action='store_true', help='强制修复，跳过检查')
    parser.add_argument('--verbose', action='store_true', help='详细输出')

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    print("🔧 关税数据库修复工具")
    print("=" * 50)

    # 验证数据库
    print("\n📊 验证数据库...")
    validation = validate_database(args.db_path)

    if validation['valid']:
        print(f"✅ 数据库验证通过")
        print(f"   📝 记录数: {validation['record_count']}")
        print(f"   📊 列数: {validation['column_count']}")
        print(f"   🔍 索引数: {validation['index_count']}")
        return 0
    else:
        print(f"❌ 数据库验证失败: {validation['error']}")

        if args.validate_only:
            print("💡 使用 --force 参数执行修复")
            return 1

    # 执行修复
    if not args.validate_only:
        print("\n🔧 开始修复...")
        if fix_table_structure(args.db_path):
            print("\n🎉 修复成功！")

            # 再次验证
            print("\n📊 修复后验证...")
            final_validation = validate_database(args.db_path)
            if final_validation['valid']:
                print(f"✅ 数据库现在正常工作")
                print(f"   📝 记录数: {final_validation['record_count']}")
                return 0
            else:
                print(f"❌ 修复后验证仍失败: {final_validation['error']}")
                return 1
        else:
            print("\n❌ 修复失败，请查看错误信息")
            return 1

    return 0

if __name__ == "__main__":
    exit(main())