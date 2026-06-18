# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0
"""
High-level image overlay pipeline.

PNG/JPG workflows call ``render_from_task_state``. Future PDF/DOCX page-image
pipelines can call ``render`` with ``ImageOverlayInput`` directly.
"""

from __future__ import annotations

import io
import zipfile
from pathlib import Path
from typing import Any, Dict, List, Optional

from layout.image_overlay.block_text_map import (
    ImageOverlayBlockMapResult,
    build_image_overlay_block_text_map,
)
from layout.image_overlay.models import ImageOverlayConfig, ImageOverlayInput, ImageOverlayResult
from layout.image_overlay.renderer import ImageOverlayRenderer
from layout.pdf_renderer.shared.block_processor import BlockProcessor
from logger.logger import LogModule, unified_logger


class ImageOverlayPipeline:
    """Reusable entry point for raster overlay export."""

    def __init__(self, renderer: Optional[ImageOverlayRenderer] = None) -> None:
        self._renderer = renderer or ImageOverlayRenderer()

    def render(
        self,
        overlay_input: ImageOverlayInput,
        config: ImageOverlayConfig,
        *,
        block_text_map: Optional[Dict[int, str]] = None,
        font_size_by_block_index: Optional[Dict[int, float]] = None,
        font_weight_by_block_index: Optional[Dict[int, str]] = None,
        task_id: str = "",
    ) -> ImageOverlayResult:
        from PIL import Image, ImageOps

        source_path = Path(overlay_input.source_image_path)
        if not source_path.is_file():
            raise FileNotFoundError(f"Source image not found: {source_path}")

        layout_doc = overlay_input.layout_document
        if layout_doc is None:
            raise ValueError("layout_document is required for image overlay rendering")

        with Image.open(source_path) as opened:
            oriented = ImageOps.exif_transpose(opened)
            canvas = oriented.convert("RGBA")

        task_state = overlay_input.task_state
        if isinstance(task_state, dict):
            task_state["overlay_source_image_size"] = [canvas.width, canvas.height]

        image_data_map = self._build_image_bytes_map(
            layout_doc,
            overlay_input.layout_zip_bytes,
        )

        block_segment_meta: Optional[Dict[int, Dict[str, Any]]] = None
        if block_text_map is None:
            block_map_result = self._build_block_text_map(
                layout_doc,
                overlay_input.segments,
                overlay_input.task_state or {},
                config.text_field,
            )
            block_text_map = block_map_result.block_text_map
            block_segment_meta = block_map_result.block_segment_meta

        if block_segment_meta and overlay_input.segments:
            from layout.image_overlay.block_text_map import (
                build_block_typography_maps_from_overlay_meta,
            )

            meta_font_map, meta_weight_map = build_block_typography_maps_from_overlay_meta(
                overlay_input.segments,
                block_segment_meta,
            )
            if meta_font_map:
                font_size_by_block_index = meta_font_map
            if meta_weight_map:
                font_weight_by_block_index = meta_weight_map

        font_family = self._resolve_font_family(config.target_language)
        task_state = overlay_input.task_state or {}
        temp_dir = task_state.get("temp_dir")
        effective_task_id = task_id or str(task_state.get("task_id") or "")
        stats = self._renderer.render(
            canvas,
            layout_doc,
            block_text_map,
            config,
            image_data_map=image_data_map,
            font_family=font_family,
            font_size_by_block_index=font_size_by_block_index,
            font_weight_by_block_index=font_weight_by_block_index,
            temp_dir=temp_dir,
            task_id=effective_task_id,
            source_image_path=str(source_path),
            block_segment_meta=block_segment_meta,
        )
        encoded = self._renderer.encode_image(canvas, str(source_path), config)
        encoded.text_blocks_drawn = stats.text_blocks_drawn
        encoded.visual_placements_drawn = stats.visual_placements_drawn
        return encoded

    @staticmethod
    def _resolve_font_family(target_language: Optional[str]) -> str:
        try:
            from translator.ai_translator.docx_translator import get_font_for_language

            return get_font_for_language(target_language or "en")
        except Exception:
            return "Calibri"

    @staticmethod
    def _build_block_text_map(
        layout_doc,
        segments: List[Dict[str, Any]],
        task_state: Dict[str, Any],
        text_field: str,
    ) -> ImageOverlayBlockMapResult:
        if not segments:
            return ImageOverlayBlockMapResult()
        return build_image_overlay_block_text_map(
            layout_doc,
            segments,
            text_field=text_field,
            task_state=task_state,
        )

    @staticmethod
    def _build_image_bytes_map(layout_doc, zip_bytes: Optional[bytes]) -> Dict[str, bytes]:
        if not zip_bytes:
            return {}
        try:
            with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zip_file:
                return BlockProcessor.extract_all_images_from_layout(layout_doc, zip_file)
        except Exception as exc:
            unified_logger.warning(
                LogModule.EXPORT,
                f"[IMAGE_OVERLAY] Failed to extract layout ZIP images: {exc}",
            )
            return {}
