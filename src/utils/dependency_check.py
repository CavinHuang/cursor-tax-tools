import importlib
import logging

logger = logging.getLogger(__name__)

def check_dependencies():
    """检查必要的依赖包是否已安装"""
    required_packages = [
        'bs4',
        'requests',
        'pandas',
        'openpyxl',
        'Levenshtein',
        'aiohttp'
    ]

    missing_packages = []
    for package in required_packages:
        try:
            importlib.import_module(package)
            logger.debug(f"依赖包 {package} 已安装")
        except ImportError:
            missing_packages.append(package)
            logger.error(f"缺少依赖包: {package}")

    if missing_packages:
        raise ImportError(
            f"缺少必要的依赖包: {', '.join(missing_packages)}\n"
            f"请运行: pip install -r requirements.txt"
        )