# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

"""
Canonical block type constants and semantic category groupings.

Both MinerU and PaddleOCR parsers normalise their output to these
canonical type strings so that downstream code can use a single set of
type-based dispatch checks.

Semantic category frozensets replace the ad-hoc sets that were previously
scattered across ~8 files, providing a single source of truth for
type-based behavior (translation, redaction, rendering, font sizing).
"""

from typing import FrozenSet

# ---------------------------------------------------------------------------
# Canonical block type string constants
# ---------------------------------------------------------------------------

TEXT = "text"
TITLE = "title"
SUB_TITLE = "sub_title"
HEADER = "header"
FOOTER = "footer"
PAGE_NUMBER = "page_number"
IMAGE = "image"
TABLE = "table"
CHART = "chart"
INTERLINE_EQUATION = "interline_equation"
CODE = "code"
PAGE_FOOTNOTE = "page_footnote"
REF_TEXT = "ref_text"
LIST = "list"
REF_LIST = "ref_list"
REFERENCES = "references"

# Legacy aliases -- older PaddleOCR output and stored segments may still
# use these strings.  They are included in the relevant category sets so
# that convenience methods like ``is_equation()`` recognise them.
LEGACY_FORMULA = "formula"
LEGACY_EQUATION = "equation"
LEGACY_FIGURE = "figure"  # Pre-standardisation alias for IMAGE

# ---------------------------------------------------------------------------
# Nested sub-types (block.raw["blocks"][n]["type"] and chunk_type values)
# ---------------------------------------------------------------------------
# These appear inside the parent block's raw layout data and also as
# chunk_type values in segment metadata.  They are NOT top-level block.type
# values but are still used for dispatch across the codebase.

IMAGE_BODY = "image_body"
TABLE_BODY = "table_body"
CHART_BODY = "chart_body"
IMAGE_CAPTION = "image_caption"
TABLE_CAPTION = "table_caption"
CHART_CAPTION = "chart_caption"
IMAGE_FOOTNOTE = "image_footnote"
TABLE_FOOTNOTE = "table_footnote"
CODE_BLOCK = "code_block"
CAPTION = "caption"  # Generic caption (used for both image and table bodies)

# ---------------------------------------------------------------------------
# Nested sub-type categories
# ---------------------------------------------------------------------------

CAPTION_SUB_TYPES: FrozenSet[str] = frozenset({
    IMAGE_CAPTION, TABLE_CAPTION, CHART_CAPTION, CAPTION,
})

BODY_SUB_TYPES: FrozenSet[str] = frozenset({
    IMAGE_BODY, TABLE_BODY, CHART_BODY,
})

# ---------------------------------------------------------------------------
# Semantic category groups
# ---------------------------------------------------------------------------

# Blocks rendered as images in the PDF overlay (never translated).
VISUAL_BLOCK_TYPES: FrozenSet[str] = frozenset({IMAGE, TABLE, CHART, LEGACY_FIGURE})

# Formula / equation blocks (never translated; may render as image or LaTeX).
EQUATION_BLOCK_TYPES: FrozenSet[str] = frozenset({
    INTERLINE_EQUATION, LEGACY_FORMULA, LEGACY_EQUATION,
})

# Structural blocks (never translated; may be excluded from output).
STRUCTURAL_BLOCK_TYPES: FrozenSet[str] = frozenset({
    HEADER, FOOTER, PAGE_NUMBER,
})

# Heading blocks (translated with markdown heading formatting).
HEADING_BLOCK_TYPES: FrozenSet[str] = frozenset({TITLE, SUB_TITLE})

# List container blocks (expanded to their child text blocks during rendering).
LIST_CONTAINER_TYPES: FrozenSet[str] = frozenset({
    LIST, REF_LIST, REFERENCES,
})

# Reference / citation entry text (translated; special font handling).
REFERENCE_BLOCK_TYPES: FrozenSet[str] = frozenset({REF_TEXT})

# Block types that do NOT contain renderable text for overlay.
NON_TEXT_BLOCK_TYPES: FrozenSet[str] = frozenset({
    IMAGE, TABLE, CHART, LIST, LEGACY_FIGURE,
})

# Block types that should NEVER be redacted from the source PDF.
# Visual content (charts, tables) must remain on the original PDF.
SKIP_REDACTION_TYPES: FrozenSet[str] = frozenset({CHART, TABLE})

# Block types whose text is renderable in a text overlay.
RENDERABLE_TEXT_BLOCK_TYPES: FrozenSet[str] = frozenset({
    TEXT, TITLE, SUB_TITLE, HEADER, FOOTER, PAGE_NUMBER,
    REF_TEXT, PAGE_FOOTNOTE,
})

# Block types skipped from overlay text rendering (visual + list containers).
SKIP_OVERLAY_BLOCK_TYPES: FrozenSet[str] = frozenset({
    IMAGE, TABLE, CHART, LIST, LEGACY_FIGURE,
})

# Block types that default to should_translate=False.
DEFAULT_SKIP_TRANSLATION_TYPES: FrozenSet[str] = frozenset({
    IMAGE, TABLE, CHART, INTERLINE_EQUATION, CODE,
    HEADER, FOOTER, PAGE_NUMBER, LEGACY_FIGURE,
})
