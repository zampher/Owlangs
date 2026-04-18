# SPDX-FileCopyrightText: 2025 Owlangs
# SPDX-License-Identifier: MPL-2.0
"""
Canonical ebook metadata extracted from source (EPUB OPF, MOBI/ebooklib, or HTML).
Stored in task_state['ebook_metadata'] and applied when exporting EPUB/MOBI
so title, author, language, identifier, etc. are preserved after translation/format conversion.
"""
from __future__ import annotations

from typing import Any, Dict, Optional

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
    title = _norm(meta.get("title"))
    book.set_title(title if title else "Untitled")
    author = _norm(meta.get("author"))
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
