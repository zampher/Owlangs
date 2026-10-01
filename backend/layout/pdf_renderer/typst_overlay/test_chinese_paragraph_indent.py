# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

"""Tests for Chinese body first-line indent in Typst overlay PDF export."""

from __future__ import annotations

from layout.pdf_renderer.typst_overlay.cjk_paragraph_indent import (
    apply_cjk_body_indent_to_block,
    cjk_body_first_line_indent_em,
    cjk_body_first_line_indent_pt,
    infer_layout_block_type,
    is_cjk_target_language,
    is_single_line_for_cjk_indent,
    resolve_target_language,
    should_apply_cjk_body_indent,
)
from layout.pdf_renderer.typst_overlay.emitter import _render_plain_block
from layout.pdf_renderer.typst_overlay.models import RenderBlock


def _plain_rb(
    *,
    block_id: str = "block-1",
    text: str = "这是一段中文正文。",
    font_size_pt: float = 10.0,
    first_line_indent_pt: float = 0.0,
    first_line_indent_em: float = 0.0,
    render_kind: str = "plain_line",
    font_size_locked: bool = False,
    inner_bbox: tuple[float, float, float, float] = (72.0, 100.0, 400.0, 140.0),
    leading_em: float = 1.25,
    fit_single_line: bool = False,
) -> RenderBlock:
    return RenderBlock(
        block_id=block_id,
        page_index=0,
        inner_bbox=inner_bbox,
        markdown_text=text,
        plain_text=text,
        render_kind=render_kind,
        font_size_pt=font_size_pt,
        first_line_indent_pt=first_line_indent_pt,
        first_line_indent_em=first_line_indent_em,
        font_size_locked=font_size_locked,
        leading_em=leading_em,
        fit_single_line=fit_single_line,
    )


def test_is_cjk_target_language_accepts_chinese_aliases():
    assert is_cjk_target_language("zh")
    assert is_cjk_target_language("zh-CN")
    assert is_cjk_target_language("zh_tw")
    assert is_cjk_target_language("Chinese")
    assert is_cjk_target_language("zh-Hans-CN")
    assert not is_cjk_target_language("en")
    assert not is_cjk_target_language("ja")
    assert not is_cjk_target_language(None)
    assert not is_cjk_target_language("")


def test_cjk_body_first_line_indent_is_two_em():
    assert cjk_body_first_line_indent_em() == 2.0
    assert cjk_body_first_line_indent_pt(10.0) == 20.0
    assert cjk_body_first_line_indent_pt(12.5) == 25.0
    assert cjk_body_first_line_indent_pt(0.0) == 2.0


def test_should_apply_cjk_body_indent_only_body_text():
    assert should_apply_cjk_body_indent(
        block_id="block-3", block_type="text", render_kind="plain",
    )
    assert should_apply_cjk_body_indent(
        block_id="block-3-group-1", block_type="text", render_kind="plain_line",
    )
    assert not should_apply_cjk_body_indent(
        block_id="caption-3", block_type="text", render_kind="plain_line",
    )
    assert not should_apply_cjk_body_indent(
        block_id="block-3", block_type="table_caption", render_kind="plain",
    )
    assert not should_apply_cjk_body_indent(
        block_id="block-3", block_type="image_caption", render_kind="plain",
    )
    assert not should_apply_cjk_body_indent(
        block_id="block-3", block_type="title", render_kind="plain",
    )
    assert not should_apply_cjk_body_indent(
        block_id="block-3", block_type="ref_text", render_kind="plain",
    )
    assert not should_apply_cjk_body_indent(
        block_id="block-3", block_type="text", render_kind="image",
    )


def test_infer_layout_block_type_from_block_id():
    types = {1: "text", 2: "title", 5: "table"}
    assert infer_layout_block_type("block-1", types) == "text"
    assert infer_layout_block_type("block-1-group-0", types) == "text"
    assert infer_layout_block_type("block-1-cross-0", types) == "text"
    assert infer_layout_block_type("block-2", types) == "title"
    assert infer_layout_block_type("caption-5", types) == "caption"
    assert infer_layout_block_type("footnote-5-0", types) == "footnote"


def test_resolve_target_language_prefers_config():
    assert resolve_target_language("zh-CN", {"to_lang": "en"}) == "zh-CN"
    assert resolve_target_language(None, {"to_lang": "zh"}) == "zh"
    assert resolve_target_language(None, {"target_language": "zh-TW"}) == "zh-TW"


def test_resolve_target_language_reads_payload():
    assert resolve_target_language(
        None,
        {"payload": {"to_lang": "zh"}},
    ) == "zh"
    # Payload wins over stale top-level task_state (matches PDF export).
    assert resolve_target_language(
        None,
        {"to_lang": "en", "payload": {"to_lang": "zh"}},
    ) == "zh"
    assert resolve_target_language(
        None,
        {"payload": {"target_language": "Chinese"}},
    ) == "Chinese"


def test_apply_indent_zh_body_text_uses_em():
    rb = _plain_rb(font_size_pt=11.0)
    indent = apply_cjk_body_indent_to_block(
        rb, target_language="zh", layout_block_type="text",
    )
    assert indent == 2.0
    assert rb.first_line_indent_em == 2.0
    assert rb.first_line_indent_pt == 0.0


def test_apply_indent_skips_caption_and_title():
    caption = _plain_rb(block_id="caption-9")
    assert apply_cjk_body_indent_to_block(
        caption, target_language="zh", layout_block_type="table_caption",
    ) == 0.0
    assert caption.first_line_indent_em == 0.0
    assert caption.first_line_indent_pt == 0.0

    title = _plain_rb(block_id="block-2")
    assert apply_cjk_body_indent_to_block(
        title, target_language="zh", layout_block_type="title",
    ) == 0.0
    assert title.first_line_indent_em == 0.0


def test_apply_indent_skips_non_chinese():
    rb = _plain_rb()
    assert apply_cjk_body_indent_to_block(
        rb, target_language="en", layout_block_type="text",
    ) == 0.0
    assert rb.first_line_indent_em == 0.0
    assert rb.first_line_indent_pt == 0.0


def test_is_single_line_for_cjk_indent_uses_font_and_bbox_height():
    # 12pt × 1.25 leading × 1.65 ≈ 24.75pt ceiling for one line
    assert is_single_line_for_cjk_indent(14.0, 12.0, leading_em=1.25)
    assert is_single_line_for_cjk_indent(24.0, 12.0, leading_em=1.25)
    assert not is_single_line_for_cjk_indent(40.0, 12.0, leading_em=1.25)
    assert not is_single_line_for_cjk_indent(14.0, 0.0)
    assert not is_single_line_for_cjk_indent(0.0, 12.0)


def test_apply_indent_skips_single_line_bbox_at_real_font_size():
    # Glyph-tight single-line bbox (~14pt tall at 12pt) must not reserve 2em.
    rb = _plain_rb(
        font_size_pt=12.0,
        inner_bbox=(72.0, 100.0, 400.0, 114.0),
    )
    assert apply_cjk_body_indent_to_block(
        rb, target_language="zh", layout_block_type="text",
    ) == 0.0
    assert rb.first_line_indent_em == 0.0
    assert rb.first_line_indent_pt == 0.0


def test_apply_indent_skips_fit_single_line_flag():
    rb = _plain_rb(
        font_size_pt=11.0,
        # Tall enough to look multi-line by height alone
        inner_bbox=(72.0, 100.0, 400.0, 140.0),
        fit_single_line=True,
    )
    assert apply_cjk_body_indent_to_block(
        rb, target_language="zh", layout_block_type="text",
    ) == 0.0
    assert rb.first_line_indent_em == 0.0


def test_apply_indent_keeps_multiline_body():
    # Default fixture height 40pt at 11pt is clearly multi-line → keep 2em.
    rb = _plain_rb(font_size_pt=11.0)
    assert apply_cjk_body_indent_to_block(
        rb, target_language="zh", layout_block_type="text",
    ) == 2.0
    assert rb.first_line_indent_em == 2.0


def test_emitter_short_path_emits_h_em_indent():
    rb = _plain_rb(
        text="短段正文",
        font_size_pt=10.0,
        first_line_indent_em=2.0,
    )
    src = _render_plain_block(rb.block_id, rb)
    assert "h(2.0em)" in src or "h(2em)" in src


def test_emitter_long_path_emits_first_line_indent_em():
    long_text = "这是一段较长的中文正文，用来触发 plain 长路径拟合渲染逻辑。" * 2
    assert len(long_text) > 40
    rb = _plain_rb(
        text=long_text,
        font_size_pt=10.0,
        first_line_indent_em=2.0,
        render_kind="plain",
    )
    src = _render_plain_block(rb.block_id, rb)
    assert (
        "first_line_indent: 2.0em" in src
        or "first_line_indent: 2em" in src
        or "h(2.0em)" in src
        or "h(2em)" in src
    )


def test_emitter_locked_short_path_emits_h_em_indent():
    rb = _plain_rb(
        text="锁定字号短段",
        font_size_pt=12.0,
        first_line_indent_em=2.0,
        font_size_locked=True,
    )
    src = _render_plain_block(rb.block_id, rb)
    assert "h(2.0em)" in src or "h(2em)" in src


def test_emitter_legacy_pt_indent_still_works():
    rb = _plain_rb(
        text="短段正文",
        font_size_pt=10.0,
        first_line_indent_pt=20.0,
    )
    src = _render_plain_block(rb.block_id, rb)
    assert "h(20.0pt)" in src or "h(20pt)" in src


def test_attach_min_font_avoids_fill_fit_false_single_line():
    """Fill-fit computed≈80pt must not zero indent when extracted=12 on tall body."""
    from types import SimpleNamespace

    from layout.pdf_renderer.typst_overlay.segment_font_metrics import (
        attach_segment_first_line_indent_em,
    )

    # Body bbox height 147pt (matches task 0df83590-style override).
    segment = {
        "computed_font_size_pt": 80.0,
        "extracted_font_size_pt": 12.0,
        "computed_leading_em": 1.25,
        "layout_block_bbox": [72.0, 296.0, 538.0, 443.0],
        "to_lang": "en",  # stale — must be ignored when payload is zh
    }
    block = SimpleNamespace(bbox=(72.0, 296.0, 538.0, 443.0))
    task_state = {
        "to_lang": "en",
        "payload": {"to_lang": "zh"},
    }
    attach_segment_first_line_indent_em(
        segment,
        block,
        block_type="text",
        block_idx=3,
        task_state=task_state,
    )
    assert segment["computed_first_line_indent_em"] == 2.0
    assert segment["first_line_indent_em"] == 2.0
    assert segment["first_line_indent_em_source"] == "auto"


def test_attach_fill_fit_only_still_indents_tall_body():
    """When only fill-fit computed exists, cap to typical body for the gate."""
    from types import SimpleNamespace

    from layout.pdf_renderer.typst_overlay.segment_font_metrics import (
        attach_segment_first_line_indent_em,
    )

    segment = {
        "computed_font_size_pt": 90.0,
        "computed_leading_em": 1.25,
        "layout_block_bbox": [72.0, 296.0, 538.0, 443.0],
    }
    block = SimpleNamespace(bbox=(72.0, 296.0, 538.0, 443.0))
    task_state = {"payload": {"to_lang": "Chinese"}}
    attach_segment_first_line_indent_em(
        segment,
        block,
        block_type="text",
        block_idx=3,
        task_state=task_state,
    )
    assert segment["computed_first_line_indent_em"] == 2.0


def test_attach_true_single_line_stays_zero():
    """Glyph-tight single line must remain 无 (0em)."""
    from types import SimpleNamespace

    from layout.pdf_renderer.typst_overlay.segment_font_metrics import (
        attach_segment_first_line_indent_em,
    )

    segment = {
        "computed_font_size_pt": 12.0,
        "extracted_font_size_pt": 12.0,
        "computed_leading_em": 1.25,
        "layout_block_bbox": [72.0, 100.0, 400.0, 114.0],  # h=14
    }
    block = SimpleNamespace(bbox=(72.0, 100.0, 400.0, 114.0))
    task_state = {"payload": {"to_lang": "zh"}}
    attach_segment_first_line_indent_em(
        segment,
        block,
        block_type="text",
        block_idx=1,
        task_state=task_state,
    )
    assert segment["computed_first_line_indent_em"] == 0.0
    assert segment["first_line_indent_em"] == 0.0


def test_attach_medium_box_indents_with_8pt_fallback():
    """Medium body (h≈20pt) needs ~8pt gate to match export post-fit indent."""
    from types import SimpleNamespace

    from layout.pdf_renderer.typst_overlay.segment_font_metrics import (
        attach_segment_first_line_indent_em,
    )

    # h=20: single-line at 12pt (threshold≈24.75) but multi-line at 8pt (≈16.5).
    segment = {
        "computed_font_size_pt": 16.0,  # ≈ fill-fit for h=20 / 1.25
        "extracted_font_size_pt": 14.0,  # still single-line at h=20
        "computed_leading_em": 1.25,
        "layout_block_bbox": [72.0, 100.0, 400.0, 120.0],
    }
    block = SimpleNamespace(bbox=(72.0, 100.0, 400.0, 120.0))
    task_state = {"payload": {"to_lang": "zh"}}
    attach_segment_first_line_indent_em(
        segment,
        block,
        block_type="text",
        block_idx=5,
        task_state=task_state,
    )
    assert segment["computed_first_line_indent_em"] == 2.0
    assert segment["first_line_indent_em"] == 2.0


def test_attach_ignores_stale_fit_single_line_flag():
    """Stale segment fit_single_line must not zero multi-line body indent."""
    from types import SimpleNamespace

    from layout.pdf_renderer.typst_overlay.segment_font_metrics import (
        attach_segment_first_line_indent_em,
    )

    segment = {
        "computed_font_size_pt": 12.0,
        "extracted_font_size_pt": 12.0,
        "computed_leading_em": 1.25,
        "fit_single_line": True,
        "layout_block_bbox": [72.0, 296.0, 538.0, 443.0],  # h=147
    }
    block = SimpleNamespace(bbox=(72.0, 296.0, 538.0, 443.0))
    task_state = {"payload": {"to_lang": "zh"}}
    attach_segment_first_line_indent_em(
        segment,
        block,
        block_type="text",
        block_idx=3,
        task_state=task_state,
    )
    assert segment["computed_first_line_indent_em"] == 2.0


def test_attach_preserves_user_override():
    from types import SimpleNamespace

    from layout.pdf_renderer.typst_overlay.segment_font_metrics import (
        attach_segment_first_line_indent_em,
    )

    segment = {
        "computed_font_size_pt": 12.0,
        "layout_block_bbox": [72.0, 296.0, 538.0, 443.0],
        "first_line_indent_em": 0.0,
        "first_line_indent_em_source": "user",
    }
    block = SimpleNamespace(bbox=(72.0, 296.0, 538.0, 443.0))
    task_state = {"payload": {"to_lang": "zh"}}
    attach_segment_first_line_indent_em(
        segment,
        block,
        block_type="text",
        block_idx=3,
        task_state=task_state,
    )
    assert segment["computed_first_line_indent_em"] == 2.0
    assert segment["first_line_indent_em"] == 0.0
    assert segment["first_line_indent_em_source"] == "user"
