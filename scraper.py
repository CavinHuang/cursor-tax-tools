import asyncio
from typing import List, Dict, Set
from tools.web_scraper import scrape_urls
from bs4 import BeautifulSoup
import re
import json
import logging
import aiohttp

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def scrape_urls(urls: List[str], headers: Dict = None, timeout: int = 30) -> List[str]:
    """异步抓取多个URL"""
    async def fetch_url(url: str) -> str:
        try:
            async with aiohttp.ClientSession(headers=headers) as session:
                async with session.get(url, timeout=timeout) as response:
                    if response.status == 200:
                        return await response.text()
                    else:
                        logger.error(f"请求失败: {url}, 状态码: {response.status}")
                        return ""
        except asyncio.TimeoutError:
            logger.error(f"请求超时: {url}")
            return ""
        except Exception as e:
            logger.error(f"请求异常: {url}, {str(e)}")
            return ""

    # 使用信号量控制并发数
    sem = asyncio.Semaphore(3)  # 最多3个并发请求

    async def fetch_with_sem(url: str) -> str:
        async with sem:
            return await fetch_url(url)

    # 并发请求所有URL
    tasks = [fetch_with_sem(url) for url in urls]
    try:
        results = await asyncio.gather(*tasks)
        return results
    except Exception as e:
        logger.error(f"并发请求失败: {str(e)}")
        return [""] * len(urls)

class TariffScraper:
    def __init__(self):
        self.base_url = "https://www.trade-tariff.service.gov.uk"
        self.browse_url = f"{self.base_url}/browse"
        self.visited_urls: Set[str] = set()
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        self.timeout = 30  # 请求超时时间
        self.max_retries = 3  # 最大重试次数

    async def scrape_with_retry(self, urls: List[str]) -> List[str]:
        """带重试的抓取"""
        for retry in range(self.max_retries):
            try:
                results = await scrape_urls(urls, headers=self.headers, timeout=self.timeout)
                if any(results):  # 只要有一个成功就返回
                    return results
            except Exception as e:
                logger.warning(f"第{retry + 1}次重试失败: {str(e)}")
                await asyncio.sleep(1)  # 失败后等待1秒再重试
        return [""] * len(urls)

    def parse_section_links(self, html: str) -> List[str]:
        """解析主页面获取section链接"""
        soup = BeautifulSoup(html, 'html.parser')
        links = []

        # 查找section表格
        section_table = soup.find('table', class_='tariff-table')
        if not section_table:
            logger.error("未找到section表格")
            return links

        # 查找所有section链接
        for row in section_table.find_all('tr'):
            link = row.find('a')
            if link and link.get('href'):
                href = link.get('href')
                if href.startswith('/sections/'):
                    full_url = f"{self.base_url}{href}"
                    if full_url not in self.visited_urls:
                        links.append(full_url)
                        logger.debug(f"找到section链接: {full_url}")

        logger.info(f"共找到 {len(links)} 个section链接")
        return links

    def parse_chapter_links(self, html: str) -> List[str]:
        """解析section页面获取chapter链接"""
        soup = BeautifulSoup(html, 'html.parser')
        links = []

        # 查找chapter表格
        chapter_table = soup.find('table', class_='govuk-table')
        if not chapter_table:
            logger.debug("未找到chapter表格")
            return links

        # 查找所有chapter链接
        for row in chapter_table.find_all('tr', class_='govuk-table__row'):
            link = row.find('a')
            if link and link.get('href'):
                href = link.get('href')
                if href.startswith('/chapters/'):
                    full_url = f"{self.base_url}{href}"
                    if full_url not in self.visited_urls:
                        links.append(full_url)
                        logger.debug(f"找到chapter链接: {full_url}")

        logger.info(f"共找到 {len(links)} 个chapter链接")
        return links

    def parse_heading_links(self, html: str) -> List[str]:
        """解析chapter页面获取heading链接"""
        soup = BeautifulSoup(html, 'html.parser')
        links = []

        # 查找heading表格
        tables = soup.find_all('table', class_='govuk-table')
        for table in tables:
            for row in table.find_all('tr', class_='govuk-table__row'):
                link = row.find('a')
                if link and link.get('href'):
                    href = link.get('href')
                    if href.startswith('/headings/'):
                        full_url = f"{self.base_url}{href}"
                        if full_url not in self.visited_urls:
                            links.append(full_url)
                            logger.debug(f"找到heading链接: {full_url}")

        logger.info(f"共找到 {len(links)} 个heading链接")
        return links

    def parse_commodity_links(self, html: str) -> List[str]:
        """解析heading页面获取commodity链接"""
        soup = BeautifulSoup(html, 'html.parser')
        links = []

        # 查找所有commodity链接
        for link in soup.find_all('a', href=True):
            href = link.get('href')
            if href and '/commodities/' in href:
                full_url = f"{self.base_url}{href}"
                if full_url not in self.visited_urls:
                    links.append(full_url)
                    logger.debug(f"找到commodity链接: {full_url}")

        logger.info(f"共找到 {len(links)} 个commodity链接")
        return links

    def parse_commodity_page(self, html: str, url: str = "") -> Dict:
        """解析commodity页面获取税率信息"""
        soup = BeautifulSoup(html, 'html.parser')
        result = {}

        # 查找商品编码
        code_match = re.search(r'/commodities/(\d+)', str(soup))
        if code_match:
            result['code'] = code_match.group(1)
            result['url'] = url or f"https://www.trade-tariff.service.gov.uk/commodities/{result['code']}"

        # 查找商品描述
        desc_elem = soup.find('h1', class_='commodity-description')
        if desc_elem:
            result['description'] = desc_elem.text.strip()
            logger.debug(f"找到商品描述: {result['description']}")
        else:
            logger.warning(f"未找到商品描述 for code: {result.get('code')}")
            result['description'] = ''

        # 查找税率 - 使用第一个找到的All countries的税率
        found_rate = False
        duty_tables = soup.find_all('table', class_='govuk-table')
        for table in duty_tables:
            if found_rate:
                break

            headers = table.find_all('th')
            country_idx = None
            duty_rate_idx = None

            # 找到Country和Duty rate列的索引
            for i, th in enumerate(headers):
                header_text = th.text.strip()
                if "Country" in header_text:
                    country_idx = i
                elif "Duty rate" in header_text:
                    duty_rate_idx = i

            if country_idx is not None and duty_rate_idx is not None:
                # 遍历表格行查找All countries
                rows = table.find_all('tr')
                for row in rows:
                    cells = row.find_all('td')
                    if cells and len(cells) > max(country_idx, duty_rate_idx):
                        country = cells[country_idx].text.strip()
                        if "All countries" in country:
                            duty_rate = cells[duty_rate_idx].text.strip()
                            result['rate'] = duty_rate
                            logger.debug(f"找到税率: {duty_rate}")
                            found_rate = True  # 找到第一个就退出
                            break

        if 'rate' not in result:
            logger.warning(f"未找到税率 for code: {result.get('code')}")
            result['rate'] = ''

        return result

    async def initialize(self) -> bool:
        """初始化抓取器，返回是否成功"""
        try:
            logger.info("开始初始化抓取器...")
            tariffs = await self.scrape_tariffs()
            if tariffs:
                self.save_to_db(tariffs)
                logger.info("初始化完成")
                return True
            else:
                logger.error("初始化失败：未获取到数据")
                return False
        except Exception as e:
            logger.error(f"初始化失败：{str(e)}")
            return False

    async def scrape_tariffs(self) -> List[Dict]:
        """抓取关税数据"""
        all_tariffs = []
        try:
            # 1. 获取section列表
            logger.info(f"开始抓取主页面: {self.browse_url}")
            content = await self.scrape_with_retry([self.browse_url])
            if not content or not content[0]:
                logger.error("无法访问主页面")
                return []

            section_urls = self.parse_section_links(content[0])
            if not section_urls:
                logger.error("未找到任何section链接")
                return []

            # 2. 获取chapter列表
            test_section_urls = section_urls[:2]  # 测试前2个section
            logger.info(f"开始抓取section: {test_section_urls}")
            section_contents = await self.scrape_with_retry(test_section_urls)

            chapter_urls = []
            for content in section_contents:
                if content:
                    urls = self.parse_chapter_links(content)
                    chapter_urls.extend(urls)

            # 3. 获取heading列表
            if chapter_urls:
                test_chapter_urls = chapter_urls[:3]  # 测试前3个chapter
                logger.info(f"开始抓取chapter: {test_chapter_urls}")
                chapter_contents = await self.scrape_with_retry(test_chapter_urls)

                heading_urls = []
                for content in chapter_contents:
                    if content:
                        urls = self.parse_heading_links(content)
                        heading_urls.extend(urls)

                # 4. 获取commodity列表
                if heading_urls:
                    test_heading_urls = heading_urls[:3]  # 测试前3个heading
                    logger.info(f"开始抓取heading: {test_heading_urls}")
                    heading_contents = await self.scrape_with_retry(test_heading_urls)

                    commodity_urls = []
                    for content in heading_contents:
                        if content:
                            urls = self.parse_commodity_links(content)
                            commodity_urls.extend(urls)

                    # 5. 获取commodity详情
                    if commodity_urls:
                        test_commodity_urls = commodity_urls[:5]  # 测试前5个commodity
                        logger.info(f"开始抓取commodity: {test_commodity_urls}")
                        commodity_contents = await self.scrape_with_retry(test_commodity_urls)

                        for i, content in enumerate(commodity_contents):
                            if content:
                                # 传入当前URL
                                tariff = self.parse_commodity_page(content, url=test_commodity_urls[i])
                                if tariff:
                                    all_tariffs.append(tariff)

            logger.info(f"共抓取 {len(all_tariffs)} 条记录")
            return all_tariffs

        except Exception as e:
            logger.error(f"抓取过程出错: {str(e)}")
            return []

    def save_to_db(self, tariffs: List[Dict]):
        """保存到数据库"""
        from tariff_db import TariffDB
        db = TariffDB()
        saved_count = 0
        for tariff in tariffs:
            try:
                db.add_tariff(
                    code=tariff['code'],
                    description=tariff['description'],
                    rate=tariff['rate'],
                    url=tariff.get('url')
                )
                saved_count += 1
            except Exception as e:
                logger.error(f"保存记录失败: {str(e)}")
                continue
        logger.info(f"成功保存 {saved_count} 条记录")

async def main():
    scraper = TariffScraper()
    tariffs = await scraper.scrape_tariffs()
    scraper.save_to_db(tariffs)

if __name__ == "__main__":
    asyncio.run(main())