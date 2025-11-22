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


async def run_optimized_scraper(update_uk: bool, update_ni: bool, batch_size: int, delay: float):
    """运行优化版爬虫"""
    try:
        from scraper_optimized import OptimizedBatchUpdateManager
        from tariff_db_optimized import OptimizedTariffDB

        print("📈 使用优化版爬虫")

        # 初始化数据库
        db = OptimizedTariffDB()
        db.optimize_database()

        # 创建更新管理器
        manager = OptimizedBatchUpdateManager()

        print(f"🔧 配置参数: UK={update_uk}, NI={update_ni}, Batch={batch_size}, Delay={delay}s")

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

        print(f'✅ 优化版更新完成: 成功={results.get("successful", 0)}, 失败={results.get("failed", 0)}')
        return results

    except ImportError as e:
        print(f"❌ 优化版爬虫导入失败: {e}")
        print("🔧 回退到原版爬虫")
        return await run_original_scraper(update_uk, update_ni, batch_size, delay)
    except Exception as e:
        print(f"❌ 优化版爬虫执行失败: {e}")
        return {"successful": 0, "failed": 0, "error": str(e)}


async def run_original_scraper(update_uk: bool, update_ni: bool, batch_size: int, delay: float):
    """运行原版爬虫"""
    try:
        from scraper import BatchUpdateManager

        print("🔧 使用原版爬虫")

        # 创建更新管理器
        manager = BatchUpdateManager()

        print(f"🔧 配置参数: UK={update_uk}, NI={update_ni}, Batch={batch_size}, Delay={delay}s")

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

        print(f'✅ 原版更新完成: 成功={results.get("successful", 0)}, 失败={results.get("failed", 0)}')
        return results

    except Exception as e:
        print(f"❌ 原版爬虫执行失败: {e}")
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

        print(f"🚀 开始数据爬取 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

        # 选择爬虫版本
        if use_optimized:
            results = await run_optimized_scraper(update_uk, update_ni, batch_size, delay)
        else:
            results = await run_original_scraper(update_uk, update_ni, batch_size, delay)

        # 输出结果摘要
        if results.get("error"):
            print(f"❌ 爬取失败: {results['error']}")
            sys.exit(1)
        else:
            print(f"🎉 爬取成功完成!")
            print(f"   📊 成功: {results.get('successful', 0)}")
            print(f"   ❌ 失败: {results.get('failed', 0)}")
            print(f"   🇬🇧 英国更新: {results.get('uk_updated', 0)}")
            print(f"   🇮🇪 北爱更新: {results.get('ni_updated', 0)}")

    except Exception as e:
        print(f"❌ 脚本执行失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())