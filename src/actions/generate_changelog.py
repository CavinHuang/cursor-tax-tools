#!/usr/bin/env python3
"""生成两版本 tariffs.db 之间的数据变动明细（data_changes）。

供 liao-tools 客户端"更新前预览"。结果写入 metadata.json 的 data_changes 字段。
对比字段：rate / north_ireland_rate / description / other_rate。
"""
import os
import sqlite3
from typing import Dict, Optional


_COMPARE_FIELDS = ['rate', 'north_ireland_rate', 'description', 'other_rate']


def _load_tariffs(db_path: str) -> Dict[str, Dict]:
    """加载数据库全部 tariffs，以 code 为键。"""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            "SELECT code, description, rate, north_ireland_rate, other_rate FROM tariffs"
        ).fetchall()
    finally:
        conn.close()
    return {row['code']: dict(row) for row in rows}


def generate_changelog(new_db_path: str,
                       old_db_path: Optional[str] = None,
                       version: Optional[str] = None,
                       previous_version: Optional[str] = None) -> Dict:
    """对比新旧 tariffs.db，生成 data_changes 结构。"""
    new_tariffs = _load_tariffs(new_db_path)

    if old_db_path and os.path.exists(old_db_path):
        old_tariffs = _load_tariffs(old_db_path)
    else:
        old_tariffs = {}

    changes = []

    for code, rec in new_tariffs.items():
        if code not in old_tariffs:
            changes.append({
                'code': code, 'change_type': 'added',
                'description': rec.get('description') or '',
                'field': None, 'old_value': None,
                'new_value': rec.get('rate') or '',
            })

    for code, rec in old_tariffs.items():
        if code not in new_tariffs:
            changes.append({
                'code': code, 'change_type': 'removed',
                'description': rec.get('description') or '',
                'field': None, 'old_value': rec.get('rate') or '',
                'new_value': None,
            })

    for code, new_rec in new_tariffs.items():
        old_rec = old_tariffs.get(code)
        if not old_rec:
            continue
        for field in _COMPARE_FIELDS:
            old_v = old_rec.get(field) or ''
            new_v = new_rec.get(field) or ''
            if old_v != new_v:
                changes.append({
                    'code': code, 'change_type': 'modified',
                    'description': new_rec.get('description') or '',
                    'field': field, 'old_value': old_v, 'new_value': new_v,
                })

    summary = {
        'added': sum(1 for c in changes if c['change_type'] == 'added'),
        'removed': sum(1 for c in changes if c['change_type'] == 'removed'),
        'modified': sum(1 for c in changes if c['change_type'] == 'modified'),
    }

    return {
        'version': version,
        'previous_version': previous_version,
        'summary': summary,
        'changes': changes,
    }


if __name__ == '__main__':
    import argparse, json
    p = argparse.ArgumentParser(description="生成两版本 db 的数据变动 changelog")
    p.add_argument('new_db', help="新版本 tariffs.db")
    p.add_argument('--old-db', help="上版本 tariffs.db")
    p.add_argument('--version')
    p.add_argument('--previous-version')
    p.add_argument('--output', default='data_changes.json')
    args = p.parse_args()
    result = generate_changelog(args.new_db, args.old_db, args.version, args.previous_version)
    with open(args.output, 'w', encoding='utf-8') as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
    print(f"生成 {args.output}: {result['summary']}")
