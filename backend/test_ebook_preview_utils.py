# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

"""Unit tests for ebook compare-reading HTML preview helpers."""

from __future__ import annotations

import io
import unittest
import zipfile


def _minimal_epub_bytes(body_html: str = "<p>Hello Compare EPUB</p>") -> bytes:
    """Build a tiny EPUB ZIP for preview tests."""
    container = """<?xml version="1.0"?>
<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
  <rootfiles>
    <rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/>
  </rootfiles>
</container>
"""
    opf = """<?xml version="1.0"?>
<package xmlns="http://www.idpf.org/2007/opf" unique-identifier="uid" version="2.0">
  <metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
    <dc:title>Preview Book</dc:title>
    <dc:identifier id="uid">preview-1</dc:identifier>
    <dc:language>en</dc:language>
  </metadata>
  <manifest>
    <item id="chap1" href="chap1.xhtml" media-type="application/xhtml+xml"/>
  </manifest>
  <spine>
    <itemref idref="chap1"/>
  </spine>
</package>
"""
    chap = f"""<?xml version="1.0" encoding="utf-8"?>
<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml">
<head><title>Chap</title></head>
<body>{body_html}</body>
</html>
"""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("mimetype", "application/epub+zip", compress_type=zipfile.ZIP_STORED)
        zf.writestr("META-INF/container.xml", container)
        zf.writestr("OEBPS/content.opf", opf)
        zf.writestr("OEBPS/chap1.xhtml", chap)
    return buf.getvalue()


class EbookPreviewUtilsTests(unittest.TestCase):
    def test_epub_bytes_to_html_contains_chapter_text(self) -> None:
        try:
            import ebooklib  # noqa: F401
        except ImportError:
            self.skipTest("ebooklib not installed")

        from utils.ebook_preview_utils import epub_bytes_to_html

        html = epub_bytes_to_html(_minimal_epub_bytes())
        self.assertIn("Hello Compare EPUB", html)
        self.assertIn("Chapter 1", html)
        self.assertIn("Preview Book", html)

    def test_ebook_bytes_to_html_dispatch_epub(self) -> None:
        try:
            import ebooklib  # noqa: F401
        except ImportError:
            self.skipTest("ebooklib not installed")

        from utils.ebook_preview_utils import ebook_bytes_to_html

        html = ebook_bytes_to_html(_minimal_epub_bytes(), "epub")
        self.assertIn("Hello Compare EPUB", html)

    def test_mobi_path_accepts_epub_zip_bytes(self) -> None:
        try:
            import ebooklib  # noqa: F401
        except ImportError:
            self.skipTest("ebooklib not installed")

        from utils.ebook_preview_utils import mobi_bytes_to_html

        # Misnamed EPUB should still preview via ZIP detection.
        html = mobi_bytes_to_html(_minimal_epub_bytes())
        self.assertIn("Hello Compare EPUB", html)

    def test_mobi7_html_extract_preview(self) -> None:
        """Legacy MOBI7 extracts to book.html, not EPUB — must still preview."""
        try:
            import mobi  # noqa: F401
        except ImportError:
            self.skipTest("mobi package not installed")

        import os
        from pathlib import Path

        from utils.ebook_preview_utils import mobi_bytes_to_html

        sample = Path(os.environ.get("TEMP", "/tmp")) / "pg46.mobi"
        if not sample.is_file() or sample.stat().st_size < 10_000:
            self.skipTest(f"Sample MOBI missing at {sample}")

        html = mobi_bytes_to_html(sample.read_bytes())
        self.assertIn("<html", html.lower())
        # Gutenberg Christmas Carol text should appear after MOBI7 unwrap.
        self.assertTrue(
            "Christmas" in html or "Scrooge" in html or "Carol" in html,
            msg="Expected Christmas Carol text in MOBI7 preview HTML",
        )

    def test_find_extracted_html_prefers_mobi7_book(self) -> None:
        import os
        import tempfile

        from utils.ebook_preview_utils import _find_extracted_html

        with tempfile.TemporaryDirectory() as td:
            mobi7 = os.path.join(td, "mobi7")
            os.makedirs(mobi7)
            book = os.path.join(mobi7, "book.html")
            with open(book, "w", encoding="utf-8") as fh:
                fh.write("<html><body><p>legacy</p></body></html>")
            found = _find_extracted_html(td, None)
            self.assertEqual(found, book)


if __name__ == "__main__":
    unittest.main()
