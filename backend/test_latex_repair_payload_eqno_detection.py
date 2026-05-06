"""XeLaTeX stderr classification for LLM repair error_type routing."""

import unittest

from utils.latex_repair_payload import _detect_error_type


class TestEqnoErrorDetection(unittest.TestCase):
    def test_eqno_in_math_mode_from_xelatex_stderr(self):
        stderr = r"""Error producing PDF.
! You can't use `\eqno' in math mode.
\veqno ->\@kernel@eqno
l.940 \]
"""
        self.assertEqual(_detect_error_type(stderr), "eqno_in_math_mode")


if __name__ == "__main__":
    unittest.main()
