# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations

import io
import os
import zipfile
import xml.etree.ElementTree as ET
from typing import List

from .base import Extractor, ExtractResult


class EpubExtractor(Extractor):
    """
    Extract textual content from an EPUB archive and split into preview segments.

    The implementation mirrors the legacy EPUB translator logic: it reads
    META-INF/container.xml to locate the OPF package, respects the spine reading
    order, parses XHTML/HTML resources with BeautifulSoup, and aggregates plain
    text for preview.
    """

    def __init__(self, file_bytes: bytes, chunk_size: int = 3000):
        self.file_bytes = file_bytes
        self.chunk_size = chunk_size

    def extract(self) -> ExtractResult:
        try:
            from bs4 import BeautifulSoup  # type: ignore
        except ImportError:
            # Without BeautifulSoup we cannot reliably parse XHTML – return empty result.
            return ExtractResult(segments=[])

        try:
            with zipfile.ZipFile(io.BytesIO(self.file_bytes), 'r') as zf:
                if 'META-INF/container.xml' not in zf.namelist():
                    return ExtractResult(segments=[])

                container_xml = zf.read('META-INF/container.xml')
                container_root = ET.fromstring(container_xml)
                ns = {'cn': 'urn:oasis:names:tc:opendocument:xmlns:container'}
                rootfile = container_root.find('cn:rootfiles/cn:rootfile', ns)
                if rootfile is None:
                    return ExtractResult(segments=[])

                opf_path = rootfile.get('full-path')
                if not opf_path:
                    return ExtractResult(segments=[])

                opf_content = zf.read(opf_path)
                opf_root = ET.fromstring(opf_content)
                ns_opf = {'opf': 'http://www.idpf.org/2007/opf'}

                manifest_items = {}
                for item in opf_root.findall('opf:manifest/opf:item', ns_opf):
                    item_id = item.get('id')
                    href = item.get('href')
                    media_type = item.get('media-type', '')
                    if not item_id or not href:
                        continue
                    full_href = os.path.join(os.path.dirname(opf_path), href).replace("\\", "/")
                    manifest_items[item_id] = {'href': full_href, 'media_type': media_type}

                spine_itemrefs = [
                    item.get('idref')
                    for item in opf_root.findall('opf:spine/opf:itemref', ns_opf)
                    if item.get('idref')
                ]

                reading_order = spine_itemrefs or list(manifest_items.keys())
                text_fragments: List[str] = []
                segment_info: List[dict] = []

                skip_tags = {'style', 'script', 'head', 'title', 'meta', '[document]'}

                for index, item_id in enumerate(reading_order):
                    item = manifest_items.get(item_id)
                    if not item:
                        continue
                    media_type = item['media_type']
                    if media_type not in (
                        'application/xhtml+xml',
                        'text/html',
                        'application/x-dtbook+xml',
                        'application/xml',
                    ):
                        continue

                    file_path = item['href']
                    if file_path not in zf.namelist():
                        continue

                    html_bytes = zf.read(file_path)
                    soup = BeautifulSoup(html_bytes, 'html.parser')
                    for node in soup.find_all(string=True):
                        parent_name = getattr(node.parent, "name", None)
                        if parent_name in skip_tags:
                            continue
                        text = node.strip()
                        if text:
                            text_fragments.append(text)
                            segment_info.append({
                                "file": file_path,
                                "index_in_file": len(segment_info),
                                "global_index": len(text_fragments) - 1,
                            })

                if not text_fragments:
                    return ExtractResult(segments=[])

                # Join fragments with double newlines to retain paragraph separation, then split.
                combined_text = "\n\n".join(text_fragments)
                from utils.markdown_splitter import split_markdown_text

                # Use deep_split=True to split by paragraphs instead of chunk_size
                # Each paragraph becomes its own segment (unless it exceeds max_block_size)
                segments = split_markdown_text(combined_text, max_block_size=self.chunk_size, deep_split=True)
                return ExtractResult(
                    segments=segments,
                    segment_info=[
                        {"source": "epub", "index": idx} for idx in range(len(segments))
                    ],
                )
        except Exception:
            # On failure, fall back to empty preview to avoid breaking the pipeline.
            return ExtractResult(segments=[])

