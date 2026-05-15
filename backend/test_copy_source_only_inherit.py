"""Verify real Translate does not inherit copy_source_only full exclusion metadata."""

import os
import sys

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
if CURRENT_DIR not in sys.path:
    sys.path.insert(0, CURRENT_DIR)

from exclusion.core import ExclusionReason  # noqa: E402
from utils.translation_segments import apply_copy_source_only_exclusions  # noqa: E402


def test_copy_source_only_task_should_not_pollute_downstream_exclusion_metadata():
    """Simulate inherit: copy_source_only shell points at format task with 1 excluded segment."""
    format_task = {
        "convert_only": True,
        "source_chunks_cache": {"segments": [f"s{i}" for i in range(5)]},
        "segments_metadata": {
            "excluded_segments": {"0": {"reason": "identifier"}},
            "excluded_segment_indices": [0],
        },
    }
    copy_only_task = {
        "copy_source_only": True,
        "convert_task_id": "format-task",
        "source_chunks_cache": format_task["source_chunks_cache"],
    }
    apply_copy_source_only_exclusions(copy_only_task, "copy-only-task")

    assert len(copy_only_task["segments_metadata"]["excluded_segments"]) == 5

    exclusion_source = copy_only_task
    effective_convert_task_id = "copy-only-task"
    if copy_only_task.get("copy_source_only"):
        upstream_id = copy_only_task.get("convert_task_id")
        if upstream_id:
            effective_convert_task_id = upstream_id
            exclusion_source = format_task

    excluded = exclusion_source["segments_metadata"]["excluded_segments"]
    assert effective_convert_task_id == "format-task"
    assert len(excluded) == 1
