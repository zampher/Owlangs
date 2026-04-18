# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

"""
Layout-based document representation for high-fidelity PDF restoration.

This module provides platform-agnostic intermediate representation (IR) for
document layout information, enabling high-fidelity PDF generation from
translated content while preserving original document structure.
"""

from layout.base import LayoutBlock, LayoutPage, LayoutDocument
from layout.markdown_builder import (
    LayoutMarkdownBuilder,
    LayoutMarkdownResult,
    LayoutChunk,
)

__all__ = [
    "LayoutBlock",
    "LayoutPage",
    "LayoutDocument",
    "LayoutMarkdownBuilder",
    "LayoutMarkdownResult",
    "LayoutChunk",
]

