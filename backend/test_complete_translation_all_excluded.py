import os
import sys

import pytest

# Ensure backend package imports work when running this test directly.
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
if CURRENT_DIR not in sys.path:
  sys.path.insert(0, CURRENT_DIR)

from app.services.task import task_manager  # noqa: E402
from utils.translation_segments import (  # noqa: E402
  complete_translation_with_source_only,
)


@pytest.mark.unit
def test_complete_translation_with_source_only_all_excluded():
  """When all segments are excluded, translation_segments should be filled with source text."""
  task_id = "unit_test_all_excluded"
  task_manager.create_task(task_id)

  total_segments = 3
  source_segments = ["seg-0", "seg-1", "seg-2"]

  excluded_segments = {i: "user_selected" for i in range(total_segments)}

  task_manager.update_task(
    task_id,
    {
      "source_chunks_cache": {"segments": source_segments},
      "segments_metadata": {
        "segment_info": [
          {"is_image": False, "separator_after": "\n\n"} for _ in range(total_segments)
        ],
      },
    },
  )

  from exclusion.core import ExclusionManager  # imported here to avoid test import cycles

  state = task_manager.get_task(task_id)
  ExclusionManager.update_excluded_segments(task_state=state, excluded_segments=excluded_segments)
  task_manager.update_task(task_id, state)

  updated_state = task_manager.get_task(task_id)

  result = complete_translation_with_source_only(task_id, updated_state)

  assert result is True

  ts = updated_state.get("translation_segments") or {}
  segments = ts.get("segments") or []

  assert len(segments) == total_segments

  for idx, seg in enumerate(segments):
    assert seg.get("segment_index") == idx
    assert seg.get("source_text") == source_segments[idx]
    assert seg.get("target_text") == source_segments[idx]
    assert seg.get("is_excluded") is True
    assert seg.get("is_failed") is False
    assert seg.get("needs_retry") is False

