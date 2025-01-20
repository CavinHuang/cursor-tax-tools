# This script updates the North Ireland data in the database

import asyncio
from typing import Dict, List, Set
from tariff_db import TariffDB
import logging
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
    self.max_retries = 5 # 最大重试次数
    self.db = TariffDB()
    self.existing_codes = self.db.get_existing_codes_north_ireland()  # 获取已存在的北爱尔兰编码
    logger.info(f"已存在 {len(self.existing_codes)} 条记录")

  async def scrape_with_retry(self, urls: List[str]) -> List[str]:
        """带重试的抓取"""
        logger.info(f"正在抓取 {len(urls)} 个北爱尔兰关税数据")
        logger.info(f"正在抓取 {self.timeout} 秒")
        for retry in range(self.max_retries):
            try:
                results = await scrape_urls(urls, headers=self.headers)
                if any(results):  # 只要有一个成功就返回
                    return results
            except Exception as e:
                logger.warning(f"第{retry + 1}次重试失败: {str(e)}")
                await asyncio.sleep(1)  # 失败后等待1秒再重试
        return [""] * len(urls)

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
            result['url'] = url or f"https://www.trade-tariff.service.gov.uk/xi/commodities/{code}"

        # 查找商品描述
        desc_elem = soup.find('h1', class_='commodity-description')
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
        duty_tables = soup.find_all('table', class_='govuk-table')
        for table in duty_tables:
            if found_rate:
                break

            headers = table.find_all('th')
            country_idx = None
            duty_rate_idx = None

            for i, th in enumerate(headers):
                header_text = th.text.strip()
                if "Country" in header_text:
                    country_idx = i
                elif "Duty rate" in header_text:
                    duty_rate_idx = i

            if country_idx is not None and duty_rate_idx is not None:
                rows = table.find_all('tr')
                for row in rows:
                    cells = row.find_all('td')
                    if cells and len(cells) > max(country_idx, duty_rate_idx):
                        country = cells[country_idx].text.strip()
                        if "All countries" in country:
                            duty_rate = cells[duty_rate_idx].text.strip()
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

  async def scrape_tariffs(self):
    """抓取现有的编码对应的北爱尔兰关税数据"""
    try:
      all_tariffs = self.db.get_all_tariffs()

      batch_size = 20
      for m in range(0, len(all_tariffs), batch_size):
        commodity_batch = all_tariffs[m:m + batch_size]
        logger.info(f"正在处理第 {m//batch_size + 1} 批关税，共 {len(commodity_batch)} 个")

        commodity_batch_urls = [tariff['north_ireland_url'] or f"{self.base_url}/{tariff['code']}" for tariff in commodity_batch]

        commodity_contents = await self.scrape_with_retry(commodity_batch_urls)
        batch_tariffs = []

        for n, content in enumerate(commodity_contents):
          if content:
            tariff = self.parse_commodity_page(content, url=commodity_batch_urls[n])
            if tariff:
              batch_tariffs.append(tariff)

        if batch_tariffs:
          self.update_tariffs(batch_tariffs)
          logger.info(f"已更新 {len(batch_tariffs)} 条记录")

      total_count = self.db.get_db_count()
      logger.info(f"抓取完成，数据库共有 {total_count} 条记录被更新")
      return []

    except Exception as e:
      logger.error(f"更新关税数据失败: {str(e)}")
      return []

  def update_tariffs(self, tariffs: List[Dict]):
    """更新关税数据"""
    updated_count = 0
    for tariff in tariffs:
      if not tariff or 'code' not in tariff:
        continue

      if tariff['code'] in self.existing_codes:
        continue

      self.db.update_north_ireland_tariff(
        code=tariff['code'],
        north_ireland_rate=tariff['rate'],
        north_ireland_url=tariff.get('url')
      )
      updated_count += 1

    logger.info(f"已更新 {updated_count} 条记录")

async def main():
  scraper = Scraper()
  await scraper.scrape_tariffs()

if __name__ == "__main__":
  asyncio.run(main())
