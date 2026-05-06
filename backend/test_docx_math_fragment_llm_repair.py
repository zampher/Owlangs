"""Tests for DOCX fragment LLM repair pipeline (mocked LLM / Pandoc)."""

import unittest
from unittest.mock import patch

from utils.docx_math_fragment_check import (
    DocxMathFragmentCheckSummary,
    DocxMathFragmentIssue,
)
from utils.docx_math_fragment_llm_repair import repair_docx_math_fragments_with_llm


class TestDocxMathFragmentLlmRepair(unittest.TestCase):
    def test_returns_error_when_llm_config_missing(self) -> None:
        task_state: dict = {"translation_segments": {"segments": []}}
        r = repair_docx_math_fragments_with_llm(task_state, "tid", None)
        self.assertFalse(r.get("success"))
        self.assertEqual(r.get("error"), "llm_config_missing")

    @patch("utils.docx_math_fragment_check.apply_docx_math_fragment_issues_to_task_state")
    @patch("utils.docx_math_fragment_check.check_all_segments_docx_math")
    def test_applies_llm_fix_and_rechecks(
        self,
        mock_recheck,
        mock_apply_issues,
    ) -> None:
        task_state = {
            "translation_segments": {
                "segments": [
                    {
                        "segment_index": 7,
                        "target_text": r"$$ x \tag{1} $$",
                        "source_text": "src",
                    },
                ]
            }
        }

        mock_apply_issues.return_value = DocxMathFragmentCheckSummary(
            pandoc_available=True,
            checked_segments=1,
            issues=[
                DocxMathFragmentIssue(
                    segment_index=7,
                    message="m",
                    stderr_snippet="Could not convert TeX math",
                    preview="p",
                )
            ],
            elapsed_seconds=0.01,
        )

        mock_recheck.return_value = DocxMathFragmentCheckSummary(
            pandoc_available=True,
            checked_segments=1,
            issues=[],
            elapsed_seconds=0.02,
        )

        cfg = {
            "base_url": "http://localhost:9999/v1",
            "model_id": "test-model",
        }

        def _fake_repair(
            _tid: str,
            _idx: int,
            _orig: str,
            stderr: str,
            _cfg: dict,
        ) -> tuple:
            self.assertIn("TeX", stderr)
            return (r"$$ x \quad \tag{1} $$", "ok")

        out = repair_docx_math_fragments_with_llm(
            task_state,
            "task-a",
            cfg,
            refresh_check_first=True,
            recheck_after=True,
            repair_snippet_fn=_fake_repair,
        )

        self.assertTrue(out.get("success"))
        self.assertEqual(out.get("segments_updated"), 1)
        self.assertEqual(out.get("issues_after"), 0)
        seg = task_state["translation_segments"]["segments"][0]
        self.assertIn(r"\quad", seg.get("target_text", ""))

    @patch("utils.docx_math_fragment_check.apply_docx_math_fragment_issues_to_task_state")
    @patch("utils.docx_math_fragment_check.check_all_segments_docx_math")
    def test_rejects_llm_that_introduces_extra_tag_numbers(
        self,
        mock_recheck,
        mock_apply_issues,
    ) -> None:
        """LLM must not paste neighboring equations (new \\tag numbers) into one segment."""
        task_state = {
            "translation_segments": {
                "segments": [
                    {
                        "segment_index": 201,
                        "target_text": r"$$\mathrm{s.t.:}\quad \sum R \tag{57}$$",
                        "source_text": "src",
                    },
                ]
            }
        }

        mock_apply_issues.return_value = DocxMathFragmentCheckSummary(
            pandoc_available=True,
            checked_segments=1,
            issues=[
                DocxMathFragmentIssue(
                    segment_index=201,
                    message="m",
                    stderr_snippet="Could not convert tex math",
                    preview="p",
                )
            ],
            elapsed_seconds=0.01,
        )

        mock_recheck.return_value = DocxMathFragmentCheckSummary(
            pandoc_available=True,
            checked_segments=1,
            issues=[],
            elapsed_seconds=0.02,
        )

        cfg = {
            "base_url": "http://localhost:9999/v1",
            "model_id": "test-model",
        }

        def _fake_repair_bad(
            _tid: str,
            _idx: int,
            _orig: str,
            _stderr: str,
            _cfg: dict,
        ) -> tuple:
            # Simulates model prepending another numbered equation not in the segment.
            return (
                r"$$\min F \tag{56}$$ $$\mathrm{s.t.:}\quad \sum R \tag{57}$$",
                "ok",
            )

        out = repair_docx_math_fragments_with_llm(
            task_state,
            "task-b",
            cfg,
            refresh_check_first=True,
            recheck_after=True,
            repair_snippet_fn=_fake_repair_bad,
        )

        self.assertTrue(out.get("success"))
        self.assertEqual(out.get("segments_updated"), 0)
        seg = task_state["translation_segments"]["segments"][0]
        self.assertEqual(
            seg.get("target_text"),
            r"$$\mathrm{s.t.:}\quad \sum R \tag{57}$$",
        )
        details = out.get("repair_details") or []
        self.assertEqual(len(details), 1)
        self.assertIn("rejected_llm_expansion", details[0].get("notes", ""))


if __name__ == "__main__":
    unittest.main()
