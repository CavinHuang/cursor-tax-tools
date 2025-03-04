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