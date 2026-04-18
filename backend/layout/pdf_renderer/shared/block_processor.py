# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

"""
Block processing utilities for PDF rendering.

This module provides shared block processing logic that can be used
by all PDF renderer implementations (ReportLab, HTML-to-PDF, etc.).
"""

import zipfile
from typing import Dict, Optional, List, Tuple
from layout.base import LayoutBlock, LayoutDocument


class BlockProcessor:
    """
    Block processing utilities.
    
    Provides methods for extracting text, layout information, and
    other block-related data from layout structures.
    """
    
    @staticmethod
    def extract_text_from_raw_layout(block_raw: dict) -> Optional[str]:
        """
        Extract text content from block.raw (layout data structure).
        This is a fallback when block.text is empty.
        
        Args:
            block_raw: Raw block data from layout (may have 'lines' -> 'spans' -> 'content')
            
        Returns:
            Extracted text string, or None if no text found
        """
        if not block_raw or not isinstance(block_raw, dict):
            return None
        
        # Try direct 'text' field first
        text = block_raw.get("text")
        if text:
            if isinstance(text, list):
                return " ".join(str(t) for t in text)
            return str(text)
        
        # Extract from lines -> spans -> content
        lines = block_raw.get("lines", [])
        if not lines:
            return None
        
        line_texts = []
        for line in lines:
            if not isinstance(line, dict):
                continue
            spans = line.get("spans", [])
            line_parts = []
            for span in spans:
                if not isinstance(span, dict):
                    continue
                # Check for 'content' field (text spans)
                content = span.get("content")
                if content:
                    line_parts.append(str(content))
                # Also check for 'text' field as fallback
                elif span.get("type") == "text":
                    text = span.get("text")
                    if text:
                        line_parts.append(str(text))
            if line_parts:
                # Join spans within the same line with space
                line_text = " ".join(line_parts).strip()
                if line_text:
                    line_texts.append(line_text)
        
        if line_texts:
            # Join different lines with newline to preserve multi-line structure
            return "\n".join(line_texts)
        return None
    
    @staticmethod
    def extract_image_captions_from_raw(
        block_raw: dict,
        block_index: Optional[int] = None,
        translated_text_by_block_index: Optional[Dict[int, str]] = None,
    ) -> List[Tuple[Tuple[float, float, float, float], str]]:
        """
        Extract image caption texts and their bboxes from an image block's raw layout.

        MinerU encodes image captions as nested blocks, typically with type
        'image_caption' or 'caption', inside the parent image block's 'blocks' list.

        Args:
            block_raw: Raw layout data for the image block
            block_index: Optional block index (for looking up translated text)
            translated_text_by_block_index: Optional mapping from block index to translated text

        Returns:
            List of (bbox, text) where bbox is (x0, y0, x1, y1) in page coordinates.
            Text will be translated if available, otherwise original text.
        """
        captions: List[Tuple[Tuple[float, float, float, float], str]] = []
        if not isinstance(block_raw, dict):
            return captions

        nested_blocks = block_raw.get("blocks") or []
        for sub in nested_blocks:
            if not isinstance(sub, dict):
                continue
            sub_type = str(sub.get("type", ""))
            if sub_type not in ("image_caption", "caption"):
                continue

            bbox = sub.get("bbox")
            if not isinstance(bbox, list) or len(bbox) != 4:
                continue
            try:
                x0, y0, x1, y1 = float(bbox[0]), float(bbox[1]), float(bbox[2]), float(bbox[3])
            except (TypeError, ValueError):
                continue

            original_text = BlockProcessor.extract_text_from_raw_layout(sub) or ""
            if not original_text.strip():
                continue

            # Try to find translated text for this caption
            translated_text = None
            if block_index is not None and translated_text_by_block_index:
                block_translated_text = translated_text_by_block_index.get(block_index)
                if block_translated_text:
                    # The translated text may contain multiple parts (image placeholder, caption, etc.)
                    # Image captions are added as separate segments after the image placeholder,
                    # so they appear as separate lines in the translated text
                    translated_lines = [line.strip() for line in block_translated_text.split('\n') if line.strip()]
                    
                    # Strategy 1: If we have multiple lines, the caption is usually the last line
                    # (image placeholder comes first, then caption)
                    if len(translated_lines) > 1:
                        # Check if any line looks like an image placeholder (contains <ph-...>)
                        import re
                        placeholder_pattern = re.compile(r'<ph-[a-zA-Z0-9]+>')
                        non_placeholder_lines = [line for line in translated_lines if not placeholder_pattern.search(line)]
                        if non_placeholder_lines:
                            # Use the last non-placeholder line as caption (most likely to be the caption)
                            translated_text = non_placeholder_lines[-1]
                        else:
                            # No placeholder found, use the last line
                            translated_text = translated_lines[-1]
                    elif len(translated_lines) == 1:
                        # Only one line - check if it's a placeholder
                        import re
                        placeholder_pattern = re.compile(r'<ph-[a-zA-Z0-9]+>')
                        if not placeholder_pattern.search(translated_lines[0]):
                            # Not a placeholder, likely the caption
                            translated_text = translated_lines[0]
                        else:
                            # It's a placeholder, no caption translation available
                            translated_text = None
                    
                    # Strategy 2: If no good match found, try to match by similarity to original text
                    # (length-based heuristic)
                    if not translated_text and original_text.strip():
                        original_len = len(original_text.strip())
                        # Find line with similar length (within 50% difference)
                        for line in translated_lines:
                            if abs(len(line) - original_len) <= original_len * 0.5:
                                translated_text = line
                                break
                    
                    # Strategy 3: If still no match, use the whole translated text (might be just the caption)
                    if not translated_text and block_translated_text.strip():
                        # Check if it's not just a placeholder
                        import re
                        placeholder_pattern = re.compile(r'^<ph-[a-zA-Z0-9]+>\s*$')
                        if not placeholder_pattern.match(block_translated_text.strip()):
                            translated_text = block_translated_text.strip()

            # Use translated text if available, otherwise use original
            caption_text = translated_text if translated_text else original_text.strip()
            captions.append(((x0, y0, x1, y1), caption_text))

        return captions
    
    @staticmethod
    def get_text_actual_width_from_layout(block_raw: dict) -> Optional[float]:
        """
        Extract actual text width from layout.json block data (from spans).
        
        Args:
            block_raw: Raw block data from layout.json (block.raw)
            
        Returns:
            Actual text width in points, or None if not available
        """
        if not block_raw or not isinstance(block_raw, dict):
            return None
        
        lines = block_raw.get("lines", [])
        if not lines:
            return None
        
        min_x = float('inf')
        max_x = float('-inf')
        
        for line in lines:
            if not isinstance(line, dict):
                continue
            spans = line.get("spans", [])
            for span in spans:
                if not isinstance(span, dict):
                    continue
                span_bbox = span.get("bbox", [])
                if len(span_bbox) >= 4:
                    try:
                        span_x0, span_y0, span_x1, span_y1 = float(span_bbox[0]), float(span_bbox[1]), float(span_bbox[2]), float(span_bbox[3])
                        min_x = min(min_x, span_x0)
                        max_x = max(max_x, span_x1)
                    except (ValueError, TypeError):
                        continue
        
        if min_x != float('inf') and max_x != float('-inf') and max_x > min_x:
            return max_x - min_x
        
        return None
    
    @staticmethod
    def extract_line_heights_from_layout(block_raw: dict) -> List[float]:
        """
        Extract actual line heights from layout.json block data.
        
        This function extracts the actual height of each line from the original layout,
        which is more accurate than estimating from block height divided by line count.
        
        Args:
            block_raw: Raw block data from layout.json (block.raw)
            
        Returns:
            List of line heights in points, empty list if not available
        """
        if not block_raw or not isinstance(block_raw, dict):
            return []
        
        lines = block_raw.get("lines", [])
        if not lines:
            return []
        
        line_heights = []
        
        for line in lines:
            if not isinstance(line, dict):
                continue
            
            line_bbox = line.get("bbox", [])
            if len(line_bbox) >= 4:
                try:
                    line_y0 = float(line_bbox[1])
                    line_y1 = float(line_bbox[3])
                    line_height = line_y1 - line_y0
                    if line_height > 0:
                        line_heights.append(line_height)
                except (ValueError, TypeError):
                    continue
        
        return line_heights
    
    @staticmethod
    def extract_original_line_structure_from_layout(block_raw: dict) -> Optional[List[str]]:
        """
        Extract original line structure from layout.json block data.
        
        This function extracts the original text lines as they appear in the PDF,
        preserving the original line breaks and structure.
        
        Args:
            block_raw: Raw block data from layout.json (block.raw)
            
        Returns:
            List of original text lines, or None if not available
        """
        if not block_raw or not isinstance(block_raw, dict):
            return None
        
        lines = block_raw.get("lines", [])
        if not lines:
            return None
        
        original_lines = []
        
        for line in lines:
            if not isinstance(line, dict):
                continue
            
            spans = line.get("spans", [])
            if not spans:
                continue
            
            # Extract text from all spans in this line
            line_text_parts = []
            for span in spans:
                if not isinstance(span, dict):
                    continue
                
                # Get text content from span
                span_text = span.get("content", "")
                if span_text:
                    line_text_parts.append(span_text)
            
            if line_text_parts:
                original_lines.append("".join(line_text_parts))
        
        return original_lines if original_lines else None
    
    @staticmethod
    def get_block_layout_size_key(block: LayoutBlock) -> Optional[Tuple[str, float]]:
        """
        Compute a layout-based size key for a block, using MinerU line heights.

        The key is a tuple of (block.type, median_line_height_rounded),
        so that blocks of the same type and similar line heights can be grouped
        and share a unified target font size.
        
        Args:
            block: LayoutBlock instance
            
        Returns:
            Tuple of (block_type, median_line_height) or None if not available
        """
        import statistics
        
        if block is None:
            return None

        block_type = getattr(block, "type", None) or "unknown"

        # Prefer precise line heights from layout.raw if available
        line_heights: List[float] = []
        if getattr(block, "raw", None) and isinstance(block.raw, dict):
            line_heights = BlockProcessor.extract_line_heights_from_layout(block.raw)

        median_line_height: Optional[float] = None
        if line_heights:
            try:
                median_line_height = float(statistics.median(line_heights))
            except Exception:
                median_line_height = None

        if median_line_height is None:
            # Fallback: use block bbox height
            try:
                x0, y0, x1, y1 = block.bbox
                block_height = float(y1) - float(y0)
                if block_height <= 0:
                    return None
                median_line_height = block_height
            except Exception:
                return None

        # Round height to reduce noise and group similar sizes together
        key_height = round(median_line_height, 1)
        return (block_type, key_height)
    
    @staticmethod
    def extract_image_from_zip(zip_file: zipfile.ZipFile, image_path: str) -> Optional[bytes]:
        """
        Extract image from ZIP file by trying multiple possible paths.
        
        This handles variations in image path formats (with/without leading slash,
        with/without 'images/' prefix).
        
        Args:
            zip_file: Open zipfile.ZipFile object
            image_path: Image path to extract
            
        Returns:
            Image bytes if found, None otherwise
        """
        if not image_path:
            return None
        
        zip_file_list = zip_file.namelist()
        possible_paths = [
            image_path,
            image_path.lstrip('/'),
            f"images/{image_path}",
            f"images/{image_path.lstrip('/')}",
        ]
        
        for path in possible_paths:
            if path in zip_file_list:
                try:
                    return zip_file.read(path)
                except Exception:
                    continue
        return None
    
    @staticmethod
    def extract_all_images_from_layout(
        layout_doc: LayoutDocument,
        zip_file: zipfile.ZipFile,
    ) -> Dict[str, bytes]:
        """
        Extract all images from layout document ZIP file.
        
        This includes:
        - Images from image blocks
        - Table images from table blocks
        
        Args:
            layout_doc: LayoutDocument instance
            zip_file: Open zipfile.ZipFile object
            
        Returns:
            Dictionary mapping image paths to image bytes
        """
        image_data_map: Dict[str, bytes] = {}
        zip_file_list = zip_file.namelist()
        
        # Extract images from image blocks
        for block in layout_doc.iter_image_blocks():
            if block.image_path:
                image_data = BlockProcessor.extract_image_from_zip(zip_file, block.image_path)
                if image_data:
                    image_data_map[block.image_path] = image_data
        
        # Extract table images from table blocks
        for block in layout_doc.iter_blocks():
            if block.type == "table":
                raw_block = block.raw if hasattr(block, "raw") and isinstance(block.raw, dict) else {}
                nested_blocks = raw_block.get("blocks", []) if isinstance(raw_block, dict) else []
                
                for sub in nested_blocks:
                    if not isinstance(sub, dict):
                        continue
                    if sub.get("type") == "table_body":
                        lines = sub.get("lines", [])
                        for line in lines:
                            if not isinstance(line, dict):
                                continue
                            spans = line.get("spans", [])
                            for span in spans:
                                if not isinstance(span, dict):
                                    continue
                                if span.get("type") == "table":
                                    img_path = span.get("image_path")
                                    if isinstance(img_path, str) and img_path.strip():
                                        image_data = BlockProcessor.extract_image_from_zip(zip_file, img_path)
                                        if image_data:
                                            image_data_map[img_path] = image_data
        
        return image_data_map

