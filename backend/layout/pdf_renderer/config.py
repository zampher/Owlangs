# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

"""
PDF renderer configuration.

This module defines the configuration class used by all PDF renderer implementations.
"""

from typing import Dict, Optional, Set, Union
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
        chart_body_format: str = "image",
        target_language: Optional[str] = None,
        output_path: Optional[Path] = None,
        # --- Typst overlay renderer fields ---
        source_pdf_path: Optional[Union[str, Path]] = None,
        typst_font_family: Optional[str] = None,
        font_size_by_block_index: Optional[Dict[int, float]] = None,
        font_weight_by_block_index: Optional[Dict[int, str]] = None,
        font_style_by_block_index: Optional[Dict[int, str]] = None,
        leading_em_by_block_index: Optional[Dict[int, float]] = None,
        rotation_by_block_index: Optional[Dict[int, int]] = None,
        table_stroke_pt_by_block_index: Optional[Dict[int, float]] = None,
        render_page_indices: Optional[Set[int]] = None,
        base_merged_pdf_bytes: Optional[bytes] = None,
        cleaned_source_output_path: Optional[Path] = None,
        skip_overlay_block_indices: Optional[Set[int]] = None,
    ):
        """
        Initialize PDF renderer configuration.

        Args:
            translated_text_by_block_index: Optional mapping from block index to translated text
            zip_bytes: Optional ZIP bytes for extracting images
            table_body_format: Table format ("html" or "image")
            equation_format: Equation format ("text" for LaTeX or "image" for rendered images)
            chart_body_format: Chart format ("html" or "image")
            target_language: Optional target language code/name for font selection
            output_path: Optional path to save PDF file (for debugging)
            source_pdf_path: Path to the original PDF file (required for Typst overlay renderer)
            typst_font_family: Typst font family name (default: "Noto Sans CJK SC")
        """
        self.translated_text_by_block_index = translated_text_by_block_index or {}
        self.zip_bytes = zip_bytes
        self.table_body_format = table_body_format
        self.equation_format = equation_format
        self.chart_body_format = chart_body_format
        self.target_language = target_language
        self.output_path = output_path

        # Typst overlay renderer fields
        self.source_pdf_path: Optional[Union[str, Path]] = source_pdf_path
        self.typst_font_family: Optional[str] = typst_font_family
        self.font_size_by_block_index = font_size_by_block_index or {}
        self.font_weight_by_block_index = font_weight_by_block_index or {}
        self.font_style_by_block_index = font_style_by_block_index or {}
        self.leading_em_by_block_index = leading_em_by_block_index or {}
        self.rotation_by_block_index = rotation_by_block_index or {}
        self.table_stroke_pt_by_block_index = table_stroke_pt_by_block_index or {}
        self.render_page_indices = render_page_indices
        self.base_merged_pdf_bytes = base_merged_pdf_bytes
        self.cleaned_source_output_path = cleaned_source_output_path
        self.skip_overlay_block_indices: Optional[Set[int]] = skip_overlay_block_indices
        
        # These will be populated during rendering
        self.type_font_baselines: Dict[str, float] = {}
        self.image_data_map: Dict[str, bytes] = {}

