# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

"""
Write Extract-phase segments to temp directory as JSON for diagnosis.
Format matches LLM API input: [{"index": i, "text": "..."}, ...] with one object per line (indent=2).
"""

import json
import os
from typing import List, Optional


def write_extract_segments_json(
    temp_dir: Optional[str],
    segments: List[str],
    task_id: str = "",
) -> Optional[str]:
    """
    Write extracted segments to temp_dir/debug/extract_segments.json in the same
    JSON format as LLM API input (one segment per line, indent=2) for diagnosis.

    Args:
        temp_dir: Task temp directory (e.g. task_state["temp_dir"]). If None or not a dir, no-op.
        segments: List of segment texts, index i = segment index.
        task_id: Optional task_id for logging.

    Returns:
        Path to the written file, or None if not written.
    """
    if not temp_dir or not os.path.isdir(temp_dir):
        return None
    if not segments:
        return None
    try:
        debug_dir = os.path.join(temp_dir, "debug")
        os.makedirs(debug_dir, exist_ok=True)
        out_path = os.path.join(debug_dir, "extract_segments.json")
        objs = [{"index": i, "text": seg} for i, seg in enumerate(segments)]
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(objs, f, ensure_ascii=False, indent=2)
        return out_path
    except OSError:
        return None


def write_translation_segments_debug_json(
    temp_dir: Optional[str],
    segments: List[dict],
    task_id: str = "",
) -> Optional[str]:
    """
    Write translation segments with font/bbox metadata to
    temp_dir/debug/translation_segments.json for diagnosis.

    Includes fields relevant to PDF typography debugging:
    source_text, target_text, modified_text, layout_block_indices,
    layout_block_bbox, computed_font_size_pt, computed_font_weight,
    computed_font_style, computed_leading_em, overlay_render_font_size_pt,
    overlay_estimated_font_size_pt, page_number.

    Args:
        temp_dir: Task temp directory (e.g. task_state["temp_dir"]).
        segments: List of segment dicts from the API response.
        task_id: Optional task_id for logging.

    Returns:
        Path to the written file, or None if not written.
    """
    if not temp_dir or not os.path.isdir(temp_dir):
        return None
    if not segments:
        return None
    try:
        debug_dir = os.path.join(temp_dir, "debug")
        os.makedirs(debug_dir, exist_ok=True)
        out_path = os.path.join(debug_dir, "translation_segments.json")

        fields = (
            "segment_index",
            "source_text",
            "target_text",
            "modified_text",
            "layout_block_indices",
            "layout_block_bbox",
            "page_number",
            "computed_font_size_pt",
            "computed_font_weight",
            "computed_font_style",
            "computed_leading_em",
            "overlay_render_font_size_pt",
            "overlay_estimated_font_size_pt",
        )
        objs = []
        for seg in segments:
            if not isinstance(seg, dict):
                continue
            item = {}
            for key in fields:
                val = seg.get(key)
                if val is not None:
                    item[key] = val
            # Always include index even if None
            if "segment_index" not in item:
                item["segment_index"] = seg.get("segment_index")
            objs.append(item)

        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(objs, f, ensure_ascii=False, indent=2)
        return out_path
    except OSError:
        return None
