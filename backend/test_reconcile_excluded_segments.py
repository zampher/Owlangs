import os
import sys

import pytest

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
if CURRENT_DIR not in sys.path:
    sys.path.insert(0, CURRENT_DIR)

from exclusion.core import ExclusionManager, ExclusionReason  # noqa: E402
from utils.translation_segments import (  # noqa: E402
    apply_copy_source_only_exclusions,
    complete_translation_with_source_only,
    reconcile_excluded_segments_from_layout,
)


@pytest.mark.unit
def test_reconcile_corrects_stale_all_excluded_metadata():
    """When metadata marks every segment excluded but layout chunks disagree, reconcile fixes metadata."""
    total = 5
    task_state = {
        "source_chunks_cache": {"segments": [f"seg-{i}" for i in range(total)]},
        "segments_metadata": {},
        "layout_prepared_chunks": [
            {"is_excluded": True, "segment_indices": [0, 1]},
            {"is_excluded": False, "segment_indices": [2, 3]},
            {"is_excluded": True, "segment_indices": [4]},
        ],
    }
    ExclusionManager.update_excluded_segments(
        task_state,
        {i: ExclusionReason.USER_SELECTED for i in range(total)},
    )

    assert reconcile_excluded_segments_from_layout(task_state, "reconcile-unit") is True
    excluded = ExclusionManager.get_excluded_segments(task_state)
    assert excluded == {0, 1, 4}
    assert len(excluded) < total


@pytest.mark.unit
def test_copy_source_only_triggers_source_only_completion():
    """Convert-toolbar flow: all segments excluded on translate task only, no reconcile undo."""
    total = 4
    task_state = {
        "source_chunks_cache": {"segments": [f"seg-{i}" for i in range(total)]},
        "segments_metadata": {"excluded_segments": {"0": {"reason": "identifier"}}},
        "layout_prepared_chunks": [
            {"is_excluded": True, "segment_indices": [0]},
            {"is_excluded": False, "segment_indices": [1, 2, 3]},
        ],
    }
    assert apply_copy_source_only_exclusions(task_state, "copy-only-unit") is True
    assert complete_translation_with_source_only("copy-only-unit", task_state) is True
    segments = task_state.get("translation_segments", {}).get("segments", [])
    assert len(segments) == total
    for idx, seg in enumerate(segments):
        assert seg.get("target_text") == f"seg-{idx}"


@pytest.mark.unit
def test_complete_translation_skips_shortcut_after_reconcile():
    """Reconcile prevents false [ALL_EXCLUDED] when layout still has translatable segments."""
    total = 4
    task_state = {
        "source_chunks_cache": {"segments": [f"seg-{i}" for i in range(total)]},
        "segments_metadata": {},
        "layout_prepared_chunks": [
            {"is_excluded": True, "segment_indices": [0]},
            {"is_excluded": False, "segment_indices": [1, 2, 3]},
        ],
    }
    ExclusionManager.update_excluded_segments(
        task_state,
        {i: ExclusionReason.USER_SELECTED for i in range(total)},
    )

    assert complete_translation_with_source_only("unit-reconcile", task_state) is False
