#!/usr/bin/env python3

import os
import sys
import tempfile

def test_optimized_db():
    print("Testing optimized database...")

    try:
        from tariff_db_optimized import OptimizedTariffDB

        # 使用临时数据库文件进行测试
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as tmp_file:
            test_db_path = tmp_file.name

        try:
            # 创建数据库实例
            db = OptimizedTariffDB(test_db_path)
            print("✓ OptimizedTariffDB created successfully")

            # 测试统计信息
            stats = db.get_statistics()
            print(f"✓ Statistics retrieved: {stats}")

            # 测试分页查询
            results = db.get_tariffs_pagination(limit=10)
            print(f"✓ Pagination query works: {len(results)} records")

            # 测试列检查
            has_updated_at = db._has_column('tariffs', 'updated_at')
            print(f"✓ Column check works, has_updated_at: {has_updated_at}")

            # 测试数据库优化
            db.optimize_database()
            print("✓ Database optimization completed")

            # 关闭数据库
            db.close()

            # 清理临时文件
            if os.path.exists(test_db_path):
                os.unlink(test_db_path)

            return True

        except Exception as e:
            print(f"✗ Test failed: {e}")
            if os.path.exists(test_db_path):
                os.unlink(test_db_path)
            return False

    except Exception as e:
        print(f"✗ Import failed: {e}")
        return False

def test_with_existing_db():
    print("\nTesting with existing database...")

    try:
        from tariff_db_optimized import OptimizedTariffDB

        # 使用现有的数据库文件
        db = OptimizedTariffDB("tariffs.db")
        print("✓ Opened existing database successfully")

        # 测试统计信息
        stats = db.get_statistics()
        print(f"✓ Statistics: total={stats.get('total_records', 0)}, errors={stats.get('active_errors', 0)}")

        # 测试列检查
        has_updated_at = db._has_column('tariffs', 'updated_at')
        print(f"✓ Column check: has_updated_at={has_updated_at}")

        db.close()
        return True

    except Exception as e:
        print(f"✗ Test with existing DB failed: {e}")
        return False

def main():
    print("Optimized Database Test")
    print("=" * 40)

    # 测试新数据库创建
    test1 = test_optimized_db()

    # 测试现有数据库兼容性
    test2 = test_with_existing_db()

    print("\n" + "=" * 40)
    if test1 and test2:
        print("✓ All tests PASSED!")
        print("The optimized database is ready for use.")
        return 0
    else:
        print("✗ Some tests FAILED!")
        return 1

if __name__ == "__main__":
    sys.exit(main())