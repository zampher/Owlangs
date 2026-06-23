# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

"""
Z-order and overlap helpers for Typst overlay rendering.

Ensures embedded images are painted before text in the overlay PDF so
translated text appears on top when regions overlap.
"""

from __future__ import annotations

from typing import Dict, List, Tuple

from layout.base import LayoutDocument
from logger.logger import LogModule, unified_logger
from layout.pdf_renderer.typst_overlay.models import RenderBlock

BBox = Tuple[float, float, float, float]


def bboxes_overlap(a: BBox, b: BBox) -> bool:
    """Return True when two axis-aligned bboxes share a positive-area intersection."""
    ax0, ay0, ax1, ay1 = a
    bx0, by0, bx1, by1 = b
    return ax0 < bx1 and ax1 > bx0 and ay0 < by1 and ay1 > by0


def _parse_bbox(raw_bbox) -> BBox | None:
    if not isinstance(raw_bbox, (list, tuple)) or len(raw_bbox) != 4:
        return None
    try:
        return tuple(float(v) for v in raw_bbox)
    except (TypeError, ValueError):
        return None


def collect_visual_region_bboxes_by_page(layout_doc: LayoutDocument) -> Dict[int, List[BBox]]:
    """Collect layout bboxes for visual blocks (image/chart/table) per page."""
    from layout.block_types import IMAGE, LEGACY_FIGURE

    by_page: Dict[int, List[BBox]] = {}
    for page in layout_doc.pages:
        for block in page.blocks:
            is_layout_image = block.type in (IMAGE, LEGACY_FIGURE) or block.has_image()
            is_visual_container = block.is_visual() and block.type in ("chart", "table")
            if not is_layout_image and not is_visual_container:
                continue
            bbox = _parse_bbox(block.bbox)
            if bbox is not None:
                by_page.setdefault(page.page_index, []).append(bbox)
    return by_page


def _render_block_layer_rank(block: RenderBlock) -> int:
    """Lower rank is painted earlier (under later blocks in Typst)."""
    if block.render_kind == "image":
        return 0
    if block.use_cover_fill:
        return 1
    if block.render_kind == "table":
        return 2
    return 3


def sort_render_blocks_image_under_text(blocks: List[RenderBlock]) -> List[RenderBlock]:
    """Sort blocks so images are emitted before text within one overlay page."""
    return sorted(
        blocks,
        key=lambda b: (
            _render_block_layer_rank(b),
            b.inner_bbox[1],
            b.inner_bbox[0],
            b.block_id,
        ),
    )


def clear_opaque_fill_over_visual_regions(
    blocks: List[RenderBlock],
    visual_bboxes: List[BBox],
) -> int:
    """Legacy helper: no longer strips opaque backing (text on images needs erase)."""
    return 0


def ensure_opaque_backing_for_text_over_embedded_images(
    blocks: List[RenderBlock],
    embedded_image_bboxes: List[BBox],
) -> int:
    """Use white backing on text overlays that sit on embedded raster images."""
    if not embedded_image_bboxes:
        return 0
    applied = 0
    for block in blocks:
        if block.render_kind in ("image", "table", "skip"):
            continue
        for image_bbox in embedded_image_bboxes:
            if bboxes_overlap(block.inner_bbox, image_bbox):
                if not block.opaque_fill:
                    block.opaque_fill = True
                    applied += 1
                break
    return applied


def background_embed_force_opaque(
    block: RenderBlock,
    page_blocks: List[RenderBlock],
) -> bool:
    """Use opaque white text backing on scanned PDFs and over embedded images."""
    if block.render_kind == "image":
        return False
    image_bboxes = [b.inner_bbox for b in page_blocks if b.render_kind == "image"]
    for image_bbox in image_bboxes:
        if bboxes_overlap(block.inner_bbox, image_bbox):
            return True
    # Engineering PDFs with embedded drawings: only erase under text-on-image.
    if image_bboxes:
        return False
    # Pure scanned pages without separate embedded images: opaque everywhere.
    return True


def finalize_render_blocks_by_page(
    render_blocks_by_page: Dict[int, List[RenderBlock]],
    layout_doc: LayoutDocument,
) -> Dict[int, List[RenderBlock]]:
    """Apply text erase backing on embedded images and image-under-text ordering."""
    finalized: Dict[int, List[RenderBlock]] = {}

    for page_idx, blocks in render_blocks_by_page.items():
        embedded_image_bboxes = [
            b.inner_bbox for b in blocks if b.render_kind == "image"
        ]
        text_opaque = ensure_opaque_backing_for_text_over_embedded_images(
            blocks,
            embedded_image_bboxes,
        )
        sorted_blocks = sort_render_blocks_image_under_text(blocks)
        finalized[page_idx] = sorted_blocks

        has_image = any(b.render_kind == "image" for b in sorted_blocks)
        has_text = any(b.render_kind not in ("image", "skip") for b in sorted_blocks)
        if has_image and has_text:
            unified_logger.info(
                LogModule.RESTOR,
                f"[TYPST_OVERLAY] Page {page_idx}: image-under-text layer order "
                f"(blocks={len(sorted_blocks)}, text_opaque_on_image={text_opaque})",
            )

    return finalized
