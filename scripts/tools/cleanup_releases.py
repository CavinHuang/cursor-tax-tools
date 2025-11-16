#!/usr/bin/env python3
"""
GitHub Release清理工具
清理旧的Release文件，保留指定数量的最新版本
"""

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime
from typing import List, Dict, Optional


def run_command(cmd: List[str], capture_output: bool = True) -> subprocess.CompletedProcess:
    """运行命令"""
    try:
        return subprocess.run(cmd, capture_output=capture_output, text=True, check=True)
    except subprocess.CalledProcessError as e:
        print(f"❌ 命令执行失败: {' '.join(cmd)}", file=sys.stderr)
        print(f"错误输出: {e.stderr}", file=sys.stderr)
        raise


def install_gh_cli():
    """安装GitHub CLI"""
    try:
        run_command(['gh', '--version'])
        print("✅ GitHub CLI 已安装")
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("📦 安装 GitHub CLI...")
        try:
            # Ubuntu/Debian安装方法
            run_command(['curl', '-fsSL', 'https://cli.github.com/packages/githubcli-archive-keyring.gpg',
                        '|', 'sudo', 'dd', 'of=/usr/share/keyrings/githubcli-archive-keyring.gpg'])
            run_command(['echo', '"deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main"',
                        '|', 'sudo', 'tee', '/etc/apt/sources.list.d/github-cli.list'])
            run_command(['sudo', 'apt', 'update'])
            run_command(['sudo', 'apt', 'install', '-y', 'gh'])
            print("✅ GitHub CLI 安装完成")
            return True
        except Exception as e:
            print(f"❌ GitHub CLI 安装失败: {e}", file=sys.stderr)
            return False


def get_releases(repo: str, tag_prefix: str = 'data-') -> List[Dict]:
    """获取Release列表"""
    try:
        cmd = ['gh', 'release', 'list', '--repo', repo, '--limit', '100', '--json', 'tagName,createdAt,name']
        result = run_command(cmd)

        releases = json.loads(result.stdout)

        # 过滤指定前缀的标签
        filtered_releases = [
            release for release in releases
            if release.get('tagName', '').startswith(tag_prefix)
        ]

        # 按创建时间排序（最新的在前）
        filtered_releases.sort(key=lambda x: x.get('createdAt', ''), reverse=True)

        return filtered_releases

    except Exception as e:
        print(f"❌ 获取Release列表失败: {e}", file=sys.stderr)
        return []


def delete_release(repo: str, tag_name: str, dry_run: bool = False) -> bool:
    """删除Release"""
    try:
        if dry_run:
            print(f"[DRY RUN] 将删除Release: {tag_name}")
            return True

        cmd = ['gh', 'release', 'delete', tag_name, '--repo', repo, '--yes']
        run_command(cmd)
        print(f"✅ 已删除Release: {tag_name}")
        return True

    except Exception as e:
        print(f"❌ 删除Release失败 {tag_name}: {e}", file=sys.stderr)
        return False


def cleanup_releases(repo: str, keep_count: int = 30, tag_prefix: str = 'data-', dry_run: bool = False):
    """清理旧Release"""
    print(f"🧹 开始清理Release (保留最新 {keep_count} 个)")

    # 获取Release列表
    releases = get_releases(repo, tag_prefix)

    if not releases:
        print("ℹ️ 没有找到需要清理的Release")
        return

    print(f"📊 找到 {len(releases)} 个 {tag_prefix} 前缀的Release")

    # 确定要删除的Release（保留最新的keep_count个）
    to_delete = releases[keep_count:]

    if not to_delete:
        print("✅ 没有需要清理的Release")
        return

    print(f"🗑️ 将删除 {len(to_delete)} 个旧Release:")

    # 显示将要删除的Release
    for release in to_delete:
        tag_name = release.get('tagName', 'unknown')
        created_at = release.get('createdAt', 'unknown')
        print(f"  - {tag_name} (创建时间: {created_at})")

    if dry_run:
        print(f"\n[DRY RUN] 模拟运行，实际不会删除任何Release")
        return

    # 确认删除
    if input(f"\n⚠️ 确认删除这 {len(to_delete)} 个Release吗? (y/N): ").lower() != 'y':
        print("❌ 用户取消删除")
        return

    # 删除Release
    deleted_count = 0
    for release in to_delete:
        tag_name = release.get('tagName')
        if delete_release(repo, tag_name, dry_run):
            deleted_count += 1

    print(f"✅ 清理完成! 删除了 {deleted_count} 个Release")


def analyze_releases(repo: str, tag_prefix: str = 'data-'):
    """分析Release情况"""
    print(f"📊 分析Release情况")

    releases = get_releases(repo, tag_prefix)

    if not releases:
        print("ℹ️ 没有找到Release")
        return

    print(f"📋 总共找到 {len(releases)} 个 {tag_prefix} 前缀的Release")

    # 按月份统计
    monthly_stats = {}
    for release in releases:
        created_at = release.get('createdAt', '')
        if created_at:
            try:
                # 解析ISO格式时间
                dt = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                month_key = dt.strftime('%Y-%m')
                monthly_stats[month_key] = monthly_stats.get(month_key, 0) + 1
            except:
                pass

    if monthly_stats:
        print("\n📅 按月统计:")
        for month, count in sorted(monthly_stats.items()):
            print(f"  {month}: {count} 个Release")

    # 显示最新的几个Release
    print("\n🔝 最新的10个Release:")
    for i, release in enumerate(releases[:10]):
        tag_name = release.get('tagName', 'unknown')
        name = release.get('name', '')
        created_at = release.get('createdAt', '')
        print(f"  {i+1:2d}. {tag_name} - {created_at}")

    # 估算存储使用情况
    total_size_mb = 0
    sample_count = 0

    print("\n📦 估算存储使用情况:")
    for release in releases[:5]:  # 只检查前5个作为样本
        tag_name = release.get('tagName')
        try:
            cmd = ['gh', 'release', 'view', tag_name, '--repo', repo, '--json', 'assets']
            result = run_command(cmd)
            release_data = json.loads(result.stdout)

            release_size = 0
            for asset in release_data.get('assets', []):
                release_size += asset.get('size', 0)

            total_size_mb += release_size / 1024 / 1024
            sample_count += 1
            print(f"  {tag_name}: {release_size / 1024 / 1024:.1f}MB")

        except Exception as e:
            print(f"  {tag_name}: 无法获取大小")

    if sample_count > 0:
        avg_size_mb = total_size_mb / sample_count
        estimated_total_mb = avg_size_mb * len(releases)
        print(f"\n💾 平均每个Release: {avg_size_mb:.1f}MB")
        print(f"💾 估算总存储使用: {estimated_total_mb:.1f}MB")


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description='GitHub Release清理工具')
    parser.add_argument('--repo', '-r',
                       default=os.getenv('GITHUB_REPOSITORY', 'owner/repo'),
                       help='GitHub仓库 (默认: 从GITHUB_REPOSITORY环境变量获取)')
    parser.add_argument('--keep', '-k', type=int, default=30,
                       help='保留的Release数量 (默认: 30)')
    parser.add_argument('--prefix', '-p', default='data-',
                       help='标签前缀 (默认: data-)')
    parser.add_argument('--dry-run', '-n', action='store_true',
                       help='模拟运行，不实际删除')
    parser.add_argument('--analyze', '-a', action='store_true',
                       help='只分析，不删除')
    parser.add_argument('--install-cli', action='store_true',
                       help='安装GitHub CLI')

    args = parser.parse_args()

    print("🧹 GitHub Release清理工具 v1.0")
    print("="*40)

    # 安装GitHub CLI
    if args.install_cli:
        install_gh_cli()
        return

    # 检查GitHub CLI
    try:
        subprocess.run(['gh', '--version'], capture_output=True, check=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("❌ GitHub CLI 未安装", file=sys.stderr)
        print("💡 请先安装: pip install gh-cli 或使用 --install-cli 参数", file=sys.stderr)
        sys.exit(1)

    # 检查认证
    try:
        result = subprocess.run(['gh', 'auth', 'status'], capture_output=True, text=True)
        if result.returncode != 0:
            print("❌ GitHub CLI 未认证", file=sys.stderr)
            print("💡 请先运行: gh auth login", file=sys.stderr)
            sys.exit(1)
    except:
        pass

    print(f"📋 仓库: {args.repo}")
    print(f"🏷️ 标签前缀: {args.prefix}")
    print(f"🔢 保留数量: {args.keep}")
    print()

    if args.analyze:
        analyze_releases(args.repo, args.prefix)
    else:
        cleanup_releases(args.repo, args.keep, args.prefix, args.dry_run)


if __name__ == "__main__":
    main()