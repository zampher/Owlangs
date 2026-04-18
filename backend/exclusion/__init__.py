# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

"""
Exclusion management module for translation segments.

This module provides unified exclusion detection, management, and operations
for all document formats.
"""

# Core classes
from exclusion.core.exclusion_reason import ExclusionReason
from exclusion.core.exclusion_manager import ExclusionManager
from exclusion.core.exclusion_detector import detect_exclusion_reason

# Batch detection
from exclusion.detection.batch_detector import ExclusionDetectionBatch

# Extractors
from exclusion.extractors.base import FormatMetadataExtractor
from exclusion.extractors.pdf_extractor import PDFMetadataExtractor
from exclusion.extractors.docx_extractor import DOCXMetadataExtractor
from exclusion.extractors.pptx_extractor import PPTXMetadataExtractor
from exclusion.extractors.markdown_extractor import MarkdownMetadataExtractor

# User operations
from exclusion.operations.user_operations import (
    exclude_translation_segment,
    unexclude_translation_segment
)

# API interfaces
from exclusion.api.extract_phase_api import ExclusionExtractAPI
from exclusion.api.translate_phase_api import ExclusionTranslateAPI

__all__ = [
    # Core
    "ExclusionReason",
    "ExclusionManager",
    "detect_exclusion_reason",
    # Batch detection
    "ExclusionDetectionBatch",
    # Extractors
    "FormatMetadataExtractor",
    "PDFMetadataExtractor",
    "DOCXMetadataExtractor",
    "PPTXMetadataExtractor",
    "MarkdownMetadataExtractor",
    # User operations
    "exclude_translation_segment",
    "unexclude_translation_segment",
    # API interfaces
    "ExclusionExtractAPI",
    "ExclusionTranslateAPI",
]
