# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

"""Lightweight ebook → HTML helpers for compare-reading previews (no translation)."""

from __future__ import annotations

import base64
import html
import mimetypes
import os
import re
import tempfile
from io import BytesIO
from typing import Any, Dict, List, Optional

from logger import unified_logger as logger
from logger.logger import LogModule
from utils.ebook_mobi_utils import is_epub_zip_bytes, is_valid_mobi_bytes
from utils.office_preview_utils import wrap_preview_html

_BODY_RE = re.compile(
    r"<body[^>]*>([\s\S]*?)</body>",
    re.IGNORECASE,
)
_MAX_CHAPTERS = 300
_MAX_HTML_CHARS = 4_000_000


def _extract_body_inner(xhtml: str) -> str:
    match = _BODY_RE.search(xhtml or "")
    if match:
        return match.group(1).strip()
    return (xhtml or "").strip()


def _guess_mime(href: str, raw: bytes) -> str:
    mime, _ = mimetypes.guess_type(href or "")
    if mime:
        return mime
    if raw[:8] == b"\x89PNG\r\n\x1a\n":
        return "image/png"
    if raw[:2] == b"\xff\xd8":
        return "image/jpeg"
    if raw[:6] in (b"GIF87a", b"GIF89a"):
        return "image/gif"
    return "application/octet-stream"


def _build_image_data_uri_map(book: Any) -> Dict[str, str]:
    """Map EPUB image href / basename → data URI for inlining in preview HTML."""
    import ebooklib

    mapping: Dict[str, str] = {}
    for item in book.get_items():
        if item.get_type() != ebooklib.ITEM_IMAGE:
            continue
        try:
            raw = item.get_content()
            if not raw:
                continue
            href = (item.get_name() or "").replace("\\", "/")
            mime = _guess_mime(href, raw)
            uri = f"data:{mime};base64,{base64.b64encode(raw).decode('ascii')}"
            if href:
                mapping[href] = uri
                mapping[href.split("/")[-1]] = uri
            item_id = item.get_id()
            if item_id:
                mapping[str(item_id)] = uri
        except Exception as exc:
            logger.warning(
                LogModule.EXPORT,
                f"[EBOOK_PREVIEW] Skip image item: {exc}",
            )
    return mapping


def _inline_img_srcs(body_html: str, image_map: Dict[str, str]) -> str:
    if not body_html or not image_map:
        return body_html

    def repl(match: re.Match) -> str:
        prefix = match.group(1)
        quote = match.group(2)
        src = (match.group(3) or "").strip()
        if not src or src.startswith("data:"):
            return match.group(0)
        key = src.replace("\\", "/")
        uri = image_map.get(key) or image_map.get(key.split("/")[-1])
        if not uri:
            return match.group(0)
        return f"{prefix}{quote}{uri}{quote}"

    return re.sub(
        r'(<img\b[^>]*\bsrc\s*=\s*)(["\'])([^"\']+)\2',
        repl,
        body_html,
        flags=re.IGNORECASE,
    )


def _spine_document_items(book: Any) -> List[Any]:
    import ebooklib

    items: List[Any] = []
    spine = getattr(book, "spine", None) or []
    for spine_item in spine:
        item = None
        if isinstance(spine_item, tuple):
            item = book.get_item_with_id(spine_item[0])
        elif isinstance(spine_item, str) and spine_item == "nav":
            continue
        elif hasattr(spine_item, "get_id"):
            item = spine_item
        if item is not None and item.get_type() == ebooklib.ITEM_DOCUMENT:
            items.append(item)
            if len(items) >= _MAX_CHAPTERS:
                logger.warning(
                    LogModule.EXPORT,
                    f"[EBOOK_PREVIEW] Truncated spine at {_MAX_CHAPTERS} chapters",
                )
                break
    if items:
        return items
    # Fallback: all documents if spine empty/unusable.
    for item in book.get_items():
        if item.get_type() == ebooklib.ITEM_DOCUMENT:
            items.append(item)
            if len(items) >= _MAX_CHAPTERS:
                break
    return items


def epub_bytes_to_html(content: bytes) -> str:
    """Convert EPUB bytes to a single HTML document for compare reading."""
    try:
        import ebooklib
        from ebooklib import epub
    except Exception as exc:
        logger.error(
            LogModule.EXPORT,
            f"[EBOOK_PREVIEW] ebooklib unavailable: {exc}",
        )
        raise RuntimeError(
            "EPUB preview requires 'ebooklib' package. Please install it."
        ) from exc

    try:
        book = epub.read_epub(BytesIO(content))
    except Exception as exc:
        logger.error(
            LogModule.EXPORT,
            f"[EBOOK_PREVIEW] Failed to open EPUB: {exc}",
            exc_info=True,
        )
        raise RuntimeError(f"EPUB preview failed: {exc}") from exc

    title_meta = book.get_metadata("DC", "title")
    title_text = title_meta[0][0] if title_meta else None
    image_map = _build_image_data_uri_map(book)
    docs = _spine_document_items(book)
    logger.info(
        LogModule.EXPORT,
        f"[EBOOK_PREVIEW] EPUB docs={len(docs)} images={len(image_map)} "
        f"title={title_text!r}",
    )

    sections: List[str] = []
    if title_text:
        sections.append(f"<h1>{html.escape(str(title_text))}</h1>")

    total_chars = 0
    for idx, item in enumerate(docs, start=1):
        try:
            raw = item.get_content() or b""
            xhtml = raw.decode("utf-8", errors="replace")
            body = _extract_body_inner(xhtml)
            body = _inline_img_srcs(body, image_map)
            if not body.strip():
                continue
            chapter_html = (
                f"<section class='ebook-chapter'>"
                f"<h2>Chapter {idx}</h2>{body}</section>"
            )
            total_chars += len(chapter_html)
            if total_chars > _MAX_HTML_CHARS:
                sections.append(
                    f"<p><em>… truncated after ~{_MAX_HTML_CHARS} characters</em></p>"
                )
                logger.warning(
                    LogModule.EXPORT,
                    f"[EBOOK_PREVIEW] Truncated HTML at chapter {idx} "
                    f"(chars={total_chars})",
                )
                break
            sections.append(chapter_html)
        except Exception as chap_exc:
            logger.warning(
                LogModule.EXPORT,
                f"[EBOOK_PREVIEW] Skip chapter {idx}: {chap_exc}",
            )

    if not sections:
        sections.append("<p><em>Empty ebook</em></p>")

    extra_css = (
        ".ebook-chapter{margin:0 0 24px 0;padding:0 0 16px 0;"
        "border-bottom:1px solid #e5e5e5}"
        ".ebook-chapter h2{font-size:1.05rem;margin:0 0 12px 0}"
        "img{max-width:100%;height:auto}"
    )
    return wrap_preview_html("".join(sections), extra_css=extra_css)


def _looks_like_html_bytes(raw: bytes) -> bool:
    head = raw[:2048].decode("utf-8", errors="ignore").lower()
    return "<html" in head or "<!doctype html" in head or "<body" in head


def _find_extracted_epub(bookpath: str, primary: Optional[str]) -> Optional[str]:
    """Return a verified EPUB path from mobi.extract output or walk of bookpath."""
    import zipfile

    candidates: List[str] = []
    if primary and os.path.isfile(primary) and primary.lower().endswith(".epub"):
        candidates.append(primary)
    if bookpath and os.path.isdir(bookpath):
        for root, _, files in os.walk(bookpath):
            for name in files:
                if name.lower().endswith(".epub"):
                    candidates.append(os.path.join(root, name))
    for path in candidates:
        try:
            with zipfile.ZipFile(path, "r"):
                return path
        except Exception as zip_exc:
            logger.warning(
                LogModule.EXPORT,
                f"[EBOOK_PREVIEW] Skip invalid EPUB candidate {path}: {zip_exc}",
            )
    return None


def _find_extracted_html(bookpath: str, primary: Optional[str]) -> Optional[str]:
    """Return MOBI7 HTML path from mobi.extract (primary or directory walk)."""
    if primary and os.path.isfile(primary):
        lower = primary.lower()
        if lower.endswith((".html", ".htm")):
            return primary
        try:
            with open(primary, "rb") as fh:
                if _looks_like_html_bytes(fh.read(2048)):
                    return primary
        except OSError:
            pass
    if not bookpath or not os.path.isdir(bookpath):
        return None
    preferred = os.path.join(bookpath, "mobi7", "book.html")
    if os.path.isfile(preferred):
        return preferred
    for root, _, files in os.walk(bookpath):
        for name in files:
            if name.lower().endswith((".html", ".htm")):
                return os.path.join(root, name)
    return None


def _build_dir_image_data_uri_map(html_path: str) -> Dict[str, str]:
    """Map relative image paths next to MOBI7 HTML → data URIs."""
    base_dir = os.path.dirname(html_path)
    mapping: Dict[str, str] = {}
    for root, _, files in os.walk(base_dir):
        for name in files:
            lower = name.lower()
            if not lower.endswith((".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg")):
                continue
            full = os.path.join(root, name)
            try:
                with open(full, "rb") as fh:
                    raw = fh.read()
                if not raw:
                    continue
                rel = os.path.relpath(full, base_dir).replace("\\", "/")
                mime = _guess_mime(rel, raw)
                uri = f"data:{mime};base64,{base64.b64encode(raw).decode('ascii')}"
                mapping[rel] = uri
                mapping[name] = uri
                mapping[f"Images/{name}"] = uri
            except OSError as exc:
                logger.warning(
                    LogModule.EXPORT,
                    f"[EBOOK_PREVIEW] Skip MOBI7 image {full}: {exc}",
                )
    return mapping


def _html_file_to_preview(html_path: str) -> str:
    """Wrap a MOBI7-extracted HTML file as compare-reading preview HTML."""
    with open(html_path, "rb") as fh:
        raw = fh.read()
    text = raw.decode("utf-8", errors="replace")
    body = _extract_body_inner(text) or text
    image_map = _build_dir_image_data_uri_map(html_path)
    body = _inline_img_srcs(body, image_map)
    if len(body) > _MAX_HTML_CHARS:
        logger.warning(
            LogModule.EXPORT,
            f"[EBOOK_PREVIEW] Truncating MOBI7 HTML "
            f"chars={len(body)} limit={_MAX_HTML_CHARS}",
        )
        body = body[:_MAX_HTML_CHARS] + "<p><em>… truncated</em></p>"
    extra_css = "img{max-width:100%;height:auto}"
    return wrap_preview_html(body, extra_css=extra_css)


def _mobi_extract_to_preview_html(content: bytes) -> str:
    """
    Extract MOBI/AZW via the mobi package and build preview HTML.

    mobi.extract() may return:
      - mobi8/*.epub (KF8)
      - mobi7/book.html (legacy MOBI)
      - *.pdf (rare)
    """
    try:
        import mobi
        import shutil
    except Exception as exc:
        raise RuntimeError(
            "MOBI/AZW preview requires 'mobi' package. Please install it."
        ) from exc

    temp_file: Optional[str] = None
    bookpath: Optional[str] = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".mobi") as tmp:
            tmp.write(content)
            temp_file = tmp.name
        bookpath, extracted = mobi.extract(temp_file)
        logger.info(
            LogModule.EXPORT,
            f"[EBOOK_PREVIEW] mobi.extract bookpath={bookpath!r} "
            f"extracted={extracted!r}",
        )
        epub_path = _find_extracted_epub(bookpath or "", extracted)
        if epub_path:
            with open(epub_path, "rb") as fh:
                return epub_bytes_to_html(fh.read())

        html_path = _find_extracted_html(bookpath or "", extracted)
        if html_path:
            logger.info(
                LogModule.EXPORT,
                f"[EBOOK_PREVIEW] Using MOBI7 HTML preview path={html_path}",
            )
            return _html_file_to_preview(html_path)

        raise RuntimeError(
            "mobi.extract() did not produce a readable EPUB or HTML file "
            f"(extracted={extracted!r})"
        )
    finally:
        if temp_file and os.path.exists(temp_file):
            try:
                os.unlink(temp_file)
            except OSError:
                pass
        if bookpath and os.path.isdir(bookpath):
            try:
                shutil.rmtree(bookpath, ignore_errors=True)
            except Exception as cleanup_exc:
                logger.warning(
                    LogModule.EXPORT,
                    f"[EBOOK_PREVIEW] Failed to cleanup extract dir "
                    f"{bookpath}: {cleanup_exc}",
                )


def mobi_bytes_to_html(content: bytes) -> str:
    """Convert MOBI/AZW (or EPUB mislabeled as MOBI) bytes to HTML."""
    if is_epub_zip_bytes(content):
        logger.info(
            LogModule.EXPORT,
            "[EBOOK_PREVIEW] MOBI path received EPUB/ZIP bytes; using EPUB reader",
        )
        return epub_bytes_to_html(content)

    if not is_valid_mobi_bytes(content):
        logger.warning(
            LogModule.EXPORT,
            "[EBOOK_PREVIEW] Bytes do not look like valid MOBI; attempting extract anyway",
        )

    try:
        return _mobi_extract_to_preview_html(content)
    except RuntimeError:
        raise
    except Exception as exc:
        logger.error(
            LogModule.EXPORT,
            f"[EBOOK_PREVIEW] MOBI extract failed: {exc}",
            exc_info=True,
        )
        raise RuntimeError(
            f"Invalid or unsupported MOBI/AZW file (extract failed: {exc})"
        ) from exc


def ebook_bytes_to_html(content: bytes, extension: str) -> str:
    """Dispatch ebook bytes to the correct HTML converter by extension."""
    ext = (extension or "").lower().lstrip(".")
    if ext in ("epub",):
        return epub_bytes_to_html(content)
    if ext in ("mobi", "azw", "azw3"):
        return mobi_bytes_to_html(content)
    raise RuntimeError(f"Unsupported ebook extension for preview: .{ext}")
