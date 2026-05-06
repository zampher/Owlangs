"""Tests for Markdown math normalization before Pandoc export."""

import unittest

from utils.math_md_normalize import normalize_md_math_for_pandoc_export


class TestMathMdNormalize(unittest.TestCase):
    def test_tag_space_before_brace(self):
        src = r"$$ a \leq b \tag {23} $$"
        out = normalize_md_math_for_pandoc_export(src)
        self.assertIn(r"\tag{23}", out)
        self.assertNotIn(r"\tag {23}", out)

    def test_tag_constraint_comma_t_in(self):
        src = (
            r"$$ r \sum_{t=0}^{T_R} R_{0, t}, t \in T_R, T_R \in T_C \tag {23} $$"
        )
        out = normalize_md_math_for_pandoc_export(src)
        self.assertIn(r"\tag{23}", out)
        self.assertIn(r"R_{0, t} \quad t \in", out.replace("  ", " "))

    def test_skips_code_fence(self):
        src = "```\n$$ \\tag {1} $$\n```\noutside $$ x \\tag {2} $$"
        out = normalize_md_math_for_pandoc_export(src)
        self.assertIn(r"\tag {1}", out)
        self.assertIn(r"\tag{2}", out)

    def test_bracket_display_tag_spacing(self):
        src = r"\[ a=b \tag {5} \]"
        out = normalize_md_math_for_pandoc_export(src)
        self.assertIn(r"\tag{5}", out)

    def test_tag_with_forall_clause(self):
        src = r"$$ R_{m} = \sum_{d = 0} R_{d}, \forall m \tag{50} $$"
        out = normalize_md_math_for_pandoc_export(src)
        self.assertIn(r"\quad \forall", out)
        self.assertNotIn(r"R_{d}, \forall", out)

    def test_tag_with_s_t_prefix(self):
        src = r"$$ s. t.: \quad \sum_{d} R_{d} = R_{m}, \forall m \tag{57} $$"
        out = normalize_md_math_for_pandoc_export(src)
        self.assertIn(r"\mathrm{s.t.:}", out)
        self.assertIn(r"\quad \forall", out)

    def test_forall_fix_does_not_corrupt_left_bracket_commas(self):
        """Inner commas in \\left[ A, B \\right] must stay; only ', \\forall' after } ] ) is rewritten."""
        src = r"$$ \mathbf{C R}_{d} \left[ C_{d}, R_{d} \right] \quad \forall d \tag{59} $$"
        out = normalize_md_math_for_pandoc_export(src)
        self.assertIn(r"\left[ C_{d}, R_{d} \right]", out.replace("  ", " "))
        self.assertNotIn(r"\left\quad", out)

    def test_tag_forall_after_bare_subscript_r_d(self):
        """texmath: 'R_d, \\forall' must become 'R_d \\quad \\forall' (no '}' before comma)."""
        src = r"$$ R_m = \sum_{d=0} R_d, \forall m \tag{50} $$"
        out = normalize_md_math_for_pandoc_export(src)
        self.assertIn(r"R_d \quad \forall", out.replace("  ", " "))
        self.assertNotIn(r"R_d, \forall", out)

    def test_tag_stacked_in_duplicate_before_in(self):
        """'t \\in T_R, T_R \\in T_C \\tag' — comma between duplicate identifier and \\in."""
        src = r"$$ r \sum \left(P\right) \leq R_{0, t} \quad t \in T_R, T_R \in T_C \tag{23} $$"
        out = normalize_md_math_for_pandoc_export(src)
        self.assertIn(r"\in T_R \quad T_R \in", out.replace("  ", " "))
        self.assertNotIn(r"T_R, T_R \in", out)

    def test_tag_subject_to_comma_not_colon(self):
        src = r"$$ s. t., \quad E_t = G_t \tag{41} $$"
        out = normalize_md_math_for_pandoc_export(src)
        self.assertIn(r"\mathrm{s.t.:},", out)

    def test_unwrap_tex_fence_so_pandoc_sees_display_math(self):
        """Repair pipelines emit ```tex + $$...$$; Pandoc treats fenced body as code unless unwrapped."""
        src = """Para before.

```tex
$$
R_{m} = \\sum_{d=0} R_{d}, \\quad \\forall m \\qquad (50)
$$
```

Para after.
"""
        out = normalize_md_math_for_pandoc_export(src)
        self.assertNotIn("```tex", out)
        self.assertIn(r"R_{m}", out)
        self.assertIn("$$\n", out)
        self.assertIn("\n$$\n", out)


if __name__ == "__main__":
    unittest.main()
