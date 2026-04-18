# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

"""
Format-specific metadata extractors for exclusion detection.

This module provides format-specific extractors that extract metadata
from different document formats (PDF, DOCX, PPTX, Markdown/HTML) to
support unified exclusion detection.
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any


class FormatMetadataExtractor(ABC):
    """Abstract base class for format-specific metadata extraction."""
    
    @abstractmethod
    def extract_metadata(
        self,
        segment_index: int,
        segment_text: str,
        format_specific_data: Optional[dict] = None
    ) -> Dict[str, Any]:
        """
        Extract metadata for a segment.
        
        Args:
            segment_index: Index of the segment
            segment_text: Text content of the segment
            format_specific_data: Optional format-specific data (e.g., chunk_block_indices for PDF)
        
        Returns:
            dict with keys:
            - block_type: Optional[str] (e.g., "table_body", "header", "image")
            - is_table: bool
            - is_image: bool
            - is_header: bool
            - is_footer: bool
            - format_specific: dict (format-specific metadata)
        """
        pass
    
    @abstractmethod
    def get_format_name(self) -> str:
        """Get format name (e.g., 'pdf', 'docx', 'pptx', 'markdown')."""
        pass


# Import all extractors for convenience
from exclusion.extractors.pdf_extractor import PDFMetadataExtractor
from exclusion.extractors.docx_extractor import DOCXMetadataExtractor
from exclusion.extractors.pptx_extractor import PPTXMetadataExtractor
from exclusion.extractors.markdown_extractor import MarkdownMetadataExtractor

__all__ = [
    "FormatMetadataExtractor",
    "PDFMetadataExtractor",
    "DOCXMetadataExtractor",
    "PPTXMetadataExtractor",
    "MarkdownMetadataExtractor",
]
