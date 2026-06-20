# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

"""Debug API routes: bbox overlay rendering for layout verification."""

from __future__ import annotations

import io
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import Response

from backend.app.services.task import task_manager
from logger import unified_logger as logger
from logger.logger import LogModule

router = APIRouter()

# ---------------------------------------------------------------------------
# colour palette for drawing block rectangles (loops when exhausted)
# ---------------------------------------------------------------------------
_BLOCK_COLORS: List[Tuple[int, int, int]] = [
    (220, 50, 50),    # red
    (50, 150, 220),   # blue
    (50, 180, 50),    # green
    (220, 160, 20),   # orange
    (160, 50, 200),   # purple
    (20, 180, 180),   # cyan
    (220, 80, 140),   # pink
    (100, 120, 40),   # olive
    (180, 100, 50),   # brown
    (50, 50, 180),    # indigo
]


def _color_for_index(idx: int) -> Tuple[int, int, int]:
    return _BLOCK_COLORS[idx % len(_BLOCK_COLORS)]


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _resolve_layout_document(task_id: str, task_state: Dict[str, Any]):
    """Reuse the same layout resolution as the translation-segments route."""
    from utils.mineru_layout_utils import needs_mineru_zip_restore
    from layout.registry import load_layout_from_engine_zip
    from utils.format_convert_utils import get_layout_block_bbox

    layout_doc = task_state.get("layout_document")
    if layout_doc is not None:
        return layout_doc

    original_filename = str(task_state.get("original_filename") or "")
    if not needs_mineru_zip_restore(original_filename):
        return None

    engine = task_state.get("layout_engine") or task_state.get("convert_engine") or "mineru"
    zip_bytes = task_state.get("layout_source_zip")
    if not zip_bytes:
        return None

    layout_doc = load_layout_from_engine_zip(engine, zip_bytes)
    if layout_doc is not None:
        task_state["layout_document"] = layout_doc
        task_state["layout_block_bbox"] = get_layout_block_bbox(layout_doc)
        logger.info(
            LogModule.ROUTE,
            f"[DEBUG-BBOX] Reloaded layout_document from {engine} ZIP for task {task_id}",
        )
    return layout_doc


def _open_source_image(task_state: Dict[str, Any]) -> Optional["Image.Image"]:
    """Open the source image for the task (raster source or rendered PDF page)."""
    from PIL import Image

    _RASTER_EXTS = {".png", ".jpg", ".jpeg", ".bmp", ".tiff", ".tif", ".webp", ".gif"}

    def _try_raster(path_candidate):
        if not path_candidate or not isinstance(path_candidate, str):
            return None
        p = Path(path_candidate)
        if not p.is_file() or p.suffix.lower() not in _RASTER_EXTS:
            return None
        try:
            return Image.open(p).convert("RGB")
        except Exception:
            return None

    # 1) try raster source image paths
    for key in ("original_file_path", "source_image_path", "converted_file_path"):
        result = _try_raster(task_state.get(key))
        if result is not None:
            return result

    # 2) try rendering page 0 of a PDF source via PyMuPDF
    def _try_pdf(pdf_path_candidate):
        if not pdf_path_candidate or not isinstance(pdf_path_candidate, str):
            return None
        p = Path(pdf_path_candidate)
        if not p.is_file() or p.suffix.lower() != ".pdf":
            return None
        try:
            import fitz
            doc = fitz.open(str(p))
            page = doc[0]
            pix = page.get_pixmap(dpi=144)
            img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
            doc.close()
            return img
        except Exception:
            return None

    for key in ("original_pdf_path", "original_file_path"):
        result = _try_pdf(task_state.get(key))
        if result is not None:
            return result

    return None



# ---------------------------------------------------------------------------
# endpoint
# ---------------------------------------------------------------------------

@router.get("/task/{task_id}/debug/bbox_overlay")
async def debug_bbox_overlay(
    task_id: str,
    page: int = Query(0, ge=0, description="Layout page index to render (0-based)"),
    show_label: bool = Query(True, description="Draw block index labels"),
    show_skipped: bool = Query(True, description="Include skipped blocks (tables/images)"),
):
    """
    Render layout-block bboxes onto the source image for visual debugging.

    Returns a PNG image that can be opened directly in a browser.
    """
    from PIL import Image, ImageDraw, ImageFont

    # ---- load task state ---------------------------------------------------
    task_state = task_manager.get_task(task_id)
    if task_state is None:
        raise HTTPException(status_code=404, detail=f"Task not found: {task_id}")

    # ---- resolve layout ----------------------------------------------------
    layout_doc = _resolve_layout_document(task_id, task_state)
    if layout_doc is None:
        raise HTTPException(
            status_code=404,
            detail="Layout document not available for this task. "
                   "The extraction may still be in progress.",
        )

    page_count = getattr(layout_doc, "page_count", 0) or 0
    pages: List[Any] = getattr(layout_doc, "pages", None) or []
    if page >= len(pages):
        raise HTTPException(
            status_code=400,
            detail=f"Page {page} out of range (0–{len(pages) - 1}, {page_count} pages)",
        )

    # ---- open source image -------------------------------------------------
    source_img = _open_source_image(task_state)
    if source_img is None:
        raise HTTPException(
            status_code=404,
            detail="Source image not available. The task may use an unsupported source format.",
        )

    img_w, img_h = source_img.size

    # ---- collect blocks for the requested page ------------------------------
    layout_page = pages[page]
    page_w = getattr(layout_page, "width", None)
    page_h = getattr(layout_page, "height", None)
    blocks = getattr(layout_page, "blocks", None) or []

    # compute coordinate scale: layout-page coords → image pixels
    if page_w and page_h and page_w > 0 and page_h > 0:
        sx = img_w / float(page_w)
        sy = img_h / float(page_h)
    else:
        sx = sy = 1.0

    draw = ImageDraw.Draw(source_img)

    # try to load a proportional font; fall back to default bitmap font
    try:
        label_font = ImageFont.truetype("arial.ttf", size=12)
    except Exception:
        label_font = ImageFont.load_default()

    drawn = 0
    skipped = 0

    for block in blocks:
        block_idx = getattr(block, "block_index", None)
        block_type = getattr(block, "type", "?")
        bbox_raw = getattr(block, "bbox", None)
        if not bbox_raw or len(bbox_raw) < 4:
            skipped += 1
            continue

        # scale bbox from layout-page coords to image pixels
        x0 = int(round(float(bbox_raw[0]) * sx))
        y0 = int(round(float(bbox_raw[1]) * sy))
        x1 = int(round(float(bbox_raw[2]) * sx))
        y1 = int(round(float(bbox_raw[3]) * sy))

        # clamp to image bounds
        x0 = max(0, min(x0, img_w - 1))
        y0 = max(0, min(y0, img_h - 1))
        x1 = max(x0 + 1, min(x1, img_w))
        y1 = max(y0 + 1, min(y1, img_h))

        should_translate = getattr(block, "should_translate", True)
        if not show_skipped and not should_translate:
            skipped += 1
            continue

        color = _color_for_index(drawn)
        draw.rectangle([x0, y0, x1, y1], outline=color, width=2)

        # label: block index + type
        if show_label:
            label_parts = []
            if block_idx is not None:
                label_parts.append(f"#{block_idx}")
            label_parts.append(block_type)
            if not should_translate:
                label_parts.append("(skip)")
            label = " ".join(label_parts)
            # draw text background for readability
            tb = draw.textbbox((x0 + 2, y0 + 2), label, font=label_font)
            draw.rectangle(
                [tb[0] - 1, tb[1] - 1, tb[2] + 1, tb[3] + 1],
                fill=(255, 255, 255, 200),
            )
            draw.text((x0 + 2, y0 + 2), label, fill=color, font=label_font)

        drawn += 1

    # ---- legend footer -----------------------------------------------------
    legend_h = 22
    legend_lines: List[str] = [
        f"task={task_id}  page={page}/{len(pages) - 1}  "
        f"img={img_w}x{img_h}  "
        f"page_size=({page_w}, {page_h})  "
        f"sx={sx:.4f} sy={sy:.4f}  "
        f"drawn={drawn} skipped={skipped}",
    ]

    # build a wider canvas for the legend
    legend_pad = 6
    try:
        _tw = max(draw.textlength(line, font=label_font) for line in legend_lines)
    except Exception:
        _tw = max(len(line) * 7 for line in legend_lines)
    legend_canvas_h = legend_h
    legend_img = Image.new("RGB", (max(img_w, int(_tw) + legend_pad * 2), legend_canvas_h), (240, 240, 240))
    legend_draw = ImageDraw.Draw(legend_img)
    legend_draw.text((legend_pad, 4), legend_lines[0], fill=(40, 40, 40), font=label_font)

    # stack source + legend
    out_img = Image.new("RGB", (legend_img.width, img_h + legend_canvas_h), (240, 240, 240))
    out_img.paste(source_img, (0, 0))
    out_img.paste(legend_img, (0, img_h))

    buf = io.BytesIO()
    out_img.save(buf, format="PNG")
    buf.seek(0)

    logger.info(
        LogModule.ROUTE,
        f"[DEBUG-BBOX] Rendered {drawn} blocks, skipped {skipped} "
        f"for task={task_id} page={page}",
    )
    return Response(content=buf.getvalue(), media_type="image/png")
