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
                    "modified": False,
                },
                {
                    "segment_index": 1,
                    "source_text": "World",
                    "target_text": "世界",
                    "modified": False,
                },
                {
                    "segment_index": 2,
                    "source_text": "Test",
                    "target_text": "测试",
                    "leading_em": 1.2,
                    "modified": False,
                },
            ],
        },
        "segments_metadata": {},
    }


@pytest.mark.unit
def test_batch_update_translation_segment_typography_sets_leading_em():
    task_state = _build_task_state()

    result = ts.batch_update_translation_segment_typography(
        task_id="unit_test_typography_batch",
        segment_indices=[0, 1, 2],
        leading_em=1.05,
        task_state=task_state,
    )

    assert result["success"] is True
    assert result["failed_indices"] == []
    assert result["updated_count"] == 3

    segments = task_state["translation_segments"]["segments"]
    for idx in (0, 1, 2):
        segment = next(s for s in segments if s["segment_index"] == idx)
        assert segment["leading_em"] == 1.05
        assert segment["modified"] is True


@pytest.mark.unit
def test_batch_update_translation_segment_typography_resets_leading_em():
    task_state = _build_task_state()

    result = ts.batch_update_translation_segment_typography(
        task_id="unit_test_typography_batch_reset",
        segment_indices=[2],
        leading_em_reset=True,
        task_state=task_state,
    )

    assert result["success"] is True
    assert result["updated_count"] == 1

    segment = next(
        s
        for s in task_state["translation_segments"]["segments"]
        if s["segment_index"] == 2
    )
    assert "leading_em" not in segment
    assert segment["modified"] is True


@pytest.mark.unit
def test_batch_update_translation_segment_typography_applies_font_size_delta():
    task_state = {
        "translation_segments": {
            "segments": [
                {
                    "segment_index": 0,
                    "target_text": "A",
                    "computed_font_size_pt": 10.0,
                    "modified": False,
                },
                {
                    "segment_index": 1,
                    "target_text": "B",
                    "font_size_pt": 8.0,
                    "font_size_source": "user",
                    "modified": False,
                },
                {
                    "segment_index": 99,
                    "target_text": "C",
                    "computed_font_size_pt": 72.0,
                    "modified": False,
                },
            ],
        },
    }

    result = ts.batch_update_translation_segment_typography(
        task_id="unit_test_typography_delta",
        segment_indices=[0, 1, 99],
        font_size_delta_pt=0.1,
        task_state=task_state,
    )

    assert result["success"] is True
    assert result["changed_indices"] == [0, 1]
    assert result["updated_count"] == 2

    segments = task_state["translation_segments"]["segments"]
    seg0 = next(s for s in segments if s["segment_index"] == 0)
    seg1 = next(s for s in segments if s["segment_index"] == 1)
    seg99 = next(s for s in segments if s["segment_index"] == 99)
    assert seg0["font_size_pt"] == 10.1
    assert seg0["font_size_source"] == "user"
    assert seg1["font_size_pt"] == 8.1
    assert seg99.get("font_size_source") != "user"
