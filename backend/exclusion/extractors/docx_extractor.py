# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

"""DOCX metadata extractor for exclusion detection."""

from typing import Dict, List, Optional, Any

from exclusion.extractors.base import FormatMetadataExtractor


class DOCXMetadataExtractor(FormatMetadataExtractor):
    """Extract metadata from DOCX segment_info."""
    
    def __init__(self, segment_info: List[dict]):
        """
        Initialize DOCX metadata extractor.
        
        Args:
            segment_info: List of segment info dicts, each containing:
                - is_table_cell: bool
                - table_index: Optional[int]
                - row_index: Optional[int]
                - cell_index: Optional[int]
                - para_index: Optional[int]
        """
        self.segment_info = segment_info
    
    def extract_metadata(
        self,
        segment_index: int,
        segment_text: str,
        format_specific_data: Optional[dict] = None
    ) -> Dict[str, Any]:
        """Extract metadata from DOCX segment_info."""
        metadata = {
            "block_type": None,
            "is_table": False,
            "is_image": False,
            "is_header": False,
            "is_footer": False,
            "format_specific": {}
        }
        
        if segment_index < len(self.segment_info):
            seg_info = self.segment_info[segment_index]
            is_table_cell = seg_info.get("is_table_cell", False)
            
            if is_table_cell:
                metadata["is_table"] = True
                metadata["block_type"] = "table"
                metadata["format_specific"] = {
                    "table_index": seg_info.get("table_index"),
                    "row_index": seg_info.get("row_index"),
                    "cell_index": seg_info.get("cell_index"),
                    "para_index": seg_info.get("para_index"),
                }
        
        return metadata
    
    def get_format_name(self) -> str:
        return "docx"
