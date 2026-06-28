# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

"""Tests for MOBI template HTML replacement order (duplicate segment texts)."""

import pytest

from utils.epub_html_segments import (
    EpubSegmentReplacementError,
    apply_segment_translations_to_html,
    apply_segment_translations_to_html_with_stats,
    rebuild_mobi_segment_mapping_from_cache,
    require_segment_replacements,
)


def test_duplicate_page_numbers_replaced_in_document_order():
    html = (
        "<p>13</p><p>Rima I</p><p>body one</p>"
        "<p>13</p><p>Rima II</p><p>body two</p>"
    )
    segments = [
        {"segment_id": 0, "item_id": "ch1", "original_text": "13"},
        {"segment_id": 1, "item_id": "ch1", "original_text": "Rima I"},
        {"segment_id": 2, "item_id": "ch1", "original_text": "body one"},
        {"segment_id": 3, "item_id": "ch1", "original_text": "13"},
        {"segment_id": 4, "item_id": "ch1", "original_text": "Rima II"},
        {"segment_id": 5, "item_id": "ch1", "original_text": "body two"},
    ]
    translated = {
        0: "P-A",
        1: "诗 I",
        2: "正文一",
        3: "P-B",
        4: "诗 II",
        5: "正文二",
    }
    out = apply_segment_translations_to_html(html, segments, translated)
    assert out.index("P-A") < out.index("诗 I") < out.index("P-B") < out.index("诗 II")
    assert "P-A" in out and "P-B" in out
    assert "<p>13</p>" not in out


def test_poem_lines_stay_in_order_after_replacement():
    html = "<p>Line A</p><p>Line B</p><p>Line C</p>"
    segments = [
        {"segment_id": 0, "item_id": "ch1", "original_text": "Line A"},
        {"segment_id": 1, "item_id": "ch1", "original_text": "Line B"},
        {"segment_id": 2, "item_id": "ch1", "original_text": "Line C"},
    ]
    translated = {0: "行A", 1: "行B", 2: "行C"}
    out = apply_segment_translations_to_html(html, segments, translated)
    assert "行A" in out and "行B" in out and "行C" in out
    assert out.index("行A") < out.index("行B") < out.index("行C")


def test_repeated_short_line_does_not_shift_next_segment():
    html = "<p>same</p><p>unique-172</p><p>same</p><p>unique-173</p>"
    segments = [
        {"segment_id": 170, "item_id": "ch1", "original_text": "same"},
        {"segment_id": 171, "item_id": "ch1", "original_text": "unique-172"},
        {"segment_id": 172, "item_id": "ch1", "original_text": "same"},
        {"segment_id": 173, "item_id": "ch1", "original_text": "unique-173"},
    ]
    translated = {
        170: "同-A",
        171: "译-172",
        172: "同-B",
        173: "译-173",
    }
    out = apply_segment_translations_to_html(html, segments, translated)
    assert "译-172" in out
    assert "译-173" in out
    assert "unique-172" not in out
    assert "unique-173" not in out
    assert out.index("译-172") < out.index("译-173")


def test_require_segment_replacements_raises_on_miss():
    with pytest.raises(EpubSegmentReplacementError):
        require_segment_replacements(1, 2, item_id="ch1", task_id="task-x")


def test_br_paragraph_text_not_in_raw_html_counts_as_missed():
    html = "<p>alpha<br/>beta</p>"
    segments = [
        {"segment_id": 0, "item_id": "ch1", "original_text": "alpha\nbeta"},
    ]
    translated = {0: "trans-AB"}
    _, applied, missed = apply_segment_translations_to_html_with_stats(
        html, segments, translated,
    )
    assert applied == 1
    assert missed == 0


def test_html_entity_unescape_allows_replacement():
    html = "<p>B&eacute;cquer</p>"
    segments = [
        {"segment_id": 0, "item_id": "ch1", "original_text": "Bécquer"},
    ]
    translated = {0: "贝克尔"}
    out = apply_segment_translations_to_html(html, segments, translated)
    assert "贝克尔" in out
    assert "B&eacute;cquer" not in out


def test_excluded_segments_are_skipped_not_missed():
    html = "<p>13</p><p>hello</p>"
    segments = [
        {"segment_id": 0, "item_id": "ch1", "original_text": "13"},
        {"segment_id": 1, "item_id": "ch1", "original_text": "hello"},
    ]
    translated = {0: "13", 1: "你好"}
    _, applied, missed = apply_segment_translations_to_html_with_stats(
        html,
        segments,
        translated,
        excluded_segment_ids={0},
    )
    assert applied == 1
    assert missed == 0


def test_rebuild_mobi_segment_mapping_uses_cache_texts():
    html = "<p>Line A</p><p>Line B</p>"
    task_state = {
        "source_chunks_cache": {
            "chunk_size": 8000,
            "segments": ["Line A", "Line B"],
            "total_segments": 2,
        },
    }
    mapping = rebuild_mobi_segment_mapping_from_cache(
        task_state,
        {"chapter_0": html},
        fallback_mapping=[
            {"segment_id": 0, "item_id": "chapter_0", "original_text": "wrong"},
            {"segment_id": 1, "item_id": "chapter_0", "original_text": "wrong"},
            {"segment_id": 2, "item_id": "chapter_0", "original_text": "extra"},
        ],
    )
    assert len(mapping) == 2
    assert mapping[0]["original_text"] == "Line A"
    assert mapping[1]["original_text"] == "Line B"
    assert mapping[0]["segment_id"] == 0
    assert mapping[1]["segment_id"] == 1


def test_untranslated_ocr_garbage_skipped_not_missed():
    html = "<p>Eievie<br/>~2026-27495-6<br/>Shooke</p>"
    segments = [
        {
            "segment_id": 1663,
            "item_id": "ch1",
            "original_text": "Eievie\n~2026-27495-6\nShooke",
        },
    ]
    translated = {1663: "Eievie\n~2026-27495-6\nShooke"}
    _, applied, missed = apply_segment_translations_to_html_with_stats(
        html, segments, translated,
    )
    assert applied == 0
    assert missed == 0


def test_ocr_typo_cache_text_still_replaces_via_dom():
    html = "<p>De aquella muda y pálida</p>"
    segments = [
        {
            "segment_id": 1654,
            "item_id": "ch1",
            "original_text": "De aqulla muda y pálida",
        },
    ]
    translated = {1654: "想起那个沉默而苍白的"}
    out = apply_segment_translations_to_html(html, segments, translated, chunk_size=8000)
    assert "想起那个沉默而苍白的" in out
    assert "aquella" not in out


def test_skip_same_source_advances_cursor_before_longer_text():
    """Failed / no-op segments must advance cursor to avoid substring false matches."""
    html = "<p>I</p><p>In the garden</p>"
    segments = [
        {"segment_id": 0, "item_id": "ch1", "original_text": "I"},
        {"segment_id": 1, "item_id": "ch1", "original_text": "In the garden"},
    ]
    translated = {0: "I", 1: "在花园里"}
    out, applied, missed = apply_segment_translations_to_html_with_stats(
        html, segments, translated,
    )
    assert "在花园里" in out
    assert applied == 1
    assert missed == 0


def test_failed_same_source_between_duplicates_no_misalignment():
    long_line = "Esta es una linea larga de prueba"
    html = f"<p>{long_line}</p><p>middle</p><p>{long_line}</p>"
    segments = [
        {"segment_id": 0, "item_id": "ch1", "original_text": long_line},
        {"segment_id": 1, "item_id": "ch1", "original_text": "middle"},
        {"segment_id": 2, "item_id": "ch1", "original_text": long_line},
    ]
    translated = {0: long_line, 1: "中间", 2: long_line}
    out, applied, missed = apply_segment_translations_to_html_with_stats(
        html, segments, translated,
    )
    assert "中间" in out
    assert applied == 1
    assert missed == 0


def test_excluded_duplicate_short_segments_advance_cursor():
    html = "<p>13</p><p>unique-line</p><p>13</p>"
    segments = [
        {"segment_id": 0, "item_id": "ch1", "original_text": "13"},
        {"segment_id": 1, "item_id": "ch1", "original_text": "unique-line"},
        {"segment_id": 2, "item_id": "ch1", "original_text": "13"},
    ]
    translated = {0: "13", 1: "唯一行", 2: "13"}
    out, applied, missed = apply_segment_translations_to_html_with_stats(
        html,
        segments,
        translated,
        excluded_segment_ids={0, 2},
    )
    assert "唯一行" in out
    assert applied == 1
    assert missed == 0


def test_image_segment_advances_cursor_past_img_tag():
    html = (
        "<p>Title</p>"
        '<p><img src="Images/image00044.jpeg" alt="cover"/></p>'
        "<p>After image</p>"
    )
    segments = [
        {"segment_id": 0, "item_id": "ch1", "original_text": "Title"},
        {
            "segment_id": 1,
            "item_id": "ch1",
            "original_text": "[Image: Images/image00044.jpeg]",
        },
        {"segment_id": 2, "item_id": "ch1", "original_text": "After image"},
    ]
    translated = {0: "标题", 1: "[Image: Images/image00044.jpeg]", 2: "图片之后"}
    out, applied, missed = apply_segment_translations_to_html_with_stats(
        html, segments, translated,
    )
    assert "标题" in out
    assert "图片之后" in out
    assert applied == 2
    assert missed == 0


def test_blockquote_inline_tags_match_cache_without_spaces():
    html = (
        "<blockquote><b>Índice</b><font size=\"2\">(no listados originalmente)</font></blockquote>"
    )
    segments = [
        {
            "segment_id": 0,
            "item_id": "ch1",
            "original_text": "Índice(no listados originalmente)",
        },
    ]
    translated = {0: "目录（原书未列）"}
    out, applied, missed = apply_segment_translations_to_html_with_stats(
        html, segments, translated,
    )
    assert "目录（原书未列）" in out
    assert applied == 1
    assert missed == 0


def test_trailing_toc_segments_replaced_when_dom_pairs_exhausted():
    """Tail TOC entries must still replace via find fallback (Rima LXXVI / Sobre)."""
    html = (
        "<p>Rima LXXIV</p><p>Rima LXXV</p>"
        "<p>Rima LXXVI</p><p>Sobre el autor</p>"
    )
    segments = [
        {"segment_id": 1746, "item_id": "ch1", "original_text": "Rima LXXIV"},
        {"segment_id": 1747, "item_id": "ch1", "original_text": "Rima LXXV"},
        {"segment_id": 1748, "item_id": "ch1", "original_text": "Rima LXXVI"},
        {"segment_id": 1749, "item_id": "ch1", "original_text": "Sobre"},
    ]
    translated = {
        1746: "韵诗 LXXIV",
        1747: "韵诗 LXXV",
        1748: "韵诗 LXXVI",
        1749: "关于",
    }
    out, applied, missed = apply_segment_translations_to_html_with_stats(
        html, segments, translated,
    )
    assert missed == 0
    assert applied == 4
    assert "韵诗 LXXVI" in out
    assert "关于" in out


def test_dom_replacements_preserved_when_tail_find_runs():
    """DOM edits must not be discarded when a later tail find pass also runs."""
    html = "<p>Hello</p><p>Tail text</p>"
    segments = [
        {"segment_id": 0, "item_id": "ch1", "original_text": "Hello"},
        {"segment_id": 1, "item_id": "ch1", "original_text": "Tail text"},
    ]
    translated = {0: "你好", 1: "尾部"}
    out, applied, missed = apply_segment_translations_to_html_with_stats(
        html, segments, translated,
    )
    assert missed == 0
    assert applied == 2
    assert "你好" in out
    assert "尾部" in out


def test_build_translated_segments_map_bilingual_merges_source_and_target():
    from utils.epub_html_segments import build_translated_segments_map

    mapping = [
        {"segment_id": 0, "item_id": "ch1", "original_text": "Hola"},
        {"segment_id": 1, "item_id": "ch1", "original_text": "Mundo"},
    ]
    task_state = {
        "bilingual_export": True,
        "bilingual_order": "target_after_source",
        "source_text_italic": True,
        "target_text_color": "black",
        "translation_segments": {
            "segments": [
                {"target_text": "你好"},
                {"target_text": "世界"},
            ],
        },
    }
    result = build_translated_segments_map(mapping, task_state)
    assert 0 in result and 1 in result
    assert "Hola" in result[0]
    assert "你好" in result[0]
    assert "Mundo" in result[1]
    assert "世界" in result[1]
    assert 'style="font-style:italic"' in result[0]


def test_bilingual_html_spans_render_in_dom_replacement():
    html = "<p>Line A</p>"
    segments = [{"segment_id": 0, "item_id": "ch1", "original_text": "Line A"}]
    translated = {
        0: (
            '<span style="color:#000000">译A</span><br/><br/>'
            '<span style="font-style:italic;color:#808080">Line A</span>'
        ),
    }
    out = apply_segment_translations_to_html(html, segments, translated)
    assert "译A" in out
    assert "Line A" in out
    assert "<span" in out
    assert "&lt;span" not in out


def test_is_valid_mobi_bytes_rejects_epub_zip():
    from utils.ebook_mobi_utils import (
        is_epub_zip_bytes,
        is_valid_mobi_bytes,
        mobi_ident_at_offset,
    )

    epub_like = b"PK\x03\x04\x14\x00\x00\x00\x08\x00" + b"\x00" * 80
    assert is_epub_zip_bytes(epub_like)
    assert not is_valid_mobi_bytes(epub_like)
    assert mobi_ident_at_offset(epub_like) not in {b"BOOKMOBI", b"TEXTREAD"}

    # Calibre writer puts BOOKMOBI at offset 60 (after 32-byte title + 28-byte PalmDB fields)
    palm_header = b"Rimas_Book".ljust(32, b"\0") + b"\0" * 28 + b"BOOKMOBI" + b"\0" * 64
    assert is_valid_mobi_bytes(palm_header)
    assert mobi_ident_at_offset(palm_header) == b"BOOKMOBI"
