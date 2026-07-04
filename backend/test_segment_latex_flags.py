# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

"""Unit tests for segment LaTeX flag classification."""

import os
import sys

import pytest

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
if CURRENT_DIR not in sys.path:
    sys.path.insert(0, CURRENT_DIR)

from utils.segment_latex_flags import (  # noqa: E402
    attach_latex_flags_to_segment,
    classify_latex_flags,
    normalize_text_for_typst_overlay,
    prepare_text_for_latex_render,
)

INTERLINE_EQUATION = (
    r"n = \frac {\left[ Z _ {1 - \alpha} \sqrt {p _ {0} (1 - p _ {0})} + "
    r"Z _ {1 - \beta} \sqrt {p _ {T} (1 - p _ {T})} \right] ^ {2}}{(p _ {T} - p _ {0}) ^ {2}}"
)

MIXED_FFR_PARAGRAPH = (
    "(5) 血管水平转变为病人水平原则: 若受试者有多个血管, 若存在一个血管金标准测量值  "
    r"\mathrm{FFR} \leq 0.80  为阳性, 则认为该病人为阳性病例, 将用于计算病人水平的灵敏度; "
    r"若所有血管金标准测量值  \mathrm{FFR} > 0.80  为阴性, 则认为该病人为阴性病例, "
    "将用于计算病人水平的特异度。"
)

PURE_TEXT = "This paragraph has no math at all."

DELIMITED_MIXED = r"Overall parameters are $W_{y}$ and more."

VPP_SUBSCRIPT_PARAGRAPH = (
    "4. 内部资源调度：在此层级，虚拟电厂运营商主要关注如何调度其内部资源以满足要求。"
    "REC 的购买量和再调度量，分别记为 R_{m} 和 R_{d}，以及每年 CER 的购买量、"
    "每月的调度量和每天的调度量，分别记为 C_{y}、C_{m} 和 C_{d}，"
    "都是通过这种分层方法确定的。虚拟电厂的内部再调度结果每天在电力层中求解，"
    "确保虚拟电厂的运行在成本和合规性方面得到优化。"
)

TABLE_WITH_INLINE_MATH = (
    "| Reagent | Amount |\n"
    "| --- | --- |\n"
    "| EDC $\\cdot$ HCl | 2.0 g |"
)

TABLE_WITH_RAW_LATEX = (
    "| Reagent | Amount |\n"
    "| --- | --- |\n"
    "| EDC \\cdot HCl | 2.0 g |"
)


@pytest.mark.unit
def test_pure_text_has_no_latex_flags():
    flags = classify_latex_flags(PURE_TEXT, block_type="text")
    assert flags == {"present": False, "mixed": False, "needs_delimiter_wrap": False}


@pytest.mark.unit
def test_interline_equation_block_is_pure_latex():
    flags = classify_latex_flags(INTERLINE_EQUATION, block_type="interline_equation")
    assert flags == {"present": True, "mixed": False, "needs_delimiter_wrap": False}


@pytest.mark.unit
def test_mixed_chinese_paragraph_needs_wrap():
    flags = classify_latex_flags(MIXED_FFR_PARAGRAPH, block_type="text")
    assert flags["present"] is True
    assert flags["mixed"] is True
    assert flags["needs_delimiter_wrap"] is True


@pytest.mark.unit
def test_delimited_mixed_text_does_not_need_wrap():
    flags = classify_latex_flags(DELIMITED_MIXED, block_type="text")
    assert flags["present"] is True
    assert flags["mixed"] is True
    assert flags["needs_delimiter_wrap"] is False


@pytest.mark.unit
def test_table_body_with_delimited_math_present_no_wrap():
    flags = classify_latex_flags(TABLE_WITH_INLINE_MATH, block_type="table_body")
    assert flags["present"] is True
    assert flags["needs_delimiter_wrap"] is False


@pytest.mark.unit
def test_table_body_with_raw_latex_needs_wrap():
    flags = classify_latex_flags(TABLE_WITH_RAW_LATEX, block_type="table_body")
    assert flags["present"] is True
    assert flags["mixed"] is True
    assert flags["needs_delimiter_wrap"] is True


@pytest.mark.unit
def test_prepare_text_wraps_when_flagged():
    flags = classify_latex_flags(MIXED_FFR_PARAGRAPH, block_type="text")
    prepared = prepare_text_for_latex_render(MIXED_FFR_PARAGRAPH, flags)
    assert r"$\mathrm{FFR}$" in prepared or r"$\mathrm{FFR} \leq 0.80$" in prepared


@pytest.mark.unit
def test_attach_latex_flags_writes_has_latex():
    segment = {"text": MIXED_FFR_PARAGRAPH, "block_type": "text"}
    flags = attach_latex_flags_to_segment(segment)
    assert segment["has_latex"] is True
    assert segment["latex_flags"] == flags


WRAPPED_MIXED = (
    "$$\n(5) 血管水平: 若存在 "
    r"\mathrm{FFR} \leq 0.80  为阳性。\n$$"
)


@pytest.mark.unit
def test_unwrap_spurious_display_math_wrapper_for_mixed_paragraph():
    flags = classify_latex_flags(WRAPPED_MIXED, block_type="text")
    normalized = normalize_text_for_typst_overlay(WRAPPED_MIXED, flags)
    assert not normalized.strip().startswith("$$")
    assert r"\mathrm{FFR}" in normalized


@pytest.mark.unit
def test_subscript_after_cjk_comma_does_not_wrap_prose_as_math():
    """Regression: C_{d}， prose must not be wrapped in a single $...$ math span."""
    flags = classify_latex_flags(VPP_SUBSCRIPT_PARAGRAPH, block_type="text")
    prepared = prepare_text_for_latex_render(VPP_SUBSCRIPT_PARAGRAPH, flags)
    assert prepared.endswith("优化。")
    assert "$C_{d}$" in prepared
    assert not prepared.endswith("$")
    assert prepared.count("$") % 2 == 0
    assert "，都是通过这种分层方法" in prepared


@pytest.mark.unit
def test_layout_block_to_render_block_promotes_mixed_latex_to_markdown():
    from layout.base import LayoutBlock
    from layout.pdf_renderer.typst_overlay.models import layout_block_to_render_block

    block = LayoutBlock(
        index=1,
        page_index=0,
        type="text",
        bbox=(0.0, 0.0, 200.0, 40.0),
        text=MIXED_FFR_PARAGRAPH,
    )
    rb = layout_block_to_render_block(
        block,
        page_index=0,
        translated_text=MIXED_FFR_PARAGRAPH,
    )
    assert rb.render_kind == "markdown"
    assert "$" in rb.markdown_text
