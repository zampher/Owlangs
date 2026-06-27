# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

"""
MinerU layout parser.

Parses MinerU's layout formats into the generic LayoutDocument IR:
1. layout.json: New format with nested structure (pdf_info -> para_blocks -> lines -> spans)
2. *_content_list.json: Legacy format with flat list structure
"""

import json
import zipfile
import io
from pathlib import Path
from typing import Optional, Dict, Any, List

from layout.base import LayoutBlock, LayoutPage, LayoutDocument
from logger import unified_logger as logger
from logger.logger import LogModule


def _extract_text_from_layout_block(block_data: Dict[str, Any]) -> Optional[str]:
    """
    Extract text content from a layout.json block structure.
    
    Args:
        block_data: Block data from layout.json (may have 'lines' -> 'spans' -> 'content')
        
    Returns:
        Extracted text string, or None if no text found
    """
    # Try direct 'text' field first
    text = block_data.get("text")
    if text:
        if isinstance(text, list):
            return " ".join(str(t) for t in text)
        return str(text)
    
    # Extract from lines -> spans -> content
    lines = block_data.get("lines", []) or []
    text_parts: List[str] = []
    for line in lines:
        if not isinstance(line, dict):
            continue
        spans = line.get("spans", [])
        for span in spans:
            if not isinstance(span, dict):
                continue
            # Check for 'content' field (text spans)
            content = span.get("content")
            if content:
                text_parts.append(str(content))
            # Table spans store full HTML for title-block style raster tables
            elif span.get("type") == "table":
                html = span.get("html")
                if html:
                    return str(html)
            # Also check for 'text' field as fallback
            elif span.get("type") == "text":
                text = span.get("text")
                if text:
                    text_parts.append(str(text))

    nested_blocks = block_data.get("blocks") or []
    if isinstance(nested_blocks, list):
        for sub in nested_blocks:
            if isinstance(sub, dict):
                sub_text = _extract_text_from_layout_block(sub)
                if sub_text:
                    if sub_text.lstrip().lower().startswith("<table"):
                        return sub_text
                    text_parts.append(sub_text)

    if text_parts:
        return " ".join(text_parts)
    return None


def _extract_image_path_from_layout_block(block_data: Dict[str, Any]) -> Optional[str]:
    """
    Extract image path from a layout.json block structure.
    
    Args:
        block_data: Block data from layout.json (may have 'blocks' -> 'lines' -> 'spans' -> 'image_path')
        
    Returns:
        Image path string, or None if no image found
    """
    # For image blocks, check nested 'blocks' structure
    blocks = block_data.get("blocks", [])
    if blocks:
        for sub_block in blocks:
            if not isinstance(sub_block, dict):
                continue
            lines = sub_block.get("lines", [])
            for line in lines:
                if not isinstance(line, dict):
                    continue
                spans = line.get("spans", [])
                for span in spans:
                    if not isinstance(span, dict):
                        continue
                    if span.get("type") == "image":
                        img_path = span.get("image_path")
                        if img_path:
                            return str(img_path)
    
    # For interline_equation blocks, check lines -> spans -> image_path
    lines = block_data.get("lines", [])
    if lines:
        for line in lines:
            if not isinstance(line, dict):
                continue
            spans = line.get("spans", [])
            for span in spans:
                if not isinstance(span, dict):
                    continue
                # Check for interline_equation spans with image_path
                if span.get("type") == "interline_equation":
                    img_path = span.get("image_path")
                    if img_path:
                        return str(img_path)
    
    # For chart blocks, check nested 'blocks' -> 'chart_body' -> lines -> spans -> image_path
    block_type = block_data.get("type", "")
    if block_type == "chart":
        for sub_block in blocks:
            if not isinstance(sub_block, dict):
                continue
            if sub_block.get("type") == CHART_BODY:
                lines = sub_block.get("lines", [])
                for line in lines:
                    if not isinstance(line, dict):
                        continue
                    spans = line.get("spans", [])
                    for span in spans:
                        if not isinstance(span, dict):
                            continue
                        # Check for chart spans with image_path
                        if span.get("type") == "chart":
                            img_path = span.get("image_path")
                            if img_path:
                                return str(img_path)
    
    # Also check direct 'image_path' field
    img_path = block_data.get("image_path")
    if img_path:
        return str(img_path)
    
    return None


def extract_mineru_image_span_content(block_data: Dict[str, Any]) -> Optional[str]:
    """OCR / alt text stored on MinerU image spans (e.g. text_image content=DAYONE)."""
    blocks = block_data.get("blocks") or []
    for sub_block in blocks:
        if not isinstance(sub_block, dict):
            continue
        for line in sub_block.get("lines") or []:
            if not isinstance(line, dict):
                continue
            for span in line.get("spans") or []:
                if not isinstance(span, dict):
                    continue
                if span.get("type") != "image":
                    continue
                content = span.get("content")
                if isinstance(content, str) and content.strip():
                    return content.strip()
    return None


from layout.block_types import LIST_CONTAINER_TYPES as _LIST_CONTAINER_TYPES, CHART_BODY

# MinerU block type → (sub_type, tags, should_translate)
_MINERU_BLOCK_SEMANTICS: Dict[str, tuple] = {
    "text": ("body", [], True),
    "title": ("title", ["heading", "title"], True),
    "sub_title": ("heading", ["heading"], True),
    "header": ("header", ["skip_translation"], False),
    "footer": ("footer", ["skip_translation"], False),
    "image": ("image_body", ["image", "skip_translation"], False),
    "interline_equation": ("display_formula", ["formula", "skip_translation"], False),
    "table": ("table_body", ["table", "skip_translation"], False),
    "chart": ("chart_body", ["chart", "skip_translation"], False),
    "code": ("code_block", ["skip_translation"], False),
    "page_number": ("page_number", ["skip_translation"], False),
    "page_footnote": ("footnote", [], True),
    "list": ("list", [], True),
    "ref_list": ("reference", [], True),
    "references": ("reference", [], True),
    "ref_text": ("reference", [], True),
}


def _get_mineru_block_semantics(block_type: str):
    """Return (sub_type, tags, should_translate) for a MinerU block type."""
    entry = _MINERU_BLOCK_SEMANTICS.get(block_type)
    if entry is not None:
        return entry
    # Unknown types default to translatable text
    return ("", [], True)


def _parse_mineru_bbox(block_data: Dict[str, Any]) -> Optional[tuple[float, float, float, float]]:
    bbox = block_data.get("bbox")
    if not isinstance(bbox, list) or len(bbox) != 4:
        return None
    try:
        return (
            float(bbox[0]),
            float(bbox[1]),
            float(bbox[2]),
            float(bbox[3]),
        )
    except (TypeError, ValueError):
        return None


def _append_mineru_block_to_pages(
    pages_dict: Dict[int, List[LayoutBlock]],
    page_idx: int,
    block_data: Dict[str, Any],
    global_index: int,
) -> int:
    """
    Append one MinerU para/discarded block to pages_dict.

    List containers are expanded into a parent shell block plus one LayoutBlock
    per nested child so extract/segmentation can keep one child block = one segment.
    """
    bbox_tuple = _parse_mineru_bbox(block_data)
    if bbox_tuple is None:
        return global_index

    x0, y0, x1, y1 = bbox_tuple
    block_type = str(block_data.get("type", "unknown"))
    nested_blocks = block_data.get("blocks") or []

    if block_type in _LIST_CONTAINER_TYPES and isinstance(nested_blocks, list) and nested_blocks:
        parent_raw = {k: v for k, v in block_data.items() if k != "blocks"}
        parent_text = _extract_text_from_layout_block(parent_raw)
        p_sub_type, p_tags, p_should_translate = _get_mineru_block_semantics(block_type)
        parent_block = LayoutBlock(
            page_index=page_idx,
            bbox=(x0, y0, x1, y1),
            type=block_type,
            sub_type=p_sub_type,
            index=global_index,
            text=parent_text,
            image_path=None,
            raw=parent_raw,
            tags=list(p_tags),
            should_translate=p_should_translate,
        )
        pages_dict.setdefault(page_idx, []).append(parent_block)
        global_index += 1

        for sub in nested_blocks:
            if not isinstance(sub, dict):
                continue
            sub_bbox_tuple = _parse_mineru_bbox(sub)
            if sub_bbox_tuple is None:
                continue
            sx0, sy0, sx1, sy1 = sub_bbox_tuple
            sub_type = str(sub.get("type", "unknown"))
            sub_text = _extract_text_from_layout_block(sub)
            s_sub_type, s_tags, s_should_translate = _get_mineru_block_semantics(sub_type)
            sub_block = LayoutBlock(
                page_index=page_idx,
                bbox=(sx0, sy0, sx1, sy1),
                type=sub_type,
                sub_type=s_sub_type,
                index=global_index,
                text=sub_text,
                image_path=None,
                raw=sub.copy(),
                tags=list(s_tags),
                should_translate=s_should_translate,
            )
            pages_dict.setdefault(page_idx, []).append(sub_block)
            global_index += 1
        return global_index

    text = _extract_text_from_layout_block(block_data)
    img_path = _extract_image_path_from_layout_block(block_data)
    if block_type == "image" and not img_path:
        img_path = _extract_image_path_from_layout_block(block_data)
    if block_type == "image" and not text:
        span_content = extract_mineru_image_span_content(block_data)
        if span_content:
            text = span_content

    b_sub_type, b_tags, b_should_translate = _get_mineru_block_semantics(block_type)
    block = LayoutBlock(
        page_index=page_idx,
        bbox=(x0, y0, x1, y1),
        type=block_type,
        sub_type=b_sub_type,
        index=global_index,
        text=text,
        image_path=img_path,
        raw=block_data.copy(),
        tags=list(b_tags),
        should_translate=b_should_translate,
    )
    pages_dict.setdefault(page_idx, []).append(block)
    return global_index + 1


def _apply_cross_page_block_pairs(doc: LayoutDocument) -> None:
    """Pair cross-page spans with their continuation blocks on the next page."""
    cross_page_sources: Dict[int, Dict] = {}
    for page in doc.pages:
        for block in page.blocks:
            raw = getattr(block, "raw", None) or {}
            if not isinstance(raw, dict):
                continue
            for line in raw.get("lines", []):
                if not isinstance(line, dict):
                    continue
                for span in line.get("spans", []):
                    if isinstance(span, dict) and span.get("cross_page"):
                        cp_bbox = tuple(line.get("bbox") or span.get("bbox") or [])
                        cp_text = (span.get("content") or "").strip()
                        if len(cp_bbox) == 4 and cp_text and block.index is not None:
                            cross_page_sources[block.index] = {
                                "target_page": page.page_index + 1,
                                "cross_bbox": cp_bbox,
                                "cross_text": cp_text,
                            }

    for page in doc.pages:
        for block in page.blocks:
            if block.index is None:
                continue
            for src_idx, src_info in list(cross_page_sources.items()):
                if page.page_index != src_info["target_page"]:
                    continue
                block_text_for_match = (block.text or "").strip()
                if not block_text_for_match and isinstance(block.raw, dict):
                    block_text_for_match = (
                        _extract_text_from_layout_block(block.raw) or ""
                    ).strip()
                lines_deleted = isinstance(block.raw, dict) and bool(
                    block.raw.get("lines_deleted") or block.raw.get("merge_prev")
                )
                if (
                    block.bbox == src_info["cross_bbox"]
                    and (block_text_for_match == src_info["cross_text"] or lines_deleted)
                ):
                    block.text = None
                    block.raw = dict(block.raw) if block.raw else {}
                    block.raw["_cross_page_pair_of"] = src_idx

                    for src_page in doc.pages:
                        for src_block in src_page.blocks:
                            if src_block.index == src_idx:
                                src_block.raw = dict(src_block.raw) if src_block.raw else {}
                                pairs = src_block.raw.get("_cross_page_pairs", [])
                                pairs.append(
                                    {
                                        "index": block.index,
                                        "bbox": block.bbox,
                                        "page_index": page.page_index,
                                    }
                                )
                                src_block.raw["_cross_page_pairs"] = pairs
                                break
                    del cross_page_sources[src_idx]
                    break


def _finalize_mineru_layout_document(
    pages_dict: Dict[int, List[LayoutBlock]],
    pdf_info: List[Any],
    metadata: Optional[Dict[str, Any]] = None,
    engine: str = "mineru",
) -> LayoutDocument:
    pages: List[LayoutPage] = []
    for page_idx in sorted(pages_dict.keys()):
        page_data = pdf_info[page_idx] if page_idx < len(pdf_info) else {}
        page_size = page_data.get("page_size", [])
        width = float(page_size[0]) if len(page_size) >= 1 else None
        height = float(page_size[1]) if len(page_size) >= 2 else None
        pages.append(
            LayoutPage(
                page_index=page_idx,
                blocks=pages_dict[page_idx],
                width=width,
                height=height,
            )
        )

    doc = LayoutDocument(pages=pages, engine=engine, metadata=metadata or {})
    _infer_title_heading_levels(doc)
    _apply_cross_page_block_pairs(doc)
    return doc


def _get_max_span_font_size(block_data: Dict[str, Any]) -> float:
    """
    Extract the maximum font size from MinerU span data in a block.

    MinerU layout.json spans include a ``size`` field (font size in points).
    Returns 0.0 if no size data is found.
    """
    max_size = 0.0
    lines = block_data.get("lines", [])
    if not isinstance(lines, list):
        return max_size
    for line in lines:
        if not isinstance(line, dict):
            continue
        spans = line.get("spans", [])
        if not isinstance(spans, list):
            continue
        for span in spans:
            if not isinstance(span, dict):
                continue
            size = span.get("size")
            if size is not None:
                try:
                    max_size = max(max_size, float(size))
                except (TypeError, ValueError):
                    continue
    return max_size


def _infer_heading_level_from_font_size(font_size: float) -> int:
    """
    Map a font size (in points) to a heading level (1-6).

    Thresholds are based on common document patterns where body text is
    typically 9-11pt and headings scale upward:
        >= 20pt  -> H1 (chapter / document title)
        >= 15pt  -> H2 (major section)
        >= 12pt  -> H3 (subsection)
        >= 10.5pt -> H4 (sub-subsection)
        >= 9pt   -> H5 (minor heading)
        else     -> H6
    """
    if font_size >= 20.0:
        return 1
    elif font_size >= 15.0:
        return 2
    elif font_size >= 12.0:
        return 3
    elif font_size >= 10.5:
        return 4
    elif font_size >= 9.0:
        return 5
    else:
        return 6


def _infer_title_heading_levels(doc: LayoutDocument) -> None:
    """
    Post-process a LayoutDocument to infer heading levels for title blocks.

    Uses font size from MinerU span data (stored in ``block.raw``) to determine
    the hierarchy level. When span ``size`` is missing, estimates from bbox height.
    Non-title blocks are left unchanged.
    """
    from layout.pdf_renderer.typst_overlay.font_fit import (
        estimate_title_font_size_pt,
        should_use_title_font_sizing,
    )

    for page in doc.pages:
        for block in page.blocks:
            if block.type != "title" or not isinstance(block.raw, dict):
                continue
            bbox = block.raw.get("bbox") or block.bbox
            bbox_height = 0.0
            if isinstance(bbox, (list, tuple)) and len(bbox) == 4:
                try:
                    bbox_height = max(0.0, float(bbox[3]) - float(bbox[1]))
                except (TypeError, ValueError):
                    bbox_height = 0.0
            if not should_use_title_font_sizing(block.text or "", block.raw, bbox_height):
                block.heading_level = 0
                continue
            font_size = _get_max_span_font_size(block.raw)
            if font_size <= 0:
                if bbox_height > 0:
                    font_size = estimate_title_font_size_pt(bbox_height, block.raw)
                    block.raw["inferred_font_size"] = font_size
                else:
                    bbox_height = 0.0
            if font_size > 0:
                block.heading_level = _infer_heading_level_from_font_size(font_size)


def parse_layout_json(layout_path: Path, engine: str = "mineru") -> LayoutDocument:
    """
    Parse MinerU layout.json file into LayoutDocument.

    Args:
        layout_path: Path to layout.json file
        
    Returns:
        LayoutDocument with parsed layout information
    """
    with open(layout_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    if not isinstance(data, dict):
        raise ValueError(f"Expected layout.json to be a dict, got {type(data)}")
    
    pdf_info = data.get("pdf_info", [])
    if not isinstance(pdf_info, list):
        raise ValueError(f"Expected pdf_info to be a list, got {type(pdf_info)}")
    
    # Group blocks by page_idx
    pages_dict: Dict[int, List[LayoutBlock]] = {}
    global_index = 0
    
    for page_data in pdf_info:
        if not isinstance(page_data, dict):
            continue
        
        page_idx = int(page_data.get("page_idx", 0))
        page_size = page_data.get("page_size")
        
        # Process para_blocks (main content)
        para_blocks = page_data.get("para_blocks", [])
        for block_data in para_blocks:
            if not isinstance(block_data, dict):
                continue
            global_index = _append_mineru_block_to_pages(
                pages_dict,
                page_idx,
                block_data,
                global_index,
            )

        # Process discarded_blocks (headers, footers, page numbers, etc.)
        discarded_blocks = page_data.get("discarded_blocks", [])
        for block_data in discarded_blocks:
            if not isinstance(block_data, dict):
                continue
            global_index = _append_mineru_block_to_pages(
                pages_dict,
                page_idx,
                block_data,
                global_index,
            )

    metadata = {
        "_backend": data.get("_backend"),
        "_version_name": data.get("_version_name"),
    }
    return _finalize_mineru_layout_document(pages_dict, pdf_info, metadata)


def parse_content_list_json(content_list_path: Path) -> LayoutDocument:
    """
    Parse MinerU content_list.json file into LayoutDocument.
    
    Args:
        content_list_path: Path to *_content_list.json file
        
    Returns:
        LayoutDocument with parsed layout information
    """
    with open(content_list_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    if not isinstance(data, list):
        raise ValueError(f"Expected content_list.json to be a list, got {type(data)}")
    
    # Group blocks by page_idx
    pages_dict: Dict[int, List[LayoutBlock]] = {}
    global_index = 0
    
    for item in data:
        if not isinstance(item, dict):
            continue
        
        page_idx = int(item.get("page_idx", 0))
        bbox = item.get("bbox")
        
        if not isinstance(bbox, list) or len(bbox) != 4:
            continue
        
        try:
            x0, y0, x1, y1 = float(bbox[0]), float(bbox[1]), float(bbox[2]), float(bbox[3])
        except (TypeError, ValueError):
            continue
        
        block_type = str(item.get("type", "unknown"))
        text = item.get("text")
        if isinstance(text, list):
            text = " ".join(str(t) for t in text)
        text = str(text) if text is not None else None

        img_path = item.get("img_path")
        img_path = str(img_path) if img_path is not None else None

        c_sub_type, c_tags, c_should_translate = _get_mineru_block_semantics(block_type)
        block = LayoutBlock(
            page_index=page_idx,
            bbox=(x0, y0, x1, y1),
            type=block_type,
            sub_type=c_sub_type,
            index=global_index,
            text=text,
            image_path=img_path,
            raw=item.copy(),
            tags=list(c_tags),
            should_translate=c_should_translate,
        )

        pages_dict.setdefault(page_idx, []).append(block)
        global_index += 1

    # Build LayoutDocument
    pages = []
    for page_idx in sorted(pages_dict.keys()):
        pages.append(LayoutPage(
            page_index=page_idx,
            blocks=pages_dict[page_idx]
        ))

    doc = LayoutDocument(pages=pages, engine=engine)
    _infer_title_heading_levels(doc)
    return doc


def parse_mineru_layout_from_zip_bytes(zip_bytes: bytes, engine: str = "mineru") -> Optional[LayoutDocument]:
    """
    Parse MinerU layout from ZIP bytes in memory.

    Tries to parse in this order:
    1. layout.json (new format with nested structure)
    2. *_middle.json (local MinerU API format, same as layout.json)
    3. *_content_list.json (legacy format with flat list)

    Args:
        zip_bytes: ZIP file content as bytes
        engine: Engine name to set on the resulting LayoutDocument (default "mineru")

    Returns:
        LayoutDocument if parsing succeeds, None otherwise
    """
    try:
        # Check if data is zlib compressed instead of ZIP format
        if isinstance(zip_bytes, bytes) and len(zip_bytes) > 2:
            header = zip_bytes[:2]
            # zlib 压缩数据通常以 0x78 0x9c (默认) 或 0x78 0xda (最佳压缩) 开头
            if header == b'\x78\x9c' or header == b'\x78\xda':
                logger.warning(LogModule.LAYOUT, f"Data appears to be zlib compressed (header: {header.hex()}), not ZIP format. Attempting to decompress...")
                try:
                    import zlib
                    decompressed = zlib.decompress(zip_bytes)
                    # Check if decompressed data is ZIP format
                    if decompressed[:4] == b'PK\x03\x04' or decompressed[:4] == b'PK\x05\x06':
                        zip_bytes = decompressed
                        logger.info(LogModule.LAYOUT, f"Successfully decompressed zlib data to ZIP format ({len(zip_bytes)} bytes)")
                    else:
                        logger.error(LogModule.LAYOUT, f"Decompressed data is not ZIP format. Header: {decompressed[:4].hex()}")
                        return None
                except Exception as zlib_error:
                    logger.error(LogModule.LAYOUT, f"Failed to decompress zlib data: {zlib_error}")
                    return None
        
        zip_file = zipfile.ZipFile(io.BytesIO(zip_bytes))
        
        # Try layout.json first (Cloud API format)
        if "layout.json" in zip_file.namelist():
            try:
                layout_data = zip_file.read("layout.json")
                data = json.loads(layout_data.decode('utf-8'))
                
                if isinstance(data, dict) and "pdf_info" in data:
                    # Parse using layout.json format
                    pdf_info = data.get("pdf_info", [])
                    pages_dict: Dict[int, List[LayoutBlock]] = {}
                    global_index = 0
                    
                    for page_data in pdf_info:
                        if not isinstance(page_data, dict):
                            continue
                        
                        page_idx = int(page_data.get("page_idx", 0))
                        page_size = page_data.get("page_size")
                        
                        # Process para_blocks
                        para_blocks = page_data.get("para_blocks", [])
                        for block_data in para_blocks:
                            if not isinstance(block_data, dict):
                                continue
                            global_index = _append_mineru_block_to_pages(
                                pages_dict,
                                page_idx,
                                block_data,
                                global_index,
                            )

                        # Process discarded_blocks
                        discarded_blocks = page_data.get("discarded_blocks", [])
                        for block_data in discarded_blocks:
                            if not isinstance(block_data, dict):
                                continue
                            global_index = _append_mineru_block_to_pages(
                                pages_dict,
                                page_idx,
                                block_data,
                                global_index,
                            )

                    metadata = {
                        "_backend": data.get("_backend"),
                        "_version_name": data.get("_version_name"),
                    }
                    logger.debug(
                        LogModule.EXTRACT,
                        f"Parsed MinerU layout.json: {len(pages_dict)} pages, {global_index} blocks",
                    )
                    return _finalize_mineru_layout_document(
                        pages_dict,
                        pdf_info,
                        metadata,
                        engine=engine,
                    )
            except Exception as e:
                logger.debug(LogModule.LAYOUT, f"Failed to parse layout.json, trying middle.json: {e}")
        
        # Try *_middle.json (Local MinerU API format)
        # middle.json has the same format as layout.json (with pdf_info field)
        middle_json_files = [f for f in zip_file.namelist() if f.endswith('_middle.json')]
        
        if middle_json_files:
            try:
                middle_json_path = middle_json_files[0]
                middle_json_data = zip_file.read(middle_json_path)
                data = json.loads(middle_json_data.decode('utf-8'))
                
                if isinstance(data, dict) and "pdf_info" in data:
                    # Same parsing logic as layout.json
                    pdf_info = data.get("pdf_info", [])
                    pages_dict: Dict[int, List[LayoutBlock]] = {}
                    global_index = 0
                    
                    for page_data in pdf_info:
                        if not isinstance(page_data, dict):
                            continue
                        
                        page_idx = int(page_data.get("page_idx", 0))
                        page_size = page_data.get("page_size")
                        
                        # Process para_blocks
                        para_blocks = page_data.get("para_blocks", [])
                        for block_data in para_blocks:
                            if not isinstance(block_data, dict):
                                continue
                            global_index = _append_mineru_block_to_pages(
                                pages_dict,
                                page_idx,
                                block_data,
                                global_index,
                            )

                        # Process discarded_blocks
                        discarded_blocks = page_data.get("discarded_blocks", [])
                        for block_data in discarded_blocks:
                            if not isinstance(block_data, dict):
                                continue
                            global_index = _append_mineru_block_to_pages(
                                pages_dict,
                                page_idx,
                                block_data,
                                global_index,
                            )

                    metadata = {
                        "_backend": data.get("_backend"),
                        "_version_name": data.get("_version_name"),
                    }
                    logger.info(
                        LogModule.EXTRACT,
                        f"Parsed MinerU middle.json: {len(pages_dict)} pages, {global_index} blocks",
                    )
                    return _finalize_mineru_layout_document(
                        pages_dict,
                        pdf_info,
                        metadata,
                        engine=engine,
                    )
            except Exception as e:
                logger.debug(LogModule.LAYOUT, f"Failed to parse middle.json, trying content_list.json: {e}")
        
        # Fallback to *_content_list.json (legacy format)
        content_list_files = [f for f in zip_file.namelist() if f.endswith('_content_list.json')]
        
        if not content_list_files:
            logger.debug(LogModule.LAYOUT, "No layout.json, middle.json or content_list.json found in MinerU ZIP")
            return None
        
        # Use the first content_list.json found
        content_list_path = content_list_files[0]
        content_list_data = zip_file.read(content_list_path)
        
        # Parse JSON
        data = json.loads(content_list_data.decode('utf-8'))
        
        if not isinstance(data, list):
            logger.warning(LogModule.EXTRACT, f"Expected content_list.json to be a list, got {type(data)}")
            return None
        
        # Group blocks by page_idx
        pages_dict: Dict[int, List[LayoutBlock]] = {}
        global_index = 0
        
        for item in data:
            if not isinstance(item, dict):
                continue
            
            page_idx = int(item.get("page_idx", 0))
            bbox = item.get("bbox")
            
            if not isinstance(bbox, list) or len(bbox) != 4:
                continue
            
            try:
                x0, y0, x1, y1 = float(bbox[0]), float(bbox[1]), float(bbox[2]), float(bbox[3])
            except (TypeError, ValueError):
                continue
            
            block_type = str(item.get("type", "unknown"))
            text = item.get("text")
            if isinstance(text, list):
                text = " ".join(str(t) for t in text)
            text = str(text) if text is not None else None

            img_path = item.get("img_path")
            img_path = str(img_path) if img_path is not None else None

            c2_sub_type, c2_tags, c2_should_translate = _get_mineru_block_semantics(block_type)
            block = LayoutBlock(
                page_index=page_idx,
                bbox=(x0, y0, x1, y1),
                type=block_type,
                sub_type=c2_sub_type,
                index=global_index,
                text=text,
                image_path=img_path,
                raw=item.copy(),
                tags=list(c2_tags),
                should_translate=c2_should_translate,
            )

            pages_dict.setdefault(page_idx, []).append(block)
            global_index += 1

        # Build LayoutDocument
        pages = []
        for page_idx in sorted(pages_dict.keys()):
            pages.append(LayoutPage(
                page_index=page_idx,
                blocks=pages_dict[page_idx]
            ))

        logger.info(LogModule.LAYOUT, f"Parsed MinerU *_content_list.json: {len(pages)} pages, {global_index} blocks")
        doc = LayoutDocument(pages=pages, engine=engine)
        _infer_title_heading_levels(doc)
        return doc

    except Exception as e:
        logger.warning(LogModule.EXTRACT, f"Failed to parse MinerU layout from ZIP: {e}")
        return None
