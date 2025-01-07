from tariff_db import TariffDB

def add_test_data():
    """添加测试数据"""
    db = TariffDB()
    test_data = [
        ("8517.12.00", "手机", 0.0),
        ("8517.13.00", "智能手表", 2.5),
        ("8517.14.00", "其他通讯设备", 3.0),
        ("8471.30.00", "笔记本电脑", 1.5),
        ("8471.41.00", "台式电脑", 2.0),
        ("8471.49.00", "其他计算机设备", 2.5),
    ]

    for code, desc, rate in test_data:
        db.add_tariff(code, desc, rate)

    print("测试数据添加完成")

if __name__ == "__main__":
    add_test_data()