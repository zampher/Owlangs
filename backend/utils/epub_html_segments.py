# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

"""Shared EPUB HTML iteration and paragraph-level segment extraction."""

from __future__ import annotations

import io
import os
import xml.etree.ElementTree as ET
import zipfile
from typing import Dict, List, Tuple

EPUB_HTML_MEDIA_TYPES = frozenset({
    "application/xhtml+xml",
    "text/html",
    "application/x-dtbook+xml",
    "application/xml",
})


def read_epub_all_files(epub_bytes: bytes) -> Dict[str, bytes]:
    """Read all files from an EPUB archive into a path -> bytes map."""
    with zipfile.ZipFile(io.BytesIO(epub_bytes), "r") as zf:
        return {name: zf.read(name) for name in zf.namelist()}


def get_epub_html_files_in_reading_order(all_files: Dict[str, bytes]) -> List[Tuple[str, bytes]]:
    """
    Return (file_path, html_bytes) pairs in spine reading order.

    Falls back to manifest order when spine is empty.
    """
    container_xml = all_files.get("META-INF/container.xml")
    if not container_xml:
        return []

    container_root = ET.fromstring(container_xml)
    ns = {"cn": "urn:oasis:names:tc:opendocument:xmlns:container"}
    rootfile = container_root.find("cn:rootfiles/cn:rootfile", ns)
    if rootfile is None:
        return []

    opf_path = rootfile.get("full-path")
    if not opf_path:
        return []

    opf_content = all_files.get(opf_path)
    if not opf_content:
        return []

    opf_root = ET.fromstring(opf_content)
    ns_opf = {"opf": "http://www.idpf.org/2007/opf"}
    opf_dir = os.path.dirname(opf_path)

    manifest_items: Dict[str, dict] = {}
    for item in opf_root.findall("opf:manifest/opf:item", ns_opf):
        item_id = item.get("id")
        href = item.get("href")
        if not item_id or not href:
            continue
        full_href = os.path.join(opf_dir, href).replace("\\", "/")
        manifest_items[item_id] = {
            "href": full_href,
            "media_type": item.get("media-type", ""),
        }

    spine_itemrefs = [
        item.get("idref")
        for item in opf_root.findall("opf:spine/opf:itemref", ns_opf)
        if item.get("idref")
    ]
    reading_order = spine_itemrefs or list(manifest_items.keys())

    html_files: List[Tuple[str, bytes]] = []
    for item_id in reading_order:
        item = manifest_items.get(item_id)
        if not item:
            continue
        if item["media_type"] not in EPUB_HTML_MEDIA_TYPES:
            continue
        file_path = item["href"]
        html_bytes = all_files.get(file_path)
        if html_bytes:
            html_files.append((file_path, html_bytes))
    return html_files


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
