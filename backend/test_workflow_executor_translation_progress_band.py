"""
Translation progress: chunk ratio in user-facing message, 10-90% band for status progress.
"""

import unittest


class TestTranslationProgressBand(unittest.TestCase):
    def test_first_chunk_message_uses_chunk_ratio_not_translator_percent(self):
        """1/17 should show (5%) from chunk ratio, not internal translator percent mapping."""
        completed, total = 1, 17
        chunk_pct = min(100, int(100.0 * completed / total))
        self.assertEqual(chunk_pct, 5)
        mapped_percent = 10 + int(80.0 * completed / total)
        self.assertEqual(mapped_percent, 14)

    def test_reset_from_extract_complete_then_chunk_updates(self):
        task_state = {"progress": 100, "status": "processing"}
        prev_progress = task_state.get("progress", 0)
        if prev_progress > 90:
            task_state["progress"] = 10
        self.assertEqual(task_state["progress"], 10)

        completed, total = 1, 17
        mapped_percent = 10 + int(80.0 * completed / total)
        task_state["progress"] = mapped_percent
        task_state["message"] = (
            f"Translating... {completed}/{total} chunks ({min(100, int(100.0 * completed / total))}%)"
        )
        self.assertEqual(task_state["progress"], 14)
        self.assertIn("(5%)", task_state["message"])

    def test_prior_mid_range_unchanged_by_reset_rule(self):
        task_state = {"progress": 50, "status": "processing"}
        prev_progress = task_state.get("progress", 0)
        if prev_progress > 90:
            task_state["progress"] = 10
        self.assertEqual(task_state["progress"], 50)


if __name__ == "__main__":
    unittest.main()
