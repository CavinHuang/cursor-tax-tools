import unittest
import asyncio
from tariff_api import TariffAPI
from tariff_db import TariffDB
from scraper import TariffScraper
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class TestTariffSystem(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        """初始化测试数据"""
        cls.db = TariffDB(db_path="test_tariff.db")
        # 添加一些测试数据
        test_data = [
            ("8517.12.00", "手机", 0.0),
            ("8517.13.00", "智能手表", 2.5),
            ("8517.14.00", "其他通讯设备", 3.0),
            ("8471.30.00", "笔记本电脑", 1.5),
        ]
        for code, desc, rate in test_data:
            cls.db.add_tariff(code, desc, rate)
        cls.api = TariffAPI()

    def test_exact_search(self):
        """测试精确查询"""
        result = self.api.search_tariff("8517.12.00", fuzzy=False)
        self.assertIsNotNone(result)
        self.assertEqual(result['code'], "8517.12.00")
        self.assertEqual(result['description'], "手机")
        self.assertEqual(result['rate'], 0.0)

    def test_fuzzy_search(self):
        """测试模糊查询"""
        results = self.api.search_tariff("8517.12")
        self.assertTrue(len(results) > 0)
        # 检查相似度排序
        self.assertGreater(results[0]['similarity'], 0.5)

    def test_nonexistent_code(self):
        """测试不存在的编码"""
        result = self.api.search_tariff("9999.99.99", fuzzy=False)
        self.assertIsNone(result)

    def test_similar_codes(self):
        """测试相似编码的查询结果"""
        results = self.api.search_tariff("8517")
        codes = [r['code'] for r in results]
        self.assertTrue(all(c.startswith("8517") for c in codes))

class TestScraper(unittest.TestCase):
    def setUp(self):
        self.scraper = TariffScraper()

    def test_parse_chapter_links(self):
        """测试章节链接解析"""
        test_html = """
        <html>
            <body>
                <a href="/chapters/85">Chapter 85</a>
                <a href="/chapters/84">Chapter 84</a>
            </body>
        </html>
        """
        links = self.scraper.parse_chapter_links(test_html)
        self.assertEqual(len(links), 2)
        self.assertTrue(all(link.startswith("https://") for link in links))

if __name__ == '__main__':
    unittest.main()