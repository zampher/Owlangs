# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0
import asyncio
import io
import os
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from io import BytesIO
from typing import Self, Literal, List, Dict, Any, Optional

import ebooklib
from ebooklib import epub
from bs4 import BeautifulSoup, NavigableString

from agents.segments_agent import SegmentsTranslateAgentConfig, SegmentsTranslateAgent
from ir.document import Document
from translator.ai_translator.base import AiTranslatorConfig, AiTranslator
from logger.logger import LogModule


@dataclass
class MobiTranslatorConfig(AiTranslatorConfig):
    insert_mode: Literal["replace", "append", "prepend"] = "replace"
    separator: str = "\n"


class MobiTranslator(AiTranslator):
    """
    A translator for translating content in MOBI files.
    This version uses ebooklib to read MOBI files and extract/translate text.
    Note: ebooklib may not support direct MOBI writing, so we may need to
    convert to EPUB for processing, then convert back to MOBI.
    """

    def __init__(self, config: MobiTranslatorConfig):
        super().__init__(config=config)
        self.chunk_size = config.chunk_size
        self.translate_agent = None
        if not self.skip_translate:
            agent_config = SegmentsTranslateAgentConfig(
                custom_prompt=config.custom_prompt,
                to_lang=config.to_lang,
                base_url=config.base_url,
                api_key=config.api_key,
                model_id=config.model_id,
                api_type=getattr(config, 'api_type', None) or getattr(config, 'api_protocol', None) or 'openai',
                temperature=config.temperature,
                thinking=config.thinking,
                concurrent=config.concurrent,
                connect_timeout=getattr(config, 'connect_timeout', 15),
                timeout=config.timeout,
                write_timeout=getattr(config, 'write_timeout', None),
                logger=self.logger,
                glossary_dict=config.glossary_dict,
                retry=config.retry,
                max_tokens=getattr(config, 'max_tokens', None),  # Get max_tokens from platform config
                segment_limit=getattr(config, 'segment_limit', 100),
                use_seg_tags=True,  # Use SEG-tag format for MOBI segments
            )
            self.translate_agent = SegmentsTranslateAgent(agent_config)
        self.insert_mode = config.insert_mode
        self.separator = config.separator

    def _pre_translate(self, document: Document) -> tuple[
        Any, List[Dict[str, Any]], List[str]
    ]:
        """
        Preprocess MOBI file and extract all text that needs translation.
        Returns: (book object, items_to_translate, original_texts)
        """
        items_to_translate = []
        original_texts = []

        # --- Step 1: Use mobi library or ebooklib to read MOBI content ---
        book = None
        try:
            # Try using mobi library for MOBI files
            import mobi
            import tempfile
            import os
            import shutil
            temp_file = None
            bookpath = None
            epub_file_path = None
            html_file_path = None
            mobi_source_html_content = None  # Used to merge HTML meta (description, publisher, etc.) into ebook_metadata
            
            try:
                # Create temporary file for mobi library
                with tempfile.NamedTemporaryFile(delete=False, suffix='.mobi') as tmp:
                    tmp.write(document.content)
                    temp_file = tmp.name
                
                # Extract MOBI file - mobi library extracts to a directory
                bookpath, epubpath = mobi.extract(temp_file)
                
                # Check what was extracted
                # bookpath is the directory where files were extracted
                # epubpath might point to an HTML file, EPUB file, or other format
                if epubpath and os.path.exists(epubpath):
                    # Check if it's an EPUB file (ZIP archive)
                    if epubpath.lower().endswith('.epub'):
                        try:
                            import zipfile
                            # Verify it's a valid ZIP/EPUB
                            with zipfile.ZipFile(epubpath, 'r') as zf:
                                epub_file_path = epubpath
                        except (zipfile.BadZipFile, Exception) as zip_error:
                            # Not a valid EPUB, might be HTML or other format
                            # Log for debugging but continue to check for HTML
                            self.logger.debug(
                                LogModule.TRANS,
                                f"[MOBI_TRANSLATOR] epubpath points to invalid EPUB: {epubpath}, error: {zip_error}"
                            )
                    
                    # Check if it's an HTML file (check extension first, then content)
                    if epubpath.lower().endswith('.html') or epubpath.lower().endswith('.htm'):
                        html_file_path = epubpath
                    elif not epub_file_path:
                        # If not EPUB and extension doesn't indicate HTML, check file content
                        # Some MOBI files extract to files without .html extension
                        try:
                            with open(epubpath, 'rb') as f:
                                content_start = f.read(1024).decode('utf-8', errors='ignore').lower()
                                if '<html' in content_start or '<!doctype html' in content_start:
                                    html_file_path = epubpath
                                    self.logger.debug(
                                        LogModule.TRANS,
                                        f"[MOBI_TRANSLATOR] Detected HTML file by content: {epubpath}"
                                    )
                        except Exception:
                            pass
                
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
                # CRITICAL: Read file content BEFORE cleanup to avoid "Bad Zip file" errors
                if epub_file_path:
                    # Read EPUB file - read content immediately before cleanup
                    try:
                        book = epub.read_epub(epub_file_path)
                    except Exception as epub_read_error:
                        # If reading fails, try to read file content first, then parse
                        # This ensures file is not deleted before reading
                        raise ValueError(
                            f"Failed to read EPUB file from MOBI extraction. "
                            f"EPUB path: {epub_file_path}, Error: {epub_read_error}"
                        )
                elif html_file_path:
                    # Read HTML file directly - mobi library extracted HTML content
                    # Read content immediately before cleanup
                    with open(html_file_path, 'rb') as f:
                        html_content = f.read()
                    mobi_source_html_content = html_content  # For merging meta into ebook_metadata later
                    
                    # Try to extract title from HTML content
                    title_text = self._extract_title_from_html(html_content)
                    # No fallback - if no title found, use empty string or None
                    # Some MOBI documents don't have titles, which is acceptable
                    
                    # Create a new EPUB book from HTML content
                    book = epub.EpubBook()
                    # Add a chapter with the HTML content
                    chapter = epub.EpubHtml(
                        title='Content',
                        file_name='content.xhtml',
                        lang='en'
                    )
                    from utils.epub_fix import sanitize_html_for_epub
                    html_str = html_content.decode("utf-8", errors="replace") if isinstance(html_content, bytes) else html_content
                    chapter.content = sanitize_html_for_epub(html_str)
                    if isinstance(chapter.content, str):
                        chapter.content = chapter.content.encode("utf-8")
                    book.add_item(chapter)
                    # Add chapter to spine. Do not add 'nav' unless we add an actual nav item;
                    # otherwise Apple Books (and other strict readers) will reject the EPUB.
                    book.spine = [chapter]
                    # Set metadata (dc:title required by EPUB; post-process adds nav)
                    book.set_identifier('mobi-html-conversion')
                    book.set_title(title_text if title_text else "Untitled")
                    book.set_language('en')
                    author_from_html = self._extract_author_from_html(html_content)
                    if author_from_html:
                        book.add_metadata("DC", "creator", author_from_html)
                    # task_state['ebook_metadata'] is filled later from book.get_metadata() in the same _pre_translate
                else:
                    # No valid file found
                    raise ValueError(
                        f"MOBI extraction did not produce a readable EPUB or HTML file. "
                        f"Extracted path: {epubpath}, Book path: {bookpath}"
                    )
            finally:
                # Clean up temporary file and extracted directory
                # CRITICAL: Only clean up AFTER book object is created and content is read
                # This prevents "Bad Zip file" errors when epub.read_epub() tries to access files
                if temp_file and os.path.exists(temp_file):
                    try:
                        os.unlink(temp_file)
                    except:
                        pass
                # Clean up extracted directory if it exists
                # Delay cleanup to ensure book reading is complete
                if bookpath and os.path.isdir(bookpath):
                    try:
                        # Use a longer delay to ensure file handles are released
                        # epub.read_epub() may keep file handles open
                        import time
                        time.sleep(0.5)  # Increased delay from 0.1 to 0.5 seconds
                        shutil.rmtree(bookpath)
                    except:
                        pass
        except ImportError:
            # mobi library not available, try ebooklib directly (will likely fail)
            try:
                book = epub.read_epub(BytesIO(document.content))
            except Exception as e:
                raise ValueError(f"Invalid MOBI file. Please install 'mobi' library: pip install mobi. Error: {e}")
        except Exception as mobi_error:
            # mobi library failed, try ebooklib as fallback
            try:
                book = epub.read_epub(BytesIO(document.content))
            except Exception as epub_error:
                raise ValueError(f"Failed to read MOBI file. mobi library error: {mobi_error}, ebooklib error: {epub_error}")

        if not book:
            raise ValueError("Failed to read MOBI file")

        # --- Step 2: Extract translatable content ---
        # Get all document items (chapters, sections, etc.)
        items = list(book.get_items())
        html_items = [
            item for item in items
            if item.get_type() == ebooklib.ITEM_DOCUMENT
        ]

        # Process items according to spine order if available
        spine = book.spine
        items_to_process = []
        if spine:
            for spine_item in spine:
                # Handle different spine formats:
                # 1. Tuple format: (item_id, linear) - spine_item[0] is item_id
                # 2. 'nav' format: ['nav', item1, item2, ...] - spine_item is 'nav' or EpubHtml object
                if isinstance(spine_item, tuple):
                    # Tuple format: (item_id, linear)
                    item_id = spine_item[0]
                    item = book.get_item_with_id(item_id)
                elif isinstance(spine_item, str) and spine_item == 'nav':
                    # Skip 'nav' marker
                    continue
                elif hasattr(spine_item, 'get_id'):
                    # EpubHtml object (from manually created spine)
                    item = spine_item
                else:
                    # Unknown format, skip
                    continue
                
                if item and item.get_type() == ebooklib.ITEM_DOCUMENT:
                    items_to_process.append(item)
        else:
            items_to_process = html_items

        # OPTIMIZATION: Store original HTML templates for delayed DOM generation
        # This allows us to skip DOM operations during translation and generate DOM only when exporting
        html_templates = {}  # item_id -> original_html_content
        segment_mapping = []  # List of segment info: {segment_id, item_id, original_text}
        
        # Extract text from each item
        for item in items_to_process:
            content = item.get_content()
            if not content:
                continue

            # OPTIMIZATION: Save original HTML template (for delayed DOM generation)
            item_id = item.get_id()
            original_html = content.decode('utf-8') if isinstance(content, bytes) else content
            html_templates[item_id] = original_html

            from utils.epub_html_segments import extract_paragraph_segments_from_html

            file_segments = extract_paragraph_segments_from_html(
                original_html,
                chunk_size=self.chunk_size,
                deep_split=True,
            )
            for text in file_segments:
                segment_id = len(original_texts)
                original_texts.append(text)
                segment_mapping.append({
                    "segment_id": segment_id,
                    "item_id": item_id,
                    "original_text": text,
                })

        # OPTIMIZATION: Extract images and save to task_state (if available)
        # This allows images to be used in preview and export phases
        image_data_map = {}  # image_path -> {"data": base64_data_uri, "mime": mime_type}
        try:
            # Extract all images from the book
            import base64
            import mimetypes
            
            for item in book.get_items():
                if item.get_type() == ebooklib.ITEM_IMAGE:
                    try:
                        img_data = item.get_content()
                        if img_data:
                            item_name = item.get_name() or ''
                            # Get MIME type
                            mime_type, _ = mimetypes.guess_type(item_name)
                            if not mime_type:
                                # Fallback: detect from content
                                if img_data.startswith(b'\x89PNG'):
                                    mime_type = 'image/png'
                                elif img_data.startswith(b'\xff\xd8'):
                                    mime_type = 'image/jpeg'
                                elif img_data.startswith(b'GIF'):
                                    mime_type = 'image/gif'
                                elif img_data.startswith(b'<svg') or img_data.startswith(b'<?xml'):
                                    mime_type = 'image/svg+xml'
                                else:
                                    mime_type = 'image/png'  # Default fallback
                            
                            # Convert to base64 data URI
                            img_base64 = base64.b64encode(img_data).decode('utf-8')
                            data_uri = f"data:{mime_type};base64,{img_base64}"
                            
                            # Store image data
                            # Use item_name as key, or item_id if name is not available
                            image_key = item_name if item_name else item.get_id()
                            image_data_map[image_key] = {
                                "data": data_uri,
                                "mime": mime_type,
                                "size": len(img_data)
                            }
                    except Exception as img_error:
                        self.logger.warning(
                            LogModule.TRANS,
                            f"[MOBI_TRANSLATOR] _pre_translate: Failed to extract image {item.get_name()}: {img_error}",
                            exc_info=True
                        )
                        continue
            
            if image_data_map:
                # Log image details for debugging
                image_keys = list(image_data_map.keys())[:5]  # First 5 image keys
                self.logger.info(
                    LogModule.TRANS,
                    f"[MOBI_TRANSLATOR] _pre_translate: Extracted {len(image_data_map)} images. "
                    f"Sample image keys: {image_keys}"
                )
                # Log each image for detailed debugging
                for img_key, img_info in list(image_data_map.items())[:10]:  # First 10 images
                    self.logger.debug(
                        LogModule.TRANS,
                        f"[MOBI_TRANSLATOR] _pre_translate: Image extracted - key={img_key}, "
                        f"mime={img_info.get('mime')}, size={img_info.get('size')} bytes"
                    )
        except Exception as e:
            self.logger.warning(
                LogModule.TRANS,
                f"[MOBI_TRANSLATOR] _pre_translate: Failed to extract images: {e}",
                exc_info=True
            )

        # OPTIMIZATION: Save HTML templates, segment mapping, and images to task_state (if available)
        # This will be used in export phase to generate DOM from templates
        try:
            task_id = getattr(self, '_task_id', None)
            if task_id:
                from backend.app.services.task import task_manager
                task_state = task_manager.get_task(task_id) if task_id else None
                if task_state:
                    task_state['mobi_html_templates'] = html_templates
                    task_state['mobi_segment_mapping'] = segment_mapping
                    # Save images to task_state (similar to DOCX workflow)
                    if image_data_map:
                        # Store in both mobi_image_data_map and image_data_map for compatibility
                        task_state['mobi_image_data_map'] = image_data_map
                        task_state['image_data_map'] = image_data_map
                    # Extract and save full ebook metadata (title, author, language, identifier, etc.) for export
                    try:
                        from utils.ebook_metadata import (
                            extract_from_ebooklib_book,
                            extract_from_html_meta,
                            merge_metadata,
                        )
                        meta = extract_from_ebooklib_book(book)
                        if mobi_source_html_content:
                            meta = merge_metadata(meta, extract_from_html_meta(mobi_source_html_content))
                        if any(meta.get(k) for k in meta):
                            task_state['ebook_metadata'] = meta
                            self.logger.debug(
                                LogModule.TRANS,
                                "[MOBI_TRANSLATOR] _pre_translate: Saved ebook_metadata (title, author, language, ...)"
                            )
                    except Exception as meta_err:
                        self.logger.debug(
                            LogModule.TRANS,
                            f"[MOBI_TRANSLATOR] _pre_translate: Could not extract ebook metadata: {meta_err}"
                        )
                    
                    # CRITICAL: Generate mobi_image_segments_info here (during _pre_translate)
                    # This ensures image segments are available for _record_mobi_segments
                    # without waiting for frontend to call get_source_preview
                    cache_info = task_state.get("source_chunks_cache", {})
                    cache_segments = cache_info.get("segments", [])
                    if html_templates and image_data_map and cache_segments:
                        self._generate_image_segments_info(
                            task_id, task_state, html_templates, image_data_map, cache_segments
                        )
                    
                    self.logger.info(
                        LogModule.TRANS,
                        f"[MOBI_TRANSLATOR] _pre_translate: Saved HTML templates for {len(html_templates)} items, "
                        f"{len(segment_mapping)} segment mappings, and {len(image_data_map)} images "
                        f"for delayed DOM generation, task_id={task_id}"
                    )
        except Exception as e:
            self.logger.debug(
                LogModule.TRANS,
                f"[MOBI_TRANSLATOR] _pre_translate: Could not save data to task_state: {e}"
            )

        return book, items_to_translate, original_texts

    def _extract_title_from_html(self, html_content: bytes) -> Optional[str]:
        """
        Extract title from HTML content.
        Tries to find title in <title> tag or first <h1> tag.
        Returns None if no title is found.
        """
        try:
            html_str = html_content.decode('utf-8', errors='ignore')
            soup = BeautifulSoup(html_str, 'html.parser')
            
            # Try to get title from <title> tag
            title_tag = soup.find('title')
            if title_tag and title_tag.string:
                title_text = title_tag.string.strip()
                if title_text and title_text.lower() not in ('untitled', 'mobi content'):
                    return title_text
            
            # Try to get title from first <h1> tag
            h1_tag = soup.find('h1')
            if h1_tag:
                h1_text = h1_tag.get_text(strip=True)
                if h1_text and h1_text.lower() not in ('untitled', 'mobi content'):
                    return h1_text
            
            # Try to get title from first heading (h1-h6)
            for tag_name in ['h1', 'h2', 'h3', 'h4', 'h5', 'h6']:
                heading = soup.find(tag_name)
                if heading:
                    heading_text = heading.get_text(strip=True)
                    if heading_text and heading_text.lower() not in ('untitled', 'mobi content'):
                        return heading_text
            
            return None
        except Exception as e:
            self.logger.debug(LogModule.TRANS, f"[MOBI_TRANSLATOR] Failed to extract title from HTML: {e}")
            return None

    def _extract_author_from_html(self, html_content: bytes) -> Optional[str]:
        """
        Extract author from HTML content for EPUB metadata.
        Tries <meta name="author">, <meta name="DC.creator">, <meta property="author">.
        """
        try:
            html_str = html_content.decode("utf-8", errors="ignore")
            soup = BeautifulSoup(html_str, "html.parser")
            meta = soup.find("meta", attrs={"name": "author"})
            if meta and meta.get("content"):
                return meta["content"].strip() or None
            meta = soup.find("meta", attrs={"name": "DC.creator"})
            if meta and meta.get("content"):
                return meta["content"].strip() or None
            meta = soup.find("meta", attrs={"property": "author"})
            if meta and meta.get("content"):
                return meta["content"].strip() or None
            return None
        except Exception as e:
            self.logger.debug(LogModule.TRANS, f"[MOBI_TRANSLATOR] Failed to extract author from HTML: {e}")
            return None

    def _generate_image_segments_info(
        self,
        task_id: str,
        task_state: Dict[str, Any],
        html_templates: Dict[str, str],
        image_data_map: Dict[str, Dict[str, Any]],
        cache_segments: List[str]
    ):
        """
        Generate mobi_image_segments_info from HTML templates and image data map.
        This is the same logic as in get_source_preview, but called during _pre_translate
        to ensure image segments are available for _record_mobi_segments.
        
        Args:
            task_id: Task identifier
            task_state: Task state dictionary
            html_templates: HTML templates dictionary (item_id -> html_content)
            image_data_map: Image data map (image_path -> {data, mime, size})
            cache_segments: Text segments from source_chunks_cache
        """
        try:
            from bs4 import BeautifulSoup
            import os
            
            mobi_image_segments_info = []
            
            # Check each HTML template for img tags
            for item_id, html_content in html_templates.items():
                try:
                    soup = BeautifulSoup(html_content, 'html.parser')
                    img_tags = soup.find_all('img')
                    
                    for img in img_tags:
                        src = img.get('src', '')
                        if not src:
                            continue
                        
                        # Try to match src with image_data_map keys
                        matched_image_path = None
                        for image_path in image_data_map.keys():
                            if src == image_path:
                                matched_image_path = image_path
                                break
                            src_filename = os.path.basename(src)
                            image_filename = os.path.basename(image_path)
                            if src_filename == image_filename:
                                matched_image_path = image_path
                                break
                            if src in image_path or image_path in src:
                                matched_image_path = image_path
                                break
                            src_fixed = src.replace('一', 'i').replace('mages', 'images')
                            if src_fixed in image_path or image_path in src_fixed:
                                matched_image_path = image_path
                                break
                        
                        if matched_image_path:
                            placeholder_id = matched_image_path
                            
                            # Try to find the position of this img tag relative to text segments
                            insert_index = None
                            context_before = None
                            context_after = None
                            
                            try:
                                before_text_nodes = []
                                after_text_nodes = []
                                
                                # Strategy 1: Check siblings within parent
                                parent = img.parent
                                if parent:
                                    siblings = list(parent.children)
                                    img_sibling_index = None
                                    for i, sibling in enumerate(siblings):
                                        if sibling == img:
                                            img_sibling_index = i
                                            break
                                    
                                    if img_sibling_index is not None:
                                        for i in range(img_sibling_index - 1, -1, -1):
                                            sibling = siblings[i]
                                            if isinstance(sibling, str) and sibling.strip():
                                                before_text_nodes.insert(0, sibling.strip())
                                            elif hasattr(sibling, 'get_text'):
                                                text = sibling.get_text(strip=True)
                                                if text:
                                                    before_text_nodes.insert(0, text)
                                        
                                        for i in range(img_sibling_index + 1, len(siblings)):
                                            sibling = siblings[i]
                                            if isinstance(sibling, str) and sibling.strip():
                                                after_text_nodes.append(sibling.strip())
                                            elif hasattr(sibling, 'get_text'):
                                                text = sibling.get_text(strip=True)
                                                if text:
                                                    after_text_nodes.append(text)
                                
                                # Strategy 2: If no text found in siblings, check body-level adjacent elements
                                if not before_text_nodes and not after_text_nodes:
                                    body = soup.find('body')
                                    if body and parent:
                                        body_children = list(body.children)
                                        parent_index = None
                                        for i, child in enumerate(body_children):
                                            if child == parent:
                                                parent_index = i
                                                break
                                        
                                        if parent_index is not None:
                                            for i in range(parent_index - 1, -1, -1):
                                                prev_elem = body_children[i]
                                                if hasattr(prev_elem, 'get_text'):
                                                    text = prev_elem.get_text(strip=True)
                                                    if text:
                                                        before_text_nodes.insert(0, text)
                                                        if len(before_text_nodes) > 0:
                                                            before_text_nodes = [before_text_nodes[-1]]
                                                            break
                                            
                                            for i in range(parent_index + 1, len(body_children)):
                                                next_elem = body_children[i]
                                                if hasattr(next_elem, 'get_text'):
                                                    text = next_elem.get_text(strip=True)
                                                    if text:
                                                        after_text_nodes.append(text)
                                                        if len(after_text_nodes) > 0:
                                                            after_text_nodes = [after_text_nodes[0]]
                                                            break
                                
                                # Try to match before_text_nodes to segments
                                if before_text_nodes:
                                    sorted_before_texts = sorted(before_text_nodes, key=len, reverse=True)
                                    for before_text in sorted_before_texts:
                                        if not before_text:
                                            continue
                                        context_before = before_text[:100]
                                        for seg_idx, seg_text in enumerate(cache_segments):
                                            if isinstance(seg_text, str):
                                                if before_text == seg_text.strip():
                                                    insert_index = seg_idx + 1
                                                    break
                                                elif before_text in seg_text:
                                                    insert_index = seg_idx + 1
                                                    break
                                                elif len(before_text) > 20 and seg_text.strip() in before_text:
                                                    insert_index = seg_idx + 1
                                                    break
                                            if insert_index is not None:
                                                break
                                        if insert_index is not None:
                                            break
                                
                                # If not found, try matching after_text_nodes
                                if insert_index is None and after_text_nodes:
                                    sorted_after_texts = sorted(after_text_nodes, key=len)
                                    for after_text in sorted_after_texts:
                                        if not after_text:
                                            continue
                                        context_after = after_text[:100]
                                        for seg_idx, seg_text in enumerate(cache_segments):
                                            if isinstance(seg_text, str):
                                                if after_text == seg_text.strip():
                                                    insert_index = seg_idx
                                                    break
                                                elif after_text in seg_text:
                                                    insert_index = seg_idx
                                                    break
                                                elif len(after_text) > 20 and seg_text.strip() in after_text:
                                                    insert_index = seg_idx
                                                    break
                                            if insert_index is not None:
                                                break
                                        if insert_index is not None:
                                            break
                                
                                # Fallback: append to end
                                if insert_index is None:
                                    insert_index = len(cache_segments) + len(mobi_image_segments_info)
                            except Exception as pos_error:
                                insert_index = len(cache_segments) + len(mobi_image_segments_info)
                            
                            image_info = image_data_map.get(matched_image_path, {})
                            data_uri = image_info.get("data", "")
                            placeholder_text = f"<ph-{placeholder_id}>"
                            
                            mobi_image_segments_info.append({
                                "insert_index": insert_index,
                                "placeholder_id": placeholder_id,
                                "image_path": matched_image_path,
                                "placeholder_text": placeholder_text,
                                "image_data": data_uri,
                            })
                            
                            self.logger.debug(
                                LogModule.TRANS,
                                f"[MOBI_TRANSLATOR] _generate_image_segments_info: Generated image segment info - "
                                f"insert_index={insert_index}, placeholder_id={placeholder_id}, image_path={matched_image_path}"
                            )
                except Exception as e:
                    self.logger.warning(
                        LogModule.TRANS,
                        f"[MOBI_TRANSLATOR] _generate_image_segments_info: Failed to parse HTML template for item_id={item_id}: {e}",
                        exc_info=True
                    )
                    continue
            
            # Save to task_state
            if mobi_image_segments_info:
                task_state["mobi_image_segments_info"] = mobi_image_segments_info
                self.logger.info(
                    LogModule.TRANS,
                    f"[MOBI_TRANSLATOR] _generate_image_segments_info: Generated and saved {len(mobi_image_segments_info)} image segments info to task_state, task_id={task_id}"
                )
        except Exception as e:
            self.logger.warning(
                LogModule.TRANS,
                f"[MOBI_TRANSLATOR] _generate_image_segments_info: Failed to generate image segments info: {e}",
                exc_info=True
            )

    def _after_translate(
            self,
            book: Any,
            items_to_translate: List[Dict[str, Any]],
            translated_texts: List[str],
            original_texts: List[str],
    ) -> bytes:
        """
        Write translated text back and repackage into MOBI/EPUB file.
        Note: Since ebooklib may not support direct MOBI writing, we convert to EPUB.
        The EPUB can later be converted back to MOBI using external tools if needed.
        """
        import time
        start_time = time.time()
        task_id = getattr(self, '_task_id', None)
        
        self.logger.info(
            LogModule.TRANS,
            f"[MOBI_TRANSLATOR] _after_translate STARTED: task_id={task_id}, "
            f"items_count={len(items_to_translate)}, translated_texts_count={len(translated_texts)}, "
            f"original_texts_count={len(original_texts) if original_texts else 0}"
        )
        
        # Validate inputs
        if not items_to_translate:
            self.logger.warning(
                LogModule.TRANS,
                f"[MOBI_TRANSLATOR] _after_translate: items_to_translate is empty, task_id={task_id}"
            )
            return b""
        
        if not translated_texts:
            self.logger.warning(
                LogModule.TRANS,
                f"[MOBI_TRANSLATOR] _after_translate: translated_texts is empty, task_id={task_id}"
            )
            return b""
        
        # Step 1: Replace text nodes with translated text
        step1_start = time.time()
        modified_soups = {}
        
        try:
            self.logger.info(
                LogModule.TRANS,
                f"[MOBI_TRANSLATOR] _after_translate Step 1 STARTED: task_id={task_id}, "
                f"processing {len(items_to_translate)} items"
            )
            
            # Validate inputs before processing
            if len(items_to_translate) != len(translated_texts):
                raise ValueError(
                    f"Items count mismatch: items_to_translate={len(items_to_translate)}, "
                    f"translated_texts={len(translated_texts)}"
                )
            
            # OPTIMIZATION: Build segment index -> translated text map from chunk data
            # This allows batch processing of chunks instead of segment-by-segment
            translated_map = {}
            chunk_data = None
            try:
                from backend.app.services.task import task_manager
                task_state = task_manager.get_task(task_id) if task_id else None
                if task_state and 'llm_api_output' in task_state:
                    chunk_data = task_state.get('llm_api_output')
                    if chunk_data and isinstance(chunk_data, list):
                        # Build map from chunk data (each chunk is a dict with segment indices as keys)
                        for chunk_idx, chunk in enumerate(chunk_data):
                            if isinstance(chunk, dict):
                                for seg_idx_str, translated_text in chunk.items():
                                    try:
                                        seg_idx = int(seg_idx_str)
                                        if seg_idx < len(items_to_translate):
                                            translated_map[seg_idx] = translated_text
                                    except (ValueError, TypeError):
                                        continue
                        if translated_map:
                            self.logger.info(
                                LogModule.TRANS,
                                f"[MOBI_TRANSLATOR] _after_translate Step 1: Built translation map from {len(chunk_data)} chunks, "
                                f"covering {len(translated_map)}/{len(items_to_translate)} segments, task_id={task_id}"
                            )
            except Exception as e:
                self.logger.debug(
                    LogModule.TRANS,
                    f"[MOBI_TRANSLATOR] _after_translate Step 1: Could not build map from chunk data: {e}, "
                    f"falling back to segment-by-segment processing"
                )
            
            # Fallback: if chunk data not available, use translated_texts list
            if not translated_map:
                translated_map = {i: translated_texts[i] for i in range(len(translated_texts))}
            
            # OPTIMIZATION: Convert original_texts list to map for O(1) lookup
            # This avoids repeated list indexing operations
            original_texts_map = {i: original_texts[i] for i in range(len(original_texts))}
            
            self.logger.info(
                LogModule.TRANS,
                f"[MOBI_TRANSLATOR] _after_translate Step 1: Created maps - "
                f"translated_map size={len(translated_map)}, original_texts_map size={len(original_texts_map)}, task_id={task_id}"
            )
            
            # OPTIMIZATION: Group items by item (epub item) for parallel processing
            # Each epub item is independent, so we can process them in parallel
            # If items share the same soup, we can still parallelize by batching items
            items_by_item = {}
            for i, item_info in enumerate(items_to_translate):
                item = item_info.get("item")
                if item is not None:
                    if item not in items_by_item:
                        items_by_item[item] = []
                    items_by_item[item].append((i, item_info))
            
            # Calculate parallel processing parameters
            import multiprocessing
            cpu_count = multiprocessing.cpu_count()
            max_workers = max(1, cpu_count // 2)
            
            self.logger.info(
                LogModule.TRANS,
                f"[MOBI_TRANSLATOR] _after_translate Step 1: Parallel processing calculation - "
                f"CPU cores={cpu_count}, max_workers={max_workers} (CPU cores // 2), task_id={task_id}"
            )
            
            # If we have only one item (all items share the same soup), batch items for parallel processing
            # Divide items into chunks based on CPU cores
            if len(items_by_item) == 1:
                # All items share the same item/soup, batch them for parallel processing
                items_list = list(items_by_item.values())[0]
                total_items = len(items_list)
                batch_size = max(100, total_items // max_workers)  # At least 100 items per batch
                calculated_batches = (total_items + batch_size - 1) // batch_size  # Ceiling division
                
                self.logger.info(
                    LogModule.TRANS,
                    f"[MOBI_TRANSLATOR] _after_translate Step 1: Batching calculation - "
                    f"total_items={total_items}, max_workers={max_workers}, "
                    f"batch_size={batch_size} (max(100, {total_items} // {max_workers})), "
                    f"calculated_batches={calculated_batches} (ceiling({total_items} / {batch_size})), task_id={task_id}"
                )
                
                batches = []
                for batch_start in range(0, len(items_list), batch_size):
                    batch_end = min(batch_start + batch_size, len(items_list))
                    batches.append(items_list[batch_start:batch_end])
                
                self.logger.info(
                    LogModule.TRANS,
                    f"[MOBI_TRANSLATOR] _after_translate Step 1: All {len(items_to_translate)} items share the same item/soup, "
                    f"batching into {len(batches)} batches for parallel processing (batch_size={batch_size}, max_workers={max_workers}), task_id={task_id}"
                )
                items_by_item = {f"batch_{idx}": batch for idx, batch in enumerate(batches)}
            else:
                self.logger.info(
                    LogModule.TRANS,
                    f"[MOBI_TRANSLATOR] _after_translate Step 1: Grouped {len(items_to_translate)} items into "
                    f"{len(items_by_item)} unique items for parallel processing, task_id={task_id}"
                )
            
            # Statistics for optimization tracking
            fast_path_count = 0
            slow_path_count = 0
            
            def process_item_batch(batch_data):
                """Process a batch of items (can be from same or different items/soups)"""
                import time
                batch_start_time = time.time()
                batch_key, items_list = batch_data
                batch_fast_count = 0
                batch_slow_count = 0
                items_processed = 0
                
                # Performance tracking
                lookup_time = 0
                dom_operation_time = 0
                string_operation_time = 0
                
                for i, item_info in items_list:
                    try:
                        # Performance: Track lookup time
                        lookup_start = time.time()
                        text_node = item_info.get("text_node")
                        translated_text = translated_map.get(i)
                        original_text = original_texts_map.get(i)
                        lookup_time += time.time() - lookup_start
                        
                        if text_node is None:
                            continue
                        
                        if translated_text is None:
                            translated_text = original_text or ""
                        
                        # Performance: Track string operation time
                        string_start = time.time()
                        if self.insert_mode == "replace":
                            new_text = translated_text
                        elif self.insert_mode == "append":
                            new_text = (original_text or "") + self.separator + translated_text
                        elif self.insert_mode == "prepend":
                            new_text = translated_text + self.separator + (original_text or "")
                        else:
                            new_text = translated_text
                        string_operation_time += time.time() - string_start
                        
                        # OPTIMIZATION: Direct string assignment (fastest)
                        # Check if text_node is still in the tree before attempting replacement
                        # Performance: Track DOM operation time
                        dom_start = time.time()
                        parent = text_node.parent
                        if parent is not None:
                            try:
                                # Try direct assignment first (fastest)
                                parent.string = new_text
                                batch_fast_count += 1
                            except (AttributeError, ValueError):
                                # Fallback to replace_with if direct assignment fails
                                # Check if text_node is still in the tree
                                if text_node.parent is not None:
                                    text_node.replace_with(NavigableString(new_text))
                                    batch_slow_count += 1
                                else:
                                    # Text node was already removed, skip it
                                    self.logger.warning(
                                        LogModule.TRANS,
                                        f"[MOBI_TRANSLATOR] _after_translate Step 1: Item {i} text_node is not part of tree, skipping"
                                    )
                                    dom_operation_time += time.time() - dom_start
                                    continue
                        else:
                            # No parent, check if we can still use replace_with
                            if hasattr(text_node, 'replace_with'):
                                try:
                                    text_node.replace_with(NavigableString(new_text))
                                    batch_slow_count += 1
                                except ValueError as e:
                                    # Text node is not part of tree
                                    self.logger.warning(
                                        LogModule.TRANS,
                                        f"[MOBI_TRANSLATOR] _after_translate Step 1: Item {i} text_node is not part of tree (no parent), skipping: {e}"
                                    )
                                    dom_operation_time += time.time() - dom_start
                                    continue
                            else:
                                self.logger.warning(
                                    LogModule.TRANS,
                                    f"[MOBI_TRANSLATOR] _after_translate Step 1: Item {i} text_node has no parent and no replace_with method, skipping"
                                )
                                dom_operation_time += time.time() - dom_start
                                continue
                        dom_operation_time += time.time() - dom_start
                        
                        items_processed += 1
                    except Exception as item_error:
                        self.logger.error(
                            LogModule.TRANS,
                            f"[MOBI_TRANSLATOR] _after_translate Step 1: Error processing item {i} in batch {batch_key}: {item_error}",
                            exc_info=True
                        )
                        continue
                
                batch_duration = time.time() - batch_start_time
                # Log performance breakdown for this batch
                self.logger.info(
                    LogModule.TRANS,
                    f"[MOBI_TRANSLATOR] _after_translate Step 1: Batch {batch_key} performance - "
                    f"items={items_processed}, duration={batch_duration:.2f}s, "
                    f"lookup_time={lookup_time:.2f}s ({lookup_time/batch_duration*100:.1f}%), "
                    f"string_time={string_operation_time:.2f}s ({string_operation_time/batch_duration*100:.1f}%), "
                    f"dom_time={dom_operation_time:.2f}s ({dom_operation_time/batch_duration*100:.1f}%), "
                    f"fast_path={batch_fast_count}, slow_path={batch_slow_count}, task_id={task_id}"
                )
                
                return batch_fast_count, batch_slow_count, items_processed
            
            # Process items in parallel if we have multiple batches/items
            total_processed = 0
            if len(items_by_item) > 1 and max_workers > 1:
                self.logger.info(
                    LogModule.TRANS,
                    f"[MOBI_TRANSLATOR] _after_translate Step 1: Processing {len(items_by_item)} batches/items in parallel "
                    f"using {max_workers} workers, task_id={task_id}"
                )
                
                with ThreadPoolExecutor(max_workers=max_workers) as executor:
                    # Submit all tasks
                    future_to_batch = {
                        executor.submit(process_item_batch, (batch_key, items_list)): (batch_key, len(items_list))
                        for batch_key, items_list in items_by_item.items()
                    }
                    
                    # Process results as they complete
                    for future in future_to_batch:
                        batch_fast, batch_slow, batch_processed = future.result()
                        fast_path_count += batch_fast
                        slow_path_count += batch_slow
                        total_processed += batch_processed
                        
                        # Log progress
                        if total_processed % 100 == 0 or total_processed == len(items_to_translate):
                            elapsed = time.time() - step1_start
                            rate = total_processed / elapsed if elapsed > 0 else 0
                            remaining_items = len(items_to_translate) - total_processed
                            eta = remaining_items / rate if rate > 0 else 0
                            self.logger.info(
                                LogModule.TRANS,
                                f"[MOBI_TRANSLATOR] _after_translate Step 1 progress: task_id={task_id}, "
                                f"processed {total_processed}/{len(items_to_translate)} items ({total_processed*100//len(items_to_translate)}%), "
                                f"elapsed={elapsed:.2f}s, rate={rate:.2f} items/s, ETA={eta:.1f}s"
                            )
            else:
                # Sequential processing for single batch/item or single worker
                for batch_idx, (batch_key, items_list) in enumerate(items_by_item.items()):
                    batch_fast, batch_slow, batch_processed = process_item_batch((batch_key, items_list))
                    fast_path_count += batch_fast
                    slow_path_count += batch_slow
                    total_processed += batch_processed
                    
                    # Log progress
                    if total_processed % 100 == 0 or total_processed == len(items_to_translate):
                        elapsed = time.time() - step1_start
                        rate = total_processed / elapsed if elapsed > 0 else 0
                        remaining_items = len(items_to_translate) - total_processed
                        eta = remaining_items / rate if rate > 0 else 0
                        self.logger.info(
                            LogModule.TRANS,
                            f"[MOBI_TRANSLATOR] _after_translate Step 1 progress: task_id={task_id}, "
                            f"processed {total_processed}/{len(items_to_translate)} items ({total_processed*100//len(items_to_translate)}%), "
                            f"elapsed={elapsed:.2f}s, rate={rate:.2f} items/s, ETA={eta:.1f}s"
                        )
            
            # Track modified soups for Step 2 (collect unique soups from all items)
            for batch_key, items_list in items_by_item.items():
                for i, item_info in items_list:
                    soup = item_info.get("soup")
                    if soup is not None and soup not in modified_soups:
                        modified_soups[soup] = item_info.get("item")
            
            step1_duration = time.time() - step1_start
            self.logger.info(
                LogModule.TRANS,
                f"[MOBI_TRANSLATOR] _after_translate Step 1 (replace text nodes) COMPLETED: "
                f"task_id={task_id}, duration={step1_duration:.2f}s, items_processed={len(items_to_translate)}, "
                f"unique_soups={len(modified_soups)}, fast_path={fast_path_count}, slow_path={slow_path_count}"
            )
        except Exception as e:
            step1_duration = time.time() - step1_start
            self.logger.error(
                LogModule.TRANS,
                f"[MOBI_TRANSLATOR] _after_translate Step 1 FAILED: task_id={task_id}, "
                f"duration={step1_duration:.2f}s, error={e}",
                exc_info=True
            )
            raise

        # Step 2: Update items with modified content
        step2_start = time.time()
        try:
            self.logger.info(
                LogModule.TRANS,
                f"[MOBI_TRANSLATOR] _after_translate Step 2 STARTED: task_id={task_id}, "
                f"updating {len(modified_soups)} items"
            )
            
            for idx, (soup, item) in enumerate(modified_soups.items()):
                # Log progress every 50 items
                if idx > 0 and idx % 50 == 0:
                    elapsed = time.time() - step2_start
                    self.logger.info(
                        LogModule.TRANS,
                        f"[MOBI_TRANSLATOR] _after_translate Step 2 progress: task_id={task_id}, "
                        f"updated {idx}/{len(modified_soups)} items, elapsed={elapsed:.2f}s"
                    )
                item.set_content(str(soup).encode('utf-8'))
            
            step2_duration = time.time() - step2_start
            self.logger.info(
                LogModule.TRANS,
                f"[MOBI_TRANSLATOR] _after_translate Step 2 (update item content) COMPLETED: "
                f"task_id={task_id}, duration={step2_duration:.2f}s, items_updated={len(modified_soups)}"
            )
        except Exception as e:
            step2_duration = time.time() - step2_start
            self.logger.error(
                LogModule.TRANS,
                f"[MOBI_TRANSLATOR] _after_translate Step 2 FAILED: task_id={task_id}, "
                f"duration={step2_duration:.2f}s, error={e}",
                exc_info=True
            )
            raise

        # Step 3: Create new EPUB file (MOBI will be converted from EPUB if needed)
        step3_start = time.time()
        try:
            self.logger.info(
                LogModule.TRANS,
                f"[MOBI_TRANSLATOR] _after_translate Step 3 STARTED: task_id={task_id}, "
                f"writing EPUB file"
            )
            
            output_buffer = BytesIO()
            epub.write_epub(output_buffer, book, {})
            epub_content = output_buffer.getvalue()
            step3_duration = time.time() - step3_start
            
            total_duration = time.time() - start_time
            self.logger.info(
                LogModule.TRANS,
                f"[MOBI_TRANSLATOR] _after_translate Step 3 (write EPUB) COMPLETED: "
                f"task_id={task_id}, duration={step3_duration:.2f}s, output_size={len(epub_content)} bytes"
            )
            self.logger.info(
                LogModule.TRANS,
                f"[MOBI_TRANSLATOR] _after_translate COMPLETED: task_id={task_id}, "
                f"total_duration={total_duration:.2f}s (Step1={step1_duration:.2f}s, "
                f"Step2={step2_duration:.2f}s, Step3={step3_duration:.2f}s)"
            )
            
            return epub_content
        except Exception as e:
            step3_duration = time.time() - step3_start
            total_duration = time.time() - start_time
            self.logger.error(
                LogModule.TRANS,
                f"[MOBI_TRANSLATOR] _after_translate Step 3 FAILED: task_id={task_id}, "
                f"duration={step3_duration:.2f}s, total_duration={total_duration:.2f}s, error={e}",
                exc_info=True
            )
            raise

    @staticmethod
    def generate_dom_from_segments_template(
        book: Any,
        html_templates: Dict[str, str],
        segment_mapping: List[Dict[str, Any]],
        translated_segments: Dict[int, str],
        task_id: Optional[str] = None,
        task_state: Optional[Dict[str, Any]] = None,
    ) -> bytes:
        """
        Generate DOM from HTML templates using string replacement (fast).
        This is called during export phase to generate the final EPUB/MOBI file.
        
        Args:
            book: EPUB book object
            html_templates: Dictionary mapping item_id to original HTML content
            segment_mapping: List of segment info: {segment_id, item_id, original_text}
            translated_segments: Dictionary mapping segment_id to translated text
            task_id: Optional task ID for logging
            
        Returns:
            EPUB file content as bytes
        """
        import time
        start_time = time.time()
        logger = None
        if task_id:
            from logger import unified_logger
            logger = unified_logger
        
        if logger:
            logger.info(
                LogModule.TRANS,
                f"[MOBI_TRANSLATOR] generate_dom_from_segments_template STARTED: task_id={task_id}, "
                f"items={len(html_templates)}, segments={len(segment_mapping)}"
            )
        
        # Step 1: Replace text in HTML templates using string replacement
        replacement_start = time.time()
        items_updated = 0
        
        for item in book.get_items():
            if item.get_type() != ebooklib.ITEM_DOCUMENT:
                continue
            
            item_id = item.get_id()
            if item_id not in html_templates:
                continue
            
            original_html = html_templates[item_id]
            modified_html = original_html
            
            # Get all segments for this item
            item_segments = [
                seg for seg in segment_mapping
                if seg['item_id'] == item_id
            ]
            
            # Sort segments by position in HTML (reverse order to avoid index shifting)
            # Use a simple heuristic: longer text first (more unique), then by segment_id (descending)
            # Process from end to start to avoid index shifting when replacing
            item_segments_sorted = sorted(
                item_segments,
                key=lambda s: (-len(s['original_text']), -s['segment_id']),  # Negative segment_id for descending
                reverse=False  # Longer text first, then higher segment_id first
            )
            
            replacements_made = 0
            for seg_info in item_segments_sorted:
                segment_id = seg_info['segment_id']
                original_text = seg_info['original_text']
                translated_text = translated_segments.get(segment_id)
                
                if translated_text and original_text in modified_html:
                    # Replace first occurrence (text should be unique in HTML)
                    modified_html = modified_html.replace(original_text, translated_text, 1)
                    replacements_made += 1

            # Sanitize for EPUB 3 (fix font/mbp:pagebreak/deprecated attrs, image path 一mages)
            from utils.epub_fix import sanitize_html_for_epub
            modified_html = sanitize_html_for_epub(modified_html)

            # Update item content
            item.set_content(modified_html.encode('utf-8'))
            items_updated += 1
            
            if logger and items_updated % 10 == 0:
                elapsed = time.time() - replacement_start
                logger.info(
                    LogModule.TRANS,
                    f"[MOBI_TRANSLATOR] generate_dom_from_segments_template: Updated {items_updated}/{len(html_templates)} items, "
                    f"elapsed={elapsed:.2f}s, task_id={task_id}"
                )
        
        replacement_duration = time.time() - replacement_start
        if logger:
            logger.info(
                LogModule.TRANS,
                f"[MOBI_TRANSLATOR] generate_dom_from_segments_template: Text replacement COMPLETED: "
                f"task_id={task_id}, duration={replacement_duration:.2f}s, items_updated={items_updated}"
            )
        
        # Step 2: Verify images are preserved in book object
        image_items_count = sum(1 for item in book.get_items() if item.get_type() == ebooklib.ITEM_IMAGE)
        if logger:
            logger.info(
                LogModule.TRANS,
                f"[MOBI_TRANSLATOR] generate_dom_from_segments_template: Book object contains {image_items_count} image items before EPUB write"
            )
        
        # Step 3: Apply full ebook_metadata from task_state so exported EPUB has correct metadata
        ebook_meta = (task_state or {}).get("ebook_metadata") or {}
        if ebook_meta:
            from utils.ebook_metadata import apply_to_ebooklib_book
            apply_to_ebooklib_book(book, ebook_meta)
        elif not (book.get_metadata("DC", "title") and book.get_metadata("DC", "title")[0] and (book.get_metadata("DC", "title")[0][0] or "").strip()):
            book.set_title("Untitled")

        # Step 4: Write EPUB file and fix for EPUBCheck/Apple Books (dc:title, nav, remove toc=ncx)
        epub_start = time.time()
        try:
            output_buffer = BytesIO()
            epub.write_epub(output_buffer, book, {})
            epub_content = output_buffer.getvalue()
            from utils.epub_fix import fix_epub_for_epubcheck
            epub_content = fix_epub_for_epubcheck(epub_content)
            epub_duration = time.time() - epub_start
            
            # Verify EPUB contains images
            import zipfile
            with zipfile.ZipFile(io.BytesIO(epub_content), 'r') as zf:
                epub_image_files = [f for f in zf.namelist() if any(f.lower().endswith(ext) for ext in ['.png', '.jpg', '.jpeg', '.gif', '.svg', '.webp'])]
                if logger:
                    logger.info(
                        LogModule.TRANS,
                        f"[MOBI_TRANSLATOR] generate_dom_from_segments_template: Generated EPUB contains {len(epub_image_files)} image files: {epub_image_files[:5] if epub_image_files else 'none'}"
                    )
            
            total_duration = time.time() - start_time
            if logger:
                logger.info(
                    LogModule.TRANS,
                    f"[MOBI_TRANSLATOR] generate_dom_from_segments_template COMPLETED: task_id={task_id}, "
                    f"total_duration={total_duration:.2f}s (replacement={replacement_duration:.2f}s, "
                    f"epub_write={epub_duration:.2f}s), output_size={len(epub_content)} bytes"
                )
            
            return epub_content
        except Exception as e:
            epub_duration = time.time() - epub_start
            total_duration = time.time() - start_time
            if logger:
                logger.error(
                    LogModule.TRANS,
                    f"[MOBI_TRANSLATOR] generate_dom_from_segments_template FAILED: task_id={task_id}, "
                    f"duration={total_duration:.2f}s (replacement={replacement_duration:.2f}s, "
                    f"epub_write={epub_duration:.2f}s), error={e}",
                    exc_info=True
                )
            raise

    def translate(self, document: Document) -> Self:
        """
        Synchronously translate MOBI document.
        """
        book, items_to_translate, original_texts = self._pre_translate(document)
        if not original_texts:
            self.logger.info(LogModule.TRANS, "\nNo plain text content found in file that needs translation.")
            return self
        if self.glossary_agent:
            self.glossary_dict_gen = self.glossary_agent.send_segments(original_texts, self.chunk_size)
            if self.translate_agent:
                self.translate_agent.update_glossary_dict(self.glossary_dict_gen)
        if self.translate_agent:
            translated_texts = self.translate_agent.send_segments(original_texts, self.chunk_size)
        else:
            translated_texts = original_texts

        task_id = getattr(self, '_task_id', None)
        task_state = None
        if task_id:
            try:
                from backend.app.services.task import task_manager
                task_state = task_manager.get_task(task_id)
            except Exception:
                task_state = None

        html_templates = (task_state or {}).get('mobi_html_templates', {})
        segment_mapping = (task_state or {}).get('mobi_segment_mapping', [])
        if html_templates and segment_mapping:
            translated_segments = {
                i: translated_texts[i] if i < len(translated_texts) else ""
                for i in range(len(segment_mapping))
            }
            document.content = self.generate_dom_from_segments_template(
                book=book,
                html_templates=html_templates,
                segment_mapping=segment_mapping,
                translated_segments=translated_segments,
                task_id=task_id,
                task_state=task_state,
            )
        elif items_to_translate:
            document.content = self._after_translate(
                book, items_to_translate, translated_texts, original_texts
            )
        return self

    async def translate_async(self, document: Document, progress_callback=None) -> Self:
        """
        Asynchronously translate MOBI document.
        
        Args:
            document: Document object to translate
            progress_callback: Optional callback function(completed: int, total: int, percent: int) for progress updates
        """
        # CRITICAL: Log whether progress_callback is received
        if progress_callback:
            self.logger.info(LogModule.TRANS, f"[MOBI_TRANSLATOR] translate_async: progress_callback received: {progress_callback}")
        else:
            self.logger.warning(LogModule.TRANS, f"[MOBI_TRANSLATOR] translate_async: progress_callback is None!")
        book, items_to_translate, original_texts = await asyncio.to_thread(
            self._pre_translate, document
        )
        if not original_texts:
            self.logger.info(LogModule.TRANS, "\nNo plain text content found in file that needs translation.")
            return self

        if self.glossary_agent:
            self.glossary_dict_gen = await self.glossary_agent.send_segments_async(original_texts, self.chunk_size)
            if self.translate_agent:
                self.translate_agent.update_glossary_dict(self.glossary_dict_gen)
        if self.translate_agent:
            # Set task_state on agent for API debug output
            task_id = getattr(self, '_task_id', None)
            if task_id:
                try:
                    from backend.app.services.task import task_manager
                    task_state = task_manager.get_task(task_id) if task_id else None
                    if task_state and self.translate_agent:
                        self.translate_agent.task_state = task_state
                        self.translate_agent.task_id = task_id
                        # Save original_texts to task_state for segment recording
                        task_state['mobi_original_texts'] = original_texts
                except Exception as e:
                    self.logger.debug(LogModule.TRANS, f"[MOBI_TRANSLATOR] Failed to set task_state on agent or save original_texts: {e}")
            
            # CRITICAL: Log before passing progress_callback to send_segments_async
            if progress_callback:
                self.logger.info(LogModule.TRANS, f"[MOBI_TRANSLATOR] Passing progress_callback to send_segments_async: {progress_callback}")
            else:
                self.logger.warning(LogModule.TRANS, f"[MOBI_TRANSLATOR] progress_callback is None when calling send_segments_async!")
            
            translated_texts = await self.translate_agent.send_segments_async(
                original_texts, self.chunk_size, progress_callback=progress_callback
            )
            
            # CRITICAL: Save original_texts and translated_texts to task_state for segment recording
            # This allows record_translation_segments to access them later
            if task_id:
                try:
                    from backend.app.services.task import task_manager
                    task_state = task_manager.get_task(task_id) if task_id else None
                    if task_state:
                        # Save texts for segment recording
                        task_state['mobi_original_texts'] = original_texts
                        task_state['mobi_translated_texts'] = translated_texts
                        self.logger.debug(
                            LogModule.TRANS,
                            f"[MOBI_TRANSLATOR] Saved {len(original_texts)} original_texts and "
                            f"{len(translated_texts)} translated_texts to task_state for segment recording"
                        )
                        
                        # Save API logs to temp directory
                        from utils.chunk_translation_helper import save_api_logs_to_temp_dir
                        save_api_logs_to_temp_dir(
                            task_state=task_state,
                            task_id=task_id,
                            subfolder="translation",
                            llm_api_input=task_state.get('llm_api_input'),
                            llm_api_output=task_state.get('llm_api_output'),
                            llm_api_system_prompt=task_state.get('llm_api_system_prompt'),
                        )
                except Exception as log_e:
                    self.logger.warning(LogModule.TRANS, f"[MOBI_TRANSLATOR] Failed to save texts or API logs: {log_e}", exc_info=True)
        else:
            translated_texts = original_texts
        
        # OPTIMIZATION: Skip _after_translate during translation phase
        # DOM generation will be deferred to export phase (when user downloads/previews)
        # This allows translation to complete immediately without slow DOM operations
        if task_id:
            try:
                from backend.app.services.task import task_manager
                task_state = task_manager.get_task(task_id) if task_id else None
                if task_state:
                    # Save book and items for later DOM generation
                    task_state['mobi_book'] = book
                    task_state['mobi_items_to_translate'] = items_to_translate
                    task_state['mobi_original_texts'] = original_texts
                    task_state['mobi_translated_texts'] = translated_texts
                    
                    self.logger.info(
                        LogModule.TRANS,
                        f"[MOBI_TRANSLATOR] translate_async: Skipping _after_translate (delayed DOM generation), "
                        f"saved book and translation data to task_state for export phase, task_id={task_id}"
                    )
            except Exception as e:
                self.logger.warning(
                    LogModule.TRANS,
                    f"[MOBI_TRANSLATOR] translate_async: Failed to save data for delayed DOM generation: {e}, "
                    f"falling back to immediate _after_translate"
                )
                # Fallback to original behavior if saving fails
                document.content = await asyncio.to_thread(
                    self._after_translate, book, items_to_translate, translated_texts, original_texts
                )
        else:
            # No task_id, use original behavior
            self.logger.info(
                LogModule.TRANS,
                f"[MOBI_TRANSLATOR] translate_async: No task_id, using immediate _after_translate"
            )
            document.content = await asyncio.to_thread(
                self._after_translate, book, items_to_translate, translated_texts, original_texts
            )
        
        return self

