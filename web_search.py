import tkinter as tk
from tkinter import ttk, messagebox
import webbrowser
import logging
import time
import requests
import sys
from typing import Dict, List, Optional, Tuple

# 配置日志
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

# 创建控制台处理器
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setLevel(logging.DEBUG)

# 设置日志格式
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
console_handler.setFormatter(formatter)

# 添加处理器到logger
logger.addHandler(console_handler)

class WebSearchAPI:
    """官网搜索API封装"""

    BASE_URL = "https://www.trade-tariff.service.gov.uk"

    def __init__(self):
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        self.timeout = 10
        self.max_retries = 3
        self.retry_delay = 1

    def get_suggestions(self, code: str) -> Tuple[bool, List[Dict] | str]:
        """获取搜索建议"""
        logger.debug(f"开始获取搜索建议: code={code}")

        for attempt in range(self.max_retries):
            try:
                # 构建请求URL和参数
                url = f"{self.BASE_URL}/search_suggestions.json"
                params = {
                    'q': code,
                    'term': code,
                    # 添加额外参数以匹配官网行为
                    'suggestion_type': 'search',
                    'format': 'json'
                }

                logger.debug(f"请求URL: {url}, 参数: {params}")

                response = requests.get(
                    url,
                    params=params,
                    headers=self.headers,
                    timeout=self.timeout
                )

                # 记录完整的请求URL
                logger.debug(f"完整请求URL: {response.url}")

                # 记录响应状态和头信息
                logger.debug(f"响应状态码: {response.status_code}")
                logger.debug(f"响应头: {dict(response.headers)}")

                response.raise_for_status()

                try:
                    data = response.json()
                    logger.debug(f"API响应内容: {data}")
                except ValueError as e:
                    logger.error(f"JSON解析失败: {str(e)}")
                    logger.debug(f"原始响应内容: {response.text}")
                    return False, "响应格式错误"

                if data:
                    # 检查不同的结果字段
                    results = data.get('results', [])
                    if not results and 'data' in data:
                        results = data['data']

                    if results:
                        logger.debug(f"找到 {len(results)} 个建议结果")
                        for result in results:
                            logger.debug(f"建议: {result}")
                        return True, results

                    logger.debug("API返回结果为空")
                    logger.debug(f"完整响应数据: {data}")
                    return False, "未找到搜索建议"

                logger.debug("API返回数据为空")
                return False, "API返回为空"

            except requests.exceptions.RequestException as e:
                logger.error(f"获取搜索建议失败 (尝试 {attempt + 1}/{self.max_retries}): {str(e)}")
                if attempt < self.max_retries - 1:
                    logger.debug(f"等待 {self.retry_delay} 秒后重试")
                    time.sleep(self.retry_delay)
                    continue
                return False, f"请求失败: {str(e)}"

    def get_url_by_type(self, item_type: str, item_id: str) -> str:
        """根据类型获取对应的URL

        Args:
            item_type: 项目类型 (Commodity/Heading/Subheading/Chemical)
            item_id: 项目ID

        Returns:
            完整的URL
        """
        type_map = {
            "Commodity": "commodities",
            "Heading": "headings",
            "Subheading": "subheadings",
            "Chemical": "chemicals"
        }

        path = type_map.get(item_type, "find_commodity")
        if path == "find_commodity":
            return f"{self.BASE_URL}/{path}?q={item_id}"
        return f"{self.BASE_URL}/{path}/{item_id}"

    def search(self, code: str) -> Tuple[bool, str, Optional[str]]:
        """搜索商品编码"""
        logger.debug(f"开始搜索商品编码: {code}")

        success, data = self.get_suggestions(code)
        if not success:
            default_url = f"{self.BASE_URL}/find_commodity?q={code}"
            logger.debug(f"获取建议失败，使用默认搜索URL: {default_url}")
            return False, default_url, data

        # 找到完全匹配的结果
        exact_match = next(
            (result for result in data if result['text'] == code),
            None
        )

        if exact_match:
            logger.debug(f"找到完全匹配: {exact_match}")
            url = self.get_url_by_type(
                exact_match['formatted_suggestion_type'],
                exact_match['id']
            )
            logger.debug(f"生成URL: {url}")
            return True, url, None

        # 没有完全匹配，使用搜索页面
        url = f"{self.BASE_URL}/find_commodity?q={code}"
        logger.debug(f"未找到完全匹配，使用搜索页面: {url}")
        return True, url, None

class WebSearchUI:
    """官网搜索UI组件"""

    def __init__(self, parent: ttk.Frame, status_var: tk.StringVar):
        self.parent = parent
        self.status_var = status_var
        self.api = WebSearchAPI()
        self.suggestion_results = {}
        self._setup_ui()

    def _setup_ui(self):
        """创建UI组件"""
        # 搜索框区域
        self.search_frame = ttk.LabelFrame(self.parent, text="官网搜索", padding="5")

        # 编码输入框
        self.code_var = tk.StringVar()
        self.code_entry = ttk.Entry(
            self.search_frame,
            textvariable=self.code_var,
            width=40
        )
        # 绑定输入变化事件
        self.code_var.trace_add("write", self._on_code_change)

        # 搜索按钮
        self.search_btn = ttk.Button(
            self.search_frame,
            text="在官网搜索",
            command=self._search
        )

        # 搜索建议列表框
        self.suggestion_frame = ttk.LabelFrame(self.parent, text="搜索建议", padding="5")
        self.suggestion_tree = ttk.Treeview(
            self.suggestion_frame,
            columns=("code", "type", "resource_id"),
            show="headings",
            height=10
        )

        # 设置列
        self.suggestion_tree.heading("code", text="编码")
        self.suggestion_tree.heading("type", text="类型")
        self.suggestion_tree.heading("resource_id", text="资源ID")

        # 调整列宽和对齐方式
        self.suggestion_tree.column("code", width=250, anchor="w")
        self.suggestion_tree.column("type", width=150, anchor="center")
        self.suggestion_tree.column("resource_id", width=100, anchor="center")

        # 设置样式
        style = ttk.Style()
        style.configure("Treeview", rowheight=25)
        style.configure("Treeview.Heading", font=('TkDefaultFont', 10, 'bold'))

        # 添加滚动条
        self.scrollbar = ttk.Scrollbar(
            self.suggestion_frame,
            orient="vertical",
            command=self.suggestion_tree.yview
        )
        self.suggestion_tree.configure(yscrollcommand=self.scrollbar.set)

        # 绑定选择事件
        self.suggestion_tree.bind('<<TreeviewSelect>>', self._on_suggestion_select)

        # 布局
        self.search_frame.pack(fill=tk.X, padx=5, pady=5)
        self.code_entry.pack(side=tk.LEFT, padx=5)
        self.search_btn.pack(side=tk.LEFT, padx=5)

        self.suggestion_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.suggestion_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=2, pady=2)
        self.scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

    def _on_code_change(self, *args):
        """处理输入变化"""
        code = self.code_var.get().strip()
        logger.debug(f"输入变化: {code}")

        if len(code) < 4:
            logger.debug("输入长度不足4个字符，清空建议列表")
            self._clear_suggestions()
            return

        if hasattr(self, '_suggestion_timer'):
            self.parent.after_cancel(self._suggestion_timer)
        logger.debug(f"设置防抖定时器: {code}")
        self._suggestion_timer = self.parent.after(300, self._fetch_suggestions, code)

    def _clear_suggestions(self):
        """清空建议列表"""
        for item in self.suggestion_tree.get_children():
            self.suggestion_tree.delete(item)
        self.suggestion_results.clear()

    def _fetch_suggestions(self, code):
        """获取搜索建议"""
        logger.debug(f"开始获取建议: {code}")
        success, data = self.api.get_suggestions(code)

        self._clear_suggestions()

        if not success:
            logger.debug(f"获取建议失败: {data}")
            self.suggestion_tree.insert("", "end", values=(f"获取搜索建议失败: {data}", "", ""))
            self.status_var.set("获取搜索建议失败")
            return

        logger.debug(f"成功获取建议，开始分组显示")
        self._display_suggestions(data)

    def _display_suggestions(self, data):
        """显示搜索建议"""
        groups = {
            "Commodity": [],
            "Heading": [],
            "Subheading": [],
            "Chemical": []
        }

        for result in data:
            suggestion_type = result['formatted_suggestion_type']
            if suggestion_type in groups:
                groups[suggestion_type].append(result)

        for suggestion_type, results in groups.items():
            if results:
                group_id = self.suggestion_tree.insert(
                    "",
                    "end",
                    values=(f"=== {suggestion_type} ===", "", ""),
                    tags=('group',)
                )

                for result in results:
                    item_id = self.suggestion_tree.insert(
                        "",
                        "end",
                        values=(
                            result['text'],
                            result['formatted_suggestion_type'],
                            result['resource_id']
                        )
                    )
                    self.suggestion_results[item_id] = result

        self.suggestion_tree.tag_configure('group', background='#f0f0f0', font=('TkDefaultFont', 10, 'bold'))

    def _on_suggestion_select(self, event):
        """处理建议选择"""
        selection = self.suggestion_tree.selection()
        if not selection:
            return

        item_id = selection[0]
        result = self.suggestion_results.get(item_id)
        if not result:
            return

        self.code_var.set(result['text'])
        url = self.api.get_url_by_type(result['formatted_suggestion_type'], result['id'])
        webbrowser.open(url)
        self.status_var.set(f"已在浏览器中打开: {url}")

    def _search(self):
        """执行搜索"""
        code = self.code_var.get().strip()
        if not code:
            messagebox.showwarning("警告", "请输入海关编码")
            return

        success, url, error = self.api.search(code)
        if not success:
            self.status_var.set("搜索建议获取失败，使用默认搜索页面")
            logger.error(f"搜索失败: {error}")

        webbrowser.open(url)
        self.status_var.set(f"已在浏览器中打开: {url}")