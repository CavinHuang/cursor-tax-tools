import logging
from typing import List, Dict, Union
from tariff_db import TariffDB
from Levenshtein import ratio

logger = logging.getLogger(__name__)

class TariffAPI:
    def __init__(self):
        self.db = TariffDB()

    def search_tariff(self, code: str, fuzzy: bool = False) -> Union[Dict, List[Dict]]:
        """查询关税信息

        Args:
            code: 商品编码
            fuzzy: 是否使用模糊匹配

        Returns:
            精确匹配时返回单个字典，模糊匹配时返回字典列表
        """
        try:
            if fuzzy:
                # 模糊查询
                results = self.db.get_all_tariffs()
                if not results:
                    return []

                # 计算相似度并排序
                scored_results = []
                for result in results:
                    # 先尝试精确匹配
                    if result['code'] == code:
                        result['similarity'] = 1.0
                        return [result]  # 找到精确匹配就直接返回

                    # 否则计算相似度
                    similarity = ratio(code, result['code'])
                    if similarity > 0.6:  # 相似度阈值
                        result['similarity'] = similarity
                        scored_results.append(result)

                # 按相似度降序排序
                scored_results.sort(key=lambda x: x['similarity'], reverse=True)
                return scored_results[:10]  # 返回前10个最相似的结果

            else:
                # 精确查询
                result = self.db.get_tariff(code)
                if result:
                    return result  # 精确匹配只返回单个结果
                return None

        except Exception as e:
            logger.error(f"查询失败: {str(e)}")
            raise

    def get_record_count(self) -> int:
        """获取数据库中的记录数"""
        try:
            return self.db.get_record_count()
        except Exception as e:
            logger.error(f"获取记录数失败: {str(e)}")
            raise