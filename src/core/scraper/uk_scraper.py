from .base_scraper import BaseScraper
from typing import List
import logging

logger = logging.getLogger(__name__)

class UKScraper(BaseScraper):
    def __init__(self):
        super().__init__()
        self.base_url = "https://www.trade-tariff.service.gov.uk/commodities/"

    async def update_tariffs(self, codes: List[str]) -> bool:
        """更新英国关税数据"""
        try:
            batch_size = 10 if len(codes) > 1 else 1  # 单个重试时不使用批处理
            total_batches = (len(codes) + batch_size - 1) // batch_size
            self.log(f"开始更新英国关税数据，共 {len(codes)} 个商品")

            for i in range(0, len(codes), batch_size):
                if self.check_should_stop():
                    self.log("收到停止信号，正在停止更新...")
                    return False

                batch = codes[i:i + batch_size]
                current_batch = i // batch_size + 1
                self.log(f"处理第 {current_batch}/{total_batches} 批")

                # 格式化编码
                formatted_batch = [self.format_commodity_code(code) for code in batch]
                urls = [f"{self.base_url}{code}" for code in formatted_batch]

                contents = await self.scrape_with_retry(urls)

                for code, content in zip(batch, contents):
                    if self.check_should_stop():
                        return False

                    try:
                        if content:
                            url = f"{self.base_url}{self.format_commodity_code(code)}"
                            tariff_data = self.parse_commodity_page(content, url)
                            if tariff_data:
                                self.db.update_uk_tariff(
                                    code,
                                    tariff_data['description'],
                                    tariff_data['rate'],
                                    tariff_data['url']
                                )
                                return True
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