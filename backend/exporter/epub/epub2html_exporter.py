# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

import base64
import io
import os
import zipfile
from dataclasses import dataclass
from xml.etree import ElementTree
from pathlib import Path
import re
import mimetypes

from bs4 import BeautifulSoup

from exporter.base import ExporterConfig
from exporter.epub.base import EpubExporter
from ir.document import Document
from utils.epub_fix import normalize_kindle_inline_reader_layout_styles


@dataclass
class Epub2HTMLExporterConfig(ExporterConfig):
    cdn: bool = True


class Epub2HTMLExporter(EpubExporter):
    def __init__(self, config: Epub2HTMLExporterConfig = None):
        config = config or Epub2HTMLExporterConfig()
        super().__init__(config=config)

    def _extract_opf_path(self, zip_file):
        """Extract OPF file path from META-INF/container.xml"""
        try:
            container_xml = zip_file.read('META-INF/container.xml')
            container_root = ElementTree.fromstring(container_xml)

            # Find rootfile element
            rootfile = container_root.find('.//{urn:oasis:names:tc:opendocument:xmlns:container}rootfile')
            if rootfile is not None:
                return rootfile.get('full-path')
        except (KeyError, ElementTree.ParseError):
            pass

        # If unable to get from container.xml, try common paths
        for common_path in ['content.opf', 'OEBPS/content.opf', 'OPS/content.opf']:
            try:
                zip_file.getinfo(common_path)
                return common_path
            except KeyError:
                continue

        raise FileNotFoundError("Unable to find OPF file")

    def _parse_opf(self, opf_content):
        """Parse OPF file to get reading order and file information"""
        root = ElementTree.fromstring(opf_content)

        # Define namespace
        ns = {
            'opf': 'http://www.idpf.org/2007/opf',
            'dc': 'http://purl.org/dc/elements/1.1/'
        }

        # Get all items in manifest
        manifest_items = {}
        manifest = root.find('.//opf:manifest', ns)
        if manifest is not None:
            for item in manifest.findall('opf:item', ns):
                item_id = item.get('id')
                href = item.get('href')
                media_type = item.get('media-type')
                manifest_items[item_id] = {
                    'href': href,
                    'media-type': media_type
                }

        # Get reading order from spine
        reading_order = []
        spine = root.find('.//opf:spine', ns)
        if spine is not None:
            for itemref in spine.findall('opf:itemref', ns):
                idref = itemref.get('idref')
                if idref in manifest_items:
                    reading_order.append(manifest_items[idref]['href'])

        return manifest_items, reading_order

    def _process_html_content(self, html_content, zip_file, base_path, manifest_items):
        """Process HTML content, embed images and styles"""
        soup = BeautifulSoup(html_content, 'html.parser')

        # Process images
        for img in soup.find_all('img'):
            src = img.get('src')
            if src:
                # Build complete path
                img_path = self._resolve_path(base_path, src)
                try:
                    img_data = zip_file.read(img_path)
                    # Get MIME type
                    mime_type, _ = mimetypes.guess_type(img_path)
                    if mime_type:
                        # Convert to base64 data URI
                        img_base64 = base64.b64encode(img_data).decode('utf-8')
                        data_uri = f"data:{mime_type};base64,{img_base64}"
                        img['src'] = data_uri
                except KeyError:
                    # If image doesn't exist, keep original path
                    pass

        # Process inline styles (<style> tags)
        for style_tag in soup.find_all('style'):
            if style_tag.string:
                # Process url() references in CSS
                style_tag.string = self._process_css_urls(
                    style_tag.string, zip_file, base_path
                )

        # Process external stylesheets
        for link in soup.find_all('link', {'rel': 'stylesheet'}):
            href = link.get('href')
            if href:
                css_path = self._resolve_path(base_path, href)
                try:
                    css_content = zip_file.read(css_path).decode('utf-8')
                    # Process URL references in CSS
                    css_content = self._process_css_urls(css_content, zip_file, base_path)

                    # Replace link tag with style tag
                    style_tag = soup.new_tag('style')
                    style_tag.string = css_content
                    link.replace_with(style_tag)
                except (KeyError, UnicodeDecodeError):
                    # If stylesheet doesn't exist or can't be decoded, remove link tag
                    link.decompose()

        return str(soup)

    def _process_css_urls(self, css_content, zip_file, base_path):
        """Process url() references in CSS"""

        def replace_url(match):
            url = match.group(1).strip('\'"')
            if url.startswith(('http://', 'https://', 'data:')):
                return match.group(0)  # Keep external links unchanged

            try:
                resource_path = self._resolve_path(base_path, url)
                resource_data = zip_file.read(resource_path)
                mime_type, _ = mimetypes.guess_type(resource_path)
                if mime_type:
                    resource_base64 = base64.b64encode(resource_data).decode('utf-8')
                    return f'url("data:{mime_type};base64,{resource_base64}")'
            except KeyError:
                pass

            return match.group(0)  # Keep original

        # Match url() function
        return re.sub(r'url\(([^)]+)\)', replace_url, css_content)

    def _resolve_path(self, base_path, relative_path):
        """Resolve relative path to absolute path"""
        if relative_path.startswith('/'):
            return relative_path.lstrip('/')

        base_dir = os.path.dirname(base_path)
        if base_dir:
            return os.path.join(base_dir, relative_path).replace('\\', '/')
        else:
            return relative_path

    def _find_html_files(self, zip_file):
        """Find all HTML files in EPUB"""
        html_files = []
        for file_info in zip_file.filelist:
            filename = file_info.filename
            if filename.lower().endswith(('.html', '.htm', '.xhtml')) and not filename.startswith('META-INF/'):
                html_files.append(filename)
        return sorted(html_files)

    # def _debug_epub_structure(self, zip_file):
        """Debug EPUB structure, print all files"""
        print("=== EPUB File Structure ===")
        for file_info in zip_file.filelist:
            print(f"File: {file_info.filename}")
        print("==================")

    def export(self, document: Document) -> Document:
        """
        Convert EPUB file binary content to a single HTML file.

        :param document: Document object containing EPUB binary content.
        :return: Document object containing single HTML file content.
        """
        epub_bytes = document.content

        with zipfile.ZipFile(io.BytesIO(epub_bytes), 'r') as zip_file:
            # Debug: print EPUB structure
            # self._debug_epub_structure(zip_file)

            try:
                # 1. Extract OPF file path
                opf_path = self._extract_opf_path(zip_file)
                opf_content = zip_file.read(opf_path)

                # 2. Parse OPF file
                manifest_items, reading_order = self._parse_opf(opf_content)

                # print(f"OPF path: {opf_path}")
                # print(f"Reading order: {reading_order}")
                # print(f"Manifest items: {list(manifest_items.keys())}")

                # 3. Read and process HTML files in reading order
                combined_html_parts = []
                base_path = os.path.dirname(opf_path)

                # Try to process files in reading order
                processed_files = set()
                for html_file in reading_order:
                    html_path = self._resolve_path(base_path, html_file)

                    # Try multiple path variants
                    possible_paths = [
                        html_path,
                        html_file,  # Original path
                        html_file.replace('.html', ''),  # Remove .html suffix
                        html_file.replace('.htm.html', '.htm'),  # Handle double suffix
                    ]

                    file_found = False
                    for path_variant in possible_paths:
                        try:
                            html_content = zip_file.read(path_variant).decode('utf-8')
                            processed_html = self._process_html_content(
                                html_content, zip_file, path_variant, manifest_items
                            )

                            # Extract body content (if exists)
                            soup = BeautifulSoup(processed_html, 'html.parser')
                            normalize_kindle_inline_reader_layout_styles(soup)
                            body = soup.find('body')
                            if body:
                                combined_html_parts.append(str(body))
                            else:
                                combined_html_parts.append(processed_html)

                            processed_files.add(path_variant)
                            file_found = True
                            # print(f"Successfully processed file: {path_variant}")
                            break

                        except (KeyError, UnicodeDecodeError):
                            continue

                    # if not file_found:
                    #     print(f"Warning: Unable to find file {html_file}, attempted paths: {possible_paths}")

            except Exception as e:
                # print(f"Failed to parse OPF, using fallback method: {e}")
                combined_html_parts = []
                processed_files = set()

            # 4. If no files were successfully processed, try to process all HTML files directly
            if not combined_html_parts:
                # print("Using fallback method: process all discovered HTML files")
                html_files = self._find_html_files(zip_file)

                for html_file in html_files:
                    if html_file in processed_files:
                        continue  # Skip already processed files

                    try:
                        html_content = zip_file.read(html_file).decode('utf-8')
                        processed_html = self._process_html_content(
                            html_content, zip_file, html_file, {}
                        )

                        # Extract body content (if exists)
                        soup = BeautifulSoup(processed_html, 'html.parser')
                        normalize_kindle_inline_reader_layout_styles(soup)
                        body = soup.find('body')
                        if body:
                            combined_html_parts.append(str(body))
                        else:
                            combined_html_parts.append(processed_html)

                        # print(f"Fallback method successfully processed: {html_file}")

                    except (KeyError, UnicodeDecodeError) as e:
                        # print(f"Fallback method failed to process {html_file}: {e}")
                        continue

            # 5. Combine into complete HTML document
            if combined_html_parts:
                # Create basic HTML structure
                html_content = f"""<!DOCTYPE html>
<html lang="zh">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{document.stem}</title>
    <style>
        body {{
            max-width: 800px;
            margin: 0 auto;
            padding: 20px;
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            line-height: 1.6;
            color: #333;
        }}
        img {{
            max-width: 100%;
            height: auto;
        }}
        .chapter {{
            margin-bottom: 2em;
            page-break-after: always;
        }}
        .chapter nav {{
            display: block !important;
            clear: both !important;
            position: static !important;
            margin: 1rem 0 !important;
            overflow: visible !important;
        }}
        .chapter nav a {{
            line-height: 1.45 !important;
        }}
        pre {{
            white-space: pre-wrap;
            word-wrap: break-word;
        }}
    </style>
</head>
<body>
    <div class="epub-content">
{''.join(f'<div class="chapter">{part}</div>' for part in combined_html_parts)}
    </div>
</body>
</html>"""
                # print(f"Successfully combined {len(combined_html_parts)} parts of content")
            else:
                html_content = f"""<!DOCTYPE html>
<html lang="zh">
<head>
    <meta charset="UTF-8">
    <title>{document.stem}</title>
</head>
<body>
    <h1>Error: Unable to extract EPUB content</h1>
    <p>No valid HTML content files found.</p>
    <p>Please check if the EPUB file format is correct.</p>
</body>
</html>"""
                # print("Warning: No valid HTML content found")

        return Document.from_bytes(content=html_content.encode("utf-8"), suffix=".html", stem=document.stem)