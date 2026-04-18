#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Scan i18nData.json and find keys unused across the codebase (excluding settings section).
Output the unused keys to i18nunused.txt at repo root.

Usage:
  python tools/find_unused_i18n.py
"""

from __future__ import annotations
import json
import os
import re
from pathlib import Path
from typing import Iterable, Set, Dict


REPO_ROOT = Path(__file__).resolve().parents[1]
I18N_FILE = REPO_ROOT / 'backend' / 'i18n' / 'i18nData.json'
OUTPUT_FILE = REPO_ROOT / 'i18nunused.txt'


def load_i18n_keys(path: Path) -> Set[str]:
    data = json.loads(path.read_text(encoding='utf-8'))
    # i18nData.json is expected to have top-level languages (e.g., zh, en)
    keys: Set[str] = set()
    if isinstance(data, dict):
        # If structured as { 'zh': {...}, 'en': {...} }
        langs = [k for k in data.keys() if isinstance(data.get(k), dict)]
        if langs and all(isinstance(data.get(lang), dict) for lang in langs):
            for lang in langs:
                keys.update(data.get(lang, {}).keys())
        else:
            # Flat dictionary of keys
            keys.update(data.keys())
    return keys


def should_skip(file_path: Path) -> bool:
    p = str(file_path)
    # Exclude settings section entirely and i18n files themselves
    if '/static/settings/' in p.replace('\\', '/'):
        return True
    if p.endswith('/backend/static/settings.html'):
        return True
    if p.endswith('/backend/i18n/i18nData.json'):
        return True
    if p.endswith('/backend/i18n/i18nSettings.json'):
        return True
    # Skip common binary/asset dirs
    if any(seg in p for seg in ['/node_modules/', '/.git/', '/dist/', '/build/']):
        return True
    return False


SEARCH_EXTS = {'.html', '.js', '.jsx', '.ts', '.tsx', '.py'}


def iter_files(base: Path) -> Iterable[Path]:
    for root, dirs, files in os.walk(base):
        for f in files:
            path = Path(root) / f
            if should_skip(path):
                continue
            if path.suffix.lower() in SEARCH_EXTS:
                yield path


def build_usage_patterns() -> Dict[str, re.Pattern]:
    # Patterns to capture i18n key usages
    patterns = {
        'data_i18n': re.compile(r'data-i18n\s*=\s*"([^"]+)"'),
        'data_i18n_placeholder': re.compile(r'data-i18n-placeholder\s*=\s*"([^"]+)"'),
        'data_i18n_title': re.compile(r'data-i18n-title\s*=\s*"([^"]+)"'),
        # JS calls: getText('key'), getText("key"), window.SettingsCore.getText('key')
        'getText_single': re.compile(r'\bgetText\(\s*\'([^\']+)\'\s*\)'),
        'getText_double': re.compile(r'\bgetText\(\s*\"([^\"]+)\"\s*\)'),
        'core_getText_single': re.compile(r'window\.SettingsCore\.getText\(\s*\'([^\']+)\'\s*\)'),
        'core_getText_double': re.compile(r'window\.SettingsCore\.getText\(\s*\"([^\"]+)\"\s*\)'),
    }
    return patterns


def find_used_keys(files: Iterable[Path]) -> Set[str]:
    patterns = build_usage_patterns()
    used: Set[str] = set()
    for path in files:
        try:
            text = path.read_text(encoding='utf-8', errors='ignore')
        except Exception:
            continue
        for pat in patterns.values():
            for m in pat.finditer(text):
                key = (m.group(1) or '').strip()
                if key:
                    used.add(key)
    return used


def main() -> None:
    if not I18N_FILE.exists():
        print(f'i18n file not found: {I18N_FILE}')
        return
    keys = load_i18n_keys(I18N_FILE)
    files = list(iter_files(REPO_ROOT))
    used = find_used_keys(files)
    unused = sorted(k for k in keys if k not in used)
    OUTPUT_FILE.write_text('\n'.join(unused) + ('\n' if unused else ''), encoding='utf-8')
    print(f'Checked {len(keys)} keys; unused: {len(unused)}')
    print(f'Output: {OUTPUT_FILE}')


if __name__ == '__main__':
    main()


