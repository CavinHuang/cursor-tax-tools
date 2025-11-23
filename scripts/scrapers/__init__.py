"""
Scrapers Module - 爬虫核心模块

这个包包含了所有的爬虫实现，包括：
- tariff_scraper.py: 关税数据爬虫（原版和优化版）

用法示例：
    from scripts.scrapers.tariff_scraper import TariffScraper, BatchUpdateManager

    scraper = TariffScraper()
    manager = BatchUpdateManager()
"""

__version__ = '1.0.0'
__all__ = ['tariff_scraper']
