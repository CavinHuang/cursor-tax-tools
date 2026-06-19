#!/usr/bin/env python3
"""测试商品删除判定逻辑

复现并验证"删除不同步"问题的修复：
被 trade-tariff 移除的编码（如 9403208000）返回 HTTP 200 + 无 duty rate（而非 404），
旧逻辑只看 HTTP 404 导致这类编码残留；should_delete_code 应识别"200 但无有效 duty rate"。
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.core.scraper import should_delete_code


def test_both_clean_404_should_delete():
    """UK 和 NI 都干净 404（data None, error None）→ 删"""
    assert should_delete_code(None, None, None, None) is True


def test_both_no_duty_rate_should_delete():
    """UK 和 NI 都 200 但无 duty rate（如 9403208000 被移除）→ 删"""
    uk = {'code': '9403208000', 'rate': '', 'description': 'Other'}
    ni = {'code': '9403208000', 'rate': '', 'description': 'Other'}
    assert should_delete_code(uk, None, ni, None) is True


def test_has_duty_rate_should_not_delete():
    """有有效 duty rate → 保留"""
    uk = {'code': '0101210000', 'rate': '5%'}
    ni = {'code': '0101210000', 'rate': '5%'}
    assert should_delete_code(uk, None, ni, None) is False


def test_rate_zero_percent_is_valid():
    """rate='0%' 是有效税率（免税），不删"""
    uk = {'code': 'X', 'rate': '0%'}
    ni = {'code': 'X', 'rate': '0%'}
    assert should_delete_code(uk, None, ni, None) is False


def test_fetch_error_should_not_delete():
    """抓取错误（data None + error 非 None）→ 保守保留，避免误删有效商品"""
    assert should_delete_code(None, "超时", None, "超时") is False


def test_uk_valid_ni_404_should_not_delete():
    """UK 有效但 NI 404 → 保留（任一地有效即保留）"""
    uk = {'code': 'X', 'rate': '5%'}
    assert should_delete_code(uk, None, None, None) is False


def test_ni_not_provided_uk_no_rate_should_delete():
    """NI 未提供 + UK 无 duty rate → 删"""
    uk = {'code': 'X', 'rate': ''}
    assert should_delete_code(uk, None, None, "未提供北爱尔兰URL") is True


def test_ni_not_provided_uk_valid_should_not_delete():
    """NI 未提供 + UK 有效 → 保留"""
    uk = {'code': 'X', 'rate': '5%'}
    assert should_delete_code(uk, None, None, "未提供北爱尔兰URL") is False


def test_empty_dict_should_not_delete():
    """parse 异常返回空 dict {} → 保守保留（状态不确定）"""
    assert should_delete_code({}, None, {}, None) is False


def test_uk_404_ni_no_rate_should_delete():
    """UK 干净 404 + NI 200 无 rate → 都无效 → 删"""
    ni = {'code': 'X', 'rate': ''}
    assert should_delete_code(None, None, ni, None) is True
