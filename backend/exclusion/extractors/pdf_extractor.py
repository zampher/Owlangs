# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

"""PDF metadata extractor for exclusion detection."""

import re
from typing import Dict, Optional, Any

from layout.block_types import TABLE_BODY
from exclusion.extractors.base import FormatMetadataExtractor


def _is_image_segment_text(text: str) -> bool:
    """
    Lightweight image-segment detector used ONLY inside PDFMetadataExtractor.

    目的：
    - 避免在此处直接导入 utils.translation_segments，从而打破
      pdf_extractor -> utils.translation_segments -> app -> exclusion -> pdf_extractor
      这一循环依赖。
    - 保持与 _is_image_segment 的核心语义一致：只有“纯图片内容”的段才算 IMAGE，
      任何带文字的 caption 一律不算。

    判定规则（和 utils.translation_segments._is_image_segment 对齐的子集）：
    - 文本在去掉空白后：
      - 仅由一个或多个 `<ph-...>` 占位符组成；或
      - 仅包含一个 data URI 图片：`data:image/...;base64,...`；或
      - 仅包含 Markdown 图片语法：`![alt](path)`，且无其他文本。
    """
    if not text:
        return False

    stripped = text.strip()
    if not stripped:
        return False

    # 1) 纯占位符：<ph-img-0> 或多个，占位符之间只允许空白/换行
    placeholder_pattern = r"^(?:\s*<ph-[^>]+>\s*)+$"
    if re.match(placeholder_pattern, stripped):
        return True

    # 2) 纯 data URI 图片
    data_uri_pattern = r"^data:image\/[a-zA-Z0-9.+-]+;base64,[A-Za-z0-9+/=\r\n]+$"
    if re.match(data_uri_pattern, stripped):
        return True

    # 3) 纯 Markdown 图片：![alt](path)
    markdown_img_pattern = r"^!\[[^\]]*\]\([^)]+\)$"
    if re.match(markdown_img_pattern, stripped):
        return True

    return False


class PDFMetadataExtractor(FormatMetadataExtractor):
    """Extract metadata from PDF layout information."""
    
    def __init__(self, block_type_map: Dict[int, str], block_image_map: Dict[int, str]):
        """
        Initialize PDF metadata extractor.
        
        Args:
            block_type_map: Mapping from block_index to block_type
            block_image_map: Mapping from block_index to image_path
        """
        self.block_type_map = block_type_map
        self.block_image_map = block_image_map
    
    def extract_metadata(
        self,
        segment_index: int,
        segment_text: str,
        format_specific_data: Optional[dict] = None
    ) -> Dict[str, Any]:
        """
        Extract metadata from PDF layout.
        
        format_specific_data should contain:
        - chunk_block_indices: List[int] (block indices for this chunk)
        - chunk_type: Optional[str] (e.g., "image")
        - image_path: Optional[str] (image path if available)
        - image_placeholder: Optional[str] (image placeholder ID)
        """
        metadata = {
            "block_type": None,
            "is_table": False,
            "is_image": False,
            "is_header": False,
            "is_footer": False,
            "format_specific": {}
        }
        
        # Check if chunk is an image chunk (from LayoutMarkdownBuilder)
        if format_specific_data:
            chunk_type = format_specific_data.get("chunk_type")
            if chunk_type == "image":
                metadata["is_image"] = True
                metadata["block_type"] = "image"
                if format_specific_data.get("image_path"):
                    metadata["format_specific"]["image_path"] = format_specific_data["image_path"]
                if format_specific_data.get("image_placeholder"):
                    metadata["format_specific"]["image_placeholder"] = format_specific_data["image_placeholder"]
                return metadata
            
            # PDF layout: table_body from LayoutMarkdownBuilder chunk_type (no string-based check)
            if chunk_type == TABLE_BODY:
                metadata["is_table"] = True
                metadata["block_type"] = TABLE_BODY
                return metadata
            
            # Check block types from chunk_block_indices
            chunk_block_indices = format_specific_data.get("chunk_block_indices", [])
            
            for block_idx in chunk_block_indices:
                if block_idx in self.block_type_map:
                    block_type = self.block_type_map[block_idx]
                    metadata["block_type"] = block_type
                    
                    if block_type == "image":
                        metadata["is_image"] = True
                        if block_idx in self.block_image_map:
                            metadata["format_specific"]["image_path"] = self.block_image_map[block_idx]
                    elif block_type in ["header", "page_header"]:
                        metadata["is_header"] = True
                    elif block_type in ["footer", "page_footer"]:
                        metadata["is_footer"] = True
                    elif block_type == "table":
                        # Caption/footnote or legacy path: block_type stays "table"; table_body
                        # is set only when chunk_type == "table_body" above.
                        metadata["block_type"] = block_type
        
        # Also check if segment text is an image-only segment (fallback).
        # IMPORTANT:
        # - We must NOT treat caption text (e.g. "Figure 1: ...") as image content.
        # - Only pure placeholders / pure markdown images / base64 image lines
        #   should be classified as image segments for exclusion.
        if not metadata["is_image"] and _is_image_segment_text(segment_text):
            metadata["is_image"] = True
            metadata["block_type"] = "image"

            # If this image segment is represented by a placeholder, try to
            # extract the placeholder id and resolve the underlying image path.
            placeholder_match = re.search(r'<ph-([^>]+)>', segment_text)
            if placeholder_match:
                placeholder_id = placeholder_match.group(1)
                metadata["format_specific"]["image_placeholder"] = placeholder_id
                # Try to find image_path from placeholder_id
                if placeholder_id.startswith("img-"):
                    try:
                        img_block_idx = int(placeholder_id.replace("img-", ""))
                        if img_block_idx in self.block_image_map:
                            metadata["format_specific"]["image_path"] = self.block_image_map[img_block_idx]
                    except ValueError:
                        # Best-effort only – ignore placeholder parsing issues
                        pass
        
        return metadata
    
    def get_format_name(self) -> str:
        return "pdf"
