# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0
"""Data models for image overlay rendering."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, Tuple


@dataclass
class ImageOverlayConfig:
    """Controls how translated text is painted onto a source raster image."""

    erase_original_text: bool = True
    cover_margin_px: float = 2.0
    default_font_size_px: float = 14.0
    min_font_size_px: float = 8.0
    max_font_size_px: float = 72.0
    text_color_rgb: Tuple[int, int, int] = (0, 0, 0)
    text_field: str = "target_text"
    target_language: Optional[str] = None
    equation_format: str = "text"
    table_body_format: str = "html"
    chart_body_format: str = "image"
    cover_color_mode: str = "max"
    output_format: Optional[str] = None
    jpeg_quality: int = 95


@dataclass
class ImageOverlayResult:
    """Rendered image bytes and response metadata."""

    image_bytes: bytes
    media_type: str
    file_extension: str
    width: int = 0
    height: int = 0
    text_blocks_drawn: int = 0
    visual_placements_drawn: int = 0


@dataclass
class ImageOverlayInput:
    """
    Normalized input for the overlay pipeline.

    Future PDF/DOCX workflows can build this from extracted page images without
    going through full task_state.
    """

    source_image_path: str
    layout_document: object
    segments: list = field(default_factory=list)
    layout_zip_bytes: Optional[bytes] = None
    task_state: Optional[dict] = None
