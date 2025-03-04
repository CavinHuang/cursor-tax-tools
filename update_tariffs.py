import asyncio
import logging
from typing import Dict, List, Set, Optional, Tuple
from tariff_db import TariffDB
from tools.web_scraper import scrape_urls
from bs4 import BeautifulSoup
import re

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class TariffScraper:
    def __init__(self):
        self.uk_base_url = "https://www.trade-tariff.service.gov.uk/commodities/"
        self.ni_base_url = "https://www.trade-tariff.service.gov.uk/xi/commodities/"
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        self.timeout = 30
        self.max_retries = 3
        self.db = TariffDB()
        self.progress_callback = None
        self.total_items = 0
        self.processed_items = 0
        self.log_callback = None
        self.should_stop = None

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
            progress = self.processed_items / (self.total_items * 2)
            self.progress_callback(progress, current_code)

    def log(self, message: str):
        """输出日志"""
        logger.info(message)
        if self.log_callback:
            self.log_callback(message)

    async def scrape_tariffs(self) -> bool:
        """抓取所有关税数据"""
        try:
            # 获取所有商品编码
            codes = await self.get_commodity_codes()
            if not codes:
                logger.error("获取商品编码失败")
                return False

            self.total_items = len(codes)
            logger.info(f"开始更新 {self.total_items} 个商品的关税数据")

            # 更新英国数据
            success_uk = await self.update_uk_tariffs(codes)
            if not success_uk:
                logger.error("更新英国关税数据失败")
                return False

            # 更新北爱尔兰数据
            success_ni = await self.update_ni_tariffs(codes)
            if not success_ni:
                logger.error("更新北爱尔兰关税数据失败")
                return False

            logger.info("所有数据更新完成")
            return True

        except Exception as e:
            logger.error(f"更新失败: {str(e)}")
            return False

    async def get_commodity_codes(self) -> List[str]:
        """获取所有商品编码"""
        # 这里可以添加从网站获取最新编码的逻辑
        # 现在先使用数据库中的编码
        return self.db.get_all_codes()

    async def update_uk_tariffs(self, codes: List[str]) -> bool:
        """更新英国关税数据"""
        try:
            batch_size = 10 if len(codes) > 1 else 1  # 单个重试时不使用批处理
            total_batches = (len(codes) + batch_size - 1) // batch_size
            self.log(f"开始更新英国关税数据，共 {len(codes)} 个商品")

            for i in range(0, len(codes), batch_size):
                # 检查是否应该停止
                if self.check_should_stop():
                    self.log("收到停止信号，正在停止更新...")
                    return False

                batch = codes[i:i + batch_size]
                current_batch = i // batch_size + 1
                self.log(f"处理第 {current_batch}/{total_batches} 批")
                urls = [f"{self.uk_base_url}{code}" for code in batch]

                contents = await self.scrape_with_retry(urls)

                for code, content in zip(batch, contents):
                    if self.check_should_stop():
                        return False

                    try:
                        if content:
                            tariff_data = self.parse_commodity_page(content)
                            if tariff_data:
                                self.db.update_uk_tariff(
                                    code,
                                    tariff_data['description'],
                                    tariff_data['rate'],
                                    tariff_data['url']
                                )
                            else:
                                raise Exception("解析页面失败")
                        else:
                            raise Exception("获取数据失败")
                    except Exception as e:
                        logger.error(f"处理英国商品 {code} 失败: {str(e)}")
                        self.db.add_scrape_error(code, f"英国数据: {str(e)}")
                        if len(codes) == 1:  # 单个重试时，立即返回失败
                            return False

                    self.processed_items += 1
                    self.update_progress(code)

            return True
        except Exception as e:
            logger.error(f"更新英国关税数据失败: {str(e)}")
            return False

    async def update_ni_tariffs(self, codes: List[str]) -> bool:
        """更新北爱尔兰关税数据"""
        try:
            batch_size = 10
            total_batches = (len(codes) + batch_size - 1) // batch_size
            self.log(f"开始更新北爱尔兰关税数据，共 {len(codes)} 个商品")

            for i in range(0, len(codes), batch_size):
                # 检查是否应该停止
                if self.check_should_stop():
                    self.log("收到停止信号，正在停止更新...")
                    return False

                batch = codes[i:i + batch_size]
                current_batch = i // batch_size + 1
                self.log(f"处理第 {current_batch}/{total_batches} 批")
                urls = [f"{self.ni_base_url}{code}" for code in batch]

                contents = await self.scrape_with_retry(urls)

                for code, content in zip(batch, contents):
                    if self.check_should_stop():
                        return False

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
                            logger.error(f"处理北爱尔兰商品 {code} 失败: {str(e)}")

                    self.processed_items += 1
                    self.update_progress(code)

            return True
        except Exception as e:
            logger.error(f"更新北爱尔兰关税数据失败: {str(e)}")
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
                if any(results):
                    return results
            except Exception as e:
                logger.warning(f"第{retry + 1}次重试失败: {str(e)}")
                await asyncio.sleep(1)
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

def main():
    """主函数"""
    scraper = TariffScraper()
    loop = asyncio.get_event_loop()
    loop.run_until_complete(scraper.scrape_tariffs())
    loop.close()

if __name__ == "__main__":
    main()