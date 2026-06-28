# SPDX-FileCopyrightText: 2025 Owlangs
# SPDX-License-Identifier: MPL-2.0
"""
Canonical ebook metadata extracted from source (EPUB OPF, MOBI/ebooklib, or HTML).
Stored in task_state['ebook_metadata'] and applied when exporting EPUB/MOBI
so title, author, language, identifier, etc. are preserved after translation/format conversion.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

# Canonical keys we store; map to Dublin Core / EPUB OPF and export usage.
# Keys: title, author (dc:creator), language, identifier, subject, description, publisher, date, rights.
EBOOK_METADATA_KEYS = [
    "title",
    "author",  # dc:creator
    "language",
    "identifier",
    "subject",
    "description",
    "publisher",
    "date",
    "rights",
]


def _norm(s: Optional[str]) -> Optional[str]:
    if s is None or not isinstance(s, str):
        return None
    t = s.strip()
    return t if t else None


def _strip_html_markup(text: Optional[str]) -> Optional[str]:
    """Plain text for Dublin Core fields (no inline HTML from bilingual export)."""
    if not text:
        return None
    raw = str(text).strip()
    if not raw:
        return None
    if "<" not in raw and ">" not in raw:
        return _norm(raw)
    try:
        from bs4 import BeautifulSoup

        plain = BeautifulSoup(raw, "html.parser").get_text(separator=" ", strip=True)
        plain = " ".join(plain.split())
        return _norm(plain)
    except Exception:
        return _norm(raw)


def _first_text(seq: Any) -> Optional[str]:
    """Get first non-empty value from ebooklib metadata list [ (value, attrs), ... ]."""
    if not seq or not isinstance(seq, (list, tuple)):
        return None
    for item in seq:
        if isinstance(item, (list, tuple)) and len(item) >= 1:
            v = item[0]
            if isinstance(v, str) and v.strip():
                return v.strip()
        elif isinstance(item, str) and item.strip():
            return item.strip()
    return None


def extract_from_opf(opf_root: Any, opf_ns: Dict[str, str], dc_ns: Dict[str, str]) -> Dict[str, Optional[str]]:
    """
    Extract Dublin Core metadata from OPF (content.opf) XML root.
    opf_ns e.g. {'opf': 'http://www.idpf.org/2007/opf'}
    dc_ns e.g. {'opf': '...', 'dc': 'http://purl.org/dc/elements/1.1/'}
    Returns dict with keys from EBOOK_METADATA_KEYS; values are stripped strings or None.
    """
    out: Dict[str, Optional[str]] = {k: None for k in EBOOK_METADATA_KEYS}
    dc_tag_to_key = {
        "title": "title",
        "creator": "author",
        "language": "language",
        "identifier": "identifier",
        "subject": "subject",
        "description": "description",
        "publisher": "publisher",
        "date": "date",
        "rights": "rights",
    }
    ns = {**opf_ns, **dc_ns}
    for dc_el, key in dc_tag_to_key.items():
        el = opf_root.find(f"opf:metadata/dc:{dc_el}", ns)
        if el is not None and el.text:
            out[key] = _norm(el.text)
    return out


def extract_from_ebooklib_book(book: Any) -> Dict[str, Optional[str]]:
    """
    Extract metadata from an ebooklib.EpubBook (or similar) via get_metadata('DC', ...).
    Returns dict with keys from EBOOK_METADATA_KEYS.
    """
    out: Dict[str, Optional[str]] = {k: None for k in EBOOK_METADATA_KEYS}
    dc_to_key = {
        "title": "title",
        "creator": "author",
        "language": "language",
        "identifier": "identifier",
        "subject": "subject",
        "description": "description",
        "publisher": "publisher",
        "date": "date",
        "rights": "rights",
    }
    for dc_name, key in dc_to_key.items():
        try:
            val = book.get_metadata("DC", dc_name)
            out[key] = _norm(_first_text(val))
        except Exception:
            pass
    return out


def extract_from_html_meta(html_content: bytes) -> Dict[str, Optional[str]]:
    """
    Extract metadata from HTML <meta> tags (e.g. MOBI converted to HTML).
    Tries name="...", property="...", and common Dublin Core names.
    Returns dict with keys from EBOOK_METADATA_KEYS; only present keys are set.
    """
    out: Dict[str, Optional[str]] = {}
    try:
        from bs4 import BeautifulSoup
        html_str = html_content.decode("utf-8", errors="ignore")
        soup = BeautifulSoup(html_str, "html.parser")
        # name -> our key
        name_to_key = {
            "title": "title",
            "author": "author",
            "DC.creator": "author",
            "creator": "author",
            "language": "language",
            "dc.language": "language",
            "identifier": "identifier",
            "subject": "subject",
            "description": "description",
            "publisher": "publisher",
            "date": "date",
            "rights": "rights",
        }
        for meta in soup.find_all("meta", attrs={"content": True}):
            name = meta.get("name") or meta.get("property")
            if not name:
                continue
            name = (name or "").strip().lower()
            key = name_to_key.get(name)
            if key and meta.get("content"):
                val = _norm(meta["content"])
                if val and (key not in out or not out[key]):
                    out[key] = val
    except Exception:
        pass
    return out


def extract_from_epub_bytes(epub_bytes: bytes) -> Dict[str, Optional[str]]:
    """Extract Dublin Core metadata from EPUB bytes via ebooklib."""
    try:
        import io

        from ebooklib import epub

        book = epub.read_epub(io.BytesIO(epub_bytes))
        return extract_from_ebooklib_book(book)
    except Exception:
        return {k: None for k in EBOOK_METADATA_KEYS}


def merge_metadata(
    base: Dict[str, Optional[str]],
    override: Dict[str, Optional[str]],
) -> Dict[str, Optional[str]]:
    """Merge override into base; override wins when non-empty. Keys from EBOOK_METADATA_KEYS only."""
    result = dict(base)
    for k in EBOOK_METADATA_KEYS:
        if k in override and override[k] is not None and (override[k] or "").strip():
            result[k] = _norm(override[k])
    return result


def apply_to_ebooklib_book(book: Any, meta: Dict[str, Any]) -> None:
    """
    Apply canonical ebook_metadata dict to an ebooklib.EpubBook (or similar).
    Sets title (defaults to "Untitled" if missing), identifier, language and add_metadata for DC creator, subject, description, publisher, date, rights.
    """
    if not meta:
        return
    title = _strip_html_markup(meta.get("title"))
    book.set_title(title if title else "Untitled")
    author = _strip_html_markup(meta.get("author"))
    if author:
        book.add_metadata("DC", "creator", author)
    lang = _norm(meta.get("language"))
    if lang:
        book.set_language(lang)
    ident = _norm(meta.get("identifier"))
    if ident:
        book.set_identifier(ident)
    for dc_name, key in (
        ("subject", "subject"),
        ("description", "description"),
        ("publisher", "publisher"),
        ("date", "date"),
        ("rights", "rights"),
    ):
        val = _norm(meta.get(key))
        if val:
            book.add_metadata("DC", dc_name, val)


def _is_placeholder_title(title: Optional[str]) -> bool:
    if not title:
        return True
    return title.strip().lower() in _PLACEHOLDER_TITLES


_PLACEHOLDER_TITLES = frozenset({"untitled", "mobi content", "content"})


def _title_from_html_templates(html_templates: Optional[Dict[str, str]]) -> Optional[str]:
    if not html_templates:
        return None
    try:
        from bs4 import BeautifulSoup
    except ImportError:
        return None
    for html in html_templates.values():
        if not html:
            continue
        soup = BeautifulSoup(html, "html.parser")
        title_tag = soup.find("title")
        if title_tag:
            title_text = title_tag.get_text(strip=True)
            if title_text and not _is_placeholder_title(title_text):
                return title_text
        for tag_name in ("h1", "h2", "h3", "p"):
            heading = soup.find(tag_name)
            if heading:
                heading_text = heading.get_text(strip=True)
                if heading_text and not _is_placeholder_title(heading_text):
                    return heading_text
    return None


def _segment_plain_target(task_state: Optional[Dict[str, Any]], segment_id: int) -> Optional[str]:
    """Plain target text from translation_segments (never bilingual HTML)."""
    if not task_state:
        return None
    ts_data = task_state.get("translation_segments") or {}
    segments = ts_data.get("segments") if isinstance(ts_data, dict) else None
    if not isinstance(segments, list) or not (0 <= segment_id < len(segments)):
        return None
    seg = segments[segment_id]
    if isinstance(seg, dict):
        return _strip_html_markup(
            seg.get("target_text") or seg.get("translated_text") or seg.get("text")
        )
    if seg is not None:
        return _strip_html_markup(str(seg))
    return None


def resolve_ebook_metadata_for_export(
    task_state: Optional[Dict[str, Any]],
    *,
    html_templates: Optional[Dict[str, str]] = None,
    translated_segments: Optional[Dict[int, str]] = None,
    original_filename: Optional[str] = None,
) -> Dict[str, Optional[str]]:
    """
    Resolve EPUB/MOBI metadata for export, filling placeholder titles from
    translated segments, cache, HTML headings, or filename.
    """
    from utils.translation_segments import _is_image_segment

    base = dict((task_state or {}).get("ebook_metadata") or {})
    result: Dict[str, Optional[str]] = {k: _norm(base.get(k)) for k in EBOOK_METADATA_KEYS}
    if result.get("title"):
        result["title"] = _strip_html_markup(result["title"])
    if result.get("author"):
        result["author"] = _strip_html_markup(result["author"])

    cache_segments: List[str] = []
    cache_info = (task_state or {}).get("source_chunks_cache") or {}
    raw_cache = cache_info.get("segments") or []
    if isinstance(raw_cache, list):
        cache_segments = [str(s) for s in raw_cache]

    if _is_placeholder_title(result.get("title")):
        title_candidates: List[str] = []
        seg0_target = _segment_plain_target(task_state, 0)
        if seg0_target:
            title_candidates.append(seg0_target)
        if translated_segments and cache_segments:
            translated_title = _strip_html_markup(_norm(translated_segments.get(0)))
            source_title = _norm(cache_segments[0])
            if (
                translated_title
                and not _is_image_segment(source_title or "")
                and translated_title not in title_candidates
            ):
                title_candidates.append(translated_title)
            if source_title and not _is_image_segment(source_title):
                plain_source = _strip_html_markup(source_title)
                if plain_source and plain_source not in title_candidates:
                    title_candidates.append(plain_source)
        html_title = _title_from_html_templates(html_templates)
        if html_title:
            title_candidates.append(html_title)
        if original_filename:
            stem = original_filename.rsplit(".", 1)[0]
            stem = stem.replace("_", " ").strip()
            if stem:
                title_candidates.append(stem)
        for candidate in title_candidates:
            if candidate and not _is_placeholder_title(candidate):
                result["title"] = candidate
                break

    if not result.get("author"):
        author_candidates: List[str] = []
        seg1_target = _segment_plain_target(task_state, 1)
        if seg1_target:
            author_candidates.append(seg1_target)
        if translated_segments:
            plain_map = _strip_html_markup(_norm(translated_segments.get(1)))
            if plain_map and plain_map not in author_candidates:
                author_candidates.append(plain_map)
        if len(cache_segments) > 1:
            author_source = cache_segments[1]
            if not _is_image_segment(author_source):
                plain_source = _strip_html_markup(author_source)
                if plain_source and plain_source not in author_candidates:
                    author_candidates.append(plain_source)
        for candidate in author_candidates:
            if candidate and not _is_image_segment(candidate):
                result["author"] = candidate
                break

    return result
