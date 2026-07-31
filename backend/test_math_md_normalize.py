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

    def test_tighten_spaced_inline_math_for_pandoc(self):
        """Pandoc rejects '$ \\\\cmd $'; strip inner spaces so math is recognized."""
        src = (
            "| 符号 | 描述 |\n| --- | --- |\n"
            r"| $ \overline{x}, \underline{x} $ | 上下界 |"
            "\n"
            r"其中，$ \pi_{G,t} $ 和 $ \pi_{R,t} $ 分别表示价格。"
            "\n"
        )
        out = normalize_md_math_for_pandoc_export(src)
        self.assertIn(r"$\overline{x}, \underline{x}$", out)
        self.assertIn(r"$\pi_{G,t}$", out)
        self.assertIn(r"$\pi_{R,t}$", out)
        self.assertNotIn(r"$ \overline", out)
        self.assertNotIn(r"$ \pi", out)

    def test_tighten_inline_math_preserves_display_blocks(self):
        src = "before\n$$\n x = 1 \n$$\nafter $ y $"
        out = normalize_md_math_for_pandoc_export(src)
        self.assertIn("$$\n x = 1 \n$$", out)
        self.assertIn("$y$", out)

    def test_collapse_overescaped_command_in_inline_math(self):
        src = r"CER$(a_C, a_R, a_E, \\mathbf{CR}, F_d)$;"
        out = normalize_md_math_for_pandoc_export(src)
        self.assertIn(r"CER$(a_C, a_R, a_E, \mathbf{CR}, F_d)$", out)
        self.assertNotIn(r"\\mathbf", out)

    def test_collapse_does_not_touch_display_matrix_breaks(self):
        src = "$$\n\\begin{matrix}a \\\\ b\\end{matrix}\n$$"
        out = normalize_md_math_for_pandoc_export(src)
        self.assertIn(r"a \\ b", out)

    def test_spaced_paren_math_converted_to_tight_dollars(self):
        """Spaced \\( \\cmd \\) becomes Pandoc-safe $\\cmd$ (not literal parentheses)."""
        src = (
            "| 符号 | 描述 |\n| --- | --- |\n"
            r"| \( \overline{x}, \underline{x} \) | 上下界 |"
            "\n"
            r"记为 \( R_{m} \) 和 \( R_{d} \)。"
            "\n"
        )
        out = normalize_md_math_for_pandoc_export(src)
        self.assertIn(r"$\overline{x}, \underline{x}$", out)
        self.assertIn(r"$R_{m}$", out)
        self.assertIn(r"$R_{d}$", out)
        self.assertNotIn(r"\(", out)
        self.assertNotIn(r"\)", out)

    def test_unwrap_tex_fence_with_algorithm_and_inline_math(self):
        """DOCX LLM repair sometimes wraps whole algorithm in ```tex; strip fence for $ math."""
        from utils.math_md_normalize import unwrap_tex_latex_fences_to_display_math

        src = (
            "```tex\n"
            "Require: $a_C, a_R, a_E$\n"
            "1: Initialize $\\theta_d$\n"
            "```\n"
        )
        out = unwrap_tex_latex_fences_to_display_math(src)
        self.assertNotIn("```", out)
        self.assertIn("$a_C, a_R, a_E$", out)
        self.assertIn(r"$\theta_d$", out)

        # Exact display math fence still unwraps to $$ ... $$
        display = "```latex\n$$\nx^2\n$$\n```\n"
        out_d = unwrap_tex_latex_fences_to_display_math(display)
        self.assertIn("$$\n", out_d)
        self.assertIn("x^2", out_d)
        self.assertNotIn("```", out_d)

        # Plain TeX source without markdown math stays fenced
        plain = "```tex\n\\documentclass{article}\n```\n"
        out_p = unwrap_tex_latex_fences_to_display_math(plain)
        self.assertIn("```tex", out_p)


if __name__ == "__main__":
    unittest.main()
