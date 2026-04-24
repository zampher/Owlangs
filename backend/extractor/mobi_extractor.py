# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations

import io
from typing import List

from .base import Extractor, ExtractResult
from logger import unified_logger as logger
from logger.logger import LogModule


class MobiExtractor(Extractor):
    """
    Extract textual content from a MOBI file and split into preview segments.

    The implementation uses ebooklib to read MOBI files, extracts text from
    all chapters in reading order, parses HTML content with BeautifulSoup,
    and aggregates plain text for preview.
    """

    def __init__(self, file_bytes: bytes, chunk_size: int = 3000):
        self.file_bytes = file_bytes
        self.chunk_size = chunk_size

    def extract(self) -> ExtractResult:
        try:
            import ebooklib
            from ebooklib import epub
            from bs4 import BeautifulSoup  # type: ignore
        except ImportError:
            # Without ebooklib and BeautifulSoup we cannot parse MOBI – return empty result.
            return ExtractResult(segments=[])

        try:
            # Read MOBI file - ebooklib doesn't support MOBI directly
            # MOBI is a binary format, not ZIP-based like EPUB
            # Try using mobi library if available, otherwise fall back to error handling
            try:
                # Try using mobi library for MOBI files
                logger.debug(LogModule.EXTRACT, "[MOBI_EXTRACTOR] attempting to import mobi library...")
                import mobi
                logger.debug(LogModule.EXTRACT, f"[MOBI_EXTRACTOR] import mobi SUCCESS from {getattr(mobi, '__file__', 'unknown')}")
                import tempfile
                import os
                import shutil
                temp_file = None
                bookpath = None
                epub_file_path = None
                
                try:
                    # Create temporary file for mobi library
                    with tempfile.NamedTemporaryFile(delete=False, suffix='.mobi') as tmp:
                        tmp.write(self.file_bytes)
                        temp_file = tmp.name
                    logger.debug(LogModule.EXTRACT, f"[MOBI_EXTRACTOR] temp mobi file created: {temp_file}, size={len(self.file_bytes)} bytes")
                    
                    # Extract MOBI file - mobi library extracts to a directory
                    logger.debug(LogModule.EXTRACT, "[MOBI_EXTRACTOR] calling mobi.extract()...")
                    bookpath, epubpath = mobi.extract(temp_file)
                    logger.debug(LogModule.EXTRACT, f"[MOBI_EXTRACTOR] mobi.extract() returned bookpath={bookpath}, epubpath={epubpath}")
                    
                    # Check what was extracted
                    # bookpath is the directory where files were extracted
                    # epubpath might point to an HTML file, EPUB file, or other format
                    html_file_path = None
                    
                    if epubpath and os.path.exists(epubpath):
                        # Check if it's an EPUB file (ZIP archive)
                        if epubpath.lower().endswith('.epub'):
                            try:
                                import zipfile
                                # Verify it's a valid ZIP/EPUB
                                with zipfile.ZipFile(epubpath, 'r') as zf:
                                    epub_file_path = epubpath
                            except (zipfile.BadZipFile, Exception) as zip_err:
                                # Not a valid EPUB, might be HTML or other format
                                logger.warning(LogModule.EXTRACT, f"[MOBI_EXTRACTOR] epubpath is invalid EPUB: {epubpath}, error: {zip_err}")
                                pass
                        
                        # Check if it's an HTML file
                        if epubpath.lower().endswith('.html') or epubpath.lower().endswith('.htm'):
                            html_file_path = epubpath
                    
                    # If no EPUB found, look for EPUB files in the extracted directory
                    if not epub_file_path and bookpath and os.path.isdir(bookpath):
                        for root, dirs, files in os.walk(bookpath):
                            for file in files:
                                if file.lower().endswith('.epub'):
                                    try:
                                        import zipfile
                                        epub_candidate = os.path.join(root, file)
                                        # Verify it's a valid EPUB
                                        with zipfile.ZipFile(epub_candidate, 'r') as zf:
                                            epub_file_path = epub_candidate
                                            break
                                    except:
                                        continue
                            if epub_file_path:
                                break
                    
                    # If no EPUB found, look for HTML files in the extracted directory
                    if not epub_file_path and not html_file_path and bookpath and os.path.isdir(bookpath):
                        for root, dirs, files in os.walk(bookpath):
                            for file in files:
                                if file.lower().endswith('.html') or file.lower().endswith('.htm'):
                                    html_file_path = os.path.join(root, file)
                                    break
                            if html_file_path:
                                break
                    
                    # Read the content
                    if epub_file_path:
                        # Read EPUB file
                        logger.debug(LogModule.EXTRACT, f"[MOBI_EXTRACTOR] reading EPUB: {epub_file_path}")
                        book = epub.read_epub(epub_file_path)
                        logger.debug(LogModule.EXTRACT, f"[MOBI_EXTRACTOR] EPUB read success, items={len(list(book.get_items()))}")
                    elif html_file_path:
                        # Read HTML file directly - mobi library extracted HTML content
                        # We'll parse it with BeautifulSoup instead of ebooklib
                        with open(html_file_path, 'rb') as f:
                            html_content = f.read()
                        # Parse HTML directly with BeautifulSoup
                        from bs4 import BeautifulSoup
                        soup = BeautifulSoup(html_content, 'html.parser')
                        # Extract text fragments from HTML
                        text_fragments = []
                        skip_tags = {'style', 'script', 'head', 'title', 'meta', '[document]'}
                        for node in soup.find_all(string=True):
                            parent_name = getattr(node.parent, "name", None)
                            if parent_name in skip_tags:
                                continue
                            text = node.strip()
                            if text:
                                text_fragments.append(text)
                        
                        if not text_fragments:
                            raise ValueError(f"MOBI extraction produced HTML file but no text content found. HTML path: {html_file_path}")
                        
                        # Join fragments and split into segments
                        combined_text = "\n\n".join(text_fragments)
                        from utils.markdown_splitter import split_markdown_text
                        # Use deep_split=True to split by paragraphs instead of chunk_size
                        # Each paragraph becomes its own segment (unless it exceeds max_block_size)
                        segments = split_markdown_text(combined_text, max_block_size=self.chunk_size, deep_split=True)
                        return ExtractResult(
                            segments=segments,
                            segment_info=[
                                {"source": "mobi", "index": idx} for idx in range(len(segments))
                            ],
                        )
                    else:
                        # No valid file found
                        raise ValueError(f"MOBI extraction did not produce a readable EPUB or HTML file. Extracted path: {epubpath}, Book path: {bookpath}")
                    
                finally:
                    # Clean up temporary file and extracted directory
                    # Note: We clean up after reading the book, but ebooklib may cache content
                    if temp_file and os.path.exists(temp_file):
                        try:
                            os.unlink(temp_file)
                        except:
                            pass
                    # Clean up extracted directory if it exists
                    # Delay cleanup slightly to ensure book reading is complete
                    if bookpath and os.path.isdir(bookpath):
                        try:
                            # Use a small delay to ensure file handles are released
                            import time
                            time.sleep(0.1)
                            shutil.rmtree(bookpath)
                        except:
                            pass
            except ImportError as import_err:
                # mobi library not available
                logger.error(LogModule.EXTRACT, f"[MOBI_EXTRACTOR] import mobi FAILED with ImportError: {import_err}", exc_info=True)
                # Cannot extract MOBI without mobi library
                return ExtractResult(segments=[])
            except Exception as mobi_error:
                # mobi library failed
                logger.error(LogModule.EXTRACT, f"[MOBI_EXTRACTOR] mobi.extract() or post-processing FAILED: {mobi_error}", exc_info=True)
                # Try ebooklib as last resort (will likely fail for MOBI)
                try:
                    book = epub.read_epub(io.BytesIO(self.file_bytes))
                except Exception as epub_error:
                    logger.error(LogModule.EXTRACT, f"[MOBI_EXTRACTOR] Failed to read MOBI with ebooklib fallback: {epub_error}")
                    return ExtractResult(segments=[])
            
            if not book:
                logger.warning(LogModule.EXTRACT, "MOBI extraction returned empty book object")
                return ExtractResult(segments=[])

            text_fragments: List[str] = []
            segment_info: List[dict] = []

            skip_tags = {'style', 'script', 'head', 'title', 'meta', '[document]'}

            # Get all items in the book (chapters, sections, etc.)
            # ebooklib represents MOBI content as items
            items = list(book.get_items())
            
            # Filter for HTML/XHTML content items
            html_items = [
                item for item in items
                if item.get_type() == ebooklib.ITEM_DOCUMENT
            ]

            # Process items in order (spine order if available, otherwise manifest order)
            spine = book.spine
            if spine:
                # Process items according to spine order
                for spine_item in spine:
                    item_id = spine_item[0]
                    item = book.get_item_with_id(item_id)
                    if item and item.get_type() == ebooklib.ITEM_DOCUMENT:
                        self._extract_text_from_item(item, text_fragments, segment_info, skip_tags)
            else:
                # No spine, process all HTML items in order
                for item in html_items:
                    self._extract_text_from_item(item, text_fragments, segment_info, skip_tags)

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
                    {"source": "mobi", "index": idx} for idx in range(len(segments))
                ],
            )
        except Exception as e:
            # Log the error for debugging
            logger.error(LogModule.EXTRACT, f"MOBI extraction failed: {e}", exc_info=True)
            # On failure, fall back to empty preview to avoid breaking the pipeline.
            return ExtractResult(segments=[])

    def _extract_text_from_item(self, item, text_fragments: List[str], segment_info: List[dict], skip_tags: set):
        """Extract text from a single ebooklib item."""
        try:
            from bs4 import BeautifulSoup  # type: ignore
            
            content = item.get_content()
            if not content:
                return
            
            soup = BeautifulSoup(content, 'html.parser')
            for node in soup.find_all(string=True):
                parent_name = getattr(node.parent, "name", None)
                if parent_name in skip_tags:
                    continue
                text = node.strip()
                if text:
                    text_fragments.append(text)
                    segment_info.append({
                        "file": item.get_name(),
                        "index_in_file": len(segment_info),
                        "global_index": len(text_fragments) - 1,
                    })
        except Exception:
            # Skip items that cannot be parsed
            pass

