# SPDX-License-Identifier: AGPL-3.0-or-later
"""Tests for preserving dynamic page numbers in header/footer tables."""

from __future__ import annotations

from lxml import etree

from converter.x2md.docx_extras import (
    _paragraph_has_page_field,
    _paragraph_should_preserve_pagination,
    text_looks_like_page_number_display,
)


def test_text_looks_like_page_number_display() -> None:
    assert text_looks_like_page_number_display("1/16")
    assert text_looks_like_page_number_display("16 / 16")
    assert text_looks_like_page_number_display("3 of 10")
    assert not text_looks_like_page_number_display("Page Number")
    assert not text_looks_like_page_number_display("AMVR-2104 (2026)")


def test_paragraph_has_page_field() -> None:
    ns = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
    p = etree.Element(f"{{{ns}}}p")
    r = etree.SubElement(p, f"{{{ns}}}r")
    instr = etree.SubElement(r, f"{{{ns}}}instrText")
    instr.text = " PAGE "
    assert _paragraph_has_page_field(p)
    assert _paragraph_should_preserve_pagination(p, "1")


def test_paragraph_preserves_static_page_display_without_field() -> None:
    ns = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
    p = etree.Element(f"{{{ns}}}p")
    assert _paragraph_should_preserve_pagination(p, "4/16")
