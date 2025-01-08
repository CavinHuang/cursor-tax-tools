import pandas as pd
import os
import sys

def create_template():
    """创建批量查询的Excel模板文件"""
    try:
        # 创建示例数据
        data = {
            'code': ['0123456789', '9876543210'],  # 示例编码
        }

        # 创建DataFrame
        df = pd.DataFrame(data)

        # 确保目录存在
        os.makedirs('templates', exist_ok=True)

        # 保存为Excel文件
        template_path = 'templates/batch_rate_template.xlsx'
        df.to_excel(template_path, index=False)

        # 使用ASCII字符输出
        print("Template file created: " + template_path)
        return True
    except Exception as e:
        print("Error creating template:", str(e), file=sys.stderr)
        return False

if __name__ == "__main__":
    # 设置stdout编码为utf-8
    if sys.stdout.encoding != 'utf-8':
        sys.stdout.reconfigure(encoding='utf-8')

    success = create_template()
    sys.exit(0 if success else 1)