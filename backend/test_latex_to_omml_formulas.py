# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

"""
Unit tests for LaTeX -> OMML conversion used in PDF workflow DOCX export.

Verifies that specific formulas (with \\leq, \\left/\\right, \\bar, \\tag) convert
correctly to Office Math ML so they are not rendered as fallback LaTeX-as-text.

Run from project root: pytest backend/test_latex_to_omml_formulas.py -v
Requires: latex2mathml, mathml2omml, mathml2omml-as (pip install latex2mathml mathml2omml mathml2omml-as or uv sync --extra docx_equation).
"""

import sys
from pathlib import Path

# Ensure project root and backend are on path (exporter uses "from exporter..." / "from logger...")
_root = Path(__file__).resolve().parent.parent
_backend = Path(__file__).resolve().parent
for p in (str(_root), str(_backend)):
    if p not in sys.path:
        sys.path.insert(0, p)

import pytest

# Formulas that were reported failing to convert to OMML in PDF->DOCX export
LATEX_FORMULAS_TO_TEST = [
    r"$$0 \leq P _ {d, t} \leq \left(1 - z _ {t}\right) \bar {P _ {d}} \tag {8}$$",
    r"$$0 \leq Q _ {t} \leq \bar {Q} \tag {10}$$",
    r"$$0 \leq R _ {w, t} \leq \left(1 - z _ {R, t}\right) \bar {R _ {w}} \tag {14}$$",
]

# Sum with lower limit (d = 0) that should be rendered as a true lower limit,
# not as a simple right subscript.
SUM_WITH_LOWER_LIMIT = (
    r"$$"
    r"\sum_ {d = 0} C _ {d} \leq C _ {y} \tag {49}"
    r"$$"
)

# Additional sum / conservation formulas with lower limits that should use
# proper lower-limit layout in OMML.
SUM_FORMULAS_WITH_LOWER_LIMIT = [
    (
        r"$$"
        r"R _ {m} = \sum_ {d = 0} R _ {d}, \forall m \tag {50}"
        r"$$"
    ),
    (
        r"$$"
        r"\sum_ {m = 0} R _ {m} \leq \sum_ {t = 0} \left(E _ {t} - r L _ {t}\right) \tag {51}"
        r"$$"
    ),
]

# Same sum formulas with extra spaces around subscripts/superscripts and braces,
# as typically produced by MinerU-style LaTeX exports.
SUM_FORMULAS_WITH_LOWER_LIMIT_SPACED = [
    (
        r"$$"
        r"\sum _ { d = 0 } C _ { d } \leq C _ { y } \tag {49}"
        r"$$"
    ),
    (
        r"$$"
        r"R _ { m } = \sum _ { d = 0 } R _ { d }, \forall m \tag {50}"
        r"$$"
    ),
    (
        r"$$"
        r"\sum _ { m = 0 } R _ { m } \leq \sum _ { t = 0 } \left(E _ { t } - r L _ { t }\right) \tag {51}"
        r"$$"
    ),
]

# Mixed text from Extract stage (algorithm with inline LaTeX, no $ delimiters)
# Exported MD style: single backslash for LaTeX commands
ALGORITHM_MIXED_TEXT = (
    "ALGORITHM1| Parameter Sensitivity-Based Dispatch Mechanism\n"
    "Require: a_{C},a_{R},a_{E} Ensure: f^{*},x^{*},\\theta^{*} 1: t\\gets t_0 "
    "2: Initialise CR and F_{d} with empty lists \\triangleright Get Initial Parameter Sensitivity   \n"
    "3: while t\\leq T_C do   \n"
    "4: \\mathbf{CR}[\\theta_d],F_d(x,\\theta_d)\\gets \\mathrm{CalculatePS}(a_E);"
    "\\triangleright \\{\\mathrm{Get~all} parameter sensitivity for current t.\\} "
    "5: t\\gets t + 24 6: end while   \n"
    "7: f_0^*,\\theta_0^*\\gets \\mathrm{CER}(a_C,a_R,a_E,\\mathbf{CR},F_d) 8: t\\gets t_0 "
    "9: while t\\leq T_C do \\triangleright {Main loop for dispatch correction}   \n"
    "10: \\mathbf{CR}[\\theta_d],F_d'(\\theta_d)\\gets \\mathrm{CalculatePS}(a_E) "
    "11: F_{d}^{\\prime}(\\theta_{d})\\leftarrow F_{d}^{\\prime}(\\theta_{d}) + \\Omega (\\theta_{d}) "
    "12: \\theta_d^\\prime \\gets \\underset {\\theta_d}{\\mathrm{argmin}}F_d^\\prime (\\theta_d) "
    "13: \\theta_d^* \\gets \\min \\Bigl (\\max \\Bigl (\\theta_d',\\underline{\\theta}\\Bigr),\\overline{\\theta}\\Bigr) "
    "14: f_{d}^{'*,*}\\gets F_{d}^{\\prime}[t,\\theta_{d}^{\\prime,*}] "
    "15: if f_{d}^{\\prime, *} <   f_{d}^{*} then   \n"
    "16: x_{d}^{*}\\gets \\mathrm{Electricity}(a_{E},\\theta_{d}^{'*});"
    "\\triangleright \\{\\mathrm{Calculate~final~solution} with updated \\theta .\\} "
    "17: f_{d}^{*},x_{d}^{*},\\theta_{d}^{*}\\gets f_{d}^{\\prime *},x_{d}^{\\prime *},\\theta_{d}^{\\prime *}; "
    "18: else   \n"
    "19: x_{d}^{*}\\gets \\mathrm{Electricity}(a_{E},\\theta_{d}^{'*});"
    "\\triangleright \\{\\mathrm{Use~solution~from~initial} parameter sensitivity.}   \n"
    "20: end if   \n"
    "21: t\\gets t + 24 22: end while   \n"
    "23: f^{*}\\gets \\sum_{d}^{T_{C}}(f_{d}^{*});"
    "\\triangleright \\{\\mathrm{Sum~up~daily~dispatch~solutions.}\\}"
)


# Use shared mixed-formula helpers (same logic used in markdown_rebuild and DOCX export)
from backend.utils.mixed_formula_text import (
    segment_mixed_text_into_md_segments,
    mixed_text_to_md,
    extract_formula_fragments_from_mixed_text,
)


def _has_latex_omml_libs() -> bool:
    """True if latex2mathml and an OMML converter (mathml2omml_as or mathml2omml) are available."""
    try:
        import latex2mathml.converter  # noqa: F401
    except ImportError:
        return False
    try:
        import mathml2omml_as  # noqa: F401
        return True
    except ImportError:
        pass
    try:
        import mathml2omml  # noqa: F401  # mathml2omml-as package exposes module "mathml2omml"
        return True
    except ImportError:
        return False


def _get_exporter():
    """Create exporter instance to use _normalize_formula_latex and _latex_to_omml."""
    from backend.exporter.md.md2docx_exporter import MD2DOCXExporter, MD2DOCXExporterConfig
    config = MD2DOCXExporterConfig()
    return MD2DOCXExporter(config=config)


def _is_fallback_omml(omml_element, latex_clean: str) -> bool:
    """Return True if the OMML is the fallback (LaTeX stored as plain text in m:t)."""
    if omml_element is None:
        return True
    try:
        text_parts = list(omml_element.itertext())
        combined = "".join(text_parts).strip()
        fallback_text = " ".join(latex_clean.split())
        return combined == fallback_text
    except Exception:
        return False


@pytest.mark.parametrize("latex_with_delimiters", LATEX_FORMULAS_TO_TEST)
@pytest.mark.skipif(not _has_latex_omml_libs(), reason="latex2mathml or mathml2omml_as not installed")
def test_latex_to_omml_conversion_succeeds(latex_with_delimiters: str) -> None:
    """
    Each formula must convert to real OMML (not fallback).
    PDF workflow exports these to DOCX; if conversion fails, they appear as raw LaTeX.
    """
    exporter = _get_exporter()
    latex_clean, _tag = exporter._normalize_formula_latex(latex_with_delimiters)
    assert latex_clean, "normalized LaTeX should be non-empty"

    omml = exporter._latex_to_omml(latex_clean)
    assert omml is not None, (
        f"LaTeX -> OMML must return an element for: {latex_clean[:60]}..."
    )

    assert not _is_fallback_omml(omml, latex_clean), (
        f"Conversion fell back to LaTeX-as-text instead of real OMML for: {latex_clean[:80]}..."
    )


@pytest.mark.skipif(not _has_latex_omml_libs(), reason="latex2mathml or mathml2omml_as not installed")
def test_sum_with_lower_limit_uses_proper_omml_structure() -> None:
    """
    Ensure sum with lower limit (d = 0) is converted to a proper OMML structure
    (typically m:nary or m:limLow), not just a simple right subscript.
    """
    exporter = _get_exporter()
    latex_clean, _tag = exporter._normalize_formula_latex(SUM_WITH_LOWER_LIMIT)
    assert latex_clean, "normalized LaTeX should be non-empty"

    omml = exporter._latex_to_omml(latex_clean)
    assert omml is not None, "LaTeX -> OMML must return an element for sum with lower limit"

    # Basic sanity: should not fall back to plain LaTeX text.
    assert not _is_fallback_omml(
        omml, latex_clean
    ), "Sum with lower limit should not fall back to LaTeX-as-text"

    # Inspect OMML XML to check that we are using a n-ary / lower-limit construct.
    from lxml import etree

    xml = etree.tostring(omml, encoding="unicode")
    # We expect at least one of the canonical lower-limit constructs to appear.
    assert (
        "<m:nary" in xml or "<m:limLow" in xml
    ), "Sum with lower limit should be represented using m:nary or m:limLow in OMML"


@pytest.mark.parametrize("latex_with_delimiters", SUM_FORMULAS_WITH_LOWER_LIMIT)
@pytest.mark.skipif(not _has_latex_omml_libs(), reason="latex2mathml or mathml2omml_as not installed")
def test_additional_sum_formulas_use_proper_omml_structure(latex_with_delimiters: str) -> None:
    """
    Ensure additional sum formulas with lower limits (d = 0, m = 0, t = 0) are
    converted to proper OMML structures with true lower limits, not simple
    right subscripts.
    """
    exporter = _get_exporter()
    latex_clean, _tag = exporter._normalize_formula_latex(latex_with_delimiters)
    assert latex_clean, "normalized LaTeX should be non-empty"

    omml = exporter._latex_to_omml(latex_clean)
    assert omml is not None, "LaTeX -> OMML must return an element for sum formula"

    # Should not fall back to plain LaTeX text.
    assert not _is_fallback_omml(
        omml, latex_clean
    ), "Sum formula with lower limit should not fall back to LaTeX-as-text"

    from lxml import etree

    xml = etree.tostring(omml, encoding="unicode")
    assert (
        "<m:nary" in xml or "<m:limLow" in xml
    ), "Sum formula with lower limit should be represented using m:nary or m:limLow in OMML"


@pytest.mark.parametrize("latex_with_delimiters", SUM_FORMULAS_WITH_LOWER_LIMIT_SPACED)
@pytest.mark.skipif(not _has_latex_omml_libs(), reason="latex2mathml or mathml2omml_as not installed")
def test_sum_formulas_with_extra_spacing_normalize_and_use_proper_omml(latex_with_delimiters: str) -> None:
    """
    Ensure MinerU-style formulas that contain extra spaces around subscripts,
    superscripts, and braces are normalized before OMML conversion and still
    produce proper lower-limit OMML structures instead of right subscripts.
    """
    exporter = _get_exporter()
    latex_clean, _tag = exporter._normalize_formula_latex(latex_with_delimiters)
    assert latex_clean, "normalized LaTeX should be non-empty"
    # Normalized form should not contain obvious " _ " or " ^ " spacing artifacts.
    assert " _ " not in latex_clean
    assert " ^ " not in latex_clean

    omml = exporter._latex_to_omml(latex_clean)
    assert omml is not None, "LaTeX -> OMML must return an element for spaced sum formula"

    assert not _is_fallback_omml(
        omml, latex_clean
    ), "Spaced sum formula with lower limit should not fall back to LaTeX-as-text"

    from lxml import etree

    xml = etree.tostring(omml, encoding="unicode")
    assert (
        "<m:nary" in xml or "<m:limLow" in xml
    ), "Spaced sum formula with lower limit should be represented using m:nary or m:limLow in OMML"


def test_latex_to_omml_formulas_list_not_empty() -> None:
    """Sanity: we have at least one formula to test."""
    assert len(LATEX_FORMULAS_TO_TEST) >= 1


# --- Mixed text (algorithm with inline LaTeX): MD segmentation and OMML ---


def test_mixed_text_to_md_wraps_formulas_in_dollars() -> None:
    """
    From Extract-stage mixed text (no $ delimiters), segment into text + formula
    and build MD so each formula part is wrapped in $...$.
    """
    segments = segment_mixed_text_into_md_segments(ALGORITHM_MIXED_TEXT)
    assert len(segments) >= 1, "should have at least one segment"
    math_segments = [s for is_math, s in segments if is_math]
    assert len(math_segments) >= 3, "algorithm text should contain multiple formula fragments"

    md = mixed_text_to_md(ALGORITHM_MIXED_TEXT)
    assert "Require:" in md and "Ensure:" in md
    # Each math segment must appear in MD wrapped as $segment$
    for frag in math_segments:
        assert f"${frag}$" in md, f"Formula segment {frag[:50]!r}... should appear as $...$ in MD"


# Hand-picked formula fragments from ALGORITHM_MIXED_TEXT for OMML conversion (short, typical)
ALGORITHM_FORMULA_FRAGMENTS_FOR_OMML = [
    r"a_{C}",
    r"a_{R}",
    r"a_{E}",
    r"f^{*}",
    r"x^{*}",
    r"\theta^{*}",
    r"t\gets t_0",
    r"F_{d}",
    r"t\leq T_C",
    r"\theta_d",
    r"\theta_0^*",
    r"\mathbf{CR}",
    r"\mathrm{CalculatePS}(a_E)",
    r"\underline{\theta}",
    r"\overline{\theta}",
]


@pytest.mark.parametrize("latex_fragment", ALGORITHM_FORMULA_FRAGMENTS_FOR_OMML)
@pytest.mark.skipif(not _has_latex_omml_libs(), reason="latex2mathml or mathml2omml_as not installed")
def test_algorithm_formula_fragments_to_omml(latex_fragment: str) -> None:
    """
    Formula fragments extracted from algorithm mixed text must convert to real OMML
    (not LaTeX-as-text fallback).
    """
    exporter = _get_exporter()
    omml = exporter._latex_to_omml(latex_fragment.strip())
    assert omml is not None, (
        f"LaTeX -> OMML must return an element for: {latex_fragment[:60]}..."
    )
    assert not _is_fallback_omml(omml, latex_fragment.strip()), (
        f"Conversion fell back to LaTeX-as-text for: {latex_fragment[:80]}..."
    )


# --- Step: _normalize_formula_latex (PDF->DOCX pipeline step 5.3) ---


@pytest.mark.parametrize(
    "latex_with_delimiters,expected_tag",
    [
        (LATEX_FORMULAS_TO_TEST[0], "8"),
        (LATEX_FORMULAS_TO_TEST[1], "10"),
        (LATEX_FORMULAS_TO_TEST[2], "14"),
    ],
)
def test_normalize_formula_latex_strips_dollars_and_tag(
    latex_with_delimiters: str, expected_tag: str
) -> None:
    """After normalize: no $$ in cleaned LaTeX, \\tag removed, tag text extracted."""
    exporter = _get_exporter()
    cleaned, tag_text = exporter._normalize_formula_latex(latex_with_delimiters)
    assert cleaned, "cleaned LaTeX should be non-empty"
    assert "$$" not in cleaned, "$$ should be stripped"
    assert "\\tag" not in cleaned, "\\tag{...} should be removed from LaTeX"
    assert tag_text == expected_tag, f"tag should be {expected_tag!r}"


# --- Step: layout_document equation extraction (same logic as md2docx_exporter) ---


def test_layout_equation_extraction_produces_latex_for_exporter() -> None:
    """
    Simulate PDF workflow: layout block with interline_equation raw content
    must be extracted to the same LaTeX string the exporter uses for OMML.
    """
    from backend.layout.base import LayoutDocument, LayoutPage, LayoutBlock

    # One of the three formulas as stored in layout (e.g. from MinerU raw)
    latex_from_layout = (
        r"0 \leq P _ {d, t} \leq \left(1 - z _ {t}\right) \bar {P _ {d}} \tag {8}"
    )
    block = LayoutBlock(
        page_index=0,
        bbox=(0, 0, 100, 20),
        type="interline_equation",
        index=0,
        text=latex_from_layout,
        raw={
            "lines": [
                {
                    "spans": [
                        {"type": "interline_equation", "content": latex_from_layout}
                    ]
                }
            ]
        },
    )
    doc = LayoutDocument(
        pages=[LayoutPage(page_index=0, blocks=[block])],
        engine="test",
    )

    # Same collection logic as md2docx_exporter._markdown_to_docx_with_layout
    equation_blocks = []
    for b in doc.iter_blocks():
        if b.type != "interline_equation":
            continue
        equation_content = None
        raw_block = b.raw or {}
        for line in raw_block.get("lines", []):
            if not isinstance(line, dict):
                continue
            for span in line.get("spans", []):
                if not isinstance(span, dict):
                    continue
                if span.get("type") == "interline_equation":
                    content = span.get("content")
                    if isinstance(content, str) and content.strip():
                        equation_content = content.strip()
                        break
            if equation_content:
                break
        if not equation_content and b.text:
            equation_content = b.text.strip()
        if equation_content:
            equation_blocks.append(equation_content)

    assert len(equation_blocks) == 1
    assert equation_blocks[0] == latex_from_layout

    # This string is what gets passed to _add_math_formula -> _normalize_formula_latex -> _latex_to_omml
    exporter = _get_exporter()
    latex_clean, tag_text = exporter._normalize_formula_latex(equation_blocks[0])
    assert "\\tag" not in latex_clean and tag_text == "8"
