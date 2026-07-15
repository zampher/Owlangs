# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

"""Shared layout group companion enrichment for Paddle, MinerU, and preview APIs."""

from __future__ import annotations

from typing import Any, Dict, Optional

from layout.base import LayoutDocument
from logger import unified_logger as logger
from logger.logger import LogModule


def enrich_layout_group_pairs_on_document(
    doc: LayoutDocument,
    paddle_raw_payload: Optional[Dict[str, Any]] = None,
    *,
    apply_paddle_groups: bool = True,
    log_prefix: str = "LAYOUT-GROUP",
) -> None:
    """Ensure group pair metadata exists after loading a layout document."""
    from layout.layout_group_pair_utils import (
        LAYOUT_GROUP_PAIRS_KEY,
        layout_group_pairs_from_raw,
        resolve_layout_group_pairs_for_block,
        sanitize_layout_group_pairs_on_document,
    )
    from layout.ocr_provider.paddle.layout_group_pairs import (
        apply_figure_wrap_layout_group_pairs,
        apply_paddle_layout_group_pairs,
        apply_spatial_layout_group_pairs,
    )
    from layout.ocr_provider.mineru.layout_group_pairs import (
        apply_mineru_spatial_layout_group_pairs,
    )

    if paddle_raw_payload and apply_paddle_groups:
        from layout.ocr_provider.paddle.zip_loader import (
            _merge_group_pair_meta_from_paddle_raw,
        )

        _merge_group_pair_meta_from_paddle_raw(doc, paddle_raw_payload)

    for page in doc.pages:
        page_height = float(page.height) if page.height else None
        page_width = float(page.width) if page.width else None
        if apply_paddle_groups:
            apply_paddle_layout_group_pairs(
                page.blocks,
                page_height=page_height,
                page_width=page_width,
            )
            apply_spatial_layout_group_pairs(
                page.blocks,
                page_height=page_height,
                page_width=page_width,
            )
            apply_figure_wrap_layout_group_pairs(
                page.blocks,
                page_height=page_height,
                page_width=page_width,
            )
        else:
            apply_mineru_spatial_layout_group_pairs(
                page.blocks,
                page_height=page_height,
                page_width=page_width,
            )
            apply_figure_wrap_layout_group_pairs(
                page.blocks,
                page_height=page_height,
                page_width=page_width,
            )

    sanitize_layout_group_pairs_on_document(doc)

    enriched_primaries = 0
    for page in doc.pages:
        for block in page.blocks:
            raw = block.raw if isinstance(block.raw, dict) else {}
            if layout_group_pairs_from_raw(raw):
                continue
            pairs = resolve_layout_group_pairs_for_block(block, doc)
            if not pairs:
                continue
            enriched = dict(raw)
            enriched[LAYOUT_GROUP_PAIRS_KEY] = pairs
            block.raw = enriched
            enriched_primaries += 1

    if enriched_primaries:
        logger.info(
            LogModule.LAYOUT,
            f"[{log_prefix}] Enriched "
            f"{enriched_primaries} primary block(s) with layout group pair metadata",
        )
