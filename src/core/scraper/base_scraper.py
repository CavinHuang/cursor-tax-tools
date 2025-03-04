import asyncio
import logging
from typing import Dict, List, Optional
from bs4 import BeautifulSoup
from ...utils.web_scraper import scrape_urls
from ..db.tariff_db import TariffDB

logger = logging.getLogger(__name__)

class BaseScraper:
    def __init__(self):
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        self.timeout = 30
        self.max_retries = 3
        self.db = TariffDB()
        self.progress_callback = None
        self.log_callback = None
        self.should_stop = None
        self.total_items = 0
        self.processed_items = 0

    def set_progress_callback(self, callback):
        """设置进度回调函数"""
        self.progress_callback = callback

    def set_log_callback(self, callback):
        """设置日志回调函数"""
        self.log_callback = callback

    def set_stop_check(self, callback):
        """设置停止检查回调"""
        self.should_stop = callback

    def check_should_stop(self) -> bool:
        """检查是否应该停止"""
        return self.should_stop and self.should_stop()

    def update_progress(self, current_code=None):
        """更新进度"""
        if self.progress_callback and self.total_items > 0:
            progress = self.processed_items / self.total_items
            self.progress_callback(progress, current_code)

    def log(self, message: str):
        """输出日志"""
        logger.info(message)
        if self.log_callback:
            self.log_callback(message)

    def format_commodity_code(self, code: str) -> str:
        """格式化商品编码，确保是10位数字"""
        # 移除所有非数字字符
        code = ''.join(filter(str.isdigit, code))
        # 补零到10位
        return code.zfill(10)

    async def scrape_with_retry(self, urls: List[str]) -> List[str]:
        """带重试的抓取"""
        try:
            # 确保URL中的编码格式正确
            formatted_urls = []
            for url in urls:
                if '/commodities/' in url:
                    code = url.split('/commodities/')[-1]
                    base = url.split('/commodities/')[0]
                    formatted_code = self.format_commodity_code(code)
                    formatted_urls.append(f"{base}/commodities/{formatted_code}")
                else:
                    formatted_urls.append(url)

            for retry in range(self.max_retries):
                try:
                    results = await scrape_urls(
                        formatted_urls,
                        headers=self.headers,
                        timeout=self.timeout
                    )
                    if any(results):  # 只要有一个成功就返回
                        return results
                except Exception as e:
                    logger.warning(f"第{retry + 1}次重试失败: {str(e)}")
                    await asyncio.sleep(1)  # 失败后等待1秒再重试
            return [""] * len(urls)
        except Exception as e:
            logger.error(f"URL处理失败: {str(e)}")
            return [""] * len(urls)

    def parse_commodity_page(self, html_content: str) -> Optional[Dict]:
        """解析商品页面"""
        try:
            soup = BeautifulSoup(html_content, 'html.parser')

            # 获取商品描述
            description = ""
            desc_elem = soup.find('h1', {'class': 'commodity-description'})
            if desc_elem:
                description = desc_elem.get_text().strip()

            # 查找税率表格
            duty_table = soup.find('table', {'class': 'duty-rates'})
            if not duty_table:
                return None

            # 查找"All countries"行的税率
            rate = None
            for row in duty_table.find_all('tr'):
                cells = row.find_all('td')
                if cells and 'All countries' in cells[0].get_text():
                    rate = cells[1].get_text().strip()
                    break

            if rate:
                return {
                    'description': description,
                    'rate': rate,
                    'url': str(soup.url) if hasattr(soup, 'url') else ''
                }

            return None

        except Exception as e:
            logger.error(f"解析页面失败: {str(e)}")
            return None

    # ... 共用方法 ...