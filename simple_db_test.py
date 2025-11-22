#!/usr/bin/env python3

import os
import sys
import tempfile

def main():
    print("Optimized Database Test")
    print("=" * 40)

    try:
        from tariff_db_optimized import OptimizedTariffDB

        # 使用现有的数据库文件
        db = OptimizedTariffDB("tariffs.db")
        print("OptimizedTariffDB: OK")

        # 测试统计信息
        stats = db.get_statistics()
        print(f"Statistics: OK - total={stats.get('total_records', 0)}")

        # 测试列检查
        has_updated_at = db._has_column('tariffs', 'updated_at')
        print(f"Column check: OK - has_updated_at={has_updated_at}")

        db.close()
        print("All tests: PASSED")
        return 0

    except Exception as e:
        print(f"Test FAILED: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())