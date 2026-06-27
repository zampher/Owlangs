# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0
"""
Generate and validate MinerU PNG/JPG image overlay from a layout.json fixture.

Usage (from repo root):

  python -m backend.tools.test_png_mineru_overlay \\
      --layout-json test/png/layout.json \\
      --source-image path/to/source.jpg

If --source-image is omitted, the tool searches next to layout.json for *.jpg/*.png.
When no raster is found, a synthetic 309x910 white canvas is used (--allow-synthetic).

Outputs under test/png/output/ (or --output-dir):
  - overlay.jpg
  - overlay_blocks.json / overlay_blocks.txt
  - segments.json
  - validation_report.json
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

_REPO_ROOT = Path(__file__).resolve().parents[2]
_BACKEND = Path(__file__).resolve().parents[1]
for _path in (str(_REPO_ROOT), str(_BACKEND)):
    if _path not in sys.path:
        sys.path.insert(0, _path)

from layout.image_overlay.block_text_map import (  # noqa: E402
    _HTML_TAG_RE,
    _resolve_table_block_html,
)
from layout.image_overlay.models import ImageOverlayConfig, ImageOverlayInput  # noqa: E402
from layout.image_overlay.pipeline import ImageOverlayPipeline  # noqa: E402
from layout.image_overlay.segment_overlay import should_use_segment_direct_overlay  # noqa: E402
from layout.mineru_layout_model import parse_layout_json  # noqa: E402
from utils.markdown_splitter import split_markdown_text  # noqa: E402

DEFAULT_LAYOUT_JSON = _REPO_ROOT / "test" / "png" / "layout.json"
DEFAULT_OUTPUT_DIR = _REPO_ROOT / "test" / "png" / "output"
DEFAULT_IMAGE_SIZE = (309, 910)
_IMAGE_NAME_RE = re.compile(r"\.(jpg|jpeg|png|webp|bmp|tif|tiff)$", re.IGNORECASE)


@dataclass
class OverlayValidationResult:
    passed: bool
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    metrics: Dict[str, Any] = field(default_factory=dict)


def _strip_html(text: str) -> str:
    return _HTML_TAG_RE.sub("", text or "").strip()


def _table_block_index(layout_doc) -> int:
    for block in layout_doc.iter_blocks():
        if block.type == "table" and block.index is not None:
            return int(block.index)
    raise ValueError("layout.json must contain exactly one table block")


def build_segments_from_mineru_table_html(
    table_html: str,
    *,
    table_block_index: int = 0,
    chunk_size: int = 8000,
    target_prefix: str = "[ZH] ",
) -> List[Dict[str, Any]]:
    """
    Build translation-like segments from MinerU table HTML (same split as full.md deep_split).
    """
    chunks = split_markdown_text(table_html, max_block_size=chunk_size, deep_split=True)
    segments: List[Dict[str, Any]] = []
    for idx, chunk in enumerate(chunks):
        source = chunk.strip()
        if not source:
            continue
        plain = _strip_html(source)
        target = f"{target_prefix}{plain}" if plain else target_prefix.rstrip()
        segments.append(
            {
                "segment_index": idx,
                "source_text": source,
                "target_text": target,
                "layout_block_indices": [table_block_index],
            }
        )
    return segments


def _extract_embedded_image_name(layout_doc) -> Optional[str]:
    for block in layout_doc.iter_blocks():
        raw = getattr(block, "raw", None) or {}
        if not isinstance(raw, dict):
            continue
        for nested in raw.get("blocks") or []:
            if not isinstance(nested, dict):
                continue
            for line in nested.get("lines") or []:
                if not isinstance(line, dict):
                    continue
                for span in line.get("spans") or []:
                    if not isinstance(span, dict):
                        continue
                    image_path = span.get("image_path")
                    if isinstance(image_path, str) and image_path.strip():
                        return image_path.strip()
    return None


def resolve_source_image(
    layout_json: Path,
    source_image: Optional[Path],
    *,
    allow_synthetic: bool,
) -> Tuple[Path, bool]:
    """Return (image_path, is_synthetic)."""
    if source_image is not None:
        path = source_image.expanduser().resolve()
        if not path.is_file():
            raise FileNotFoundError(f"Source image not found: {path}")
        return path, False

    layout_dir = layout_json.parent
    for pattern in ("*.jpg", "*.jpeg", "*.png", "*.webp"):
        matches = sorted(layout_dir.glob(pattern))
        if matches:
            return matches[0].resolve(), False

    embedded = None
    try:
        layout_doc = parse_layout_json(layout_json)
        embedded = _extract_embedded_image_name(layout_doc)
    except Exception:
        embedded = None
    if embedded:
        for candidate in (
            layout_dir / embedded,
            layout_dir / "images" / Path(embedded).name,
            layout_dir / Path(embedded).name,
        ):
            if candidate.is_file():
                return candidate.resolve(), False

    if not allow_synthetic:
        raise FileNotFoundError(
            "No source image found. Pass --source-image or place a JPG/PNG next to layout.json, "
            "or use --allow-synthetic for bbox-only validation."
        )

    from PIL import Image

    synthetic_path = layout_dir / "_synthetic_source.jpg"
    synthetic_path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", DEFAULT_IMAGE_SIZE, color=(255, 255, 255)).save(
        synthetic_path,
        format="JPEG",
        quality=95,
    )
    return synthetic_path.resolve(), True


def validate_overlay_result(
    segments: Sequence[Dict[str, Any]],
    layout_doc,
    *,
    image_size: Tuple[int, int],
    drawn_count: int,
    debug_payload: Optional[Dict[str, Any]] = None,
) -> OverlayValidationResult:
    """Run structural checks on segment bboxes and overlay debug output."""
    result = OverlayValidationResult(passed=True)
    page = layout_doc.pages[0] if layout_doc.pages else None
    page_w = float(page.width) if page and page.width else 111.0
    page_h = float(page.height) if page and page.height else 327.0

    subdivided = sum(
        1
        for seg in segments
        if isinstance(seg.get("layout_block_bbox"), list) and seg.get("layout_block_bbox")
    )
    overlay_items_count = sum(
        1
        for seg in segments
        if (seg.get("target_text") or "").strip()
        and isinstance(seg.get("layout_block_bbox"), list)
        and seg.get("layout_block_bbox")
    )

    result.metrics["segment_count"] = len(segments)
    result.metrics["bbox_subdivided_count"] = subdivided
    result.metrics["overlay_draw_items"] = overlay_items_count
    result.metrics["renderer_drawn_count"] = drawn_count
    result.metrics["image_size"] = list(image_size)
    result.metrics["layout_page_size"] = [page_w, page_h]

    if not should_use_segment_direct_overlay(layout_doc):
        result.errors.append("layout is not a single-table image layout")
    if subdivided < 2:
        result.errors.append(
            f"expected bbox subdivision for >=2 segments, got {subdivided}"
        )
    if overlay_items_count < 2:
        result.errors.append(
            f"expected >=2 overlay draw items, got {overlay_items_count}"
        )
    if drawn_count < 1:
        result.errors.append(f"renderer drew 0 text blocks (drawn_count={drawn_count})")

    bboxes_with_text: List[Tuple[int, Tuple[float, float, float, float], str]] = []
    for seg in segments:
        raw_bbox = seg.get("layout_block_bbox")
        if not isinstance(raw_bbox, list) or not raw_bbox:
            continue
        first = raw_bbox[0]
        if not isinstance(first, (list, tuple)) or len(first) < 4:
            continue
        try:
            bbox = tuple(float(v) for v in first[:4])
        except (TypeError, ValueError):
            continue
        bboxes_with_text.append(
            (int(seg.get("segment_index", -1)), bbox, _strip_html(seg.get("source_text") or "")[:60])
        )

    if len(bboxes_with_text) < 2:
        result.errors.append("fewer than 2 segments received layout_block_bbox")
    else:
        ys = [b[1][1] for b in bboxes_with_text]
        result.metrics["bbox_y_min"] = min(ys)
        result.metrics["bbox_y_max"] = max(b[1][3] for b in bboxes_with_text)

        for _idx, bbox, _preview in bboxes_with_text:
            x0, y0, x1, y1 = bbox
            if x0 < -1 or y0 < -1 or x1 > page_w + 1 or y1 > page_h + 1:
                result.errors.append(
                    f"bbox {bbox} exceeds layout page ({page_w}x{page_h})"
                )
                break
            if y1 <= y0 or x1 <= x0:
                result.errors.append(f"degenerate bbox {bbox}")
                break

        unit_seg = next(
            (item for item in bboxes_with_text if "UNIT 20-01" in item[2]),
            None,
        )
        puteri_seg = next(
            (item for item in bboxes_with_text if "PUTERI HARBOUR" in item[2]),
            None,
        )
        if unit_seg and puteri_seg:
            result.metrics["unit_row_bbox"] = list(unit_seg[1])
            result.metrics["puteri_row_bbox"] = list(puteri_seg[1])
            if unit_seg[1][1] >= puteri_seg[1][1]:
                result.errors.append(
                    "UNIT 20-01 row should be above PUTERI HARBOUR row (y0 order)"
                )
            if unit_seg[1] == puteri_seg[1]:
                result.errors.append("UNIT and PUTERI segments share identical bbox")

    if debug_payload:
        result.metrics["debug_drawn_count"] = debug_payload.get("drawn_count")
        sx = float(debug_payload.get("coord_scale_sx") or 0)
        sy = float(debug_payload.get("coord_scale_sy") or 0)
        result.metrics["coord_scale"] = [sx, sy]
        img_w = int(debug_payload.get("image_width") or image_size[0])
        img_h = int(debug_payload.get("image_height") or image_size[1])
        for entry in debug_payload.get("drawn_blocks") or []:
            image_bbox = entry.get("image_bbox")
            if not isinstance(image_bbox, (list, tuple)) or len(image_bbox) < 4:
                continue
            try:
                ix0, iy0, ix1, iy1 = (float(v) for v in image_bbox[:4])
            except (TypeError, ValueError):
                continue
            if ix0 < -2 or iy0 < -2 or ix1 > img_w + 2 or iy1 > img_h + 2:
                result.errors.append(
                    f"image_bbox {image_bbox} exceeds raster {img_w}x{img_h}"
                )
                break

    result.passed = not result.errors
    return result


def run_overlay_test(
    layout_json: Path,
    source_image: Optional[Path] = None,
    output_dir: Optional[Path] = None,
    *,
    allow_synthetic: bool = True,
    target_language: str = "zh",
) -> OverlayValidationResult:
    layout_json = layout_json.resolve()
    if not layout_json.is_file():
        raise FileNotFoundError(f"layout.json not found: {layout_json}")

    out_dir = (output_dir or DEFAULT_OUTPUT_DIR).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    layout_doc = parse_layout_json(layout_json)
    table_idx = _table_block_index(layout_doc)
    table_block = next(
        b for b in layout_doc.iter_blocks() if int(b.index) == table_idx
    )
    table_html = _resolve_table_block_html(table_block)
    if not table_html:
        raise ValueError("Could not extract table HTML from layout.json")

    segments = build_segments_from_mineru_table_html(
        table_html,
        table_block_index=table_idx,
    )
    (out_dir / "segments.json").write_text(
        json.dumps(segments, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    image_path, is_synthetic = resolve_source_image(
        layout_json,
        source_image,
        allow_synthetic=allow_synthetic,
    )

    task_state: Dict[str, Any] = {
        "task_id": "test_png_mineru_overlay",
        "temp_dir": str(out_dir),
        "overlay_source_image_size": None,
    }
    config = ImageOverlayConfig(
        text_field="target_text",
        target_language=target_language,
        output_format="jpg",
        erase_original_text=True,
    )
    overlay_input = ImageOverlayInput(
        source_image_path=str(image_path),
        layout_document=layout_doc,
        segments=segments,
        task_state=task_state,
    )

    pipeline = ImageOverlayPipeline()
    render_result = pipeline.render(
        overlay_input,
        config,
        task_id="test_png_mineru_overlay",
    )

    overlay_path = out_dir / f"overlay.{render_result.file_extension}"
    overlay_path.write_bytes(render_result.image_bytes)

    debug_payload: Optional[Dict[str, Any]] = None
    debug_json = out_dir / "debug" / "image_overlay" / "overlay_blocks.json"
    if debug_json.is_file():
        debug_payload = json.loads(debug_json.read_text(encoding="utf-8"))
        for name in ("overlay_blocks.json", "overlay_blocks.txt"):
            src = out_dir / "debug" / "image_overlay" / name
            if src.is_file():
                dst = out_dir / name
                dst.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")

    image_size = (
        int(render_result.width or task_state.get("overlay_source_image_size", [0])[0]),
        int(render_result.height or task_state.get("overlay_source_image_size", [1])[1]),
    )
    if image_size[0] <= 0 or image_size[1] <= 0:
        image_size = DEFAULT_IMAGE_SIZE

    validation = validate_overlay_result(
        segments,
        layout_doc,
        image_size=image_size,
        drawn_count=render_result.text_blocks_drawn,
        debug_payload=debug_payload,
    )
    validation.metrics["overlay_path"] = str(overlay_path)
    validation.metrics["source_image"] = str(image_path)
    validation.metrics["source_image_synthetic"] = is_synthetic
    validation.metrics["layout_json"] = str(layout_json)

    report_path = out_dir / "validation_report.json"
    report_path.write_text(
        json.dumps(
            {
                "passed": validation.passed,
                "errors": validation.errors,
                "warnings": validation.warnings,
                "metrics": validation.metrics,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return validation


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Generate MinerU PNG overlay from layout.json and validate bboxes.",
    )
    parser.add_argument(
        "--layout-json",
        type=Path,
        default=DEFAULT_LAYOUT_JSON,
        help=f"Path to MinerU layout.json (default: {DEFAULT_LAYOUT_JSON})",
    )
    parser.add_argument(
        "--source-image",
        type=Path,
        default=None,
        help="Source raster image (JPG/PNG). Auto-detected next to layout.json when omitted.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help=f"Output directory (default: {DEFAULT_OUTPUT_DIR})",
    )
    parser.add_argument(
        "--allow-synthetic",
        action="store_true",
        default=True,
        help="Use a synthetic 309x910 canvas when no source image is found (default: on).",
    )
    parser.add_argument(
        "--no-allow-synthetic",
        action="store_false",
        dest="allow_synthetic",
        help="Fail when no source image is available.",
    )
    parser.add_argument(
        "--target-language",
        default="zh",
        help="Target language for overlay font selection (default: zh).",
    )
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = _build_arg_parser().parse_args(argv)
    try:
        validation = run_overlay_test(
            args.layout_json,
            source_image=args.source_image,
            output_dir=args.output_dir,
            allow_synthetic=args.allow_synthetic,
            target_language=args.target_language,
        )
    except Exception as exc:
        print(f"[FAIL] {exc}", file=sys.stderr)
        return 1

    metrics = validation.metrics
    print(f"segments={metrics.get('segment_count')} subdivided={metrics.get('bbox_subdivided_count')}")
    print(f"overlay_items={metrics.get('overlay_draw_items')} drawn={metrics.get('renderer_drawn_count')}")
    print(f"overlay={metrics.get('overlay_path')}")
    print(f"report={args.output_dir / 'validation_report.json'}")

    if validation.passed:
        print("[PASS] overlay validation succeeded")
        return 0

    for err in validation.errors:
        print(f"[FAIL] {err}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
