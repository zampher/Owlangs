# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

"""Tests for pruning stale excluded_segments after layout rebuild."""

from __future__ import annotations

from exclusion.core.exclusion_manager import ExclusionManager


def test_prune_keeps_in_range_user_selected_only() -> None:
    task_state = {
        "segments_metadata": {
            "excluded_segments": {
                "0": {"reason": "user_selected"},
                "5": {"reason": "language_match"},
                "100": {"reason": "image"},
                "bad": {"reason": "user_selected"},
            },
            "excluded_segment_indices": [0, 5, 100],
        }
    }
    removed = ExclusionManager.prune_stale_excluded_segments(
        task_state, new_total=10, task_id="t1"
    )
    assert removed == 3
    kept = task_state["segments_metadata"]["excluded_segments"]
    assert kept == {"0": {"reason": "user_selected"}}
    assert task_state["segments_metadata"]["excluded_segment_indices"] == [0]


def test_prune_noop_when_empty() -> None:
    task_state = {"segments_metadata": {}}
    assert ExclusionManager.prune_stale_excluded_segments(task_state, new_total=5) == 0
