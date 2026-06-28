# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

"""Tests for EPUB OPF parsing with default XML namespaces."""

from __future__ import annotations

import io
import zipfile

from extractor.epub_extractor import EpubExtractor
from utils.epub_html_segments import (
    collect_epub_paragraph_segments,
    get_epub_html_files_in_reading_order,
    read_epub_all_files,
)


def _build_epub(
    *,
    container_xml: str,
    opf_xml: str,
    chapter_path: str,
    chapter_html: str,
) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("mimetype", "application/epub+zip")
        zf.writestr("META-INF/container.xml", container_xml)
        zf.writestr("OEBPS/content.opf", opf_xml)
        zf.writestr(chapter_path, chapter_html)
    return buf.getvalue()


def test_default_namespace_opf_yields_html_files_and_segments():
    container_xml = """<?xml version="1.0"?>
<container xmlns="urn:oasis:names:tc:opendocument:xmlns:container" version="1.0">
  <rootfiles>
    <rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/>
  </rootfiles>
</container>"""
    opf_xml = """<?xml version="1.0"?>
<package xmlns="http://www.idpf.org/2007/opf" version="3.0" unique-identifier="id">
  <metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
    <dc:title>Test Book</dc:title>
  </metadata>
  <manifest>
    <item id="c1" href="chapter.xhtml" media-type="application/xhtml+xml"/>
  </manifest>
  <spine>
    <itemref idref="c1"/>
  </spine>
</package>"""
    chapter_html = """<?xml version="1.0" encoding="utf-8"?>
<html xmlns="http://www.w3.org/1999/xhtml">
  <body><p>Hello EPUB world.</p><p>Second paragraph.</p></body>
</html>"""
    epub_bytes = _build_epub(
        container_xml=container_xml,
        opf_xml=opf_xml,
        chapter_path="OEBPS/chapter.xhtml",
        chapter_html=chapter_html,
    )

    all_files = read_epub_all_files(epub_bytes)
    html_files = get_epub_html_files_in_reading_order(all_files)
    assert len(html_files) == 1
    assert html_files[0][0].endswith("chapter.xhtml")

    _, segments = collect_epub_paragraph_segments(all_files, chunk_size=3000, deep_split=True)
    assert len(segments) >= 2

    result = EpubExtractor(epub_bytes, chunk_size=3000).extract()
    assert len(result.segments) >= 2


def test_percent_encoded_href_is_resolved():
    container_xml = """<?xml version="1.0"?>
<container xmlns="urn:oasis:names:tc:opendocument:xmlns:container" version="1.0">
  <rootfiles>
    <rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/>
  </rootfiles>
</container>"""
    opf_xml = """<?xml version="1.0"?>
<package xmlns="http://www.idpf.org/2007/opf" version="3.0" unique-identifier="id">
  <manifest>
    <item id="c1" href="ch%20apter.xhtml" media-type="application/xhtml+xml"/>
  </manifest>
  <spine>
    <itemref idref="c1"/>
  </spine>
</package>"""
    chapter_html = """<?xml version="1.0" encoding="utf-8"?>
<html xmlns="http://www.w3.org/1999/xhtml"><body><p>Encoded path works.</p></body></html>"""
    chapter_path = "OEBPS/ch apter.xhtml"
    epub_bytes = _build_epub(
        container_xml=container_xml,
        opf_xml=opf_xml,
        chapter_path=chapter_path,
        chapter_html=chapter_html,
    )

    all_files = read_epub_all_files(epub_bytes)
    html_files = get_epub_html_files_in_reading_order(all_files)
    assert len(html_files) == 1
    assert html_files[0][0].endswith("ch apter.xhtml")
