# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

"""
LayoutDocument merging utilities.

Merges multiple LayoutDocuments (e.g. from split PDF parts) into a single
LayoutDocument, adjusting page_index and block.index to maintain global
uniqueness and correct reading order.
"""

from typing import List

from layout.base import LayoutDocument, LayoutPage, LayoutBlock


def merge_layout_documents(docs: List[LayoutDocument]) -> LayoutDocument:
    """
    Merge multiple LayoutDocuments into one.

    Adjusts ``page_index`` for all pages/blocks and reassigns ``block.index``
    globally so that segment mapping remains valid across the merged document.

    Args:
        docs: List of LayoutDocuments, in correct reading order.

    Returns:
        A new LayoutDocument containing all pages and blocks from the inputs.
    """
    merged_pages: List[LayoutPage] = []
    global_block_idx = 0
    page_offset = 0

    for doc in docs:
        for page in doc.pages:
            new_page = LayoutPage(
                page_index=page.page_index + page_offset,
                blocks=[],
                width=page.width,
                height=page.height,
            )
            for block in page.blocks:
                new_block = LayoutBlock(
                    page_index=block.page_index + page_offset,
                    bbox=block.bbox,
                    type=block.type,
                    index=global_block_idx,
                    text=block.text,
                    image_path=block.image_path,
                    raw=_adjust_raw_page_idx(block.raw, page_offset) if block.raw else {},
                )
                new_page.blocks.append(new_block)
                global_block_idx += 1
            merged_pages.append(new_page)
        page_offset += doc.page_count

    metadata = docs[0].metadata.copy() if docs else {}
    return LayoutDocument(pages=merged_pages, engine="mineru", metadata=metadata)


def _adjust_raw_page_idx(raw: dict, page_offset: int) -> dict:
    """Return a shallow copy of *raw* with ``page_idx`` incremented by *page_offset*."""
    adjusted = dict(raw)
    if "page_idx" in adjusted:
        adjusted["page_idx"] = adjusted["page_idx"] + page_offset
    return adjusted
