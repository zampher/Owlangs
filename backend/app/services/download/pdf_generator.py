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
ENABLE_LAYOUT_PDF_GENERATION: bool = False
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
        equation_format: Optional[str] = None
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
            else:
                segments = segments_data.get("segments") or []
                is_deep_split_enabled = bool(task_state.get("deep_split"))
                logger.info(
                    LogModule.EXPORT,
                    f"[PDF_REVIEW] Task {task_id}: Using deep_split={is_deep_split_enabled} "
                    f"from task_state for PDF review generation"
                )
                
                # Use modified_text or target_text (translated text from segments)
                # These texts may already contain formatting (LaTeX formulas, Markdown tables)
                # which will be preserved and used directly
                text_field = "modified_text"  # Prefer modified_text (user-edited translations)
                # Check if any segment has modified_text, otherwise use target_text
                has_modified = any(seg.get("modified_text") for seg in segments)
                if not has_modified:
                    text_field = "target_text"
                
                logger.info(LogModule.EXPORT, f"[LAYOUT] Building block text map from segments: {len(segments)} segments, text_field={text_field}, deep_split={is_deep_split_enabled}")
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
            
            # Get ZIP bytes for image extraction
            zip_bytes = None
            attachments = task_state.get("attachments", {})
            if "mineru" in attachments:
                try:
                    mineru_attachment = attachments["mineru"]
                    if hasattr(mineru_attachment, "content"):
                        zip_bytes = mineru_attachment.content
                except Exception as e:
                    logger.debug(LogModule.EXPORT, f"Failed to get ZIP bytes from attachments: {e}")
            
            # Resolve table body format
            # Priority: function parameter > task payload > default "html"
            table_body_format_resolved = "html"
            if table_body_format and table_body_format.lower() in ("html", "image"):
                table_body_format_resolved = table_body_format.lower()
            else:
                payload_obj = task_state.get("payload")
                try:
                    if isinstance(payload_obj, dict):
                        table_body_format_resolved = (payload_obj.get("table_body_format") or payload_obj.get("table_format") or "html").lower()
                    elif payload_obj is not None:
                        table_body_format_resolved = (
                            getattr(payload_obj, "table_body_format", None)
                            or getattr(payload_obj, "table_format", None)
                            or "html"
                        ).lower()
                except Exception:
                    table_body_format_resolved = "html"
            if table_body_format_resolved not in ("html", "image"):
                table_body_format_resolved = "html"
            
            # Resolve equation format
            # Priority: function parameter > task payload > default "text"
            equation_format_resolved = "text"
            if equation_format and equation_format.lower() in ("text", "image"):
                equation_format_resolved = equation_format.lower()
            else:
                payload_obj = task_state.get("payload")
                try:
                    if isinstance(payload_obj, dict):
                        equation_format_resolved = (payload_obj.get("equation_format") or "text").lower()
                    elif payload_obj is not None:
                        equation_format_resolved = (getattr(payload_obj, "equation_format", None) or "text").lower()
                except Exception:
                    equation_format_resolved = "text"
            if equation_format_resolved not in ("text", "image"):
                equation_format_resolved = "text"
            
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
                        logger.info(LogModule.EXPORT, "[REPORTLAB] Executing ReportLab PDF generation in thread pool to avoid blocking")
                        # Extract target language from task_state
                        target_language = None
                        payload_obj = task_state.get("payload")
                        if isinstance(payload_obj, dict):
                            target_language = payload_obj.get("to_lang") or payload_obj.get("target_language")
                        elif hasattr(payload_obj, "to_lang"):
                            target_language = getattr(payload_obj, "to_lang", None) or getattr(payload_obj, "target_language", None)
                        
                        pdf_bytes = await loop.run_in_executor(
                            None,
                            lambda: render_layout_pdf(
                                layout_doc,
                                translated_text_by_block_index=block_text_map if block_text_map else None,
                                zip_bytes=zip_bytes,
                                output_path=output_dir / f"{file_stem}_reportlab_debug.pdf" if logger.level <= 10 else None,  # 10 is DEBUG level
                                table_body_format=table_body_format_resolved,
                                equation_format=equation_format_resolved,
                                target_language=target_language,
                                renderer_type="reportlab",  # Use ReportLab renderer
                            )
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
        block_text_map: Dict[int, str] = {}
        block_text_sequences = defaultdict(list) if is_deep_split_enabled else None
        layout_chunk_block_texts: List[List[str]] = task_state.get("layout_chunk_block_texts") or []
        
        # Build block index to type mapping and original texts for hints
        layout_block_original_texts: Dict[int, str] = {}
        block_index_to_type: Dict[int, str] = {}
        for block in layout_doc.iter_blocks():
            if block.index is not None:
                layout_block_original_texts[block.index] = (block.text or "").strip()
                block_index_to_type[block.index] = block.type
        
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
            indices = seg.get("layout_block_indices") or []
            if not indices:
                continue
            
            # Extract text from specified field
            text = seg.get(text_field) or ""
            if not text:
                continue
            
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
                if block_type == "image":
                    # Keep image blocks for potential caption mapping
                    image_block_indices.append(block_index_int)
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
                block_hints: List[str] = []
                if seg_index < len(layout_chunk_block_texts):
                    candidate_hints = layout_chunk_block_texts[seg_index] or []
                    if len(candidate_hints) == expected_blocks:
                        block_hints = candidate_hints
                if len(block_hints) != expected_blocks:
                    block_hints = [(layout_block_original_texts.get(idx) or "") for idx in text_block_indices]
                
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
        
        return block_text_map

