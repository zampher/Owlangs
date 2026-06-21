# SPDX-FileCopyrightText: 2026 Zampherss
# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Optional


def merge_template_into_current(template_data: Any, current_data: Any) -> Any:
    """
    Merge template structure into current data without overwriting user values.

    Rules:
    - dict + dict: recursively merge; template provides missing keys, current keeps existing keys.
    - other types: keep current if it is not None; otherwise fall back to template.
    """
    if isinstance(template_data, dict) and isinstance(current_data, dict):
        # Start from current data to preserve its key order.
        # New keys from the template are appended at the end.
        merged = dict(current_data)
        for k, tv in template_data.items():
            if k in merged:
                merged[k] = merge_template_into_current(tv, merged[k])
            else:
                merged[k] = tv
        return merged

    if current_data is not None:
        return current_data
    return template_data


def maybe_merge_json_file_with_template(
    *,
    current_path: Path,
    template_path: Path,
    write_back: bool = True,
) -> Optional[dict]:
    """
    If both current and template exist, merge template structure into current and optionally write back.
    Returns merged dict when merge happened or current dict when no merge is needed; returns None on parse failures.
    """
    if not current_path.exists() or not template_path.exists():
        return None

    try:
        current_data = json.loads(current_path.read_text(encoding="utf-8-sig"))
        template_data = json.loads(template_path.read_text(encoding="utf-8-sig"))
    except Exception:
        return None

    if not isinstance(current_data, dict) or not isinstance(template_data, dict):
        return None

    merged = merge_template_into_current(template_data, current_data)
    if merged == current_data:
        return current_data

    if write_back:
        current_path.parent.mkdir(parents=True, exist_ok=True)
        current_path.write_text(
            json.dumps(merged, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    return merged

