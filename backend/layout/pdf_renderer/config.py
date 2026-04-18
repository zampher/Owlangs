# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

"""
PDF renderer configuration.

This module defines the configuration class used by all PDF renderer implementations.
"""

from typing import Dict, Optional
from pathlib import Path


class PDFRendererConfig:
    """
    PDF renderer shared configuration.
    
    This class contains all configuration needed by PDF renderer implementations.
    It avoids passing many individual parameters and provides a single source of truth.
    """
    
    def __init__(
        self,
        translated_text_by_block_index: Optional[Dict[int, str]] = None,
        zip_bytes: Optional[bytes] = None,
        table_body_format: str = "html",
        equation_format: str = "text",
        target_language: Optional[str] = None,
        output_path: Optional[Path] = None,
    ):
        """
        Initialize PDF renderer configuration.
        
        Args:
            translated_text_by_block_index: Optional mapping from block index to translated text
            zip_bytes: Optional ZIP bytes for extracting images
            table_body_format: Table format ("html" or "image")
            equation_format: Equation format ("text" for LaTeX or "image" for rendered images)
            target_language: Optional target language code/name for font selection
            output_path: Optional path to save PDF file (for debugging)
        """
        self.translated_text_by_block_index = translated_text_by_block_index or {}
        self.zip_bytes = zip_bytes
        self.table_body_format = table_body_format
        self.equation_format = equation_format
        self.target_language = target_language
        self.output_path = output_path
        
        # These will be populated during rendering
        self.type_font_baselines: Dict[str, float] = {}
        self.image_data_map: Dict[str, bytes] = {}

