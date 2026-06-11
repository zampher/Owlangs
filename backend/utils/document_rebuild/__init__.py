# SPDX-FileCopyrightText: 2026 Zampherss
# SPDX-License-Identifier: MPL-2.0

"""
Document rebuild package.

Re-exports all public APIs so that existing callers using
``from utils.document_rebuild import ...`` continue to work unchanged.
"""

# --- Markdown rebuild ---
from .markdown_rebuild import (
    has_revised_segments,
    rebuild_markdown_document_from_segments,
    _prepare_image_data_map,
    _process_images_and_create_markdown_document,
    _rebuild_markdown_from_layout_segments,
    _rebuild_markdown_from_text_segments,
)

# --- DOCX rebuild ---
from .docx_rebuild import (
    rebuild_docx_document_from_segments,
)

# --- HTML tag utilities ---
from .html_tag_utils import (
    _close_unclosed_inline_tags,
)

# --- Table / layout extraction utilities ---
from .table_layout_utils import (
    _extract_table_from_layout_block,
    _extract_equation_from_layout_block,
    _extract_chart_from_layout_block,
    _is_chart_body_segment,
    _is_markdown_table,
    _markdown_table_to_html,
    _replace_table_cells_with_translations,
)

# --- General utilities re-exported for backward compatibility ---
# These live at utils/ level but were historically imported from utils.document_rebuild
from utils.format_convert_utils import (
    convert_html_to_docx,
)
from utils.image_placeholder_utils import (
    _replace_placeholders_with_images,
    PLACEHOLDER_PATTERN,
)

__all__ = [
    # Public API
    "has_revised_segments",
    "rebuild_markdown_document_from_segments",
    "rebuild_docx_document_from_segments",
    "convert_html_to_docx",
    # Semi-public (used by external modules)
    "_replace_placeholders_with_images",
    "_close_unclosed_inline_tags",
    "PLACEHOLDER_PATTERN",
]
