# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0
"""Core Pillow renderer: erase OCR regions and paint translated text."""

from __future__ import annotations

import io
import re
from typing import Any, Callable, Dict, List, Optional, Tuple

from PIL import Image, ImageDraw, ImageFont

from layout.base import LayoutBlock, LayoutDocument, LayoutPage
from layout.image_overlay.debug_output import (
    resolve_image_overlay_debug_dir,
    write_image_overlay_debug,
)
from layout.image_overlay.font_resolver import font_loader_for_family
from layout.image_overlay.models import ImageOverlayConfig, ImageOverlayResult
from layout.image_overlay.segment_overlay import SegmentOverlayDrawItem
from layout.block_types import EQUATION_BLOCK_TYPES, VISUAL_BLOCK_TYPES, IMAGE, TABLE, CHART, LIST, LEGACY_FIGURE
from layout.pdf_renderer.typst_overlay.visual_images import (
    VisualImagePlacement,
    collect_visual_image_placements,
    lookup_image_bytes,
)
from logger.logger import LogModule, unified_logger

_SKIP_TEXT_BLOCK_TYPES = frozenset({IMAGE, LEGACY_FIGURE, LIST})
_CJK_CHAR_RE = re.compile(
    r"[\u4e00-\u9fff\u3400-\u4dbf\u3040-\u30ff\uac00-\ud7af]",
)

_MEDIA_TYPES = {
    "png": "image/png",
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "webp": "image/webp",
    "bmp": "image/bmp",
    "gif": "image/gif",
    "tif": "image/tiff",
    "tiff": "image/tiff",
}


def _normalize_output_extension(output_format: Optional[str], source_path: str) -> str:
    ext = (output_format or "").strip().lower().lstrip(".")
    if not ext:
        ext = source_path.rsplit(".", 1)[-1].lower() if "." in source_path else "png"
    if ext == "jpeg":
        return "jpg"
    return ext


def _normalize_overlay_line_endings(text: str) -> str:
    """Normalize line endings only; keep revision text byte-for-byte otherwise."""
    return (text or "").replace("\r\n", "\n").replace("\r", "\n")


def _plain_overlay_text(text: str) -> str:
    """Return overlay text for raster drawing (WYSIWYG with segment revision)."""
    return _normalize_overlay_line_endings(text)


def _effective_page_dimensions(
    page: Optional[LayoutPage],
    layout_doc: Optional[LayoutDocument] = None,
) -> Tuple[Optional[float], Optional[float]]:
    """Resolve layout page size, inferring from block extents when MinerU omits page_size."""
    if layout_doc is not None:
        from layout.image_overlay.coordinate_space import layout_canvas_dimensions

        canvas_w, canvas_h = layout_canvas_dimensions(layout_doc, page)
        if canvas_w and canvas_h:
            return canvas_w, canvas_h
    if page is None:
        return None, None
    page_w = getattr(page, "width", None)
    page_h = getattr(page, "height", None)
    if page_w and page_h and page_w > 0 and page_h > 0:
        return float(page_w), float(page_h)
    max_x = 0.0
    max_y = 0.0
    for block in page.blocks:
        x0, y0, x1, y1 = block.bbox
        max_x = max(max_x, float(x1), float(x0))
        max_y = max(max_y, float(y1), float(y0))
    if max_x > 1.0 and max_y > 1.0:
        return max_x, max_y
    if page_w and page_w > 0:
        return float(page_w), float(page_h) if page_h else None
    if page_h and page_h > 0:
        return float(page_w) if page_w else None, float(page_h)
    return None, None


def _coord_scale_factors(
    page: Optional[LayoutPage],
    image_size: Tuple[int, int],
    layout_doc: Optional[LayoutDocument] = None,
) -> Tuple[float, float]:
    """Map layout coordinates to raster pixels (MinerU page_size vs actual image pixels)."""
    img_w, img_h = image_size
    page_w, page_h = _effective_page_dimensions(page, layout_doc)
    if not page_w or not page_h or page_w <= 0 or page_h <= 0:
        return 1.0, 1.0
    if abs(page_w - img_w) <= 1 and abs(page_h - img_h) <= 1:
        return 1.0, 1.0
    return img_w / page_w, img_h / page_h


def _overlay_line_count(text: str) -> int:
    """Count visual lines implied by embedded newlines in overlay text."""
    normalized = _plain_overlay_text(text)
    if not normalized:
        return 1
    return max(1, normalized.count("\n") + 1)


def _bbox_font_cap_px(
    scaled_bbox: Tuple[int, int, int, int],
    text: str,
    *,
    fill_ratio: float = 0.90,
) -> float:
    """Max font size (px) so each OCR line fits the raster bbox height."""
    _, y0, _, y1 = scaled_bbox
    bbox_h_px = max(1, y1 - y0)
    return (bbox_h_px / _overlay_line_count(text)) * fill_ratio


def _pt_to_image_px(pt: float, sy: float) -> float:
    return float(pt) * (96.0 / 72.0) * max(sy, 1e-6)


def _image_px_to_pt(px: float, sy: float) -> float:
    """Convert raster overlay font px back to typographic pt (inverse of _pt_to_image_px)."""
    scale = (96.0 / 72.0) * max(sy, 1e-6)
    if scale <= 0:
        return 0.0
    return float(px) / scale


def _user_font_size_px_from_pt(user_pt: float, sy: float) -> float:
    """Map overlay render pt to raster pixels (includes layout->image scale sy)."""
    return _pt_to_image_px(user_pt, sy)


def overlay_render_pt_from_fitted_px(fitted_px: float, sy: float) -> float:
    """Overlay font size shown in UI = typographic pt equivalent of drawn pixel size."""
    from layout.pdf_renderer.typst_overlay.font_fit import USER_FONT_SIZE_PT_MIN

    pt = _image_px_to_pt(float(fitted_px), sy)
    return round(max(USER_FONT_SIZE_PT_MIN, min(72.0, pt)), 1)


def _overlay_fit_padding(bbox_w: int, bbox_h: int) -> Tuple[int, int]:
    padding_x = max(0, int(bbox_w * 0.02))
    padding_y = max(0, int(bbox_h * 0.06)) if bbox_h > 12 else 0
    return padding_x, padding_y


def _mineru_layout_font_size_pt(block: LayoutBlock) -> Optional[float]:
    from layout.mineru_layout_model import _get_max_span_font_size

    raw = getattr(block, "raw", None) or {}
    if not isinstance(raw, dict):
        return None
    span_size = _get_max_span_font_size(raw)
    if span_size > 0:
        return span_size
    for key in ("font_size", "orig_font_size", "inferred_font_size"):
        value = raw.get(key)
        if isinstance(value, (int, float)) and float(value) > 0:
            return float(value)
    return None


def _estimate_overlay_font_size_pt(block: LayoutBlock, text: str) -> Optional[float]:
    from layout.pdf_renderer.typst_overlay.font_fit import (
        FontFitCalculator,
        USER_FONT_SIZE_PT_MIN,
    )
    from layout.pdf_renderer.typst_overlay.models import layout_block_to_render_block

    raw = getattr(block, "raw", None) or {}
    layout_raw = raw if isinstance(raw, dict) else {}
    rb = layout_block_to_render_block(
        block,
        page_index=getattr(block, "page_index", 0) or 0,
        translated_text=text,
    )
    calc = FontFitCalculator(min_size_pt=USER_FONT_SIZE_PT_MIN)
    try:
        fitted = calc.calculate_fit_params(rb, layout_raw=layout_raw)
        if fitted.font_size_pt > 0:
            return float(fitted.font_size_pt)
    except Exception:
        pass
    try:
        return float(calc.estimate_font_size(rb, layout_raw=layout_raw))
    except Exception:
        return None


def _preferred_font_size_px(
    block: Optional[LayoutBlock],
    page: Optional[LayoutPage],
    image_size: Tuple[int, int],
    scaled_bbox: Tuple[int, int, int, int],
    text: str,
    user_pt: Optional[float],
    *,
    layout_pt: Optional[float] = None,
    estimated_pt: Optional[float] = None,
) -> Tuple[float, float]:
    """Return (preferred font px, bbox height cap px) for overlay fitting."""
    _, sy = _coord_scale_factors(page, image_size)
    bbox_cap_px = _bbox_font_cap_px(scaled_bbox, text)
    if user_pt is not None and user_pt > 0:
        from layout.pdf_renderer.typst_overlay.segment_font_metrics import (
            FONT_SIZE_PT_MAX,
            FONT_SIZE_PT_MIN,
        )

        clamped_pt = max(
            FONT_SIZE_PT_MIN,
            min(FONT_SIZE_PT_MAX, float(user_pt)),
        )
        user_px = _user_font_size_px_from_pt(clamped_pt, sy)
        # Manual override: exact user pt in px; height may overflow OCR bbox.
        return user_px, bbox_cap_px

    if layout_pt is None and block is not None:
        layout_pt = _mineru_layout_font_size_pt(block)
    if estimated_pt is None and layout_pt is None and block is not None:
        estimated_pt = _estimate_overlay_font_size_pt(block, text)

    candidates: List[float] = [bbox_cap_px]
    if layout_pt is not None and layout_pt > 0:
        candidates.append(_pt_to_image_px(layout_pt, sy))

    if block is not None:
        _, y0, _, y1 = block.bbox
        layout_line_h_px = max(1.0, float(y1) - float(y0)) * sy
        candidates.append(
            (layout_line_h_px / _overlay_line_count(text)) * 0.88,
        )

    if layout_pt is None and block is not None:
        if estimated_pt is None:
            estimated_pt = _estimate_overlay_font_size_pt(block, text)
        if estimated_pt is not None and estimated_pt > 0:
            candidates.append(_pt_to_image_px(estimated_pt, sy))

    preferred = max(3.0, min(72.0, min(candidates)))
    return preferred, bbox_cap_px


def resolve_layout_page_for_segment(
    layout_doc: Any,
    segment: Dict[str, Any],
    block_indices: Optional[List[Any]] = None,
) -> Optional[LayoutPage]:
    """Pick the layout page used to scale segment bboxes to raster pixels."""
    from layout.base import LayoutDocument

    if not isinstance(layout_doc, LayoutDocument) or not layout_doc.pages:
        return None
    pages = layout_doc.pages
    page_num = segment.get("pdf_page_number")
    if isinstance(page_num, int) and page_num >= 1:
        page_idx = page_num - 1
        if page_idx < len(pages):
            return pages[page_idx]
    indices = block_indices if block_indices is not None else segment.get("layout_block_indices")
    if indices:
        try:
            first_idx = int(indices[0])
        except (TypeError, ValueError, IndexError):
            first_idx = None
        if first_idx is not None:
            for page in pages:
                for block in page.blocks:
                    if block.index == first_idx:
                        return page
    return pages[0]


def scale_layout_bboxes_to_image_pixels(
    bboxes: Any,
    *,
    page: Optional[LayoutPage],
    image_size: Tuple[int, int],
    layout_doc: Optional[LayoutDocument] = None,
) -> List[List[float]]:
    """Map layout-space bbox lists to image pixel coordinates."""
    if not isinstance(bboxes, list) or not bboxes:
        return []
    scaled: List[List[float]] = []
    for entry in bboxes:
        if not isinstance(entry, (list, tuple)) or len(entry) < 4:
            continue
        try:
            layout_bbox = tuple(float(v) for v in entry[:4])
        except (TypeError, ValueError):
            continue
        left, top, right, bottom = _scale_bbox_to_image(
            layout_bbox,
            page,
            image_size,
            layout_doc=layout_doc,
        )
        scaled.append([float(left), float(top), float(right), float(bottom)])
    return scaled


def transform_segment_bboxes_to_image_pixels(
    segment: Dict[str, Any],
    *,
    layout_doc: Any,
    image_size: Tuple[int, int],
) -> bool:
    """Map segment layout_block_bbox from layout canvas to source raster pixels (idempotent)."""
    from layout.image_overlay.coordinate_space import (
        COORDINATE_SPACE_IMAGE_PX,
        clamp_bbox_to_image_pixels,
        clear_segment_bbox_image_mapping,
        segment_bbox_exceeds_image_size,
        segment_bbox_mapped_to_image_size,
    )

    if segment_bbox_mapped_to_image_size(segment, image_size):
        if not segment_bbox_exceeds_image_size(segment, image_size):
            raw_bboxes = segment.get("layout_block_bbox")
            if not isinstance(raw_bboxes, list):
                return False
            clamped: List[Any] = []
            changed = False
            for entry in raw_bboxes:
                fixed = clamp_bbox_to_image_pixels(entry, image_size)
                if fixed is not None:
                    clamped.append(fixed)
                    if fixed != list(entry)[:4]:
                        changed = True
            if clamped:
                segment["layout_block_bbox"] = clamped
            return changed
        unified_logger.warning(
            LogModule.LAYOUT,
            "[IMAGE_OVERLAY] Segment bbox exceeds reference image "
            f"{image_size[0]}x{image_size[1]} despite cached mapping; remapping",
        )
        clear_segment_bbox_image_mapping(segment)
    raw_bboxes = segment.get("layout_block_bbox")
    if not raw_bboxes:
        return False

    page = resolve_layout_page_for_segment(layout_doc, segment)
    sx, sy = _coord_scale_factors(page, image_size, layout_doc)
    scaled = scale_layout_bboxes_to_image_pixels(
        raw_bboxes,
        page=page,
        image_size=image_size,
        layout_doc=layout_doc,
    )
    if not scaled:
        return False
    segment["layout_block_bbox"] = scaled
    segment["layout_block_bbox_space"] = COORDINATE_SPACE_IMAGE_PX
    segment["layout_block_bbox_image_size"] = [int(image_size[0]), int(image_size[1])]
    if abs(sx - 1.0) > 0.001 or abs(sy - 1.0) > 0.001:
        from layout.image_overlay.coordinate_space import layout_coordinate_space

        unified_logger.debug(
            LogModule.LAYOUT,
            f"[IMAGE_OVERLAY] Mapped segment bbox to source image "
            f"{image_size[0]}x{image_size[1]} "
            f"(layout_space={layout_coordinate_space(layout_doc)}, "
            f"sx={sx:.4f}, sy={sy:.4f})",
        )
    return True


def _scale_bbox_to_image(
    bbox: Tuple[float, float, float, float],
    page: Optional[LayoutPage],
    image_size: Tuple[int, int],
    *,
    layout_doc: Optional[LayoutDocument] = None,
) -> Tuple[int, int, int, int]:
    x0, y0, x1, y1 = bbox
    img_w, img_h = image_size
    sx, sy = _coord_scale_factors(page, image_size, layout_doc)
    if sx != 1.0 or sy != 1.0:
        x0, x1 = x0 * sx, x1 * sx
        y0, y1 = y0 * sy, y1 * sy
    # Clamp to image bounds, guaranteeing at least 1 px width/height
    left = max(0, min(int(round(min(x0, x1))), img_w - 1))
    top = max(0, min(int(round(min(y0, y1))), img_h - 1))
    right = max(left + 1, min(img_w, int(round(max(x0, x1)))))
    bottom = max(top + 1, min(img_h, int(round(max(y0, y1)))))
    return left, top, right, bottom


def _pixel_luminance(rgb: Tuple[int, int, int]) -> float:
    r, g, b = rgb
    return 0.299 * r + 0.587 * g + 0.114 * b


def _mean_rgb(samples: List[Tuple[int, int, int]]) -> Optional[Tuple[int, int, int]]:
    if not samples:
        return None
    r = sum(c[0] for c in samples) // len(samples)
    g = sum(c[1] for c in samples) // len(samples)
    b = sum(c[2] for c in samples) // len(samples)
    return (r, g, b)


def _sample_vertical_side_strip(
    pixels,
    *,
    x_start: int,
    x_end: int,
    y0: int,
    y1: int,
    img_w: int,
    img_h: int,
) -> List[Tuple[int, int, int]]:
    """Collect RGB samples from a vertical strip [x_start, x_end) x [y0, y1)."""
    if x_end <= x_start or y1 <= y0:
        return []
    samples: List[Tuple[int, int, int]] = []
    x_lo = max(0, x_start)
    x_hi = min(img_w, x_end)
    y_lo = max(0, y0)
    y_hi = min(img_h, y1)
    for x in range(x_lo, x_hi):
        for y in range(y_lo, y_hi):
            samples.append(pixels[x, y][:3])
    return samples


def _pick_cover_color_from_samples(
    samples: List[Tuple[int, int, int]],
    mode: str,
) -> Optional[Tuple[int, int, int]]:
    """Pick RGB from strip pixels: max/min by luminance, or mean of all pixels."""
    if not samples:
        return None
    if mode == "avg":
        return _mean_rgb(samples)
    use_min = mode == "min"
    best = samples[0]
    best_lum = _pixel_luminance(best)
    for rgb in samples[1:]:
        lum = _pixel_luminance(rgb)
        if use_min:
            if lum < best_lum:
                best = rgb
                best_lum = lum
        elif lum > best_lum:
            best = rgb
            best_lum = lum
    return best


def _sample_cover_color(
    image: Image.Image,
    bbox: Tuple[int, int, int, int],
    mode: str = "max",
) -> Tuple[int, int, int]:
    """Estimate background fill from left/right strip pixels (max, min, or avg)."""
    img_w, img_h = image.size
    x0, y0, x1, y1 = bbox
    strip_w = 3
    rgb = image.convert("RGB")
    pixels = rgb.load()

    left_samples = _sample_vertical_side_strip(
        pixels,
        x_start=x0 - strip_w,
        x_end=x0,
        y0=y0,
        y1=y1,
        img_w=img_w,
        img_h=img_h,
    )
    right_samples = _sample_vertical_side_strip(
        pixels,
        x_start=x1,
        x_end=x1 + strip_w,
        y0=y0,
        y1=y1,
        img_w=img_w,
        img_h=img_h,
    )

    picked = _pick_cover_color_from_samples(left_samples + right_samples, mode)
    if picked:
        return picked
    return (255, 255, 255)


def _erase_region(
    draw: ImageDraw.ImageDraw,
    bbox: Tuple[int, int, int, int],
    fill_rgb: Tuple[int, int, int],
    margin_px: float,
) -> None:
    x0, y0, x1, y1 = bbox
    if x0 >= x1 or y0 >= y1:
        from logger import unified_logger as _log
        _log.warning(
            "[IMAGE_OVERLAY] Skipping erase_region with invalid bbox: "
            f"({x0}, {y0}, {x1}, {y1}) — width={x1 - x0}, height={y1 - y0}",
        )
        return
    m = max(0.0, margin_px)
    draw.rectangle(
        (x0 - m, y0 - m, x1 + m, y1 + m),
        fill=fill_rgb,
    )


def _should_wrap_by_character(text: str) -> bool:
    stripped = text.strip()
    if not stripped:
        return False
    if " " not in stripped:
        return True
    cjk_count = len(_CJK_CHAR_RE.findall(stripped))
    return cjk_count >= max(1, int(len(stripped) * 0.35))


def _wrap_characters(
    text: str,
    font: ImageFont.ImageFont,
    max_width: int,
    draw: ImageDraw.ImageDraw,
) -> List[str]:
    lines: List[str] = []
    current = ""
    for ch in text:
        candidate = f"{current}{ch}"
        if draw.textlength(candidate, font=font) <= max_width:
            current = candidate
            continue
        if current:
            lines.append(current)
        current = ch
    if current:
        lines.append(current)
    return lines


def _wrap_paragraph_for_bbox(
    text: str,
    font: ImageFont.ImageFont,
    max_width: int,
    draw: ImageDraw.ImageDraw,
) -> List[str]:
    if _should_wrap_by_character(text):
        return _wrap_characters(text, font, max_width, draw)
    return _wrap_words(text, font, max_width, draw)


def _wrap_text_for_bbox(
    text: str,
    font: ImageFont.ImageFont,
    max_width: int,
    draw: ImageDraw.ImageDraw,
) -> List[str]:
    if "\n" not in text:
        return _wrap_paragraph_for_bbox(text, font, max_width, draw)
    lines: List[str] = []
    for paragraph in text.split("\n"):
        if not paragraph:
            lines.append("")
            continue
        lines.extend(_wrap_paragraph_for_bbox(paragraph, font, max_width, draw))
    return lines


def _wrap_words(text: str, font: ImageFont.ImageFont, max_width: int, draw: ImageDraw.ImageDraw) -> List[str]:
    words = text.split()
    if not words:
        return []
    lines: List[str] = []
    current = words[0]
    for word in words[1:]:
        candidate = f"{current} {word}"
        if draw.textlength(candidate, font=font) <= max_width:
            current = candidate
        else:
            lines.append(current)
            current = word
    lines.append(current)
    return lines


def _measure_wrapped_text(
    lines: List[str],
    font: ImageFont.ImageFont,
    draw: ImageDraw.ImageDraw,
) -> Tuple[int, int]:
    if not lines:
        return 0, 0
    ascent, descent = font.getmetrics()
    line_h = ascent + descent
    max_w = max(int(draw.textlength(line, font=font)) for line in lines)
    return max_w, line_h * len(lines)


def _fit_text_lines(
    draw: ImageDraw.ImageDraw,
    text: str,
    bbox: Tuple[int, int, int, int],
    font_loader: Callable[[int], ImageFont.ImageFont],
    config: ImageOverlayConfig,
    preferred_size_px: Optional[float] = None,
    *,
    font_size_locked: bool = False,
) -> Tuple[ImageFont.ImageFont, List[str], int]:
    x0, y0, x1, y1 = bbox
    max_w = max(1, x1 - x0)
    max_h = max(1, y1 - y0)
    min_size = max(1, min(int(config.min_font_size_px), int(max_h * 0.98)))
    if font_size_locked and preferred_size_px is not None and preferred_size_px > 0:
        locked_size = max(1, int(round(preferred_size_px)))
        font = font_loader(locked_size)
        lines = _wrap_text_for_bbox(text, font, max_w, draw)
        return font, lines, locked_size
    bbox_max = max(min_size, int(max_h * 0.95))
    if preferred_size_px is not None and preferred_size_px > 0:
        max_size = max(min_size, min(bbox_max, int(round(preferred_size_px))))
    else:
        max_size = max(min_size, min(int(config.max_font_size_px), bbox_max))
    best_font = font_loader(min_size)
    best_lines: List[str] = []
    lo, hi = min_size, max_size
    while lo <= hi:
        mid = (lo + hi) // 2
        font = font_loader(mid)
        lines = _wrap_text_for_bbox(text, font, max_w, draw)
        _, total_h = _measure_wrapped_text(lines, font, draw)
        if total_h <= max_h:
            best_font = font
            best_lines = lines
            lo = mid + 1
        else:
            hi = mid - 1
    if not best_lines:
        for size in range(max_size, 0, -1):
            font = font_loader(size)
            lines = _wrap_text_for_bbox(text, font, max_w, draw)
            _, total_h = _measure_wrapped_text(lines, font, draw)
            if total_h <= max_h:
                return font, lines, size
        best_font = font_loader(min_size)
        best_lines = _wrap_text_for_bbox(text, best_font, max_w, draw)
        return best_font, best_lines, min_size
    fitted_size = max(lo - 1, min_size)
    return best_font, best_lines, fitted_size


def _draw_text_in_bbox(
    draw: ImageDraw.ImageDraw,
    text: str,
    bbox: Tuple[int, int, int, int],
    font_loader: Callable[[int], ImageFont.ImageFont],
    config: ImageOverlayConfig,
    preferred_size_px: Optional[float] = None,
    *,
    bold: bool = False,
    font_size_locked: bool = False,
) -> Tuple[int, int]:
    plain = _plain_overlay_text(text)
    if not plain.strip():
        return 0, 0
    x0, y0, x1, y1 = bbox
    max_w = max(1, x1 - x0)
    bbox_h = max(1, y1 - y0)
    padding_x, padding_y = _overlay_fit_padding(max_w, bbox_h)
    fit_bbox = (x0, y0 + padding_y, x1 - padding_x, y1)
    font, lines, fitted_size_px = _fit_text_lines(
        draw,
        plain,
        fit_bbox,
        font_loader,
        config,
        preferred_size_px=preferred_size_px,
        font_size_locked=font_size_locked,
    )
    start_y = y0 + padding_y
    for idx, line in enumerate(lines):
        line_x = x0 + padding_x
        line_y = start_y + idx * (font.getmetrics()[0] + font.getmetrics()[1])
        draw.text(
            (line_x, line_y),
            line,
            fill=config.text_color_rgb,
            font=font,
        )
    return fitted_size_px, len(lines)


def dry_run_overlay_font_size_pt(
    block: LayoutBlock,
    text: str,
    page: Optional[LayoutPage],
    image_size: Tuple[int, int],
    config: Optional[ImageOverlayConfig] = None,
    *,
    user_pt: Optional[float] = None,
    font_family: str = "Calibri",
    bold: bool = False,
) -> Optional[float]:
    """Return overlay render pt (px_to_pt of fitted size) matching production render."""
    plain = _plain_overlay_text(text)
    if not plain.strip():
        return None

    cfg = config or ImageOverlayConfig()
    bbox = _scale_bbox_to_image(block.bbox, page, image_size)
    x0, y0, x1, y1 = bbox
    dummy = Image.new("RGB", image_size, "white")
    draw = ImageDraw.Draw(dummy)
    font_loader = font_loader_for_family(font_family, bold=bold)
    mineru_pt = _mineru_layout_font_size_pt(block)
    estimated_pt = _estimate_overlay_font_size_pt(block, text)
    preferred_px, _ = _preferred_font_size_px(
        block,
        page,
        image_size,
        bbox,
        text,
        user_pt,
        layout_pt=mineru_pt,
        estimated_pt=estimated_pt,
    )
    _, _, fitted_px = _fit_text_lines(
        draw,
        plain,
        (x0, y0, x1, y1),
        font_loader,
        cfg,
        preferred_size_px=preferred_px,
        font_size_locked=user_pt is not None and user_pt > 0,
    )
    _, sy = _coord_scale_factors(page, image_size)
    return overlay_render_pt_from_fitted_px(float(fitted_px), sy)


def _segment_layout_bbox_to_image(
    bbox: Tuple[float, float, float, float],
    layout_doc: LayoutDocument,
    page: Optional[LayoutPage],
    image_size: Tuple[int, int],
    *,
    bbox_space: Optional[str] = None,
) -> Tuple[int, int, int, int]:
    """Map a segment layout bbox to source raster pixel coordinates."""
    from layout.image_overlay.coordinate_space import COORDINATE_SPACE_IMAGE_PX

    if bbox_space == COORDINATE_SPACE_IMAGE_PX:
        img_w, img_h = image_size
        x0, y0, x1, y1 = bbox
        left = max(0, min(int(round(min(x0, x1))), img_w - 1))
        top = max(0, min(int(round(min(y0, y1))), img_h - 1))
        right = max(left + 1, min(img_w, int(round(max(x0, x1)))))
        bottom = max(top + 1, min(img_h, int(round(max(y0, y1)))))
        return left, top, right, bottom
    return _scale_bbox_to_image(bbox, page, image_size, layout_doc=layout_doc)


def _should_render_text_block(block: LayoutBlock, config: ImageOverlayConfig) -> bool:
    if block.type in _SKIP_TEXT_BLOCK_TYPES:
        return False
    if block.type == "table" and (config.table_body_format or "html").lower() == "image":
        return False
    if block.type == "chart" and (config.chart_body_format or "image").lower() == "image":
        return False
    if block.type in EQUATION_BLOCK_TYPES and (config.equation_format or "text").lower() == "image":
        return False
    return True


def _paste_visual_placement(
    canvas: Image.Image,
    placement: VisualImagePlacement,
    image_data_map: Dict[str, bytes],
    layout_doc: LayoutDocument,
) -> bool:
    payload = lookup_image_bytes(image_data_map, placement.image_path)
    if not payload:
        return False
    try:
        overlay = Image.open(io.BytesIO(payload)).convert("RGBA")
    except Exception:
        return False
    page = layout_doc.get_page(placement.page_index)
    bbox = _scale_bbox_to_image(
        placement.inner_bbox, page, canvas.size, layout_doc=layout_doc,
    )
    x0, y0, x1, y1 = bbox
    target_w = max(1, x1 - x0)
    target_h = max(1, y1 - y0)
    resized = overlay.resize((target_w, target_h), Image.Resampling.LANCZOS)
    if canvas.mode != "RGBA":
        canvas.paste(resized, (x0, y0), resized if resized.mode == "RGBA" else None)
    else:
        canvas.alpha_composite(resized, (x0, y0))
    return True


class ImageOverlayRenderer:
    """Paint translated text and optional visual assets onto a raster canvas."""

    def render(
        self,
        canvas: Image.Image,
        layout_doc: LayoutDocument,
        block_text_map: Dict[int, str],
        config: ImageOverlayConfig,
        *,
        image_data_map: Optional[Dict[str, bytes]] = None,
        font_family: str = "Calibri",
        font_size_by_block_index: Optional[Dict[int, float]] = None,
        font_weight_by_block_index: Optional[Dict[int, str]] = None,
        temp_dir: Optional[str] = None,
        task_id: str = "",
        source_image_path: str = "",
        block_segment_meta: Optional[Dict[int, Dict[str, Any]]] = None,
        segment_overlay_items: Optional[List[SegmentOverlayDrawItem]] = None,
    ) -> ImageOverlayResult:
        draw = ImageDraw.Draw(canvas)
        image_data_map = image_data_map or {}
        font_loader = font_loader_for_family(font_family)
        font_size_by_block_index = font_size_by_block_index or {}
        font_weight_by_block_index = font_weight_by_block_index or {}
        block_segment_meta = block_segment_meta or {}

        first_page = layout_doc.pages[0] if layout_doc.pages else None
        coord_scale = _coord_scale_factors(first_page, canvas.size, layout_doc)
        page_dimensions = (
            _effective_page_dimensions(first_page, layout_doc) if first_page else (None, None)
        )

        if first_page and (coord_scale[0] != 1.0 or coord_scale[1] != 1.0):
            page_w, page_h = page_dimensions
            unified_logger.info(
                LogModule.RESTOR,
                "[IMAGE_OVERLAY] Layout->image coord scale "
                f"sx={coord_scale[0]:.4f} sy={coord_scale[1]:.4f} "
                f"(page={page_w}x{page_h}, image={canvas.width}x{canvas.height})",
            )

        drawn_debug: List[Dict[str, object]] = []
        skipped_debug: List[Dict[str, object]] = []

        visual_blocks: set[int] = set()
        visual_count = 0
        placements = collect_visual_image_placements(
            layout_doc,
            chart_body_format=config.chart_body_format,
            table_body_format=config.table_body_format,
            equation_format=config.equation_format,
            image_data_map=image_data_map,
        )
        for placement in placements:
            visual_blocks.add(placement.block_index)
            if config.erase_original_text:
                page = layout_doc.get_page(placement.page_index)
                bbox = _scale_bbox_to_image(
                    placement.inner_bbox, page, canvas.size, layout_doc=layout_doc,
                )
                fill = _sample_cover_color(canvas, bbox, config.cover_color_mode)
                _erase_region(draw, bbox, fill, config.cover_margin_px)
            if _paste_visual_placement(canvas, placement, image_data_map, layout_doc):
                visual_count += 1

        text_count = 0
        if segment_overlay_items:
            page = first_page
            for item in segment_overlay_items:
                if not (item.text or "").strip():
                    continue
                bbox = _segment_layout_bbox_to_image(
                    item.layout_bbox,
                    layout_doc,
                    page,
                    canvas.size,
                )
                if config.erase_original_text:
                    fill = _sample_cover_color(canvas, bbox, config.cover_color_mode)
                    _erase_region(draw, bbox, fill, config.cover_margin_px)
                user_pt = item.user_font_size_pt
                preferred_px, bbox_cap_px = _preferred_font_size_px(
                    None,
                    page,
                    canvas.size,
                    bbox,
                    item.text,
                    user_pt,
                    layout_pt=None,
                    estimated_pt=None,
                )
                bold = (item.font_weight or "regular") == "bold"
                block_font_loader = font_loader_for_family(font_family, bold=bold) if bold else font_loader
                plain_text = _plain_overlay_text(item.text)
                user_font_locked = user_pt is not None and user_pt > 0
                fitted_size_px, line_count = _draw_text_in_bbox(
                    draw,
                    item.text,
                    bbox,
                    block_font_loader,
                    config,
                    preferred_size_px=preferred_px,
                    bold=bold,
                    font_size_locked=user_font_locked,
                )
                _, sy = _coord_scale_factors(page, canvas.size, layout_doc)
                render_font_size_pt = overlay_render_pt_from_fitted_px(
                    float(fitted_size_px), sy,
                )
                drawn_debug.append(
                    {
                        "segment_index": item.segment_index,
                        "block_type": "segment_overlay",
                        "page_index": page.page_index if page else 0,
                        "layout_bbox": [float(v) for v in item.layout_bbox],
                        "image_bbox": list(bbox),
                        "overlay_text": item.text,
                        "plain_text": plain_text,
                        "user_font_size_pt": user_pt,
                        "bbox_font_cap_px": round(bbox_cap_px, 2),
                        "preferred_font_size_px": round(preferred_px, 2),
                        "fitted_font_size_px": fitted_size_px,
                        "render_font_size_pt": render_font_size_pt,
                        "line_count": line_count,
                        "font_bold": bold,
                        "coord_scale_sx": coord_scale[0],
                        "coord_scale_sy": coord_scale[1],
                    }
                )
                text_count += 1
        else:
            for block in layout_doc.iter_blocks():
                if block.index is None:
                    continue
                if block.index in visual_blocks:
                    skipped_debug.append(
                        {
                            "block_index": block.index,
                            "block_type": block.type,
                            "page_index": block.page_index,
                            "reason": "visual_placement",
                            "layout_bbox": list(block.bbox),
                            "layout_text": (block.text or "").strip(),
                        }
                    )
                    continue
                if not _should_render_text_block(block, config):
                    skipped_debug.append(
                        {
                            "block_index": block.index,
                            "block_type": block.type,
                            "page_index": block.page_index,
                            "reason": "block_type_or_format",
                            "layout_bbox": list(block.bbox),
                            "layout_text": (block.text or "").strip(),
                        }
                    )
                    continue
                text = block_text_map.get(block.index) or ""
                if not text.strip():
                    skipped_debug.append(
                        {
                            "block_index": block.index,
                            "block_type": block.type,
                            "page_index": block.page_index,
                            "reason": "no_overlay_text",
                            "layout_bbox": list(block.bbox),
                            "layout_text": (block.text or "").strip(),
                        }
                    )
                    continue
                page = layout_doc.get_page(block.page_index)
                bbox = _scale_bbox_to_image(
                    block.bbox, page, canvas.size, layout_doc=layout_doc,
                )
                if config.erase_original_text:
                    fill = _sample_cover_color(canvas, bbox, config.cover_color_mode)
                    _erase_region(draw, bbox, fill, config.cover_margin_px)
                user_pt = font_size_by_block_index.get(block.index)
                mineru_pt = _mineru_layout_font_size_pt(block)
                estimated_pt = _estimate_overlay_font_size_pt(block, text)
                preferred_px, bbox_cap_px = _preferred_font_size_px(
                    block,
                    page,
                    canvas.size,
                    bbox,
                    text,
                    user_pt,
                    layout_pt=mineru_pt,
                    estimated_pt=estimated_pt,
                )
                bold = (font_weight_by_block_index.get(block.index) or "regular") == "bold"
                block_font_loader = font_loader_for_family(font_family, bold=bold) if bold else font_loader
                plain_text = _plain_overlay_text(text)
                segment_meta = block_segment_meta.get(block.index) or {}
                user_font_locked = user_pt is not None and user_pt > 0
                fitted_size_px, line_count = _draw_text_in_bbox(
                    draw,
                    text,
                    bbox,
                    block_font_loader,
                    config,
                    preferred_size_px=preferred_px,
                    bold=bold,
                    font_size_locked=user_font_locked,
                )
                _, sy = _coord_scale_factors(page, canvas.size, layout_doc)
                render_font_size_pt = overlay_render_pt_from_fitted_px(
                    float(fitted_size_px), sy,
                )
                drawn_debug.append(
                    {
                        "block_index": block.index,
                        "block_type": block.type,
                        "page_index": block.page_index,
                        "layout_bbox": [float(v) for v in block.bbox],
                        "image_bbox": list(bbox),
                        "layout_text": (block.text or "").strip(),
                        "overlay_text": text,
                        "plain_text": plain_text,
                        "source_segment_index": segment_meta.get("source_segment_index"),
                        "segment_layout_block_indices": segment_meta.get("layout_block_indices"),
                        "segment_text_block_indices": segment_meta.get("text_block_indices"),
                        "resolution_method": segment_meta.get("resolution_method"),
                        "matched_source_text": segment_meta.get("matched_source_text"),
                        "mineru_font_size_pt": mineru_pt,
                        "user_font_size_pt": user_pt,
                        "estimated_font_size_pt": estimated_pt,
                        "bbox_font_cap_px": round(bbox_cap_px, 2),
                        "preferred_font_size_px": round(preferred_px, 2),
                        "fitted_font_size_px": fitted_size_px,
                        "render_font_size_pt": render_font_size_pt,
                        "line_count": line_count,
                        "font_bold": bold,
                        "coord_scale_sx": coord_scale[0],
                        "coord_scale_sy": coord_scale[1],
                    }
                )
                text_count += 1

        debug_dir = resolve_image_overlay_debug_dir(temp_dir)
        if debug_dir is not None:
            try:
                json_path, txt_path = write_image_overlay_debug(
                    debug_dir,
                    task_id=task_id,
                    source_image_path=source_image_path,
                    image_size=canvas.size,
                    output_format=config.output_format,
                    page_dimensions=page_dimensions,
                    coord_scale=coord_scale,
                    drawn_blocks=drawn_debug,
                    skipped_blocks=skipped_debug,
                )
                if json_path:
                    unified_logger.info(
                        LogModule.RESTOR,
                        f"[IMAGE_OVERLAY] Wrote overlay debug to {json_path}"
                        + (f" and {txt_path}" if txt_path else ""),
                    )
            except Exception as debug_err:
                unified_logger.warning(
                    LogModule.EXPORT,
                    f"[IMAGE_OVERLAY] Debug output skipped (export continues): {debug_err}",
                )

        unified_logger.info(
            LogModule.RESTOR,
            f"[IMAGE_OVERLAY] Drew {text_count} text block(s), {visual_count} visual placement(s)",
        )
        return ImageOverlayResult(
            image_bytes=b"",
            media_type="",
            file_extension="",
            width=canvas.width,
            height=canvas.height,
            text_blocks_drawn=text_count,
            visual_placements_drawn=visual_count,
        )

    def encode_image(
        self,
        canvas: Image.Image,
        source_path: str,
        config: ImageOverlayConfig,
    ) -> ImageOverlayResult:
        ext = _normalize_output_extension(config.output_format, source_path)
        media_type = _MEDIA_TYPES.get(ext, "application/octet-stream")
        buf = io.BytesIO()
        save_image = canvas
        if ext in {"jpg", "jpeg"} and canvas.mode in {"RGBA", "LA", "P"}:
            save_image = canvas.convert("RGB")
        save_kwargs = {}
        if ext in {"jpg", "jpeg"}:
            save_kwargs["quality"] = max(50, min(100, int(config.jpeg_quality)))
            save_kwargs["optimize"] = True
        elif ext == "png":
            save_kwargs["optimize"] = True
        save_image.save(buf, format=ext.upper() if ext != "jpg" else "JPEG", **save_kwargs)
        payload = buf.getvalue()
        return ImageOverlayResult(
            image_bytes=payload,
            media_type=media_type,
            file_extension=ext,
            width=canvas.width,
            height=canvas.height,
        )
