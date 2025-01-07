#!/usr/bin/env /workspace/tmp_windsurf/py310/bin/python3

import aiohttp
import asyncio
from typing import List, Optional, Dict
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def scrape_urls(urls: List[str], headers: Dict = None, max_concurrent: int = 3) -> List[Optional[str]]:
    """异步抓取多个URL的内容"""
    if headers is None:
        headers = {}

    async def fetch_url(session: aiohttp.ClientSession, url: str) -> Optional[str]:
        try:
            async with session.get(url, headers=headers) as response:
                if response.status == 200:
                    return await response.text()
                logger.error(f"抓取失败 {url}: 状态码 {response.status}")
                return None
        except Exception as e:
            logger.error(f"抓取失败 {url}: {str(e)}")
            return None

    semaphore = asyncio.Semaphore(max_concurrent)

    async def bounded_fetch(session: aiohttp.ClientSession, url: str) -> Optional[str]:
        async with semaphore:
            return await fetch_url(session, url)

    async with aiohttp.ClientSession() as session:
        tasks = [bounded_fetch(session, url) for url in urls]
        return await asyncio.gather(*tasks)

# 如果直接运行此文件，执行测试
if __name__ == "__main__":
    async def test():
        test_urls = [
            "https://www.trade-tariff.service.gov.uk/browse",
            "https://www.trade-tariff.service.gov.uk/chapters/85",
            "https://www.trade-tariff.service.gov.uk/chapters/84",
        ]
        results = await scrape_urls(test_urls)
        for url, content in zip(test_urls, results):
            if content:
                logger.info(f"成功抓取 {url}: {len(content)} 字节")
            else:
                logger.error(f"抓取失败 {url}")

    asyncio.run(test())