import asyncio
import logging
from typing import Dict, List, Set
from tariff_db import TariffDB
from tools.web_scraper import scrape_urls
from bs4 import BeautifulSoup
import re

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class Scraper:
    def __init__(self):
        self.base_url = "https://www.trade-tariff.service.gov.uk/xi/commodities/"
        self.browse_url = f"{self.base_url}/browse"
        self.visited_urls: Set[str] = set()
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        self.timeout = 30  # 请求超时时间
        self.max_retries = 3  # 最大重试次数
        self.db = TariffDB()
        self.progress_callback = None
        self.total_items = 0
        self.processed_items = 0

    def set_progress_callback(self, callback):
        """设置进度回调函数"""
        self.progress_callback = callback

    def update_progress(self):
        """更新进度"""
        if self.progress_callback and self.total_items > 0:
            progress = self.processed_items / self.total_items
            self.progress_callback(progress)

    async def scrape_tariffs(self):
        """抓取所有关税数据"""
        try:
            # 获取所有商品编码
            codes = self.db.get_all_codes()
            self.total_items = len(codes)
            logger.info(f"开始更新 {self.total_items} 个商品的北爱尔兰关税数据")

            # 分批处理
            batch_size = 10
            for i in range(0, len(codes), batch_size):
                batch = codes[i:i + batch_size]
                urls = [f"{self.base_url}{code}" for code in batch]

                # 抓取数据
                contents = await self.scrape_with_retry(urls)

                # 处理结果
                for code, content in zip(batch, contents):
                    if content:
                        try:
                            tariff_data = self.parse_commodity_page(content)
                            if tariff_data:
                                self.db.update_north_ireland_tariff(
                                    code,
                                    tariff_data['rate'],
                                    tariff_data['url']
                                )
                        except Exception as e:
                            logger.error(f"处理商品 {code} 失败: {str(e)}")

                    self.processed_items += 1
                    self.update_progress()

            logger.info("更新完成")
            return True

        except Exception as e:
            logger.error(f"更新失败: {str(e)}")
            return False

    async def scrape_with_retry(self, urls: List[str]) -> List[str]:
        """带重试的抓取"""
        for retry in range(self.max_retries):
            try:
                results = await scrape_urls(
                    urls,
                    headers=self.headers,
                    max_concurrent=3
                )
                if any(results):  # 只要有一个成功就返回
                    return results
            except Exception as e:
                logger.warning(f"第{retry + 1}次重试失败: {str(e)}")
                await asyncio.sleep(1)  # 失败后等待1秒再重试
        return [""] * len(urls)

    def parse_commodity_page(self, html_content: str) -> Dict:
        """解析商品页面"""
        try:
            soup = BeautifulSoup(html_content, 'html.parser')

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
                    'rate': rate,
                    'url': str(soup.url) if hasattr(soup, 'url') else ''
                }

            return None

        except Exception as e:
            logger.error(f"解析页面失败: {str(e)}")
            return None

def main():
    """主函数"""
    scraper = Scraper()
    loop = asyncio.get_event_loop()
    loop.run_until_complete(scraper.scrape_tariffs())
    loop.close()

if __name__ == "__main__":
    main()