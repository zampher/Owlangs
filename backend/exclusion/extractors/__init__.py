# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

"""Format-specific metadata extractors."""

from exclusion.extractors.base import FormatMetadataExtractor
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
