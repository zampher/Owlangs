# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

import io
import base64
import mimetypes
import os
import re
from dataclasses import dataclass

import ebooklib
from ebooklib import epub
from bs4 import BeautifulSoup

from logger import unified_logger as logger
from logger.logger import LogModule
from exporter.base import ExporterConfig
from exporter.mobi.base import MobiExporter
from ir.document import Document


@dataclass
class Mobi2HTMLExporterConfig(ExporterConfig):
    cdn: bool = False  # Whether to use CDN for resources
    image_data_map: dict = None  # Optional image data map from task_state for fallback image lookup


def _chapter_inner_html_from_soup(soup: BeautifulSoup) -> str:
    """
    Return HTML for one spine item without nesting <body> inside the merged document.

    Kindle/MOBI-derived chapters are full XHTML documents; concatenating str(body) produced
    invalid nested <body> tags and confused layout (narrow column / broken flow).
    """
    body = soup.find("body")
    if body:
        return body.decode_contents()
    return str(soup)


class Mobi2HTMLExporter(MobiExporter):
    """
    Convert MOBI file binary content to a single HTML file.
    Similar to Epub2HTMLExporter, but for MOBI format.
    """

    def __init__(self, config: Mobi2HTMLExporterConfig = None):
        config = config or Mobi2HTMLExporterConfig()
        self.cdn = config.cdn
        self.image_data_map = config.image_data_map or {}  # Store image_data_map for fallback lookup

    def export(self, document: Document) -> Document:
        """
        Convert MOBI/EPUB file binary content to a single HTML file.
        
        Note: After delayed DOM generation, document.content may be EPUB format
        (ZIP-based) instead of MOBI format (binary). This method handles both formats.

        :param document: Document object containing MOBI or EPUB binary content.
        :return: Document object containing HTML content.
        """
        content_bytes = document.content
        
        if not content_bytes:
            error_msg = "Document content is empty"
            return Document(suffix='.html', content=self._generate_error_html(error_msg).encode('utf-8'))

        try:
            # CRITICAL: Check if content is EPUB format (ZIP-based) or MOBI format (binary)
            # EPUB files start with ZIP signature: PK\x03\x04 or PK\x05\x06
            # MOBI files have different binary signatures
            is_epub_format = False
            if len(content_bytes) >= 4:
                zip_signature = content_bytes[:4]
                # Check for ZIP signatures (EPUB is a ZIP file)
                if zip_signature == b'PK\x03\x04' or zip_signature == b'PK\x05\x06' or zip_signature == b'PK\x07\x08':
                    is_epub_format = True
                    logger.debug(LogModule.EXPORT, f"[MOBI2HTML] Detected EPUB format (ZIP signature: {zip_signature.hex()}), content size: {len(content_bytes)} bytes")
            
            book = None
            
            if is_epub_format:
                # Content is EPUB format (from delayed DOM generation)
                # Try ebooklib first, fallback to zipfile parsing if it fails
                try:
                    logger.info(LogModule.EXPORT, f"[MOBI2HTML] Reading EPUB content with ebooklib, size: {len(content_bytes)} bytes, image_data_map size: {len(self.image_data_map) if self.image_data_map else 0}")
                    book = epub.read_epub(io.BytesIO(content_bytes))
                    image_items_in_book = sum(1 for item in book.get_items() if item.get_type() == ebooklib.ITEM_IMAGE)
                    logger.info(LogModule.EXPORT, f"[MOBI2HTML] Successfully read EPUB with ebooklib, spine length: {len(book.spine) if book.spine else 0}, items count: {len(list(book.get_items()))}, image items: {image_items_in_book}")
                except Exception as epub_error:
                    import zipfile
                    logger.warning(LogModule.EXPORT, f"[MOBI2HTML] ebooklib failed to read EPUB: {epub_error}, trying zipfile fallback")
                    
                    # Fallback: Use zipfile to directly parse EPUB (similar to Epub2HTMLExporter)
                    try:
                        return self._export_epub_with_zipfile(content_bytes)
                    except Exception as zip_error:
                        logger.error(LogModule.EXPORT, f"[MOBI2HTML] zipfile fallback also failed: {zip_error}", exc_info=True)
                        error_msg = f"Failed to read EPUB content. ebooklib error: {str(epub_error)}, zipfile error: {str(zip_error)}"
                        return Document(suffix='.html', content=self._generate_error_html(error_msg).encode('utf-8'))
            else:
                # Content is MOBI format (original file)
                # Read MOBI file - ebooklib doesn't support MOBI directly
                # MOBI is a binary format, not ZIP-based like EPUB
                # Try using mobi library if available, otherwise fall back to error handling
                try:
                    # Try using mobi library for MOBI files
                    import mobi
                    import tempfile
                    import os
                    temp_file = None
                    try:
                        # Create temporary file for mobi library
                        with tempfile.NamedTemporaryFile(delete=False, suffix='.mobi') as tmp:
                            tmp.write(content_bytes)
                            temp_file = tmp.name
                        
                        # Extract MOBI file - mobi library extracts to a directory
                        bookpath, epubpath = mobi.extract(temp_file)
                        
                        # If extraction successful, read the extracted EPUB
                        if epubpath and os.path.exists(epubpath):
                            book = epub.read_epub(epubpath)
                        else:
                            # If no EPUB extracted, try reading MOBI directly with ebooklib (may fail)
                            book = epub.read_epub(io.BytesIO(content_bytes))
                    finally:
                        # Clean up temporary file
                        if temp_file and os.path.exists(temp_file):
                            try:
                                os.unlink(temp_file)
                            except:
                                pass
                except ImportError:
                    # mobi library not available, try ebooklib directly (will likely fail)
                    try:
                        book = epub.read_epub(io.BytesIO(content_bytes))
                    except Exception as epub_error:
                        # ebooklib doesn't support MOBI format directly
                        error_msg = f"MOBI file cannot be read directly with ebooklib. MOBI is a binary format, not ZIP-based like EPUB. Please install 'mobi' library: pip install mobi. Error: {str(epub_error)}"
                        return Document(suffix='.html', content=self._generate_error_html(error_msg).encode('utf-8'))
                except Exception as mobi_error:
                    # mobi library failed, try ebooklib as fallback
                    try:
                        book = epub.read_epub(io.BytesIO(content_bytes))
                    except Exception as epub_error:
                        error_msg = f"Failed to read MOBI file. mobi library error: {str(mobi_error)}, ebooklib error: {str(epub_error)}"
                        return Document(suffix='.html', content=self._generate_error_html(error_msg).encode('utf-8'))
            
            if not book:
                return Document(suffix='.html', content=self._generate_error_html().encode('utf-8'))

            # Extract title and metadata
            title = book.get_metadata('DC', 'title')
            # No fallback - if no title found, use None
            # Some MOBI documents don't have titles, which is acceptable
            title_text = title[0][0] if title else None

            # Get all HTML content items
            html_items = []
            spine = book.spine
            
            if spine:
                # Process items according to spine order
                # Handle different spine formats:
                # 1. Tuple format: (item_id, linear) - spine_item[0] is item_id
                # 2. 'nav' format: ['nav', item1, item2, ...] - spine_item is 'nav' or EpubHtml object
                # 3. EpubHtml object: spine_item is directly an EpubHtml object
                for spine_item in spine:
                    item = None
                    
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
                        html_items.append(item)
            else:
                # No spine, get all document items
                items = list(book.get_items())
                html_items = [
                    item for item in items
                    if item and item.get_type() == ebooklib.ITEM_DOCUMENT
                ]

            # Combine all HTML content with image processing
            combined_html_parts = []
            for item in html_items:
                if not item:
                    continue
                try:
                    content = item.get_content()
                    if not content:
                        continue
                    
                    # Decode content if it's bytes
                    if isinstance(content, bytes):
                        try:
                            content = content.decode('utf-8')
                        except UnicodeDecodeError:
                            try:
                                content = content.decode('latin-1')
                            except UnicodeDecodeError:
                                continue
                    
                    soup = BeautifulSoup(content, 'html.parser')
                    
                    # Process images: convert image references to base64 data URIs
                    self._process_images_in_soup(soup, book)
                    
                    # Process CSS images in style tags
                    self._process_css_images_in_soup(soup, book)
                    
                    # Extract body content if exists
                    combined_html_parts.append(
                        f'<section class="owlangs-mobi-chapter" role="region">{_chapter_inner_html_from_soup(soup)}</section>'
                    )
                except Exception as item_error:
                    # Log but continue processing other items
                    logger.warning(LogModule.EXPORT, f"[MOBI2HTML] Failed to process item: {item_error}, skipping")
                    continue

            # Generate final HTML
            html_content = self._generate_html(title_text, combined_html_parts)
            return Document(suffix='.html', content=html_content.encode('utf-8'))

        except Exception as e:
            return Document(suffix='.html', content=self._generate_error_html(str(e)).encode('utf-8'))

    def _generate_html(self, title: str | None, content_parts: list) -> str:
        """Generate complete HTML document from title and content parts."""
        combined_content = "\n".join(content_parts)
        
        # Generate title tag - only include if title exists
        title_tag = f"    <title>{title}</title>" if title else ""
        
        # Generate h1 tag - only include if title exists
        h1_tag = f"    <h1>{title}</h1>" if title else ""
        
        html_template = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
{title_tag}
    <style>
        /* Single-page preview: full viewport width; legacy MOBI CSS often sets narrow body/max-width */
        html {{
            box-sizing: border-box;
        }}
        *, *::before, *::after {{
            box-sizing: inherit;
        }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
            line-height: 1.6;
            margin: 0;
            padding: clamp(12px, 2.5vw, 28px);
            color: #333;
            width: 100%;
            max-width: none;
        }}
        h1 {{
            color: #2c3e50;
            border-bottom: 2px solid #3498db;
            padding-bottom: 10px;
        }}
        .epub-content {{
            margin-top: 20px;
            width: 100%;
            max-width: min(52rem, 100%);
            margin-left: auto;
            margin-right: auto;
        }}
        .owlangs-mobi-chapter {{
            width: 100%;
        }}
        .owlangs-mobi-chapter + .owlangs-mobi-chapter {{
            margin-top: 2.25rem;
            padding-top: 2rem;
            border-top: 1px solid #e8e8e8;
        }}
        img {{
            max-width: 100%;
            height: auto;
        }}
    </style>
</head>
<body>
{h1_tag}
    <div class="epub-content">
        {combined_content}
    </div>
</body>
</html>"""
        return html_template

    def _export_epub_with_zipfile(self, epub_bytes: bytes) -> Document:
        """
        Fallback method: Parse EPUB directly using zipfile (similar to Epub2HTMLExporter).
        This is used when ebooklib fails to read the EPUB.
        """
        import zipfile
        import os
        
        with zipfile.ZipFile(io.BytesIO(epub_bytes), 'r') as zip_file:
            # Debug: List all files in EPUB
            all_files = [f.filename for f in zip_file.filelist]
            image_files = [f for f in all_files if any(f.lower().endswith(ext) for ext in ['.png', '.jpg', '.jpeg', '.gif', '.svg', '.webp'])]
            logger.info(LogModule.EXPORT, f"[MOBI2HTML] EPUB contains {len(all_files)} files, {len(image_files)} image files: {image_files[:5] if image_files else 'none'}")
            logger.info(LogModule.EXPORT, f"[MOBI2HTML] image_data_map available: {len(self.image_data_map) if self.image_data_map else 0} images")
            
            # Find all HTML files
            html_files = []
            for file_info in zip_file.filelist:
                filename = file_info.filename
                if filename.lower().endswith(('.html', '.htm', '.xhtml')) and not filename.startswith('META-INF/'):
                    html_files.append(filename)
            
            html_files = sorted(html_files)
            logger.debug(LogModule.EXPORT, f"[MOBI2HTML] Found {len(html_files)} HTML files: {html_files[:3] if html_files else 'none'}")
            
            if not html_files:
                error_msg = "No HTML files found in EPUB"
                return Document(suffix='.html', content=self._generate_error_html(error_msg).encode('utf-8'))
            
            # Combine all HTML content with image processing
            combined_html_parts = []
            images_processed = 0
            for html_file in html_files:
                try:
                    html_content = zip_file.read(html_file).decode('utf-8')
                    soup = BeautifulSoup(html_content, 'html.parser')
                    
                    # Count images before processing
                    img_tags_before = len(soup.find_all('img'))
                    
                    # Process images: convert image references to base64 data URIs
                    # Pass image_data_map for fallback lookup
                    self._process_images_in_zipfile(soup, zip_file, html_file)
                    
                    # Process CSS images in style tags
                    self._process_css_images_in_zipfile(soup, zip_file, html_file)
                    
                    # Count images after processing
                    img_tags_after = len(soup.find_all('img'))
                    images_processed_in_file = sum(1 for img in soup.find_all('img') if img.get('src', '').startswith('data:'))
                    images_processed += images_processed_in_file
                    logger.debug(LogModule.EXPORT, f"[MOBI2HTML] Processed {html_file}: {img_tags_before} img tags, {images_processed_in_file} converted to data URIs")
                    
                    combined_html_parts.append(
                        f'<section class="owlangs-mobi-chapter" role="region">{_chapter_inner_html_from_soup(soup)}</section>'
                    )
                except Exception as e:
                    logger.warning(LogModule.EXPORT, f"[MOBI2HTML] Failed to process HTML file {html_file}: {e}", exc_info=True)
                    continue
            
            logger.info(LogModule.EXPORT, f"[MOBI2HTML] zipfile fallback: Processed {len(html_files)} HTML files, converted {images_processed} images to data URIs")
            
            if not combined_html_parts:
                error_msg = "No valid HTML content found in EPUB files"
                return Document(suffix='.html', content=self._generate_error_html(error_msg).encode('utf-8'))
            
            # Try to extract title from OPF file
            title_text = self._extract_title_from_epub_zipfile(zip_file)
            
            # No fallback - if no title found, use None
            # Some MOBI documents don't have titles, which is acceptable
            
            # Generate final HTML
            html_content = self._generate_html(title_text, combined_html_parts)
            return Document(suffix='.html', content=html_content.encode('utf-8'))

    def _extract_title_from_epub_zipfile(self, zip_file) -> str:
        """
        Extract title from EPUB OPF file.
        Returns the title if found, None otherwise.
        """
        try:
            # Find OPF file path from META-INF/container.xml
            container_path = 'META-INF/container.xml'
            if container_path not in zip_file.namelist():
                logger.debug(LogModule.EXPORT, f"[MOBI2HTML] No container.xml found in EPUB")
                return None
            
            # Read container.xml to find OPF file path
            container_xml = zip_file.read(container_path).decode('utf-8')
            container_soup = BeautifulSoup(container_xml, 'xml')
            
            # Find rootfile with media-type="application/oebps-package+xml"
            rootfile = container_soup.find('rootfile', {'media-type': 'application/oebps-package+xml'})
            if not rootfile:
                # Try alternative media-type
                rootfile = container_soup.find('rootfile', {'media-type': 'application/epub+zip'})
            
            if not rootfile or not rootfile.get('full-path'):
                logger.debug(LogModule.EXPORT, f"[MOBI2HTML] No rootfile found in container.xml")
                return None
            
            opf_path = rootfile.get('full-path')
            logger.debug(LogModule.EXPORT, f"[MOBI2HTML] Found OPF file: {opf_path}")
            
            # Read OPF file
            if opf_path not in zip_file.namelist():
                logger.debug(LogModule.EXPORT, f"[MOBI2HTML] OPF file {opf_path} not found in EPUB")
                return None
            
            opf_xml = zip_file.read(opf_path).decode('utf-8')
            opf_soup = BeautifulSoup(opf_xml, 'xml')
            
            # Find title in metadata
            # Try dc:title first (Dublin Core)
            title_elem = opf_soup.find('dc:title')
            if not title_elem:
                # Try title without namespace
                title_elem = opf_soup.find('title')
            
            if title_elem and title_elem.string:
                title_text = title_elem.string.strip()
                if title_text:
                    logger.info(LogModule.EXPORT, f"[MOBI2HTML] Extracted title from OPF: {title_text}")
                    return title_text
            
            logger.debug(LogModule.EXPORT, f"[MOBI2HTML] No title found in OPF metadata")
            return None
            
        except Exception as e:
            logger.warning(LogModule.EXPORT, f"[MOBI2HTML] Failed to extract title from EPUB: {e}", exc_info=True)
            return None

    def _process_images_in_soup(self, soup: BeautifulSoup, book: epub.EpubBook):
        """
        Process images in BeautifulSoup: convert image references to base64 data URIs.
        Uses ebooklib book object to find and read image items.
        """
        for img in soup.find_all('img'):
            src = img.get('src')
            if not src:
                continue
            
            # Try to find image item in book
            # Image src might be relative path or item ID
            img_item = None
            
            # Method 1: Try to get by ID (if src is an item ID)
            try:
                img_item = book.get_item_with_id(src)
            except:
                pass
            
            # Method 2: Try to find by file name/href
            if not img_item:
                for item in book.get_items():
                    if item.get_type() == ebooklib.ITEM_IMAGE:
                        item_name = item.get_name()
                        if item_name and (src in item_name or item_name.endswith(src)):
                            img_item = item
                            break
            
            # Method 3: Try to resolve relative path
            if not img_item:
                # Remove leading slash and try to match
                src_clean = src.lstrip('/')
                for item in book.get_items():
                    if item.get_type() == ebooklib.ITEM_IMAGE:
                        item_name = item.get_name()
                        if item_name and (src_clean in item_name or item_name.endswith(src_clean)):
                            img_item = item
                            break
            
            if img_item:
                try:
                    img_data = img_item.get_content()
                    if img_data:
                        # Get MIME type
                        item_name = img_item.get_name() or ''
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
                        img['src'] = data_uri
                except Exception as img_error:
                    logger.warning(LogModule.EXPORT, f"[MOBI2HTML] Failed to process image {src}: {img_error}")
                    # Fallback to image_data_map if available
                    if self.image_data_map:
                        img_found = self._try_get_image_from_map(src, img)
                        if not img_found:
                            logger.warning(LogModule.EXPORT, f"[MOBI2HTML] Image not found in book or image_data_map: {src}")
                    # Keep original src if processing fails
            else:
                # Image item not found in book, try image_data_map fallback
                if self.image_data_map:
                    img_found = self._try_get_image_from_map(src, img)
                    if not img_found:
                        logger.debug(LogModule.EXPORT, f"[MOBI2HTML] Image not found in book or image_data_map: {src}")

    def _process_css_images_in_soup(self, soup: BeautifulSoup, book: epub.EpubBook):
        """
        Process CSS url() references in style tags: convert image references to base64 data URIs.
        Uses ebooklib book object to find and read image items.
        """
        for style_tag in soup.find_all('style'):
            if style_tag.string:
                style_tag.string = self._process_css_urls_for_book(style_tag.string, book)

    def _process_css_urls_for_book(self, css_content: str, book: epub.EpubBook) -> str:
        """Process url() references in CSS using ebooklib book object."""
        def replace_url(match):
            url = match.group(1).strip('\'"')
            if url.startswith(('http://', 'https://', 'data:')):
                return match.group(0)  # Keep external links unchanged
            
            # Try to find image item in book
            img_item = None
            
            # Method 1: Try to get by ID
            try:
                img_item = book.get_item_with_id(url)
            except:
                pass
            
            # Method 2: Try to find by file name/href
            if not img_item:
                url_clean = url.lstrip('/')
                for item in book.get_items():
                    if item.get_type() == ebooklib.ITEM_IMAGE:
                        item_name = item.get_name()
                        if item_name and (url in item_name or url_clean in item_name or item_name.endswith(url) or item_name.endswith(url_clean)):
                            img_item = item
                            break
            
            if img_item:
                try:
                    img_data = img_item.get_content()
                    if img_data:
                        item_name = img_item.get_name() or ''
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
                                mime_type = 'image/png'
                        
                        img_base64 = base64.b64encode(img_data).decode('utf-8')
                        return f'url("data:{mime_type};base64,{img_base64}")'
                except Exception:
                    pass
            
            return match.group(0)  # Keep original
        
        return re.sub(r'url\(([^)]+)\)', replace_url, css_content)

    def _process_images_in_zipfile(self, soup: BeautifulSoup, zip_file, html_file_path: str):
        """
        Process images in BeautifulSoup: convert image references to base64 data URIs.
        Uses zipfile to read images from EPUB archive.
        """
        img_tags = soup.find_all('img')
        logger.info(LogModule.EXPORT, f"[MOBI2HTML] _process_images_in_zipfile: Found {len(img_tags)} img tags in {html_file_path}")
        
        for idx, img in enumerate(img_tags):
            src = img.get('src')
            if not src:
                logger.debug(LogModule.EXPORT, f"[MOBI2HTML] _process_images_in_zipfile: img tag #{idx} has no src attribute")
                continue
            
            logger.info(LogModule.EXPORT, f"[MOBI2HTML] _process_images_in_zipfile: Processing img #{idx}: src={src}")
            
            try:
                # Resolve image path relative to HTML file
                img_path = self._resolve_path_for_zipfile(html_file_path, src)
                
                # Try multiple path variants (handle encoding: "一mages" -> "images", fullwidth "。" -> ".")
                src_fixed = src.replace('\u3002', '.').replace('一', 'i')
                possible_paths = [
                    img_path,
                    src.lstrip('/'),  # Remove leading slash
                    src,  # Original path
                    src_fixed.lstrip('/'),  # Fixed path
                    src_fixed,  # Fixed path without leading slash
                    # Also try common image directory patterns
                    f"images/{src.lstrip('/')}",
                    f"Images/{src.lstrip('/')}",
                    f"images/{src_fixed.lstrip('/')}",
                    f"Images/{src_fixed.lstrip('/')}",
                    f"OEBPS/images/{src.lstrip('/')}",
                    f"OEBPS/Images/{src.lstrip('/')}",
                    f"OEBPS/images/{src_fixed.lstrip('/')}",
                    f"OEBPS/Images/{src_fixed.lstrip('/')}",
                ]
                
                img_data = None
                found_path = None
                for path_variant in possible_paths:
                    try:
                        img_data = zip_file.read(path_variant)
                        found_path = path_variant
                        logger.debug(LogModule.EXPORT, f"[MOBI2HTML] Found image in EPUB: src={src}, found_path={found_path}")
                        break
                    except KeyError:
                        continue
                
                if not img_data:
                    logger.warning(LogModule.EXPORT, f"[MOBI2HTML] Image not found in EPUB: src={src}, html_file={html_file_path}, tried {len(possible_paths)} paths")
                    logger.debug(LogModule.EXPORT, f"[MOBI2HTML] Tried paths: {possible_paths[:10]}")
                    # Fallback: Try to get image from image_data_map (from Extract phase)
                    if self.image_data_map:
                        logger.info(LogModule.EXPORT, f"[MOBI2HTML] Trying image_data_map fallback: src={src}, map_size={len(self.image_data_map)}")
                        img_found = self._try_get_image_from_map(src, img)
                        if img_found:
                            logger.info(LogModule.EXPORT, f"[MOBI2HTML] Successfully found image in image_data_map: src={src}")
                            continue
                        # Also try with fixed path
                        if src_fixed != src:
                            logger.info(LogModule.EXPORT, f"[MOBI2HTML] Trying image_data_map with fixed path: src_fixed={src_fixed}")
                            img_found = self._try_get_image_from_map(src_fixed, img)
                            if img_found:
                                logger.info(LogModule.EXPORT, f"[MOBI2HTML] Successfully found image in image_data_map with fixed path: src={src}, src_fixed={src_fixed}")
                                continue
                        logger.warning(LogModule.EXPORT, f"[MOBI2HTML] Image not found in image_data_map: src={src}, available keys: {list(self.image_data_map.keys())[:10]}")
                    else:
                        logger.warning(LogModule.EXPORT, f"[MOBI2HTML] image_data_map is empty, cannot use fallback")
                    logger.error(LogModule.EXPORT, f"[MOBI2HTML] FAILED to process image: src={src}, img tag will keep original src")
                    continue
                
                if img_data:
                    # Get MIME type
                    mime_type, _ = mimetypes.guess_type(found_path)
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
                    img['src'] = data_uri
                    logger.info(LogModule.EXPORT, f"[MOBI2HTML] Successfully converted image to data URI: src={src}, found_path={found_path}, mime={mime_type}, size={len(img_data)} bytes, data_uri_length={len(data_uri)}")
            except Exception as img_error:
                logger.warning(LogModule.EXPORT, f"[MOBI2HTML] Failed to process image {src} in zipfile: {img_error}")
                # Keep original src if processing fails

    def _process_css_images_in_zipfile(self, soup: BeautifulSoup, zip_file, html_file_path: str):
        """
        Process CSS url() references in style tags: convert image references to base64 data URIs.
        Uses zipfile to read images from EPUB archive.
        """
        for style_tag in soup.find_all('style'):
            if style_tag.string:
                style_tag.string = self._process_css_urls_for_zipfile(style_tag.string, zip_file, html_file_path)

    def _process_css_urls_for_zipfile(self, css_content: str, zip_file, base_path: str) -> str:
        """Process url() references in CSS using zipfile."""
        def replace_url(match):
            url = match.group(1).strip('\'"')
            if url.startswith(('http://', 'https://', 'data:')):
                return match.group(0)  # Keep external links unchanged
            
            try:
                resource_path = self._resolve_path_for_zipfile(base_path, url)
                
                # Try multiple path variants
                possible_paths = [
                    resource_path,
                    url.lstrip('/'),
                    url,
                ]
                
                resource_data = None
                for path_variant in possible_paths:
                    try:
                        resource_data = zip_file.read(path_variant)
                        break
                    except KeyError:
                        continue
                
                if resource_data:
                    mime_type, _ = mimetypes.guess_type(path_variant)
                    if mime_type:
                        resource_base64 = base64.b64encode(resource_data).decode('utf-8')
                        return f'url("data:{mime_type};base64,{resource_base64}")'
            except Exception:
                pass
            
            return match.group(0)  # Keep original
        
        return re.sub(r'url\(([^)]+)\)', replace_url, css_content)

    def _try_get_image_from_map(self, src: str, img_tag) -> bool:
        """
        Try to get image from image_data_map (from Extract phase).
        Returns True if image was found and set, False otherwise.
        """
        if not self.image_data_map:
            return False
        
        logger.info(LogModule.EXPORT, f"[MOBI2HTML] _try_get_image_from_map: Looking for src={src}, map has {len(self.image_data_map)} entries")
        if len(self.image_data_map) > 0:
            sample_keys = list(self.image_data_map.keys())[:5]
            logger.info(LogModule.EXPORT, f"[MOBI2HTML] _try_get_image_from_map: Sample keys in map: {sample_keys}")
        
        # Fix encoding issues in src (e.g., "一mages" -> "images", fullwidth period "。" -> ".")
        src_fixed = src.replace('\u3002', '.').replace('一', 'i')
        
        # Try multiple matching strategies
        for img_key, img_info in self.image_data_map.items():
            if not isinstance(img_info, dict) or 'data' not in img_info:
                logger.debug(LogModule.EXPORT, f"[MOBI2HTML] Skipping invalid image_info: key={img_key}, type={type(img_info)}")
                continue
            
            # Match strategies:
            # 1. Exact match (original and fixed)
            if img_key == src or img_key == src_fixed:
                img_tag['src'] = img_info['data']
                logger.info(LogModule.EXPORT, f"[MOBI2HTML] Found image in image_data_map (exact match): src={src}, key={img_key}")
                return True
            
            # 2. Filename match (handle encoding issues)
            try:
                from pathlib import Path
                img_filename = Path(img_key).name if img_key else ''
                src_filename = Path(src).name if src else ''
                src_filename_fixed = Path(src_fixed).name if src_fixed else ''
                
                # Try original filename match
                if img_filename and src_filename and img_filename == src_filename:
                    img_tag['src'] = img_info['data']
                    logger.info(LogModule.EXPORT, f"[MOBI2HTML] Found image in image_data_map (filename match): src={src}, src_filename={src_filename}, matched_key={img_key}, img_filename={img_filename}")
                    return True
                
                # Try fixed filename match
                if img_filename and src_filename_fixed and img_filename == src_filename_fixed:
                    img_tag['src'] = img_info['data']
                    logger.info(LogModule.EXPORT, f"[MOBI2HTML] Found image in image_data_map (filename match with fix): src={src}, src_filename_fixed={src_filename_fixed}, matched_key={img_key}, img_filename={img_filename}")
                    return True
            except Exception as e:
                logger.debug(LogModule.EXPORT, f"[MOBI2HTML] Filename match failed: {e}")
                pass
            
            # 3. Path contains match (handle encoding: "一mages" vs "images", fullwidth "。" vs ".")
            if src and img_key:
                # Normalize paths for comparison
                src_normalized = src.replace('\\', '/').lower().replace('\u3002', '.')
                key_normalized = img_key.replace('\\', '/').lower()
                # Fix encoding issues
                src_normalized_fixed = src_normalized.replace('一', 'i')
                key_normalized_fixed = key_normalized.replace('一', 'i')
                
                # Check if one contains the other (handles partial matches)
                # Try original paths
                if (src_normalized in key_normalized or 
                    key_normalized in src_normalized or
                    src_normalized.endswith(key_normalized) or
                    key_normalized.endswith(src_normalized)):
                    img_tag['src'] = img_info['data']
                    logger.info(LogModule.EXPORT, f"[MOBI2HTML] Found image in image_data_map (path match): src={src}, matched_key={img_key}")
                    return True
                
                # Try fixed paths
                if (src_normalized_fixed in key_normalized_fixed or 
                    key_normalized_fixed in src_normalized_fixed or
                    src_normalized_fixed.endswith(key_normalized_fixed) or
                    key_normalized_fixed.endswith(src_normalized_fixed)):
                    img_tag['src'] = img_info['data']
                    logger.info(LogModule.EXPORT, f"[MOBI2HTML] Found image in image_data_map (path match with fix): src={src}, src_fixed={src_fixed}, matched_key={img_key}")
                    return True
        
        return False

    def _resolve_path_for_zipfile(self, base_path: str, relative_path: str) -> str:
        """Resolve relative path to absolute path for zipfile."""
        if relative_path.startswith('/'):
            return relative_path.lstrip('/')
        
        base_dir = os.path.dirname(base_path)
        if base_dir:
            return os.path.join(base_dir, relative_path).replace('\\', '/')
        else:
            return relative_path

    def _generate_error_html(self, error_msg: str = None) -> str:
        """Generate error HTML page."""
        error_text = error_msg if error_msg else "Unknown error"
        return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Error</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
            line-height: 1.6;
            max-width: 800px;
            margin: 0 auto;
            padding: 20px;
            color: #333;
        }}
        h1 {{
            color: #e74c3c;
        }}
    </style>
</head>
<body>
    <h1>Error: Unable to extract MOBI content</h1>
    <p>Please check if the MOBI file format is correct.</p>
    <p>Error details: {error_text}</p>
</body>
</html>"""

