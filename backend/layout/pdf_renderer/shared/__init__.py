# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

"""
Shared components for PDF rendering.

These components can be reused by all PDF renderer implementations
(ReportLab, HTML-to-PDF, etc.).
"""

from layout.pdf_renderer.shared.layout_calculator import LayoutCalculator
from layout.pdf_renderer.shared.text_utils import TextUtils
from utils.font_utils import FontUtils
from layout.pdf_renderer.shared.font_calculator import FontSizeCalculator
from layout.pdf_renderer.shared.block_processor import BlockProcessor
from layout.pdf_renderer.shared.table_utils import TableUtils

__all__ = [
    'LayoutCalculator',
    'TextUtils',
    'FontUtils',
    'FontSizeCalculator',
    'BlockProcessor',
    'TableUtils',
]

