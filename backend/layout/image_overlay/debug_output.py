# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0
"""Debug dumps for image overlay text placement (bbox + text)."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


def resolve_image_overlay_debug_dir(temp_dir: Optional[str]) -> Optional[Path]:
    """Return ``{temp_dir}/debug/image_overlay`` when temp_dir exists."""
    if not temp_dir:
        return None
    root = Path(temp_dir)
    if not root.is_dir():
        return None
    debug_dir = root / "debug" / "image_overlay"
    debug_dir.mkdir(parents=True, exist_ok=True)
    return debug_dir


def _drawn_entry_label(entry: Dict[str, Any]) -> str:
    block_index = entry.get("block_index")
    if block_index is not None:
        prefix = f"block {block_index}"
    elif entry.get("segment_index") is not None:
        prefix = f"segment {entry.get('segment_index')}"
    else:
        prefix = "entry"
    return f"[{prefix}] type={entry.get('block_type')} page={entry.get('page_index')}"


def _skipped_entry_label(entry: Dict[str, Any]) -> str:
    block_index = entry.get("block_index")
    if block_index is not None:
        prefix = f"block {block_index}"
    elif entry.get("segment_index") is not None:
        prefix = f"segment {entry.get('segment_index')}"
    else:
        prefix = "entry"
    return f"[{prefix}] type={entry.get('block_type')} reason={entry.get('reason')}"


def write_image_overlay_debug(
    debug_dir: Path,
    *,
    task_id: str,
    source_image_path: str,
    image_size: Tuple[int, int],
    output_format: Optional[str],
    page_dimensions: Optional[Tuple[Optional[float], Optional[float]]],
    coord_scale: Tuple[float, float],
    drawn_blocks: List[Dict[str, Any]],
    skipped_blocks: List[Dict[str, Any]],
) -> Tuple[Optional[str], Optional[str]]:
    """
    Write overlay placement debug artifacts next to other task debug files.

    Returns:
        (json_path, txt_path) or (None, None) on failure.
    """
    payload: Dict[str, Any] = {
        "task_id": task_id,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_image_path": source_image_path,
        "image_width": image_size[0],
        "image_height": image_size[1],
        "output_format": output_format,
        "page_width": page_dimensions[0] if page_dimensions else None,
        "page_height": page_dimensions[1] if page_dimensions else None,
        "coord_scale_sx": coord_scale[0],
        "coord_scale_sy": coord_scale[1],
        "drawn_count": len(drawn_blocks),
        "skipped_count": len(skipped_blocks),
        "drawn_blocks": drawn_blocks,
        "skipped_blocks": skipped_blocks,
    }
    json_path = debug_dir / "overlay_blocks.json"
    txt_path = debug_dir / "overlay_blocks.txt"
    try:
        json_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        lines: List[str] = [
            f"task_id={task_id}",
            f"source_image={source_image_path}",
            f"image_size={image_size[0]}x{image_size[1]}",
            f"page_size={page_dimensions}",
            f"coord_scale=sx:{coord_scale[0]:.6f} sy:{coord_scale[1]:.6f}",
            f"drawn={len(drawn_blocks)} skipped={len(skipped_blocks)}",
            "",
            "=== DRAWN BLOCKS ===",
        ]
        for entry in drawn_blocks:
            lines.append(_drawn_entry_label(entry))
            lines.append(f"  layout_bbox={entry.get('layout_bbox')}")
            lines.append(f"  image_bbox={entry.get('image_bbox')}")
            if entry.get("segment_index") is not None:
                lines.append(f"  segment_index={entry.get('segment_index')}")
            lines.append(f"  layout_text={entry.get('layout_text', '')!r}")
            lines.append(f"  overlay_text={entry.get('overlay_text', '')!r}")
            if entry.get("source_segment_index") is not None:
                lines.append(f"  source_segment_index={entry.get('source_segment_index')}")
            if entry.get("segment_layout_block_indices") is not None:
                lines.append(
                    f"  segment_layout_block_indices={entry.get('segment_layout_block_indices')}"
                )
            lines.append(f"  plain_text={entry.get('plain_text', '')!r}")
            lines.append(
                "  font_pt mineru={mineru_font_size_pt} user={user_font_size_pt} "
                "estimated={estimated_font_size_pt} render={render_font_size_pt} "
                "bbox_cap_px={bbox_font_cap_px} "
                "preferred_px={preferred_font_size_px} fitted_px={fitted_font_size_px} "
                "lines={line_count}".format(
                    mineru_font_size_pt=entry.get("mineru_font_size_pt"),
                    user_font_size_pt=entry.get("user_font_size_pt"),
                    estimated_font_size_pt=entry.get("estimated_font_size_pt"),
                    render_font_size_pt=entry.get("render_font_size_pt"),
                    bbox_font_cap_px=entry.get("bbox_font_cap_px"),
                    preferred_font_size_px=entry.get("preferred_font_size_px"),
                    fitted_font_size_px=entry.get("fitted_font_size_px"),
                    line_count=entry.get("line_count"),
                )
            )
            lines.append("")
        if skipped_blocks:
            lines.append("=== SKIPPED BLOCKS ===")
            for entry in skipped_blocks:
                lines.append(_skipped_entry_label(entry))
                if entry.get("layout_bbox") is not None:
                    lines.append(f"  layout_bbox={entry.get('layout_bbox')}")
                if entry.get("layout_text"):
                    lines.append(f"  layout_text={entry.get('layout_text')!r}")
                lines.append("")
        txt_path.write_text("\n".join(lines), encoding="utf-8")
        return str(json_path), str(txt_path)
    except OSError:
        return None, None
