# 数据变动 Changelog 生成 实现计划（cursor-tax-tools 端）

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** cursor-tax-tools 每次发布版本时，生成「本版本相对上版本」的完整数据变动明细（added/removed/modified，含商品描述），作为 `metadata.json` 的 `data_changes` 字段发布，供 liao-tools 客户端展示「每个版本的数据变化」。

**Architecture:** 新增 `generate_changelog.py`（sqlite3 对比新旧 `tariffs.db` 生成变动明细）→ 集成进 `generate_metadata.py`（`data_changes` 字段）→ CI workflow 发布前下载上版本 db 并传参 → 同时 commit 已写好的删除逻辑修复（`should_delete_code` + `scrape_with_retry`，确保废止编码被移除从而出现在 changelog）。

**Tech Stack:** Python 3.11、sqlite3、pytest、GitHub Actions（softprops/action-gh-release）

**两仓库契约（本 plan 产出，liao-tools Plan 2 消费）**：`metadata.json` 新增 `data_changes` 字段，结构见下方「契约」。

---

## 契约：`data_changes`（写入 metadata.json）

```json
{
  "data_changes": {
    "version": "data-123",
    "previous_version": "data-122",
    "summary": { "added": 5, "removed": 2, "modified": 10 },
    "changes": [
      { "code": "9403208000", "change_type": "removed", "description": "Other", "field": null, "old_value": "5%", "new_value": null },
      { "code": "0202200000", "change_type": "added", "description": "新商品", "field": null, "old_value": null, "new_value": "3%" },
      { "code": "0101210000", "change_type": "modified", "description": "活马", "field": "rate", "old_value": "5%", "new_value": "6%" }
    ]
  }
}
```

字段约定：
- `change_type`: `added` / `removed` / `modified`
- `added`: `field=null, old_value=null, new_value=新rate, description=新描述`
- `removed`: `field=null, old_value=旧rate, new_value=null, description=旧描述`
- `modified`: `field=变更字段(rate/north_ireland_rate/description/other_rate), old_value, new_value, description=新描述`
- 对比字段（与 liao-tools `diff_tariffs` 一致）：`rate` / `north_ireland_rate` / `description` / `other_rate`

---

## File Structure

- Create: `src/actions/generate_changelog.py` — 对比新旧 db 生成 data_changes（纯函数，sqlite3）
- Create: `tests/test_generate_changelog.py` — TDD 测试
- Modify: `src/actions/generate_metadata.py` — `generate_metadata` 增加 `old_db_path`/`previous_version` 参数，输出 `data_changes`
- Modify: `.github/workflows/scrape-tariff.yml` — 发布前下载上版本 db，`generate_metadata` 传 `--old-db`
- Commit（已写好，本 plan 提交）: `src/core/scraper.py`（删除逻辑修复）+ `tests/test_delete_logic.py`

---

## Task 1: 提交已写好的删除逻辑修复

**背景**：`should_delete_code`（识别"200 无 duty rate"的废止编码）+ `scrape_with_retry`（不伪装 404）已写好并通过 10 个测试，但未 commit。这是 changelog 能正确反映「删除」的前提（废止编码必须先从 db 移除，才会出现在 changelog 的 removed 里）。

**Files:** `src/core/scraper.py`、`tests/test_delete_logic.py`（均已改/建好）

- [ ] **Step 1: 确认测试通过**

Run: `cd <cursor-tax-tools 根> && python -m pytest tests/test_delete_logic.py -v`
Expected: 10 passed

- [ ] **Step 2: Commit**

```bash
git add src/core/scraper.py tests/test_delete_logic.py
git commit -m "fix(scraper): 删除判定识别"200 无 duty rate"的废止编码 + scrape_with_retry 不伪装 404"
```

---

## Task 2: `generate_changelog.py` 对比函数（TDD）

**Files:**
- Create: `src/actions/generate_changelog.py`
- Create: `tests/test_generate_changelog.py`

- [ ] **Step 1: 写失败测试** `tests/test_generate_changelog.py`:

```python
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
    # modified
    m = codes[('0101010000', 'modified')]
    assert m['field'] == 'rate' and m['old_value'] == '5%' and m['new_value'] == '6%'
    assert m['description'] == 'A'
    # removed（带旧 rate + 旧描述）
    r = codes[('0202020000', 'removed')]
    assert r['field'] is None and r['old_value'] == '0%' and r['new_value'] is None
    assert r['description'] == 'B'
    # added（带新 rate + 新描述）
    a = codes[('0303030000', 'added')]
    assert a['field'] is None and a['old_value'] is None and a['new_value'] == '0%'
    assert a['description'] == 'C'
    # summary
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
    _make_db(new, [('0101010000', 'AA', '6%', '4%', None)])  # description+rate+ni 都变
    result = generate_changelog(new, old)
    fields = sorted(c['field'] for c in result['changes'] if c['change_type'] == 'modified')
    assert fields == ['description', 'north_ireland_rate', 'rate']
```

- [ ] **Step 2: 跑测试确认失败**

Run: `python -m pytest tests/test_generate_changelog.py -v`
Expected: FAIL（`ModuleNotFoundError: No module named 'src.actions.generate_changelog'`）

- [ ] **Step 3: 实现** `src/actions/generate_changelog.py`:

```python
#!/usr/bin/env python3
"""生成两版本 tariffs.db 之间的数据变动明细（data_changes）。

供 liao-tools 客户端展示"每个版本的数据变化"。结果写入 metadata.json 的 data_changes 字段。
对比字段与客户端 diff_tariffs 保持一致：rate / north_ireland_rate / description / other_rate。
"""
import os
import sqlite3
from typing import Dict, Optional


# 对比字段：(db 列名,)
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
    """对比新旧 tariffs.db，生成 data_changes 结构。

    Args:
        new_db_path: 新版本 tariffs.db
        old_db_path: 上版本 tariffs.db（None 或文件不存在 → 全部记为 added）
        version: 新版本号
        previous_version: 上版本号

    Returns:
        dict: {version, previous_version, summary{added,removed,modified}, changes[]}
    """
    new_tariffs = _load_tariffs(new_db_path)

    if old_db_path and os.path.exists(old_db_path):
        old_tariffs = _load_tariffs(old_db_path)
    else:
        old_tariffs = {}

    changes = []

    # added：新有旧无
    for code, rec in new_tariffs.items():
        if code not in old_tariffs:
            changes.append({
                'code': code,
                'change_type': 'added',
                'description': rec.get('description') or '',
                'field': None,
                'old_value': None,
                'new_value': rec.get('rate') or '',
            })

    # removed：旧有新无（保留旧 rate 作为 old_value，旧描述便于用户识别删了什么）
    for code, rec in old_tariffs.items():
        if code not in new_tariffs:
            changes.append({
                'code': code,
                'change_type': 'removed',
                'description': rec.get('description') or '',
                'field': None,
                'old_value': rec.get('rate') or '',
                'new_value': None,
            })

    # modified：共有 code 的字段变化（每个变更字段一行）
    for code, new_rec in new_tariffs.items():
        old_rec = old_tariffs.get(code)
        if not old_rec:
            continue
        for field in _COMPARE_FIELDS:
            old_v = old_rec.get(field) or ''
            new_v = new_rec.get(field) or ''
            if old_v != new_v:
                changes.append({
                    'code': code,
                    'change_type': 'modified',
                    'description': new_rec.get('description') or '',
                    'field': field,
                    'old_value': old_v,
                    'new_value': new_v,
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
```

- [ ] **Step 4: 跑测试确认通过**

Run: `python -m pytest tests/test_generate_changelog.py -v`
Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add src/actions/generate_changelog.py tests/test_generate_changelog.py
git commit -m "feat(changelog): 新增两版本 db 数据变动对比（added/removed/modified）"
```

---

## Task 3: 集成 `data_changes` 到 `generate_metadata.py`

**Files:** Modify `src/actions/generate_metadata.py`

- [ ] **Step 1: 给 `generate_metadata` 增加参数并写入 `data_changes`**

修改 `generate_metadata` 函数签名（约第 191 行），增加 `old_db_path` 与 `previous_version` 参数：

```python
def generate_metadata(db_path: str = 'tariffs.db',
                     version: str = None,
                     results_path: str = 'update_results.json',
                     output_path: str = 'metadata.json',
                     task_file: str = None,
                     old_db_path: str = None,
                     previous_version: str = None) -> Dict:
```

在文件顶部 import 区增加：

```python
from src.actions.generate_changelog import generate_changelog
```

在 `generate_metadata` 内、构建 `metadata = {...}` 的 dict 中（`'download_urls'` 之后、闭合 `}` 之前），增加 `data_changes` 字段：

```python
        'data_changes': generate_changelog(db_path, old_db_path, version, previous_version),
```

（`generate_changelog` 内部已处理 old_db_path 不存在的情况，安全。）

- [ ] **Step 2: 给 CLI（`if __name__ == "__main__"`）增加参数**

在 `argparse` 区（约第 308 行）增加：

```python
    parser.add_argument('--old-db', type=str, help='上版本 tariffs.db（用于生成 data_changes）')
    parser.add_argument('--previous-version', type=str, help='上版本号')
```

在 `generate_metadata(...)` 调用（约第 320 行）传入：

```python
    metadata = generate_metadata(
        db_path=args.db_path,
        version=version,
        results_path=args.results_path,
        output_path=args.output_path,
        task_file=args.task_file,
        old_db_path=args.old_db,
        previous_version=args.previous_version,
    )
```

- [ ] **Step 3: 验证（手动生成一个 metadata 看 data_changes 字段）**

Run:
```bash
python -c "import sys; sys.argv=['x','tariffs.db','--old-db','tariffs.db','--version','data-test','--output','/tmp/test_meta.json']; exec(open('src/actions/generate_metadata.py').read())" 2>&1 | tail -3
python -c "import json; d=json.load(open('/tmp/test_meta.json')); print('data_changes keys:', list(d.get('data_changes',{}).keys())); print('summary:', d['data_changes']['summary'])"
```
Expected: `data_changes` 含 `version/previous_version/summary/changes` 四键，summary 全 0（新旧同一 db）

- [ ] **Step 4: Commit**

```bash
git add src/actions/generate_metadata.py
git commit -m "feat(metadata): generate_metadata 集成 data_changes 变动明细"
```

---

## Task 4: CI workflow 集成（下载上版本 db + 传参）

**Files:** Modify `.github/workflows/scrape-tariff.yml`

- [ ] **Step 1: 在「生成元数据」步骤前，新增「下载上版本数据库」步骤**

在 `name: 生成元数据`（约第 178 行）**之前**插入新步骤：

```yaml
    - name: 下载上版本数据库（用于 data_changes changelog）
      id: prev_db
      run: |
        PREV_URL="https://github.com/${{ github.repository }}/releases/download/latest-data/tariffs.db"
        if curl -s -f -L "$PREV_URL" > previous_tariffs.db 2>/dev/null && [ -s previous_tariffs.db ]; then
          echo "has_previous=true" >> $GITHUB_OUTPUT
          echo "INFO: 已下载上版本 db 用于 changelog 对比"
        else
          echo "has_previous=false" >> $GITHUB_OUTPUT
          echo "INFO: 无上版本 db（首次发布），本次全部记为 added"
        fi
```

- [ ] **Step 2: 修改「生成元数据」步骤，传入 old-db 与 previous-version**

找到原「生成元数据」步骤（约第 178 行），**保留**其 `id/env/if` 与原有 `total_changes` 输出（下游「检查发布条件」依赖 `steps.metadata.outputs.total_changes`），仅追加 old-db 参数：

```yaml
    - name: 生成元数据
      id: metadata
      if: steps.file_info.outputs.has_database_file == 'true'
      env:
        VERSION: data-${{ github.run_number }}
        GITHUB_REPOSITORY: CavinHuang/cursor-tax-tools
        HAS_PREVIOUS: ${{ steps.prev_db.outputs.has_previous }}
      run: |
        echo "INFO: 生成元数据..."
        OLD_DB_ARG=""
        PREV_VER_ARG=""
        if [ "$HAS_PREVIOUS" = "true" ]; then
          OLD_DB_ARG="--old-db previous_tariffs.db"
          # previous_version 从已下载的 current_metadata.json 读取
          PREV_VER=$(python -c "import json; print(json.load(open('current_metadata.json')).get('version',''))" 2>/dev/null || echo "")
          if [ -n "$PREV_VER" ]; then
            PREV_VER_ARG="--previous-version $PREV_VER"
          fi
        fi
        python scripts/actions/generate_metadata.py tariffs.db "$VERSION" update_results.json metadata.json $OLD_DB_ARG $PREV_VER_ARG

        if [ -f "metadata.json" ]; then
          TOTAL_CHANGES=$(python -c "import json; data=json.load(open('metadata.json')); print(data.get('changes_summary', {}).get('total_updates', 0))")
          echo "total_changes=$TOTAL_CHANGES" >> $GITHUB_OUTPUT
          echo "metadata_generated=true" >> $GITHUB_OUTPUT
          echo "INFO: data_changes: $(python -c "import json; print(json.load(open('metadata.json')).get('data_changes',{}).get('summary'))")"
        else
          echo "metadata_generated=false" >> $GITHUB_OUTPUT
        fi
```

> 说明：① `current_metadata.json` 在「检查现有数据」步骤（约第 65-89 行）已下载，含上版本 `version`，用作 `previous_version`。② **务必保留 `total_changes` 输出**——下游「检查发布条件」步骤（约第 213 行）用 `steps.metadata.outputs.total_changes` 判断是否达到发布阈值。

- [ ] **Step 3: 验证 workflow 语法**

Run: `python -c "import yaml; yaml.safe_load(open('.github/workflows/scrape-tariff.yml'))" && echo "YAML OK"`
Expected: `YAML OK`

- [ ] **Step 4: Commit**

```bash
git add .github/workflows/scrape-tariff.yml
git commit -m "ci: 发布前下载上版本 db 生成 data_changes changelog"
```

---

## 完成标准

- [ ] `tests/test_generate_changelog.py` 4 测试通过；`tests/test_delete_logic.py` 10 测试通过
- [ ] `generate_metadata.py --old-db` 能产出含 `data_changes` 的 metadata.json
- [ ] `scrape-tariff.yml` YAML 合法，含「下载上版本 db」步骤
- [ ] 4 个 commit（删除修复 / generate_changelog / metadata 集成 / CI 集成）

## 后续（liao-tools Plan 2，独立 plan）

客户端消费 `data_changes`：下载 metadata → 解析 `data_changes.changes` → 写入 `change_log`（映射 added/removed/modified 行）→ 前端「更新历史」展示（已支持三种类型 + 描述）。客户端 `diff_tariffs` 保留为回退（旧 metadata 无 data_changes 时）。
