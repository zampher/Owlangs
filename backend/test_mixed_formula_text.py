# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

"""Tests for mixed plain text + LaTeX delimiter wrapping."""

from utils.mixed_formula_text import mixed_text_to_md, segment_mixed_text_into_md_segments


LOG_REPRO_MATHCAL = (
    r"where   \mathcal{A}(\boldsymbol{x}^{o}),\mathcal{P}(\boldsymbol{x}^{o})   "
    r"denote the amplitude and phase components respectively"
)


def test_nested_mathcal_chain_fully_wrapped():
    md = mixed_text_to_md(LOG_REPRO_MATHCAL)
    outside = [md.split("$")[i] for i in range(0, len(md.split("$")), 2)]
    for chunk in outside:
        assert r"\mathcal" not in chunk
    assert r"\mathcal{A}(\boldsymbol{x}^{o})" in md
    assert r"\mathcal{P}(\boldsymbol{x}^{o})" in md


def test_neq_command_not_split():
    segments = segment_mixed_text_into_md_segments(
        r"\sum_{i \neq j} COR"
    )
    math_parts = [s for is_math, s in segments if is_math]
    assert any(r"\neq" in part for part in math_parts)
    assert not any(part == "eq" for part in math_parts)


def test_literal_backslash_n_not_wrapped_as_math():
    md = mixed_text_to_md(r"2.28 克\n(=1,838 克聚乙烯醇)")
    assert r"$\n$" not in md
    assert "2.28 克" in md
