# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

from utils.epub_html_segments import extract_paragraph_segments_from_html


def test_extract_paragraph_segments_splits_by_block_tags():
    html = (
        "<html><body>"
        "<p>First paragraph.</p>"
        "<p>Second paragraph with <em>emphasis</em>.</p>"
        "</body></html>"
    )
    segments = extract_paragraph_segments_from_html(html, chunk_size=3000, deep_split=True)
    assert len(segments) == 2
    assert segments[0] == "First paragraph."
    assert "Second paragraph" in segments[1]
    assert "emphasis" in segments[1]


def test_extract_paragraph_segments_matches_extractor_and_translator_granularity():
    html = "<html><body><div>Line one<br>Line two</div></body></html>"
    segments = extract_paragraph_segments_from_html(html, chunk_size=3000, deep_split=True)
    # div block keeps line break as single segment unless deep split breaks lines
    assert len(segments) >= 1
    assert "Line one" in segments[0]
