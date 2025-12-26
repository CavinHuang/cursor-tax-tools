#!/usr/bin/env python3
"""
章节调度器 - 负责章节分配和断点恢复

功能：
1. 解析现有 metadata.json
2. 识别已完成和待处理的章节
3. 生成每个 shard 的任务分配
4. 创建部分完成的元数据
"""

import json
import sys
import os
from typing import Dict, List, Optional, Tuple
from pathlib import Path

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))


class ChapterScheduler:
    """章节调度器 - 管理章节分配和断点恢复"""

    # 默认的章节分片配置
    DEFAULT_SHARD_RANGES = {
        "shard_0": (1, 25, "uk"),     # UK章节1-25
        "shard_1": (26, 50, "uk"),    # UK章节26-50
        "shard_2": (51, 75, "uk"),    # UK章节51-75
        "shard_3": (76, 99, "uk"),    # UK章节76-99
        "shard_4": (1, 50, "ni"),     # NI章节1-50
        "shard_5": (51, 99, "ni"),    # NI章节51-99
    }

    def __init__(self, metadata_path: Optional[str] = None):
        """
        初始化章节调度器

        Args:
            metadata_path: 现有 metadata.json 的路径，如果为 None 则尝试下载
        """
        self.metadata = None
        self.metadata_path = metadata_path
        self._load_metadata()

    def _load_metadata(self):
        """加载现有的元数据"""
        if self.metadata_path and os.path.exists(self.metadata_path):
            try:
                with open(self.metadata_path, 'r', encoding='utf-8') as f:
                    self.metadata = json.load(f)
                print(f"✅ 已加载元数据: {self.metadata_path}")
            except Exception as e:
                print(f"⚠️  加载元数据失败: {e}")
                self.metadata = None
        else:
            print("ℹ️  未找到现有元数据，将进行首次完整爬取")

    def get_all_chapters(self) -> Dict[str, List[str]]:
        """
        获取所有章节列表（按 shard 分组）

        Returns:
            Dict[str, List[str]]: 键为 shard_id，值为章节列表（格式化为两位数）
        """
        tasks = {}

        for shard_id, (start_chapter, end_chapter, _) in self.DEFAULT_SHARD_RANGES.items():
            chapters = [
                f"{chapter:02d}"  # 格式化为两位数，如 "01", "02"
                for chapter in range(start_chapter, end_chapter + 1)
            ]
            tasks[shard_id] = chapters

        return tasks

    def get_pending_tasks(self) -> Dict[str, List[str]]:
        """
        获取每个 shard 待处理的章节列表

        Returns:
            Dict[str, List[str]]: 键为 shard_id，值为待处理章节列表
        """
        # 首次运行或没有元数据
        if not self.metadata or not self.metadata.get("partial_info"):
            print("ℹ️  首次运行，将爬取所有章节")
            return self.get_all_chapters()

        # 断点恢复：排除已完成的章节
        partial_info = self.metadata["partial_info"]
        completed_chapters = set(partial_info.get("completed_chapters", []))

        print(f"ℹ️  断点恢复: 已完成 {len(completed_chapters)} 个章节")

        return self._filter_pending_chapters(completed_chapters)

    def _filter_pending_chapters(self, completed_chapters: set) -> Dict[str, List[str]]:
        """
        过滤掉已完成的章节

        Args:
            completed_chapters: 已完成章节的集合

        Returns:
            Dict[str, List[str]]: 键为 shard_id，值为待处理章节列表
        """
        tasks = {}

        for shard_id, (start_chapter, end_chapter, _) in self.DEFAULT_SHARD_RANGES.items():
            chapters = [
                f"{chapter:02d}"
                for chapter in range(start_chapter, end_chapter + 1)
                if f"{chapter:02d}" not in completed_chapters
            ]

            if chapters:  # 只包含有待处理任务的 shard
                tasks[shard_id] = chapters

        return tasks

    def create_partial_metadata(
        self,
        shard_id: str,
        completed_chapters: List[str],
        completed_urls: List[str],
        total_urls: int
    ) -> dict:
        """
        创建部分完成的元数据

        Args:
            shard_id: 当前 shard 的 ID
            completed_chapters: 当前 shard 已完成的章节列表
            completed_urls: 当前 shard 已处理的 URL 列表
            total_urls: 总 URL 数量

        Returns:
            dict: 部分完成的元数据结构
        """
        # 计算所有已完成的章节数量（包括之前运行的）
        all_completed_chapters = set(completed_chapters)

        if self.metadata and self.metadata.get("partial_info"):
            all_completed_chapters.update(
                self.metadata["partial_info"].get("completed_chapters", [])
            )

        pending_chapters = self._get_all_chapter_list()
        for chapter in all_completed_chapters:
            if chapter in pending_chapters:
                pending_chapters.remove(chapter)

        return {
            "is_partial": True,
            "shard_id": shard_id,
            "completed_chapters": sorted(list(all_completed_chapters)),
            "pending_chapters": sorted(pending_chapters),
            "completed_urls": completed_urls,
            "total_urls": total_urls,
            "completed_count": len(completed_urls)
        }

    def _get_all_chapter_list(self) -> List[str]:
        """获取所有章节的列表（01-99）"""
        return [f"{i:02d}" for i in range(1, 100)]

    def save_shard_progress(self, shard_id: str, progress_data: dict):
        """
        保存单个 shard 的进度

        Args:
            shard_id: Shard ID
            progress_data: 进度数据字典
        """
        progress_file = f"shard_{shard_id}_progress.json"

        try:
            with open(progress_file, 'w', encoding='utf-8') as f:
                json.dump(progress_data, f, indent=2, ensure_ascii=False, default=str)
            print(f"💾 已保存进度: {progress_file}")
        except Exception as e:
            print(f"⚠️  保存进度失败: {e}")

    def generate_task_summary(self, tasks: Dict[str, List[str]]) -> dict:
        """
        生成任务分配摘要

        Args:
            tasks: 任务分配字典

        Returns:
            dict: 任务摘要
        """
        total_chapters = sum(len(chapters) for chapters in tasks.values())

        summary = {
            "total_shards": len(tasks),
            "total_chapters": total_chapters,
            "shard_details": {}
        }

        for shard_id, chapters in tasks.items():
            summary["shard_details"][shard_id] = {
                "chapter_count": len(chapters),
                "chapters": chapters[:5] + ["..."] if len(chapters) > 5 else chapters
            }

        return summary


def main():
    """主函数 - 命令行接口"""
    import argparse

    parser = argparse.ArgumentParser(description="章节调度器")
    parser.add_argument(
        "--metadata",
        type=str,
        help="现有 metadata.json 的路径"
    )
    parser.add_argument(
        "--output",
        type=str,
        default="task_assignment.json",
        help="输出任务分配文件路径"
    )
    parser.add_argument(
        "--summary",
        action="store_true",
        help="显示任务摘要"
    )

    args = parser.parse_args()

    # 创建调度器
    scheduler = ChapterScheduler(args.metadata)

    # 获取待处理任务
    tasks = scheduler.get_pending_tasks()

    # 保存任务分配
    if args.output:
        with open(args.output, 'w', encoding='utf-8') as f:
            json.dump(tasks, f, indent=2, ensure_ascii=False)
        print(f"✅ 任务分配已保存到: {args.output}")

    # 显示摘要
    if args.summary:
        summary = scheduler.generate_task_summary(tasks)
        print("\n📊 任务分配摘要:")
        print(f"   总Shard数: {summary['total_shards']}")
        print(f"   总章节数: {summary['total_chapters']}")
        for shard_id, detail in summary['shard_details'].items():
            print(f"   {shard_id}: {detail['chapter_count']} 个章节")


if __name__ == "__main__":
    main()
