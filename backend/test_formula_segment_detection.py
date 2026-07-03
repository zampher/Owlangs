# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

"""Unit tests for _is_formula_segment heuristics."""

import os
import sys

import pytest

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
if CURRENT_DIR not in sys.path:
    sys.path.insert(0, CURRENT_DIR)

from exclusion.core.exclusion_detector import detect_exclusion_reason  # noqa: E402
from utils.translation_segments import _is_formula_segment  # noqa: E402

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

BLAND_ALTMAN_PARAGRAPH = (
    "在血管水平，CT-QFR值和金标准FFR值进行Bland-Altman偏差分析显示均值为  "
    r"0.00 \pm 0.04  ，均值  +1.96  标准差为0.09，均值-1.96标准差为-0.09。"
)


@pytest.mark.unit
def test_pure_interline_equation_is_formula():
    assert _is_formula_segment(INTERLINE_EQUATION) is True


@pytest.mark.unit
def test_chinese_paragraph_with_ffr_inline_not_formula():
    assert _is_formula_segment(MIXED_FFR_PARAGRAPH) is False
    detected = detect_exclusion_reason(
        MIXED_FFR_PARAGRAPH,
        block_type="text",
        target_lang="en",
        strict_table_priority=True,
    )
    assert detected is None or detected[0].value != "formula"


@pytest.mark.unit
def test_chinese_paragraph_with_pm_inline_not_formula():
    assert _is_formula_segment(BLAND_ALTMAN_PARAGRAPH) is False
    detected = detect_exclusion_reason(
        BLAND_ALTMAN_PARAGRAPH,
        block_type="text",
        target_lang="en",
        strict_table_priority=True,
    )
    assert detected is None or detected[0].value != "formula"


@pytest.mark.unit
def test_display_math_delimiters_still_formula():
    assert _is_formula_segment(r"$$\alpha + \beta = \gamma$$") is True
