# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

"""Tests for MOBI/EPUB image placeholder helpers."""

import base64
import sys
import types

from utils.ebook_image_utils import (
    decode_data_uri,
    ensure_ebooklib_images,
    image_paths_match,
    inline_images_in_epub_documents,
    parse_html_extractor_image_segment,
    reconcile_epub_image_links,
    relative_epub_href,
    segment_list_has_html_extractor_image,
)
from utils.translation_segments import _is_image_segment


def test_parse_html_extractor_image_segment():
    assert parse_html_extractor_image_segment("[Image: Images/foo.jpeg]") == "Images/foo.jpeg"
    assert parse_html_extractor_image_segment("  [Image: path/to/img.png]  ") == "path/to/img.png"
    assert parse_html_extractor_image_segment("not an image") is None


def test_is_image_segment_recognizes_html_extractor_placeholder():
    assert _is_image_segment("[Image: Images/image00044.jpeg]")
    assert not _is_image_segment("See [Image: x] in text")


def test_image_paths_match():
    assert image_paths_match("Images/foo.jpeg", "Images/foo.jpeg")
    assert image_paths_match("Images/foo.jpeg", "foo.jpeg")
    assert not image_paths_match("a.png", "b.png")


def test_segment_list_has_html_extractor_image():
    segments = ["intro", "[Image: Images/cover.jpg]", "outro"]
    assert segment_list_has_html_extractor_image(segments, "Images/cover.jpg")
    assert segment_list_has_html_extractor_image(segments, "cover.jpg")
    assert not segment_list_has_html_extractor_image(segments, "other.png")


def test_decode_data_uri():
    raw = b"hello"
    b64 = base64.b64encode(raw).decode("ascii")
    data_uri = f"data:image/png;base64,{b64}"
    decoded, mime = decode_data_uri(data_uri)
    assert decoded == raw
    assert mime == "image/png"


def test_resolve_image_data_entry_fuzzy_match():
    from utils.ebook_image_utils import resolve_image_data_entry

    raw = b"abc"
    b64 = base64.b64encode(raw).decode("ascii")
    image_map = {
        "Images/foo.jpeg": {"data": f"data:image/jpeg;base64,{b64}"},
    }
    assert resolve_image_data_entry(image_map, "mobi7/Images/foo.jpeg") is not None
    assert resolve_image_data_entry(image_map, "missing.png") is None


def test_ensure_ebooklib_images_adds_missing_items(monkeypatch):
    class StubImage:
        def __init__(self):
            self.file_name = ""
            self.media_type = ""
            self.content = b""

        def get_type(self):
            return 1

        def get_name(self):
            return self.file_name

        def get_id(self):
            return self.file_name

    fake_epub = types.ModuleType("epub")
    fake_epub.EpubImage = StubImage
    fake_ebooklib = types.ModuleType("ebooklib")
    fake_ebooklib.epub = fake_epub
    fake_ebooklib.ITEM_IMAGE = 1
    monkeypatch.setitem(sys.modules, "ebooklib", fake_ebooklib)
    monkeypatch.setitem(sys.modules, "ebooklib.epub", fake_epub)

    class FakeImageItem:
        def __init__(self, name: str):
            self.file_name = name
            self._name = name

        def get_type(self):
            return 1

        def get_name(self):
            return self._name

        def get_id(self):
            return self._name

    class FakeBook:
        def __init__(self):
            self._items: list[FakeImageItem] = []

        def get_items(self):
            return list(self._items)

        def add_item(self, item):
            self._items.append(item)

    book = FakeBook()
    raw = b"\xff\xd8\xff"
    b64 = base64.b64encode(raw).decode("ascii")
    image_data_map = {
        "Images/test.jpg": {
            "data": f"data:image/jpeg;base64,{b64}",
            "mime": "image/jpeg",
        }
    }
    added = ensure_ebooklib_images(book, image_data_map)
    assert added == 1
    assert len(book.get_items()) == 1
    assert book.get_items()[0].file_name == "Images/test.jpg"
    assert ensure_ebooklib_images(book, image_data_map) == 0


def test_relative_epub_href():
    assert relative_epub_href("OEBPS/chapter1.xhtml", "OEBPS/Images/foo.jpeg") == "Images/foo.jpeg"
    assert relative_epub_href("OEBPS/Text/ch1.xhtml", "Images/cover.jpg") == "../../Images/cover.jpg"


def test_reconcile_epub_image_links_fixes_broken_src(monkeypatch):
    pytest = __import__("pytest")
    pytest.importorskip("bs4")

    fake_ebooklib = types.ModuleType("ebooklib")
    fake_ebooklib.ITEM_IMAGE = 1
    fake_ebooklib.ITEM_DOCUMENT = 2
    monkeypatch.setitem(sys.modules, "ebooklib", fake_ebooklib)

    class FakeImageItem:
        def __init__(self, name: str, content: bytes, item_type: int):
            self._name = name
            self._content = content
            self._type = item_type

        def get_type(self):
            return self._type

        def get_name(self):
            return self._name

        def get_id(self):
            return self._name

        def get_content(self):
            return self._content

        def set_content(self, content: bytes):
            self._content = content

    class FakeBook:
        def __init__(self):
            self._items = [
                FakeImageItem(
                    "Images/test.jpg",
                    b"\xff\xd8\xff",
                    fake_ebooklib.ITEM_IMAGE,
                ),
                FakeImageItem(
                    "OEBPS/chapter.xhtml",
                    b'<html><body><img src="test.jpg"/></body></html>',
                    fake_ebooklib.ITEM_DOCUMENT,
                ),
            ]

        def get_items(self):
            return list(self._items)

        def get_item_with_id(self, _item_id):
            return None

    book = FakeBook()
    fixed = reconcile_epub_image_links(book)
    assert fixed == 1
    updated = book.get_items()[1].get_content().decode("utf-8")
    assert "../Images/test.jpg" in updated


def test_inline_images_in_epub_documents_embeds_data_uri(monkeypatch):
    pytest = __import__("pytest")
    pytest.importorskip("bs4")

    fake_ebooklib = types.ModuleType("ebooklib")
    fake_ebooklib.ITEM_IMAGE = 1
    fake_ebooklib.ITEM_DOCUMENT = 2
    monkeypatch.setitem(sys.modules, "ebooklib", fake_ebooklib)

    class FakeImageItem:
        def __init__(self, name: str, content: bytes, item_type: int, media_type: str = ""):
            self._name = name
            self._content = content
            self._type = item_type
            self.media_type = media_type

        def get_type(self):
            return self._type

        def get_name(self):
            return self._name

        def get_id(self):
            return self._name

        def get_content(self):
            return self._content

        def set_content(self, content: bytes):
            self._content = content

    class FakeBook:
        def __init__(self):
            self._items = [
                FakeImageItem(
                    "Images/test.jpg",
                    b"\xff\xd8\xff",
                    fake_ebooklib.ITEM_IMAGE,
                    "image/jpeg",
                ),
                FakeImageItem(
                    "chapter.xhtml",
                    b'<html><body><img src="Images/test.jpg"/></body></html>',
                    fake_ebooklib.ITEM_DOCUMENT,
                ),
            ]

        def get_items(self):
            return list(self._items)

        def get_item_with_id(self, _item_id):
            return None

    book = FakeBook()
    inlined = inline_images_in_epub_documents(book)
    assert inlined == 1
    updated = book.get_items()[1].get_content().decode("utf-8")
    assert updated.startswith("<html>")
    assert 'src="data:image/jpeg;base64,' in updated


def test_prepare_epub_bytes_for_mobi(monkeypatch):
    from utils import ebook_image_utils

    calls: list[str] = []

    def fake_reconcile(_book):
        calls.append("reconcile")
        return 1

    def fake_inline(_book):
        calls.append("inline")
        return 1

    class FakeBook:
        pass

    def fake_read_epub(_stream):
        return FakeBook()

    def fake_write_epub(out, _book, _opts):
        out.write(b"prepared-epub")

    fake_epub_mod = types.ModuleType("epub")
    fake_epub_mod.read_epub = fake_read_epub
    fake_epub_mod.write_epub = fake_write_epub
    monkeypatch.setitem(sys.modules, "ebooklib.epub", fake_epub_mod)
    monkeypatch.setattr(ebook_image_utils, "reconcile_epub_image_links", fake_reconcile)
    monkeypatch.setattr(ebook_image_utils, "inline_images_in_epub_documents", fake_inline)

    result = ebook_image_utils.prepare_epub_bytes_for_mobi(b"fake-epub-bytes")
    assert result == b"prepared-epub"
    assert calls == ["reconcile", "inline"]
