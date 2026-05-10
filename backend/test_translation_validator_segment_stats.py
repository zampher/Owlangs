# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

"""Unit tests for summarize_segment_translation_stats."""

import unittest

from utils.translation_validator import summarize_segment_translation_stats


class TestSummarizeSegmentTranslationStats(unittest.TestCase):
    def test_counts_eligible_and_buckets(self) -> None:
        task_state = {
            "translation_segments": {
                "segments": [
                    {"source_text": "hello", "target_text": "你好"},
                    {
                        "source_text": "same",
                        "target_text": "same",
                        "is_excluded": False,
                    },
                    {"is_excluded": True},
                    {"is_image": True},
                    {"status": "cleared", "source_text": "x", "target_text": "x"},
                ]
            }
        }
        s = summarize_segment_translation_stats(task_state)
        self.assertEqual(s["total"], 5)
        self.assertEqual(s["excluded"], 1)
        self.assertEqual(s["image"], 1)
        self.assertEqual(s["cleared"], 1)
        self.assertEqual(s["eligible"], 2)
        self.assertEqual(s["success"], 1)
        self.assertEqual(s["failed"], 1)


if __name__ == "__main__":
    unittest.main()
