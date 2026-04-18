import time

from exclusion.core.exclusion_manager import ExclusionManager
from exclusion.core.exclusion_reason import ExclusionReason


def _build_task_state_for_reference_user_unexcluded():
    """
    Build a minimal fake task_state to verify that user_unexcluded_segments
    always override automatic content-based exclusions (e.g. reference).
    """
    # Simulate 200 segments in source_chunks_cache
    segments = [f"segment-{i}" for i in range(200)]

    task_state = {
        "source_chunks_cache": {
            "segments": segments,
        },
        "segments_metadata": {
            # Primary source: excluded_segments dict
            # Segment 100 was previously auto-detected as reference and stored here.
            "excluded_segments": {
                "100": {
                    "reason": ExclusionReason.REFERENCE.value,
                    "detected_at": time.time(),
                    "metadata": {"from": "unit-test"},
                }
            },
            # Fallback source: detected_exclusion_reasons dict
            # Same segment 100 is also present here as a content-based exclusion.
            "detected_exclusion_reasons": {
                "100": {
                    "reason": ExclusionReason.REFERENCE.value,
                    "detected_at": time.time(),
                }
            },
            # User explicitly un-excluded segment 100 in the UI.
            "user_unexcluded_segments": [100],
        },
    }
    return task_state


def test_user_unexcluded_overrides_content_based_reference():
    """
    Ensure that user_unexcluded_segments has the highest priority and can override
    both primary excluded_segments and the content-based fallback from
    detected_exclusion_reasons.
    """
    task_state = _build_task_state_for_reference_user_unexcluded()

    excluded = ExclusionManager.get_excluded_segments(task_state)

    # Segment 100 should NOT be excluded because user_unexcluded_segments overrides
    # both excluded_segments and detected_exclusion_reasons fallback.
    assert 100 not in excluded, (
        "Segment 100 is in user_unexcluded_segments but still appears in excluded "
        f"set: {excluded.get(100)}"
    )

    # Sanity check: other indices are not accidentally excluded.
    for idx in [0, 1, 50, 199]:
        assert idx not in excluded


if __name__ == "__main__":
    # Simple manual runner so this file can be executed directly if needed.
    test_user_unexcluded_overrides_content_based_reference()
    print("user-unexcluded priority tests passed.")

