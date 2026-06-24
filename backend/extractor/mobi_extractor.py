# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations

import io
from typing import List

from .base import Extractor, ExtractResult
from logger import unified_logger as logger
from logger.logger import LogModule
from utils.epub_html_segments import decode_html_bytes, extract_paragraph_segments_from_html


class MobiExtractor(Extractor):
    """
    Extract textual content from a MOBI file and split into preview segments.

    Uses HtmlExtractor paragraph splitting (same as HTML workflow) so Extract
    preview segments align with translation segments.
    """

    def __init__(self, file_bytes: bytes, chunk_size: int = 3000):
        self.file_bytes = file_bytes
        self.chunk_size = chunk_size

    def extract(self) -> ExtractResult:
        try:
            import ebooklib
            from ebooklib import epub
        except ImportError:
            return ExtractResult(segments=[])

        try:
            book = None
            try:
                logger.debug(LogModule.EXTRACT, "[MOBI_EXTRACTOR] attempting to import mobi library...")
                import mobi
                import tempfile
                import os
                import shutil
                temp_file = None
                bookpath = None
                epub_file_path = None

                try:
                    with tempfile.NamedTemporaryFile(delete=False, suffix=".mobi") as tmp:
                        tmp.write(self.file_bytes)
                        temp_file = tmp.name

                    bookpath, epubpath = mobi.extract(temp_file)
                    html_file_path = None

                    if epubpath and os.path.exists(epubpath):
                        if epubpath.lower().endswith(".epub"):
                            try:
                                import zipfile
                                with zipfile.ZipFile(epubpath, "r") as zf:
                                    epub_file_path = epubpath
                            except Exception as zip_err:
                                logger.warning(
                                    LogModule.EXTRACT,
                                    f"[MOBI_EXTRACTOR] epubpath is invalid EPUB: {epubpath}, error: {zip_err}",
                                )
                        if epubpath.lower().endswith((".html", ".htm")):
                            html_file_path = epubpath

                    if not epub_file_path and bookpath and os.path.isdir(bookpath):
                        for root, _, files in os.walk(bookpath):
                            for file in files:
                                if file.lower().endswith(".epub"):
                                    try:
                                        import zipfile
                                        epub_candidate = os.path.join(root, file)
                                        with zipfile.ZipFile(epub_candidate, "r") as zf:
                                            epub_file_path = epub_candidate
                                            break
                                    except Exception:
                                        continue
                            if epub_file_path:
                                break

                    if not epub_file_path and not html_file_path and bookpath and os.path.isdir(bookpath):
                        for root, _, files in os.walk(bookpath):
                            for file in files:
                                if file.lower().endswith((".html", ".htm")):
                                    html_file_path = os.path.join(root, file)
                                    break
                            if html_file_path:
                                break

                    if epub_file_path:
                        book = epub.read_epub(epub_file_path)
                    elif html_file_path:
                        with open(html_file_path, "rb") as f:
                            html_content = f.read()
                        segments = extract_paragraph_segments_from_html(
                            decode_html_bytes(html_content),
                            chunk_size=self.chunk_size,
                            deep_split=True,
                        )
                        return ExtractResult(
                            segments=segments,
                            segment_info=[
                                {"source": "mobi", "index": idx} for idx in range(len(segments))
                            ],
                        )
                    else:
                        raise ValueError(
                            f"MOBI extraction did not produce a readable EPUB or HTML file. "
                            f"Extracted path: {epubpath}, Book path: {bookpath}"
                        )
                finally:
                    if temp_file and os.path.exists(temp_file):
                        try:
                            os.unlink(temp_file)
                        except Exception:
                            pass
                    if bookpath and os.path.isdir(bookpath):
                        try:
                            import time
                            time.sleep(0.1)
                            shutil.rmtree(bookpath)
                        except Exception:
                            pass
            except ImportError as import_err:
                logger.error(
                    LogModule.EXTRACT,
                    f"[MOBI_EXTRACTOR] import mobi FAILED with ImportError: {import_err}",
                    exc_info=True,
                )
                return ExtractResult(segments=[])
            except Exception as mobi_error:
                logger.error(
                    LogModule.EXTRACT,
                    f"[MOBI_EXTRACTOR] mobi.extract() or post-processing FAILED: {mobi_error}",
                    exc_info=True,
                )
                try:
                    book = epub.read_epub(io.BytesIO(self.file_bytes))
                except Exception as epub_error:
                    logger.error(
                        LogModule.EXTRACT,
                        f"[MOBI_EXTRACTOR] Failed to read MOBI with ebooklib fallback: {epub_error}",
                    )
                    return ExtractResult(segments=[])

            if not book:
                logger.warning(LogModule.EXTRACT, "MOBI extraction returned empty book object")
                return ExtractResult(segments=[])

            segments = self._extract_segments_from_book(book)
            if not segments:
                return ExtractResult(segments=[])

            return ExtractResult(
                segments=segments,
                segment_info=[
                    {"source": "mobi", "index": idx} for idx in range(len(segments))
                ],
            )
        except Exception as e:
            logger.error(LogModule.EXTRACT, f"MOBI extraction failed: {e}", exc_info=True)
            return ExtractResult(segments=[])

    def _extract_segments_from_book(self, book) -> List[str]:
        import ebooklib

        segments: List[str] = []
        html_items = [
            item for item in book.get_items()
            if item.get_type() == ebooklib.ITEM_DOCUMENT
        ]

        spine = book.spine
        items_to_process = []
        if spine:
            for spine_item in spine:
                item_id = spine_item[0]
                item = book.get_item_with_id(item_id)
                if item and item.get_type() == ebooklib.ITEM_DOCUMENT:
                    items_to_process.append(item)
        else:
            items_to_process = html_items

        for item in items_to_process:
            content = item.get_content()
            if not content:
                continue
            html_str = decode_html_bytes(content) if isinstance(content, bytes) else content
            file_segments = extract_paragraph_segments_from_html(
                html_str,
                chunk_size=self.chunk_size,
                deep_split=True,
            )
            segments.extend(file_segments)

        return segments
