import os
import sys

import pytest

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
if CURRENT_DIR not in sys.path:
    sys.path.insert(0, CURRENT_DIR)

from utils.translation_validator import refresh_task_state_segment_failure_flags  # noqa: E402


@pytest.mark.unit
def test_refresh_flags_marks_same_cjk_as_failed():
    task_state = {
        "translation_segments": {
            "segments": [
                {
                    "segment_index": 0,
                    "source_text": "你好世界",
                    "target_text": "你好世界",
                    "is_excluded": False,
                },
            ],
        },
    }
    n = refresh_task_state_segment_failure_flags(task_state)
    assert n == 1
    seg0 = task_state["translation_segments"]["segments"][0]
    assert seg0["is_failed"] is True
    assert seg0["needs_retry"] is True


@pytest.mark.unit
def test_refresh_skips_excluded():
    task_state = {
        "translation_segments": {
            "segments": [
                {
                    "segment_index": 0,
                    "source_text": "你好",
                    "target_text": "你好",
                    "is_excluded": True,
                },
            ],
        },
    }
    n = refresh_task_state_segment_failure_flags(task_state)
    assert n == 0
