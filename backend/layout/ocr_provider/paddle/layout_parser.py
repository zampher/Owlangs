# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

"""
PaddleOCR layout parser: JSONL result → :class:`LayoutDocument`.

Parses the PaddleOCR v2 async API result payload, converting it into
the platform-agnostic layout IR used by all downstream consumers.

PaddleOCR returns bbox coordinates in image pixel space (relative to the
rendered page image).  The downstream pipeline expects coordinates in PDF
point space (1/72 inch).  This module normalises bbox values when
``pdf_page_dims`` is provided, using the ratio of PDF point dimensions to
PaddleOCR image dimensions.
"""

from typing import Any, Dict, List, Optional, Tuple

from layout.base import LayoutBlock, LayoutPage, LayoutDocument
from layout.ocr_provider.paddle.block_labels import map_paddle_label
from logger import unified_logger as logger
from logger.logger import LogModule

# Sentinel value for image_path on PaddleOCR image blocks so that
# LayoutBlock.has_image() returns True even though PaddleOCR does not
# provide separate image files.
_PADDLE_IMAGE_PATH_SENTINEL = "__paddle_image__"

# When bbox max extent exceeds reported page size by more than this ratio,
# treat bbox as living in a larger render-pixel canvas than dataInfo reports.
_BBOX_EXCEEDS_PAGE_RATIO = 1.02
# Tolerance for treating dataInfo dimensions as PDF points (not render pixels).
_PDF_DIM_MATCH_RATIO = 1.05


def _resolve_paddle_render_dimensions(
    image_w_raw: Any,
    image_h_raw: Any,
    max_x1: float,
    max_y1: float,
    pdf_w_pt: Optional[float],
    pdf_h_pt: Optional[float],
) -> Tuple[Optional[float], Optional[float], bool]:
    """Resolve PaddleOCR render canvas size and whether bbox is already PDF pt.

    PaddleOCR responses are inconsistent: ``dataInfo.pages[*].width/height`` may
    report PDF point dimensions while ``block_bbox`` stays in high-DPI render
    pixels, or bbox may already be normalised to PDF points when dataInfo matches
    the PDF page size.

    Returns:
        (render_w, render_h, bbox_already_pdf_pt)
    """
    image_w: Optional[float] = (
        float(image_w_raw) if image_w_raw is not None and float(image_w_raw) > 0 else None
    )
    image_h: Optional[float] = (
        float(image_h_raw) if image_h_raw is not None and float(image_h_raw) > 0 else None
    )

    if image_w is None and max_x1 > 0:
        image_w = max_x1
    if image_h is None and max_y1 > 0:
        image_h = max_y1

    bbox_already_pdf_pt = False
    if (
        pdf_w_pt
        and pdf_h_pt
        and max_x1 > 0
        and max_y1 > 0
        and max_x1 <= pdf_w_pt * _PDF_DIM_MATCH_RATIO
        and max_y1 <= pdf_h_pt * _PDF_DIM_MATCH_RATIO
    ):
        # Bbox fits inside the PDF page — coordinates are already in point space.
        bbox_already_pdf_pt = True
        if image_w and image_h:
            if (
                abs(image_w - pdf_w_pt) <= max(2.0, pdf_w_pt * 0.02)
                and abs(image_h - pdf_h_pt) <= max(2.0, pdf_h_pt * 0.02)
            ):
                return image_w, image_h, True
        return pdf_w_pt, pdf_h_pt, True

    # Bbox exceeds PDF page bounds → pixel space on a larger render canvas.
    if pdf_w_pt and pdf_h_pt and max_x1 > 0 and max_y1 > 0:
        if max_x1 > pdf_w_pt * _PDF_DIM_MATCH_RATIO and (
            image_w is None or image_w <= pdf_w_pt * _PDF_DIM_MATCH_RATIO
        ):
            image_w = max(image_w or 0.0, max_x1)
        if max_y1 > pdf_h_pt * _PDF_DIM_MATCH_RATIO and (
            image_h is None or image_h <= pdf_h_pt * _PDF_DIM_MATCH_RATIO
        ):
            image_h = max(image_h or 0.0, max_y1)

    # Reported dataInfo size is smaller than bbox extent — use bbox as ground truth.
    if image_w and max_x1 > image_w * _BBOX_EXCEEDS_PAGE_RATIO:
        image_w = max_x1
    if image_h and max_y1 > image_h * _BBOX_EXCEEDS_PAGE_RATIO:
        image_h = max_y1

    if not bbox_already_pdf_pt and pdf_w_pt and pdf_h_pt and image_w and image_h:
        image_w, image_h = _sync_render_canvas_aspect_ratio(
            image_w,
            image_h,
            pdf_w_pt,
            pdf_h_pt,
            max_x1,
            max_y1,
        )

    return image_w, image_h, bbox_already_pdf_pt


def _sync_render_canvas_aspect_ratio(
    render_w: float,
    render_h: float,
    pdf_w_pt: float,
    pdf_h_pt: float,
    max_x1: float,
    max_y1: float,
) -> Tuple[float, float]:
    """Derive a uniform pixel→PDF scale by aligning render canvas to PDF aspect.

    Paddle ``dataInfo`` height is often wrong (PDF points mixed with pixel width,
    or pixel aspect ≠ PDF aspect).  Mismatched ``scale_x``/``scale_y`` yields
    bbox widths that look fine while heights are too short.
    """
    pdf_aspect = pdf_w_pt / pdf_h_pt
    if pdf_aspect <= 0:
        return render_w, render_h

    in_pixel_space = (
        max_x1 > pdf_w_pt * _PDF_DIM_MATCH_RATIO
        or max_y1 > pdf_h_pt * _PDF_DIM_MATCH_RATIO
        or render_w > pdf_w_pt * _PDF_DIM_MATCH_RATIO
        or render_h > pdf_h_pt * _PDF_DIM_MATCH_RATIO
    )
    if not in_pixel_space:
        return render_w, render_h

    render_w = max(render_w, max_x1)
    synced_h = render_w / pdf_aspect
    if max_y1 > synced_h * _BBOX_EXCEEDS_PAGE_RATIO:
        synced_h = max(max_y1, render_h)
        render_w = synced_h * pdf_aspect
        logger.info(
            LogModule.LAYOUT,
            f"[PADDLE_PARSE] Sync render width from bbox height: "
            f"render={render_w:.1f}x{synced_h:.1f}px "
            f"(pdf={pdf_w_pt:.1f}x{pdf_h_pt:.1f}pt, max_bbox=({max_x1:.1f},{max_y1:.1f}))",
        )
        return render_w, synced_h

    if abs(synced_h - render_h) / max(render_h, 1.0) <= 0.02:
        return render_w, render_h

    logger.info(
        LogModule.LAYOUT,
        f"[PADDLE_PARSE] Sync render height to PDF aspect: "
        f"{render_h:.1f}px → {synced_h:.1f}px "
        f"(render_w={render_w:.1f}px, pdf={pdf_w_pt:.1f}x{pdf_h_pt:.1f}pt)",
    )
    return render_w, synced_h


def parse_paddle_layout(
    raw_data: Dict[str, Any],
    engine: str = "paddle",
    pdf_page_dims: Optional[List[Tuple[float, float]]] = None,
) -> Optional[LayoutDocument]:
    """
    Convert PaddleOCR JSONL result to platform-agnostic LayoutDocument.

    The PaddleOCR v2 API returns each page with a nested structure::

        {
            "layoutParsingResults": [
                {                                   # page-level payload
                    "dataInfo": {
                        "pages": [{"width": 595, "height": 842}]
                    },
                    "layoutParsingResults": [       # inner list (one per model pass)
                        {
                            "prunedResult": {
                                "parsing_res_list": [
                                    {
                                        "block_label": "text",
                                        "block_bbox": [x0, y0, x1, y1],
                                        "block_content": "...",
                                    },
                                    ...
                                ]
                            }
                        }
                    ]
                },
                ...
            ]
        }

    PaddleOCR renders each PDF page to an image before OCR, so
    ``dataInfo.pages[*].width/height`` are the *image* dimensions in
    pixels.  ``block_bbox`` coordinates are relative to that image.
    When ``pdf_page_dims`` (the actual PDF page dimensions in points,
    one tuple per page) is provided, bbox values are scaled from pixel
    space to point space so they match the downstream Typst overlay /
    redaction pipeline which operates in PDF points (1/72 inch).

    Args:
        raw_data: Parsed JSON payload from PaddleOCR.
        engine: Engine name to set on the resulting LayoutDocument (default "paddle").
        pdf_page_dims: Optional list of (width_pt, height_pt) tuples, one per
            page, giving the actual PDF page dimensions in points.  Used to
            normalise bbox coordinates from image pixels to PDF points.

    Returns:
        LayoutDocument or None if parsing fails.
    """
    try:
        layout_results = raw_data.get("layoutParsingResults", [])

        pages: List[LayoutPage] = []
        global_block_idx = 0

        # Track the cumulative physical page index across all outer chunks
        # for pdf_page_dims lookup.
        physical_page_index = 0

        for chunk_index, page_payload in enumerate(layout_results):
            if not isinstance(page_payload, dict):
                continue

            data_info = page_payload.get("dataInfo", {})
            pages_meta = data_info.get("pages", [])
            inner_results = page_payload.get("layoutParsingResults", [])

            if not inner_results:
                continue

            # PaddleOCR processes a batch of physical pages per API request.
            # Each entry in dataInfo.pages and each entry in inner_results
            # corresponds to ONE physical page.  They are NOT multiple model
            # passes on the same image — each inner has a distinct page number
            # and covers different content.
            for inner_idx, inner in enumerate(inner_results):
                if not isinstance(inner, dict):
                    continue

                # --- physical page dimensions ---
                page_meta = pages_meta[inner_idx] if inner_idx < len(pages_meta) else {}
                image_w_raw = page_meta.get("width")
                image_h_raw = page_meta.get("height")

                pruned = inner.get("prunedResult", {})
                if not isinstance(pruned, dict):
                    continue
                parsing_res_list = pruned.get("parsing_res_list", [])
                if not parsing_res_list:
                    continue

                # Collect blocks for this physical page
                raw_blocks: List[Tuple[tuple, str, str, list, bool, str, dict]] = []
                max_x1 = 0.0
                max_y1 = 0.0
                for block in parsing_res_list:
                    if not isinstance(block, dict):
                        continue
                    raw_label = str(block.get("block_label", "") or "")
                    block_type, sub_type, tags, should_translate = map_paddle_label(raw_label)
                    bbox_raw = block.get("block_bbox")
                    if not (isinstance(bbox_raw, list) and len(bbox_raw) == 4):
                        continue
                    try:
                        bbox = tuple(float(v) for v in bbox_raw)
                    except (TypeError, ValueError):
                        continue
                    text = str(block.get("block_content", "") or "")
                    raw_blocks.append((bbox, block_type, sub_type, tags, should_translate, text, dict(block)))
                    if bbox[2] > max_x1:
                        max_x1 = bbox[2]
                    if bbox[3] > max_y1:
                        max_y1 = bbox[3]

                if not raw_blocks:
                    continue

                # Sort blocks by PaddleOCR block_order to get correct
                # reading order.  Blocks without block_order (images,
                # tables, charts) are placed at the end, sorted by
                # spatial position (top→bottom, left→right).
                def _block_sort_key(item):
                    _raw = item[6]
                    _order = _raw.get("block_order")
                    _bbox = item[0]
                    if _order is not None:
                        return (0, _order, _bbox[1], _bbox[0])
                    return (1, _bbox[1], _bbox[0], 0)

                raw_blocks.sort(key=_block_sort_key)

                # --- bbox scaling to PDF point space ---
                pdf_w_pt: Optional[float] = None
                pdf_h_pt: Optional[float] = None
                if pdf_page_dims and physical_page_index < len(pdf_page_dims):
                    pdf_w_pt, pdf_h_pt = pdf_page_dims[physical_page_index]

                image_w, image_h, bbox_already_pdf_pt = _resolve_paddle_render_dimensions(
                    image_w_raw, image_h_raw, max_x1, max_y1, pdf_w_pt, pdf_h_pt,
                )

                scale_x = 1.0
                scale_y = 1.0
                if bbox_already_pdf_pt:
                    logger.info(
                        LogModule.LAYOUT,
                        f"[PADDLE_PARSE] Physical page {physical_page_index}: "
                        f"bbox already in PDF point space "
                        f"(pdf={pdf_w_pt:.1f}x{pdf_h_pt:.1f}pt, max_bbox=({max_x1:.1f},{max_y1:.1f}))",
                    )
                elif pdf_w_pt and pdf_h_pt and image_w and image_h and image_w > 0 and image_h > 0:
                    scale_x = pdf_w_pt / image_w
                    scale_y = pdf_h_pt / image_h
                    logger.info(
                        LogModule.LAYOUT,
                        f"[PADDLE_PARSE] Physical page {physical_page_index}: bbox scaling "
                        f"render=({image_w:.1f}x{image_h:.1f})px → "
                        f"pdf=({pdf_w_pt:.1f}x{pdf_h_pt:.1f})pt "
                        f"(sx={scale_x:.6f}, sy={scale_y:.6f})",
                    )
                elif pdf_w_pt and pdf_h_pt:
                    logger.warning(
                        LogModule.LAYOUT,
                        f"[PADDLE_PARSE] Physical page {physical_page_index}: "
                        f"cannot compute bbox scale "
                        f"(render_w={image_w}, render_h={image_h}, "
                        f"pdf_w={pdf_w_pt}, pdf_h={pdf_h_pt}); "
                        f"bbox will NOT be normalised",
                    )

                # --- build LayoutBlock list ---
                blocks: List[LayoutBlock] = []
                for bbox, block_type, sub_type, tags, should_translate, text, raw_dict in raw_blocks:
                    if scale_x != 1.0 or scale_y != 1.0:
                        bbox = (
                            round(bbox[0] * scale_x, 3),
                            round(bbox[1] * scale_y, 3),
                            round(bbox[2] * scale_x, 3),
                            round(bbox[3] * scale_y, 3),
                        )

                    image_path: Optional[str] = None
                    if block_type == "image":
                        image_path = _PADDLE_IMAGE_PATH_SENTINEL

                    lb = LayoutBlock(
                        page_index=physical_page_index,
                        bbox=bbox,
                        type=block_type,
                        sub_type=sub_type,
                        index=global_block_idx,
                        text=text,
                        tags=list(tags),
                        should_translate=should_translate,
                        image_path=image_path,
                        raw=raw_dict,
                    )
                    blocks.append(lb)
                    global_block_idx += 1

                pages.append(LayoutPage(
                    page_index=physical_page_index,
                    blocks=blocks,
                    width=pdf_w_pt if pdf_w_pt else image_w,
                    height=pdf_h_pt if pdf_h_pt else image_h,
                ))
                logger.info(
                    LogModule.LAYOUT,
                    f"[PADDLE_PARSE] Physical page {physical_page_index}: "
                    f"{len(blocks)} blocks "
                    f"(chunk {chunk_index}, inner {inner_idx})",
                )
                physical_page_index += 1

        doc = LayoutDocument(pages=pages, engine=engine)
        logger.info(LogModule.LAYOUT, f"Parsed PaddleOCR layout: {len(pages)} pages, {global_block_idx} blocks")
        return doc

    except Exception as e:
        logger.error(LogModule.LAYOUT, f"Failed to parse PaddleOCR layout: {e}", exc_info=True)
        return None


def extract_paddle_markdown(raw_data: Dict[str, Any]) -> str:
    """Extract markdown text from a PaddleOCR result payload.

    When the API does not include a ``markdown.text`` field (common for
    image inputs), the fallback builds basic markdown from the layout
    blocks' ``block_content`` so that downstream segment extraction can
    still produce translatable segments.
    """
    markdown = raw_data.get("markdown", {})
    if isinstance(markdown, dict):
        text = str(markdown.get("text", "") or "")
        if text.strip():
            return text
    elif markdown and str(markdown).strip():
        return str(markdown)

    logger.info(LogModule.LAYOUT, "[PADDLE] No markdown in API result; building from layout blocks")
    return _build_markdown_from_blocks(raw_data)


def _build_markdown_from_blocks(raw_data: Dict[str, Any]) -> str:
    """Build basic markdown from PaddleOCR block_content as a fallback."""
    layout_results = raw_data.get("layoutParsingResults", [])
    parts: List[str] = []

    for page_payload in layout_results:
        if not isinstance(page_payload, dict):
            continue

        inner_results = page_payload.get("layoutParsingResults", [])
        for inner in inner_results:
            if not isinstance(inner, dict):
                continue
            pruned = inner.get("prunedResult", {})
            if not isinstance(pruned, dict):
                continue
            parsing_res_list = pruned.get("parsing_res_list", [])
            if not parsing_res_list:
                continue

            for block in parsing_res_list:
                if not isinstance(block, dict):
                    continue
                raw_label = str(block.get("block_label", "") or "").strip().lower()
                content = str(block.get("block_content", "") or "").strip()
                if not content:
                    continue

                # Format heading levels
                if raw_label == "doc_title":
                    parts.append(f"# {content}")
                elif raw_label in ("paragraph_title",):
                    parts.append(f"## {content}")
                elif raw_label in ("display_formula", "formula"):
                    parts.append(f"$$\n{content}\n$$")
                elif raw_label in ("table",):
                    # block_content for tables may already contain HTML/markdown
                    parts.append(content)
                elif raw_label in ("header", "footer", "number", "aside_text",
                                   "header_image", "footer_image", "image"):
                    # Skip non-content blocks
                    continue
                else:
                    parts.append(content)

            parts.append("")  # page separator (one per physical page)

    result = "\n\n".join(parts).strip()
    logger.info(LogModule.LAYOUT, f"[PADDLE] Built fallback markdown: {len(result)} chars, {len(parts)} blocks")
    return result
