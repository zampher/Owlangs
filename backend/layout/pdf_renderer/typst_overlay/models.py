# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

"""
Data models for Typst overlay rendering.

These models bridge Owlangs' LayoutDocument/LayoutBlock IR
to the Typst overlay rendering pipeline.
"""

from dataclasses import dataclass, field
from typing import List, Optional, Tuple


@dataclass
class RenderLineBox:
    """A single preserved line with its exact bounding box."""
    text: str
    bbox: Tuple[float, float, float, float]  # (x0, y0, x1, y1)


@dataclass
class RenderTocEntry:
    """A single table-of-contents entry for Typst TOC rendering."""
    title: str
    page_label: str
    bbox: List[float]  # [x0, y0, x1, y1]
    number: str = ""
    level: int = 1


@dataclass
class RenderBlock:
    """A single renderable block with all typographic properties needed by Typst."""

    block_id: str                          # unique identifier
    page_index: int                        # zero-based page index
    inner_bbox: Tuple[float, float, float, float]  # placeable inner region

    # -- text content --
    markdown_text: str = ""                # markdown with formula tokens
    plain_text: str = ""                   # plain text fallback
    render_kind: str = "markdown"          # "markdown" | "plain" | "plain_line" | "skip"

    # -- typography --
    font_size_pt: float = 10.0
    leading_em: float = 1.25
    font_weight: str = "regular"           # "regular" | "bold"
    first_line_indent_pt: float = 0.0
    justify_text: bool = False

    # -- colors --
    text_color: Tuple[float, float, float] = (0.0, 0.0, 0.0)
    cover_fill: Tuple[float, float, float] = (1.0, 1.0, 1.0)
    use_cover_fill: bool = False
    opaque_fill: bool = False            # render text with opaque background fill (for caption/footer overlay)

    # -- cover / TOC --
    cover_bbox: Optional[List[float]] = None  # cover rect bbox when different from inner_bbox
    toc_entries: Optional[List[RenderTocEntry]] = None  # TOC entries for table-of-contents rendering

    # -- fit-to-box settings --
    fit_to_box: bool = False               # enable font-size fitting
    fit_single_line: bool = False          # single-line fit mode
    fit_min_font_size_pt: float = 6.0
    fit_max_font_size_pt: float = 24.0
    fit_min_leading_em: float = 0.9
    fit_max_height_pt: float = 0.0
    fit_target_width_pt: float = 0.0
    fit_target_height_pt: float = 0.0
    fit_shift_up_pt: float = 0.0

    # -- embedded visual (chart/table body as image) --
    image_rel_path: str = ""                # path relative to Typst work dir

    # -- advanced --
    math_map: Optional[List[dict]] = None    # formula identifier -> latex map
    preserve_line_breaks: bool = False
    preserved_line_boxes: Optional[List[RenderLineBox]] = None
    skip_reason: str = ""                   # non-empty means skip rendering


@dataclass
class RenderPageSpec:
    """A complete page specification for Typst overlay generation."""

    page_index: int
    page_width_pt: float
    page_height_pt: float
    blocks: List[RenderBlock] = field(default_factory=list)
    source_pdf_path: str = ""             # path to the cleaned source PDF page image


def layout_block_to_render_block(
    block,
    page_index: int,
    translated_text: str,
    *,
    block_id: str = "",
    font_size_pt: float = 10.0,
    leading_em: float = 1.25,
    font_weight: str = "regular",
) -> RenderBlock:
    """
    Convert an Owlangs LayoutBlock to a Typst RenderBlock.

    Args:
        block: Owlangs LayoutBlock from layout.base
        page_index: zero-based page index
        translated_text: the translated text to render
        block_id: override block identifier (defaults to "block-{index}")
        font_size_pt: font size in points
        leading_em: line height in em
        font_weight: "regular" or "bold"

    Returns:
        RenderBlock ready for Typst source generation
    """
    x0, y0, x1, y1 = block.bbox

    raw = block.raw if hasattr(block, 'raw') else {}
    heading_level = getattr(block, 'heading_level', 0) or 0

    # Determine render kind from block type
    block_type = getattr(block, 'type', 'text') or 'text'
    if block_type in ('image', 'figure', 'table'):
        # Image/table blocks: skip text rendering, keep original
        render_kind = "skip"
    elif block_type in ('title', 'header') or heading_level >= 1:
        # Titles use markdown rendering so multi-line document titles wrap with leading.
        render_kind = "markdown"
    elif len(translated_text) < 80:
        render_kind = "plain_line"
    else:
        render_kind = "markdown"

    # Detect if the text appears to contain formula tokens ($...$)
    # Use  $  as a simple heuristic
    if '$' in translated_text and render_kind == "plain":
        render_kind = "markdown"

    # Read font info from raw MinerU data if available
    block_font_size = font_size_pt
    block_font_weight = font_weight
    if isinstance(raw, dict):
        # Some MinerU output includes font_size in raw['orig_font_size'] or similar
        raw_font_size = (
            raw.get('font_size')
            or raw.get('orig_font_size')
            or raw.get('inferred_font_size')
        )
        if raw_font_size and isinstance(raw_font_size, (int, float)):
            block_font_size = float(raw_font_size)
        raw_font_weight = raw.get('font_weight') or raw.get('weight')
        if raw_font_weight:
            block_font_weight = str(raw_font_weight)

    return RenderBlock(
        block_id=block_id or f"block-{block.index}" if hasattr(block, 'index') else f"block-{page_index}",
        page_index=page_index,
        inner_bbox=block.bbox,
        markdown_text=translated_text,
        plain_text=translated_text,
        render_kind=render_kind,
        font_size_pt=block_font_size,
        leading_em=leading_em,
        font_weight=block_font_weight,
        skip_reason="image" if render_kind == "skip" else "",
        use_cover_fill=False,
    )
