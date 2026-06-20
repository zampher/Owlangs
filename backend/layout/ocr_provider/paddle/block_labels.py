# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

"""
PaddleOCR block label mapping.

Maps PaddleOCR ``block_label`` strings to the platform-agnostic
(block_type, sub_type, tags, should_translate) tuples used by
:class:`LayoutBlock`.
"""

from typing import Dict, Tuple, List

# Paddle label → (block_type, sub_type, tags, should_translate)
PADDLE_LABEL_MAP: Dict[str, Tuple[str, str, List[str], bool]] = {
    "doc_title": ("title", "title", ["heading", "title"], True),
    "text": ("text", "body", [], True),
    "paragraph_title": ("text", "heading", ["heading"], True),
    "abstract": ("text", "abstract", ["abstract"], True),
    "content": ("text", "table_of_contents", ["toc"], True),
    "reference_content": ("text", "reference_entry", ["skip_translation"], False),
    "formula_number": ("text", "formula_number", ["skip_translation"], False),
    "header": ("header", "header", ["skip_translation"], False),
    "footer": ("footer", "footer", ["skip_translation"], False),
    "footnote": ("text", "footnote", [], True),
    "aside_text": ("text", "metadata", ["skip_translation"], False),
    "number": ("page_number", "page_number", ["skip_translation"], False),
    "figure_title": ("text", "figure_caption", ["caption"], True),
    "table_title": ("text", "table_caption", ["caption"], True),
    "table": ("table", "table_html", ["table"], False),
    "chart": ("chart", "chart_body", ["chart", "skip_translation"], False),
    "header_image": ("image", "image_body", ["image", "skip_translation"], False),
    "footer_image": ("image", "image_body", ["image", "skip_translation"], False),
    "image": ("image", "image_body", ["image", "skip_translation"], False),
    "algorithm": ("code", "code_block", ["code"], False),
    "display_formula": ("formula", "display_formula", ["formula"], False),
    "formula": ("formula", "display_formula", ["formula"], False),
    "vision_footnote": ("text", "footnote", [], True),
}


def map_paddle_label(raw_label: str):
    """Return (block_type, sub_type, tags, should_translate) for a PaddleOCR label."""
    entry = PADDLE_LABEL_MAP.get(raw_label.strip().lower())
    if entry is not None:
        return entry
    # Unknown labels default to translatable text
    return ("text", "body", [], True)
