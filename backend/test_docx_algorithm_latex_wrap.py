"""Tests for bare LaTeX wrapping before DOCX export."""

import unittest

from utils.docx_algorithm_latex_wrap import wrap_bare_latex_for_docx_algorithms


class TestDocxAlgorithmLatexWrap(unittest.TestCase):
    def test_numbered_latex_line_wrapped(self):
        src = "ALGORITHM 1 | Test\n4: \\mathbf{CR}[\\theta_d] \\gets x\n"
        out = wrap_bare_latex_for_docx_algorithms(src)
        self.assertIn("$", out)
        self.assertIn(r"4: $\mathbf{CR}", out.replace("\n", ""))

    def test_while_do_wraps_condition_only(self):
        src = "ALGORITHM 1\n3: while t\\leq T_C do\n"
        out = wrap_bare_latex_for_docx_algorithms(src)
        self.assertIn("while $t\\leq T_C$ do", out)

    def test_if_then_wraps_condition(self):
        src = "ALGORITHM 1\n15: if f_{d}^{*} < g then\n"
        out = wrap_bare_latex_for_docx_algorithms(src)
        self.assertIn("if $f_{d}^{*} < g$ then", out)

    def test_require_ensure_split_and_wrap(self):
        src = (
            "Require: a_{C},a_{R},a_{E} Ensure: f^{*},x^{*} 1: t\\gets t_0\n"
        )
        out = wrap_bare_latex_for_docx_algorithms(src)
        self.assertIn(r"Require: $a_{C},a_{R},a_{E}$", out)
        self.assertIn(r"Ensure: $f^{*},x^{*}$", out)
        self.assertIn(r"1: $t\gets t_0$", out)

    def test_plain_paragraph_unchanged(self):
        src = "Hello world. No algorithm here.\n"
        out = wrap_bare_latex_for_docx_algorithms(src)
        self.assertEqual(out, src)


if __name__ == "__main__":
    unittest.main()
