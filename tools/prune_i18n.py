#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Prune i18nData.json keys based on i18nunused.txt.

Behavior:
- Read all keys from repo_root/i18nunused.txt (one key per line)
- Load backend/static/i18nData.json
- If top-level is languages (e.g., {'zh': {...}, 'en': {...}}), delete those keys from each language map
- If top-level is a flat dict, delete keys directly
- Write a timestamped backup: i18nData.json.bak
- Overwrite i18nData.json with pruned content

Usage:
  python tools/prune_i18n.py
"""

from __future__ import annotations
import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Set


REPO_ROOT = Path(__file__).resolve().parents[1]
I18N_FILE = REPO_ROOT / 'backend' / 'i18n' / 'i18nData.json'
UNUSED_FILE = REPO_ROOT / 'i18nunused.txt'


def load_unused_keys(path: Path) -> Set[str]:
    if not path.exists():
        return set()
    return {line.strip() for line in path.read_text(encoding='utf-8').splitlines() if line.strip()}


def make_backup(src: Path) -> Path:
    backup = src.with_suffix('.json.bak')
    # include timestamp to avoid overwriting old backup
    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_ts = src.parent / f"{src.stem}.{ts}.bak"
    shutil.copy2(src, backup)
    shutil.copy2(src, backup_ts)
    return backup_ts


def prune_i18n(data: Dict[str, Any], unused: Set[str]) -> Dict[str, Any]:
    # If structured by languages
    if all(isinstance(v, dict) for v in data.values()):
        for lang, mapping in list(data.items()):
            if not isinstance(mapping, dict):
                continue
            for key in list(mapping.keys()):
                if key in unused:
                    mapping.pop(key, None)
    else:
        # Flat structure
        for key in list(data.keys()):
            if key in unused:
                data.pop(key, None)
    return data


def main() -> None:
    if not I18N_FILE.exists():
        print(f"i18n file not found: {I18N_FILE}")
        return
    unused = load_unused_keys(UNUSED_FILE)
    if not unused:
        print(f"No unused keys found in {UNUSED_FILE}; nothing to prune.")
        return

    raw = I18N_FILE.read_text(encoding='utf-8')
    try:
        data = json.loads(raw)
    except Exception as e:
        print(f"Failed to parse {I18N_FILE}: {e}")
        return

    before_counts = {}
    if all(isinstance(v, dict) for v in data.values()):
        for lang, mapping in data.items():
            if isinstance(mapping, dict):
                before_counts[lang] = len(mapping)
    else:
        before_counts['flat'] = len(data)

    backup = make_backup(I18N_FILE)
    pruned = prune_i18n(data, unused)

    I18N_FILE.write_text(json.dumps(pruned, ensure_ascii=False, indent=2), encoding='utf-8')

    after_counts = {}
    if all(isinstance(v, dict) for v in pruned.values()):
        for lang, mapping in pruned.items():
            if isinstance(mapping, dict):
                after_counts[lang] = len(mapping)
    else:
        after_counts['flat'] = len(pruned)

    print(f"Backup created: {backup}")
    print(f"Pruned {len(unused)} candidate keys.")
    print(f"Counts before: {before_counts}")
    print(f"Counts after:  {after_counts}")


if __name__ == '__main__':
    main()


