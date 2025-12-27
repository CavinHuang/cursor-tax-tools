#!/usr/bin/env python3
"""
单个 Shard 执行器 - 执行单个分片的爬取任务

功能：
1. 读取分配的章节列表
2. 执行爬取并实时写入分片数据库
3. 定期检查超时并保存进度
4. 超时时优雅退出并保存当前状态
"""

import asyncio
import sys
import os
import json
import time
from typing import List, Dict, Optional
from pathlib import Path

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from chapter_scheduler import ChapterScheduler
from progress_monitor import ProgressMonitor, ShardProgress


class ShardExecutor:
    """单个 Shard 执行器"""

    def __init__(
        self,
        shard_id: str,
        chapters: List[str],
        data_type: str = "uk",
        output_db: str = None
    ):
        """
        初始化 Shard 执行器

        Args:
            shard_id: Shard ID (如 "shard_0")
            chapters: 分配的章节列表
            data_type: 数据类型 ("uk" 或 "ni")
            output_db: 输出数据库路径
        """
        self.shard_id = shard_id
        self.chapters = chapters
        self.data_type = data_type
        self.output_db = output_db or f"tariffs_{shard_id}.db"

        self.monitor = ProgressMonitor()
        self.results = {
            "shard_id": shard_id,
            "status": "unknown",
            "chapters_assigned": chapters,
            "chapters_completed": [],
            "chapters_failed": [],
            "start_time": None,
            "end_time": None,
            "interrupted": False,
            "interrupt_reason": None,
        }

    async def execute(self):
        """执行 shard 爬取任务"""
        self.results["start_time"] = time.time()

        # 注册 shard 到监控器
        self.monitor.register_shard(self.shard_id, len(self.chapters))

        print(f"\n{'='*60}")
        print(f"🚀 Shard {self.shard_id} 开始执行")
        print(f"📋 分配章节: {len(self.chapters)} 个")
        print(f"📁 输出数据库: {self.output_db}")
        print(f"{'='*60}\n")

        try:
            # 动态导入爬虫模块
            from scraper import TariffScraper
            from tariff_db import TariffDB

            # 创建独立的数据库实例
            shard_db = TariffDB(db_path=self.output_db)
            print(f"✅ 使用独立数据库: {self.output_db}")

            scraper = TariffScraper()
            # 替换为分片数据库
            scraper.db = shard_db
            # 清空现有编码缓存（因为我们要爬取新的数据）
            scraper.existing_codes = set()

            total_urls = 0
            completed_urls = []

            # 遍历每个章节
            for i, chapter in enumerate(self.chapters):
                # 检查超时
                should_stop, reason = self.monitor.should_create_partial(self.shard_id)
                if should_stop:
                    print(f"\n⏸️  收到停止信号: {reason}")
                    self.results["interrupted"] = True
                    self.results["interrupt_reason"] = reason
                    break

                # 更新进度
                print(f"📖 [{i+1}/{len(self.chapters)}] 处理章节 {chapter}...")
                self.monitor.update_shard_progress(
                    self.shard_id,
                    completed_chapters=i,
                    current_chapter=chapter,
                    urls_processed=total_urls,
                    status="in_progress"
                )

                # 爬取章节
                try:
                    chapter_urls = await self._scrape_chapter(
                        scraper, chapter
                    )

                    if chapter_urls:
                        completed_urls.extend(chapter_urls)
                        total_urls = len(completed_urls)
                        self.results["chapters_completed"].append(chapter)
                    else:
                        print(f"⚠️  章节 {chapter} 无数据")
                        self.results["chapters_failed"].append(chapter)

                except Exception as e:
                    print(f"❌ 章节 {chapter} 失败: {e}")
                    self.results["chapters_failed"].append(chapter)
                    continue

            # 最终更新进度
            self.monitor.update_shard_progress(
                self.shard_id,
                completed_chapters=len(self.results["chapters_completed"]),
                current_chapter="",
                urls_processed=total_urls,
                status="interrupted" if self.results["interrupted"] else "completed"
            )

            # 设置最终状态
            if self.results["interrupted"]:
                self.results["status"] = "partial"
            elif self.results["chapters_failed"]:
                self.results["status"] = "partial"
            else:
                self.results["status"] = "success"

        except Exception as e:
            print(f"\n❌ Shard 执行失败: {e}")
            import traceback
            traceback.print_exc()
            self.results["status"] = "failed"
            self.results["error"] = str(e)

        finally:
            self.results["end_time"] = time.time()
            self._save_results()

        # 打印结果摘要
        self._print_summary()

        return self.results

    async def _scrape_chapter(
        self,
        scraper,
        chapter: str
    ) -> List[str]:
        """
        爬取单个章节

        Args:
            scraper: TariffScraper 实例
            chapter: 章节号

        Returns:
            List[str]: 处理的 URL 列表
        """
        from bs4 import BeautifulSoup
        import logging

        logger = logging.getLogger(__name__)
        processed_urls = []

        try:
            # 1. 构建章节URL
            chapter_url = f"{scraper.base_url}/chapters/{chapter}"
            logger.info(f"正在爬取章节: {chapter_url}")

            # 2. 爬取章节页面
            results = await scraper.scrape_with_retry([chapter_url])
            status, content = results[0]

            if status != 200 or not content:
                logger.warning(f"章节 {chapter} 页面失败 (status={status})")
                return []

            # 3. 解析heading链接
            soup = BeautifulSoup(content, 'html.parser')
            heading_urls = []

            # 查找heading表格
            heading_table = soup.find('table', class_='govuk-table')
            if heading_table:
                for row in heading_table.find_all('tr', class_='govuk-table__row'):
                    link = row.find('a')
                    if link and link.get('href'):
                        href = link.get('href')
                        if href.startswith('/headings/'):
                            full_url = f"{scraper.base_url}{href}"
                            heading_urls.append(full_url)

            logger.info(f"章节 {chapter} 找到 {len(heading_urls)} 个heading")

            # 4. 分批爬取heading页面并解析commodity链接
            batch_size = 20
            for i in range(0, len(heading_urls), batch_size):
                heading_batch = heading_urls[i:i + batch_size]

                heading_results = await scraper.scrape_with_retry(heading_batch)
                commodity_urls = []

                for h_status, h_content in heading_results:
                    if h_status == 200 and h_content:
                        h_soup = BeautifulSoup(h_content, 'html.parser')
                        # 查找commodity链接
                        for row in h_soup.find_all('tr', class_='govuk-table__row'):
                            link = row.find('a')
                            if link and link.get('href'):
                                href = link.get('href')
                                if href.startswith('/commodities/'):
                                    full_url = f"{scraper.base_url}{href}"
                                    commodity_urls.append(full_url)

                logger.info(f"  Heading批次 {i//batch_size + 1}: 找到 {len(commodity_urls)} 个commodity")

                # 5. 分批爬取commodity页面并解析保存
                for j in range(0, len(commodity_urls), batch_size):
                    commodity_batch = commodity_urls[j:j + batch_size]

                    commodity_results = await scraper.scrape_with_retry(commodity_batch)

                    for k, (c_status, c_content) in enumerate(commodity_results):
                        if c_status == 200 and c_content:
                            # 解析commodity页面并保存到数据库
                            tariff = scraper.parse_commodity_page(
                                c_content,
                                url=commodity_batch[k]
                            )
                            if tariff:
                                scraper.db.save_tariff(tariff)
                                processed_urls.append(commodity_batch[k])
                        elif c_status == 404:
                            # 404 - 标记删除
                            import re
                            code_match = re.search(r'/commodities/(\d+)', commodity_batch[k])
                            if code_match:
                                code = code_match.group(1)
                                scraper.db.mark_as_deleted(code)
                                logger.info(f"  Commodity {code} 已删除 (404)")

                logger.info(f"  Commodity批次完成，本批处理了 {len(commodity_urls)} 个URL")

            return processed_urls

        except Exception as e:
            logger.error(f"爬取章节 {chapter} 失败: {e}")
            import traceback
            traceback.print_exc()
            return []

    def _save_results(self):
        """保存结果到文件"""
        result_file = f"shard_{self.shard_id}_results.json"

        try:
            with open(result_file, 'w', encoding='utf-8') as f:
                json.dump(self.results, f, indent=2, ensure_ascii=False, default=str)
            print(f"💾 结果已保存: {result_file}")
        except Exception as e:
            print(f"⚠️  保存结果失败: {e}")

    def _print_summary(self):
        """打印执行摘要"""
        elapsed = self.results["end_time"] - self.results["start_time"]

        print(f"\n{'='*60}")
        print(f"📊 Shard {self.shard_id} 执行摘要")
        print(f"{'='*60}")
        print(f"📁 状态: {self.results['status']}")
        print(f"✅ 完成章节: {len(self.results['chapters_completed'])}/{len(self.chapters)}")
        print(f"❌ 失败章节: {len(self.results['chapters_failed'])}")

        if self.results["interrupted"]:
            print(f"⏸️  中断原因: {self.results['interrupt_reason']}")

        print(f"⏱️  耗时: {elapsed:.2f} 秒")
        print(f"{'='*60}\n")


def main():
    """主函数 - 命令行接口"""
    import argparse

    parser = argparse.ArgumentParser(description="单个 Shard 执行器")
    parser.add_argument(
        "--shard-id",
        type=str,
        required=True,
        help="Shard ID (如 shard_0)"
    )
    parser.add_argument(
        "--chapters",
        type=str,
        required=False,
        help="章节列表（JSON 数组格式或逗号分隔）"
    )
    parser.add_argument(
        "--data-type",
        type=str,
        default="uk",
        choices=["uk", "ni"],
        help="数据类型"
    )
    parser.add_argument(
        "--output-db",
        type=str,
        help="输出数据库路径"
    )
    parser.add_argument(
        "--task-file",
        type=str,
        help="从文件读取任务分配（JSON 格式）"
    )

    args = parser.parse_args()

    # 解析章节列表
    if args.task_file:
        # 从文件读取任务分配
        with open(args.task_file, 'r') as f:
            task_assignment = json.load(f)
        chapters = task_assignment.get(args.shard_id, [])
    elif args.chapters:
        if args.chapters.startswith("["):
            # JSON 格式
            chapters = json.loads(args.chapters)
        else:
            # 逗号分隔
            chapters = args.chapters.split(",")
    else:
        print(f"❌ 必须提供 --chapters 或 --task-file 参数")
        sys.exit(1)

    if not chapters:
        print(f"❌ 没有分配章节给 {args.shard_id}")
        sys.exit(1)

    # 创建并执行 shard
    executor = ShardExecutor(
        shard_id=args.shard_id,
        chapters=chapters,
        data_type=args.data_type,
        output_db=args.output_db
    )

    # 执行
    result = asyncio.run(executor.execute())

    # 根据状态设置退出码
    if result["status"] == "failed":
        sys.exit(1)
    elif result["status"] == "partial":
        sys.exit(0)  # 部分成功也算成功
    else:
        sys.exit(0)


if __name__ == "__main__":
    main()
