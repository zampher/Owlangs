# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0
"""Expand layout block indices for text overlay (list parent -> child blocks)."""

from __future__ import annotations

from typing import Dict, List

from layout.base import LayoutDocument
from logger.logger import LogModule, unified_logger

_RENDERABLE_TEXT_BLOCK_TYPES = frozenset(
    {"text", "title", "header", "footer", "page_number", "ref_text", "figure", "caption"}
)


def _bbox_contains(outer: tuple, inner: tuple, *, margin: float = 1.0) -> bool:
    ox0, oy0, ox1, oy1 = outer
    ix0, iy0, ix1, iy1 = inner
    return (
        ix0 >= ox0 - margin
        and iy0 >= oy0 - margin
        and ix1 <= ox1 + margin
        and iy1 <= oy1 + margin
    )


def _is_list_expandable_child_type(block_type: str) -> bool:
    return block_type in _RENDERABLE_TEXT_BLOCK_TYPES and block_type not in {
        "list",
        "figure",
    }


def _collect_list_child_indices(
    list_index: int,
    layout_doc: LayoutDocument,
    block_index_to_type: Dict[int, str],
    block_index_to_bbox: Dict[int, tuple],
) -> List[int]:
    list_bbox = block_index_to_bbox.get(list_index)
    if not list_bbox:
        return []

    page_index = None
    for block in layout_doc.iter_blocks():
        if block.index == list_index:
            page_index = block.page_index
            break
    if page_index is None:
        return []

    page_blocks = sorted(
        (
            block
            for block in layout_doc.iter_blocks()
            if block.page_index == page_index and block.index is not None
        ),
        key=lambda block: block.index,
    )

    sequential_children: List[int] = []
    passed_list = False
    for block in page_blocks:
        if block.index == list_index:
            passed_list = True
            continue
        if not passed_list:
            continue
        btype = block_index_to_type.get(block.index, block.type)
        if btype == "list":
            break
        if btype in {"image", "table", "chart", "interline_equation"}:
            break
        child_bbox = block_index_to_bbox.get(block.index, block.bbox)
        if not _bbox_contains(list_bbox, child_bbox):
            break
        if _is_list_expandable_child_type(btype) and (block.text or "").strip():
            sequential_children.append(block.index)

    if sequential_children:
        return sequential_children

    contained: List[int] = []
    for block in page_blocks:
        if block.index == list_index:
            continue
        btype = block_index_to_type.get(block.index, block.type)
        if not _is_list_expandable_child_type(btype) or not (block.text or "").strip():
            continue
        child_bbox = block_index_to_bbox.get(block.index, block.bbox)
        if _bbox_contains(list_bbox, child_bbox):
            contained.append(block.index)
    contained.sort(
        key=lambda idx: (
            block_index_to_bbox.get(idx, (0, 0, 0, 0))[1],
            block_index_to_bbox.get(idx, (0, 0, 0, 0))[0],
        )
    )
    return contained


def expand_renderable_block_indices(
    indices: List[int],
    layout_doc: LayoutDocument,
    block_index_to_type: Dict[int, str],
    block_index_to_bbox: Dict[int, tuple],
) -> List[int]:
    """Expand non-renderable list blocks to contained text/ref_text layout blocks."""
    expanded: List[int] = []
    seen: set[int] = set()

    for raw_idx in indices:
        try:
            block_index_int = int(raw_idx)
        except (TypeError, ValueError):
            continue
        if block_index_int in seen:
            continue
        block_type = block_index_to_type.get(block_index_int, "text")
        if block_type != "list":
            seen.add(block_index_int)
            expanded.append(block_index_int)
            continue

        child_indices = _collect_list_child_indices(
            block_index_int,
            layout_doc,
            block_index_to_type,
            block_index_to_bbox,
        )
        if child_indices:
            unified_logger.info(
                LogModule.EXPORT,
                f"[LAYOUT] Expanded list block {block_index_int} to child blocks {child_indices}",
            )
            for child_idx in child_indices:
                if child_idx not in seen:
                    seen.add(child_idx)
                    expanded.append(child_idx)
        else:
            unified_logger.warning(
                LogModule.EXPORT,
                f"[LAYOUT] List block {block_index_int} has no renderable children; "
                "translation will not overlay on Typst PDF",
            )
            seen.add(block_index_int)
            expanded.append(block_index_int)
    return expanded
