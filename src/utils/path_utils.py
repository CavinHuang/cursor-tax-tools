import os
import logging

logger = logging.getLogger(__name__)

def ensure_app_directories():
    """确保应用程序所需的目录结构存在"""
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))

    directories = {
        'datas': os.path.join(base_dir, 'datas'),
        'templates': os.path.join(base_dir, 'datas', 'templates'),
        'output': os.path.join(base_dir, 'datas', 'output'),
    }

    for name, path in directories.items():
        try:
            os.makedirs(path, exist_ok=True)
            logger.debug(f"确保目录存在: {path}")
        except Exception as e:
            logger.error(f"创建目录失败 {name}: {str(e)}")
            raise

def get_app_path(path_type: str = "") -> str:
    """获取应用程序相关路径

    Args:
        path_type: 路径类型，可选值：
            - "": 返回应用程序根目录
            - "data": 返回数据目录
            - "templates": 返回模板目录
            - "output": 返回输出目录
    """
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))

    paths = {
        "": base_dir,
        "data": os.path.join(base_dir, "datas"),
        "templates": os.path.join(base_dir, "datas", "templates"),
        "output": os.path.join(base_dir, "datas", "output")
    }

    path = paths.get(path_type, base_dir)
    os.makedirs(path, exist_ok=True)
    return path