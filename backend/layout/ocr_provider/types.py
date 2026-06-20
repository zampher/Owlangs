# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

"""
Common types for the OCR provider layer.
"""

from dataclasses import dataclass, field
from typing import Dict, Any, List

from layout.base import LayoutDocument
from ir.markdown_document import MarkdownDocument


@dataclass
class OCRProviderResult:
    """Unified result from an OCR provider's convert() call."""

    layout_document: LayoutDocument
    markdown_document: MarkdownDocument
    raw_data: Dict[str, Any] = field(default_factory=dict)
    attachments: List[str] = field(default_factory=list)
