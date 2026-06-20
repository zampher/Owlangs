# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

"""Tests for PaddleOCR block label mapping."""

import sys
from pathlib import Path

_OWLANGS = Path(__file__).resolve().parent.parent.parent.parent.parent
if str(_OWLANGS) not in sys.path:
    sys.path.insert(0, str(_OWLANGS))

from layout.ocr_provider.paddle.block_labels import map_paddle_label, PADDLE_LABEL_MAP


def test_all_labels_mapped():
    """Every label returns a valid (block_type, sub_type, tags, should_translate) tuple."""
    for label, (bt, st, tags, tr) in PADDLE_LABEL_MAP.items():
        assert isinstance(bt, str), f"block_type should be str for {label}"
        assert isinstance(st, str), f"sub_type should be str for {label}"
        assert isinstance(tags, list), f"tags should be list for {label}"
        assert isinstance(tr, bool), f"should_translate should be bool for {label}"


def test_text_translatable():
    """text blocks should be translatable."""
    bt, st, tags, tr = map_paddle_label("text")
    assert bt == "text"
    assert st == "body"
    assert tr is True


def test_doc_title():
    """doc_title should be translatable with title tags."""
    bt, st, tags, tr = map_paddle_label("doc_title")
    assert bt == "title"
    assert "heading" in tags
    assert "title" in tags
    assert tr is True


def test_image_skip_translation():
    """image block should not be translated."""
    bt, st, tags, tr = map_paddle_label("image")
    assert "skip_translation" in tags
    assert tr is False


def test_table_not_translatable():
    """table block should not be translated."""
    bt, st, tags, tr = map_paddle_label("table")
    assert bt == "table"
    assert tr is False


def test_formula_not_translatable():
    """formula block should not be translated."""
    bt, st, tags, tr = map_paddle_label("display_formula")
    assert bt == "formula"
    assert tr is False


def test_header_not_translatable():
    """header should not be translated."""
    bt, st, tags, tr = map_paddle_label("header")
    assert "skip_translation" in tags
    assert tr is False


def test_footer_not_translatable():
    """footer should not be translated."""
    bt, st, tags, tr = map_paddle_label("footer")
    assert "skip_translation" in tags
    assert tr is False


def test_unknown_label_defaults():
    """Unknown labels should default to translatable text."""
    bt, st, tags, tr = map_paddle_label("some_unknown_label")
    assert bt == "text"
    assert st == "body"
    assert tr is True


def test_case_insensitive():
    """Label mapping is case-insensitive."""
    bt1, st1, tags1, tr1 = map_paddle_label("Doc_Title")
    bt2, st2, tags2, tr2 = map_paddle_label("doc_title")
    assert bt1 == bt2
    assert tr1 == tr2


def test_whitespace_handled():
    """Labels with surrounding whitespace are handled."""
    bt, st, tags, tr = map_paddle_label("  text  ")
    assert bt == "text"
    assert tr is True


if __name__ == "__main__":
    test_all_labels_mapped()
    test_text_translatable()
    test_doc_title()
    test_image_skip_translation()
    test_table_not_translatable()
    test_formula_not_translatable()
    test_header_not_translatable()
    test_footer_not_translatable()
    test_unknown_label_defaults()
    test_case_insensitive()
    test_whitespace_handled()
    print("Paddle block labels tests passed")
