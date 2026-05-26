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
    lines = block_data.get("lines", [])
    if not lines:
        return None
    
    text_parts = []
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
            # Also check for 'text' field as fallback
            elif span.get("type") == "text":
                text = span.get("text")
                if text:
                    text_parts.append(str(text))
    
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
    
    # Also check direct 'image_path' field
    img_path = block_data.get("image_path")
    if img_path:
        return str(img_path)
    
    return None


def parse_layout_json(layout_path: Path) -> LayoutDocument:
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
            
            bbox = block_data.get("bbox")
            if not isinstance(bbox, list) or len(bbox) != 4:
                continue
            
            try:
                x0, y0, x1, y1 = float(bbox[0]), float(bbox[1]), float(bbox[2]), float(bbox[3])
            except (TypeError, ValueError):
                continue
            
            block_type = str(block_data.get("type", "unknown"))
            
            # 特殊处理参考文献等嵌套结构：
            # MinerU 会把一整块引用区域标记为 type="list"，内部再用 blocks[*].type="ref_text" 表示每条引文。
            # 为了后续翻译校对和 PDF 重建时能精确按「每条引文」对齐，
            # 我们在 IR 里把这些内层 ref_text 也提升为独立的 LayoutBlock。
            nested_blocks = block_data.get("blocks") or []
            if block_type == "list" and isinstance(nested_blocks, list) and nested_blocks:
                # 先创建一个外层 list block（主要保留整体 bbox 信息，不带 blocks，避免后续重复提取文本）
                parent_raw = {k: v for k, v in block_data.items() if k != "blocks"}
                parent_text = _extract_text_from_layout_block(parent_raw)  # 通常为空
                parent_block = LayoutBlock(
                    page_index=page_idx,
                    bbox=(x0, y0, x1, y1),
                    type=block_type,
                    index=global_index,
                    text=parent_text,
                    image_path=None,
                    raw=parent_raw,
                )
                pages_dict.setdefault(page_idx, []).append(parent_block)
                global_index += 1

                # 再为每个内层 ref_text/create 子块创建独立的 LayoutBlock
                for sub in nested_blocks:
                    if not isinstance(sub, dict):
                        continue
                    sub_bbox = sub.get("bbox")
                    if not isinstance(sub_bbox, list) or len(sub_bbox) != 4:
                        continue
                    try:
                        sx0, sy0, sx1, sy1 = (
                            float(sub_bbox[0]),
                            float(sub_bbox[1]),
                            float(sub_bbox[2]),
                            float(sub_bbox[3]),
                        )
                    except (TypeError, ValueError):
                        continue

                    sub_type = str(sub.get("type", "unknown"))
                    sub_text = _extract_text_from_layout_block(sub)

                    sub_block = LayoutBlock(
                        page_index=page_idx,
                        bbox=(sx0, sy0, sx1, sy1),
                        type=sub_type,
                        index=global_index,
                        text=sub_text,
                        image_path=None,
                        raw=sub.copy(),
                    )
                    pages_dict.setdefault(page_idx, []).append(sub_block)
                    global_index += 1

                # 这一 para_block 已经拆分完成，继续处理下一个
                continue
            
            # 普通块按原逻辑处理
            # Extract text content
            text = _extract_text_from_layout_block(block_data)
            
            # Extract image path
            img_path = _extract_image_path_from_layout_block(block_data)
            
            # If it's an image block but no image_path found, try to find it in nested structure
            if block_type == "image" and not img_path:
                blocks = block_data.get("blocks", [])
                if blocks:
                    img_path = _extract_image_path_from_layout_block(block_data)
            
            block = LayoutBlock(
                page_index=page_idx,
                bbox=(x0, y0, x1, y1),
                type=block_type,
                index=global_index,
                text=text,
                image_path=img_path,
                raw=block_data.copy()
            )
            
            pages_dict.setdefault(page_idx, []).append(block)
            global_index += 1
        
        # Process discarded_blocks (headers, footers, page numbers, etc.)
        discarded_blocks = page_data.get("discarded_blocks", [])
        for block_data in discarded_blocks:
            if not isinstance(block_data, dict):
                continue
            
            bbox = block_data.get("bbox")
            if not isinstance(bbox, list) or len(bbox) != 4:
                continue
            
            try:
                x0, y0, x1, y1 = float(bbox[0]), float(bbox[1]), float(bbox[2]), float(bbox[3])
            except (TypeError, ValueError):
                continue
            
            block_type = str(block_data.get("type", "unknown"))
            
            # Extract text content
            text = _extract_text_from_layout_block(block_data)
            
            # Discarded blocks typically don't have images
            img_path = None
            
            block = LayoutBlock(
                page_index=page_idx,
                bbox=(x0, y0, x1, y1),
                type=block_type,
                index=global_index,
                text=text,
                image_path=img_path,
                raw=block_data.copy()
            )
            
            pages_dict.setdefault(page_idx, []).append(block)
            global_index += 1
    
    # Build LayoutDocument
    pages = []
    for page_idx in sorted(pages_dict.keys()):
        page_data = pdf_info[page_idx] if page_idx < len(pdf_info) else {}
        page_size = page_data.get("page_size", [])
        width = float(page_size[0]) if len(page_size) >= 1 else None
        height = float(page_size[1]) if len(page_size) >= 2 else None
        
        pages.append(LayoutPage(
            page_index=page_idx,
            blocks=pages_dict[page_idx],
            width=width,
            height=height
        ))
    
    metadata = {
        "_backend": data.get("_backend"),
        "_version_name": data.get("_version_name")
    }
    
    return LayoutDocument(pages=pages, engine="mineru", metadata=metadata)


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
        
        block = LayoutBlock(
            page_index=page_idx,
            bbox=(x0, y0, x1, y1),
            type=block_type,
            index=global_index,
            text=text,
            image_path=img_path,
            raw=item.copy()
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
    
    return LayoutDocument(pages=pages, engine="mineru")


def parse_mineru_layout_from_zip_bytes(zip_bytes: bytes) -> Optional[LayoutDocument]:
    """
    Parse MinerU layout from ZIP bytes in memory.
    
    Tries to parse in this order:
    1. layout.json (new format with nested structure)
    2. *_middle.json (local MinerU API format, same as layout.json)
    3. *_content_list.json (legacy format with flat list)
    
    Args:
        zip_bytes: ZIP file content as bytes
        
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
                            
                            bbox = block_data.get("bbox")
                            if not isinstance(bbox, list) or len(bbox) != 4:
                                continue
                            
                            try:
                                x0, y0, x1, y1 = float(bbox[0]), float(bbox[1]), float(bbox[2]), float(bbox[3])
                            except (TypeError, ValueError):
                                continue
                            
                            block_type = str(block_data.get("type", "unknown"))

                            # 同样地，在 layout.json fallback 路径中也对引用 list 进行展开，
                            # 保证布局 IR 和主路径保持一致。
                            nested_blocks = block_data.get("blocks") or []
                            if block_type == "list" and isinstance(nested_blocks, list) and nested_blocks:
                                parent_raw = {k: v for k, v in block_data.items() if k != "blocks"}
                                parent_text = _extract_text_from_layout_block(parent_raw)
                                parent_block = LayoutBlock(
                                    page_index=page_idx,
                                    bbox=(x0, y0, x1, y1),
                                    type=block_type,
                                    index=global_index,
                                    text=parent_text,
                                    image_path=None,
                                    raw=parent_raw,
                                )
                                pages_dict.setdefault(page_idx, []).append(parent_block)
                                global_index += 1

                                for sub in nested_blocks:
                                    if not isinstance(sub, dict):
                                        continue
                                    sub_bbox = sub.get("bbox")
                                    if not isinstance(sub_bbox, list) or len(sub_bbox) != 4:
                                        continue
                                    try:
                                        sx0, sy0, sx1, sy1 = (
                                            float(sub_bbox[0]),
                                            float(sub_bbox[1]),
                                            float(sub_bbox[2]),
                                            float(sub_bbox[3]),
                                        )
                                    except (TypeError, ValueError):
                                        continue

                                    sub_type = str(sub.get("type", "unknown"))
                                    sub_text = _extract_text_from_layout_block(sub)

                                    sub_block = LayoutBlock(
                                        page_index=page_idx,
                                        bbox=(sx0, sy0, sx1, sy1),
                                        type=sub_type,
                                        index=global_index,
                                        text=sub_text,
                                        image_path=None,
                                        raw=sub.copy(),
                                    )
                                    pages_dict.setdefault(page_idx, []).append(sub_block)
                                    global_index += 1

                                continue

                            text = _extract_text_from_layout_block(block_data)
                            img_path = _extract_image_path_from_layout_block(block_data)
                            
                            if block_type == "image" and not img_path:
                                img_path = _extract_image_path_from_layout_block(block_data)
                            
                            block = LayoutBlock(
                                page_index=page_idx,
                                bbox=(x0, y0, x1, y1),
                                type=block_type,
                                index=global_index,
                                text=text,
                                image_path=img_path,
                                raw=block_data.copy()
                            )
                            
                            pages_dict.setdefault(page_idx, []).append(block)
                            global_index += 1
                        
                        # Process discarded_blocks
                        discarded_blocks = page_data.get("discarded_blocks", [])
                        for block_data in discarded_blocks:
                            if not isinstance(block_data, dict):
                                continue
                            
                            bbox = block_data.get("bbox")
                            if not isinstance(bbox, list) or len(bbox) != 4:
                                continue
                            
                            try:
                                x0, y0, x1, y1 = float(bbox[0]), float(bbox[1]), float(bbox[2]), float(bbox[3])
                            except (TypeError, ValueError):
                                continue
                            
                            block_type = str(block_data.get("type", "unknown"))
                            text = _extract_text_from_layout_block(block_data)
                            
                            block = LayoutBlock(
                                page_index=page_idx,
                                bbox=(x0, y0, x1, y1),
                                type=block_type,
                                index=global_index,
                                text=text,
                                image_path=None,
                                raw=block_data.copy()
                            )
                            
                            pages_dict.setdefault(page_idx, []).append(block)
                            global_index += 1
                    
                    # Build LayoutDocument
                    pages = []
                    for page_idx in sorted(pages_dict.keys()):
                        page_data = pdf_info[page_idx] if page_idx < len(pdf_info) else {}
                        page_size = page_data.get("page_size", [])
                        width = float(page_size[0]) if len(page_size) >= 1 else None
                        height = float(page_size[1]) if len(page_size) >= 2 else None
                        
                        pages.append(LayoutPage(
                            page_index=page_idx,
                            blocks=pages_dict[page_idx],
                            width=width,
                            height=height
                        ))
                    
                    metadata = {
                        "_backend": data.get("_backend"),
                        "_version_name": data.get("_version_name")
                    }
                    
                    logger.debug(LogModule.EXTRACT, f"Parsed MinerU layout.json: {len(pages)} pages, {global_index} blocks")
                    return LayoutDocument(pages=pages, engine="mineru", metadata=metadata)
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
                            
                            bbox = block_data.get("bbox")
                            if not isinstance(bbox, list) or len(bbox) != 4:
                                continue
                            
                            try:
                                x0, y0, x1, y1 = float(bbox[0]), float(bbox[1]), float(bbox[2]), float(bbox[3])
                            except (TypeError, ValueError):
                                continue
                            
                            block_type = str(block_data.get("type", "unknown"))
                            text = _extract_text_from_layout_block(block_data)
                            img_path = _extract_image_path_from_layout_block(block_data)
                            
                            block = LayoutBlock(
                                page_index=page_idx,
                                bbox=(x0, y0, x1, y1),
                                type=block_type,
                                index=global_index,
                                text=text,
                                image_path=img_path,
                                raw=block_data.copy()
                            )
                            
                            pages_dict.setdefault(page_idx, []).append(block)
                            global_index += 1
                        
                        # Process discarded_blocks
                        discarded_blocks = page_data.get("discarded_blocks", [])
                        for block_data in discarded_blocks:
                            if not isinstance(block_data, dict):
                                continue
                            
                            bbox = block_data.get("bbox")
                            if not isinstance(bbox, list) or len(bbox) != 4:
                                continue
                            
                            try:
                                x0, y0, x1, y1 = float(bbox[0]), float(bbox[1]), float(bbox[2]), float(bbox[3])
                            except (TypeError, ValueError):
                                continue
                            
                            block_type = str(block_data.get("type", "unknown"))
                            text = _extract_text_from_layout_block(block_data)
                            
                            block = LayoutBlock(
                                page_index=page_idx,
                                bbox=(x0, y0, x1, y1),
                                type=block_type,
                                index=global_index,
                                text=text,
                                image_path=None,
                                raw=block_data.copy()
                            )
                            
                            pages_dict.setdefault(page_idx, []).append(block)
                            global_index += 1
                    
                    # Build LayoutDocument
                    pages = []
                    for page_idx in sorted(pages_dict.keys()):
                        page_data = pdf_info[page_idx] if page_idx < len(pdf_info) else {}
                        page_size = page_data.get("page_size", [])
                        width = float(page_size[0]) if len(page_size) >= 1 else None
                        height = float(page_size[1]) if len(page_size) >= 2 else None
                        
                        pages.append(LayoutPage(
                            page_index=page_idx,
                            blocks=pages_dict[page_idx],
                            width=width,
                            height=height
                        ))
                    
                    metadata = {
                        "_backend": data.get("_backend"),
                        "_version_name": data.get("_version_name")
                    }
                    
                    logger.info(LogModule.EXTRACT, f"Parsed MinerU middle.json: {len(pages)} pages, {global_index} blocks")
                    return LayoutDocument(pages=pages, engine="mineru", metadata=metadata)
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
            
            block = LayoutBlock(
                page_index=page_idx,
                bbox=(x0, y0, x1, y1),
                type=block_type,
                index=global_index,
                text=text,
                image_path=img_path,
                raw=item.copy()
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
        return LayoutDocument(pages=pages, engine="mineru")
        
    except Exception as e:
        logger.warning(LogModule.EXTRACT, f"Failed to parse MinerU layout from ZIP: {e}")
        return None
