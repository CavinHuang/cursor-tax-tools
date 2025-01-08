import pandas as pd
import os

def create_template():
    """创建批量查询的Excel模板文件"""
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
    print(f"模板文件已创建: {template_path}")

if __name__ == "__main__":
    create_template()