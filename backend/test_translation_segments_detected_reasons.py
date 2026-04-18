import os
import sys
import time

import pytest

# Ensure backend package and app.* imports work when running this test directly.
# NOTE: Other backend tests (e.g. test_imports.py) add the backend directory itself
# to sys.path so that "app" can be imported as a top-level package.
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
if CURRENT_DIR not in sys.path:
    sys.path.insert(0, CURRENT_DIR)

from app.routes.service.app_routes_translation_segments import (  # noqa: E402
    _enrich_translation_segments_with_detected_reasons,
)
from app.services.task import task_manager  # noqa: E402


def _build_task_state_with_detected_reasons():
    """
    Build a minimal task_state that contains detected_exclusion_reasons.

    This simulates Extract phase having stored detection results for:
    - segment 0: language_match (with metadata)
    - segment 3: identifier (string-only format)
    """
    return {
        "segments_metadata": {
            "detected_exclusion_reasons": {
                "0": {
                    "reason": "language_match",
                    "metadata": {
                        "detected_lang": "ja",
                        "target_lang": "zh",
                        "detected_at": time.time(),
                    },
                },
                "3": "identifier",
            }
        }
    }


@pytest.mark.unit
def test_enrich_translation_segments_with_detected_reasons():
    """
    Ensure that _enrich_translation_segments_with_detected_reasons:
    - Reads detected_exclusion_reasons from task_state.segments_metadata
    - Populates detected_exclusion_reason on matching segments
    - Merges exclusion_metadata when available
    """
    task_id = "unit_test_detected_reasons"

    # Create task and attach minimal segments_metadata with detected reasons
    task_manager.create_task(task_id)
    task_manager.update_task(task_id, _build_task_state_with_detected_reasons())

    # Build a minimal translation-segments style response
    response_data = {
        "segments": [
            {
                "segment_index": 0,
                "source_text": "日本語の文です。",
                "target_text": "This is a Japanese sentence.",
            },
            {
                "segment_index": 1,
                "source_text": "Normal content",
                "target_text": "Normal content translated",
            },
            {
                "segment_index": 3,
                "source_text": "OM13034",
                "target_text": "OM13034",
            },
        ],
        "metadata": {
            "total_segments": 3,
        },
    }

    _enrich_translation_segments_with_detected_reasons(task_id, response_data)

    segments = response_data["segments"]

    # Segment 0 should have language_match with metadata
    seg0 = next(s for s in segments if s.get("segment_index") == 0)
    assert (
        seg0.get("detected_exclusion_reason") == "language_match"
    ), "Segment 0 should be enriched with language_match detected_exclusion_reason"
    meta0 = seg0.get("exclusion_metadata") or {}
    assert meta0.get("detected_lang") == "ja"
    assert meta0.get("target_lang") == "zh"

    # Segment 1 has no detection and should not be enriched
    seg1 = next(s for s in segments if s.get("segment_index") == 1)
    assert "detected_exclusion_reason" not in seg1
    assert "exclusion_metadata" not in seg1

    # Segment 3 should have identifier from string-only format
    seg3 = next(s for s in segments if s.get("segment_index") == 3)
    assert (
        seg3.get("detected_exclusion_reason") == "identifier"
    ), "Segment 3 should be enriched with identifier detected_exclusion_reason"

    # Metadata should contain aggregated detected_exclusion_reason_counts
    meta = response_data.get("metadata") or {}
    detected_counts = meta.get("detected_exclusion_reason_counts") or {}
    assert detected_counts.get("language_match") == 1
    assert detected_counts.get("identifier") == 1

