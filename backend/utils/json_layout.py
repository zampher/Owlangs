# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0
"""
JSON layout preservation: parse newlines from original file and dump back
so exported JSON keeps the same line breaks (e.g. blank lines between sections).

Applies to flat JSON objects (top-level key-value only). ARB is one such format.
"""
import json
import re
from typing import Any


# Match a single top-level key line: "key": value (value can be string, number, etc.)
_RE_KEY_LINE = re.compile(r'^\s*"([^"]+)"\s*:\s*(.+)$')


def parse_json_layout(json_text: str) -> list[tuple[str, int]]:
    """
    Parse original JSON text to record key order and newlines before each key.
    Used for flat JSON (e.g. ARB: top-level keys only).

    Returns:
        List of (key, newlines_before) in key order. newlines_before is 0, 1, or 2
        (0 = same line as previous, 1 = single newline, 2 = blank line).
    """
    layout: list[tuple[str, int]] = []
    lines = json_text.split('\n')
    blank_count = 0
    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()
        if not stripped:
            blank_count += 1
            i += 1
            continue
        # Opening/closing brace only
        if stripped in ('{', '}'):
            i += 1
            continue
        m = _RE_KEY_LINE.match(line)
        if m:
            key = m.group(1)
            # Cap blank lines so we don't emit excessive newlines
            newlines_before = min(blank_count, 2) if blank_count else 0
            layout.append((key, newlines_before))
            blank_count = 0
        i += 1
    return layout


def dump_json_preserving_layout(content: dict[str, Any], layout: list[tuple[str, int]]) -> str:
    """
    Dump JSON dict to string preserving key order and newlines from layout.
    Keys in content that are not in layout are appended at the end with single newline.
    """
    if not content:
        return '{\n}\n'
    # Build key order and newlines from layout; then add any extra keys from content
    seen = set()
    key_order: list[tuple[str, int]] = []
    for key, newlines in layout:
        if key in content and key not in seen:
            key_order.append((key, newlines))
            seen.add(key)
    for key in content:
        if key not in seen:
            key_order.append((key, 1))  # extra key: one newline before
    # Emit lines
    out: list[str] = ['{']
    emitted_keys = [k for k, _ in key_order if k in content]
    for idx, (key, newlines_before) in enumerate(key_order):
        if key not in content:
            continue
        val = content[key]
        # Emit newlines before this key (except before first key)
        if newlines_before > 0:
            out.append('')
            if newlines_before >= 2:
                out.append('')
        # JSON-encode value (strings get escaped)
        val_str = json.dumps(val, ensure_ascii=False)
        # Last emitted key: no trailing comma (JSON standard)
        is_last = key == emitted_keys[-1] if emitted_keys else True
        comma = '' if is_last else ','
        out.append(f'  "{key}": {val_str}{comma}')
    out.append('}')
    return '\n'.join(out) + '\n'
