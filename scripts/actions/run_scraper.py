#!/usr/bin/env python3
"""
GitHub Actions脚本: 执行关税数据爬取
支持原版和优化版爬虫，并输出统计信息
"""

import asyncio
import json
import os
import sys
import time
from datetime import datetime


async def run_original_scraper(update_uk: bool = True, update_ni: bool = True, batch_size: int = 100, delay: float = 0.2):
    """运行原版爬虫"""
    try:
        from scraper import BatchUpdateManager

        print(f"🔧 使用原版爬虫 (UK={update_uk}, NI={update_ni}, 批量={batch_size}, 延迟={delay}s)")

        manager = BatchUpdateManager()
        start_time = time.time()

        results = await manager.update_all_tariffs(
            update_uk=update_uk,
            update_ni=update_ni,
            batch_size=batch_size,
            delay_between_batches=delay
        )

        processing_time = (time.time() - start_time) / 60
        results['processing_time_minutes'] = processing_time

        print(f"✅ 原版爬虫完成: 成功={results.get('successful', 0)}, 失败={results.get('failed', 0)}")
        return results

    except ImportError as e:
        print(f"❌ 原版爬虫导入失败: {e}", file=sys.stderr)
        return None
    except Exception as e:
        print(f"❌ 原版爬虫执行失败: {e}", file=sys.stderr)
        return None


async def run_optimized_scraper(update_uk: bool = True, update_ni: bool = True, batch_size: int = 100, delay: float = 0.2):
    """运行优化版爬虫"""
    try:
        from scraper_optimized import OptimizedBatchUpdateManager
        from tariff_db_optimized import OptimizedTariffDB

        print(f"📈 使用优化版爬虫 (UK={update_uk}, NI={update_ni}, 批量={batch_size}, 延迟={delay}s)")

        # 初始化优化版数据库
        db = OptimizedTariffDB()
        db.optimize_database()
        print("🔧 数据库优化完成")

        # 创建管理器
        def progress_callback(completed, total, message):
            if completed % 100 == 0 or completed == total:
                print(f"📊 进度: {completed}/{total} - {message}")

        def status_callback(message):
            print(f"📝 状态: {message}")

        manager = OptimizedBatchUpdateManager(
            progress_callback=progress_callback,
            status_callback=status_callback
        )

        start_time = time.time()

        results = await manager.update_all_tariffs_optimized(
            update_uk=update_uk,
            update_ni=update_ni,
            batch_size=batch_size,
            delay_between_batches=delay
        )

        processing_time = (time.time() - start_time) / 60
        results['processing_time_minutes'] = processing_time

        print(f"✅ 优化版爬虫完成: 成功={results.get('successful', 0)}, 失败={results.get('failed', 0)}")

        # 输出性能指标
        if 'performance_metrics' in results:
            metrics = results['performance_metrics']
            print("📈 性能指标:")
            print(f"  总请求数: {metrics.get('total_requests', 0)}")
            print(f"  成功率: {metrics.get('success_rate', 0):.2%}")
            print(f"  平均响应时间: {metrics.get('avg_response_time', 0):.2f}s")
            print(f"  请求速率: {metrics.get('requests_per_second', 0):.2f} req/s")
            print(f"  内存使用: {metrics.get('current_memory_mb', 0):.1f} MB")

        return results

    except ImportError as e:
        print(f"❌ 优化版爬虫导入失败: {e}", file=sys.stderr)
        print("💡 提示: 请安装优化版依赖: pip install backoff psutil prometheus-client structlog", file=sys.stderr)
        return None
    except Exception as e:
        print(f"❌ 优化版爬虫执行失败: {e}", file=sys.stderr)
        return None


def save_results(results: dict, output_path: str = 'update_results.json'):
    """保存结果到文件"""
    try:
        # 确保所有数值都是可序列化的
        serializable_results = {}
        for key, value in results.items():
            if isinstance(value, (int, float, str, bool, type(None))):
                serializable_results[key] = value
            elif isinstance(value, (list, tuple)):
                serializable_results[key] = list(value)
            elif isinstance(value, dict):
                serializable_results[key] = {k: v for k, v in value.items() if isinstance(v, (int, float, str, bool, type(None), list, dict))}
            else:
                serializable_results[key] = str(value)

        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(serializable_results, f, indent=2, default=str, ensure_ascii=False)

        print(f"💾 结果已保存: {output_path}")
        return True

    except Exception as e:
        print(f"❌ 保存结果失败: {e}", file=sys.stderr)
        return False


def print_summary(results: dict):
    """打印结果摘要"""
    if not results:
        print("❌ 没有有效的结果")
        return

    print("\n" + "="*50)
    print("📊 爬取结果摘要")
    print("="*50)

    total = results.get('total', 0)
    completed = results.get('completed', 0)
    successful = results.get('successful', 0)
    failed = results.get('failed', 0)
    skipped = results.get('skipped', 0)
    uk_updated = results.get('uk_updated', 0)
    ni_updated = results.get('ni_updated', 0)
    processing_time = results.get('processing_time_minutes', 0)

    print(f"📋 总记录数: {total:,}")
    print(f"✅ 已完成: {completed:,}")
    print(f"🎯 成功: {successful:,}")
    print(f"❌ 失败: {failed:,}")
    print(f"⏭️ 跳过: {skipped:,}")

    if uk_updated > 0 or ni_updated > 0:
        print(f"🇬🇧 英国更新: {uk_updated:,}")
        print(f"🇮🇪 北爱尔兰更新: {ni_updated:,}")

    if processing_time > 0:
        rate = completed / processing_time if processing_time > 0 else 0
        print(f"⏱️ 处理时间: {processing_time:.1f} 分钟")
        print(f"🚀 处理速率: {rate:.1f} 条/分钟")

    if completed > 0:
        success_rate = successful / completed * 100
        print(f"📈 成功率: {success_rate:.2f}%")

    print("="*50)


def main():
    """主函数"""
    # 解析命令行参数
    args = {
        'use_optimized': os.getenv('USE_OPTIMIZED', 'true').lower() == 'true',
        'update_uk': os.getenv('INPUT_UPDATE_UK', 'true').lower() == 'true',
        'update_ni': os.getenv('INPUT_UPDATE_NI', 'true').lower() == 'true',
        'batch_size': int(os.getenv('INPUT_BATCH_SIZE', '100')),
        'delay': float(os.getenv('INPUT_DELAY', '0.2')),
        'output_file': os.getenv('OUTPUT_FILE', 'update_results.json')
    }

    print("🚀 开始执行关税数据爬取...")
    print(f"📋 配置: 优化版={args['use_optimized']}, UK={args['update_uk']}, NI={args['update_ni']}")
    print(f"⚙️ 参数: 批量={args['batch_size']}, 延迟={args['delay']}s")

    try:
        # 选择爬虫版本
        if args['use_optimized']:
            results = asyncio.run(run_optimized_scraper(
                update_uk=args['update_uk'],
                update_ni=args['update_ni'],
                batch_size=args['batch_size'],
                delay=args['delay']
            ))
        else:
            results = asyncio.run(run_original_scraper(
                update_uk=args['update_uk'],
                update_ni=args['update_ni'],
                batch_size=args['batch_size'],
                delay=args['delay']
            ))

        if not results:
            print("❌ 爬虫执行失败", file=sys.stderr)
            sys.exit(1)

        # 保存结果
        if not save_results(results, args['output_file']):
            sys.exit(1)

        # 打印摘要
        print_summary(results)

        # 输出环境变量供GitHub Actions使用
        successful = results.get('successful', 0)
        failed = results.get('failed', 0)
        uk_updated = results.get('uk_updated', 0)
        ni_updated = results.get('ni_updated', 0)

        print(f"::set-output name=successful::{successful}")
        print(f"::set-output name=failed::{failed}")
        print(f"::set-output name=uk_updated::{uk_updated}")
        print(f"::set-output name=ni_updated::{ni_updated}")
        print(f"::set-output name=total::{results.get('total', 0)}")
        print(f"::set-output name=completed::{results.get('completed', 0)}")

        # 如果失败率过高，设置警告
        completed_count = results.get('completed', 0)
        if completed_count > 0:
            failure_rate = failed / completed_count
            if failure_rate > 0.1:  # 失败率超过10%
                print(f"::warning::失败率过高: {failure_rate:.2%}")

    except KeyboardInterrupt:
        print("⏹️ 用户中断执行", file=sys.stderr)
        sys.exit(130)
    except Exception as e:
        print(f"❌ 执行失败: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()