# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

"""Helpers for MOBI/EPUB HtmlExtractor image placeholders and ebooklib image embedding."""

from __future__ import annotations

import base64
import io
import mimetypes
import os
import re
from pathlib import PurePosixPath
from typing import Any, Dict, List, Optional, Tuple

# HtmlExtractor emits standalone image blocks as "[Image: {src}]"
HTML_EXTRACTOR_IMAGE_SEGMENT_RE = re.compile(
    r"^\[Image:\s*(.+?)\]\s*$",
    re.IGNORECASE,
)


def parse_html_extractor_image_segment(text: str) -> Optional[str]:
    """Return image src/path from HtmlExtractor segment text, or None."""
    if not text:
        return None
    match = HTML_EXTRACTOR_IMAGE_SEGMENT_RE.match(text.strip())
    if not match:
        return None
    path = match.group(1).strip()
    return path or None


def image_paths_match(path_a: str, path_b: str) -> bool:
    """Match image paths by full path, suffix, or basename."""
    if not path_a or not path_b:
        return False
    a = path_a.replace("\\", "/").lstrip("./")
    b = path_b.replace("\\", "/").lstrip("./")
    if a == b or a in b or b in a:
        return True
    return os.path.basename(a) == os.path.basename(b)


def segment_list_has_html_extractor_image(
    segments: List[Any],
    image_path: str,
) -> bool:
    """True when segments already contain [Image: ...] for the same file."""
    for seg in segments:
        if isinstance(seg, dict):
            text = seg.get("text") or seg.get("source_text") or ""
        else:
            text = str(seg)
        parsed = parse_html_extractor_image_segment(text)
        if parsed and image_paths_match(parsed, image_path):
            return True
    return False


def resolve_image_data_entry(
    image_data_map: Optional[Dict[str, Dict[str, str]]],
    key: str,
) -> Optional[Dict[str, str]]:
    """Look up image_data_map by exact key or fuzzy path match."""
    if not image_data_map or not key:
        return None
    direct = image_data_map.get(key)
    if isinstance(direct, dict) and direct.get("data"):
        return direct
    key_norm = str(key).replace("\\", "/")
    for map_key, info in image_data_map.items():
        if not isinstance(info, dict) or not info.get("data"):
            continue
        if image_paths_match(key_norm, str(map_key).replace("\\", "/")):
            return info
    return None


def decode_data_uri(data_uri: str) -> tuple[bytes, str]:
    """Decode a data:image/...;base64,... URI to (bytes, mime_type)."""
    if not data_uri or not data_uri.startswith("data:"):
        raise ValueError("Not a data URI")
    header, _, payload = data_uri.partition(",")
    if ";base64" not in header:
        raise ValueError("Only base64 data URIs are supported")
    mime = header[5:].split(";")[0].strip() or "image/jpeg"
    return base64.b64decode(payload), mime


def _book_image_names(book: Any) -> set[str]:
    import ebooklib

    names: set[str] = set()
    for item in book.get_items():
        if item.get_type() != ebooklib.ITEM_IMAGE:
            continue
        for candidate in (item.get_name(), getattr(item, "file_name", None), item.get_id()):
            if candidate:
                names.add(str(candidate).replace("\\", "/"))
    return names


def _image_item_href(item: Any) -> str:
    for candidate in (item.get_name(), getattr(item, "file_name", None), item.get_id()):
        if candidate:
            return str(candidate).replace("\\", "/")
    return ""


def relative_epub_href(from_doc_href: str, to_asset_href: str) -> str:
    """Compute a POSIX relative href from one EPUB document to another resource."""
    from_dir = PurePosixPath(from_doc_href.replace("\\", "/")).parent
    to_path = PurePosixPath(to_asset_href.replace("\\", "/"))
    rel = os.path.relpath(to_path.as_posix(), from_dir.as_posix())
    return rel.replace("\\", "/")


def _resolve_image_item_for_src(
    book: Any,
    doc_href: str,
    src: str,
    image_items: List[Tuple[str, Any]],
) -> Optional[Any]:
    import ebooklib

    src_norm = str(src).strip().replace("\\", "/")
    if not src_norm or src_norm.startswith("data:"):
        return None

    try:
        by_id = book.get_item_with_id(src_norm)
        if by_id and by_id.get_type() == ebooklib.ITEM_IMAGE:
            return by_id
    except Exception:
        pass

    if doc_href:
        doc_dir = PurePosixPath(doc_href.replace("\\", "/")).parent
        try:
            resolved = (doc_dir / PurePosixPath(src_norm)).as_posix()
        except Exception:
            resolved = src_norm.lstrip("/")
    else:
        resolved = src_norm.lstrip("/")

    for href, item in image_items:
        if href == src_norm or href == resolved:
            return item
        if image_paths_match(resolved, href) or image_paths_match(src_norm, href):
            return item
    return None


def reconcile_epub_image_links(book: Any) -> int:
    """
    Fix img src attributes in EPUB documents so they resolve to manifest image hrefs.

    Returns the number of img tags updated.
    """
    if not book:
        return 0

    try:
        from bs4 import BeautifulSoup
    except ImportError:
        return 0

    import ebooklib

    image_items: List[Tuple[str, Any]] = []
    for item in book.get_items():
        if item.get_type() != ebooklib.ITEM_IMAGE:
            continue
        href = _image_item_href(item)
        if href:
            image_items.append((href, item))

    if not image_items:
        return 0

    fixed = 0
    for item in book.get_items():
        if item.get_type() != ebooklib.ITEM_DOCUMENT:
            continue
        content = item.get_content()
        if not content:
            continue
        if isinstance(content, bytes):
            try:
                html = content.decode("utf-8")
            except UnicodeDecodeError:
                html = content.decode("latin-1", errors="replace")
        else:
            html = str(content)

        doc_href = _image_item_href(item) or (item.get_name() or "")
        soup = BeautifulSoup(html, "html.parser")
        changed = False
        for img in soup.find_all("img"):
            src = img.get("src")
            if not src or str(src).startswith("data:"):
                continue
            img_item = _resolve_image_item_for_src(book, doc_href, str(src), image_items)
            if not img_item:
                continue
            asset_href = _image_item_href(img_item)
            if not asset_href:
                continue
            new_src = relative_epub_href(doc_href, asset_href) if doc_href else asset_href
            if img.get("src") != new_src:
                img["src"] = new_src
                changed = True
                fixed += 1

        if changed:
            rendered = str(soup)
            if rendered:
                item.set_content(rendered.encode("utf-8"))

    return fixed


def inline_images_in_epub_documents(book: Any) -> int:
    """
    Replace img src with data URIs so Calibre MOBI conversion embeds images reliably.

    Returns the number of img tags inlined.
    """
    if not book:
        return 0

    try:
        from bs4 import BeautifulSoup
    except ImportError:
        return 0

    import ebooklib

    image_items: List[Tuple[str, Any]] = []
    for item in book.get_items():
        if item.get_type() != ebooklib.ITEM_IMAGE:
            continue
        href = _image_item_href(item)
        if href:
            image_items.append((href, item))

    if not image_items:
        return 0

    inlined = 0
    for item in book.get_items():
        if item.get_type() != ebooklib.ITEM_DOCUMENT:
            continue
        content = item.get_content()
        if not content:
            continue
        if isinstance(content, bytes):
            try:
                html = content.decode("utf-8")
            except UnicodeDecodeError:
                html = content.decode("latin-1", errors="replace")
        else:
            html = str(content)

        doc_href = _image_item_href(item) or (item.get_name() or "")
        soup = BeautifulSoup(html, "html.parser")
        changed = False
        for img in soup.find_all("img"):
            src = img.get("src")
            if not src or str(src).startswith("data:"):
                continue
            img_item = _resolve_image_item_for_src(book, doc_href, str(src), image_items)
            if not img_item:
                continue
            try:
                img_bytes = img_item.get_content()
            except Exception:
                continue
            if not img_bytes:
                continue
            mime = (
                getattr(img_item, "media_type", None)
                or mimetypes.guess_type(_image_item_href(img_item))[0]
                or "image/jpeg"
            )
            data_uri = f"data:{mime};base64,{base64.b64encode(img_bytes).decode('ascii')}"
            img["src"] = data_uri
            changed = True
            inlined += 1

        if changed:
            rendered = str(soup)
            if rendered:
                item.set_content(rendered.encode("utf-8"))

    return inlined


def prepare_epub_bytes_for_mobi(epub_bytes: bytes) -> bytes:
    """
    Normalize image links and inline images before Calibre EPUB->MOBI conversion.

    EPUB readers tolerate broken relative paths more than MOBI/KF8; inlining avoids
    path resolution issues inside converted MOBI files.
    """
    if not epub_bytes:
        return epub_bytes

    from ebooklib import epub

    try:
        book = epub.read_epub(io.BytesIO(epub_bytes))
    except Exception:
        return epub_bytes

    links_fixed = reconcile_epub_image_links(book)
    images_inlined = inline_images_in_epub_documents(book)
    try:
        from logger import unified_logger as logger
        from logger.logger import LogModule

        logger.info(
            LogModule.EXPORT,
            f"prepare_epub_bytes_for_mobi: links_fixed={links_fixed}, images_inlined={images_inlined}",
        )
    except Exception:
        pass

    out = io.BytesIO()
    try:
        epub.write_epub(out, book, {})
        prepared = out.getvalue()
    except Exception as write_err:
        try:
            from logger import unified_logger as logger
            from logger.logger import LogModule

            logger.warning(
                LogModule.EXPORT,
                f"prepare_epub_bytes_for_mobi: write_epub failed, using raw EPUB: {write_err}",
                exc_info=True,
            )
        except Exception:
            pass
        return epub_bytes
    try:
        from utils.epub_fix import fix_epub_for_epubcheck

        prepared = fix_epub_for_epubcheck(prepared)
    except Exception:
        pass
    return prepared


def ensure_ebooklib_images(
    book: Any,
    image_data_map: Optional[Dict[str, Dict[str, str]]],
) -> int:
    """
    Embed images from task_state image_data_map into an ebooklib book when missing.

    Returns the number of image items added.
    """
    if not book or not image_data_map:
        return 0

    from ebooklib import epub

    existing = _book_image_names(book)
    added = 0

    for key, info in image_data_map.items():
        if not isinstance(info, dict):
            continue
        key_norm = str(key).replace("\\", "/")
        if any(image_paths_match(key_norm, name) for name in existing):
            continue

        data_uri = info.get("data") or ""
        if not data_uri:
            continue

        try:
            img_bytes, mime = decode_data_uri(data_uri)
        except Exception:
            continue

        file_name = key_norm
        if not file_name:
            file_name = f"images/embedded_{added}.jpg"

        img_item = epub.EpubImage()
        img_item.file_name = file_name
        img_item.media_type = (
            info.get("mime")
            or mime
            or mimetypes.guess_type(file_name)[0]
            or "image/jpeg"
        )
        img_item.content = img_bytes
        book.add_item(img_item)
        existing.add(file_name)
        added += 1

    return added
