import logging
import re
from typing import List, Dict, Union, Optional
from tariff_db import TariffDB
from Levenshtein import ratio

logger = logging.getLogger(__name__)

class TariffAPI:
    def __init__(self):
        self.db = TariffDB()

    def _normalize_code(self, code: str) -> str:
        """标准化商品编码，只保留数字"""
        return ''.join(filter(str.isdigit, str(code)))

    def _calculate_similarity(self, code1: str, code2: str) -> float:
        """计算两个编码的相似度，考虑前缀匹配权重"""
        # 标准化编码，只保留数字
        norm_code1 = self._normalize_code(code1)
        norm_code2 = self._normalize_code(code2)

        # 如果任一编码为空，返回0相似度
        if not norm_code1 or not norm_code2:
            return 0.0

        # 计算最长公共前缀长度
        prefix_len = 0
        for c1, c2 in zip(norm_code1, norm_code2):
            if c1 != c2:
                break
            prefix_len += 1

        # 计算前缀匹配得分（0-1之间）
        max_len = max(len(norm_code1), len(norm_code2))
        prefix_score = prefix_len / max_len if max_len > 0 else 0

        # 计算整体编辑距离相似度
        edit_score = ratio(norm_code1, norm_code2)

        # 综合得分：前缀匹配权重0.7，编辑距离权重0.3
        final_score = prefix_score * 0.7 + edit_score * 0.3

        return final_score

    def exact_search(self, code: str) -> Optional[Dict]:
        """精确查询关税信息

        Args:
            code: 商品编码

        Returns:
            匹配的关税信息，未找到返回None
        """
        try:
            # 标准化输入编码
            norm_code = self._normalize_code(code)
            result = self.db.get_tariff(norm_code)
            if result:
                result['similarity'] = 1.0  # 精确匹配设置相似度为1
            return result
        except Exception as e:
            logger.error(f"精确查询失败: {str(e)}")
            return None

    def search_tariff(self, code: str, fuzzy: bool = False) -> Union[Dict, List[Dict]]:
        """查询关税信息

        Args:
            code: 商品编码
            fuzzy: 是否使用模糊匹配

        Returns:
            精确匹配时返回单个字典，模糊匹配时返回字典列表，模糊匹配结果包含similarity字段
        """
        try:
            if fuzzy:
                return self.fuzzy_search(code)
            else:
                return self.exact_search(code)
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

    def fuzzy_search(self, query: str, limit: int = 10) -> List[Dict]:
        """模糊搜索关税信息

        Args:
            query: 搜索关键词
            limit: 返回结果数量限制

        Returns:
            匹配的关税信息列表，按相似度排序，每个结果包含similarity字段
        """
        try:
            # 标准化查询编码
            norm_query = self._normalize_code(query)

            # 如果标准化后的查询为空，返回空列表
            if not norm_query:
                return []

            # 先尝试精确匹配
            exact_result = self.exact_search(norm_query)
            if exact_result:
                return [exact_result]

            # 获取所有记录
            all_tariffs = self.db.get_all_tariffs()

            # 计算每条记录的相似度
            scored_results = []
            for tariff in all_tariffs:
                # 计算相似度
                similarity = self._calculate_similarity(norm_query, tariff['code'])

                if similarity > 0.2:  # 降低相似度阈值，因为前缀匹配更严格
                    tariff['similarity'] = similarity  # 将相似度添加到结果中
                    scored_results.append((similarity, tariff))

            # 按相似度排序并限制返回数量
            scored_results.sort(reverse=True, key=lambda x: x[0])
            return [item[1] for item in scored_results[:limit]]

        except Exception as e:
            logger.error(f"模糊搜索失败: {str(e)}")
            return []

    def get_all_codes(self) -> List[str]:
        """获取所有商品编码"""
        try:
            tariffs = self.db.get_all_tariffs()
            return [t['code'] for t in tariffs]
        except Exception as e:
            logger.error(f"获取编码列表失败: {str(e)}")
            return []