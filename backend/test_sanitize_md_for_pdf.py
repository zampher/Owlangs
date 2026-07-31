# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

"""Regression tests for PDF Markdown sanitize (raw LaTeX outside math)."""

import unittest

from utils.format_convert_utils import _sanitize_md_for_pdf


class TestSanitizeMdForPdf(unittest.TestCase):
    def test_inline_math_before_cjk_not_double_escaped(self):
        """CJK after closing $ must not trigger outside-math backslash doubling."""
        src = (
            r"其中，$\pi_{G,t}$、$\pi_{R,t}$和$\pi_{C,t}$分别表示$t$时刻的价格。"
        )
        out = _sanitize_md_for_pdf(src)
        self.assertIn(r"$\pi_{G,t}$", out)
        self.assertIn(r"$\pi_{R,t}$", out)
        self.assertIn(r"$\pi_{C,t}$", out)
        self.assertNotIn(r"$\\pi", out)

    def test_pipe_table_spaced_inline_math_not_double_escaped(self):
        src = (
            "| 符号 | 描述 |\n"
            "| --- | --- |\n"
            r"| $ \pi_{G,t}, \pi_{R,t}, \pi_{C,t} $ | t时刻价格 |"
            "\n"
        )
        out = _sanitize_md_for_pdf(src)
        self.assertIn(r"$ \pi_{G,t}, \pi_{R,t}, \pi_{C,t} $", out)
        self.assertNotIn(r"$ \\pi", out)
        self.assertNotIn(r"$ \\\\pi", out)

    def test_pipe_table_after_normalize_then_sanitize_keeps_single_backslash(self):
        """Full PDF prep path: tighten spaces then sanitize without doubling \\cmd."""
        from utils.math_md_normalize import normalize_md_math_for_pandoc_export

        src = (
            "| 符号 | 描述 |\n| --- | --- |\n"
            r"| $ \overline{x}, \underline{x} $ | 上下界 |"
            "\n"
            r"其中，$\pi_{G,t}$、$\pi_{R,t}$和$\pi_{C,t}$分别表示价格。"
            "\n"
        )
        out = _sanitize_md_for_pdf(normalize_md_math_for_pandoc_export(src))
        self.assertIn(r"$\overline{x}, \underline{x}$", out)
        self.assertIn(r"$\pi_{R,t}$", out)
        self.assertNotIn(r"$\\overline", out)
        self.assertNotIn(r"$\\pi", out)

    def test_spaced_paren_table_math_full_pipeline(self):
        from utils.math_md_normalize import normalize_md_math_for_pandoc_export

        src = (
            "| 符号 | 描述 |\n| --- | --- |\n"
            r"| \( \overline{x}, \underline{x} \) | 上下界 |"
            "\n"
        )
        out = _sanitize_md_for_pdf(normalize_md_math_for_pandoc_export(src))
        self.assertIn(r"$\overline{x}, \underline{x}$", out)
        self.assertNotIn(r"\(", out)
        self.assertNotIn(r"$\\overline", out)

    def test_raw_latex_outside_math_still_escaped(self):
        """Bare \\command outside math must still be doubled for Pandoc raw_tex."""
        src = r"See \htm rewrite outside math and keep $\pi$ intact."
        out = _sanitize_md_for_pdf(src)
        self.assertIn(r"\\htm", out)
        self.assertIn(r"$\pi$", out)
        self.assertNotIn(r"$\\pi$", out)

    def test_math_after_ascii_letters_not_double_escaped(self):
        """Algorithm style CER$(..., \\mathbf{CR}, ...)$ must stay single-backslash."""
        src = r"7: $f_0^*, \theta_0^* \leftarrow$ CER$(a_C, a_R, a_E, \mathbf{CR}, F_d)$;"
        out = _sanitize_md_for_pdf(src)
        self.assertIn(r"CER$(a_C, a_R, a_E, \mathbf{CR}, F_d)$", out)
        self.assertNotIn(r"\\mathbf", out)


if __name__ == "__main__":
    unittest.main()
