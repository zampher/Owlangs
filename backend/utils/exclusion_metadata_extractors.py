# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

"""
Format-specific metadata extractors for exclusion detection.

DEPRECATED: This module is deprecated. Please use the new exclusion module instead.

For backward compatibility, this module re-exports from exclusion.extractors:
- FormatMetadataExtractor
- PDFMetadataExtractor
- DOCXMetadataExtractor
- PPTXMetadataExtractor
- MarkdownMetadataExtractor

New code should import from exclusion.extractors or exclusion directly.
"""

# Backward compatibility: Re-export from new exclusion module
from exclusion.extractors import (
    FormatMetadataExtractor,
    PDFMetadataExtractor,
    DOCXMetadataExtractor,
    PPTXMetadataExtractor,
    MarkdownMetadataExtractor
)

__all__ = [
    "FormatMetadataExtractor",
    "PDFMetadataExtractor",
    "DOCXMetadataExtractor",
    "PPTXMetadataExtractor",
    "MarkdownMetadataExtractor",
]
