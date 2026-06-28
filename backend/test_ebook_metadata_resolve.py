# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

"""Tests for export-time ebook metadata resolution."""

from utils.ebook_metadata import resolve_ebook_metadata_for_export


def test_resolve_title_from_translated_first_segment_when_untitled():
    task_state = {
        "ebook_metadata": {"title": "Untitled", "author": None},
        "source_chunks_cache": {
            "segments": ["Rimas", "Gustavo Adolfo Bécquer"],
        },
    }
    meta = resolve_ebook_metadata_for_export(
        task_state,
        translated_segments={0: "诗韵", 1: "古斯塔沃·阿道夫·贝克尔"},
    )
    assert meta["title"] == "诗韵"
    assert meta["author"] == "古斯塔沃·阿道夫·贝克尔"


def test_resolve_title_from_filename_when_metadata_empty():
    task_state = {"ebook_metadata": {}}
    meta = resolve_ebook_metadata_for_export(
        task_state,
        original_filename="Rimas_(Bécquer,_1925).mobi",
    )
    assert meta["title"] == "Rimas (Bécquer, 1925)"


def test_resolve_title_author_from_translation_segments_not_bilingual_html():
    """Bilingual inline HTML in translated_segments must not become OPF title/author."""
    task_state = {
        "ebook_metadata": {"title": "Untitled"},
        "translation_segments": {
            "segments": [
                {"target_text": "里马斯"},
                {"target_text": "古斯塔沃·阿道夫·贝克尔"},
            ],
        },
        "source_chunks_cache": {
            "segments": ["Rimas", "Gustavo Adolfo Bécquer"],
        },
    }
    bilingual_html = {
        0: '<span class="source">Rimas</span> <span class="target">里马斯</span>',
        1: '<span class="source">Gustavo Adolfo Bécquer</span> '
        '<span class="target">古斯塔沃·阿道夫·贝克尔</span>',
    }
    meta = resolve_ebook_metadata_for_export(
        task_state,
        translated_segments=bilingual_html,
    )
    assert meta["title"] == "里马斯"
    assert meta["author"] == "古斯塔沃·阿道夫·贝克尔"


def test_strip_html_from_existing_metadata():
    task_state = {
        "ebook_metadata": {
            "title": '<span class="target">诗韵</span>',
            "author": '<b>Author Name</b>',
        },
    }
    meta = resolve_ebook_metadata_for_export(task_state)
    assert meta["title"] == "诗韵"
    assert meta["author"] == "Author Name"
