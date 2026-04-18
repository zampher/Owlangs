# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

"""PPTX metadata extractor for exclusion detection."""

from typing import Dict, Optional, Any

from exclusion.extractors.base import FormatMetadataExtractor


class PPTXMetadataExtractor(FormatMetadataExtractor):
    """Extract metadata from PPTX element_type."""
    
    def __init__(self, element_type_map: Dict[int, str]):
        """
        Initialize PPTX metadata extractor.
        
        Args:
            element_type_map: Mapping from segment_index to element_type
                (e.g., "table_cell", "notes", "master", "text_frame")
        """
        self.element_type_map = element_type_map
    
    def extract_metadata(
        self,
        segment_index: int,
        segment_text: str,
        format_specific_data: Optional[dict] = None
    ) -> Dict[str, Any]:
        """Extract metadata from PPTX element_type."""
        metadata = {
            "block_type": None,
            "is_table": False,
            "is_image": False,
            "is_header": False,
            "is_footer": False,
            "format_specific": {}
        }
        
        element_type = self.element_type_map.get(segment_index, "text_frame")
        metadata["block_type"] = element_type
        
        if element_type == "table_cell":
            metadata["is_table"] = True
        elif element_type in ["notes", "master"]:
            # Notes and master can be treated as structural
            metadata["format_specific"] = {"element_type": element_type}
        
        return metadata
    
    def get_format_name(self) -> str:
        return "pptx"
