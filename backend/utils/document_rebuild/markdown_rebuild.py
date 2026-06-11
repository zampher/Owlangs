# SPDX-FileCopyrightText: 2026 Zamphersss
# SPDX-License-Identifier: MPL-2.0

"""Markdown document rebuild from translation segments (layout and text paths)."""

import re
from pathlib import Path
from typing import Optional, Dict, Any, List, Tuple

from ir.markdown_document import MarkdownDocument
from logger import unified_logger as logger
from logger.logger import LogModule
from utils.translation_segments import get_translation_segments
from utils.markdown_splitter import join_markdown_texts
from utils.image_placeholder_utils import _replace_placeholders_with_images, PLACEHOLDER_PATTERN
from utils.mixed_formula_text import mixed_text_to_md, has_mixed_formula_content
from .html_tag_utils import _close_unclosed_inline_tags
from .table_layout_utils import (
    _extract_chart_from_layout_block,
    _is_chart_body_segment,
    _is_markdown_table,
    _markdown_table_to_html,
    _replace_table_cells_with_translations,
    _extract_table_from_layout_block,
    _extract_equation_from_layout_block,
)

def _recover_layout_block_indices_from_prepared_chunks(
    segments: List[Dict[str, Any]],
    task_state: Optional[Dict[str, Any]],
) -> int:
    """Map segment_index -> layout block indices via extract-phase metadata or prepared chunks."""
    segment_layout_map = (task_state or {}).get("segment_layout_block_map")
    if segment_layout_map:
        recovered = 0
        for segment in segments:
            if segment.get("layout_block_indices"):
                continue
            seg_idx = segment.get("segment_index")
            if seg_idx is None:
                continue
            try:
                seg_idx = int(seg_idx)
            except (TypeError, ValueError):
                continue
            if seg_idx < 0 or seg_idx >= len(segment_layout_map):
                continue
            blocks = segment_layout_map[seg_idx] or []
            if blocks:
                segment["layout_block_indices"] = list(blocks)
                recovered += 1
        if recovered:
            logger.info(
                LogModule.RESTOR,
                f"[REBUILD] Recovered layout_block_indices for {recovered} segments "
                f"from segment_layout_block_map",
            )
            return recovered

    prepared = (task_state or {}).get("layout_prepared_chunks") or []
    if not prepared:
        return 0
    seg_to_blocks: Dict[int, List[int]] = {}
    for chunk in prepared:
        if not isinstance(chunk, dict):
            continue
        block_indices = chunk.get("block_indices") or []
        if not block_indices:
            continue
        segment_indices = chunk.get("segment_indices") or []
        if len(segment_indices) != 1:
            # Multiple segments share one translation chunk; aggregated block_indices must not
            # be copied to every segment (would mark text segments as image blocks).
            continue
        try:
            seg_idx = int(segment_indices[0])
        except (TypeError, ValueError, IndexError):
            continue
        existing = seg_to_blocks.setdefault(seg_idx, [])
        for raw_bidx in block_indices:
            try:
                bidx = int(raw_bidx)
            except (TypeError, ValueError):
                continue
            if bidx not in existing:
                existing.append(bidx)
    recovered = 0
    for segment in segments:
        if segment.get("layout_block_indices"):
            continue
        seg_idx = segment.get("segment_index")
        if seg_idx is None:
            continue
        blocks = seg_to_blocks.get(int(seg_idx))
        if blocks:
            segment["layout_block_indices"] = list(blocks)
            recovered += 1
    return recovered


# Feature flag: high-fidelity PDF layout rebuild.
# When True, PDF rebuild uses layout_document-based block types,
# supporting equation_format/table_body_format switching (e.g. export
# formulas/tables as images instead of LaTeX/HTML text).
# When False, PDF rebuild falls back to text-based segment concatenation,
# which ignores format parameters — this prevents image-format export
# from working correctly.
ENABLE_PDF_LAYOUT_REBUILD: bool = True


def has_revised_segments(task_state: Dict[str, Any]) -> bool:
    """
    Check if any translation segments have been modified or retranslated.
    
    Args:
        task_state: Task state dictionary
        
    Returns:
        True if any segments have been modified or retranslated, False otherwise
    """
    segments_data = task_state.get("translation_segments")
    if not segments_data:
        logger.debug(LogModule.RESTOR,"[HAS_REVISED] No translation_segments found in task_state")
        return False
    
    segments = segments_data.get("segments", [])
    if not segments:
        logger.debug(LogModule.RESTOR,"[HAS_REVISED] Empty segments list")
        return False
    
    logger.debug(LogModule.RESTOR,f"[HAS_REVISED] Checking {len(segments)} segments for revisions")
    
    # Sample first 10 segments to check their structure
    sample_count = min(10, len(segments))
    for i in range(sample_count):
        seg = segments[i]
        seg_idx = seg.get("segment_index", i)
        modified = seg.get("modified", False)
        modified_text = seg.get("modified_text")
        target_text = seg.get("target_text", "")
        retry_count = seg.get("retry_count", 0)
        logger.debug(LogModule.RESTOR,
            f"[HAS_REVISED] Sample segment {seg_idx}: modified={modified}, "
            f"modified_text={'present' if modified_text is not None else 'None'}, "
            f"target_text_len={len(target_text)}, retry_count={retry_count}"
        )
    
    modified_count = 0
    modified_text_diff_count = 0
    
    for segment in segments:
        segment_index = segment.get("segment_index", -1)
        # Check if segment is marked as modified (user manually edited or retranslated)
        if segment.get("modified", False):
            modified_count += 1
            logger.info(LogModule.TRANS, f"[HAS_REVISED] Found modified segment at index {segment_index}")
            return True
        # CRITICAL: Also check if modified_text differs from target_text
        # This ensures we detect user edits even if modified flag is not set
        # Frontend may update modified_text directly without setting modified flag
        modified_text = segment.get("modified_text")
        target_text = segment.get("target_text", "")
        if modified_text is not None and modified_text != target_text:
            modified_text_diff_count += 1
            logger.info(
                LogModule.RESTOR,
                f"[HAS_REVISED] Found segment with modified_text at index {segment_index} "
                f"(modified_text differs from target_text): "
                f"target='{target_text[:50]}...', modified='{modified_text[:50]}...'",
            )
            return True
    
    logger.debug(
        LogModule.RESTOR,
        f"[HAS_REVISED] No modified or retranslated segments found. "
        f"Summary: total={len(segments)}, modified={modified_count}, "
        f"modified_text_diff={modified_text_diff_count}",
    )
    return False


def _prepare_image_data_map(task_state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Prepare image_data_map from task_state for markdown rebuild.
    
    Args:
        task_state: Task state dictionary
        
    Returns:
        Image data map dictionary
    """
    # Replace placeholders with actual image markdown if available
    # CRITICAL: Get image_data_map from task_state, ensuring we work with the actual reference
    # Priority: translation_image_data_map > image_data_map > create new dict
    if "image_data_map" not in task_state:
        # Create new dict in task_state if it doesn't exist
        # Prefer translation_image_data_map if available, otherwise create empty dict
        if task_state.get("translation_image_data_map"):
            # Copy translation_image_data_map to image_data_map
            task_state["image_data_map"] = dict(task_state["translation_image_data_map"])
        else:
            task_state["image_data_map"] = {}
    else:
        # image_data_map exists, but if it's empty and translation_image_data_map exists, copy it
        if not task_state["image_data_map"] and task_state.get("translation_image_data_map"):
            task_state["image_data_map"].update(task_state["translation_image_data_map"])
    
    # Get reference to the dict in task_state (so updates persist)
    return task_state["image_data_map"]


def _process_images_and_create_markdown_document(
    markdown_content: str,
    task_state: Dict[str, Any],
    segments: List[Dict[str, Any]],
    file_stem: Optional[str],
    metadata: Dict[str, Any],
    output_dir: Optional[Path] = None,
) -> MarkdownDocument:
    """
    Process images in markdown content and create MarkdownDocument.
    
    This is shared logic for both layout and text path rebuilds.
    
    Args:
        markdown_content: Rebuilt markdown content
        task_state: Task state dictionary
        segments: List of translation segments
        file_stem: File stem for the document
        metadata: Segments metadata
        output_dir: Optional output directory for saving images
        
    Returns:
        MarkdownDocument instance
    """
    # Get file stem from metadata or parameter
    if not file_stem:
        original_filename = metadata.get("original_filename")
        if original_filename:
            file_stem = Path(original_filename).stem
        else:
            file_stem = "rebuilt"
    
    # Process images
    image_data_map = _prepare_image_data_map(task_state)
    
    if image_data_map:
        # Store original keys count for comparison
        original_keys_count = len(image_data_map)
        markdown_content, saved_image_paths = _replace_placeholders_with_images(
            markdown_content, image_data_map, output_dir, update_image_data_map=True
        )
        # Log updated keys for debugging
        if saved_image_paths:
            updated_keys = [f"./images/{path.name}" for path in saved_image_paths]
            logger.debug(LogModule.TRANS, f"[REBUILD] Updated image_data_map with {len(updated_keys)} file paths: {updated_keys[:5]}")
            logger.debug(LogModule.TRANS, f"[REBUILD] image_data_map keys count: {original_keys_count} -> {len(image_data_map)}")
        if saved_image_paths:
            logger.debug(LogModule.TRANS, f"Saved {len(saved_image_paths)} images to {output_dir / 'images' if output_dir else 'images'}")
        
        # CRITICAL: Ensure updated image_data_map is saved back to task_state
        # This ensures MD2DOCXExporter can access the updated keys
        if image_data_map:
            task_state["image_data_map"] = image_data_map
            logger.debug(LogModule.RESTOR,f"[REBUILD] Saved updated image_data_map back to task_state with {len(image_data_map)} keys")

    # Close any unclosed <del>/<s>/<ins> in rebuilt content to prevent strikethrough
    # bleeding into exported HTML (e.g. from layout extraction or translation output)
    markdown_content = _close_unclosed_inline_tags(
        markdown_content,
        log_context={"context": "full_markdown", "segment_count": len(segments)},
    )

    # Create new MarkdownDocument
    markdown_bytes = markdown_content.encode('utf-8')
    markdown_doc = MarkdownDocument.from_bytes(
        content=markdown_bytes,
        suffix=".md",
        stem=file_stem
    )
    
    logger.debug(LogModule.TRANS, f"Rebuilt MarkdownDocument from {len(segments)} segments")
    return markdown_doc


def _rebuild_markdown_from_layout_segments(
    segments: List[Dict[str, Any]],
    task_state: Dict[str, Any],
    layout_doc: Any,
    block_index_to_type: Dict[int, str],
    equation_format: Optional[str] = None,
    table_body_format: Optional[str] = None,
    chart_body_format: Optional[str] = None,
    bilingual_export: bool = False,
    target_first: bool = False,
    source_text_italic: bool = False,
    source_text_color: Optional[str] = None,
    target_text_italic: bool = False,
    target_text_color: Optional[str] = None,
) -> str:
    """
    Rebuild markdown content from segments using layout information (PDF path).
    
    This function handles PDF/layout-driven rebuilds where block types come from layout_document.
    
    Args:
        segments: List of translation segments (already sorted by segment_index)
        task_state: Task state dictionary
        layout_doc: LayoutDocument instance
        block_index_to_type: Mapping from block index to block type
        equation_format: Optional format for equations ('text' or 'image')
        table_body_format: Optional format for tables ('html' or 'image')
        chart_body_format: Optional format for charts ('html' or 'image', default: 'image')
        
    Returns:
        Rebuilt markdown content string
    """
    # Filter out segments that correspond to header or footer blocks (for PDF with layout)
    filtered_segments = []
    for segment in segments:
        block_indices = segment.get("layout_block_indices", [])
        # Check if this segment corresponds to header, footer, or page_number blocks
        is_excluded_block = False
        if block_indices:
            for bidx in block_indices:
                block_type = block_index_to_type.get(bidx, "")
                if block_type in ("header", "footer", "page_number"):
                    is_excluded_block = True
                    logger.debug(LogModule.RESTOR,
                        f"[REBUILD] Skipping segment (segment_index={segment.get('segment_index')}) "
                        f"because it corresponds to {block_type} block(s): {block_indices}"
                    )
                    break
        
        # Only include segments that are not header, footer, or page_number
        if not is_excluded_block:
            filtered_segments.append(segment)
    
    segments = filtered_segments
    logger.info(
        LogModule.TRANS,
        f"Filtered out header/footer/page_number segments, remaining: {len(segments)} segments "
        f"(keeping original segment_index/layout order without additional bbox-based resorting)"
    )

    # Collect all target texts and separators (use modified_text if available, otherwise use target_text)
    target_texts = []
    separators = []  # separators[i] is the separator between target_texts[i] and target_texts[i+1]
    modified_segments_count = 0
    for i, segment in enumerate(segments):
        # Priority: modified_text > target_text
        target_text = segment.get("modified_text") or segment.get("target_text", "")
        is_modified = segment.get("modified", False) or segment.get("retry_count", 0) > 0
        if is_modified:
            modified_segments_count += 1
        # CRITICAL: Check if segment is cleared (status="cleared" or empty target_text with modified=True)
        # Cleared segments should be exported as empty string, not skipped
        is_cleared = segment.get("status") == "cleared" or (not target_text and is_modified and segment.get("target_length", -1) == 0)
        if target_text or is_cleared:
            # Include segment even if target_text is empty (for cleared segments)
            target_texts.append(target_text if not is_cleared else "")
            # Get separator after this segment (if available)
            # This separator is between current segment and next segment
            if i < len(segments) - 1:  # Not the last segment
                separator = segment.get("separator_after")
                separators.append(separator)
    
    logger.debug(LogModule.TRANS, f"Rebuilding Markdown: {len(segments)} segments, {modified_segments_count} modified, {len(target_texts)} with content")

    if not target_texts:
        logger.warning(LogModule.RESTOR,"No target texts found in segments")
        return ""

    # Build mapping from segment index to block types (for title formatting)
    # CRITICAL: Use segment_index (not array index) as key to handle filtered/cleared segments
    segment_to_block_types: Dict[int, List[str]] = {}
    for segment in segments:
        segment_index = segment.get("segment_index", -1)
        block_indices = segment.get("layout_block_indices", [])
        if block_indices and segment_index >= 0:
            block_types = [block_index_to_type.get(bidx, "text") for bidx in block_indices if bidx in block_index_to_type]
            if block_types:
                segment_to_block_types[segment_index] = block_types
    
    # Count segments per table block index: when only one segment maps to a table block, treat it as table body
    # so we can apply table_html even when target_text is plain text (e.g. after translation).
    table_block_index_to_segment_count: Dict[int, int] = {}
    for segment in segments:
        for bidx in segment.get("layout_block_indices", []):
            if block_index_to_type.get(bidx) == "table":
                table_block_index_to_segment_count[bidx] = table_block_index_to_segment_count.get(bidx, 0) + 1
    
    # Build mapping from target_texts index to segment index
    # This is needed because target_texts may have fewer items than segments (if some were skipped)
    # But we already handle cleared segments in the loop above, so target_texts should match segments
    target_idx_to_segment_idx: Dict[int, int] = {}
    target_idx = 0
    for segment in segments:
        segment_index = segment.get("segment_index", -1)
        target_text = segment.get("modified_text") or segment.get("target_text", "")
        is_cleared = segment.get("status") == "cleared" or (not target_text and segment.get("modified", False) and segment.get("target_length", -1) == 0)
        if target_text or is_cleared:
            target_idx_to_segment_idx[target_idx] = segment_index
            target_idx += 1
    
    # Check if we need to apply format parameters
    should_apply_format = (
        equation_format is not None or table_body_format is not None or chart_body_format is not None
    )
    
    # Build block index to block mapping (used for format processing and title heading level)
    block_index_to_block: Dict[int, Any] = {}
    try:
        from layout.base import LayoutDocument as _LD
        if isinstance(layout_doc, _LD):
            for block in layout_doc.iter_blocks():
                if block.index is not None:
                    block_index_to_block[block.index] = block
    except Exception as e:
        logger.debug(LogModule.RESTOR, f"Failed to build block index to block mapping: {e}")
        should_apply_format = False

    # P0b: Post-process title blocks to filter out false positives (body text that
    # MinerU misclassifies as "title"). Only self-hosted MinerU (middle.json) provides
    # font size data in its layout.json — the Cloud API does not, so heading hierarchy
    # from font sizes is unavailable and all valid titles use H1 (default).
    if layout_doc is not None:
        try:
            from layout.pdf_font_extractor import _is_likely_heading
            for page in layout_doc.pages:
                for block in page.blocks:
                    if block.type == "title" and not _is_likely_heading(block):
                        block.heading_level = 0  # false positive → body text
        except Exception as e:
            logger.debug(LogModule.RESTOR,
                f"Failed to filter false-positive titles: {e}")

    # Format target texts based on block types; record table block segment role for caption-before-body reorder
    formatted_texts = []
    target_idx_to_table_block: Dict[int, int] = {}
    target_idx_to_is_table_body: Dict[int, bool] = {}
    for i, target_text in enumerate(target_texts):
        formatted = target_text
        # Get segment index for this target_text
        segment_index = target_idx_to_segment_idx.get(i, -1)
        if segment_index >= 0:
            # Get block types for this segment
            block_types = segment_to_block_types.get(segment_index, [])
            
            # Handle format parameters for tables and equations
            if should_apply_format:
                # Find the corresponding segment to get block_indices
                segment = None
                for seg in segments:
                    if seg.get("segment_index") == segment_index:
                        segment = seg
                        break
                
                if segment:
                    block_indices = segment.get("layout_block_indices", [])
                    
                    # Handle table format
                    # IMPORTANT:
                    # - PDF layout表格的 caption / body / footnote 共用同一个 layout block index（type=='table'）
                    # - LayoutMarkdownBuilder 会按顺序输出：caption -> body(markdown table) -> footnote 文本
                    # - 这里不能仅根据 block_type 判断，而是要基于内容是否是 markdown 表格来区分 body
                    is_table_block = any(
                        block_index_to_type.get(bidx) == "table"
                        for bidx in block_indices
                        if bidx in block_index_to_type
                    )
                    
                    # Treat as table body when: target is markdown table, or segment has block_type/is_table_body,
                    # or this is the only segment for this table block (so it must be body).
                    table_block_idx = next(
                        (bidx for bidx in block_indices
                         if block_index_to_type.get(bidx) == "table"),
                        None
                    )
                    is_table_body_segment = (
                        _is_markdown_table(target_text)
                        or segment.get("block_type") == "table_body"
                        or segment.get("is_table_body")
                        or (
                            table_block_idx is not None
                            and table_block_index_to_segment_count.get(table_block_idx, 0) == 1
                        )
                    )
                    if is_table_block and table_block_idx is not None:
                        target_idx_to_table_block[i] = table_block_idx
                        target_idx_to_is_table_body[i] = is_table_body_segment

                    # Handle chart format for chart blocks (similar to table handling)
                    is_chart_block = "chart" in block_types
                    is_chart_body_segment = False
                    chart_block_idx = None
                    if is_chart_block:
                        for bidx in block_indices:
                            btype = block_index_to_type.get(bidx, "")
                            if btype == "chart":
                                chart_block_idx = bidx
                                # Chart body: image markdown (![Chart](layoutimgN)) or markdown table
                                is_chart_body_segment = _is_chart_body_segment(
                                    target_text, chart_block_idx, segments, segment=segment
                                )
                                break

                    if is_chart_block and chart_block_idx is not None and chart_body_format and is_chart_body_segment:
                        chart_block = block_index_to_block.get(chart_block_idx)
                        if chart_block:
                            chart_content, chart_image_path = _extract_chart_from_layout_block(chart_block)

                            if chart_body_format == "image" and chart_image_path:
                                filename = chart_image_path.split('/')[-1].split('\\')[-1]
                                formatted = f"![Chart]({filename})"
                                logger.info(
                                    LogModule.RESTOR,
                                    f"[HTML-REBUILD] Replaced chart body segment {segment_index} "
                                    f"with image format for block {chart_block_idx}"
                                )
                            elif chart_body_format == "html" and chart_content:
                                # Chart content is markdown table, convert to HTML
                                formatted = _markdown_table_to_html(chart_content)
                                logger.info(
                                    LogModule.RESTOR,
                                    f"[HTML-REBUILD] Replaced chart body segment {segment_index} "
                                    f"with HTML format for block {chart_block_idx}"
                                )
                            else:
                                logger.debug(
                                    LogModule.RESTOR,
                                    f"[HTML-REBUILD] Chart body segment {segment_index} for block {chart_block_idx}: "
                                    f"chart_body_format={chart_body_format}, chart_content={'present' if chart_content else 'None'}, "
                                    f"keeping original target_text"
                                )
                        else:
                            logger.warning(
                                LogModule.RESTOR,
                                f"[HTML-REBUILD] Chart block {chart_block_idx} not found in block_index_to_block"
                            )

                    if is_table_block and table_body_format and is_table_body_segment and table_block_idx is not None:
                        table_block = block_index_to_block.get(table_block_idx)
                        if table_block:
                            table_html, table_image_path = _extract_table_from_layout_block(table_block)
                            
                            if table_body_format == "image" and table_image_path:
                                filename = table_image_path.split('/')[-1].split('\\')[-1]
                                formatted = f"![Table]({filename})"
                                logger.info(
                                    LogModule.RESTOR,
                                    f"[HTML-REBUILD] Replaced table body segment {segment_index} "
                                    f"with image format for block {table_block_idx}"
                                )
                            elif table_body_format == "html" and table_html:
                                original_target_preview = (target_text or "")[:100]
                                replaced_html = _replace_table_cells_with_translations(
                                    table_html,
                                    table_block_idx,
                                    segments,
                                    block_index_to_type
                                )
                                if replaced_html is not None:
                                    formatted = replaced_html
                                    logger.info(
                                        LogModule.RESTOR,
                                        f"[HTML-REBUILD] Replaced table BODY segment {segment_index} "
                                        f"for block {table_block_idx} with HTML format (cell translations)."
                                    )
                                elif _is_markdown_table(target_text):
                                    formatted = (
                                        _markdown_table_to_html(target_text)
                                        if target_text
                                        else target_text
                                    )
                                    logger.info(
                                        LogModule.RESTOR,
                                        f"[HTML-REBUILD] No table cell translations for block {table_block_idx}; "
                                        f"converted translated markdown table to HTML for segment {segment_index}."
                                    )
                                else:
                                    # Target is plain text (e.g. after translation); use layout table_html
                                    # so export renders as HTML table instead of plain text.
                                    formatted = table_html
                                    logger.info(
                                        LogModule.RESTOR,
                                        f"[HTML-REBUILD] Table body segment {segment_index} for block {table_block_idx}: "
                                        f"target_text is not markdown table; using layout table_html so export renders as HTML table."
                                    )
                            else:
                                logger.debug(
                                    LogModule.RESTOR,
                                    f"[HTML-REBUILD] Table body segment {segment_index} for block {table_block_idx}: "
                                    f"table_body_format={table_body_format}, table_html={'present' if table_html else 'None'}, "
                                    f"keeping original target_text"
                                )
                        else:
                            logger.warning(
                                LogModule.RESTOR,
                                f"[HTML-REBUILD] Table block {table_block_idx} not found in block_index_to_block"
                            )
                    
                    # Handle equation format for interline_equation blocks
                    if "interline_equation" in block_types and equation_format:
                        eq_block_idx = next(
                            (bidx for bidx in block_indices
                             if block_index_to_type.get(bidx) == "interline_equation"),
                            None
                        )
                        if eq_block_idx is not None:
                            eq_block = block_index_to_block.get(eq_block_idx)
                            if eq_block:
                                eq_content, eq_image_path = _extract_equation_from_layout_block(eq_block)

                                if equation_format == "image" and eq_image_path:
                                    # Use image format
                                    filename = eq_image_path.split('/')[-1].split('\\')[-1]
                                    formatted = f"![Equation]({filename})"
                                elif equation_format == "latex" and eq_content:
                                    # Use layout LaTeX wrapped for Pandoc/PDF (do not use translated plain text)
                                    formatted = f"$$\n{eq_content}\n$$"
                                elif equation_format == "text" and eq_content:
                                    # For layout equations we trust eq_content as pure LaTeX and
                                    # keep it as a block formula. Do NOT run mixed_text_to_md here,
                                    # otherwise commands like \min, \leq, \tag will be split and
                                    # wrapped with extra '$',破坏原始 LaTeX。
                                    formatted = f"$$\n{eq_content}\n$$"
                                # If format doesn't match available data, keep original target_text

                    # Additional handling for non-equation blocks that still contain LaTeX (e.g. algorithm lines)
                    # when exporting equations as text. This covers segments like ALGORITHM1 where block_type is
                    # "text" but content mixes plain text and LaTeX commands.
                    if (
                        equation_format == "text"
                        and "interline_equation" not in block_types
                        and formatted
                    ):
                        raw_non_eq = formatted
                        is_mixed_non_eq = has_mixed_formula_content(raw_non_eq)
                        if is_mixed_non_eq:
                            logger.info(
                                LogModule.RESTOR,
                                f"[REBUILD] Mixed text with formula (non-equation block): "
                                f"segment_index={segment_index}, block_indices={segment.get('layout_block_indices', [])}, "
                                f"is_mixed={is_mixed_non_eq}, preview={repr((raw_non_eq or '')[:120])}..."
                            )
                            formatted = mixed_text_to_md(raw_non_eq)
            
            # Handle title formatting (independent of format parameters)
            if "title" in block_types:
                text_stripped = formatted.strip()
                # Remove any existing markdown heading markers
                text_stripped = re.sub(r'^#+\s*', '', text_stripped)
                # Infer heading level from block metadata (font size in layout blocks)
                level = 1  # default H1
                block_indices: List[int] = []
                for seg in segments:
                    if seg.get("segment_index") == segment_index:
                        block_indices = seg.get("layout_block_indices", [])
                        break
                is_body_text = False
                for bidx in block_indices:
                    if block_index_to_type.get(bidx) == "title":
                        block = block_index_to_block.get(bidx)
                        if block is not None:
                            bl = getattr(block, "heading_level", 1)
                            if isinstance(bl, int) and 0 <= bl <= 6:
                                if bl == 0:
                                    # heading_level=0 means false-positive title (body text)
                                    is_body_text = True
                                else:
                                    level = bl
                                break
                if is_body_text:
                    formatted = text_stripped
                else:
                    # Add markdown heading format with correct level
                    formatted = f"{'#' * level} {text_stripped}"
        formatted_texts.append(formatted)
    
    # Reorder table block segments so caption comes before table body (image) in exported DOCX/HTML/PDF
    n_ft = len(formatted_texts)
    order: List[int] = list(range(n_ft))
    block_to_indices: Dict[int, List[int]] = {}
    for idx in range(n_ft):
        blk = target_idx_to_table_block.get(idx)
        if blk is not None:
            block_to_indices.setdefault(blk, []).append(idx)
    for block_idx, indices in block_to_indices.items():
        if len(indices) < 2:
            continue
        # Caption (is_table_body=False) must come before body (is_table_body=True)
        sorted_indices = sorted(
            indices,
            key=lambda idx: (target_idx_to_is_table_body.get(idx, False), idx),
        )
        positions = sorted(indices)
        for k, pos in enumerate(positions):
            order[pos] = sorted_indices[k]
    # Apply reorder to formatted_texts and separators for markdown_parts loop
    reordered_formatted_texts = [formatted_texts[order[i]] for i in range(n_ft)]
    reordered_target_idx_to_segment_idx: Dict[int, int] = {
        i: target_idx_to_segment_idx.get(order[i], -1) for i in range(n_ft)
    }
    reordered_separators: List[Any] = []
    for i in range(n_ft - 1):
        lo, hi = min(order[i], order[i + 1]), max(order[i], order[i + 1])
        if hi == lo + 1 and lo < len(separators):
            reordered_separators.append(separators[lo])
        else:
            reordered_separators.append("\n\n")
    formatted_texts = reordered_formatted_texts
    target_idx_to_segment_idx = reordered_target_idx_to_segment_idx
    separators = reordered_separators
    
    # Bilingual export: interleave source and target for text/title blocks, and for
    # table/equation blocks when rendered in text format (HTML/LaTeX). Image-rendered
    # tables (table_body_format=image) and equations (equation_format=image) skip
    # bilingual since binary images cannot be interleaved.
    if bilingual_export:
        from utils.bilingual_export_utils import build_bilingual_segment_text
        bilingual_formatted_texts = []
        for i, formatted in enumerate(formatted_texts):
            segment_index = target_idx_to_segment_idx.get(i, -1)
            segment = None
            for seg in segments:
                if seg.get("segment_index") == segment_index:
                    segment = seg
                    break
            if not segment:
                bilingual_formatted_texts.append(formatted)
                continue

            source_text = segment.get("source_text", "")
            is_excluded = bool(segment.get("is_excluded", False))
            is_cleared = bool(
                segment.get("status") == "cleared"
                or (not formatted and segment.get("modified", False) and segment.get("target_length", -1) == 0)
            )

            # Skip bilingual only for segments rendered as images (cannot interleave binary images).
            # Image/table captions share layout block indices with image/table blocks but contain
            # real text — use segment content, not layout block type alone.
            block_types = segment_to_block_types.get(segment_index, [])
            from utils.bilingual_export_utils import should_skip_bilingual_for_image_render

            if should_skip_bilingual_for_image_render(
                segment,
                block_types,
                table_body_format=table_body_format,
                equation_format=equation_format,
                is_table_body=target_idx_to_is_table_body.get(i, False),
            ):
                bilingual_formatted_texts.append(formatted)
                continue

            # For text/title blocks, and table/equation blocks in text format, build bilingual
            combined = build_bilingual_segment_text(
                source_text=source_text,
                target_text=formatted,
                target_first=target_first,
                is_excluded=is_excluded,
                is_cleared=is_cleared,
                inner_separator="\n\n",
                source_text_italic=source_text_italic,
                source_text_color=source_text_color,
                target_text_italic=target_text_italic,
                target_text_color=target_text_color,
                use_html_styles=True,
            )
            bilingual_formatted_texts.append(combined)
        
        formatted_texts = bilingual_formatted_texts
        logger.debug(
            LogModule.TRANS,
            f"Bilingual layout rebuild: {len(formatted_texts)} interleaved segments"
        )
    
    # Use bbox from Layout extraction phase (task_state["layout_block_bbox"]); normalize int keys and float bbox (JSON round-trip safe)
    _raw_bbox = task_state.get("layout_block_bbox") or {}
    block_index_to_bbox: Dict[int, Tuple[float, float, float, float]] = {}
    for k, v in _raw_bbox.items():
        if v is None or len(v) < 4:
            continue
        try:
            bidx = int(k) if not isinstance(k, int) else k
            block_index_to_bbox[bidx] = (float(v[0]), float(v[1]), float(v[2]), float(v[3]))
        except (TypeError, ValueError, IndexError):
            pass
    if not block_index_to_bbox and layout_doc:
        try:
            from layout.base import LayoutDocument as _LD
            if isinstance(layout_doc, _LD):
                for block in layout_doc.iter_blocks():
                    if block.index is not None and getattr(block, "bbox", None):
                        block_index_to_bbox[block.index] = tuple(float(x) for x in block.bbox)
        except Exception as e:
            logger.debug(LogModule.RESTOR, f"Failed to build block_index_to_bbox: {e}")

    def _bbox_y_overlap(bbox1: Tuple[float, float, float, float], bbox2: Tuple[float, float, float, float], tolerance: float = 2.0) -> bool:
        """Check if two layout bboxes (x0, y0, x1, y1) overlap in y (same row). Coerce to float for bbox from JSON."""
        y0_1, y1_1 = float(bbox1[1]), float(bbox1[3])
        y0_2, y1_2 = float(bbox2[1]), float(bbox2[3])
        return not (y1_1 <= y0_2 - tolerance or y1_2 <= y0_1 - tolerance)

    # Rebuild markdown with proper line breaks based on layout
    # For PDF: image-type segments on the same row get no newline (side-by-side); others use double/single newline
    markdown_parts = []
    for i, formatted_text in enumerate(formatted_texts):
        if i > 0:
            # Get segment indices for previous and current target_texts
            prev_segment_idx = target_idx_to_segment_idx.get(i - 1, -1)
            curr_segment_idx = target_idx_to_segment_idx.get(i, -1)
            
            # Find corresponding segments
            prev_segment = None
            curr_segment = None
            for segment in segments:
                seg_idx = segment.get("segment_index", -1)
                if seg_idx == prev_segment_idx:
                    prev_segment = segment
                if seg_idx == curr_segment_idx:
                    curr_segment = segment
                if prev_segment and curr_segment:
                    break
            
            # Determine separator based on layout block boundaries
            if prev_segment and curr_segment:
                prev_blocks = set(prev_segment.get("layout_block_indices", []))
                curr_blocks = set(curr_segment.get("layout_block_indices", []))
                
                # If segments belong to different blocks, use double newline unless both are image-type on same row
                if prev_blocks and curr_blocks and not prev_blocks.intersection(curr_blocks):
                    # Both must be image-type only (not equation/table); same row => no newline so they stay on one line
                    prev_types = {block_index_to_type.get(b) for b in prev_blocks}
                    curr_types = {block_index_to_type.get(b) for b in curr_blocks}
                    prev_all_image = prev_types <= {"image"}
                    curr_all_image = curr_types <= {"image"}
                    if prev_all_image and curr_all_image and block_index_to_bbox:
                        prev_bidx = next(iter(prev_blocks))
                        curr_bidx = next(iter(curr_blocks))
                        bbox_prev = block_index_to_bbox.get(prev_bidx)
                        bbox_curr = block_index_to_bbox.get(curr_bidx)
                        if bbox_prev and bbox_curr and _bbox_y_overlap(bbox_prev, bbox_curr):
                            markdown_parts.append(" ")
                            logger.debug(
                                LogModule.RESTOR,
                                f"[REBUILD] Same-row image blocks prev={prev_bidx} curr={curr_bidx}, no newline (side-by-side)"
                            )
                        else:
                            markdown_parts.append("\n\n")
                    else:
                        markdown_parts.append("\n\n")
                elif i - 1 < len(separators) and separators[i - 1] is not None:
                    # Use preserved separator; empty or whitespace-only would merge segments
                    # (e.g. "# heading" + "" + "paragraph" -> one line in MD/HTML), so enforce at least \n
                    sep = separators[i - 1]
                    sep_str = sep if isinstance(sep, str) else (str(sep) if sep is not None else "")
                    markdown_parts.append(sep_str if sep_str.strip() else "\n")
                else:
                    # Default: single newline for same block or unknown
                    markdown_parts.append("\n")
            elif i - 1 < len(separators) and separators[i - 1] is not None:
                # Use preserved separator if segments not found; never use empty (would merge lines)
                sep = separators[i - 1]
                sep_str = sep if isinstance(sep, str) else (str(sep) if sep is not None else "")
                markdown_parts.append(sep_str if sep_str.strip() else "\n")
            else:
                # Default: single newline
                markdown_parts.append("\n")
        
        markdown_parts.append(formatted_text)
    
    markdown_content = "".join(markdown_parts)
    logger.info(LogModule.TRANS, f"Rebuilt markdown using layout information, content length: {len(markdown_content)} characters")
    return markdown_content


def _rebuild_markdown_from_text_segments(
    segments: List[Dict[str, Any]],
    bilingual_export: bool = False,
    target_first: bool = False,
    source_text_italic: bool = False,
    source_text_color: Optional[str] = None,
    target_text_italic: bool = False,
    target_text_color: Optional[str] = None,
) -> str:
    """
    Rebuild markdown content from segments using text-based logic (MD/TXT path).
    
    This function handles text-driven rebuilds where no layout information is available.
    
    Args:
        segments: List of translation segments (already sorted by segment_index)
        bilingual_export: If True, interleave source and target text for each segment.
        target_first: If True and bilingual_export is True, place target before source.
        
    Returns:
        Rebuilt markdown content string
    """
    from utils.bilingual_export_utils import build_bilingual_segment_text

    # Collect all target texts and separators (use modified_text if available, otherwise use target_text)
    target_texts = []
    separators = []  # separators[i] is the separator between target_texts[i] and target_texts[i+1]
    modified_segments_count = 0
    for i, segment in enumerate(segments):
        # Priority: modified_text > target_text
        target_text = segment.get("modified_text") or segment.get("target_text", "")
        is_modified = segment.get("modified", False) or segment.get("retry_count", 0) > 0
        if is_modified:
            modified_segments_count += 1
        # CRITICAL: Check if segment is cleared (status="cleared" or empty target_text with modified=True)
        # Cleared segments should be exported as empty string, not skipped
        is_cleared = segment.get("status") == "cleared" or (not target_text and is_modified and segment.get("target_length", -1) == 0)
        if target_text or is_cleared:
            # Include segment even if target_text is empty (for cleared segments)
            target_texts.append(target_text if not is_cleared else "")
            # Get separator after this segment (if available)
            # This separator is between current segment and next segment
            if i < len(segments) - 1:  # Not the last segment
                separator = segment.get("separator_after")
                separators.append(separator)
    
    logger.debug(LogModule.TRANS, f"Rebuilding Markdown: {len(segments)} segments, {modified_segments_count} modified, {len(target_texts)} with content")

    if not target_texts:
        logger.warning(LogModule.RESTOR,"No target texts found in segments")
        return ""

    # Apply bilingual interleaving if requested
    if bilingual_export:
        bilingual_texts = []
        text_idx = 0
        for segment in segments:
            target_text = segment.get("modified_text") or segment.get("target_text", "")
            is_modified = segment.get("modified", False) or segment.get("retry_count", 0) > 0
            is_cleared = segment.get("status") == "cleared" or (not target_text and is_modified and segment.get("target_length", -1) == 0)
            if not target_text and not is_cleared:
                continue
            if text_idx >= len(target_texts):
                break
            source_text = segment.get("source_text", "")
            is_excluded = bool(segment.get("is_excluded", False))
            combined = build_bilingual_segment_text(
                source_text=source_text,
                target_text=target_text if not is_cleared else "",
                target_first=target_first,
                is_excluded=is_excluded,
                is_cleared=is_cleared,
                inner_separator="\n\n",
                source_text_italic=source_text_italic,
                source_text_color=source_text_color,
                target_text_italic=target_text_italic,
                target_text_color=target_text_color,
                use_html_styles=True,
            )
            bilingual_texts.append(combined)
            text_idx += 1
        target_texts = bilingual_texts
        logger.debug(LogModule.TRANS, f"Bilingual markdown rebuild: {len(target_texts)} interleaved segments")

    # Rebuild markdown using preserved separators or intelligent joining
    if len(separators) == len(target_texts) - 1 and all(s is not None for s in separators):
        # All separators preserved, use them; empty/whitespace-only -> paragraph break (double newline)
        markdown_content = target_texts[0]
        for i in range(1, len(target_texts)):
            raw = separators[i - 1] if i - 1 < len(separators) else "\n\n"
            sep_str = raw if isinstance(raw, str) else (str(raw) if raw is not None else "\n\n")
            # Use paragraph break when separator is empty so EPUB/MOBI get proper line breaks
            separator = sep_str if sep_str.strip() else "\n\n"
            markdown_content += separator + target_texts[i]
        logger.debug(LogModule.TRANS, f"Rebuilt markdown using preserved separators, content length: {len(markdown_content)} characters")
    else:
        # Use intelligent markdown joining to preserve format (handles single vs double newlines)
        # This preserves original formatting like lists, tables, quotes, etc.
        markdown_content = join_markdown_texts(target_texts)
        logger.debug(LogModule.TRANS, f"Rebuilt markdown using intelligent joining, content length: {len(markdown_content)} characters")
    
    return markdown_content


def rebuild_markdown_document_from_segments(
    task_state: Dict[str, Any],
    file_stem: Optional[str] = None,
    output_dir: Optional[Path] = None,
    equation_format: Optional[str] = None,
    table_body_format: Optional[str] = None,
    chart_body_format: Optional[str] = None,
    bilingual_export: bool = False,
    target_first: bool = False,
) -> Optional[MarkdownDocument]:
    """
    Rebuild MarkdownDocument from revised translation segments.
    
    This is the main entry point that routes to layout-based or text-based rebuild
    based on source_input_type and layout_document availability.
    
    Args:
        task_state: Task state dictionary containing translation_segments
        file_stem: File stem for the document (if None, will try to get from metadata)
        output_dir: Optional output directory for saving images
        equation_format: Optional format for equations ('text' or 'image')
        table_body_format: Optional format for tables ('html' or 'image')
        chart_body_format: Optional format for charts ('html' or 'image', default: 'image')
        bilingual_export: If True, interleave source and target text for each segment.
        target_first: If True and bilingual_export is True, place target before source.
        
    Returns:
        Rebuilt MarkdownDocument, or None if segments are not available
    """
    # Resolve bilingual settings from explicit args -> task_state
    # Note: only use stored value if bilingual_export was not explicitly provided
    # (None means "not specified", not "False")
    if bilingual_export is None and task_state:
        from utils.bilingual_export_utils import get_bilingual_config
        _be, _tf = get_bilingual_config(task_state)
        if _be:
            bilingual_export = True
            target_first = _tf

    style_source_italic = False
    style_source_color: Optional[str] = None
    style_target_italic = False
    style_target_color: Optional[str] = None
    if bilingual_export and task_state:
        from utils.bilingual_export_utils import get_bilingual_style_config
        (
            style_source_italic,
            style_source_color,
            style_target_italic,
            style_target_color,
        ) = get_bilingual_style_config(task_state)

    segments_data = get_translation_segments(None, task_state)
    if not segments_data:
        logger.warning(LogModule.RESTOR,"No translation segments found for rebuilding document")
        return None
    
    segments = segments_data.get("segments", [])
    metadata = segments_data.get("metadata", {})
    
    if not segments:
        logger.warning(LogModule.RESTOR,"Empty segments list, cannot rebuild document")
        return None
    
    # P0: Only use layout for rebuild when source is layout-driven (PDF with layout_document).
    # Text-driven (MD/TXT) must not use layout block types to avoid mixing.
    source_input_type = (task_state.get("source_input_type") if task_state else None) or (metadata.get("source_input_type") if isinstance(metadata, dict) else None) or "text"
    if source_input_type not in ("layout", "text"):
        source_input_type = "text"
    layout_doc = task_state.get("layout_document") if task_state else None

    # P0a: Auto-promote to layout when layout_doc AND layout_chunk_block_map are both present.
    # layout_chunk_block_map is the definitive indicator of a PDF layout workflow.
    # Without this promotion, newly-created tasks (inherited from convert phase) may still have
    # source_input_type="text", causing the layout-based format regeneration to be skipped
    # (e.g. equation_format=image / table_body_format=image have no effect).
    if layout_doc is not None and source_input_type != "layout":
        _has_layout_map = bool(task_state.get("layout_chunk_block_map")) if task_state else False
        if _has_layout_map:
            source_input_type = "layout"
            logger.info(
                LogModule.RESTOR,
                "[REBUILD] Auto-promoted source_input_type to 'layout' "
                "(layout_document + layout_chunk_block_map present)",
            )

    is_pdf_with_layout = layout_doc is not None and source_input_type == "layout"
    segments_with_layout_indices = sum(1 for s in segments if s.get("layout_block_indices"))

    # P1: Log key branch and WARNING on mixed usage for quick diagnosis
    if layout_doc is not None and source_input_type != "layout":
        logger.info(LogModule.RESTOR, f"[REBUILD] MD path: using text-based segment type (source_input_type={source_input_type}, skipping layout)")
    if segments_with_layout_indices and not is_pdf_with_layout:
        logger.warning(
            LogModule.RESTOR,
            f"[REBUILD] {segments_with_layout_indices} segment(s) have layout_block_indices but no layout_document/source_input_type!=layout; using text-only rebuild",
        )
    if is_pdf_with_layout and segments_with_layout_indices == 0:
        logger.info(
            LogModule.RESTOR,
            "[REBUILD] Layout branch taken but no segment has layout_block_indices; attempting recovery",
        )
        recovered_count = _recover_layout_block_indices_from_prepared_chunks(segments, task_state)
        segments_with_layout_indices = sum(
            1 for s in segments if s.get("layout_block_indices")
        )
        if recovered_count:
            logger.info(
                LogModule.RESTOR,
                f"[REBUILD] Recovered layout_block_indices for {recovered_count} segments "
                f"from layout_prepared_chunks",
            )
        elif segments_with_layout_indices == 0:
            logger.info(
                LogModule.RESTOR,
                "[REBUILD] layout_block_indices recovery failed; block types may not apply (check segment recording)",
            )

    # Sort segments by segment_index so text path and layout path have a consistent baseline order.
    # For PDF layout path, _rebuild_markdown_from_layout_segments will re-sort by layout order (page + bbox y)
    # so that image/paragraph position matches the source PDF when segment_index does not follow layout.
    segments.sort(key=lambda x: x.get("segment_index", 0))
    
    # Route to appropriate rebuild function based on source type
    if not ENABLE_PDF_LAYOUT_REBUILD:
        is_pdf_with_layout = False

    if is_pdf_with_layout:
        # Build block type mapping from layout_document
        block_index_to_type: Dict[int, str] = {}
        try:
            from layout.base import LayoutDocument as _LD
            if isinstance(layout_doc, _LD):
                for block in layout_doc.iter_blocks():
                    if block.index is not None:
                        block_index_to_type[block.index] = block.type
                logger.info(LogModule.TRANS, f"Loaded block type mapping: {len(block_index_to_type)} blocks")
                logger.info(LogModule.RESTOR, "[REBUILD] PDF path: using layout_document for block types")
        except Exception as e:
            logger.debug(LogModule.RESTOR,f"Failed to build block type mapping: {e}")
            is_pdf_with_layout = False
        
        if is_pdf_with_layout and block_index_to_type:
            # Use layout-based rebuild
            markdown_content = _rebuild_markdown_from_layout_segments(
                segments=segments,
                task_state=task_state,
                layout_doc=layout_doc,
                block_index_to_type=block_index_to_type,
                equation_format=equation_format,
                table_body_format=table_body_format,
                chart_body_format=chart_body_format,
                bilingual_export=bilingual_export,
                target_first=target_first,
                source_text_italic=style_source_italic,
                source_text_color=style_source_color,
                target_text_italic=style_target_italic,
                target_text_color=style_target_color,
            )
        else:
            # Fallback to text-based rebuild if layout loading failed
            logger.warning(LogModule.RESTOR, "[REBUILD] Layout loading failed, falling back to text-based rebuild")
            markdown_content = _rebuild_markdown_from_text_segments(
                segments=segments,
                bilingual_export=bilingual_export,
                target_first=target_first,
                source_text_italic=style_source_italic,
                source_text_color=style_source_color,
                target_text_italic=style_target_italic,
                target_text_color=style_target_color,
            )
    else:
        # Use text-based rebuild for MD/TXT paths
        if not is_pdf_with_layout:
            logger.debug(LogModule.RESTOR, "[REBUILD] Text path: using text-based segment type for rebuild")
        markdown_content = _rebuild_markdown_from_text_segments(
            segments=segments,
            bilingual_export=bilingual_export,
            target_first=target_first,
            source_text_italic=style_source_italic,
            source_text_color=style_source_color,
            target_text_italic=style_target_italic,
            target_text_color=style_target_color,
        )
    
    if not markdown_content:
        logger.warning(LogModule.RESTOR,"No markdown content generated from segments")
        return None

    # P0c: Clean up metadata lines (authors, dates, funding, keywords) that MinerU
    # may have incorrectly marked as headings. These are always body text.
    markdown_content = _clean_metadata_headings(markdown_content)

    # Process images and create MarkdownDocument (shared logic)
    return _process_images_and_create_markdown_document(
        markdown_content=markdown_content,
        task_state=task_state,
        segments=segments,
        file_stem=file_stem,
        metadata=metadata,
        output_dir=output_dir,
    )


def _clean_metadata_headings(markdown_text: str) -> str:
    """
    Remove heading markers from metadata lines that MinerU may have incorrectly
    marked as headings — authors with superscripts, dates, funding info, keywords.

    These are always body text and should not appear as ``# Author Name`` in output.
    """
    _METADATA_HEADING_PATTERNS = (
        r'^#\s+\S+\s+\\?\^?\{\d',          # Author: # Yun Li ^{1}
        r'^#\s+\\?\^?\{\d+\}',              # Affiliation: # ^{1} Department...
        r'^#\s+Correspondence:',             # English metadata
        r'^#\s+Received:',
        r'^#\s+Revised:',
        r'^#\s+Accepted:',
        r'^#\s+Handling Editor:',
        r'^#\s+Funding:',
        r'^#\s+Keywords:',
        r'^#\s+通讯作者',                     # Chinese metadata
        r'^#\s+收稿日期',
        r'^#\s+修订日期',
        r'^#\s+接收日期',
        r'^#\s+责任编辑',
        r'^#\s+基金项目',
        r'^#\s+关键词',
        # Author list with Unicode superscript characters (¹²³...)
        r'^#\s+\S+[\s·,，][\u2070-\u209F\u00B2\u00B3¹²³]',
        # Author list separated by | with superscripts
        r'^#\s+\S+\s*\|\s*\S+[\u2070-\u209F\u00B2\u00B3¹²³]',
        # Overlong heading lines (> 120 chars after #) — certainly body text
        r'^#\s+.{120,}$',
    )
    compiled = [re.compile(p) for p in _METADATA_HEADING_PATTERNS]

    lines = markdown_text.split("\n")
    cleaned = []
    for line in lines:
        stripped = line.lstrip()
        if any(p.match(stripped) for p in compiled):
            cleaned.append(stripped.lstrip("#").strip())
        else:
            cleaned.append(line)
    return "\n".join(cleaned)
