# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

"""PDF export failure should map Overfull/xdvipdfmx crashes to a segment index."""

from __future__ import annotations

from pathlib import Path

from utils.pdf_export_failure_locator import (
    build_pdf_export_user_detail,
    extract_long_token_context,
    extract_overfull_hbox_context,
    extract_pdf_export_failure_context,
    match_segment_index_for_pdf_failure,
)


def test_match_long_digit_run_to_segment_index(tmp_path: Path) -> None:
    nines = "9" * 500
    segs = [
        {"segment_index": 0, "target_text": "normal text"},
        {
            "segment_index": 26,
            "source_text": f"TOC line\n{nines}\nmore",
            "target_text": f"TOC line\n{nines}\nmore",
        },
        {"segment_index": 27, "target_text": "other"},
    ]
    idx, basis = match_segment_index_for_pdf_failure(
        error_token=nines,
        md_snippet="",
        tex_snippet="",
        segments=segs,
    )
    assert idx == 26
    assert basis == "long_token"
    detail = build_pdf_export_user_detail(idx, "xdvipdfmx_unbreakable_token")
    assert "Suspected bad segment: 26" in detail
    assert "请打开并检查片段 26" in detail


def test_extract_overfull_hbox_context(tmp_path: Path) -> None:
    nines = "9" * 300
    tex = tmp_path / "doc.tex"
    md = tmp_path / "doc.md"
    tex_lines = ["a", "b"] + ["x " + nines] + ["c"]
    # line numbers are 1-based: nines are on line 3
    tex.write_text("\n".join(tex_lines), encoding="utf-8")
    md.write_text(f"before\n{nines}\nafter\n", encoding="utf-8")
    stderr = (
        r"Overfull \hbox (22896.2305pt too wide) in paragraph at lines 3--3"
        "\nxdvipdfmx:fatal: File ended prematurely\n"
    )
    ctx = extract_overfull_hbox_context(stderr, tex, md)
    assert ctx is not None
    assert ctx.error_type == "overfull_hbox_unbreakable"
    assert ctx.line_no == 3
    assert nines[:50] in (ctx.error_token or "")


def test_extract_pdf_export_failure_falls_back_to_long_token(tmp_path: Path) -> None:
    nines = "9" * 400
    md = tmp_path / "doc.md"
    md.write_text(f"head\n{nines}\ntail\n", encoding="utf-8")
    stderr = "xdvipdfmx:fatal: File ended prematurely\nError producing PDF.\n"
    ctx = extract_pdf_export_failure_context(stderr, None, md)
    assert ctx is not None
    assert len(ctx.error_token) >= 400
    assert ctx.error_type == "xdvipdfmx_unbreakable_token"

    idx, _ = match_segment_index_for_pdf_failure(
        error_token=ctx.error_token,
        md_snippet=ctx.md_snippet,
        tex_snippet="",
        segments=[
            {"segment_index": 1, "target_text": "nope"},
            {"segment_index": 9, "source_text": nines},
        ],
    )
    assert idx == 9


def test_extract_pdf_export_failure_prefers_long_token_over_weak_overfull(
    tmp_path: Path,
) -> None:
    """Debug tex line numbers may not match engine logs; MD long token wins."""
    nines = "9" * 400
    md = tmp_path / "doc.md"
    tex = tmp_path / "doc.tex"
    md.write_text(f"head\n{nines}\ntail\n", encoding="utf-8")
    # Wrong line content relative to stderr "lines 3--3"
    tex.write_text("one\ntwo\nshort-token-here\nfour\n", encoding="utf-8")
    stderr = (
        r"Overfull \hbox (100pt too wide) in paragraph at lines 3--3"
        "\nxdvipdfmx:fatal: File ended prematurely\n"
    )
    ctx = extract_pdf_export_failure_context(stderr, tex, md)
    assert ctx is not None
    assert len(ctx.error_token) >= 400
    idx, basis = match_segment_index_for_pdf_failure(
        error_token=ctx.error_token,
        md_snippet=ctx.md_snippet,
        tex_snippet=ctx.tex_snippet,
        segments=[{"segment_index": 26, "source_text": nines}],
    )
    assert idx == 26
    assert basis == "long_token"

