# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

"""
PDF Generator Service

Handles PDF generation from layout documents and workflows.
"""

import asyncio
from collections import defaultdict
from typing import Dict, Any, Optional, List
from pathlib import Path

from logger import unified_logger as logger
from logger.logger import LogModule

# Temporary feature flag: high-fidelity layout-based PDF (ReportLab/HTML fallback).
# When False, this generator will short-circuit and not create additional PDFs,
# so that the system only uses the Pandoc+XeLaTeX markdown-based PDF that is
# already generated for markdown_based workflows.
ENABLE_LAYOUT_PDF_GENERATION: bool = True
# Default PDF renderer type: "typst_overlay" (high-fidelity, preserves original layout)
# or "reportlab" (direct rendering, no HTML intermediate).
DEFAULT_PDF_RENDERER_TYPE: str = "typst_overlay"

# Block types that Typst overlay can render as text (non-image/table/chart).
_RENDERABLE_TEXT_BLOCK_TYPES = frozenset(
    {"text", "title", "header", "footer", "page_number", "ref_text", "figure", "caption"}
)


def _segment_export_text(segment: Dict[str, Any], text_field: str) -> str:
    """Resolve per-segment export text (modified_text falls back to target_text)."""
    if text_field == "source_text":
        return (segment.get("source_text") or "").strip()
    return (segment.get("modified_text") or segment.get("target_text") or "").strip()


def _bbox_contains(outer: tuple, inner: tuple, *, margin: float = 1.0) -> bool:
    ox0, oy0, ox1, oy1 = outer
    ix0, iy0, ix1, iy1 = inner
    return (
        ix0 >= ox0 - margin
        and iy0 >= oy0 - margin
        and ix1 <= ox1 + margin
        and iy1 <= oy1 + margin
    )


def _is_list_expandable_child_type(block_type: str) -> bool:
    """Block types that can receive translated text when a list parent is expanded."""
    return block_type in _RENDERABLE_TEXT_BLOCK_TYPES and block_type not in {
        "list",
        "figure",
    }


def _collect_list_child_indices(
    list_index: int,
    layout_doc,
    block_index_to_type: Dict[int, str],
    block_index_to_bbox: Dict[int, tuple],
) -> List[int]:
    """Resolve MinerU list parent blocks to their renderable child layout blocks."""
    list_bbox = block_index_to_bbox.get(list_index)
    if not list_bbox:
        return []

    page_index = None
    for block in layout_doc.iter_blocks():
        if block.index == list_index:
            page_index = block.page_index
            break
    if page_index is None:
        return []

    page_blocks = sorted(
        (
            block
            for block in layout_doc.iter_blocks()
            if block.page_index == page_index and block.index is not None
        ),
        key=lambda block: block.index,
    )

    # MinerU IR emits list children as consecutive indices immediately after the parent.
    sequential_children: List[int] = []
    passed_list = False
    for block in page_blocks:
        if block.index == list_index:
            passed_list = True
            continue
        if not passed_list:
            continue
        btype = block_index_to_type.get(block.index, block.type)
        if btype == "list":
            break
        if btype in {"image", "table", "chart", "interline_equation"}:
            break
        child_bbox = block_index_to_bbox.get(block.index, block.bbox)
        if not _bbox_contains(list_bbox, child_bbox):
            break
        if _is_list_expandable_child_type(btype) and (block.text or "").strip():
            sequential_children.append(block.index)

    if sequential_children:
        return sequential_children

    # Fallback: any renderable text block contained in the list bbox on the same page.
    contained: List[int] = []
    for block in page_blocks:
        if block.index == list_index:
            continue
        btype = block_index_to_type.get(block.index, block.type)
        if not _is_list_expandable_child_type(btype) or not (block.text or "").strip():
            continue
        child_bbox = block_index_to_bbox.get(block.index, block.bbox)
        if _bbox_contains(list_bbox, child_bbox):
            contained.append(block.index)
    contained.sort(
        key=lambda idx: (
            block_index_to_bbox.get(idx, (0, 0, 0, 0))[1],
            block_index_to_bbox.get(idx, (0, 0, 0, 0))[0],
        )
    )
    return contained


def _expand_renderable_block_indices(
    indices: List[int],
    layout_doc,
    block_index_to_type: Dict[int, str],
    block_index_to_bbox: Dict[int, tuple],
) -> List[int]:
    """Expand non-renderable list blocks to contained text/ref_text layout blocks."""
    expanded: List[int] = []
    seen: set[int] = set()

    for raw_idx in indices:
        try:
            block_index_int = int(raw_idx)
        except (TypeError, ValueError):
            continue
        if block_index_int in seen:
            continue
        block_type = block_index_to_type.get(block_index_int, "text")
        if block_type != "list":
            seen.add(block_index_int)
            expanded.append(block_index_int)
            continue

        child_indices = _collect_list_child_indices(
            block_index_int,
            layout_doc,
            block_index_to_type,
            block_index_to_bbox,
        )
        if child_indices:
            logger.info(
                LogModule.EXPORT,
                f"[LAYOUT] Expanded list block {block_index_int} to child blocks {child_indices}",
            )
            for child_idx in child_indices:
                if child_idx not in seen:
                    seen.add(child_idx)
                    expanded.append(child_idx)
        else:
            logger.warning(
                LogModule.EXPORT,
                f"[LAYOUT] List block {block_index_int} has no renderable children; "
                "translation will not overlay on Typst PDF",
            )
            seen.add(block_index_int)
            expanded.append(block_index_int)
    return expanded


class PDFGenerator:
    """Service for generating PDF files."""
    
    def __init__(self, task_manager):
        """
        Initialize PDF generator.
        
        Args:
            task_manager: Task manager instance for logging
        """
        self.task_manager = task_manager
    
    async def generate(
        self,
        workflow,
        output_dir: Path,
        file_stem: str,
        task_state: Dict[str, Any],
        task_id: str,
        table_body_format: Optional[str] = None,
        equation_format: Optional[str] = None,
        renderer_type: Optional[str] = None,  # "reportlab" (default) or "typst_overlay"
    ) -> Path:
        """
        Generate PDF from layout document using ReportLab (direct rendering, no HTML intermediate).

        When ENABLE_LAYOUT_PDF_GENERATION is False, this method will **not** generate a new
        PDF and will instead raise a ValueError so that callers can rely on the existing
        Pandoc+XeLaTeX PDF generated from markdown.
        """
        try:
            if not ENABLE_LAYOUT_PDF_GENERATION:
                logger.info(
                    LogModule.EXPORT,
                    "[PDF] Layout-based PDF generation is disabled (ENABLE_LAYOUT_PDF_GENERATION=False); "
                    "skipping high-fidelity ReportLab/HTML path."
                )
                raise ValueError("Layout-based PDF generation is disabled.")
            # Check if layout-based rendering is available
            layout_doc = task_state.get("layout_document")
            use_layout_rendering = False
            
            if layout_doc is not None:
                try:
                    from layout.base import LayoutDocument as _LD
                    if isinstance(layout_doc, _LD):
                        use_layout_rendering = True
                        source_input_type = task_state.get("source_input_type") or "layout"
                        logger.info(LogModule.EXPORT, f"[LAYOUT] Using layout_document for block types (source_input_type={source_input_type})")
                        self.task_manager.add_log(task_id, "info", f"[LAYOUT] Using layout-based PDF rendering ({layout_doc.page_count} pages, {sum(1 for _ in layout_doc.iter_blocks())} blocks)")
                except Exception as e:
                    logger.debug(LogModule.EXPORT, f"[LAYOUT] Failed to validate layout_document: {e}")
                    use_layout_rendering = False
            
            if not use_layout_rendering:
                original_filename = task_state.get("original_filename", "")
                error_msg = f"Layout document not available. Cannot generate high-fidelity PDF without layout information. Original file: {original_filename}"
                # Expected for non-PDF sources (e.g. .md); log as WARNING so it is not treated as a failure
                logger.warning(LogModule.CONFIG, f"[LAYOUT] {error_msg}")
                self.task_manager.add_log(task_id, "warning", "Layout information not available. PDF not generated; other formats are still available.")
                raise ValueError(error_msg)
            
            # Direct PDF generation using ReportLab (no HTML intermediate)
            # CRITICAL: Build block text mapping from translation segments
            # This ensures we use translated text (target_text/modified_text) from segments,
            # while layout_document provides structure information (formula/table/image positions and formats)
            segments_data = task_state.get("translation_segments")
            if not segments_data or not isinstance(segments_data, dict):
                logger.warning(LogModule.EXPORT, f"[LAYOUT] No translation segments found in task_state")
                block_text_map: Dict[int, str] = {}
                font_size_by_block_index: Dict[int, float] = {}
                font_weight_by_block_index: Dict[int, str] = {}
                font_style_by_block_index: Dict[int, str] = {}
                leading_em_by_block_index: Dict[int, float] = {}
            else:
                segments = segments_data.get("segments") or []
                is_deep_split_enabled = bool(task_state.get("deep_split"))
                logger.info(
                    LogModule.EXPORT,
                    f"[PDF_REVIEW] Task {task_id}: Using deep_split={is_deep_split_enabled} "
                    f"from task_state for PDF review generation"
                )
                
                # Per-segment text uses modified_text with target_text fallback inside
                # build_block_text_map_from_segments (same as frontend / DOCX export).
                text_field = "target_text"
                logger.info(
                    LogModule.EXPORT,
                    f"[LAYOUT] Building block text map from segments: {len(segments)} segments, "
                    f"deep_split={is_deep_split_enabled}",
                )
                # Build mapping: segments (translated text) -> layout blocks (structure)
                # If segments contain formatting info (LaTeX, Markdown tables), it's preserved
                # Layout blocks provide structure (formula/table/image positions, formats)
                block_text_map = self.build_block_text_map_from_segments(
                    layout_doc,
                    segments,
                    text_field=text_field,
                    task_state=task_state,
                    is_deep_split_enabled=is_deep_split_enabled,
                )
                logger.info(LogModule.EXPORT,f"[LAYOUT] Built block text map: {len(block_text_map)} blocks mapped")

                from layout.pdf_renderer.typst_overlay.segment_font_metrics import (
                    build_block_font_map_from_segments,
                    build_block_font_style_map_from_segments,
                    build_block_font_weight_map_from_segments,
                    build_block_leading_map_from_segments,
                )
                font_size_by_block_index = build_block_font_map_from_segments(
                    segments,
                    task_state,
                )
                font_weight_by_block_index = build_block_font_weight_map_from_segments(
                    segments,
                    task_state,
                )
                font_style_by_block_index = build_block_font_style_map_from_segments(
                    segments,
                    task_state,
                )
                leading_em_by_block_index = build_block_leading_map_from_segments(
                    segments,
                    task_state,
                )
                if font_size_by_block_index:
                    logger.info(
                        LogModule.EXPORT,
                        f"[LAYOUT] User font overrides for {len(font_size_by_block_index)} block(s)",
                    )
                if leading_em_by_block_index:
                    logger.info(
                        LogModule.EXPORT,
                        f"[LAYOUT] User leading overrides for {len(leading_em_by_block_index)} block(s)",
                    )
            
            # Get ZIP bytes for image extraction (chart/table/image embedding)
            zip_bytes = None
            try:
                from backend.app.services.download.download_service import _resolve_layout_zip_bytes
                zip_bytes = _resolve_layout_zip_bytes(task_state)
            except Exception:
                attachments = task_state.get("attachments", {})
                if "mineru" in attachments:
                    try:
                        mineru_attachment = attachments["mineru"]
                        if hasattr(mineru_attachment, "content"):
                            zip_bytes = mineru_attachment.content
                        elif isinstance(mineru_attachment, bytes):
                            zip_bytes = mineru_attachment
                    except Exception as e:
                        logger.debug(LogModule.EXPORT, f"Failed to get ZIP bytes from attachments: {e}")
            if not zip_bytes:
                logger.warning(
                    LogModule.EXPORT,
                    f"[PDF] Task {task_id}: layout ZIP not found; chart image embedding may fail",
                )
            
            # Resolve table/equation/chart format (PDF defaults: table=image, chart=image, equation=latex)
            from backend.app.services.download.download_service import _resolve_export_format_settings

            equation_format_resolved, table_body_format_resolved, chart_body_format_resolved = _resolve_export_format_settings(
                task_state,
                task_state.get("payload"),
                equation_format,
                table_body_format,
                None,
            )
            
            # Check if we should use ReportLab for direct PDF generation
            from backend.config.system_config import get_system_config
            system_config = get_system_config()
            use_reportlab = system_config.pdf.use_reportlab if system_config.pdf else False
            fallback_to_html = system_config.pdf.fallback_to_html if system_config.pdf else True
            
            # Auto-enable ReportLab in debug mode to avoid Playwright issues
            import sys
            is_debugging = hasattr(sys, 'gettrace') and sys.gettrace() is not None
            if is_debugging and use_layout_rendering:
                # Check if ReportLab is available
                try:
                    from layout.pdf_renderer_reportlab import REPORTLAB_AVAILABLE
                    if REPORTLAB_AVAILABLE:
                        logger.info(LogModule.EXPORT,f"[REPORTLAB] Debug mode detected: auto-enabling ReportLab to avoid Playwright issues")
                        use_reportlab = True
                    else:
                        logger.warning(LogModule.EXPORT, f"[REPORTLAB] Debug mode detected but ReportLab not available, will try Playwright")
                except ImportError:
                    logger.warning(LogModule.EXPORT, f"[REPORTLAB] Debug mode detected but ReportLab import failed, will try Playwright")
            
            # Debug logging for ReportLab decision
            logger.info(LogModule.EXPORT, f"[REPORTLAB] Configuration check: use_reportlab={use_reportlab}, use_layout_rendering={use_layout_rendering}, fallback_to_html={fallback_to_html}, is_debugging={is_debugging}")
            
            pdf_file = output_dir / f"{file_stem}_translated.pdf"
            
            # Use ReportLab for direct PDF generation (preferred method)
            if use_reportlab and use_layout_rendering:
                try:
                    from layout.pdf_renderer import render_layout_pdf, REPORTLAB_AVAILABLE
                    
                    if REPORTLAB_AVAILABLE:
                        logger.info(LogModule.EXPORT, "[REPORTLAB] Using ReportLab for direct PDF generation (high-fidelity)")
                        self.task_manager.add_log(task_id, "info", "[REPORTLAB] Generating PDF using ReportLab (high-fidelity)")
                        
                        # Generate PDF using ReportLab
                        # Run in thread pool to avoid blocking event loop
                        loop = asyncio.get_event_loop()
                        logger.info(LogModule.EXPORT, f"[PDF] Executing PDF generation in thread pool (renderer={renderer_type or DEFAULT_PDF_RENDERER_TYPE})")
                        # Extract target language from task_state
                        target_language = None
                        payload_obj = task_state.get("payload")
                        if isinstance(payload_obj, dict):
                            target_language = payload_obj.get("to_lang") or payload_obj.get("target_language")
                        elif hasattr(payload_obj, "to_lang"):
                            target_language = getattr(payload_obj, "to_lang", None) or getattr(payload_obj, "target_language", None)

                        # Build renderer kwargs based on renderer type
                        _rt = renderer_type or DEFAULT_PDF_RENDERER_TYPE
                        render_kwargs = dict(
                            translated_text_by_block_index=block_text_map if block_text_map else None,
                            zip_bytes=zip_bytes,
                            table_body_format=table_body_format_resolved,
                            equation_format=equation_format_resolved,
                            chart_body_format=chart_body_format_resolved,
                            target_language=target_language,
                            renderer_type=_rt,
                            font_size_by_block_index=(
                                font_size_by_block_index
                                if font_size_by_block_index
                                else None
                            ),
                            font_weight_by_block_index=(
                                font_weight_by_block_index
                                if font_weight_by_block_index
                                else None
                            ),
                            font_style_by_block_index=(
                                font_style_by_block_index
                                if font_style_by_block_index
                                else None
                            ),
                            leading_em_by_block_index=(
                                leading_em_by_block_index
                                if leading_em_by_block_index
                                else None
                            ),
                        )
                        if _rt == "typst_overlay":
                            source_pdf = task_state.get("original_file_path")
                            if not source_pdf or not Path(source_pdf).exists():
                                logger.warning(LogModule.EXPORT, f"[PDF] source_pdf_path not found, falling back to ReportLab")
                                _rt = "reportlab"
                                render_kwargs["renderer_type"] = _rt
                            else:
                                render_kwargs["source_pdf_path"] = source_pdf
                                render_kwargs["output_path"] = pdf_file
                        else:
                            render_kwargs["output_path"] = output_dir / f"{file_stem}_reportlab_debug.pdf" if logger.level <= 10 else None

                        pdf_bytes = await loop.run_in_executor(
                            None,
                            lambda: render_layout_pdf(layout_doc, **render_kwargs)
                        )
                        
                        # Save PDF
                        with open(pdf_file, 'wb') as f:
                            f.write(pdf_bytes)
                        
                        logger.info(LogModule.EXPORT, f"[REPORTLAB] Successfully generated PDF: {pdf_file.stat().st_size if pdf_file.exists() else 0} bytes")
                        self.task_manager.add_log(task_id, "info", f"[REPORTLAB] PDF generated successfully: {pdf_file.stat().st_size if pdf_file.exists() else 0} bytes")
                        
                        # Store PDF path in task_state (use dict format for consistency)
                        if "downloadable_files" not in task_state:
                            task_state["downloadable_files"] = {}
                        task_state["downloadable_files"]["pdf"] = {"path": str(pdf_file)}
                        
                        return pdf_file  # Success, exit early
                        
                except ImportError as e:
                    logger.warning(LogModule.EXPORT, f"[REPORTLAB] ReportLab not available: {e}")
                    if not fallback_to_html:
                        raise ValueError("ReportLab is required but not available. Install with: pip install reportlab")
                except Exception as e:
                    logger.error(LogModule.EXPORT, f"[REPORTLAB] Failed to generate PDF with ReportLab: {e}", exc_info=True)
                    self.task_manager.add_log(task_id, "warning", f"[REPORTLAB] PDF generation failed: {e}")
                    if not fallback_to_html:
                        raise ValueError(f"ReportLab PDF generation failed: {e}")
                    logger.info(LogModule.EXPORT, "[REPORTLAB] Falling back to HTML → PDF conversion")
            
            # Fallback to HTML → PDF (if ReportLab is not available or failed)
            temp_html_file = None
            if not use_reportlab or fallback_to_html:
                logger.info(LogModule.EXPORT, "[LAYOUT] Using HTML → PDF conversion (Playwright/browser) as fallback")
                
                # Build HTML for fallback (only if ReportLab is not available)
                from layout.html_renderer import render_layout_html
                logger.info(LogModule.EXPORT, f"[LAYOUT] Rendering layout-based HTML for fallback: {len(block_text_map)} blocks mapped")
                html_content = render_layout_html(layout_doc, translated_text_by_block_index=block_text_map if block_text_map else None, zip_bytes=zip_bytes)
                
                # Create temporary HTML file
                temp_html_file = output_dir / f"{file_stem}_temp.html"
                logger.info(LogModule.EXPORT,f"[LAYOUT] Writing HTML to temporary file: {temp_html_file}")
                with open(temp_html_file, 'w', encoding='utf-8') as f:
                    f.write(html_content)
                
                # Use Playwright to convert HTML to PDF (fallback only)
                try:
                    from playwright.async_api import async_playwright
                except ImportError:
                    self.task_manager.add_log(task_id, "warning", "Playwright not available, cannot use HTML fallback")
                    raise ValueError("Neither ReportLab nor Playwright is available. Cannot generate PDF.")
                
                async with async_playwright() as p:
                    browser = await p.chromium.launch(headless=True)
                    page = await browser.new_page()
                    await page.goto(f"file://{temp_html_file.absolute()}")
                    await page.pdf(path=str(pdf_file), format="A4", print_background=True)
                    await browser.close()
                
                logger.info(LogModule.EXPORT, f"[PLAYWRIGHT] PDF generated via HTML fallback: {pdf_file.stat().st_size if pdf_file.exists() else 0} bytes")
            
            # Store PDF path in task_state
            if "downloadable_files" not in task_state:
                task_state["downloadable_files"] = {}
            task_state["downloadable_files"]["pdf"] = {"path": str(pdf_file)}
            
            # Clean up temporary HTML file if it exists
            if temp_html_file and temp_html_file.exists():
                try:
                    temp_html_file.unlink()
                except Exception as cleanup_error:
                    logger.warning(LogModule.EXPORT, f"Error cleaning up temp HTML file: {cleanup_error}")
            
            self.task_manager.add_log(task_id, "success", f"PDF file generated: {pdf_file}")
            
            return pdf_file
                
        except FileNotFoundError:
            # Re-raise FileNotFoundError as-is (already logged)
            raise
        except Exception as e:
            err_str = str(e)
            is_layout_unavailable = "Layout document not available" in err_str
            if is_layout_unavailable:
                logger.warning(LogModule.EXPORT, f"[PDF] PDF not generated (no layout): {e}")
                self.task_manager.add_log(task_id, "warning", f"PDF not generated: {err_str}")
            else:
                logger.error(LogModule.EXPORT, f"[PDF] PDF generation failed: {e}", exc_info=True)
                self.task_manager.add_log(task_id, "error", f"PDF generation failed: {err_str}")
            raise
    
    def build_block_text_map_from_segments(
        self,
        layout_doc,
        segments: List[Dict],
        text_field: str,
        task_state: Dict[str, Any],
        is_deep_split_enabled: bool = False,
    ) -> Dict[int, str]:
        """
        Build block text mapping from segments (unified for both original and translated PDF).
        
        This function extracts text from segments and distributes it to layout blocks,
        using the same logic for both source_text (original PDF) and target_text/modified_text (translated PDF).
        
        CRITICAL: This function prioritizes information from segments:
        1. Text content: Uses target_text/modified_text from segments (translated text with preserved formatting)
        2. Block mapping: Uses layout_block_indices from segments to map to layout blocks
        3. Block type: Uses layout_document's block.type for structure (formula, table, image, etc.)
        
        The rendered PDF will use:
        - Layout structure (formula/table/image positions, formats) from layout_document
        - Translated text content (with preserved LaTeX formulas, Markdown tables) from segments
        
        If segments already contain formatting information (e.g., LaTeX formulas in $...$, 
        Markdown tables in |...| format), these are preserved and used directly.
        If not, the layout_document's structure information is used as fallback.
        
        Args:
            layout_doc: LayoutDocument instance (provides structure: formula/table/image positions and formats)
            segments: List of segment dictionaries (provides translated text with preserved formatting)
            text_field: Field name to extract from segments ('source_text', 'target_text', or 'modified_text')
            task_state: Task state dictionary (for layout_chunk_block_texts)
            is_deep_split_enabled: Whether deep split is enabled (affects how multiple segments map to same block)
            
        Returns:
            Dictionary mapping block index to text content (translated text from segments)
        """
        from layout.pdf_renderer.typst_overlay.segment_font_metrics import (
            resolve_segment_layout_block_indices,
        )

        block_text_map: Dict[int, str] = {}
        block_text_sequences = defaultdict(list) if is_deep_split_enabled else None
        layout_chunk_block_texts: List[List[str]] = task_state.get("layout_chunk_block_texts") or []
        
        # Build block index to type mapping, original texts, and raw data for hints
        layout_block_original_texts: Dict[int, str] = {}
        block_index_to_type: Dict[int, str] = {}
        block_index_to_raw: Dict[int, Dict] = {}
        block_index_to_bbox: Dict[int, tuple] = {}
        for block in layout_doc.iter_blocks():
            if block.index is not None:
                layout_block_original_texts[block.index] = (block.text or "").strip()
                block_index_to_type[block.index] = block.type
                block_index_to_raw[block.index] = getattr(block, "raw", None) or {}
                block_index_to_bbox[block.index] = block.bbox
        
        # Helper function to distribute text to multiple blocks (with whitespace boundary handling)
        def _split_by_newlines(text: str, expected: int) -> List[str]:
            text = (text or "").replace("\r", "")
            parts = [part.strip() for part in text.split("\n") if part.strip()]
            return parts if len(parts) == expected else None
        
        def _nearest_whitespace_boundary(text: str, target: int) -> int:
            text_len = len(text)
            if target >= text_len:
                return text_len
            if text[target:target + 1].isspace():
                return target
            window = 20
            forward = next((target + offset for offset in range(1, window) if target + offset < text_len and text[target + offset].isspace()), None)
            backward = next((target - offset for offset in range(1, window) if target - offset > 0 and text[target - offset].isspace()), None)
            candidates = [pos for pos in [backward, forward] if pos is not None]
            if not candidates:
                return target
            return min(candidates, key=lambda pos: abs(pos - target))
        
        def _split_by_weights(text: str, weights: List[int]) -> List[str]:
            if not weights:
                return []
            normalized_text = text.strip()
            if not normalized_text:
                return [""] * len(weights)
            total_weight = sum(weights) or len(weights)
            text_len = len(normalized_text)
            result: List[str] = []
            cursor = 0
            for idx, weight in enumerate(weights):
                if idx == len(weights) - 1:
                    piece = normalized_text[cursor:].strip()
                    result.append(piece)
                    break
                share = max(1, round(text_len * weight / total_weight))
                tentative_end = min(text_len, cursor + share)
                boundary = _nearest_whitespace_boundary(normalized_text, tentative_end)
                end_pos = max(boundary, cursor + 1)
                piece = normalized_text[cursor:end_pos].strip()
                result.append(piece)
                cursor = end_pos
            if len(result) < len(weights):
                result.extend([""] * (len(weights) - len(result)))
            elif len(result) > len(weights):
                extra = result[len(weights) - 1:]
                merged = " ".join(piece for piece in extra if piece)
                result = result[:len(weights) - 1] + [merged]
            return result
        
        def _distribute_text_to_blocks(text: str, block_hints: List[str]) -> List[str]:
            expected = len(block_hints)
            if expected == 0:
                return []
            normalized_text = (text or "").strip()
            if not normalized_text:
                return [""] * expected
            newline_split = _split_by_newlines(normalized_text, expected)
            if newline_split:
                return newline_split
            weights = [max(len((hint or "").strip()), 1) for hint in block_hints]
            return _split_by_weights(normalized_text, weights)
        
        # Map text from segments to blocks
        for seg_index, seg in enumerate(segments):
            # For segments with text (even if is_image=True, e.g., image captions), participate in mapping
            # Only skip segments with no text at all
            indices = resolve_segment_layout_block_indices(seg, task_state)
            if not indices:
                continue
            
            text = _segment_export_text(seg, text_field)
            if not text:
                continue

            indices = _expand_renderable_block_indices(
                indices,
                layout_doc,
                block_index_to_type,
                block_index_to_bbox,
            )
            
            # Filter out image blocks from indices, BUT keep image blocks for image caption segments
            # Image captions are text segments that map to image blocks, and their text should be preserved
            text_block_indices: List[int] = []
            image_block_indices: List[int] = []  # Track image blocks separately for caption mapping
            for idx in indices:
                try:
                    block_index_int = int(idx)
                except (TypeError, ValueError):
                    continue
                block_type = block_index_to_type.get(block_index_int)

                # Skip cross-page paired blocks: they have no standalone text;
                # their share of the translation is rendered via the source block's
                # _split_cross_page_text logic.
                raw = block_index_to_raw.get(block_index_int, {})
                if isinstance(raw, dict) and raw.get("_cross_page_pair_of") is not None:
                    continue

                if block_type == "image":
                    # Keep image blocks for potential caption mapping
                    image_block_indices.append(block_index_int)
                elif block_type == "list":
                    # Parent list blocks are not rendered by Typst; children were expanded above.
                    continue
                else:
                    text_block_indices.append(block_index_int)
            
            # If we have text but only image blocks, this might be an image caption segment
            # Map the text to the image block(s) so it can be retrieved later
            if not text_block_indices and image_block_indices and text:
                # This is likely an image caption segment - map text to image block
                for img_idx in image_block_indices:
                    if img_idx in block_text_map:
                        # Merge with existing text (image placeholder + caption)
                        block_text_map[img_idx] = f"{block_text_map[img_idx]}\n{text}"
                    else:
                        block_text_map[img_idx] = text
                continue
            
            if not text_block_indices:
                continue
            
            try:
                expected_blocks = len(text_block_indices)
                if expected_blocks == 1:
                    # One layout block per segment: never split by partial span hints.
                    per_block_texts = [text.strip()]
                else:
                    block_hints = [
                        (layout_block_original_texts.get(idx) or "")
                        for idx in text_block_indices
                    ]
                    if all(not hint.strip() for hint in block_hints):
                        if seg_index < len(layout_chunk_block_texts):
                            candidate_hints = layout_chunk_block_texts[seg_index] or []
                            if len(candidate_hints) == expected_blocks:
                                block_hints = candidate_hints
                    per_block_texts = _distribute_text_to_blocks(text, block_hints)
                
                for block_index_int, block_text in zip(text_block_indices, per_block_texts):
                    try:
                        normalized_block_text = block_text.strip()
                        if not normalized_block_text:
                            continue
                        
                        if is_deep_split_enabled and block_text_sequences is not None:
                            block_text_sequences[block_index_int].append(normalized_block_text)
                        else:
                            # Merge with newline if block already has text
                            if block_index_int in block_text_map:
                                existing_text = block_text_map[block_index_int]
                                if normalized_block_text:
                                    block_text_map[block_index_int] = f"{existing_text}\n{normalized_block_text}"
                            else:
                                block_text_map[block_index_int] = normalized_block_text
                    except (TypeError, ValueError):
                        continue
            except Exception as distribute_error:
                logger.warning(
                    LogModule.EXPORT,
                    f"[LAYOUT] Failed to distribute text for segment {seg_index} (field={text_field}): {distribute_error}"
                )
        
        # Merge deep split sequences if enabled
        if is_deep_split_enabled and block_text_sequences:
            logger.info(LogModule.EXPORT, f"[LAYOUT] Deep split enabled: merging {len(block_text_sequences)} block sequences")
            for idx, parts in block_text_sequences.items():
                merged = "\n".join(part for part in parts if part).strip()
                if merged:
                    block_text_map[idx] = merged

        self._reconcile_block_text_map_lengths(
            block_text_map,
            segments,
            text_field,
            task_state,
            layout_doc,
            layout_block_original_texts,
            block_index_to_type,
            block_index_to_raw,
            block_index_to_bbox,
        )
        
        return block_text_map

    @staticmethod
    def _reconcile_block_text_map_lengths(
        block_text_map: Dict[int, str],
        segments: List[Dict],
        text_field: str,
        task_state: Dict[str, Any],
        layout_doc,
        layout_block_original_texts: Dict[int, str],
        block_index_to_type: Dict[int, str],
        block_index_to_raw: Dict[int, Dict],
        block_index_to_bbox: Dict[int, tuple],
    ) -> None:
        """Recover block text when mapping used a partial segment instead of full paragraph."""
        from layout.pdf_renderer.typst_overlay.segment_font_metrics import (
            resolve_segment_layout_block_indices,
        )
        from layout.pdf_renderer.typst_overlay.text_metrics import (
            is_suspiciously_short_mapped_text,
        )

        dedicated_texts: Dict[int, List[str]] = defaultdict(list)
        for seg in segments:
            seg_text = _segment_export_text(seg, text_field)
            if not seg_text:
                continue
            text_indices: List[int] = []
            resolved = _expand_renderable_block_indices(
                resolve_segment_layout_block_indices(seg, task_state),
                layout_doc,
                block_index_to_type,
                block_index_to_bbox,
            )
            for raw_idx in resolved:
                try:
                    block_index_int = int(raw_idx)
                except (TypeError, ValueError):
                    continue
                if block_index_to_type.get(block_index_int) == "image":
                    continue
                raw = block_index_to_raw.get(block_index_int, {})
                if isinstance(raw, dict) and raw.get("_cross_page_pair_of") is not None:
                    continue
                text_indices.append(block_index_int)
            if len(text_indices) == 1:
                dedicated_texts[text_indices[0]].append(seg_text)

        for block_index, original in layout_block_original_texts.items():
            mapped = (block_text_map.get(block_index) or "").strip()
            if not is_suspiciously_short_mapped_text(mapped, original):
                continue
            candidates = dedicated_texts.get(block_index) or []
            if not candidates:
                continue
            best = max(candidates, key=len)
            if len(best) > len(mapped):
                logger.warning(
                    LogModule.EXPORT,
                    f"[LAYOUT] block_text_map[{block_index}] suspiciously short "
                    f"(mapped={len(mapped)}, layout={len(original)}); "
                    f"recovering from dedicated segment text ({len(best)} chars)",
                )
                block_text_map[block_index] = best

