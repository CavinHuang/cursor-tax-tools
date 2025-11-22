#!/usr/bin/env python3
"""
GitHub Actions 爬虫执行脚本
替代工作流中的内联Python代码
"""

import asyncio
import os
import json
import sys
from datetime import datetime

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))


async def run_optimized_scraper(update_uk: bool, update_ni: bool, batch_size: int, delay: float):
    """运行优化版爬虫"""
    try:
        # 检查必要的依赖
        try:
            import backoff
            import psutil
        except ImportError as e:
            print(f"ERROR: 优化版缺少依赖: {e}")
            print("INFO: 回退到原版爬虫")
            return await run_original_scraper(update_uk, update_ni, batch_size, delay)

        from scraper_optimized import OptimizedBatchUpdateManager
        from tariff_db_optimized import OptimizedTariffDB

        print("Using optimized scraper")

        # 初始化数据库
        db = OptimizedTariffDB()
        db.optimize_database()

        # 创建更新管理器
        manager = OptimizedBatchUpdateManager()

        print(f"Config parameters: UK={update_uk}, NI={update_ni}, Batch={batch_size}, Delay={delay}s")

        # 执行更新
        results = await manager.update_all_tariffs_optimized(
            update_uk=update_uk,
            update_ni=update_ni,
            batch_size=batch_size,
            delay_between_batches=delay
        )

        # 保存结果
        with open('update_results.json', 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=2, default=str, ensure_ascii=False)

        print(f'Optimized scraper completed: successful={results.get("successful", 0)}, failed={results.get("failed", 0)}')
        return results

    except ImportError as e:
        print(f"Optimized scraper import failed: {e}")
        print("Falling back to original scraper")
        return await run_original_scraper(update_uk, update_ni, batch_size, delay)
    except Exception as e:
        print(f"Optimized scraper execution failed: {e}")
        return {"successful": 0, "failed": 0, "error": str(e)}


async def run_original_scraper(update_uk: bool, update_ni: bool, batch_size: int, delay: float):
    """运行原版爬虫"""
    try:
        from scraper import BatchUpdateManager

        print("Using original scraper")

        # 创建更新管理器
        manager = BatchUpdateManager()

        print(f"Config parameters: UK={update_uk}, NI={update_ni}, Batch={batch_size}, Delay={delay}s")

        # 执行更新
        results = await manager.update_all_tariffs(
            update_uk=update_uk,
            update_ni=update_ni,
            batch_size=batch_size,
            delay_between_batches=delay
        )

        # 保存结果
        with open('update_results.json', 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=2, default=str, ensure_ascii=False)

        print(f'Original scraper completed: successful={results.get("successful", 0)}, failed={results.get("failed", 0)}')
        return results

    except Exception as e:
        print(f"Original scraper execution failed: {e}")
        return {"successful": 0, "failed": 0, "error": str(e)}


async def main():
    """主函数"""
    try:
        # 解析环境变量
        update_uk = os.getenv('INPUT_UPDATE_UK', 'true').lower() == 'true'
        update_ni = os.getenv('INPUT_UPDATE_NI', 'true').lower() == 'true'
        batch_size = int(os.getenv('INPUT_BATCH_SIZE', '100'))
        delay = float(os.getenv('INPUT_DELAY', '0.2'))
        use_optimized = os.getenv('USE_OPTIMIZED', 'true').lower() == 'true'

        print(f"Starting data scraping - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

        # 选择爬虫版本
        if use_optimized:
            results = await run_optimized_scraper(update_uk, update_ni, batch_size, delay)
        else:
            results = await run_original_scraper(update_uk, update_ni, batch_size, delay)

        # 输出结果摘要
        if results.get("error"):
            print(f"ERROR: Scraping failed - {results['error']}")
            sys.exit(1)
        else:
            print(f"SUCCESS: Scraping completed!")
            print(f"   Successful: {results.get('successful', 0)}")
            print(f"   Failed: {results.get('failed', 0)}")
            print(f"   UK updated: {results.get('uk_updated', 0)}")
            print(f"   NI updated: {results.get('ni_updated', 0)}")

    except Exception as e:
        print(f"ERROR: Script execution failed - {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())