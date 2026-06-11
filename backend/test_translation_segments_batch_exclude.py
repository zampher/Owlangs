import os
import sys

import pytest

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
if CURRENT_DIR not in sys.path:
    sys.path.insert(0, CURRENT_DIR)

from utils import translation_segments as ts  # noqa: E402


def _build_task_state() -> dict:
    return {
        "translation_segments": {
            "segments": [
                {
                    "segment_index": 0,
                    "source_text": "Hello",
                    "target_text": "你好",
                    "is_excluded": False,
                },
                {
                    "segment_index": 1,
                    "source_text": "World",
                    "target_text": "世界",
                    "is_excluded": False,
                },
                {
                    "segment_index": 2,
                    "source_text": "Formula",
                    "target_text": "Formula",
                    "is_excluded": False,
                },
            ],
        },
        "segments_metadata": {},
    }


@pytest.mark.unit
def test_exclude_translation_segments_batch_updates_all_segments():
    task_state = _build_task_state()

    result = ts.exclude_translation_segments_batch(
        task_id="unit_test_exclude_batch",
        segment_indices=[0, 1, 2],
        task_state=task_state,
    )

    assert result["success"] is True
    assert result["failed_indices"] == []
    assert len(result["segments"]) == 3

    segments = task_state["translation_segments"]["segments"]
    for idx in (0, 1, 2):
        segment = next(s for s in segments if s["segment_index"] == idx)
        assert segment["is_excluded"] is True
        assert segment["target_text"] == segment["source_text"]

    excluded_indices = task_state["segments_metadata"]["excluded_segment_indices"]
    assert excluded_indices == [0, 1, 2]


@pytest.mark.unit
def test_unexclude_translation_segments_batch_clears_exclusions():
    task_state = _build_task_state()

    ts.exclude_translation_segments_batch(
        task_id="unit_test_unexclude_batch",
        segment_indices=[0, 1],
        task_state=task_state,
    )

    result = ts.unexclude_translation_segments_batch(
        task_id="unit_test_unexclude_batch",
        segment_indices=[0, 1],
        task_state=task_state,
    )

    assert result["success"] is True
    assert result["failed_indices"] == []
    assert len(result["segments"]) == 2

    segments = task_state["translation_segments"]["segments"]
    for idx in (0, 1):
        segment = next(s for s in segments if s["segment_index"] == idx)
        assert segment["is_excluded"] is False

    user_unexcluded = task_state["segments_metadata"].get("user_unexcluded_segments", [])
    assert 0 in user_unexcluded
    assert 1 in user_unexcluded
