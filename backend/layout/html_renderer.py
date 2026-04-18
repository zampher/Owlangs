# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

"""
HTML renderer for layout-based document rendering.

Generates absolutely positioned HTML from LayoutDocument and translated text,
enabling high-fidelity PDF generation.
"""

import base64
import zipfile
import io
from typing import Dict, Optional

from layout.base import LayoutDocument, LayoutBlock
from logger import unified_logger as logger
from logger.logger import LogModule


def render_layout_html(
    layout_doc: LayoutDocument,
    translated_text_by_block_index: Optional[Dict[int, str]] = None,
    zip_bytes: Optional[bytes] = None,
) -> str:
    """
    Render LayoutDocument as absolutely positioned HTML.
    
    Args:
        layout_doc: LayoutDocument instance
        translated_text_by_block_index: Optional mapping from block index to translated text
        zip_bytes: Optional ZIP bytes for extracting images (if available)
        
    Returns:
        HTML string with absolutely positioned blocks
    """
    if translated_text_by_block_index is None:
        translated_text_by_block_index = {}
    
    # Extract images from ZIP if available
    image_data_map: Dict[str, str] = {}
    if zip_bytes:
        try:
            zip_file = zipfile.ZipFile(io.BytesIO(zip_bytes))
            for block in layout_doc.iter_image_blocks():
                if block.image_path:
                    try:
                        # Try to read image from ZIP
                        image_data = zip_file.read(block.image_path)
                        # Convert to base64
                        import mimetypes
                        mime_type, _ = mimetypes.guess_type(block.image_path)
                        if not mime_type:
                            mime_type = "image/jpeg"  # Default
                        base64_data = base64.b64encode(image_data).decode('utf-8')
                        image_data_map[block.image_path] = f"data:{mime_type};base64,{base64_data}"
                    except Exception as e:
                        logger.debug(LogModule.LAYOUT, f"Failed to extract image {block.image_path} from ZIP: {e}")
        except Exception as e:
            logger.warning(LogModule.LAYOUT, f"Failed to extract images from ZIP: {e}")
    
    # Determine page dimensions: prefer page.width/page.height from layout, fallback to max bbox
    # Layout coordinates are in points (1 point = 1/72 inch), which we use directly as px for HTML
    # (In practice, browsers treat 1pt ≈ 1px at 96 DPI, so this is acceptable)
    page_widths = []
    page_heights = []
    for page in layout_doc.pages:
        if page.width and page.height:
            # Use explicit page dimensions from layout (e.g., from page_size in layout.json)
            page_widths.append(float(page.width))
            page_heights.append(float(page.height))
        else:
            # Calculate from blocks if page dimensions not specified
            max_x = 0
            max_y = 0
            for block in page.blocks:
                x0, y0, x1, y1 = block.bbox
                max_x = max(max_x, x1)
                max_y = max(max_y, y1)
            if max_x > 0 and max_y > 0:
                page_widths.append(max_x)
                page_heights.append(max_y)
    
    # Use maximum dimensions across all pages for consistent styling
    # Fallback to A4 if no dimensions found
    if page_widths:
        max_width = max(page_widths)
    else:
        max_width = 595  # A4 width in points
    
    if page_heights:
        max_height = max(page_heights)
    else:
        max_height = 842  # A4 height in points
    
    html_parts = []
    
    # HTML header
    html_parts.append("""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <title></title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
            background: white;
            padding: 0;
            margin: 0;
        }
        .page {
            position: relative;
            width: """ + str(max_width) + """px;
            height: """ + str(max_height) + """px;
            background: white;
            margin: 0;
            box-shadow: none;
            page-break-after: always;
            /* Debug: draw page border so layout extents are clearly visible */
            border: 1px solid rgba(0, 0, 0, 0.2);
        }
        .block {
            position: absolute;
            border: none;
            outline: none;
        }
        .block.text {
            font-size: 12px;
            line-height: 1.4;
            color: #000;
            white-space: pre-wrap;
            word-wrap: break-word;
            border: none;
            outline: none;
        }
        .block.image {
            border: none;
            outline: none;
            overflow: hidden;
        }
        .block.image img {
            /* Use natural image dimensions, constrained by max-width/max-height to fit within bbox */
            display: block;
            border: none;
            outline: none;
            width: auto;
            height: auto;
            object-fit: contain;
        }
        @media print {
            * {
                box-shadow: none !important;
                text-shadow: none !important;
                border: none !important;
                outline: none !important;
            }
            body {
                background: white !important;
                padding: 0 !important;
                margin: 0 !important;
            }
            .page {
                margin: 0 !important;
                box-shadow: none !important;
                background: white !important;
                border: none !important;
                outline: none !important;
            }
            .block {
                box-shadow: none !important;
                border: none !important;
                outline: none !important;
            }
            .block.text {
                border: none !important;
                outline: none !important;
            }
            .block.image {
                border: none !important;
                outline: none !important;
            }
            .block.image img {
                border: none !important;
                outline: none !important;
                /* Preserve natural image dimensions, constrained by max-width/max-height in print */
                width: auto !important;
                height: auto !important;
                object-fit: contain !important;
            }
        }
        @page {
            margin: 0 !important;
            size: auto;
        }
    </style>
</head>
<body>
""")
    
    # Render each page
    # Note: We don't deduplicate blocks anymore to preserve all content including headers/footers
    # The previous deduplication was too aggressive and removed legitimate repeated content
    total_blocks = 0
    rendered_blocks = 0
    
    for page in layout_doc.pages:
        # Use page-specific dimensions if available, otherwise use max dimensions
        page_width = float(page.width) if page.width else max_width
        page_height = float(page.height) if page.height else max_height
        html_parts.append(f'    <div class="page" data-page-index="{page.page_index}" style="width:{page_width}px;height:{page_height}px;">\n')
        
        # Render blocks in this page
        for block in page.blocks:
            total_blocks += 1
            x0, y0, x1, y1 = block.bbox
            width = x1 - x0
            height = y1 - y0
            
            # Skip blocks with invalid dimensions
            if width <= 0 or height <= 0:
                continue
            
            style = f"left:{x0}px;top:{y0}px;width:{width}px;height:{height}px;"
            
            # Render all block types that exist in the layout
            # Only skip blocks with invalid dimensions (already checked above)
            if block.type == "image" and block.image_path:
                # Render image block: align to block start, constrain within bbox, preserve aspect ratio
                image_src = image_data_map.get(block.image_path, "")
                if image_src:
                    rendered_blocks += 1
                    # Container sets position and size constraints (bbox)
                    # Image uses natural size but constrained by max-width/max-height to fit within bbox
                    container_style = f"left:{x0}px;top:{y0}px;width:{width}px;height:{height}px;overflow:hidden;"
                    html_parts.append(
                        f'        <div class="block image" style="{container_style}">\n'
                        f'            <img src="{image_src}" alt="Image" style="display:block;max-width:{width}px;max-height:{height}px;width:auto;height:auto;object-fit:contain;" />\n'
                        f'        </div>\n'
                    )
            else:
                # Render all other block types (text, title, header, footer, page_number, figure, table, formula, equation, etc.)
                # This ensures we don't miss any content that was previously excluded
                if block.text or block.type in ("text", "title", "header", "footer", "page_number", "figure", "table", "formula", "equation"):
                    rendered_blocks += 1
                    # Use translated text if available, otherwise use original text
                    # For headers/footers/page_numbers, always use original text if no translation available
                    if block.index is not None and block.index in translated_text_by_block_index:
                        text = translated_text_by_block_index[block.index]
                    else:
                        # Always use original text for headers/footers/page_numbers if no translation
                        text = block.text or ""
                    
                    # Don't render empty blocks
                    if not text.strip():
                        continue
                    
                    # Escape HTML
                    text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")
                    
                    # Include block type in class for styling
                    block_type_class = f" {block.type}" if block.type in ("header", "footer", "page_number", "title", "figure", "table", "formula", "equation") else ""
                    block_index_attr = f' data-block-index="{block.index}"' if block.index is not None else ""
                    html_parts.append(
                        f'        <div class="block text{block_type_class}" style="{style}"{block_index_attr}>\n'
                        f'            {text}\n'
                        f'        </div>\n'
                    )
        
        html_parts.append("    </div>\n")
    
    # HTML footer
    html_parts.append("""</body>
</html>
""")
    
    logger.info(
        "[LAYOUT] render_layout_html: total_blocks=%s, rendered=%s",
        total_blocks,
        rendered_blocks,
    )
    
    return "".join(html_parts)
