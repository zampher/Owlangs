# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

"""Markdown/HTML metadata extractor for exclusion detection."""

from typing import Dict, Optional, Any

from exclusion.extractors.base import FormatMetadataExtractor


class MarkdownMetadataExtractor(FormatMetadataExtractor):
    """Extract metadata from Markdown/HTML text patterns."""
    
    def extract_metadata(
        self,
        segment_index: int,
        segment_text: str,
        format_specific_data: Optional[dict] = None
    ) -> Dict[str, Any]:
        """Extract metadata from text patterns (no format-specific metadata)."""
        metadata = {
            "block_type": None,
            "is_table": False,
            "is_image": False,
            "is_header": False,
            "is_footer": False,
            "format_specific": {}
        }
        
        # Check if it's a table (markdown table syntax)
        from utils.translation_segments import _is_table_segment
        if _is_table_segment(segment_text):
            metadata["is_table"] = True
            metadata["block_type"] = "table"
        
        return metadata
    
    def get_format_name(self) -> str:
        return "markdown"
