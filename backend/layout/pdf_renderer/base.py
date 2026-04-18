# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

"""
Base classes for PDF renderers.

This module defines the abstract base class that all PDF renderer implementations
must inherit from.
"""

from abc import ABC, abstractmethod
from typing import Dict, Optional
from pathlib import Path

from layout.base import LayoutDocument
from layout.pdf_renderer.config import PDFRendererConfig
from layout.pdf_renderer.shared.layout_calculator import LayoutCalculator
from layout.pdf_renderer.shared.font_calculator import FontSizeCalculator
from layout.pdf_renderer.shared.text_utils import TextUtils
from utils.font_utils import FontUtils
from logger.logger import unified_logger, LogModule


class BasePDFRenderer(ABC):
    """
    Abstract base class for PDF renderers.
    
    All PDF renderer implementations (ReportLab, HTML-to-PDF, etc.) must
    inherit from this class and implement the `render` method.
    
    This class provides shared components (layout calculator, font calculator, etc.)
    that can be used by all implementations.
    """
    
    def __init__(self, config: PDFRendererConfig):
        """
        Initialize PDF renderer.
        
        Args:
            config: PDF renderer configuration
        """
        self.config = config
        
        # Initialize shared components (all implementations can use these)
        self.layout_calc = LayoutCalculator()
        self.font_calc = FontSizeCalculator(
            config.type_font_baselines or {},
            config
        )
        self.text_utils = TextUtils()
        self.font_utils = FontUtils()
    
    def prepare(self, layout_doc: LayoutDocument) -> None:
        """
        Prepare phase: calculate font baselines, extract images, etc.
        
        This method performs shared preprocessing that all implementations need.
        It can be called by implementations before rendering.
        
        Args:
            layout_doc: LayoutDocument instance
        """
        # Calculate type-specific font baselines (shared logic)
        # Note: The actual implementation of _calculate_type_font_baselines
        # is still in pdf_renderer_reportlab.py and will be migrated later.
        # For now, we'll import it from there using lazy import to avoid circular imports.
        try:
            import importlib
            pdf_renderer_module = importlib.import_module('layout.pdf_renderer_reportlab')
            _calculate_type_font_baselines = getattr(pdf_renderer_module, '_calculate_type_font_baselines', None)
            
            if _calculate_type_font_baselines:
                self.config.type_font_baselines = _calculate_type_font_baselines(
                    layout_doc,
                    self.config.translated_text_by_block_index
                )
                
                unified_logger.debug(
                    LogModule.RESTOR,
                    f"[PDF_RENDERER] Calculated type font baselines: {self.config.type_font_baselines}"
                )
            else:
                unified_logger.warning(
                    LogModule.RESTOR,
                    "[PDF_RENDERER] _calculate_type_font_baselines not found, using empty baselines"
                )
                self.config.type_font_baselines = {}
        except Exception as e:
            unified_logger.warning(
                LogModule.RESTOR,
                f"[PDF_RENDERER] Could not calculate type font baselines: {e}, using empty baselines"
            )
            self.config.type_font_baselines = {}
        
        # Update font calculator with new baselines
        self.font_calc.type_font_baselines = self.config.type_font_baselines
        
        # Extract image data from ZIP (shared logic)
        if self.config.zip_bytes:
            self.config.image_data_map = self._extract_images_from_zip(
                self.config.zip_bytes,
                layout_doc
            )
    
    def _extract_images_from_zip(
        self,
        zip_bytes: bytes,
        layout_doc: LayoutDocument
    ) -> Dict[str, bytes]:
        """
        Extract image data from ZIP bytes.
        
        Args:
            zip_bytes: ZIP file bytes
            layout_doc: LayoutDocument instance (to find image paths)
            
        Returns:
            Dictionary mapping image paths to image data bytes
        """
        import zipfile
        import io
        
        image_data_map: Dict[str, bytes] = {}
        
        try:
            zip_file = zipfile.ZipFile(io.BytesIO(zip_bytes))
            
            # Iterate through all image blocks to find image paths
            for block in layout_doc.iter_image_blocks():
                if block.image_path:
                    try:
                        # Try to read image from ZIP
                        image_data = zip_file.read(block.image_path)
                        image_data_map[block.image_path] = image_data
                    except KeyError:
                        # Image not found in ZIP, try with different path variations
                        # (e.g., with/without leading slash, different directory separators)
                        import os
                        possible_paths = [
                            block.image_path,
                            block.image_path.lstrip('/'),
                            os.path.basename(block.image_path),
                        ]
                        
                        for path in possible_paths:
                            try:
                                image_data = zip_file.read(path)
                                image_data_map[block.image_path] = image_data
                                break
                            except KeyError:
                                continue
        except Exception as e:
            unified_logger.warning(
                LogModule.RESTOR,
                f"[PDF_RENDERER] Failed to extract images from ZIP: {e}"
            )
        
        return image_data_map
    
    @abstractmethod
    def render(self, layout_doc: LayoutDocument) -> bytes:
        """
        Render LayoutDocument to PDF bytes.
        
        This method must be implemented by all PDF renderer subclasses.
        
        Args:
            layout_doc: LayoutDocument instance
            
        Returns:
            PDF file content as bytes
            
        Raises:
            NotImplementedError: If not implemented by subclass
        """
        raise NotImplementedError("Subclasses must implement render() method")

