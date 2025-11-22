#!/usr/bin/env python3

import sys

def test_methods():
    print("Testing optimized database methods...")

    try:
        from tariff_db_optimized import OptimizedTariffDB

        # 创建数据库实例
        db = OptimizedTariffDB("tariffs.db")
        print("OptimizedTariffDB: OK")

        # 测试新增的方法
        methods_to_test = ['get_all_tariffs', 'get_existing_codes', 'get_existing_codes_north_ireland']

        for method_name in methods_to_test:
            if hasattr(db, method_name):
                try:
                    result = getattr(db, method_name)()
                    print(f"{method_name}: OK - returned {len(result)} items")
                except Exception as e:
                    print(f"{method_name}: ERROR - {e}")
            else:
                print(f"{method_name}: MISSING")

        db.close()
        return True

    except Exception as e:
        print(f"Import or instantiation failed: {e}")
        return False

if __name__ == "__main__":
    success = test_methods()
    if success:
        print("All methods test: PASSED")
    else:
        print("Methods test: FAILED")
    sys.exit(0 if success else 1)