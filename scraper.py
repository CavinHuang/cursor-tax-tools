import asyncio
from typing import List, Dict, Set
from tools.web_scraper import scrape_urls
from bs4 import BeautifulSoup
import re
import logging
from tariff_db import TariffDB

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

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
        self.db = TariffDB()
        self.existing_codes = self.db.get_existing_codes()  # 获取已存在的编码
        logger.info(f"已存在 {len(self.existing_codes)} 条记录")

    async def scrape_with_retry(self, urls: List[str]) -> List[str]:
        """带重试的抓取"""
        for retry in range(self.max_retries):
            try:
                results = await scrape_urls(urls, headers=self.headers)
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

        try:
            # 查找商品编码
            code_match = re.search(r'/commodities/(\d+)', str(soup))
            if code_match:
                code = code_match.group(1)
                # 如果编码已存在，直接返回空
                if code in self.existing_codes:
                    logger.debug(f"编码 {code} 已存在，跳过")
                    return {}

                result['code'] = code
                result['url'] = url or f"https://www.trade-tariff.service.gov.uk/commodities/{code}"

            # 查找商品描述（更新：使用正确的class名）
            desc_elem = soup.find('h1', class_='commodity-header')
            if desc_elem:
                result['description'] = desc_elem.text.strip()
                logger.debug(f"找到商品描述: {result['description']}")
            else:
                error_msg = f"未找到商品描述 for code: {result.get('code')}"
                logger.warning(error_msg)
                if result.get('code'):
                    self.db.add_scrape_error(result['code'], error_msg)
                result['description'] = ''

            # 查找税率
            found_rate = False
            duty_tables = soup.find_all('table', class_='small-table')
            for table in duty_tables:
                if found_rate:
                    break

                headers = table.find_all('th')
                duty_rate_idx = None

                # 查找"Duty rate"列的索引
                for i, th in enumerate(headers):
                    header_text = th.text.strip()
                    if "Duty rate" in header_text:
                        duty_rate_idx = i
                        break

                if duty_rate_idx is not None:
                    # 查找包含"All countries"或"United Kingdom"的行
                    rows = table.find_all('tr')
                    for row in rows:
                        cells = row.find_all(['td', 'th'])
                        if cells and len(cells) > duty_rate_idx:
                            country_cell = cells[0].get_text(strip=True)
                            if "All countries" in country_cell or "United Kingdom" in country_cell:
                                # 使用更精确的CSS选择器提取税率
                                duty_rate_elem = cells[duty_rate_idx].find('span', class_='duty-expression')
                                if duty_rate_elem:
                                    # 找到嵌套的span中的税率值
                                    rate_span = duty_rate_elem.find('span')
                                    duty_rate = rate_span.get_text(strip=True) if rate_span else duty_rate_elem.get_text(strip=True)
                                else:
                                    # 备用方法：直接获取文本
                                    duty_rate = cells[duty_rate_idx].get_text(strip=True)

                                result['rate'] = duty_rate
                                logger.debug(f"找到税率: {duty_rate}")
                                found_rate = True
                                break

            if 'rate' not in result and result.get('code'):
                error_msg = f"未找到税率 for code: {result.get('code')}"
                logger.warning(error_msg)
                self.db.add_scrape_error(result['code'], error_msg)
                result['rate'] = ''

            return result

        except Exception as e:
            error_msg = f"解析页面失败: {str(e)}"
            logger.error(error_msg)
            if result.get('code'):
                self.db.add_scrape_error(result['code'], error_msg)
            return {}

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
            batch_size = 10  # 每批处理5个section
            for i in range(0, len(section_urls), batch_size):
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

                        # 5. 分批处理commodity并直接保存
                        for m in range(0, len(commodity_urls), batch_size):
                            commodity_batch = commodity_urls[m:m + batch_size]
                            logger.info(f"正在处理第 {m//batch_size + 1} 批commodity，共 {len(commodity_batch)} 个")

                            commodity_contents = await self.scrape_with_retry(commodity_batch)
                            batch_tariffs = []

                            for n, content in enumerate(commodity_contents):
                                if content:
                                    tariff = self.parse_commodity_page(content, url=commodity_batch[n])
                                    if tariff:
                                        batch_tariffs.append(tariff)

                            # 直接保存这一批数据
                            if batch_tariffs:
                                self.save_to_db(batch_tariffs)
                                logger.info(f"已保存 {len(batch_tariffs)} 条commodity记录")

            total_count = self.get_db_count()
            logger.info(f"抓取完成，数据库共有 {total_count} 条记录")
            return []

        except Exception as e:
            logger.error(f"抓取过程出错: {str(e)}")
            return []

    def save_to_db(self, tariffs: List[Dict]):
        """保存到数据库"""
        saved_count = 0
        for tariff in tariffs:
            try:
                if not tariff or 'code' not in tariff:
                    continue

                if tariff['code'] in self.existing_codes:
                    continue

                self.db.add_tariff(
                    code=tariff['code'],
                    description=tariff['description'],
                    rate=tariff['rate'],
                    url=tariff.get('url')
                )
                self.existing_codes.add(tariff['code'])  # 更新已存在编码集合
                saved_count += 1

                # 如果保存成功，清除可能存在的错误记录
                self.db.clear_scrape_error(tariff['code'])

            except Exception as e:
                logger.error(f"保存记录失败: {str(e)}")
                if tariff.get('code'):
                    self.db.add_scrape_error(tariff['code'], f"保存失败: {str(e)}")
                continue
        logger.info(f"成功保存 {saved_count} 条记录")

    def get_db_count(self) -> int:
        """获取数据库中的记录总数"""
        from tariff_db import TariffDB
        db = TariffDB()
        return db.get_record_count()

    def auto_update_single(self, code: str, uk_url: str, ni_url: str = None) -> Dict:
        """自动更新单个商品的税率信息（支持英国和北爱尔兰）

        Args:
            code: 商品编码
            uk_url: 英国税率URL
            ni_url: 北爱尔兰税率URL（可选）

        Returns:
            包含更新结果的字典：{
                'success': bool,
                'message': str,
                'updated': bool,
                'old_data': dict,
                'new_data': dict
            }
        """
        try:
            # 获取当前数据
            old_data = self.db.get_tariff(code)
            if not old_data:
                return {
                    'success': False,
                    'message': f'未找到商品编码 {code} 的记录',
                    'updated': False,
                    'old_data': None,
                    'new_data': None
                }

            # 抓取新数据
            # 临时保存现有的编码列表
            saved_existing_codes = self.existing_codes.copy()
            # 清空 existing_codes 以允许解析已存在的记录（用于自动更新）
            self.existing_codes = set()
            
            async def fetch_uk_data():
                """抓取并解析英国数据"""
                content_list = await self.scrape_with_retry([uk_url])
                content = content_list[0] if content_list else ""
                if not content:
                    return None
                return self.parse_commodity_page(content, uk_url)
            
            async def fetch_ni_data():
                """抓取并解析北爱尔兰数据"""
                if not ni_url:
                    return None
                content_list = await self.scrape_with_retry([ni_url])
                content = content_list[0] if content_list else ""
                if not content:
                    return None
                return self.parse_commodity_page(content, ni_url)

            # 使用asyncio.run执行异步操作
            uk_data_parsed = asyncio.run(fetch_uk_data())
            ni_data_parsed = asyncio.run(fetch_ni_data())
            
            # 恢复原有的 existing_codes
            self.existing_codes = saved_existing_codes

            if not uk_data_parsed:
                return {
                    'success': False,
                    'message': '解析英国网页失败，无法获取税率信息',
                    'updated': False,
                    'old_data': old_data,
                    'new_data': None
                }

            # 提取要更新的数据
            new_uk_rate = uk_data_parsed.get('rate', '')
            new_description = uk_data_parsed.get('description', '')
            new_ni_rate = ni_data_parsed.get('rate', '') if ni_data_parsed else ''

            # 对比税率是否变化（忽略大小写和空格）
            old_uk_rate = old_data.get('rate', '') or ''
            new_uk_rate_clean = new_uk_rate.strip().lower() if new_uk_rate else ''
            old_uk_rate_clean = old_uk_rate.strip().lower() if old_uk_rate else ''
            
            old_ni_rate = old_data.get('north_ireland_rate', '') or ''
            new_ni_rate_clean = new_ni_rate.strip().lower() if new_ni_rate else ''
            old_ni_rate_clean = old_ni_rate.strip().lower() if old_ni_rate else ''

            # 检查是否有变化
            uk_rate_changed = new_uk_rate_clean != old_uk_rate_clean
            ni_rate_changed = new_ni_rate_clean != old_ni_rate_clean
            desc_changed = new_description and new_description != old_data.get('description', '')

            if not uk_rate_changed and not ni_rate_changed and not desc_changed:
                return {
                    'success': True,
                    'message': '英国税率、北爱尔兰税率和描述均无变化，无需更新',
                    'updated': False,
                    'old_data': old_data,
                    'new_data': old_data
                }

            # 执行更新
            update_data = {}
            if uk_rate_changed:
                update_data['rate'] = new_uk_rate
            if ni_rate_changed:
                update_data['north_ireland_rate'] = new_ni_rate
            if desc_changed:
                update_data['description'] = new_description

            self.db.update_tariff(code=code, **update_data)

            # 获取更新后的数据
            updated_data = self.db.get_tariff(code)

            # 构建消息
            changed_parts = []
            if uk_rate_changed:
                changed_parts.append('英国税率')
            if ni_rate_changed:
                changed_parts.append('北爱尔兰税率')
            if desc_changed:
                changed_parts.append('描述')
            
            change_msg = '、'.join(changed_parts)
            return {
                'success': True,
                'message': f'成功更新数据（{change_msg}）',
                'updated': True,
                'old_data': old_data,
                'new_data': updated_data
            }

        except Exception as e:
            logger.error(f"自动更新失败: {str(e)}")
            return {
                'success': False,
                'message': f'自动更新失败: {str(e)}',
                'updated': False,
                'old_data': None,
                'new_data': None
            }

async def main():
    scraper = TariffScraper()
    tariffs = await scraper.scrape_tariffs()
    scraper.save_to_db(tariffs)

if __name__ == "__main__":
    asyncio.run(main())