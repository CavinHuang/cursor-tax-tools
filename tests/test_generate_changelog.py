#!/usr/bin/env python3
"""测试 generate_changelog：两版本 tariffs.db 的数据变动对比。"""
import os
import sys
import sqlite3
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.actions.generate_changelog import generate_changelog


def _make_db(path, rows):
    """rows: list of (code, description, rate, north_ireland_rate, other_rate)"""
    conn = sqlite3.connect(path)
    conn.execute("""CREATE TABLE tariffs (
        code TEXT PRIMARY KEY, description TEXT, rate TEXT,
        north_ireland_rate TEXT, other_rate TEXT)""")
    conn.executemany(
        "INSERT INTO tariffs (code, description, rate, north_ireland_rate, other_rate) VALUES (?,?,?,?,?)",
        rows)
    conn.commit()
    conn.close()


def _tmp():
    fd, path = tempfile.mkstemp(suffix='.db')
    os.close(fd)
    return path


def test_added_removed_modified():
    old = _tmp(); new = _tmp()
    _make_db(old, [
        ('0101010000', 'A', '5%', '3%', None),   # rate 变 → modified
        ('0202020000', 'B', '0%', None, None),    # 新库无 → removed
    ])
    _make_db(new, [
        ('0101010000', 'A', '6%', '3%', None),    # rate 5%→6%
        ('0303030000', 'C', '0%', None, None),    # 旧库无 → added
    ])
    result = generate_changelog(new, old, version='data-2', previous_version='data-1')

    codes = {(c['code'], c['change_type']): c for c in result['changes']}
    m = codes[('0101010000', 'modified')]
    assert m['field'] == 'rate' and m['old_value'] == '5%' and m['new_value'] == '6%'
    assert m['description'] == 'A'
    r = codes[('0202020000', 'removed')]
    assert r['field'] is None and r['old_value'] == '0%' and r['new_value'] is None
    assert r['description'] == 'B'
    a = codes[('0303030000', 'added')]
    assert a['field'] is None and a['old_value'] is None and a['new_value'] == '0%'
    assert a['description'] == 'C'
    assert result['summary'] == {'added': 1, 'removed': 1, 'modified': 1}
    assert result['version'] == 'data-2' and result['previous_version'] == 'data-1'


def test_no_change():
    old = _tmp(); new = _tmp()
    _make_db(old, [('0101010000', 'A', '5%', None, None)])
    _make_db(new, [('0101010000', 'A', '5%', None, None)])
    result = generate_changelog(new, old)
    assert result['changes'] == []
    assert result['summary'] == {'added': 0, 'removed': 0, 'modified': 0}


def test_old_db_missing_all_added():
    new = _tmp()
    _make_db(new, [('0101010000', 'A', '5%', None, None)])
    result = generate_changelog(new, old_db_path=None)
    assert result['summary']['added'] == 1
    assert result['summary']['removed'] == 0


def test_modified_multiple_fields_one_row_per_field():
    old = _tmp(); new = _tmp()
    _make_db(old, [('0101010000', 'A', '5%', '3%', None)])
    _make_db(new, [('0101010000', 'AA', '6%', '4%', None)])
    result = generate_changelog(new, old)
    fields = sorted(c['field'] for c in result['changes'] if c['change_type'] == 'modified')
    assert fields == ['description', 'north_ireland_rate', 'rate']
