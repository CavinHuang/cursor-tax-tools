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

            scraper = TariffScraper()
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
        # 这里应该调用实际的爬虫逻辑
        # 暂时返回模拟数据
        await asyncio.sleep(0.1)  # 模拟网络延迟
        return [f"https://example.com/chapter/{chapter}"]

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
        required=True,
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
    elif args.chapters.startswith("["):
        # JSON 格式
        chapters = json.loads(args.chapters)
    else:
        # 逗号分隔
        chapters = args.chapters.split(",")

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
