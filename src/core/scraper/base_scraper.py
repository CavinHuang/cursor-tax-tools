import asyncio
import logging
import re
from typing import Dict, List, Optional
from bs4 import BeautifulSoup
from ...utils.web_scraper import scrape_urls
from ..db.tariff_db import TariffDB

logger = logging.getLogger(__name__)

class BaseScraper:
    def __init__(self):
        self.base_url = "https://www.trade-tariff.service.gov.uk"
        self.browse_url = f"{self.base_url}/browse"
        self.visited_urls = set()
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

    def parse_commodity_page(self, html_content: str, url: str = '') -> Optional[Dict]:
        """解析商品页面"""
        try:
            if not html_content:
                logger.error("页面内容为空")
                return None

            soup = BeautifulSoup(html_content, 'html.parser')
            logger.debug(f"开始解析页面: {len(html_content)} 字节")

            # 获取商品描述
            description = self._parse_description(soup)
            logger.debug(f"找到商品描述: {description}")

            # 查找税率表格 #import_duties的兄弟 class govuk-table或者duty-rates
            import_duties = soup.find('h3', {'id': 'import_duties'})
            print(import_duties)
            if import_duties:
                duty_table = import_duties.find_next_sibling('table', {'class': ['govuk-table', 'duty-rates']})
            else:
                duty_table = soup.find('table', {'class': ['govuk-table', 'duty-rates']})
            if not duty_table:
                logger.error("未找到税率表格")
                return None

            # 查找"All countries"行的税率
            rate = self._parse_rate(soup)

            result = {
                'description': description,
                'rate': rate,
                'url': url  # 使用传入的URL
            }
            logger.debug(f"解析结果: {result}")
            return result

        except Exception as e:
            logger.error(f"解析页面失败: {str(e)}")
            logger.debug(f"页面内容: {html_content[:200]}...")  # 记录部分页面内容以便调试
            return None

    def _parse_description(self, soup):
        """解析商品描述"""
        # 尝试多种可能的选择器
        selectors = [
            'h1.commodity-description',
            'h1.govuk-heading-l',
            '.commodity-header h1',
            '#content h1'
        ]

        for selector in selectors:
            element = soup.select_one(selector)
            if element:
                return element.text.strip()

        logger.warning("未找到商品描述，使用默认描述")
        return "商品描述未找到"

    def _parse_rate(self, soup):
        """解析税率"""
        # 尝试查找包含 "All countries" 的行
        rows = soup.select('table tr')
        for row in rows:
            cells = row.select('td')
            if not cells:
                continue

            # 检查是否包含 "All countries"
            country_cell = cells[0].text.strip().lower()
            if "all countries" in country_cell:
                # 获取税率列
                if len(cells) > 1:
                    rate = cells[2].text.strip()
                    return rate if rate else ""

        logger.warning("未找到'All countries'的税率，使用默认税率")
        return ""

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

    async def get_all_commodity_codes(self) -> List[str]:
        """获取所有商品编码"""
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

            # 2. 分批处理section
            commodity_codes = []
            batch_size = 10  # 每批处理10个
            total_sections = len(section_urls)

            for i in range(0, total_sections, batch_size):
                if self.should_stop and self.should_stop():
                    break

                batch_urls = section_urls[i:i + batch_size]
                logger.info(f"正在处理第 {i//batch_size + 1} 批section，共 {len(batch_urls)} 个")

                section_contents = await self.scrape_with_retry(batch_urls)
                chapter_urls = []
                for content in section_contents:
                    if content:
                        urls = self.parse_chapter_links(content)
                        chapter_urls.extend(urls)

                # 3. 分批处理chapter
                for j in range(0, len(chapter_urls), batch_size):
                    chapter_batch = chapter_urls[j:j + batch_size]
                    logger.info(f"正在处理第 {j//batch_size + 1} 批chapter，共 {len(chapter_batch)} 个")

                    chapter_contents = await self.scrape_with_retry(chapter_batch)
                    heading_urls = []
                    for content in chapter_contents:
                        if content:
                            urls = self.parse_heading_links(content)
                            heading_urls.extend(urls)

                    # 4. 分批处理heading
                    for k in range(0, len(heading_urls), batch_size):
                        heading_batch = heading_urls[k:k + batch_size]
                        logger.info(f"正在处理第 {k//batch_size + 1} 批heading，共 {len(heading_batch)} 个")

                        heading_contents = await self.scrape_with_retry(heading_batch)
                        commodity_urls = []
                        for content in heading_contents:
                            if content:
                                urls = self.parse_commodity_links(content)
                                commodity_urls.extend(urls)

                        # 5. 从commodity URL中提取编码
                        for url in commodity_urls:
                            code_match = re.search(r'/commodities/(\d+)', url)
                            if code_match:
                                code = self.format_commodity_code(code_match.group(1))
                                if code not in commodity_codes:
                                    commodity_codes.append(code)
                                    if self.log_callback:
                                        self.log_callback(f"找到商品编码: {code}")

                # 更新进度
                progress = (i + batch_size) / total_sections
                if self.progress_callback:
                    self.progress_callback(progress, f"已找到 {len(commodity_codes)} 个编码")

            logger.info(f"共找到 {len(commodity_codes)} 个商品编码")
            return commodity_codes

        except Exception as e:
            logger.error(f"获取商品编码失败: {str(e)}")
            return []

    # ... 共用方法 ...