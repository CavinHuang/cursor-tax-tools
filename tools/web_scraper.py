#!/usr/bin/env /workspace/tmp_windsurf/py310/bin/python3

import aiohttp
import asyncio
import ssl
from typing import List, Optional, Dict
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def scrape_urls(urls: List[str], headers: Dict = None, max_concurrent: int = 15, proxy: str = None) -> List[Optional[str]]:
    """异步抓取多个URL的内容

    Args:
        urls: 要抓取的URL列表
        headers: 请求头
        max_concurrent: 最大并发数
        proxy: 代理服务器地址，格式：http://host:port 或 socks5://host:port
    """
    if headers is None:
        headers = {}

    # 创建 SSL 上下文（放在外面，可以在 fetch_url 中使用）
    ssl_context = ssl.create_default_context()
    ssl_context.check_hostname = False
    ssl_context.verify_mode = ssl.CERT_NONE

    async def fetch_url(session: aiohttp.ClientSession, url: str) -> Optional[str]:
        try:
            # 在请求时也传递 ssl 参数（完全禁用 SSL 验证）
            async with session.get(url, headers=headers, proxy=proxy, ssl=False) as response:
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

    # 使用连接池优化性能
    connector = aiohttp.TCPConnector(
        limit=50,  # 总连接池大小
        limit_per_host=20,  # 每个主机的连接数
        ttl_dns_cache=300,  # DNS缓存5分钟
        use_dns_cache=True,
        ssl=ssl_context,  # 使用自定义 SSL 上下文
    )
    timeout = aiohttp.ClientTimeout(total=60, connect=20)  # 设置超时（增加以应对慢速连接）

    async with aiohttp.ClientSession(connector=connector, timeout=timeout, trust_env=True) as session:
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