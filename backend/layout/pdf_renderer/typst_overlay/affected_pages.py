# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

"""Compute PDF page indices affected by translation segment edits."""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional, Set

from layout.base import LayoutBlock, LayoutDocument
from layout.pdf_renderer.typst_overlay.segment_font_metrics import (
    resolve_segment_layout_block_indices,
)


def _block_has_cross_page_lines(block: LayoutBlock) -> bool:
    raw = getattr(block, "raw", None) or {}
    if not isinstance(raw, dict):
        return False
    for line in raw.get("lines") or []:
        if not isinstance(line, dict):
            continue
        for span in line.get("spans") or []:
            if isinstance(span, dict) and span.get("cross_page"):
                return True
    return False


def _layout_block_map(layout_doc: LayoutDocument) -> Dict[int, LayoutBlock]:
    block_map: Dict[int, LayoutBlock] = {}
    for block in layout_doc.iter_blocks():
        if block.index is None:
            continue
        block_map[int(block.index)] = block
    return block_map


def compute_affected_page_indices_0based(
    layout_doc: Optional[LayoutDocument],
    segments: List[Dict[str, Any]],
    segment_indices: Iterable[int],
    task_state: Optional[Dict[str, Any]] = None,
    *,
    include_neighbor_pages: bool = False,
) -> List[int]:
    """Return sorted zero-based page indices that must be re-rendered."""
    if layout_doc is None or not segments:
        return []

    index_set = {int(i) for i in segment_indices}
    if not index_set:
        return []

    seg_by_index: Dict[int, Dict[str, Any]] = {}
    for seg in segments:
        if not isinstance(seg, dict):
            continue
        raw_idx = seg.get("segment_index")
        if raw_idx is None:
            continue
        try:
            seg_by_index[int(raw_idx)] = seg
        except (TypeError, ValueError):
            continue

    block_map = _layout_block_map(layout_doc)
    page_count = max(1, int(getattr(layout_doc, "page_count", 0) or 0))
    affected: Set[int] = set()

    for seg_idx in sorted(index_set):
        segment = seg_by_index.get(seg_idx)
        if segment is None:
            continue
        block_indices = resolve_segment_layout_block_indices(segment, task_state)
        for block_idx in block_indices:
            block = block_map.get(block_idx)
            if block is None:
                continue
            page_index = getattr(block, "page_index", None)
            if page_index is None:
                continue
            try:
                page_i = int(page_index)
            except (TypeError, ValueError):
                continue
            if page_i < 0 or page_i >= page_count:
                continue
            affected.add(page_i)
            if _block_has_cross_page_lines(block):
                next_page = page_i + 1
                if next_page < page_count:
                    affected.add(next_page)
            if include_neighbor_pages:
                if page_i > 0:
                    affected.add(page_i - 1)
                if page_i + 1 < page_count:
                    affected.add(page_i + 1)

    return sorted(affected)


def compute_affected_page_numbers_1based(
    layout_doc: Optional[LayoutDocument],
    segments: List[Dict[str, Any]],
    segment_indices: Iterable[int],
    task_state: Optional[Dict[str, Any]] = None,
    *,
    include_neighbor_pages: bool = False,
) -> List[int]:
    """Return sorted one-based page numbers for API consumers."""
    return [
        page + 1
        for page in compute_affected_page_indices_0based(
            layout_doc,
            segments,
            segment_indices,
            task_state,
            include_neighbor_pages=include_neighbor_pages,
        )
    ]
