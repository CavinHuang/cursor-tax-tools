import yaml
import sys
import os

def main():
    workflow_path = '.github/workflows/scrape-tariff.yml'

    try:
        with open(workflow_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # 基本YAML语法检查
        yaml.safe_load(content)
        print("YAML syntax: OK")

        # 检查是否还有问题模式
        if 'env.' in content and '||' in content:
            lines = content.split('\n')
            for i, line in enumerate(lines, 1):
                if 'env.' in line and '||' in line:
                    print(f"Found potential issue at line {i}: {line.strip()}")
                    return 1

        print("Expression format: OK")
        print("Validation: PASSED")
        return 0

    except yaml.YAMLError as e:
        print(f"YAML error: {e}")
        return 1
    except Exception as e:
        print(f"Error: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())