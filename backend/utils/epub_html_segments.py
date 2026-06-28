# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

"""Shared EPUB HTML iteration and paragraph-level segment extraction."""

from __future__ import annotations

import io
import os
import re
import xml.etree.ElementTree as ET
import zipfile
from typing import Any, Dict, List, Optional, Tuple

EPUB_HTML_MEDIA_TYPES = frozenset({
    "application/xhtml+xml",
    "text/html",
    "application/x-dtbook+xml",
    "application/xml",
})

OPF_NS = "http://www.idpf.org/2007/opf"


def _local_xml_name(tag: str) -> str:
    if tag and "}" in tag:
        return tag.rsplit("}", 1)[-1]
    return tag or ""


def _normalize_epub_zip_path(*parts: str) -> str:
    from urllib.parse import unquote

    cleaned = [p.replace("\\", "/").strip("/") for p in parts if p]
    joined = unquote("/".join(cleaned))
    while "//" in joined:
        joined = joined.replace("//", "/")
    return joined.lstrip("/")


def _lookup_epub_file(all_files: Dict[str, bytes], path: str) -> Optional[bytes]:
    norm = _normalize_epub_zip_path(path)
    if norm in all_files:
        return all_files[norm]
    norm_lower = norm.lower()
    for key, data in all_files.items():
        if key.replace("\\", "/").lower() == norm_lower:
            return data
    return None


def _find_container_opf_path(container_root: Any) -> Optional[str]:
    for el in container_root.iter():
        if _local_xml_name(el.tag) == "rootfile":
            full_path = el.get("full-path")
            if full_path:
                return full_path.replace("\\", "/")
    return None


def _parse_opf_manifest_and_spine(
    opf_root: Any,
    opf_dir: str,
) -> Tuple[Dict[str, dict], List[str]]:
    """Parse manifest items and spine order from OPF (default or prefixed namespace)."""
    manifest_items: Dict[str, dict] = {}
    manifest_el = opf_root.find(f"{{{OPF_NS}}}manifest")
    if manifest_el is not None:
        for item in manifest_el.findall(f"{{{OPF_NS}}}item"):
            item_id = item.get("id")
            href = item.get("href")
            if not item_id or not href:
                continue
            manifest_items[item_id] = {
                "href": _normalize_epub_zip_path(opf_dir, href),
                "media_type": (item.get("media-type") or "").strip(),
            }

    spine_itemrefs: List[str] = []
    spine_el = opf_root.find(f"{{{OPF_NS}}}spine")
    if spine_el is not None:
        for itemref in spine_el.findall(f"{{{OPF_NS}}}itemref"):
            idref = itemref.get("idref")
            if idref:
                spine_itemrefs.append(idref)

    return manifest_items, spine_itemrefs


def _fallback_epub_html_files(all_files: Dict[str, bytes]) -> List[Tuple[str, bytes]]:
    """Last-resort: collect HTML/XHTML files from the EPUB archive."""
    html_files: List[Tuple[str, bytes]] = []
    for name in sorted(all_files.keys()):
        norm = name.replace("\\", "/")
        lower = norm.lower()
        if not lower.endswith((".xhtml", ".html", ".htm")):
            continue
        if lower.startswith("meta-inf/"):
            continue
        data = all_files.get(name)
        if data:
            html_files.append((norm, data))
    return html_files


def _is_epub_html_media_type(media_type: str) -> bool:
    mt = (media_type or "").split(";")[0].strip().lower()
    if mt in EPUB_HTML_MEDIA_TYPES:
        return True
    return mt.endswith("+xml") and ("html" in mt or "xhtml" in mt)


def read_epub_all_files(epub_bytes: bytes) -> Dict[str, bytes]:
    """Read all files from an EPUB archive into a path -> bytes map."""
    with zipfile.ZipFile(io.BytesIO(epub_bytes), "r") as zf:
        return {name: zf.read(name) for name in zf.namelist()}


BLOCK_TAGS = frozenset({
    "p", "h1", "h2", "h3", "h4", "h5", "h6",
    "blockquote", "pre", "code", "div", "section", "article",
    "ul", "ol", "table",
})


def get_epub_html_files_in_reading_order(all_files: Dict[str, bytes]) -> List[Tuple[str, bytes]]:
    """
    Return (file_path, html_bytes) pairs in spine reading order.

    Falls back to manifest order when spine is empty, then to archive HTML scan.
    """
    container_xml = _lookup_epub_file(all_files, "META-INF/container.xml")
    if not container_xml:
        return _fallback_epub_html_files(all_files)

    container_root = ET.fromstring(container_xml)
    opf_path = _find_container_opf_path(container_root)
    if not opf_path:
        return _fallback_epub_html_files(all_files)

    opf_content = _lookup_epub_file(all_files, opf_path)
    if not opf_content:
        return _fallback_epub_html_files(all_files)

    opf_root = ET.fromstring(opf_content)
    opf_dir = os.path.dirname(opf_path.replace("\\", "/"))

    manifest_items, spine_itemrefs = _parse_opf_manifest_and_spine(opf_root, opf_dir)
    reading_order = spine_itemrefs or list(manifest_items.keys())

    html_files: List[Tuple[str, bytes]] = []
    for item_id in reading_order:
        item = manifest_items.get(item_id)
        if not item:
            continue
        if not _is_epub_html_media_type(item["media_type"]):
            continue
        file_path = item["href"]
        html_bytes = _lookup_epub_file(all_files, file_path)
        if html_bytes:
            html_files.append((file_path, html_bytes))

    if html_files:
        return html_files
    return _fallback_epub_html_files(all_files)


def extract_paragraph_segments_from_html(
    html_content: str,
    chunk_size: int = 3000,
    deep_split: bool = True,
) -> List[str]:
    """Extract translation segments from HTML using the same logic as HtmlExtractor."""
    from extractor.html_extractor import HtmlExtractor

    result = HtmlExtractor(html_content, chunk_size=chunk_size, deep_split=deep_split).extract()
    return result.segments


def decode_html_bytes(html_bytes: bytes) -> str:
    return html_bytes.decode("utf-8", errors="replace")


def collect_epub_paragraph_segments(
    all_files: Dict[str, bytes],
    chunk_size: int,
    deep_split: bool = True,
) -> Tuple[List[Tuple[str, str, int, int]], List[str]]:
    """
    Collect paragraph segments from all HTML resources in spine order.

    Returns:
        file_ranges: list of (file_path, html_str, start_idx, end_idx) with end exclusive
        all_segments: flat list of segment texts
    """
    file_ranges: List[Tuple[str, str, int, int]] = []
    all_segments: List[str] = []

    for file_path, html_bytes in get_epub_html_files_in_reading_order(all_files):
        html_str = decode_html_bytes(html_bytes)
        start_idx = len(all_segments)
        segments = extract_paragraph_segments_from_html(html_str, chunk_size, deep_split)
        all_segments.extend(segments)
        file_ranges.append((file_path, html_str, start_idx, len(all_segments)))

    return file_ranges, all_segments


def _normalize_block_text(text: str) -> str:
    if not text:
        return ""
    return re.sub(r"\s+", " ", text.strip())


def _compact_text(text: str) -> str:
    """Whitespace-insensitive text key for HTML vs cache matching."""
    import html as html_module

    if not text:
        return ""
    normalized = html_module.unescape(text)
    return re.sub(r"\s+", "", normalized)


def _split_plain_text_into_segments(
    text: str,
    chunk_size: int,
    deep_split: bool,
) -> List[str]:
    """Split plain block text the same way HtmlExtractor deep_split would."""
    from extractor.html_extractor import HtmlExtractor

    if not text or not text.strip():
        return []
    return HtmlExtractor(
        text,
        chunk_size=chunk_size,
        deep_split=deep_split,
    ).extract().segments


def _element_block_text(element: Any) -> str:
    """Plain text for a block element, aligned with _StructuredHtmlParser output."""
    name = getattr(element, "name", None)
    if name in ("ul", "ol"):
        items = [
            li.get_text(strip=True)
            for li in element.find_all("li", recursive=False)
        ]
        return "\n".join(item for item in items if item)
    if name == "table":
        rows: List[str] = []
        for tr in element.find_all("tr"):
            cells = [
                cell.get_text(strip=True)
                for cell in tr.find_all(["td", "th"])
            ]
            row_text = " | ".join(cells)
            if row_text:
                rows.append(row_text)
        return "\n".join(rows)
    return element.get_text(separator="\n", strip=True)


def _parser_blocks(html_content: str) -> List[str]:
    from extractor.html_extractor import _StructuredHtmlParser

    parser = _StructuredHtmlParser()
    parser.feed(html_content.replace("\r\n", "\n"))
    parser.close()
    return parser.blocks


def _block_element_candidates(soup: Any) -> List[Any]:
    order: Dict[int, int] = {}
    for idx, el in enumerate(soup.find_all(True)):
        order[id(el)] = idx

    candidates = [el for el in soup.find_all(BLOCK_TAGS) if el.name in BLOCK_TAGS]
    candidates.sort(key=lambda el: order.get(id(el), 0))
    return candidates


def _leaf_block_element_candidates(soup: Any) -> List[Any]:
    """Block elements that do not contain nested block tags (parser-aligned leaves)."""
    order: Dict[int, int] = {}
    for idx, el in enumerate(soup.find_all(True)):
        order[id(el)] = idx

    candidates: List[Any] = []
    for el in soup.find_all(BLOCK_TAGS):
        if el.name not in BLOCK_TAGS:
            continue
        if el.find(BLOCK_TAGS):
            continue
        candidates.append(el)
    candidates.sort(key=lambda el: order.get(id(el), 0))
    return candidates


def _segment_texts_match(left: str, right: str) -> bool:
    if left == right:
        return True
    if _normalize_block_text(left) == _normalize_block_text(right):
        return True
    return _compact_text(left) == _compact_text(right)


def _texts_match(block_text: str, element_text: str) -> bool:
    return _segment_texts_match(block_text, element_text)


def _image_segment_path(original_text: str) -> Optional[str]:
    from utils.translation_segments import _is_image_segment

    if not _is_image_segment(original_text):
        return None
    match = re.search(r"\[Image:\s*([^\]]+)", original_text)
    if not match:
        return None
    return match.group(1).strip()


def _advance_past_image_in_html(
    html: str,
    original_text: str,
    search_pos: int,
) -> int:
    """Advance cursor past the next <img> matching an image segment placeholder."""
    path = _image_segment_path(original_text)
    needles: List[str] = []
    if path:
        needles.extend([path, path.replace("\\", "/")])
        basename = path.replace("\\", "/").split("/")[-1]
        if basename:
            needles.append(basename)
    for needle in needles:
        idx = html.find(needle, search_pos)
        if idx == -1:
            continue
        img_start = html.rfind("<img", search_pos, idx + len(needle))
        tag_start = img_start if img_start != -1 else idx
        end = html.find(">", tag_start)
        return end + 1 if end != -1 else idx + len(needle)
    img_start = html.lower().find("<img", search_pos)
    if img_start != -1:
        end = html.find(">", img_start)
        return end + 1 if end != -1 else img_start + 4
    return search_pos


def _advance_past_next_leaf_block(html: str, search_pos: int) -> int:
    """Best-effort cursor resync to the next leaf block when text lookup fails."""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    for element in _leaf_block_element_candidates(soup):
        element_html = str(element)
        pos = html.find(element_html, search_pos)
        if pos != -1:
            return pos + len(element_html)
    return search_pos


def _match_block_elements(
    html_content: str,
    soup: Optional[Any] = None,
) -> List[Optional[Tuple[Any, str]]]:
    """
    Map each HtmlExtractor parser block to a BeautifulSoup leaf block element.

    Returns a list aligned 1:1 with ``_parser_blocks(html_content)``. Image blocks
    and empty blocks are ``None``. Text blocks with no DOM match are ``None`` so
    callers can fall back to find-based replacement instead of consuming the
    wrong element.
    """
    from bs4 import BeautifulSoup

    blocks = _parser_blocks(html_content)
    if soup is None:
        soup = BeautifulSoup(html_content, "html.parser")
    candidates = _leaf_block_element_candidates(soup)
    used: set[int] = set()
    aligned: List[Optional[Tuple[Any, str]]] = []
    cand_idx = 0

    for block in blocks:
        if not block or not block.strip() or block.strip().startswith("[Image:"):
            aligned.append(None)
            continue
        element_text_cache = {
            id(el): _element_block_text(el)
            for el in candidates[cand_idx:]
            if id(el) not in used
        }
        found = None
        for i in range(cand_idx, len(candidates)):
            el = candidates[i]
            if id(el) in used:
                continue
            el_text = element_text_cache.get(id(el), _element_block_text(el))
            if _texts_match(block, el_text):
                found = el
                cand_idx = i + 1
                used.add(id(el))
                break
        aligned.append((found, block) if found is not None else None)
    return aligned


def _append_translation_nodes(element: Any, translated: str) -> None:
    """Append plain text or inline HTML fragment nodes to a block element."""
    from bs4 import BeautifulSoup, NavigableString

    if not translated:
        return
    if "<" in translated and ">" in translated:
        fragment = BeautifulSoup(translated, "html.parser")
        for child in list(fragment.contents):
            element.append(child)
        return
    element.append(NavigableString(translated))


def _apply_translations_to_element(
    element: Any,
    original_sub_segments: List[str],
    translations: List[str],
) -> None:
    from bs4 import BeautifulSoup, NavigableString

    if not translations:
        return
    if len(translations) == 1:
        element.clear()
        _append_translation_nodes(element, translations[0])
        return

    uses_line_breaks = bool(element.find_all("br"))
    if not uses_line_breaks and len(original_sub_segments) > 1:
        uses_line_breaks = any("\n" in seg for seg in original_sub_segments)

    element.clear()
    for idx, translated in enumerate(translations):
        if idx > 0:
            if uses_line_breaks:
                element.append(BeautifulSoup("", "html.parser").new_tag("br"))
            elif "<br" in translations[0] or "<br" in translated:
                element.append(BeautifulSoup("<br/><br/>", "html.parser"))
            else:
                element.append(NavigableString("\n\n"))
        _append_translation_nodes(element, translated)


def apply_segment_translations_to_html(
    html_content: str,
    item_segment_entries: List[Dict[str, Any]],
    translated_segments: Dict[int, str],
    chunk_size: int = 3000,
    deep_split: bool = True,
) -> str:
    """
    Apply translated segments to HTML using ordered substring replacement.

    Walks segment_mapping in segment_id order with a moving cursor so duplicate
    source texts map to the correct occurrence. Does not fall back to earlier matches.
    """
    html_out, _, _ = apply_segment_translations_to_html_with_stats(
        html_content,
        item_segment_entries,
        translated_segments,
        chunk_size=chunk_size,
        deep_split=deep_split,
    )
    return html_out


class EpubSegmentReplacementError(RuntimeError):
    """Raised when translated segments cannot be applied to HTML templates."""


def require_segment_replacements(
    applied: int,
    missed: int,
    *,
    item_id: Optional[str] = None,
    task_id: Optional[str] = None,
) -> None:
    if missed > 0:
        raise EpubSegmentReplacementError(
            f"Segment replacement incomplete: applied={applied}, missed={missed}, "
            f"item_id={item_id}, task_id={task_id}",
        )


def split_block_into_segments(
    block: str,
    chunk_size: int,
    deep_split: bool = True,
) -> List[str]:
    """Split one parser block into segments (same rules as HtmlExtractor deep_split)."""
    return _split_plain_text_into_segments(block, chunk_size, deep_split)


def _normalize_html_search_text(text: str) -> str:
    """Normalize text for loose HTML substring search."""
    import html as html_module

    normalized = html_module.unescape(text)
    normalized = normalized.replace("\xa0", " ")
    normalized = re.sub(r"\s+", " ", normalized).strip()
    return normalized


def _decode_html_prefix_length(html: str, end_index: int) -> int:
    """Return decoded text length for html[:end_index] (entity-aware)."""
    import html as html_module

    return len(html_module.unescape(html[:end_index]))


def _encode_html_index_from_decoded(html: str, decoded_index: int) -> int:
    """Map a decoded-text index back to an index in raw HTML."""
    import html as html_module

    decoded_len = 0
    html_index = 0
    while html_index < len(html) and decoded_len < decoded_index:
        if html[html_index] == "&":
            semi = html.find(";", html_index)
            if semi != -1:
                entity = html[html_index: semi + 1]
                decoded_len += len(html_module.unescape(entity))
                html_index = semi + 1
                continue
        decoded_len += 1
        html_index += 1
    return html_index


def _locate_decoded_text_in_html(
    html: str,
    text: str,
    search_pos: int,
) -> Optional[Tuple[int, int]]:
    """Locate plain text in html that may contain entities instead of unicode."""
    import html as html_module

    decoded_html = html_module.unescape(html)
    decoded_search = _decode_html_prefix_length(html, search_pos)
    idx = decoded_html.find(text, decoded_search)
    if idx == -1:
        return None
    start = _encode_html_index_from_decoded(html, idx)
    end = _encode_html_index_from_decoded(html, idx + len(text))
    return start, end - start


def _locate_segment_text_in_html(
    html: str,
    text: str,
    search_pos: int,
) -> Optional[Tuple[int, int]]:
    """Return (start_index, match_length) for segment text inside HTML."""
    if not text:
        return None
    idx = html.find(text, search_pos)
    if idx != -1:
        return idx, len(text)
    if "\n" in text:
        for variant in (
            text.replace("\n", "<br/>"),
            text.replace("\n", "<br />"),
            text.replace("\n", "<br>"),
        ):
            idx = html.find(variant, search_pos)
            if idx != -1:
                return idx, len(variant)
    decoded = _locate_decoded_text_in_html(html, text, search_pos)
    if decoded is not None:
        return decoded
    norm_text = _normalize_html_search_text(text)
    if norm_text and norm_text != text:
        idx = html.find(norm_text, search_pos)
        if idx != -1:
            return idx, len(norm_text)
        decoded_norm = _locate_decoded_text_in_html(html, norm_text, search_pos)
        if decoded_norm is not None:
            return decoded_norm
    return None


def _advance_search_past_segment(
    html: str,
    original_text: str,
    search_pos: int,
) -> int:
    """Move the export cursor past original_text without modifying HTML."""
    if not original_text:
        return search_pos
    from utils.translation_segments import _is_image_segment

    if _is_image_segment(original_text):
        return _advance_past_image_in_html(html, original_text, search_pos)
    loc = _locate_segment_text_in_html(html, original_text, search_pos)
    if loc is None:
        return search_pos
    idx, match_len = loc
    return idx + match_len


def _export_skip_replacement(original: str, translated: str) -> bool:
    """True when export should keep HTML source text unchanged (not counted as missed)."""
    from utils.translation_segments import _is_image_segment

    if not translated:
        return False
    if _is_image_segment(original):
        return True
    if original == translated:
        return True
    return False


_PLACEHOLDER_TITLES = frozenset({"untitled", "mobi content", "content", ""})


def _classify_export_segment_type(
    original_text: str,
    *,
    excluded: bool = False,
) -> str:
    """Classify a segment for export miss diagnostics."""
    from utils.translation_segments import _is_image_segment

    text = (original_text or "").strip()
    if excluded:
        return "excluded"
    if _is_image_segment(original_text):
        return "image"
    if re.match(r"^Rima\s+[IVXLCDM]+$", text, re.IGNORECASE):
        return "toc_entry"
    if re.match(r"^[IVXLCDM]+$", text):
        return "roman_numeral"
    if re.match(r"^\d+$", text):
        return "page_number"
    if len(text) <= 6 and text.isalpha():
        return "short_heading"
    return "text"


def _miss_log_entry(
    reason: str,
    *,
    segment_id: Optional[int] = None,
    original_text: str = "",
    translated_text: str = "",
    excluded: bool = False,
    **extra: Any,
) -> Dict[str, Any]:
    """Build a structured miss-log record with segment text and type."""
    entry: Dict[str, Any] = {
        "segment_id": segment_id,
        "reason": reason,
        "segment_type": _classify_export_segment_type(
            original_text,
            excluded=excluded,
        ),
        "original_text": (original_text or "")[:200],
        "translated_text": (translated_text or "")[:200],
    }
    entry.update(extra)
    return entry


def _log_segment_replace_misses(
    task_id: Optional[str],
    item_id: Optional[str],
    miss_log: List[Dict[str, Any]],
    missed: int,
) -> None:
    if not miss_log:
        return
    try:
        from logger import unified_logger
        from logger.logger import LogModule

        header = (
            f"[MOBI_SEGMENT_REPLACE] task={task_id} item_id={item_id} "
            f"missed={missed} detail_count={len(miss_log)}"
        )
        unified_logger.warning(LogModule.TRANS, header)
        for entry in miss_log[:30]:
            unified_logger.warning(
                LogModule.TRANS,
                "[MOBI_SEGMENT_REPLACE] "
                f"task={task_id} item_id={item_id} "
                f"segment_id={entry.get('segment_id')} "
                f"reason={entry.get('reason')} "
                f"type={entry.get('segment_type')} "
                f"original={entry.get('original_text')!r} "
                f"target={entry.get('translated_text')!r}",
            )
        if len(miss_log) > 30:
            unified_logger.warning(
                LogModule.TRANS,
                f"[MOBI_SEGMENT_REPLACE] task={task_id} item_id={item_id} "
                f"... and {len(miss_log) - 30} more missed segment(s)",
            )
    except ImportError:
        pass


def rebuild_mobi_segment_mapping_from_cache(
    task_state: Optional[Dict[str, Any]],
    html_templates: Dict[str, str],
    *,
    fallback_mapping: Optional[List[Dict[str, Any]]] = None,
) -> List[Dict[str, Any]]:
    """
    Rebuild MOBI segment_mapping using source_chunks_cache (Extract phase authority).

    Keeps item_id assignment from per-chapter extraction while using cache segment texts
    so export-time find/replace aligns with translation_segments indices.
    """
    if not task_state or not html_templates:
        return list(fallback_mapping or [])

    cache_info = task_state.get("source_chunks_cache") or {}
    cache_segments = cache_info.get("segments") or []
    if not cache_segments:
        return list(fallback_mapping or [])

    cache_chunk_size = (
        cache_info.get("chunk_size")
        or task_state.get("mobi_chunk_size")
        or 3000
    )

    item_ranges: List[Tuple[str, int, int]] = []
    total_extracted = 0
    for item_id, html in html_templates.items():
        per_item = extract_paragraph_segments_from_html(
            html,
            chunk_size=int(cache_chunk_size),
            deep_split=True,
        )
        start = total_extracted
        total_extracted += len(per_item)
        item_ranges.append((item_id, start, total_extracted))

    if total_extracted != len(cache_segments):
        first_item = next(iter(html_templates.keys()), "chapter_0")
        fallback_by_id = {
            int(entry["segment_id"]): entry
            for entry in (fallback_mapping or [])
            if entry.get("segment_id") is not None
        }
        try:
            from logger import unified_logger
            from logger.logger import LogModule

            unified_logger.warning(
                LogModule.TRANS,
                "[MOBI_SEGMENT_MAPPING] Cache segment count "
                f"({len(cache_segments)}) != per-item extraction ({total_extracted}); "
                f"using cache texts with item_id from fallback or {first_item!r}",
            )
        except ImportError:
            pass
        return [
            {
                "segment_id": idx,
                "item_id": str(
                    fallback_by_id.get(idx, {}).get("item_id") or first_item
                ),
                "original_text": str(text),
            }
            for idx, text in enumerate(cache_segments)
        ]

    mapping: List[Dict[str, Any]] = []
    for item_id, start, end in item_ranges:
        for idx in range(start, end):
            mapping.append({
                "segment_id": idx,
                "item_id": item_id,
                "original_text": str(cache_segments[idx]),
            })
    return mapping


def build_translated_segments_map(
    segment_mapping: List[Dict[str, Any]],
    task_state: Optional[Dict[str, Any]],
    translated_texts: Optional[List[str]] = None,
) -> Dict[int, str]:
    """Build segment_id -> target text map from translation_segments or mobi_translated_texts."""
    from utils.bilingual_export_utils import (
        build_bilingual_segment_text,
        get_bilingual_config,
        get_bilingual_style_config,
    )
    from utils.translation_segments import _is_image_segment

    bilingual_enabled, target_first = get_bilingual_config(task_state)
    source_italic, source_color, target_italic, target_color = get_bilingual_style_config(
        task_state
    )

    result: Dict[int, str] = {}
    ts_list: Optional[List[Any]] = None
    if task_state:
        ts_data = task_state.get("translation_segments") or {}
        if isinstance(ts_data, dict):
            raw = ts_data.get("segments")
            if isinstance(raw, list):
                ts_list = raw

    for entry in segment_mapping:
        sid = int(entry["segment_id"])
        original = entry.get("original_text") or ""
        text = ""
        is_excluded = False
        is_cleared = False
        if ts_list is not None and 0 <= sid < len(ts_list):
            seg = ts_list[sid]
            if isinstance(seg, dict):
                text = (
                    seg.get("target_text")
                    or seg.get("translated_text")
                    or seg.get("text")
                    or ""
                )
                is_excluded = bool(seg.get("excluded", False))
                is_cleared = bool(seg.get("cleared", False))
            elif seg is not None:
                text = str(seg)
        if not text and translated_texts is not None and sid < len(translated_texts):
            text = translated_texts[sid] or ""
        if bilingual_enabled:
            text = build_bilingual_segment_text(
                original,
                text,
                target_first=target_first,
                is_excluded=is_excluded,
                is_cleared=is_cleared,
                inner_separator="<br/><br/>",
                source_text_italic=source_italic,
                source_text_color=source_color,
                target_text_italic=target_italic,
                target_text_color=target_color,
                use_html_styles=True,
            )
        if text or not _is_image_segment(original):
            result[sid] = text

    revised = (task_state or {}).get("revised_segments") or {}
    for seg_id, seg_data in revised.items():
        if not isinstance(seg_data, dict):
            continue
        target_text = seg_data.get("target_text")
        if not target_text:
            continue
        try:
            sid = int(seg_id)
        except (TypeError, ValueError):
            continue
        if bilingual_enabled:
            original = ""
            for entry in segment_mapping:
                if int(entry.get("segment_id", -1)) == sid:
                    original = entry.get("original_text") or ""
                    break
            target_text = build_bilingual_segment_text(
                original,
                target_text,
                target_first=target_first,
                inner_separator="<br/><br/>",
                source_text_italic=source_italic,
                source_text_color=source_color,
                target_text_italic=target_italic,
                target_text_color=target_color,
                use_html_styles=True,
            )
        result[sid] = target_text
    return result


def _dom_fallback_replace_segment(
    html: str,
    translated_text: str,
    search_pos: int,
) -> Optional[Tuple[str, int]]:
    """
    Replace the next leaf block after search_pos when substring find fails.

    Used for cache/HTML spelling drift (e.g. OCR typo in cache vs correct HTML text).
    """
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    for element in _leaf_block_element_candidates(soup):
        element_html = str(element)
        pos = html.find(element_html, search_pos)
        if pos == -1:
            continue
        block_text = _element_block_text(element)
        if not block_text or not block_text.strip():
            continue
        _apply_translations_to_element(element, [block_text], [translated_text])
        updated = str(element)
        new_html = html[:pos] + updated + html[pos + len(element_html):]
        return new_html, pos + len(updated)
    return None


def _apply_entry_via_find(
    html: str,
    search_pos: int,
    segment_id: int,
    original_text: str,
    translated_text: str,
) -> Tuple[str, int, bool]:
    """
    Replace one segment via ordered substring search.

    Returns (updated_html, new_search_pos, applied).
    """
    if not original_text or not translated_text:
        return html, search_pos, False
    if translated_text == original_text:
        new_pos = _advance_search_past_segment(html, original_text, search_pos)
        return html, new_pos, False

    loc = _locate_segment_text_in_html(html, original_text, search_pos)
    if loc is not None:
        idx, match_len = loc
        updated = html[:idx] + translated_text + html[idx + match_len:]
        return updated, idx + len(translated_text), True

    fallback = _dom_fallback_replace_segment(html, translated_text, search_pos)
    if fallback is not None:
        updated, new_pos = fallback
        return updated, new_pos, True

    return html, search_pos, False


def _consume_image_entries(entries: List[Dict[str, Any]], ptr: int) -> int:
    """Advance ptr past consecutive image segment entries."""
    from utils.translation_segments import _is_image_segment

    while ptr < len(entries):
        original_text = entries[ptr].get("original_text") or ""
        if not _is_image_segment(original_text):
            break
        ptr += 1
    return ptr


def _process_entry_for_export(
    *,
    segment_id: int,
    original_text: str,
    translated_text: str,
    excluded_segment_ids: set[int],
    html_for_find: str,
    search_pos: int,
    miss_log: List[Dict[str, Any]],
) -> Tuple[str, int, int, int]:
    """
    Apply or skip one segment during export.

    Returns (html_for_find, search_pos, applied_delta, missed_delta).
    """
    from utils.translation_segments import _is_image_segment

    if segment_id in excluded_segment_ids or _is_image_segment(original_text):
        new_pos = _advance_search_past_segment(html_for_find, original_text, search_pos)
        return html_for_find, new_pos, 0, 0

    if not translated_text:
        miss_log.append(_miss_log_entry(
            "empty_target",
            segment_id=segment_id,
            original_text=original_text,
            translated_text=translated_text,
            excluded=segment_id in excluded_segment_ids,
        ))
        return html_for_find, search_pos, 0, 1

    if _export_skip_replacement(original_text, translated_text):
        new_pos = _advance_search_past_segment(html_for_find, original_text, search_pos)
        return html_for_find, new_pos, 0, 0

    if translated_text == original_text:
        new_pos = _advance_search_past_segment(html_for_find, original_text, search_pos)
        return html_for_find, new_pos, 0, 0

    updated_html, new_pos, applied = _apply_entry_via_find(
        html_for_find,
        search_pos,
        segment_id,
        original_text,
        translated_text,
    )
    if applied:
        return updated_html, new_pos, 1, 0

    miss_log.append(_miss_log_entry(
        "not_found",
        segment_id=segment_id,
        original_text=original_text,
        translated_text=translated_text,
    ))
    return html_for_find, search_pos, 0, 1


def _apply_segment_translations_via_find(
    html_content: str,
    item_segment_entries: List[Dict[str, Any]],
    translated_segments: Dict[int, str],
    excluded_segment_ids: set[int],
    *,
    task_id: Optional[str] = None,
    item_id: Optional[str] = None,
) -> Tuple[str, int, int]:
    """Apply translations using ordered substring replacement with a moving cursor."""
    entries = sorted(item_segment_entries, key=lambda s: int(s["segment_id"]))
    modified_html = html_content
    search_pos = 0
    applied = 0
    missed = 0
    miss_log: List[Dict[str, Any]] = []

    for entry in entries:
        segment_id = int(entry["segment_id"])
        original_text = entry.get("original_text") or ""
        if not original_text:
            continue
        translated_text = translated_segments.get(segment_id, "")
        modified_html, search_pos, applied_delta, missed_delta = _process_entry_for_export(
            segment_id=segment_id,
            original_text=original_text,
            translated_text=translated_text,
            excluded_segment_ids=excluded_segment_ids,
            html_for_find=modified_html,
            search_pos=search_pos,
            miss_log=miss_log,
        )
        applied += applied_delta
        missed += missed_delta

    _log_segment_replace_misses(task_id, item_id, miss_log, missed)
    return modified_html, applied, missed


def _apply_segment_translations_via_dom(
    html_content: str,
    item_segment_entries: List[Dict[str, Any]],
    translated_segments: Dict[int, str],
    chunk_size: int,
    deep_split: bool,
    excluded_segment_ids: set[int],
    *,
    task_id: Optional[str] = None,
    item_id: Optional[str] = None,
) -> Tuple[str, int, int]:
    """Apply translations by aligning parser blocks to DOM elements with find fallback."""
    from bs4 import BeautifulSoup

    from utils.translation_segments import _is_image_segment

    entries = sorted(item_segment_entries, key=lambda s: int(s["segment_id"]))
    ptr = 0
    applied = 0
    missed = 0
    miss_log: List[Dict[str, Any]] = []

    soup = BeautifulSoup(html_content, "html.parser")
    blocks = _parser_blocks(html_content)
    aligned_matches = _match_block_elements(html_content, soup)

    for block, match in zip(blocks, aligned_matches):
        if not block or not block.strip():
            continue

        if block.strip().startswith("[Image:"):
            ptr = _consume_image_entries(entries, ptr)
            continue

        sub_segments = split_block_into_segments(block, chunk_size, deep_split)
        if not sub_segments:
            continue

        if match is None:
            # No DOM target for this parser block; defer to tail find pass on str(soup).
            for _sub in sub_segments:
                if ptr >= len(entries):
                    missed += 1
                    miss_log.append(_miss_log_entry(
                        "entry_exhausted",
                        original_text=_sub,
                        segment_type="text",
                    ))
                    break
                ptr += 1
            continue

        element, _block_text = match
        orig_subs: List[str] = []
        trans_subs: List[str] = []

        for sub in sub_segments:
            if ptr >= len(entries):
                missed += 1
                miss_log.append(_miss_log_entry(
                    "entry_exhausted",
                    original_text=sub,
                    segment_type="text",
                ))
                break

            entry = entries[ptr]
            sid = int(entry["segment_id"])
            original_text = entry.get("original_text") or ""
            ptr += 1

            if sid in excluded_segment_ids or _is_image_segment(original_text):
                continue

            translated_text = translated_segments.get(sid, "")
            if not translated_text:
                missed += 1
                miss_log.append(_miss_log_entry(
                    "empty_target",
                    segment_id=sid,
                    original_text=original_text,
                    translated_text=translated_text,
                ))
                continue

            if _export_skip_replacement(original_text, translated_text):
                continue

            if translated_text == original_text:
                continue

            if not _segment_texts_match(original_text, sub):
                el_text = _element_block_text(element)
                if len(sub_segments) == 1 and el_text:
                    orig_subs = [el_text]
                    trans_subs = [translated_text]
                    applied += 1
                    break
                if _compact_text(original_text) == _compact_text(sub):
                    orig_subs.append(sub)
                    trans_subs.append(translated_text)
                    applied += 1
                    continue
                missed += 1
                miss_log.append(_miss_log_entry(
                    "text_mismatch",
                    segment_id=sid,
                    original_text=original_text,
                    translated_text=translated_text,
                    html_sub=sub[:200],
                ))
                continue

            orig_subs.append(sub)
            trans_subs.append(translated_text)
            applied += 1

        if orig_subs and trans_subs:
            _apply_translations_to_element(element, orig_subs, trans_subs)

    # Tail find pass must run on DOM-updated HTML. Never replace str(soup) with a
    # parallel string built from the original template (that discards DOM edits).
    html_out = str(soup)
    find_search_pos = 0
    while ptr < len(entries):
        entry = entries[ptr]
        sid = int(entry["segment_id"])
        original_text = entry.get("original_text") or ""
        translated_text = translated_segments.get(sid, "")
        ptr += 1
        html_out, find_search_pos, applied_delta, missed_delta = (
            _process_entry_for_export(
                segment_id=sid,
                original_text=original_text,
                translated_text=translated_text,
                excluded_segment_ids=excluded_segment_ids,
                html_for_find=html_out,
                search_pos=find_search_pos,
                miss_log=miss_log,
            )
        )
        applied += applied_delta
        missed += missed_delta

    _log_segment_replace_misses(task_id, item_id, miss_log, missed)
    return html_out, applied, missed


def apply_segment_translations_to_html_with_stats(
    html_content: str,
    item_segment_entries: List[Dict[str, Any]],
    translated_segments: Dict[int, str],
    chunk_size: int = 3000,
    deep_split: bool = True,
    excluded_segment_ids: Optional[set[int]] = None,
    *,
    task_id: Optional[str] = None,
    item_id: Optional[str] = None,
) -> Tuple[str, int, int]:
    """Apply translations and return (html, applied_count, missed_count)."""
    excluded = excluded_segment_ids or set()
    return _apply_segment_translations_via_dom(
        html_content,
        item_segment_entries,
        translated_segments,
        chunk_size=chunk_size,
        deep_split=deep_split,
        excluded_segment_ids=excluded,
        task_id=task_id,
        item_id=item_id,
    )
