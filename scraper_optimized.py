"""
优化版关税爬虫系统
- 智能并发控制
- 自适应重试机制
- 性能监控和指标收集
- 内存优化和流式处理
- 智能错误恢复
"""

import asyncio
import aiohttp
import logging
import time
import re
import threading
from typing import List, Dict, Optional, Tuple, AsyncIterator, Callable
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup
import backoff  # 需要安装: pip install backoff
from dataclasses import dataclass
from enum import Enum
import psutil  # 需要安装: pip install psutil
from contextlib import asynccontextmanager

from tariff_db_optimized import OptimizedTariffDB
from tools.web_scraper import scrape_urls

logger = logging.getLogger(__name__)

class ErrorType(Enum):
    """错误类型枚举"""
    NETWORK = "network"
    PARSING = "parsing"
    VALIDATION = "validation"
    RATE_LIMIT = "rate_limit"
    SERVER_ERROR = "server_error"

@dataclass
class PerformanceMetrics:
    """性能指标数据类"""
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    retry_count: int = 0
    avg_response_time: float = 0.0
    current_memory_mb: float = 0.0
    concurrent_requests: int = 0
    requests_per_second: float = 0.0

class AdaptiveSemaphore:
    """自适应信号量 - 根据成功率动态调整并发数"""

    def __init__(self, initial_max: int = 20, min_max: int = 5, max_max: int = 50):
        self.min_max = min_max
        self.max_max = max_max
        self.current_max = initial_max
        self.semaphore = asyncio.Semaphore(initial_max)
        self.success_count = 0
        self.total_count = 0
        self.adjustment_interval = 50  # 每50次请求调整一次
        self.request_history = []
        self._lock = asyncio.Lock()

    async def acquire(self):
        """获取信号量"""
        await self.semaphore.acquire()

    def release(self):
        """释放信号量"""
        self.semaphore.release()

    async def record_success(self):
        """记录成功请求"""
        async with self._lock:
            self.success_count += 1
            self.total_count += 1
            await self._adjust_if_needed()

    async def record_failure(self):
        """记录失败请求"""
        async with self._lock:
            self.total_count += 1
            await self._adjust_if_needed()

    async def _adjust_if_needed(self):
        """如果需要，调整并发数"""
        if self.total_count % self.adjustment_interval == 0:
            success_rate = self.success_count / self.total_count

            old_max = self.current_max

            # 根据成功率调整
            if success_rate > 0.95:  # 成功率很高，增加并发
                self.current_max = min(self.current_max + 5, self.max_max)
            elif success_rate < 0.8:  # 成功率较低，减少并发
                self.current_max = max(self.current_max - 5, self.min_max)

            # 如果并发数发生变化，重新创建信号量
            if self.current_max != old_max:
                used = self.semaphore._value
                self.semaphore = asyncio.Semaphore(self.current_max)
                logger.info(f"🔄 调整并发数: {old_max} → {self.current_max} (成功率: {success_rate:.2f})")

class SmartRetryManager:
    """智能重试管理器"""

    def __init__(self, max_retries: int = 3):
        self.max_retries = max_retries
        self.retry_stats = {}

    @backoff.on_exception(
        backoff.expo,
        (aiohttp.ClientError, asyncio.TimeoutError),
        max_tries=3,
        base=1,
        max_value=30
    )
    async def execute_with_retry(self, func, *args, **kwargs):
        """执行函数并在失败时重试"""
        try:
            return await func(*args, **kwargs)
        except Exception as e:
            error_type = self._classify_error(e)
            if error_type == ErrorType.RATE_LIMIT:
                # 速率限制时增加等待时间
                await asyncio.sleep(backoff.expo(1) * 2)
            raise

    def _classify_error(self, error: Exception) -> ErrorType:
        """分类错误类型"""
        if isinstance(error, aiohttp.ClientError):
            return ErrorType.NETWORK
        elif isinstance(error, asyncio.TimeoutError):
            return ErrorType.NETWORK
        elif "rate limit" in str(error).lower():
            return ErrorType.RATE_LIMIT
        elif "500" in str(error) or "502" in str(error) or "503" in str(error):
            return ErrorType.SERVER_ERROR
        else:
            return ErrorType.PARSING

class OptimizedTariffScraper:
    """优化版关税爬虫"""

    def __init__(self, db: OptimizedTariffDB = None):
        self.db = db or OptimizedTariffDB()
        self.base_url = "https://www.trade-tariff.service.gov.uk"
        self.browse_url = f"{self.base_url}/browse"

        # 优化配置
        self.timeout = aiohttp.ClientTimeout(total=60, connect=20)
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-GB,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
            'Cache-Control': 'max-age=0'
        }

        # 自适应并发控制
        self.adaptive_semaphore = AdaptiveSemaphore(initial_max=20, min_max=5, max_max=50)
        self.retry_manager = SmartRetryManager()

        # 性能监控
        self.metrics = PerformanceMetrics()
        self.start_time = time.time()

        # 内存监控
        self.memory_threshold_mb = 500  # 内存使用阈值

    @asynccontextmanager
    async def get_session(self):
        """获取HTTP会话上下文管理器"""
        connector = aiohttp.TCPConnector(
            limit=50,
            limit_per_host=20,
            ttl_dns_cache=300,
            use_dns_cache=True,
            keepalive_timeout=30,
            enable_cleanup_closed=True
        )

        async with aiohttp.ClientSession(
            headers=self.headers,
            timeout=self.timeout,
            connector=connector
        ) as session:
            yield session

    async def check_memory_usage(self):
        """检查内存使用情况"""
        process = psutil.Process()
        memory_info = process.memory_info()
        memory_mb = memory_info.rss / 1024 / 1024

        self.metrics.current_memory_mb = memory_mb

        if memory_mb > self.memory_threshold_mb:
            logger.warning(f"WARNING: 内存使用过高: {memory_mb:.1f}MB > {self.memory_threshold_mb}MB")
            # 可以在这里实现内存清理策略
            import gc
            gc.collect()

        return memory_mb

    async def scrape_with_metrics(self, url: str, session: aiohttp.ClientSession) -> Tuple[int, Optional[str]]:
        """带性能指标的网页抓取"""
        start_time = time.time()

        async with self.adaptive_semaphore:
            try:
                async with session.get(url) as response:
                    content = await response.text()
                    status_code = response.status

                    # 记录请求指标
                    response_time = time.time() - start_time
                    self._update_metrics(status_code == 200, response_time)

                    await self.check_memory_usage()

                    if status_code == 200:
                        await self.adaptive_semaphore.record_success()
                        return status_code, content
                    else:
                        await self.adaptive_semaphore.record_failure()
                        return status_code, None

            except Exception as e:
                await self.adaptive_semaphore.record_failure()
                logger.error(f"抓取失败 {url}: {str(e)}")
                return 0, None

    def _update_metrics(self, success: bool, response_time: float):
        """更新性能指标"""
        self.metrics.total_requests += 1

        if success:
            self.metrics.successful_requests += 1
        else:
            self.metrics.failed_requests += 1

        # 更新平均响应时间
        total_time = self.metrics.avg_response_time * (self.metrics.total_requests - 1) + response_time
        self.metrics.avg_response_time = total_time / self.metrics.total_requests

        # 更新请求速率
        elapsed_time = time.time() - self.start_time
        if elapsed_time > 0:
            self.metrics.requests_per_second = self.metrics.total_requests / elapsed_time

    async def parse_tariff_data_optimized(self, html_content: str, url: str) -> Dict:
        """优化版关税数据解析"""
        try:
            soup = BeautifulSoup(html_content, 'html.parser')

            # 使用更精确的CSS选择器
            code_element = soup.select_one('h1.heading-xlarge')
            if not code_element:
                raise ValueError("无法找到商品编码")

            code = code_element.get_text(strip=True)

            # 优化描述提取
            desc_element = soup.select_one('p.lede')
            description = desc_element.get_text(strip=True) if desc_element else ""

            # 优化税率提取 - 支持多种税率格式
            rate = ""
            rate_patterns = [
                r'(\d+\.?\d*)\s*%.*?third country',
                r'Third country.*?(\d+\.?\d*)\s*%',
                r'Import duty.*?(\d+\.?\d*)\s*%'
            ]

            for pattern in rate_patterns:
                match = re.search(pattern, html_content, re.IGNORECASE)
                if match:
                    rate = f"{match.group(1)}%"
                    break

            return {
                'code': code,
                'description': description,
                'rate': rate,
                'url': url,
                'success': True
            }

        except Exception as e:
            logger.error(f"解析失败 {url}: {str(e)}")
            return {
                'code': '',
                'description': '',
                'rate': '',
                'url': url,
                'success': False,
                'error': str(e)
            }

    async def auto_update_single_optimized(self, code: str, uk_url: str, ni_url: str = None) -> Dict:
        """优化版单个商品自动更新"""
        try:
            # 获取现有数据
            old_data = self.db.get_tariff(code)

            urls = [uk_url]
            if ni_url:
                urls.append(ni_url)

            # 并发抓取
            async with self.get_session() as session:
                tasks = [self.scrape_with_metrics(url, session) for url in urls]
                results = await asyncio.gather(*tasks, return_exceptions=True)

            # 解析结果
            uk_data = {'success': False}
            ni_data = {'success': False}

            # 处理英国数据
            if isinstance(results[0], tuple) and results[0][0] == 200:
                uk_data = await self.parse_tariff_data_optimized(results[0][1], uk_url)

            # 处理北爱尔兰数据
            if ni_url and len(results) > 1 and isinstance(results[1], tuple) and results[1][0] == 200:
                ni_content = results[1][1]
                # 北爱尔兰页面解析可能略有不同
                ni_parsed = await self.parse_tariff_data_optimized(ni_content, ni_url)
                if ni_parsed['success']:
                    ni_data = ni_parsed

            # 智能对比和更新
            return await self._smart_update(code, old_data, uk_data, ni_data)

        except Exception as e:
            logger.error(f"优化更新失败 {code}: {str(e)}")
            await self._record_error(code, str(e), ErrorType.NETWORK)
            return self._create_error_result(str(e))

    async def _smart_update(self, code: str, old_data: Dict, uk_data: Dict, ni_data: Dict) -> Dict:
        """智能更新逻辑"""
        try:
            updated_data = old_data.copy() if old_data else {}
            any_updated = False
            uk_updated = False
            ni_updated = False

            # 英国数据更新
            if uk_data.get('success'):
                uk_rate = uk_data.get('rate', '')
                if old_data and old_data.get('rate', '').strip().lower() != uk_rate.strip().lower():
                    updated_data['rate'] = uk_rate
                    updated_data['description'] = uk_data.get('description', '')
                    updated_data['url'] = uk_data.get('url')
                    uk_updated = True
                    any_updated = True
                    logger.info(f"✅ 英国税率更新 {code}: {uk_rate}")
                elif not old_data:
                    # 新记录
                    updated_data.update({
                        'code': code,
                        'description': uk_data.get('description', ''),
                        'rate': uk_rate,
                        'url': uk_data.get('url')
                    })
                    uk_updated = True
                    any_updated = True

            # 北爱尔兰数据更新
            if ni_data.get('success'):
                ni_rate = ni_data.get('rate', '')
                if old_data and old_data.get('north_ireland_rate', '').strip().lower() != ni_rate.strip().lower():
                    updated_data['north_ireland_rate'] = ni_rate
                    updated_data['north_ireland_url'] = ni_data.get('url')
                    ni_updated = True
                    any_updated = True
                    logger.info(f"✅ 北爱尔兰税率更新 {code}: {ni_rate}")
                elif not old_data:
                    # 新记录
                    updated_data['north_ireland_rate'] = ni_rate
                    updated_data['north_ireland_url'] = ni_data.get('url')
                    ni_updated = True
                    any_updated = True

            # 保存到数据库
            if any_updated:
                update_type = 'both' if (uk_updated and ni_updated) else ('uk' if uk_updated else 'ni')
                await self._save_with_history(updated_data, update_type)

            return {
                'overall_success': uk_data.get('success', False) or ni_data.get('success', False),
                'uk_success': uk_data.get('success', False),
                'ni_success': ni_data.get('success', False),
                'uk_updated': uk_updated,
                'ni_updated': ni_updated,
                'message': self._generate_update_message(uk_data, ni_data, any_updated),
                'old_data': old_data,
                'new_data': updated_data,
                'updated': any_updated,
                'metrics': self._get_current_metrics()
            }

        except Exception as e:
            logger.error(f"智能更新失败 {code}: {str(e)}")
            return self._create_error_result(str(e))

    async def _save_with_history(self, data: Dict, update_type: str):
        """保存数据并记录历史"""
        try:
            self.db.add_tariff_with_history(
                code=data['code'],
                description=data.get('description', ''),
                rate=data.get('rate', ''),
                url=data.get('url'),
                other_rate=data.get('other_rate'),
                north_ireland_rate=data.get('north_ireland_rate'),
                north_ireland_url=data.get('north_ireland_url'),
                update_type=update_type
            )
        except Exception as e:
            logger.error(f"保存数据失败: {str(e)}")
            raise

    async def _record_error(self, code: str, error_message: str, error_type: ErrorType):
        """记录错误信息"""
        try:
            # 这里可以扩展为更详细的错误记录
            logger.error(f"记录错误 {code} ({error_type.value}): {error_message}")
        except Exception as e:
            logger.error(f"记录错误失败: {str(e)}")

    def _create_error_result(self, error_message: str) -> Dict:
        """创建错误结果"""
        return {
            'overall_success': False,
            'uk_success': False,
            'ni_success': False,
            'uk_updated': False,
            'ni_updated': False,
            'message': f'更新失败: {error_message}',
            'old_data': None,
            'new_data': None,
            'updated': False,
            'metrics': self._get_current_metrics()
        }

    def _generate_update_message(self, uk_data: Dict, ni_data: Dict, any_updated: bool) -> str:
        """生成更新消息"""
        messages = []

        if uk_data.get('success'):
            messages.append("英国成功")
        else:
            messages.append("英国失败")

        if ni_data.get('success'):
            messages.append("北爱尔兰成功")
        else:
            messages.append("北爱尔兰失败")

        status = "数据已更新" if any_updated else "数据无变化"
        return f"{status} | {' | '.join(messages)}"

    def _get_current_metrics(self) -> Dict:
        """获取当前性能指标"""
        return {
            'total_requests': self.metrics.total_requests,
            'success_rate': self.metrics.successful_requests / max(self.metrics.total_requests, 1),
            'avg_response_time': self.metrics.avg_response_time,
            'requests_per_second': self.metrics.requests_per_second,
            'current_memory_mb': self.metrics.current_memory_mb,
            'concurrent_limit': self.adaptive_semaphore.current_max
        }

class OptimizedBatchUpdateManager:
    """优化版批量更新管理器"""

    def __init__(self, db: OptimizedTariffDB = None,
                 progress_callback: Callable = None,
                 status_callback: Callable = None):
        self.scraper = OptimizedTariffScraper(db)
        self.db = db or OptimizedTariffDB()
        self.progress_callback = progress_callback
        self.status_callback = status_callback

        # 控制状态
        self.is_paused = False
        self.is_cancelled = False
        self.is_running = False

        # 性能统计
        self.stats = {
            'total': 0,
            'completed': 0,
            'successful': 0,
            'failed': 0,
            'skipped': 0,
            'uk_updated': 0,
            'ni_updated': 0,
            'start_time': None,
            'errors': [],
            'performance_metrics': {}
        }

    async def update_all_tariffs_optimized(self,
                                         update_uk: bool = True,
                                         update_ni: bool = True,
                                         batch_size: int = 100,
                                         delay_between_batches: float = 0.2,
                                         filter_func: Callable = None) -> Dict:
        """优化版批量更新所有关税数据"""
        try:
            self.is_running = True
            self.stats['start_time'] = time.time()

            await self._notify_status("INFO: 开始优化版批量更新...")

            # 获取所有关税数据
            all_tariffs = self.db.get_all_tariffs()
            self.stats['total'] = len(all_tariffs)

            if filter_func:
                all_tariffs = [t for t in all_tariffs if filter_func(t)]
                self.stats['total'] = len(all_tariffs)

            await self._notify_status(f"INFO: 准备更新 {self.stats['total']} 条关税记录")

            # 分批处理
            await self._process_batches(all_tariffs, batch_size, delay_between_batches, update_uk, update_ni)

            # 完成统计
            await self._finalize_stats()

            return self.stats

        except Exception as e:
            logger.error(f"优化批量更新失败: {str(e)}")
            await self._notify_status(f"ERROR: 批量更新失败: {str(e)}")
            raise
        finally:
            self.is_running = False

    async def _process_batches(self, tariffs: List[Dict], batch_size: int, delay: float, update_uk: bool, update_ni: bool):
        """分批处理关税数据"""
        total_count = len(tariffs)
        start_time = time.time()

        for i in range(0, total_count, batch_size):
            if self.is_cancelled:
                break

            # 等待暂停恢复
            while self.is_paused and not self.is_cancelled:
                await asyncio.sleep(0.1)

            if self.is_cancelled:
                break

            batch = tariffs[i:i + batch_size]
            await self._process_single_batch(batch, update_uk, update_ni)

            # 计算进度和预估时间
            completed = min(i + batch_size, total_count)
            await self._update_progress_and_eta(completed, total_count, start_time)

            # 批次间延迟
            if i + batch_size < total_count and delay > 0:
                await self._notify_status(f"⏳ 批次间等待 {delay} 秒...")
                await asyncio.sleep(delay)

    async def _process_single_batch(self, batch: List[Dict], update_uk: bool, update_ni: bool):
        """处理单个批次"""
        tasks = []

        for tariff in batch:
            if self.is_cancelled:
                break

            uk_url = tariff.get('url', f"https://www.trade-tariff.service.gov.uk/commodities/{tariff['code']}")
            ni_url = tariff.get('north_ireland_url')

            if update_ni and tariff['code'] and not ni_url:
                ni_url = f"https://www.trade-tariff.service.gov.uk/xi/commodities//{tariff['code']}"

            task = self.scraper.auto_update_single_optimized(tariff['code'], uk_url, ni_url)
            tasks.append(task)

        # 并发执行批次任务
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # 统计结果
        await self._process_batch_results(results)

    async def _process_batch_results(self, results: List):
        """处理批次结果"""
        for result in results:
            self.stats['completed'] += 1

            if isinstance(result, Exception):
                self.stats['failed'] += 1
                self.stats['errors'].append(str(result))
                continue

            if result.get('overall_success', False):
                self.stats['successful'] += 1
                if result.get('uk_updated', False):
                    self.stats['uk_updated'] += 1
                if result.get('ni_updated', False):
                    self.stats['ni_updated'] += 1
            else:
                self.stats['failed'] += 1
                self.stats['errors'].append(result.get('message', 'Unknown error'))

    async def _update_progress_and_eta(self, completed: int, total: int, start_time: float):
        """更新进度和预估时间"""
        self._update_progress(completed, total, f"已处理: {completed}/{total}")

        if completed > 0:
            elapsed_time = time.time() - start_time
            rate = completed / elapsed_time if elapsed_time > 0 else 0

            if rate > 0:
                remaining = total - completed
                eta_seconds = remaining / rate
                eta_minutes = eta_seconds / 60

                progress_msg = f"处理速度: {rate:.1f}条/分钟, 预计剩余: {eta_minutes:.0f}分钟"
            else:
                progress_msg = "正在计算处理速度..."

            self._update_progress(completed, total, progress_msg)

    async def _finalize_stats(self):
        """完成统计"""
        total_time = time.time() - self.stats['start_time']
        total_minutes = total_time / 60

        await self._notify_status(f"✅ 优化版批量更新完成！总用时: {total_minutes:.1f}分钟")

        # 获取最终性能指标
        final_metrics = self.scraper._get_current_metrics()
        self.stats['performance_metrics'] = final_metrics

        final_message = (f"更新完成 - 成功: {self.stats['successful']}, "
                        f"失败: {self.stats['failed']}, "
                        f"UK更新: {self.stats['uk_updated']}, "
                        f"NI更新: {self.stats['ni_updated']}")

        self._update_progress(self.stats['total'], self.stats['total'], final_message)

    def pause(self):
        """暂停更新"""
        self.is_paused = True
        asyncio.create_task(self._notify_status("INFO: 批量更新已暂停"))

    def resume(self):
        """恢复更新"""
        self.is_paused = False
        asyncio.create_task(self._notify_status("INFO: 批量更新已恢复"))

    def cancel(self):
        """取消更新"""
        self.is_cancelled = True
        self.is_paused = False
        asyncio.create_task(self._notify_status("INFO: 正在取消批量更新..."))

    async def _notify_status(self, message: str):
        """通知状态"""
        logger.info(message)
        if self.status_callback:
            if asyncio.iscoroutinefunction(self.status_callback):
                await self.status_callback(message)
            else:
                self.status_callback(message)

    def _update_progress(self, completed: int, total: int, message: str):
        """更新进度"""
        if self.progress_callback:
            if asyncio.iscoroutinefunction(self.progress_callback):
                asyncio.create_task(self.progress_callback(completed, total, message))
            else:
                self.progress_callback(completed, total, message)