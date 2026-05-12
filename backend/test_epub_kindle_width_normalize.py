# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

"""Regression: Kindle KF8 inline styles break browser layout (narrow column, overlap)."""

from bs4 import BeautifulSoup

from utils.epub_fix import (
    normalize_kindle_inline_reader_layout_styles,
    normalize_kindle_inline_width_styles,
    sanitize_html_for_epub,
)


def test_normalize_kindle_inline_width_strips_zero_pt():
    html = (
        '<p style="text-align:center;width:0pt;height:1em"><span><b>前言</b></span></p>'
    )
    soup = BeautifulSoup(html, "html.parser")
    n = normalize_kindle_inline_width_styles(soup)
    assert n == 1
    style = soup.find("p").get("style") or ""
    assert "0pt" not in style
    assert "text-align:center" in style
    assert "height:1em" in style


def test_reader_layout_strips_width_and_height():
    html = '<p style="text-align:center;width:0pt;height:1em">x</p>'
    soup = BeautifulSoup(html, "html.parser")
    normalize_kindle_inline_reader_layout_styles(soup)
    style = soup.find("p").get("style") or ""
    assert "0pt" not in style
    assert "height" not in style.lower()
    assert "text-align:center" in style


def test_sanitize_html_for_epub_applies_kindle_width_strip():
    html = '<div style="width:0pt;color:red">x</div>'
    out = sanitize_html_for_epub(html)
    assert "width:0pt" not in out
    assert "color:red" in out


def test_sanitize_removes_height_1em_overlap_guard():
    html = '<p style="text-align:center;height:1em">' + ("word " * 80) + "</p>"
    out = sanitize_html_for_epub(html)
    assert "height:1em" not in out.lower()
    assert "text-align:center" in out


def test_height_strip_removes_zero_pt_on_list_items():
    html = '<ul><li style="height:0pt" value="1">A</li><li style="height:0pt">B</li></ul>'
    out = sanitize_html_for_epub(html)
    assert "height:0pt" not in out.lower()
    assert "A" in out and "B" in out


def test_width_strip_removes_negative_pt():
    html = '<p style="width:-14pt; height:0pt"><a href="#">TOC</a></p>'
    out = sanitize_html_for_epub(html)
    assert "-14pt" not in out
    assert "height:0pt" not in out.lower()


def test_kindle_width_strip_preserves_nonzero_width():
    html = '<div style="width:50%;margin:auto">x</div>'
    out = sanitize_html_for_epub(html)
    assert "width:50%" in out


def test_overlap_styles_strip_negative_margin():
    html = '<div style="margin-top:-12px;padding:4px">x</div>'
    out = sanitize_html_for_epub(html)
    assert "-12px" not in out
    assert "padding:4px" in out.replace(" ", "")


def test_overlap_styles_strip_line_height_zero():
    html = '<p style="line-height:0;margin:1em">x</p>'
    out = sanitize_html_for_epub(html)
    assert "line-height:0" not in out.lower()
    assert "margin:1em" in out.replace(" ", "")
