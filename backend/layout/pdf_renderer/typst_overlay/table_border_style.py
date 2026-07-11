# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

"""Table border style presets for Typst overlay PDF tables."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

TABLE_BORDER_STYLE_GRID = "grid"
TABLE_BORDER_STYLE_BOOKTABS = "booktabs"
TABLE_BORDER_STYLE_BOOKTABS_2 = "booktabs_2"
TABLE_BORDER_STYLE_BOOKTABS_3 = "booktabs_3"
TABLE_BORDER_STYLE_HORIZONTAL = "horizontal"
TABLE_BORDER_STYLE_OUTER = "outer"
TABLE_BORDER_STYLE_NONE = "none"

DEFAULT_TABLE_BORDER_STYLE = TABLE_BORDER_STYLE_BOOKTABS

BOOKTABS_BORDER_STYLES = frozenset({
    TABLE_BORDER_STYLE_BOOKTABS,
    TABLE_BORDER_STYLE_BOOKTABS_2,
    TABLE_BORDER_STYLE_BOOKTABS_3,
})

VALID_TABLE_BORDER_STYLES = frozenset({
    TABLE_BORDER_STYLE_GRID,
    TABLE_BORDER_STYLE_BOOKTABS,
    TABLE_BORDER_STYLE_BOOKTABS_2,
    TABLE_BORDER_STYLE_BOOKTABS_3,
    TABLE_BORDER_STYLE_HORIZONTAL,
    TABLE_BORDER_STYLE_OUTER,
    TABLE_BORDER_STYLE_NONE,
})


def is_booktabs_border_style(style: Optional[str]) -> bool:
    """Return True when [style] is a booktabs (three-line) table preset."""
    normalized = normalize_table_border_style(style)
    return normalized in BOOKTABS_BORDER_STYLES


def booktabs_header_row_count(style: Optional[str]) -> int:
    """Return title/header row count for a booktabs preset (0 when not booktabs)."""
    normalized = normalize_table_border_style(style)
    if normalized == TABLE_BORDER_STYLE_BOOKTABS_3:
        return 3
    if normalized == TABLE_BORDER_STYLE_BOOKTABS_2:
        return 2
    if normalized == TABLE_BORDER_STYLE_BOOKTABS:
        return 1
    return 0


def _normalize_title_cell_key(text: Any) -> str:
    """Normalize title cell text for adjacent-equality comparison."""
    return str(text or "").strip()


def group_adjacent_equal_row_cells(row: List[Any]) -> List[tuple[str, int]]:
    """Group adjacent cells in one row with identical text into (text, colspan) spans."""
    groups: List[tuple[str, int]] = []
    for cell in row:
        text = _normalize_title_cell_key(cell)
        if groups and groups[-1][0] == text:
            prev_text, span = groups[-1]
            groups[-1] = (prev_text, span + 1)
        else:
            groups.append((text, 1))
    return groups


def normalize_table_border_style(value: Any) -> Optional[str]:
    """Normalize user table border style; return None when invalid."""
    if value is None:
        return None
    style = str(value).strip().lower()
    if style not in VALID_TABLE_BORDER_STYLES:
        return None
    return style


def resolve_table_border_style(
    style: Optional[str],
    *,
    stroke_pt: float = 0.5,
) -> str:
    """Return effective border style; stroke_pt=0 implies no visible lines."""
    normalized = normalize_table_border_style(style) or DEFAULT_TABLE_BORDER_STYLE
    if stroke_pt <= 0 or normalized == TABLE_BORDER_STYLE_NONE:
        return TABLE_BORDER_STYLE_NONE
    return normalized


def build_block_table_border_style_map_from_segments(
    segments: List[Dict[str, Any]],
    task_state: Optional[Dict[str, Any]] = None,
) -> Dict[int, str]:
    """Expand segment-level table border style overrides to layout block indices."""
    from layout.pdf_renderer.typst_overlay.segment_font_metrics import (
        resolve_segment_layout_block_indices,
    )

    block_map: Dict[int, str] = {}
    for seg in segments:
        if not isinstance(seg, dict):
            continue
        if "table_border_style" not in seg:
            continue
        style = normalize_table_border_style(seg.get("table_border_style"))
        if style is None:
            continue
        for idx in resolve_segment_layout_block_indices(seg, task_state):
            block_map[idx] = style
    return block_map
