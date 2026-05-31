# SPDX-FileCopyrightText: 2026 Zamphersssss
# SPDX-License-Identifier: MPL-2.0

"""DOCX document rebuild from translation segments."""

import ast
import base64
import io
import os
import re
from pathlib import Path
from typing import Optional, Dict, Any, List, Tuple

from logger import unified_logger as logger
from logger.logger import LogModule
from utils.translation_segments import get_translation_segments

# Support placeholder IDs with path characters (e.g., "mobi7/Images/image00044.jpeg")
# Characters allowed: letters, numbers, underscore, dot, slash, hyphen
PLACEHOLDER_PATTERN = re.compile(r"<ph-([a-zA-Z0-9_./-]+)>")


def _apply_run_style(run, style, font_name, font_size, is_bold, is_italic):
    if style:
        run.style = style
    if font_name:
        run.font.name = font_name
    if font_size:
        run.font.size = font_size
    if is_bold is not None:
        run.bold = is_bold
    if is_italic is not None:
        run.italic = is_italic


def _add_image_to_paragraph(paragraph, image_entry, style, font_name, font_size, is_bold, is_italic) -> bool:
    data_uri = image_entry.get("data")
    if not data_uri or "," not in data_uri or not data_uri.startswith("data:image/"):
        return False

    try:
        base64_data = data_uri.split(",", 1)[1]
        image_bytes = base64.b64decode(base64_data)
    except Exception as e:
        logger.warning(LogModule.RESTOR,f"[DOCX-IMAGE] Failed to decode base64 for placeholder '{image_entry.get('alt')}', error: {e}")
        return False

    alt_text = image_entry.get("alt", "")
    is_formula_or_table = "equation" in alt_text.lower() or "table" in alt_text.lower()
    
    # Determine max width based on image type
    # Formula and table images: smaller max width (4 inches) to match text size
    # Regular images: larger max width (6 inches)
    try:
        from docx.shared import Inches
        from PIL import Image
        
        # Get image dimensions to maintain aspect ratio
        image_stream = io.BytesIO(image_bytes)
        pil_image = Image.open(image_stream)
        original_width, original_height = pil_image.size
        
        # Set max width based on image type
        max_width_inches = 4.0 if is_formula_or_table else 6.0
        max_width_pixels = max_width_inches * 96  # Assume 96 DPI for conversion
        
        # Calculate width and height maintaining aspect ratio
        if original_width > max_width_pixels:
            width_inches = max_width_inches
            height_inches = (original_height / original_width) * max_width_inches
        else:
            # Use original size if smaller than max
            width_inches = original_width / 96.0
            height_inches = original_height / 96.0
        
        # Reset stream for add_picture
        image_stream.seek(0)
        run = paragraph.add_run()
        run.add_picture(image_stream, width=Inches(width_inches))
    except ImportError:
        # Fallback if PIL is not available: use default size
        logger.warning(LogModule.RESTOR,"[DOCX-IMAGE] PIL not available, using default image size")
        image_stream = io.BytesIO(image_bytes)
        run = paragraph.add_run()
        try:
            from docx.shared import Inches
            # Use smaller default size for formula/table images
            max_width = Inches(4.0) if is_formula_or_table else Inches(6.0)
            run.add_picture(image_stream, width=max_width)
        except Exception as e:
            logger.warning(LogModule.RESTOR,f"[DOCX-IMAGE] add_picture failed for placeholder '{alt_text}', error: {e}")
            return False
    except Exception as e:
        logger.warning(LogModule.RESTOR,f"[DOCX-IMAGE] Failed to process image size for placeholder '{alt_text}': {e}, using default size")
        # Fallback: use default size
        image_stream = io.BytesIO(image_bytes)
        run = paragraph.add_run()
        try:
            from docx.shared import Inches
            max_width = Inches(4.0) if is_formula_or_table else Inches(6.0)
            run.add_picture(image_stream, width=max_width)
        except Exception as e2:
            logger.warning(LogModule.RESTOR,f"[DOCX-IMAGE] add_picture failed for placeholder '{alt_text}', error: {e2}")
            return False

    if alt_text:
        caption_run = paragraph.add_run(f" ({alt_text})")
        _apply_run_style(caption_run, style, font_name, font_size, is_bold, is_italic)
    logger.info(LogModule.TRANS, f"[DOCX-IMAGE] Inserted image placeholder='{alt_text}' size={len(image_bytes)} bytes, width={width_inches if 'width_inches' in locals() else 'default'} inches")
    return True


def _apply_translation_to_run_range(
    paragraph,
    target_text: str,
    run_start: int,
    run_end: Optional[int],
) -> bool:
    """
    Write translated text only into runs [run_start, run_end), matching DocxTranslator._after_translate
    (proportional split across multiple runs). Preserves fonts/formatting on runs outside the range.

    Returns False if placeholders are present (caller should fall back to full-paragraph replace)
    or if the slice has no replaceable text runs.
    """
    if PLACEHOLDER_PATTERN.search(target_text or ""):
        return False

    from utils.docx_utils import is_image_run
    from translator.ai_translator.docx_translator import preserve_page_breaks_in_run

    para_runs = list(paragraph.runs)
    if not para_runs:
        return False

    re = len(para_runs) if run_end is None else min(int(run_end), len(para_runs))
    rs = max(0, min(int(run_start), len(para_runs)))
    if rs >= re:
        return False

    text_runs = []
    for ri in range(rs, re):
        r = para_runs[ri]
        if not is_image_run(r):
            text_runs.append(r)

    if not text_runs:
        return False

    ft = target_text or ""

    if len(text_runs) == 1:
        preserve_page_breaks_in_run(text_runs[0], ft)
        return True

    original_lengths = [len(run.text or "") for run in text_runs]
    total_o = sum(original_lengths)
    if total_o == 0:
        preserve_page_breaks_in_run(text_runs[0], ft)
        return True

    cur = 0
    for idx, run in enumerate(text_runs):
        proportion = original_lengths[idx] / total_o
        piece_len = int(len(ft) * proportion)
        if idx == len(text_runs) - 1:
            chunk = ft[cur:]
        else:
            chunk = ft[cur : cur + piece_len]
            cur += piece_len
        preserve_page_breaks_in_run(run, chunk)
    return True


def _insert_text_and_images(paragraph, text: str, image_data_map: Dict[str, Dict[str, str]], style, font_name, font_size, is_bold, is_italic):
    if not PLACEHOLDER_PATTERN.search(text or ""):
        if text:
            run = paragraph.add_run(text)
            _apply_run_style(run, style, font_name, font_size, is_bold, is_italic)
        return

    last_pos = 0
    for match in PLACEHOLDER_PATTERN.finditer(text):
        if match.start() > last_pos:
            preceding = text[last_pos:match.start()]
            if preceding:
                run = paragraph.add_run(preceding)
                _apply_run_style(run, style, font_name, font_size, is_bold, is_italic)

        placeholder_id = match.group(1)
        image_entry = image_data_map.get(placeholder_id)
        if not image_entry or not _add_image_to_paragraph(paragraph, image_entry, style, font_name, font_size, is_bold, is_italic):
            fallback_run = paragraph.add_run(match.group(0))
            _apply_run_style(fallback_run, style, font_name, font_size, is_bold, is_italic)

        last_pos = match.end()

    if last_pos < len(text):
        remaining = text[last_pos:]
        if remaining:
            run = paragraph.add_run(remaining)
            _apply_run_style(run, style, font_name, font_size, is_bold, is_italic)


def rebuild_docx_document_from_segments(
    task_state: Dict[str, Any],
    translated_docx_document,
    bilingual_export: bool = False,
    target_first: bool = False,
    source_text_italic: bool = True,
    source_text_color: str = "gray",
    target_text_italic: bool = False,
    target_text_color: Optional[str] = None,
) -> Optional[Any]:
    """
    Rebuild DOCX Document from revised translation segments.
    
    This function modifies the translated DOCX document by updating paragraph
    texts based on revised segments, preserving styles and structure.
    
    Args:
        task_state: Task state dictionary containing translation_segments
        translated_docx_document: Translated DOCX Document object from workflow
        bilingual_export: If True, insert source text paragraphs alongside translations.
        target_first: If True and bilingual_export is True, place source before target paragraph.
        
    Returns:
        Modified DOCX Document, or None if rebuilding failed
    """
    from ir.document import Document
    
    segments_data = get_translation_segments(None, task_state)
    if not segments_data:
        logger.warning(LogModule.RESTOR,"No translation segments found for rebuilding DOCX document")
        return None
    
    segments = segments_data.get("segments", [])
    if not segments:
        logger.warning(LogModule.RESTOR,"Empty segments list, cannot rebuild DOCX document")
        return None
    
    # Sort segments by index
    segments.sort(key=lambda x: x.get("segment_index", 0))
    
    # Initialize table1_segments for trace logging (will be populated later)
    table1_segments = []
    
    try:
        # Import python-docx for DOCX manipulation
        from docx import Document as DocxDocument
        from docx.text.paragraph import Paragraph
        from docx.text.run import Run
        
        # Get the DOCX content bytes
        docx_bytes = translated_docx_document.content
        logger.info(LogModule.TRANS, f"[DOCX-IMAGE] Rebuild start: doc length={len(docx_bytes)} bytes")
        
        # Load DOCX from bytes
        docx_io = io.BytesIO(docx_bytes)
        doc = DocxDocument(docx_io)
        
        image_data_map = (
            task_state.get("translation_image_data_map")
            or task_state.get("image_data_map")
            or {}
        )

        # Import helper function for TOC detection
        from utils.docx_utils import paragraph_has_toc_field
        
        # Build a mapping from segment index to (target_text, segment_info)
        segment_data_map = {}
        modified_segments = []
        # Note: table1_segments is already initialized at function start for trace logging
        
        for segment in segments:
            segment_index = segment.get("segment_index", -1)
            # CRITICAL: Use the same priority as frontend: modified_text ?? target_text ?? ''
            # Frontend uses: segment['modified_text'] ?? segment['target_text'] ?? ''
            # We must use the same logic to ensure consistency
            modified_text = segment.get("modified_text")
            target_text_raw = segment.get("target_text", "")
            # Use modified_text if available (not None), otherwise use target_text (same as frontend)
            target_text = modified_text if modified_text is not None else target_text_raw
            source_text = segment.get("source_text", "")
            
            # CRITICAL: Log if target_text is same as source_text for table cells (potential issue)
            segment_info = segment.get("segment_info", {})
            is_table_cell = segment_info.get("is_table_cell", False)
            if is_table_cell and target_text and source_text and target_text.strip() == source_text.strip():
                table_idx = segment_info.get("table_index")
                row_idx = segment_info.get("row_index")
                cell_idx = segment_info.get("cell_index")
                logger.warning(LogModule.RESTOR,
                    f"[DOCX-REBUILD] Table cell segment {segment_index} (Table {table_idx}, Row {row_idx}, Cell {cell_idx}): "
                    f"target_text equals source_text! This may indicate translation was not saved correctly. "
                    f"source='{source_text[:100]}...', target='{target_text[:100]}...', "
                    f"modified_text={'present' if modified_text is not None else 'None'}"
                )
            # CRITICAL: Log table cell segments with target_text for debugging (especially for Table 1)
            if is_table_cell:
                table_idx = segment_info.get("table_index")
                row_idx = segment_info.get("row_index")
                cell_idx = segment_info.get("cell_index")
                # Log all table cell segments for Table 1 (table_index=0) to diagnose export issues
                if table_idx == 0:
                    logger.info(
                        LogModule.RESTOR,
                        f"[DOCX-REBUILD-TABLE1] Segment {segment_index} (Table {table_idx}, Row {row_idx}, Cell {cell_idx}): "
                        f"source='{source_text[:80] if source_text else '(empty)'}...', "
                        f"target='{target_text[:80] if target_text else '(empty)'}...', "
                        f"modified_text={'present' if modified_text is not None else 'None'}",
                    )
            is_modified = segment.get("modified", False) or segment.get("retry_count", 0) > 0
            is_failed = segment.get("is_failed", False)
            failure_reason = segment.get("failure_reason")
            is_excluded = segment.get("is_excluded", False)
            exclusion_reason = segment.get("exclusion_reason")
            
            # CRITICAL: Check if segment is cleared (status="cleared" or empty target_text with modified=True)
            # Cleared segments should be exported as empty string
            is_cleared = segment.get("status") == "cleared" or (not target_text and is_modified and segment.get("target_length", -1) == 0)
            
            # CRITICAL: Even if segment is marked as failed or excluded, if target_text exists and differs from source_text,
            # use the target_text. This ensures correct translations are not lost due to incorrect failure/exclusion detection.
            # This is especially important for language_match exclusions where translation might have been done before exclusion.
            # Only use source_text if target_text is empty or same as source_text.
            if (is_failed or is_excluded) and target_text and target_text.strip() != source_text.strip():
                logger.warning(LogModule.RESTOR,
                    f"[DOCX-REBUILD] Segment {segment_index} marked as {'FAILED' if is_failed else 'EXCLUDED'} "
                    f"(reason={failure_reason or exclusion_reason}), "
                    f"but target_text differs from source_text. Using target_text for export: "
                    f"source='{source_text[:50] if source_text else '(empty)'}...', "
                    f"target='{target_text[:50]}...'"
                )
            
            # CRITICAL: For table cells, ensure we always use target_text if it exists and differs from source_text,
            # even if it's empty or marked as failed. This is especially important for table cells where
            # translations might be incorrectly marked as failed but are actually correct.
            segment_info = segment.get("segment_info", {})
            is_table_cell = segment_info.get("is_table_cell", False)
            
            # For table cells, log detailed information about target_text availability
            if is_table_cell:
                table_idx = segment_info.get("table_index")
                row_idx = segment_info.get("row_index")
                cell_idx = segment_info.get("cell_index")
                logger.debug(LogModule.RESTOR,
                    f"[DOCX-REBUILD-TABLE] Processing table cell segment {segment_index}: "
                    f"Table {table_idx}, Row {row_idx}, Cell {cell_idx}, "
                    f"source_text='{source_text[:50] if source_text else '(empty)'}...', "
                    f"target_text='{target_text[:50] if target_text else '(empty)'}...', "
                    f"is_failed={is_failed}, is_excluded={is_excluded}, "
                    f"target_differs_from_source={target_text.strip() != source_text.strip() if target_text and source_text else False}"
                )

            if segment_index >= 0:
                # CRITICAL: Include segment in segment_data_map if:
                # 1. It has target_text (even if same as source_text - frontend shows it, so we should export it)
                # 2. It is cleared (should be exported as empty string)
                # 3. For table cells: always include to ensure we can match and update (frontend shows all table cells)
                # 
                # The key principle: if frontend shows a translation (even if it's the same as source),
                # we should include it in segment_data_map so we can match and update it.
                # The update logic will determine whether to actually update based on current_element_text.
                
                # Determine final_target_text to use
                final_target_text = target_text if not is_cleared else ""
                
                # CRITICAL: Include segment if:
                # - It has target_text (even if same as source - frontend shows it)
                # - It is cleared (should be exported as empty)
                # - It's a table cell (always include for matching)
                should_include = False
                if final_target_text or is_cleared:
                    # Has target_text or is cleared - include it
                    should_include = True
                elif is_table_cell:
                    # For table cells, always include even if target_text is empty
                    # This ensures we can match and update table cells
                    should_include = True
                
                if should_include:
                    segment_data_map[segment_index] = {
                        "target_text": final_target_text,
                        "source_text": source_text,  # Store source_text for logging
                        "segment_info": segment_info,
                        "is_excluded": is_excluded,
                        "is_failed": is_failed,
                    }
                    if is_modified:
                        modified_segments.append(segment_index)
                    
                    
                    # Collect Table1 (table_index=0) segments for trace logging
                    if is_table_cell:
                        table_idx = segment_info.get("table_index")
                        if table_idx == 0:  # Table1
                            table1_segments.append({
                                "segment_index": segment_index,
                                "row_index": segment_info.get("row_index"),
                                "cell_index": segment_info.get("cell_index"),
                                "source_text": source_text,
                                "target_text": final_target_text,
                                "modified_text": modified_text if modified_text is not None else None,
                            })
        
        # CRITICAL: Log Table1 segments with trace level for debugging
        if table1_segments:
            # Sort by row_index and cell_index for better readability
            table1_segments.sort(key=lambda x: (x["row_index"], x["cell_index"]))
            logger.trace(
                LogModule.RESTOR,
                f"[DOCX-REBUILD-TABLE1] Table1 (table_index=0) segments collected for export: {len(table1_segments)} segments",
            )
            for seg in table1_segments:
                logger.trace(
                    LogModule.RESTOR,
                    f"[DOCX-REBUILD-TABLE1] Segment {seg['segment_index']} - "
                    f"Row {seg['row_index']}, Cell {seg['cell_index']}: "
                    f"source='{seg['source_text'][:100] if seg['source_text'] else '(empty)'}...', "
                    f"target='{seg['target_text'][:100] if seg['target_text'] else '(empty)'}...', "
                    f"modified_text={'present' if seg['modified_text'] is not None else 'None'}",
                )
        else:
            logger.trace(
                LogModule.RESTOR,
                "[DOCX-REBUILD-TABLE1] No Table1 segments found in segment_data_map",
            )
        
        if not segment_data_map:
            logger.warning(LogModule.RESTOR,"No valid segment indices found")
            return None
        
        # Build para_index_map similar to DocxTranslator._pre_translate_with_metadata
        # This maps (is_table_cell, table_idx, row_idx, cell_idx, para_local_idx) -> paragraph
        para_index_map = {}
        para_count = 0
        
        # Map document body paragraphs (non-TOC)
        for para in doc.paragraphs:
            if not paragraph_has_toc_field(para):
                para_key = (False, None, None, None, para_count)
                para_index_map[para_key] = para
                para_count += 1
        
        # OPTIMIZATION: Pre-compute and cache merged regions for all tables
        # This avoids recalculating them multiple times during para_index counting
        from utils.table_utils import (
            get_all_merged_regions_docx,
            is_merged_cell_start_at_position_docx,
            is_cell_in_merged_region_docx,
        )
        
        # Cache merged regions for all tables
        table_merged_regions_cache: Dict[int, List[Tuple[int, int, int, int]]] = {}
        for table_idx, table in enumerate(doc.tables):
            table_merged_regions_cache[table_idx] = get_all_merged_regions_docx(table)
        
        # Helper function to iterate over table cells, skipping merged cell continuation parts
        def iterate_table_cells(table, table_idx: int, merged_regions: List[Tuple[int, int, int, int]]):
            """
            Iterate over table cells, skipping merged cell continuation parts.
            Yields (row_idx, cell_idx, cell) tuples for cells that should be processed.
            """
            processed_cells: set = set()
            
            for row_idx, row in enumerate(table.rows):
                for cell_idx, cell in enumerate(row.cells):
                    # Skip if already processed (part of a merged region)
                    if (row_idx, cell_idx) in processed_cells:
                        continue
                    
                    # Check if this cell is part of a merged region
                    is_in_merged, merge_range = is_cell_in_merged_region_docx(
                        table, row_idx, cell_idx, merged_regions
                    )
                    
                    if is_in_merged and merge_range is not None:
                        # Mark all cells in this merged region as processed
                        start_row, start_col, end_row, end_col = merge_range
                        for r in range(start_row, end_row + 1):
                            for c in range(start_col, end_col + 1):
                                processed_cells.add((r, c))
                        
                        # Only process if this is the start of the merged region
                        is_start = is_merged_cell_start_at_position_docx(
                            table, row_idx, cell_idx, merged_regions
                        )
                        if not is_start:
                            # Skip continuation cells (they are part of a merged region but not the start)
                            continue
                    
                    yield (row_idx, cell_idx, cell)
        
        # Map table cell paragraphs using the helper function
        for table_idx, table in enumerate(doc.tables):
            merged_regions = table_merged_regions_cache[table_idx]
            
            for row_idx, cell_idx, cell in iterate_table_cells(table, table_idx, merged_regions):
                # Map paragraphs in this cell (only if it's a start cell or not merged)
                cell_para_count = 0
                for para in cell.paragraphs:
                    if not paragraph_has_toc_field(para):
                        para_key = (True, table_idx, row_idx, cell_idx, cell_para_count)
                        para_index_map[para_key] = para
                        cell_para_count += 1
        
        # OPTIMIZATION: Helper function to calculate para_index for a given table cell position
        # This avoids recalculating merged regions and counting paragraphs multiple times
        def calculate_para_index_for_cell(
            target_table_idx: int,
            target_row_idx: int,
            target_cell_idx: int
        ) -> int:
            """
            Calculate the global para_index for a given table cell position.
            This matches the extraction logic: count all non-TOC paragraphs before this cell,
            skipping merged cell continuation parts.
            
            Returns:
                The global para_index (0-based) for the first paragraph in the target cell.
            """
            para_count = 0
            
            # Count document body paragraphs
            for p in doc.paragraphs:
                if not paragraph_has_toc_field(p):
                    para_count += 1
            
            # Count paragraphs in tables before target table
            for t_idx in range(target_table_idx):
                table_before = doc.tables[t_idx]
                merged_regions_before = table_merged_regions_cache[t_idx]
                
                for row_idx, cell_idx, cell in iterate_table_cells(table_before, t_idx, merged_regions_before):
                    for p in cell.paragraphs:
                        if not paragraph_has_toc_field(p):
                            para_count += 1
            
            # Count paragraphs in current table before target cell
            if target_table_idx < len(doc.tables):
                table = doc.tables[target_table_idx]
                merged_regions = table_merged_regions_cache[target_table_idx]
                processed_cells: set = set()
                
                # Count rows before target row
                for r_idx in range(target_row_idx):
                    for c_idx in range(len(table.rows[r_idx].cells)):
                        # Skip if already processed (part of a merged region)
                        if (r_idx, c_idx) in processed_cells:
                            continue
                        
                        # Check if this cell is part of a merged region
                        is_in_merged, merge_range = is_cell_in_merged_region_docx(
                            table, r_idx, c_idx, merged_regions
                        )
                        
                        if is_in_merged and merge_range is not None:
                            # Mark all cells in this merged region as processed
                            start_row, start_col, end_row, end_col = merge_range
                            for r_merged in range(start_row, end_row + 1):
                                for c_merged in range(start_col, end_col + 1):
                                    processed_cells.add((r_merged, c_merged))
                            
                            # Only process if this is the start of the merged region
                            is_start = is_merged_cell_start_at_position_docx(
                                table, r_idx, c_idx, merged_regions
                            )
                            if not is_start:
                                continue
                        
                        # Count paragraphs in this cell
                        for p in table.rows[r_idx].cells[c_idx].paragraphs:
                            if not paragraph_has_toc_field(p):
                                para_count += 1
                
                # Count cells in target row before target cell
                for c_idx in range(target_cell_idx):
                    # Skip if already processed (part of a merged region)
                    if (target_row_idx, c_idx) in processed_cells:
                        continue
                    
                    # Check if this cell is part of a merged region
                    is_in_merged, merge_range = is_cell_in_merged_region_docx(
                        table, target_row_idx, c_idx, merged_regions
                    )
                    
                    if is_in_merged and merge_range is not None:
                        # Mark all cells in this merged region as processed
                        start_row, start_col, end_row, end_col = merge_range
                        for r_merged in range(start_row, end_row + 1):
                            for c_merged in range(start_col, end_col + 1):
                                processed_cells.add((r_merged, c_merged))
                        
                        # Only process if this is the start of the merged region
                        is_start = is_merged_cell_start_at_position_docx(
                            table, target_row_idx, c_idx, merged_regions
                        )
                        if not is_start:
                            continue
                    
                    # Count paragraphs in this cell
                    for p in table.rows[target_row_idx].cells[c_idx].paragraphs:
                        if not paragraph_has_toc_field(p):
                            para_count += 1
            
            return para_count
        
        # Deep split yields multiple segments per paragraph; process in document order so run-range
        # edits compose predictably (para_index, then run_start_index).
        rebuild_segments_sorted = sorted(
            segment_data_map.items(),
            key=lambda kv: (
                kv[1]["segment_info"].get("para_index") or 0,
                kv[1]["segment_info"].get("run_start_index") or 0,
                kv[0],
            ),
        )

        # Update elements with revised text using segment_info for precise location
        updated_count = 0
        skipped_count = 0
        
        for segment_index, segment_data in rebuild_segments_sorted:
            target_text = segment_data["target_text"]
            source_text = segment_data.get("source_text", "")
            seg_info = segment_data["segment_info"]
            
            # Get original segment for additional metadata (is_failed, etc.)
            original_segment = None
            for seg in segments:
                if seg.get("segment_index") == segment_index:
                    original_segment = seg
                    break
            
            # CRITICAL: Ensure we use the same logic as frontend for getting target_text
            # Frontend uses: modified_text ?? target_text ?? ''
            # We should do the same to ensure consistency
            # If segment_data_map has empty target_text but original_segment has valid translation, use it
            if original_segment:
                # Get modified_text and target_text from original_segment (same priority as frontend)
                original_modified = original_segment.get("modified_text")
                original_target = original_segment.get("target_text", "")
                # Use modified_text if available, otherwise use target_text (same as frontend)
                original_final_target = original_modified if original_modified is not None else original_target
                original_source = original_segment.get("source_text", "")
                
                # CRITICAL: If target_text from segment_data_map is empty or same as source_text,
                # but original_segment has a valid translation that differs from source_text, use it.
                # This ensures we use the same data that frontend sees.
                if (not target_text or target_text.strip() == source_text.strip()) and original_final_target and original_final_target.strip() != original_source.strip():
                    target_text = original_final_target
                    logger.info(
                        LogModule.RESTOR,
                        f"[DOCX-REBUILD] Segment {segment_index}: "
                        f"target_text was empty or same as source in segment_data_map, but found valid translation in original_segment. "
                        f"Using original_final_target: '{original_final_target[:50]}...' (source: '{original_source[:50]}...')",
                    )
                # Also update source_text if it's different from what we have
                if original_source and original_source.strip() != source_text.strip():
                    source_text = original_source
            
            if not seg_info:
                # Segment info should always be available after refactoring
                # If not available, this is an error condition
                logger.error(LogModule.RESTOR,
                    f"[DOCX-REBUILD] Segment {segment_index} has no segment_info. "
                    "This should not happen after refactoring. Extract phase should always generate segment_info."
                )
                continue
            
            # Use segment_info for precise location
            para_index = seg_info.get('para_index')
            is_table_cell = seg_info.get('is_table_cell', False)
            table_idx = seg_info.get('table_index')
            row_idx = seg_info.get('row_index')
            cell_idx = seg_info.get('cell_index')
            run_start = seg_info.get('run_start_index', 0)
            run_end = seg_info.get('run_end_index')
            
            element = None
            cell_local_idx_hint = seg_info.get("cell_local_idx")
            if (
                is_table_cell
                and table_idx is not None
                and row_idx is not None
                and cell_idx is not None
                and cell_local_idx_hint is not None
            ):
                hint_key = (True, table_idx, row_idx, cell_idx, cell_local_idx_hint)
                element = para_index_map.get(hint_key)

            if element is None and is_table_cell and table_idx is not None and row_idx is not None and cell_idx is not None:
                # For table cells, need to find the correct cell-local para index
                if table_idx < len(doc.tables):
                    table = doc.tables[table_idx]
                    if row_idx < len(table.rows) and cell_idx < len(table.rows[row_idx].cells):
                        cell = table.rows[row_idx].cells[cell_idx]
                        
                        # Log table cell content (source and target text) with detailed info
                        # Get is_failed from the original segment (need to look it up)
                        is_failed_log = original_segment.get("is_failed", False) if original_segment else False
                        logger.info(
                            LogModule.RESTOR,
                            f"[DOCX-REBUILD-TABLE] Table {table_idx}, Row {row_idx}, Cell {cell_idx}, Segment {segment_index}: "
                            f"source_text='{source_text[:100] if source_text else '(empty)'}...', "
                            f"target_text='{target_text[:100] if target_text else '(empty)'}...', "
                            f"para_index={para_index}, is_failed={is_failed_log}",
                        )
                        
                        # OPTIMIZATION: Use unified function to calculate para_index
                        # This avoids recalculating merged regions and counting paragraphs multiple times
                        body_para_count = calculate_para_index_for_cell(table_idx, row_idx, cell_idx)
                        
                        # Find the matching paragraph in the cell
                        # CRITICAL: Use the same logic as DocxTranslator._pre_translate_with_metadata
                        # We need to match the global para_index by counting paragraphs in the same order
                        # as they were counted during extraction
                        cell_local_idx = 0
                        found_para = False
                        cell_para_count_before_search = body_para_count
                        
                        for p in cell.paragraphs:
                            if not paragraph_has_toc_field(p):
                                if body_para_count == para_index:
                                    para_key = (True, table_idx, row_idx, cell_idx, cell_local_idx)
                                    element = para_index_map.get(para_key)
                                    if element:
                                        found_para = True
                                        logger.info(
                                            LogModule.RESTOR,
                                            f"[DOCX-REBUILD] Found element for segment {segment_index} at "
                                            f"Table {table_idx}, Row {row_idx}, Cell {cell_idx}, "
                                            f"cell_local_idx={cell_local_idx}, para_index={para_index}, "
                                            f"body_para_count={body_para_count}",
                                        )
                                    break
                                body_para_count += 1
                                cell_local_idx += 1
                        
                        if not found_para and element is None:
                            # Try alternative: use cell_local_idx directly from para_index_map
                            # Sometimes the para_index calculation might be off, so try all cell paragraphs
                            logger.warning(LogModule.RESTOR,
                                f"[DOCX-REBUILD] Could not find element using para_index={para_index} for "
                                f"segment {segment_index} at Table {table_idx}, Row {row_idx}, Cell {cell_idx}. "
                                f"source_text='{source_text[:100] if source_text else '(empty)'}...', "
                                f"target_text='{target_text[:100] if target_text else '(empty)'}...', "
                                f"body_para_count={body_para_count}, cell has {len(cell.paragraphs)} paragraphs. "
                                f"Trying alternative matching..."
                            )
                            # Try matching by text content as fallback
                            # CRITICAL: Improve text matching to handle cases where para_index is incorrect
                            # For table cells with multiple paragraphs, we need to match by content similarity
                            source_stripped = source_text.strip() if source_text else ""
                            best_match = None
                            best_match_score = 0
                            
                            for cell_local_idx_alt in range(len(cell.paragraphs)):
                                para_alt = cell.paragraphs[cell_local_idx_alt]
                                if not paragraph_has_toc_field(para_alt):
                                    para_key_alt = (True, table_idx, row_idx, cell_idx, cell_local_idx_alt)
                                    element_alt = para_index_map.get(para_key_alt)
                                    if element_alt and source_stripped:
                                        # Check if this paragraph contains the source text
                                        para_text = element_alt.text.strip()
                                        
                                        # Calculate match score: exact match > contains > partial match
                                        match_score = 0
                                        target_stripped = target_text.strip() if target_text else ""
                                        
                                        if match_score == 0:
                                            # Standard matching logic
                                            if para_text == source_stripped:
                                                match_score = 100  # Exact match
                                            elif source_stripped in para_text:
                                                # Source text is contained in paragraph (common case)
                                                match_score = 80
                                            elif para_text in source_stripped:
                                                # Paragraph is contained in source text (less common)
                                                match_score = 60
                                            # CRITICAL: Also check if paragraph contains target_text (paragraph already translated)
                                            # This is important for cells with mixed translated/untranslated content
                                            elif target_stripped and target_stripped in para_text:
                                                # Paragraph already contains translated text, this is likely the correct match
                                                match_score = 75  # High score for target text in paragraph
                                                logger.info(
                                                    LogModule.RESTOR,
                                                    f"[DOCX-REBUILD] Segment {segment_index} - Paragraph contains target_text (already translated): "
                                                    f"cell_local_idx={cell_local_idx_alt}, para_text='{para_text[:100]}...', "
                                                    f"target_text='{target_stripped[:100]}...'",
                                                )
                                            elif len(source_stripped) > 10:
                                                # For longer texts, check if a significant portion matches
                                                # This handles cases where paragraph might have been partially translated
                                                common_chars = sum(1 for c in source_stripped[:50] if c in para_text[:100])
                                                if common_chars > len(source_stripped[:50]) * 0.5:
                                                    match_score = 40
                                        
                                        if match_score > best_match_score:
                                            best_match_score = match_score
                                            best_match = element_alt
                                            
                                        if match_score >= 80:
                                            element = element_alt
                                            logger.info(
                                                LogModule.RESTOR,
                                                f"[DOCX-REBUILD] Found element for segment {segment_index} using text matching: "
                                                f"Table {table_idx}, Row {row_idx}, Cell {cell_idx}, cell_local_idx={cell_local_idx_alt}, "
                                                f"match_score={match_score}, para_text='{para_text[:80]}...', source_text='{source_stripped[:80]}...'",
                                            )
                                            break
                            
                            # If no high-confidence match found, use best match if score is reasonable
                            if element is None and best_match and best_match_score >= 40:
                                # Find the cell_local_idx for best_match
                                best_match_cell_local_idx = None
                                for cell_local_idx_find in range(len(cell.paragraphs)):
                                    para_find = cell.paragraphs[cell_local_idx_find]
                                    if not paragraph_has_toc_field(para_find):
                                        para_key_find = (True, table_idx, row_idx, cell_idx, cell_local_idx_find)
                                        element_find = para_index_map.get(para_key_find)
                                        if element_find == best_match:
                                            best_match_cell_local_idx = cell_local_idx_find
                                            break
                                
                                if best_match_cell_local_idx is not None:
                                    element = best_match
                                    logger.info(
                                        LogModule.RESTOR,
                                        f"[DOCX-REBUILD] Using best text match for segment {segment_index} (score={best_match_score}): "
                                        f"Table {table_idx}, Row {row_idx}, Cell {cell_idx}, "
                                        f"cell_local_idx={best_match_cell_local_idx}, "
                                        f"para_text='{best_match.text.strip()[:80] if best_match.text else '(empty)'}...', "
                                        f"source_text='{source_stripped[:80]}...'",
                                    )
                            
                            # If still not found, try matching all paragraphs in the cell by text similarity
                            if element is None:
                                logger.warning(LogModule.RESTOR,
                                    f"[DOCX-REBUILD] Text matching failed for segment {segment_index} at "
                                    f"Table {table_idx}, Row {row_idx}, Cell {cell_idx}. "
                                    f"source_text='{source_stripped[:100] if source_stripped else '(empty)'}...', "
                                    f"target_text='{target_text[:100] if target_text else '(empty)'}...', "
                                    f"cell has {len(cell.paragraphs)} paragraphs. "
                                    f"Trying all cell paragraphs as last resort..."
                                )
                                # Last resort: try all paragraphs in the cell
                                # For cells with multiple paragraphs, try to match by position or content
                                # If para_index suggests a specific position, try paragraphs near that position
                                cell_para_count_before = body_para_count
                                estimated_cell_local_idx = max(0, para_index - cell_para_count_before)
                                
                                # First, try paragraphs near the estimated position
                                candidates = []
                                for cell_local_idx_last in range(len(cell.paragraphs)):
                                    para_last = cell.paragraphs[cell_local_idx_last]
                                    if not paragraph_has_toc_field(para_last):
                                        para_key_last = (True, table_idx, row_idx, cell_idx, cell_local_idx_last)
                                        element_last = para_index_map.get(para_key_last)
                                        if element_last and element_last.text.strip():
                                            para_text_last = element_last.text.strip()
                                            # Calculate distance from estimated position
                                            distance = abs(cell_local_idx_last - estimated_cell_local_idx)
                                            candidates.append((element_last, cell_local_idx_last, distance, para_text_last))
                                
                                # Sort by distance, then try to match by content
                                candidates.sort(key=lambda x: x[2])  # Sort by distance
                                
                                for element_last, cell_local_idx_last, distance, para_text_last in candidates:
                                    # If we have source_text, prefer paragraphs that contain it or are similar
                                    if source_stripped:
                                        source_in_para = source_stripped in para_text_last
                                        para_in_source = para_text_last in source_stripped
                                        
                                        if source_in_para or para_in_source:
                                            element = element_last
                                            logger.warning(LogModule.RESTOR,
                                                f"[DOCX-REBUILD] Using fallback paragraph for segment {segment_index} (matched by content): "
                                                f"Table {table_idx}, Row {row_idx}, Cell {cell_idx}, cell_local_idx={cell_local_idx_last}, "
                                                f"para_text='{para_text_last[:80]}...', source_text='{source_stripped[:80]}...'"
                                            )
                                            break
                                    
                                    # If no content match and this is the closest to estimated position, use it
                                    if distance == candidates[0][2] and element is None:
                                        element = element_last
                                        logger.warning(LogModule.RESTOR,
                                            f"[DOCX-REBUILD] Using fallback paragraph for segment {segment_index} (closest to estimated position): "
                                            f"Table {table_idx}, Row {row_idx}, Cell {cell_idx}, cell_local_idx={cell_local_idx_last}, "
                                            f"distance={distance}, para_text='{para_text_last[:80]}...'"
                                        )
                                        break
                                
                                # If still no match, try to find an unmatched paragraph
                                if element is None and candidates:
                                    for candidate_element, candidate_cell_local_idx, candidate_distance, candidate_para_text in candidates:
                                        element = candidate_element
                                        logger.warning(LogModule.RESTOR,
                                            f"[DOCX-REBUILD] Using unmatched paragraph for segment {segment_index} (cell_local_idx={candidate_cell_local_idx}): "
                                            f"Table {table_idx}, Row {row_idx}, Cell {cell_idx}, "
                                            f"para_text='{candidate_para_text[:80]}...'"
                                        )
                                        break
                                    
                                    if element is None:
                                        element = candidates[0][0]
                                        first_cell_local_idx = candidates[0][1]
                                        first_para_text = candidates[0][3]
                                        logger.warning(LogModule.RESTOR,
                                            f"[DOCX-REBUILD] Using first available paragraph for segment {segment_index} as last resort: "
                                            f"Table {table_idx}, Row {row_idx}, Cell {cell_idx}, cell_local_idx={first_cell_local_idx}, "
                                            f"para_text='{first_para_text[:80]}...'"
                                        )
            else:
                # For non-table paragraphs, para_index is the document body paragraph index
                para_key = (False, None, None, None, para_index)
                element = para_index_map.get(para_key)
            
            if element is None:
                logger.error(LogModule.RESTOR,
                    f"[DOCX-REBUILD] ❌ Could not locate element for segment {segment_index}: "
                    f"para_index={para_index}, is_table_cell={is_table_cell}, "
                    f"table_idx={table_idx}, row_idx={row_idx}, cell_idx={cell_idx}, "
                    f"source_text='{source_text[:100] if source_text else '(empty)'}...', "
                    f"target_text='{target_text[:100] if target_text else '(empty)'}...'. "
                    f"Falling back to simple index matching."
                )
                # Fallback to simple index matching
                paragraphs = [p for p in doc.paragraphs if not paragraph_has_toc_field(p) and p.text.strip()]
                table_paragraphs = []
                for table in doc.tables:
                    for row in table.rows:
                        for cell in row.cells:
                            for para in cell.paragraphs:
                                if not paragraph_has_toc_field(para) and para.text.strip():
                                    table_paragraphs.append(para)
                all_text_elements = paragraphs + table_paragraphs
                if segment_index < len(all_text_elements):
                    element = all_text_elements[segment_index]
                    logger.info(LogModule.TRANS, f"[DOCX-REBUILD] Using fallback index matching for segment {segment_index}")
                else:
                    # Last resort: try to find element by text content matching
                    # This is especially important for table cells where para_index might be incorrect
                    if is_table_cell and table_idx is not None and row_idx is not None and cell_idx is not None:
                        logger.warning(LogModule.RESTOR,
                            f"[DOCX-REBUILD] Segment {segment_index} index out of range, "
                            f"trying text-based matching for table cell: Table {table_idx}, Row {row_idx}, Cell {cell_idx}"
                        )
                        # Try to find the cell and match by text content
                        if table_idx < len(doc.tables):
                            table = doc.tables[table_idx]
                            if row_idx < len(table.rows) and cell_idx < len(table.rows[row_idx].cells):
                                cell = table.rows[row_idx].cells[cell_idx]
                                # Try to find paragraph in cell that contains source_text
                                for para in cell.paragraphs:
                                    if not paragraph_has_toc_field(para):
                                        para_text = para.text.strip()
                                        source_stripped = source_text.strip()
                                        if source_stripped and para_text:
                                            # Check if source_text matches or is contained in para_text
                                            if source_stripped == para_text or source_stripped in para_text or para_text in source_stripped:
                                                element = para
                                                logger.info(
                                                    LogModule.RESTOR,
                                                    f"[DOCX-REBUILD] Found element for segment {segment_index} using text-based matching: "
                                                    f"Table {table_idx}, Row {row_idx}, Cell {cell_idx}, "
                                                    f"para_text='{para_text[:50]}...', source_text='{source_stripped[:50]}...'",
                                                )
                                                break
                    if element is None:
                        # CRITICAL: For table cells, try one more time to find the element by direct cell access
                        # This is important because para_index might be incorrect for table cells
                        if is_table_cell and table_idx is not None and row_idx is not None and cell_idx is not None:
                            logger.warning(LogModule.RESTOR,
                                f"[DOCX-REBUILD] Segment {segment_index} at Table {table_idx}, Row {row_idx}, Cell {cell_idx} "
                                f"could not be matched. Trying direct cell access as last resort..."
                            )
                            # Try direct cell access - use the first non-empty paragraph in the cell
                            if table_idx < len(doc.tables):
                                table = doc.tables[table_idx]
                                if row_idx < len(table.rows) and cell_idx < len(table.rows[row_idx].cells):
                                    cell = table.rows[row_idx].cells[cell_idx]
                                    # Use the first paragraph that matches source_text or any non-empty paragraph
                                    for para in cell.paragraphs:
                                        if not paragraph_has_toc_field(para):
                                            para_text = para.text.strip()
                                            if para_text:
                                                # If source_text matches or is contained, use this paragraph
                                                if source_text and source_text.strip():
                                                    source_stripped = source_text.strip()
                                                    if source_stripped == para_text or source_stripped in para_text or para_text in source_stripped:
                                                        element = para
                                                        logger.info(
                                                            LogModule.RESTOR,
                                                            f"[DOCX-REBUILD] Found element for segment {segment_index} using direct cell access: "
                                                            f"Table {table_idx}, Row {row_idx}, Cell {cell_idx}, "
                                                            f"para_text='{para_text[:50]}...', source_text='{source_stripped[:50]}...'",
                                                        )
                                                        break
                                                else:
                                                    # If no source_text, use first non-empty paragraph
                                                    element = para
                                                    logger.info(
                                                        LogModule.RESTOR,
                                                        f"[DOCX-REBUILD] Found element for segment {segment_index} using first non-empty paragraph: "
                                                        f"Table {table_idx}, Row {row_idx}, Cell {cell_idx}, para_text='{para_text[:50]}...'"
                                                    )
                                                    break
                        
                        if element is None:
                            logger.error(LogModule.RESTOR,
                                f"[DOCX-REBUILD] ❌ Could not locate element for segment {segment_index} after all attempts. "
                                f"This segment will be skipped. "
                                f"is_table_cell={is_table_cell}, table_idx={table_idx}, row_idx={row_idx}, cell_idx={cell_idx}, "
                                f"source_text='{source_text[:50] if source_text else '(empty)'}...', "
                                f"target_text='{target_text[:50] if target_text else '(empty)'}...'"
                            )
                            continue
            
            # CRITICAL: Only update if target_text is different from current element text
            # This prevents unnecessary updates and ensures we apply translations even if marked as failed
            current_element_text = element.text.strip() if element.text else ""
            target_text_stripped = target_text.strip() if target_text else ""
            source_text_stripped = source_text.strip() if source_text else ""
            
            # CRITICAL: For table cells, we need to ensure we apply translations correctly.
            # The key principle: if we have a valid target_text that differs from source_text,
            # we MUST update the element to apply the translation.
            is_table_cell_check = seg_info and seg_info.get('is_table_cell')
            should_update = False
            
            if is_table_cell_check:
                table_idx_log = seg_info.get('table_index')
                row_idx_log = seg_info.get('row_index')
                cell_idx_log = seg_info.get('cell_index')
                
                # CRITICAL: Primary rule - if target_text exists and differs from source_text, we should update
                # unless current_element_text already contains the target_text (already translated correctly)
                if target_text_stripped and target_text_stripped != source_text_stripped:
                    # We have a valid translation that differs from source
                    # Check if current text already contains target_text (already translated correctly)
                    if target_text_stripped in current_element_text:
                        # Current text already contains target_text, no update needed
                        should_update = False
                        logger.debug(LogModule.RESTOR,
                            f"[DOCX-REBUILD-TABLE] Segment {segment_index}: Table cell already contains target text, skipping update: "
                            f"Table {table_idx_log}, Row {row_idx_log}, Cell {cell_idx_log}, "
                            f"current='{current_element_text[:80]}...', target='{target_text_stripped[:80]}...'"
                        )
                    elif current_element_text != target_text_stripped:
                        # Current text is different from target, update needed
                        should_update = True
                        logger.info(
                            LogModule.RESTOR,
                            f"[DOCX-REBUILD-TABLE] Segment {segment_index}: Table cell will be updated with translation: "
                            f"Table {table_idx_log}, Row {row_idx_log}, Cell {cell_idx_log}, "
                            f"current='{current_element_text[:80]}...', source='{source_text_stripped[:80]}...', target='{target_text_stripped[:80]}...'"
                        )
                    else:
                        # Current text already matches target_text exactly, no update needed
                        should_update = False
                        logger.debug(LogModule.RESTOR,
                            f"[DOCX-REBUILD-TABLE] Segment {segment_index}: Table cell already has target text (exact match), skipping update: "
                            f"Table {table_idx_log}, Row {row_idx_log}, Cell {cell_idx_log}"
                        )
                else:
                    # No valid translation (target_text is empty or same as source_text)
                    should_update = False
                    logger.debug(LogModule.RESTOR,
                        f"[DOCX-REBUILD-TABLE] Segment {segment_index}: Table cell has no valid translation, skipping update: "
                        f"Table {table_idx_log}, Row {row_idx_log}, Cell {cell_idx_log}, "
                        f"target_text={'empty' if not target_text_stripped else 'same as source'}"
                    )
            else:
                # For non-table cells, use simple comparison
                should_update = target_text_stripped != current_element_text
            
            # CRITICAL: For table cells, log detailed information for debugging
            if is_table_cell_check:
                logger.info(
                    LogModule.RESTOR,
                    f"[DOCX-REBUILD-TABLE] Segment {segment_index} at Table {seg_info.get('table_index')}, "
                    f"Row {seg_info.get('row_index')}, Cell {seg_info.get('cell_index')}: "
                    f"current_element_text='{current_element_text[:100]}...', "
                    f"target_text='{target_text_stripped[:100]}...', "
                    f"source_text='{source_text_stripped[:100] if source_text_stripped else '(empty)'}...', "
                    f"current==source={current_element_text == source_text_stripped}, "
                    f"target!=source={target_text_stripped != source_text_stripped}, "
                    f"target_in_current={target_text_stripped in current_element_text if target_text_stripped else False}, "
                    f"source_in_current={source_text_stripped in current_element_text if source_text_stripped else False}, "
                    f"will_update={should_update}"
                )
            
            # CRITICAL: Log Table1 updates with trace level for debugging
            if is_table_cell_check and seg_info and seg_info.get('table_index') == 0:
                logger.trace(LogModule.RESTOR,
                    f"[DOCX-REBUILD-TABLE1-UPDATE] Segment {segment_index} - "
                    f"Row {seg_info.get('row_index')}, Cell {seg_info.get('cell_index')}: "
                    f"current_element_text='{current_element_text[:100]}...', "
                    f"target_text='{target_text_stripped[:100] if target_text_stripped else '(empty)'}...', "
                    f"source_text='{source_text_stripped[:100] if source_text_stripped else '(empty)'}...', "
                    f"will_update={should_update}",
                )
            
            # Check if update is needed
            if should_update:
                applied_slice = _apply_translation_to_run_range(
                    element, target_text, run_start, run_end
                )
                if not applied_slice:
                    logger.debug(
                        LogModule.RESTOR,
                        f"[DOCX-REBUILD] Run-range apply failed or skipped (placeholders/empty slice); "
                        f"fallback full-paragraph replace segment={segment_index} "
                        f"run_start={run_start} run_end={run_end}",
                    )
                    runs = element.runs
                    if runs:
                        first_run = runs[0]
                        style = first_run.style
                        font_name = first_run.font.name
                        font_size = first_run.font.size
                        is_bold = first_run.bold
                        is_italic = first_run.italic
                        element.clear()
                        _insert_text_and_images(
                            element,
                            target_text,
                            image_data_map,
                            style,
                            font_name,
                            font_size,
                            is_bold,
                            is_italic,
                        )
                    else:
                        _insert_text_and_images(
                            element,
                            target_text,
                            image_data_map,
                            None,
                            None,
                            None,
                            None,
                            None,
                        )
                
                updated_count += 1
                
                # Log update for debugging (especially for table cells)
                if seg_info and seg_info.get('is_table_cell'):
                    logger.info(
                        LogModule.RESTOR,
                        f"[DOCX-REBUILD] ✅ Updated segment {segment_index} at Table {seg_info.get('table_index')}, "
                        f"Row {seg_info.get('row_index')}, Cell {seg_info.get('cell_index')}: "
                        f"'{current_element_text[:50]}...' -> '{target_text_stripped[:50]}...'"
                    )
                    # CRITICAL: Log Table1 updates with trace level for debugging
                    if seg_info.get('table_index') == 0:
                        logger.trace(
                            LogModule.RESTOR,
                            f"[DOCX-REBUILD-TABLE1-UPDATED] Segment {segment_index} - "
                            f"Row {seg_info.get('row_index')}, Cell {seg_info.get('cell_index')}: "
                            f"✅ Successfully updated: '{current_element_text[:100]}...' -> '{target_text_stripped[:100]}...'",
                        )
            else:
                # No update needed - target_text matches current element text
                skipped_count += 1
                if seg_info and seg_info.get('is_table_cell'):
                    # For table cells, log more details about why update was skipped
                    logger.info(
                        LogModule.RESTOR,
                        f"[DOCX-REBUILD-TABLE] Skipped segment {segment_index} at Table {seg_info.get('table_index')}, "
                        f"Row {seg_info.get('row_index')}, Cell {seg_info.get('cell_index')}: "
                        f"target_text='{target_text_stripped[:50] if target_text_stripped else '(empty)'}...', "
                        f"current_element_text='{current_element_text[:50]}...', "
                        f"source_text='{source_text_stripped[:50] if source_text_stripped else '(empty)'}...', "
                        f"target==current={target_text_stripped == current_element_text}, "
                        f"target==source={target_text_stripped == source_text_stripped}"
                    )
                else:
                    logger.debug(LogModule.RESTOR,
                        f"[DOCX-REBUILD] Segment {segment_index} skipped (target_text matches current element text): "
                        f"'{target_text_stripped[:50] if target_text_stripped else '(empty)'}...'"
                    )
        
        if updated_count == 0 and not bilingual_export:
            logger.warning(LogModule.RESTOR,"No text elements were updated in DOCX document")
            return None
        
        # Bilingual export: insert source text paragraphs alongside translations
        if bilingual_export:
            extras_original = task_state.get("docx_extras_original", {})
            logger.info(
                LogModule.RESTOR,
                f"[BILINGUAL-DOCX] extras_original from task_state: keys={list(extras_original.keys()) if extras_original else 'empty'}"
            )
            if extras_original and "textboxes_sdts" in extras_original:
                tb_items = extras_original["textboxes_sdts"]
                tb_debug = []
                for item in tb_items:
                    if isinstance(item, (list, tuple)) and len(item) >= 2:
                        k = item[0]
                        tb_debug.append(f"type={type(k).__name__},val={k}")
                    else:
                        tb_debug.append(f"bad_item:type={type(item).__name__},val={item!r}")
                logger.info(
                    LogModule.RESTOR,
                    f"[BILINGUAL-DOCX] textboxes_sdts has {len(tb_items)} items: {tb_debug}"
                )
            _insert_bilingual_source_paragraphs(
                doc,
                segment_data_map,
                para_index_map,
                target_first=target_first,
                extras_original=extras_original,
                source_text_italic=source_text_italic,
                source_text_color=source_text_color,
                target_text_italic=target_text_italic,
                target_text_color=target_text_color,
            )
        
        # Save modified DOCX back to bytes
        output_io = io.BytesIO()
        doc.save(output_io)
        output_io.seek(0)
        new_bytes = output_io.read()
        
        # Create new Document object with updated content
        new_doc = Document.from_bytes(
            content=new_bytes,
            suffix=translated_docx_document.suffix,
            stem=translated_docx_document.stem
        )
        
        logger.info(
            LogModule.RESTOR,
            f"Rebuilt DOCX Document: updated {updated_count} elements from {len(segments)} segments "
            f"({len(modified_segments)} modified), skipped {skipped_count} (no change needed)"
        )
        return new_doc
        
    except ImportError:
        logger.error(LogModule.RESTOR,"python-docx not available, cannot rebuild DOCX document")
        return None
    except Exception as e:
        import traceback
        tb = traceback.format_exc()
        logger.error(LogModule.RESTOR,f"Failed to rebuild DOCX document: {e}\n{tb}")
        return None


def _normalize_key(k) -> tuple:
    """Convert a key to a canonical tuple form.

    Task state data may go through JSON serialization, which converts
    tuples to lists. This helper ensures we can compare reliably.
    """
    if isinstance(k, (list, tuple)):
        return tuple(_normalize_key(item) for item in k)
    return k


def _insert_bilingual_source_paragraphs(
    doc,
    segment_data_map: Dict[int, Dict[str, Any]],
    para_index_map: Dict[Tuple, Any],
    target_first: bool = False,
    extras_original: Optional[Dict[str, Any]] = None,
    source_text_italic: bool = True,
    source_text_color: str = "gray",
    target_text_italic: bool = False,
    target_text_color: Optional[str] = None,
) -> None:
    """Insert source-text paragraphs next to translated paragraphs for bilingual export.

    Strategy for body / table cells:
      - Skip excluded or failed segments (emit target only).
      - Group remaining segments by para_index.
      - For each paragraph that has at least one translated segment, create a
        new paragraph containing the concatenated source_text of its segments.
      - Insert BEFORE the translated paragraph when target_first=False
        (source first, target after), otherwise AFTER it.
      - Process paragraphs in *descending* para_index order so insertions do
        not shift the positions of paragraphs yet to be processed.

    Strategy for headers/footers / textboxes:
      - Use extras_original saved during translation to obtain source text.
      - Insert a styled source paragraph after (or before) the translated text.
    """
    from docx.text.paragraph import Paragraph
    from docx.shared import RGBColor

    _SOURCE_COLOR_MAP = {
        "gray": RGBColor(0x80, 0x80, 0x80),
        "red": RGBColor(0xFF, 0x00, 0x00),
        "blue": RGBColor(0x00, 0x00, 0xFF),
        "green": RGBColor(0x00, 0x80, 0x00),
        "orange": RGBColor(0xFF, 0xA5, 0x00),
        "black": RGBColor(0x00, 0x00, 0x00),
    }
    _resolved_color = _SOURCE_COLOR_MAP.get(source_text_color) if source_text_color else None

    def _apply_target_style(para: Paragraph) -> None:
        """Apply target-text style (italic/color) to all runs in a paragraph."""
        if not para:
            return
        _target_color = None
        if target_text_color:
            _target_color = _SOURCE_COLOR_MAP.get(target_text_color)
        for run in para.runs:
            if target_text_italic:
                run.italic = True
            if _target_color:
                try:
                    run.font.color.rgb = _target_color
                except Exception:
                    pass

    def _copy_source_format(src_para: Paragraph, dst_para: Paragraph) -> None:
        """Copy font/bold/italic/size from src_para runs to dst_para runs.
        Only overrides color when a non-default color was explicitly chosen.
        """
        for src_run, dst_run in zip(src_para.runs, dst_para.runs):
            try:
                if src_run.font.name:
                    dst_run.font.name = src_run.font.name
                if src_run.bold is not None:
                    dst_run.bold = src_run.bold
                if src_run.font.size:
                    dst_run.font.size = src_run.font.size
                # Preserve italic from original; do not override with source_text_italic
                if src_run.italic is not None:
                    dst_run.italic = src_run.italic
                # Color: if user chose a non-default color, override; else keep original
                if _resolved_color:
                    dst_run.font.color.rgb = _resolved_color
                elif src_run.font.color and src_run.font.color.rgb:
                    dst_run.font.color.rgb = src_run.font.color.rgb
            except Exception:
                pass

    # ------------------------------------------------------------------
    # 1. Body paragraphs + table cells (from translation_segments)
    # ------------------------------------------------------------------
    para_key_to_sources: Dict[Tuple, List[str]] = {}
    para_key_to_element: Dict[Tuple, Paragraph] = {}

    for segment_index, segment_data in segment_data_map.items():
        # Skip excluded or failed segments: emit target only, no bilingual
        is_excluded = segment_data.get("is_excluded", False)
        is_failed = segment_data.get("is_failed", False)
        if is_excluded or is_failed:
            continue

        seg_info = segment_data.get("segment_info", {})
        source_text = segment_data.get("source_text", "")
        if not source_text or not source_text.strip():
            continue

        is_table_cell = seg_info.get("is_table_cell", False)
        table_idx = seg_info.get("table_index")
        row_idx = seg_info.get("row_index")
        cell_idx = seg_info.get("cell_index")
        cell_local_idx = seg_info.get("cell_local_idx", 0)
        para_index = seg_info.get("para_index")

        if is_table_cell and table_idx is not None and row_idx is not None and cell_idx is not None:
            para_key = (True, table_idx, row_idx, cell_idx, cell_local_idx)
        else:
            if para_index is not None:
                para_key = (False, None, None, None, para_index)
            else:
                continue

        element = para_index_map.get(para_key)
        if element is None:
            logger.debug(
                LogModule.RESTOR,
                f"[BILINGUAL-DOCX] Could not locate paragraph for segment {segment_index}, key={para_key}"
            )
            continue

        para_key_to_element[para_key] = element
        para_key_to_sources.setdefault(para_key, []).append(source_text)

    inserted_count = 0

    if para_key_to_sources:
        # Process in descending order so earlier insertions do not affect later ones
        sorted_para_keys = sorted(para_key_to_sources.keys(), reverse=True)

        for para_key in sorted_para_keys:
            sources = para_key_to_sources[para_key]
            if not sources:
                continue

            combined_source = " ".join(s.strip() for s in sources if s.strip())
            if not combined_source:
                continue

            element = para_key_to_element.get(para_key)
            if element is None:
                continue

            try:
                parent = element._element.getparent()
                if parent is None:
                    continue

                new_para = doc.add_paragraph(combined_source)
                _copy_source_format(element, new_para)

                # target_first=False -> source should come BEFORE target
                # target_first=True  -> source should come AFTER target
                if target_first:
                    element._element.addnext(new_para._element)
                else:
                    element._element.addprevious(new_para._element)

                _apply_target_style(element)
                inserted_count += 1
            except Exception as e:
                logger.warning(
                    LogModule.RESTOR,
                    f"[BILINGUAL-DOCX] Failed to insert source paragraph for key={para_key}: {e}"
                )

    # ------------------------------------------------------------------
    # 2. Headers / footers
    # ------------------------------------------------------------------
    if extras_original:
        hf_items = extras_original.get("headers_footers", [])
        if hf_items:
            for idx, section in enumerate(doc.sections):
                for name, part in (("header", section.header), ("footer", section.footer)):
                    key = (name, idx)
                    # Find the matching original text
                    original_text = None
                    for item in hf_items:
                        if not isinstance(item, (list, tuple)) or len(item) != 2:
                            continue
                        k, text = item
                        if _normalize_key(k) == key and text and text.strip():
                            original_text = text
                            break
                    if not original_text:
                        continue

                    try:
                        if part.paragraphs:
                            target_para = part.paragraphs[0]
                            new_para = part.add_paragraph(original_text)
                            _copy_source_format(target_para, new_para)

                            if target_first:
                                target_para._element.addnext(new_para._element)
                            else:
                                target_para._element.addprevious(new_para._element)

                            _apply_target_style(target_para)
                            inserted_count += 1
                    except Exception as e:
                        logger.warning(
                            LogModule.RESTOR,
                            f"[BILINGUAL-DOCX] Failed to insert bilingual header/footer for {key}: {e}"
                        )

    # ------------------------------------------------------------------
    # 3. Textboxes / SDTs
    # ------------------------------------------------------------------
        raw_tb_items = extras_original.get("textboxes_sdts", [])
        # Parse string items back to (key, text) tuples — task state data may have
        # been serialized/deserialized, converting tuples to string representations.
        tb_items = []
        for item in raw_tb_items:
            if isinstance(item, str):
                try:
                    parsed = ast.literal_eval(item)
                    if isinstance(parsed, (list, tuple)) and len(parsed) >= 2:
                        tb_items.append(parsed)
                    else:
                        logger.warning(
                            LogModule.RESTOR,
                            f"[BILINGUAL-DOCX] String item not a valid pair: {item[:120]!r}"
                        )
                except Exception:
                    logger.warning(
                        LogModule.RESTOR,
                        f"[BILINGUAL-DOCX] Failed to parse string item: {item[:120]!r}"
                    )
            else:
                tb_items.append(item)
        logger.info(
            LogModule.RESTOR,
            f"[BILINGUAL-DOCX] Textbox/SDT section: extras_original has textboxes_sdts={bool(raw_tb_items)}, "
            f"count={len(raw_tb_items)}, parsed={len(tb_items)} items"
        )
        if tb_items:
            # Log what keys are available
            keys_found = [_normalize_key(item[0]) if isinstance(item, (list, tuple)) and len(item) >= 2 else f"BAD:{type(item).__name__}:{item!r}" for item in tb_items]
            logger.info(
                LogModule.RESTOR,
                f"[BILINGUAL-DOCX] Textbox/SDT keys in tb_items: {keys_found}"
            )
            # Locate textbox containers in document XML
            try:
                from lxml import etree
                nsmap = doc._element.nsmap
                # Search all w:txbxContent and legacy v:textbox nodes
                txbx_nodes = doc._element.xpath('.//*[local-name()="txbxContent"]')
                pict_nodes = doc._element.xpath('.//*[local-name()="pict"]//*[local-name()="textbox"]')
                all_containers = txbx_nodes + pict_nodes

                # Also include drawing elements with text (same iteration order as extraction)
                drawing_nodes = doc._element.xpath('.//*[local-name()="drawing"]')
                for drawing in drawing_nodes:
                    text_elements = drawing.xpath('.//*[local-name()="t"]')
                    if text_elements:
                        all_containers.append(drawing)

                logger.info(
                    LogModule.RESTOR,
                    f"[BILINGUAL-DOCX] Found {len(txbx_nodes)} txbxContent nodes, {len(pict_nodes)} pict/textbox nodes, "
                    f"{len(drawing_nodes)} drawing nodes -> {len(all_containers)} total containers"
                )

                container_idx = 0
                for container in all_containers:
                    key = ("textbox", container_idx)
                    # Try to match with saved original text
                    original_text = None
                    for item in tb_items:
                        if not isinstance(item, (list, tuple)) or len(item) != 2:
                            continue
                        k, text = item
                        if _normalize_key(k) == key and text and text.strip():
                            original_text = text
                            break

                    container_idx += 1

                    logger.info(
                        LogModule.RESTOR,
                        f"[BILINGUAL-DOCX] Textbox container {container_idx - 1}: key={key}, match_found={original_text is not None}"
                    )

                    if not original_text:
                        continue

                    # Find first paragraph inside this container
                    para_elems = container.xpath('.//*[local-name()="p"]')
                    logger.info(
                        LogModule.RESTOR,
                        f"[BILINGUAL-DOCX] Textbox {key}: {len(para_elems)} paragraph(s) found in container"
                    )
                    if para_elems:
                        try:
                            target_para = Paragraph(para_elems[0], None)
                            new_para = doc.add_paragraph(original_text)
                            _copy_source_format(target_para, new_para)

                            if target_first:
                                target_para._element.addnext(new_para._element)
                            else:
                                target_para._element.addprevious(new_para._element)

                            _apply_target_style(target_para)
                            inserted_count += 1
                            logger.info(
                                LogModule.RESTOR,
                                f"[BILINGUAL-DOCX] Successfully inserted bilingual textbox for {key}"
                            )
                        except Exception as e:
                            logger.warning(
                                LogModule.RESTOR,
                                f"[BILINGUAL-DOCX] Failed to insert bilingual textbox for {key}: {e}"
                            )

                # Handle SDTs
                sdt_elems = doc._element.body.xpath('.//*[local-name()="sdt"]')
                logger.info(
                    LogModule.RESTOR,
                    f"[BILINGUAL-DOCX] SDT section: found {len(sdt_elems)} body SDT elements"
                )
                sdt_index = 0
                for sdt in sdt_elems:
                    parent_sdt = sdt.xpath('./ancestor::*[local-name()="sdt"]')
                    if parent_sdt:
                        continue

                    # Try sdt_content keys
                    for sub_idx in range(10):  # reasonable upper bound
                        key = ("sdt_content", sdt_index, sub_idx)
                        original_text = None
                        for item in tb_items:
                            if not isinstance(item, (list, tuple)) or len(item) != 2:
                                continue
                            k, text = item
                            if _normalize_key(k) == key and text and text.strip():
                                original_text = text
                                break
                        if not original_text:
                            continue

                        sdt_contents = sdt.xpath('.//*[local-name()="sdtContent"]')
                        if sub_idx < len(sdt_contents):
                            para_elems = sdt_contents[sub_idx].xpath('.//*[local-name()="p"]')
                            if para_elems:
                                try:
                                    target_para = Paragraph(para_elems[0], None)
                                    new_para = doc.add_paragraph(original_text)
                                    _copy_source_format(target_para, new_para)

                                    if target_first:
                                        target_para._element.addnext(new_para._element)
                                    else:
                                        target_para._element.addprevious(new_para._element)

                                    _apply_target_style(target_para)
                                    inserted_count += 1
                                except Exception as e:
                                    logger.warning(
                                        LogModule.RESTOR,
                                        f"[BILINGUAL-DOCX] Failed to insert bilingual SDT for {key}: {e}"
                                    )

                    # Try direct sdt key
                    key = ("sdt", sdt_index)
                    original_text = None
                    for item in tb_items:
                        if not isinstance(item, (list, tuple)) or len(item) != 2:
                            continue
                        k, text = item
                        if _normalize_key(k) == key and text and text.strip():
                            original_text = text
                            break
                    if original_text:
                        para_elems = sdt.xpath('.//*[local-name()="p"]')
                        if para_elems:
                            try:
                                target_para = Paragraph(para_elems[0], None)
                                new_para = doc.add_paragraph(original_text)
                                _copy_source_format(target_para, new_para)

                                if target_first:
                                    target_para._element.addnext(new_para._element)
                                else:
                                    target_para._element.addprevious(new_para._element)

                                _apply_target_style(target_para)
                                inserted_count += 1
                            except Exception as e:
                                logger.warning(
                                    LogModule.RESTOR,
                                    f"[BILINGUAL-DOCX] Failed to insert bilingual SDT for {key}: {e}"
                                )

                    # Try sdt_child keys — iterate child SDTs inside this parent
                    child_sdts = sdt.xpath('.//*[local-name()="sdt"]')
                    for child_idx, child_sdt in enumerate(child_sdts):
                        key = ("sdt_child", sdt_index, child_idx)
                        original_text = None
                        for item in tb_items:
                            if not isinstance(item, (list, tuple)) or len(item) != 2:
                                continue
                            k, text = item
                            if _normalize_key(k) == key and text and text.strip():
                                original_text = text
                                break
                        if not original_text:
                            continue
                        para_elems = child_sdt.xpath('.//*[local-name()="p"]')
                        if para_elems:
                            try:
                                target_para = Paragraph(para_elems[0], None)
                                new_para = doc.add_paragraph(original_text)
                                _copy_source_format(target_para, new_para)

                                if target_first:
                                    target_para._element.addnext(new_para._element)
                                else:
                                    target_para._element.addprevious(new_para._element)

                                _apply_target_style(target_para)
                                inserted_count += 1
                            except Exception as e:
                                logger.warning(
                                    LogModule.RESTOR,
                                    f"[BILINGUAL-DOCX] Failed to insert bilingual SDT child for {key}: {e}"
                                )

                    sdt_index += 1
            except Exception as e:
                logger.warning(
                    LogModule.RESTOR,
                    f"[BILINGUAL-DOCX] Failed to process textbox/SDT bilingual insertion: {e}"
                )

    logger.info(
        LogModule.RESTOR,
        f"[BILINGUAL-DOCX] Inserted {inserted_count} source paragraphs (target_first={target_first})"
    )
