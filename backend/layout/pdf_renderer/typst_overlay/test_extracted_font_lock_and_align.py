# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

"""Extracted PDF font lock + single-line LTR/RTL alignment."""

from __future__ import annotations

from types import SimpleNamespace

from layout.pdf_renderer.typst_overlay.cjk_paragraph_indent import (
    is_rtl_target_language,
    resolve_single_line_horizontal_align,
)
from layout.pdf_renderer.typst_overlay.emitter import (
    _render_markdown_block,
    _render_plain_block,
)
from layout.pdf_renderer.typst_overlay.font_fit import FontFitCalculator
from layout.pdf_renderer.typst_overlay.models import (
    RenderBlock,
    layout_block_to_render_block,
)


def test_rtl_language_resolves_right_align():
    assert is_rtl_target_language("ar")
    assert is_rtl_target_language("he-IL")
    assert resolve_single_line_horizontal_align("ar") == "right"
    assert resolve_single_line_horizontal_align("zh") == "left"
    assert resolve_single_line_horizontal_align("en") == "left"


def test_extracted_font_size_locks_render_block(monkeypatch):
    monkeypatch.setattr(
        "layout.pdf_font_extractor.resolve_prefer_extracted_pdf_font_size",
        lambda *_a, **_k: True,
    )
    layout_block = SimpleNamespace(
        index=3,
        bbox=(100.0, 200.0, 400.0, 220.0),
        type="text",
        heading_level=0,
        raw={"extracted_font_size": 11.5, "extracted_font_size_source": "pdf"},
    )
    rb = layout_block_to_render_block(
        layout_block,
        page_index=0,
        translated_text="Locked extracted size",
        block_id="block-3",
    )
    assert rb.font_size_pt == 11.5
    assert rb.font_size_locked is True

    fitted = FontFitCalculator().calculate_fit_params(rb)
    assert fitted.font_size_pt == 11.5
    assert fitted.font_size_locked is True
    assert fitted.fit_to_box is False
    # Single-line locked body: stay on one line (extend if needed), never wrap-fit.
    assert fitted.fit_single_line is True


def test_locked_multiline_leading_uses_real_font_and_bbox():
    """Multi-line locked body leading must come from font×bbox, not the 1.25 table."""
    from layout.pdf_renderer.typst_overlay.font_fit import (
        BODY_LINE_METRICS_EM,
        quantize_body_leading_em,
    )
    from layout.pdf_renderer.typst_overlay.text_metrics import estimate_wrap_line_count

    font_size = 10.0
    # Tall multi-line bbox (~48pt) with real locked font — leading must be
    # solved from wrap lines at that font, not estimate_leading()'s 1.25.
    bbox = (72.0, 100.0, 320.0, 148.0)
    text = (
        "这是一段需要在固定字号下自动折成多行的中文正文，"
        "用来验证行间距会根据真字号和bbox高度重新计算。"
    )
    block = RenderBlock(
        block_id="body-ml-lock",
        page_index=0,
        inner_bbox=bbox,
        plain_text=text,
        markdown_text=text,
        font_size_pt=font_size,
        font_size_locked=True,
        leading_em=1.25,  # old default — must be replaced
    )
    layout_raw = {"type": "text"}
    fitted = FontFitCalculator().calculate_fit_params(
        block, layout_raw=layout_raw, page_width_pt=612.0,
    )
    assert fitted.font_size_locked is True
    assert fitted.fit_single_line is False
    assert fitted.leading_em_locked is True
    assert fitted.leading_em != 1.25

    # Recompute on the (possibly edge-shrunk) fitted bbox.
    expected = FontFitCalculator().estimate_body_leading_em_at_font(
        fitted, font_size, layout_raw=layout_raw,
    )
    assert fitted.leading_em == expected

    x0, y0, x1, y1 = fitted.inner_bbox
    wrap_lines = estimate_wrap_line_count(
        text, x1 - x0, font_size, layout_raw,
    )
    visual_lines = max(1, int(wrap_lines + 0.999999))
    assert visual_lines >= 2
    formula = quantize_body_leading_em(
        ((y1 - y0) - visual_lines * font_size * BODY_LINE_METRICS_EM)
        / ((visual_lines - 1) * font_size)
    )
    assert fitted.leading_em == formula


def test_locked_multiline_refits_font_when_overflow_exceeds_10_percent():
    """First-glyph-sized lock that overflows multi-line bbox by >10% must shrink."""
    from layout.pdf_renderer.typst_overlay.font_fit import (
        BODY_LEADING_EM_MIN,
        LOCKED_MULTILINE_HEIGHT_OVERFLOW_RATIO,
        estimate_body_content_height_pt,
    )

    # Clearly multi-line vs font-aware gate (12pt × 1.25 × 1.65 ≈ 24.8),
    # but locked size still overflows height at minimum leading.
    bbox = (72.0, 100.0, 220.0, 148.0)  # height 48pt
    text = (
        "超大首字号导致多行正文在最小行距下仍明显超出原始段落高度，"
        "因此需要触发保底重算字号逻辑，继续加长这段中文以保证折行足够多。"
    )
    locked_pt = 16.0
    block = RenderBlock(
        block_id="body-ml-overflow",
        page_index=0,
        inner_bbox=bbox,
        plain_text=text,
        markdown_text=text,
        font_size_pt=locked_pt,
        font_size_locked=True,
    )
    layout_raw = {"type": "text"}
    calc = FontFitCalculator()
    # Sanity: locked size really overflows the gate before fit.
    overflow_h = estimate_body_content_height_pt(
        text, bbox[2] - bbox[0], locked_pt, BODY_LEADING_EM_MIN, layout_raw,
    )
    assert overflow_h > (bbox[3] - bbox[1]) * LOCKED_MULTILINE_HEIGHT_OVERFLOW_RATIO

    fitted = calc.calculate_fit_params(
        block, layout_raw=layout_raw, page_width_pt=612.0,
    )
    assert fitted.fit_single_line is False
    assert fitted.font_size_locked is True
    assert fitted.font_size_pt < locked_pt

    # After refit, content at the new size should fit the (possibly shrunk) bbox.
    x0, y0, x1, y1 = fitted.inner_bbox
    fitted_h = estimate_body_content_height_pt(
        text, x1 - x0, fitted.font_size_pt, fitted.leading_em, layout_raw,
    )
    assert fitted_h <= (y1 - y0) * LOCKED_MULTILINE_HEIGHT_OVERFLOW_RATIO + 0.5


def test_locked_multiline_keeps_font_when_within_overflow_budget():
    """Fitting locked size must not be needlessly reduced."""
    font_size = 10.0
    bbox = (72.0, 100.0, 360.0, 160.0)
    text = "短一些的多行正文在真字号下应当保留提取字号。"
    block = RenderBlock(
        block_id="body-ml-keep",
        page_index=0,
        inner_bbox=bbox,
        plain_text=text,
        markdown_text=text,
        font_size_pt=font_size,
        font_size_locked=True,
    )
    fitted = FontFitCalculator().calculate_fit_params(
        block, layout_raw={"type": "text"}, page_width_pt=612.0,
    )
    assert fitted.fit_single_line is False
    assert fitted.font_size_pt == font_size


def test_single_line_body_extends_instead_of_wrapping():
    """Wide overflow on a short bbox must prefer horizontal extend, not wrap."""
    page_w = 612.0
    bbox = (72.0, 100.0, 200.0, 114.0)  # ~14pt tall → single-line
    text = "这是一段明显超出原始单行宽度的中文译文内容需要延申"
    block = RenderBlock(
        block_id="body-sl",
        page_index=0,
        inner_bbox=bbox,
        plain_text=text,
        markdown_text=text,
        font_size_pt=12.0,
    )
    fitted = FontFitCalculator().calculate_fit_params(
        block, layout_raw={"type": "text"}, page_width_pt=page_w,
    )
    assert fitted.fit_single_line is True
    assert fitted.fit_to_box is True
    assert fitted.fit_target_width_pt > (bbox[2] - bbox[0])


def test_real_font_tall_single_line_extends_not_wraps():
    """
    Extracted large fonts often yield single-line bboxes taller than the legacy
    32pt gate; those must still extend horizontally instead of wrapping.
    """
    page_w = 612.0
    # 18pt × 1.25 × 1.65 ≈ 37.1 → font-aware single-line, but > 32pt fixed gate.
    bbox = (72.0, 100.0, 220.0, 134.0)  # height 34pt
    text = "真字号单行超宽译文必须同行延申而不是折到第二行"
    block = RenderBlock(
        block_id="body-sl-tall",
        page_index=0,
        inner_bbox=bbox,
        plain_text=text,
        markdown_text=text,
        font_size_pt=18.0,
        font_size_locked=True,
    )
    fitted = FontFitCalculator().calculate_fit_params(
        block, layout_raw={"type": "text"}, page_width_pt=page_w,
    )
    assert fitted.fit_single_line is True
    assert fitted.fit_target_width_pt > (bbox[2] - bbox[0])
    src = _render_plain_block("block-sl-tall", fitted)
    assert "clip: false" in src
    assert "pdftr_fit_markdown(" not in src


def test_locked_single_line_overflow_emits_nowrap_and_extended_width():
    text = "单行锁定字号超宽译文应当同行延申而不是自动换行"
    block = RenderBlock(
        block_id="b-lock-sl",
        page_index=0,
        inner_bbox=(72.0, 100.0, 180.0, 114.0),
        plain_text=text,
        markdown_text=text,
        font_size_pt=12.0,
        font_size_locked=True,
        fit_single_line=True,
        fit_target_width_pt=320.0,
        render_kind="plain_line",
        horizontal_align="left",
    )
    src = _render_plain_block("block-lock-sl", block)
    assert "clip: false" in src
    assert "measure(" in src
    assert "pdftr_fit_markdown(" not in src


def test_recipe_line_locked_emits_measure_based_single_line():
    """Mixed CJK/Latin recipe lines must measure natural width (no soft wrap)."""
    text = "1/2  杯（120毫升）干红葡萄酒"
    block = RenderBlock(
        block_id="recipe",
        page_index=0,
        inner_bbox=(72.0, 200.0, 172.0, 214.0),
        plain_text=text,
        markdown_text=text,
        font_size_pt=11.0,
        font_size_locked=True,
        render_kind="plain_line",
    )
    fitted = FontFitCalculator().calculate_fit_params(
        block, layout_raw={"type": "text"}, page_width_pt=612.0,
    )
    assert fitted.fit_single_line is True
    assert fitted.fit_target_width_pt > 100.0
    src = _render_plain_block("block-recipe", fitted)
    assert "measure(" in src
    assert "calc.max(" in src
    assert "pdftr_fit_markdown(" not in src
    assert "scaled-font" not in src


def test_single_line_fit_emits_left_align_not_center():
    block = RenderBlock(
        block_id="b-sl",
        page_index=0,
        inner_bbox=(10.0, 20.0, 300.0, 36.0),
        markdown_text="Single line title",
        plain_text="Single line title",
        font_size_pt=12.0,
        fit_to_box=True,
        fit_single_line=True,
        fit_min_font_size_pt=8.0,
        fit_max_font_size_pt=12.0,
        horizontal_align="left",
    )
    src = _render_markdown_block("block-sl", block)
    assert "h_align: left" in src
    assert "h_align: center" not in src


def test_locked_plain_line_uses_horizontal_align():
    block = RenderBlock(
        block_id="b-rtl",
        page_index=0,
        inner_bbox=(0.0, 0.0, 200.0, 22.0),
        plain_text="نص قصير",
        markdown_text="نص قصير",
        font_size_pt=14.0,
        font_size_locked=True,
        render_kind="plain_line",
        horizontal_align="right",
    )
    src = _render_plain_block("block-rtl", block)
    assert "align(right + horizon)" in src
    assert "14.0pt" in src
