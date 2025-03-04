import aiohttp
import asyncio
from typing import List, Dict, Optional
import logging

logger = logging.getLogger(__name__)

async def scrape_urls(
    urls: List[str],
    headers: Optional[Dict] = None,
    timeout: int = 30,
    max_concurrent: int = 3
) -> List[str]:
    """异步抓取多个URL的内容"""
    if not urls:
        return []

    # 创建信号量控制并发
    semaphore = asyncio.Semaphore(max_concurrent)

    async def fetch_url(session: aiohttp.ClientSession, url: str) -> str:
        """抓取单个URL的内容"""
        async with semaphore:
            try:
                async with session.get(url, timeout=timeout) as response:
                    if response.status == 200:
                        return await response.text()
                    else:
                        logger.warning(f"请求失败 {url}: HTTP {response.status}")
                        return ""
            except Exception as e:
                logger.error(f"抓取失败 {url}: {str(e)}")
                return ""

    try:
        async with aiohttp.ClientSession(headers=headers) as session:
            tasks = [
                fetch_url(session, url)
                for url in urls
            ]
            return await asyncio.gather(*tasks)
    except Exception as e:
        logger.error(f"创建会话失败: {str(e)}")
        return [""] * len(urls)