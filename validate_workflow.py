#!/usr/bin/env python3
"""
GitHub Actions 工作流验证脚本
"""

import yaml
import sys
import os

def validate_workflow_syntax(file_path):
    """验证工作流语法"""
    print(f"Validating workflow: {file_path}")

    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # 检查基本的YAML语法
        yaml.safe_load(content)
        print("✓ YAML syntax: OK")

        # 检查关键配置
        lines = content.split('\n')
        issues = []

        for i, line in enumerate(lines, 1):
            line = line.strip()

            # 检查是否还有未修复的env引用
            if 'env.' in line and '||' in line:
                issues.append(f"Line {i}: Found unresolved env reference: {line}")

            # 检查timeout-minutes的格式
            if line.startswith('timeout-minutes:') and '${{' in line:
                issues.append(f"Line {i}: timeout-minutes should not contain expressions")

        if issues:
            print("⚠ Issues found:")
            for issue in issues:
                print(f"  - {issue}")
            return False
        else:
            print("✓ Expression format: OK")
            return True

    except yaml.YAMLError as e:
        print(f"✗ YAML syntax error: {e}")
        return False
    except Exception as e:
        print(f"✗ Validation error: {e}")
        return False

def main():
    workflow_path = '.github/workflows/scrape-tariff.yml'

    if not os.path.exists(workflow_path):
        print(f"Workflow file not found: {workflow_path}")
        return 1

    print("GitHub Actions Workflow Validation")
    print("=" * 50)

    if validate_workflow_syntax(workflow_path):
        print("\n🎉 Workflow validation PASSED!")
        print("The workflow file is ready for GitHub Actions.")
        return 0
    else:
        print("\n❌ Workflow validation FAILED!")
        print("Please fix the issues before committing.")
        return 1

if __name__ == "__main__":
    sys.exit(main())