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
