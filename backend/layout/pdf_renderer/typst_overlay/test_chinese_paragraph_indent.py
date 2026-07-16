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
) -> RenderBlock:
    return RenderBlock(
        block_id=block_id,
        page_index=0,
        inner_bbox=(72.0, 100.0, 400.0, 140.0),
        markdown_text=text,
        plain_text=text,
        render_kind=render_kind,
        font_size_pt=font_size_pt,
        first_line_indent_pt=first_line_indent_pt,
        first_line_indent_em=first_line_indent_em,
        font_size_locked=font_size_locked,
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
