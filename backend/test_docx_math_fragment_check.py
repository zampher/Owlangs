"""Tests for per-segment Pandoc DOCX math smoke checks."""

import subprocess
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from utils.docx_math_fragment_check import (
    DocxMathFragmentCheckSummary,
    _stderr_has_docx_math_issue,
    apply_docx_math_fragment_issues_to_task_state,
    check_segment_docx_math_pandoc,
)


class TestDocxMathFragmentCheck(unittest.TestCase):
    def test_stderr_heuristic_tex_math_warning(self):
        self.assertTrue(
            _stderr_has_docx_math_issue("[WARNING] Could not convert TeX math\nunexpected \\tag")
        )
        self.assertFalse(_stderr_has_docx_math_issue(""))

    @patch("utils.docx_math_fragment_check._prepare_segment_like_docx_export", return_value="$$ x $$")
    @patch("utils.docx_math_fragment_check.subprocess.run")
    def test_check_segment_flags_texmath_stderr(
        self, mock_run: MagicMock, _mock_prep: MagicMock
    ) -> None:
        mock_run.return_value = subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stderr=b"[WARNING] Could not convert TeX math\n",
            stdout=b"",
        )
        pandoc = Path("C:/fake/pandoc.exe")
        issue = check_segment_docx_math_pandoc(
            r"$$ x \tag{1} $$", 3, pandoc
        )
        self.assertIsNotNone(issue)
        assert issue is not None
        self.assertEqual(issue.segment_index, 3)

    @patch("utils.docx_math_fragment_check.check_all_segments_docx_math")
    def test_apply_writes_task_state(self, mock_check: MagicMock) -> None:
        from utils.docx_math_fragment_check import DocxMathFragmentIssue

        mock_check.return_value = DocxMathFragmentCheckSummary(
            pandoc_available=True,
            checked_segments=1,
            issues=[
                DocxMathFragmentIssue(
                    segment_index=0,
                    message="m",
                    stderr_snippet="e",
                    preview="p",
                )
            ],
            elapsed_seconds=0.01,
        )
        task_state: dict = {}
        summary = apply_docx_math_fragment_issues_to_task_state(task_state)
        self.assertEqual(len(summary.issues), 1)
        payload = task_state.get("docx_math_fragment_issues")
        self.assertIsNotNone(payload)
        assert payload is not None
        self.assertEqual(payload.get("issue_count"), 1)


if __name__ == "__main__":
    unittest.main()
