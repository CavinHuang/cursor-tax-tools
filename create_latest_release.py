#!/usr/bin/env python3
"""
创建 latest-data 标签指向最新数据发布
"""

import subprocess
import sys
from datetime import datetime

def run_command(cmd):
    """运行命令并返回结果"""
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        return result.returncode == 0, result.stdout, result.stderr
    except Exception as e:
        return False, "", str(e)

def main():
    print("INFO: 创建 latest-data 标签...")

    # 删除现有的 latest-data 标签（如果存在）
    success, stdout, stderr = run_command("gh release delete latest-data --yes 2>/dev/null || true")
    if success:
        print("INFO: 删除了现有的 latest-data release")

    success, stdout, stderr = run_command("git tag -d latest-data 2>/dev/null || true")
    if success:
        print("INFO: 删除了现有的 latest-data 标签")

    # 获取当前最新数据标签
    success, stdout, stderr = run_command("git tag -l 'data-*' --sort=-version:refname | head -1")
    if not success or not stdout.strip():
        print("ERROR: 无法获取最新数据标签")
        return 1

    latest_tag = stdout.strip()
    print(f"INFO: 找到最新数据标签: {latest_tag}")

    # 创建新的 latest-data 标签指向相同提交
    success, stdout, stderr = run_command(f"git tag latest-data {latest_tag}")
    if not success:
        print(f"ERROR: 创建标签失败: {stderr}")
        return 1

    print("INFO: 本地标签创建成功")

    # 推送标签到远程
    success, stdout, stderr = run_command("git push origin latest-data --force")
    if not success:
        print(f"ERROR: 推送标签失败: {stderr}")
        return 1

    print("SUCCESS: latest-data 标签创建并推送成功!")

    # 创建 latest-data release
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    release_notes = f"""最新关税数据

当前版本: {latest_tag}
更新时间: {current_time}

这是始终指向最新数据的永久链接。建议在应用中使用以下链接：
- 元数据: https://github.com/CavinHuang/cursor-tax-tools/releases/download/latest-data/metadata.json
- 数据库: https://github.com/CavinHuang/cursor-tax-tools/releases/download/latest-data/tariffs.db

历史版本请查看 Releases 页面。"""

    success, stdout, stderr = run_command(f'gh release create latest-data --title "Latest Tariff Data" --notes "{release_notes}" --target latest-data')
    if not success:
        print(f"ERROR: 创建 release 失败: {stderr}")
        return 1

    print("SUCCESS: latest-data release 创建成功!")
    print("INFO: 远程更新现在应该可以工作了")

    return 0

if __name__ == "__main__":
    sys.exit(main())