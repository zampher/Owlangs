# SPDX-FileCopyrightText: 2026 Zampherssss
# SPDX-License-Identifier: MPL-2.0

"""Table/equation extraction from layout blocks and markdown-HTML table conversion utilities."""

import re
from typing import Optional, Dict, Any, Tuple, List
from html.parser import HTMLParser
from html import escape

from logger import unified_logger as logger
from logger.logger import LogModule

from .html_tag_utils import _close_unclosed_inline_tags


def _ensure_table_html_closed(html: str) -> str:
    """
    Ensure that all HTML table tags (<table>, <thead>, <tbody>, <tr>, <td>, <th>)
    are properly closed.  Unclosed tags break the markdown parser which treats
    everything after an unclosed <table> as part of the same HTML block,
    preventing inline-image syntax from being converted to <img> tags.
    """
    if not html or not html.strip():
        return html

    try:
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, "html.parser")
        # BeautifulSoup automatically closes all unclosed tags
        normalised = str(soup)
        if normalised.strip():
            return normalised
    except ImportError:
        pass  # BeautifulSoup not available, use regex fallback
    except Exception as exc:
        logger.debug(
            LogModule.RESTOR,
            f"[TABLE-HTML] BeautifulSoup normalisation failed: {exc}, using regex fallback",
        )

    # Regex fallback: simply ensure </table> is present
    stripped = html.rstrip()
    if "<table" in stripped.lower() and "</table>" not in stripped.lower():
        stripped += "\n</table>"
        logger.debug(
            LogModule.RESTOR,
            "[TABLE-HTML] Appended missing </table> closing tag (regex fallback)",
        )
    return stripped


def _extract_table_from_layout_block(block) -> tuple[Optional[str], Optional[str]]:
    """
    Extract table HTML and image path from layout block.
    
    Args:
        block: LayoutBlock instance
        
    Returns:
        Tuple of (table_html, table_image_path), both can be None
    """
    if not hasattr(block, 'raw') or not isinstance(block.raw, dict):
        return None, None
    
    raw_block = block.raw
    nested_blocks = raw_block.get("blocks", [])
    
    table_html = None
    table_image_path = None
    
    for sub in nested_blocks:
        if not isinstance(sub, dict):
            continue
        if str(sub.get("type", "")) != "table_body":
            continue
        
        lines = sub.get("lines", [])
        for line in lines:
            if not isinstance(line, dict):
                continue
            spans = line.get("spans", [])
            for span in spans:
                if not isinstance(span, dict):
                    continue
                if span.get("type") == "table":
                    html = span.get("html")
                    if isinstance(html, str) and html.strip():
                        table_html = html
                    img_path = span.get("image_path")
                    if isinstance(img_path, str) and img_path.strip():
                        table_image_path = img_path
                    if table_html or table_image_path:
                        break
            if table_html or table_image_path:
                break
        if table_html or table_image_path:
            break
    
    # Also check block.image_path as fallback
    if not table_image_path and hasattr(block, 'image_path') and block.image_path:
        table_image_path = str(block.image_path)
    
    # CRITICAL: Ensure table HTML has proper closing tags.
    # Layout analysis tools (e.g. MinerU) may produce incomplete HTML that
    # breaks the markdown parser — everything after an unclosed <table> is
    # treated as raw HTML, so ![alt](data:...) images are never converted
    # to <img> tags.
    if table_html:
        table_html = _ensure_table_html_closed(table_html)
    
    return table_html, table_image_path


def _markdown_table_separator_index(lines: list[str]) -> int:
    """
    Return index of the first line that looks like a markdown table separator
    (only -, :, | and spaces; contains |). Requires at least one preceding line
    that contains |. Returns -1 if not found.
    Used so we can detect tables where the separator is not at line 1 (e.g. when
    cells contain newlines).
    """
    for i, line in enumerate(lines):
        if "|" not in line:
            continue
        stripped = line.replace(" ", "")
        if not stripped or not all(ch in "-:|" for ch in stripped):
            continue
        if i >= 1 and any("|" in lines[j] for j in range(i)):
            return i
    return -1


def _is_markdown_table(text: str) -> bool:
    """
    Heuristically detect whether a piece of text is a Markdown table.

    This is used to distinguish table body segments (which are generated from
    HTML via `_html_table_to_markdown`) from table caption/footnote segments,
    which are plain text but share the same layout block index.

    Tables with newlines inside cells have the separator row after more than one
    line (e.g. first row spans two lines, then "| --- | --- |"). We search for
    the first separator-like line instead of requiring it at index 1.
    """
    if not text:
        return False
    lines = [ln.rstrip() for ln in str(text).splitlines() if ln.strip()]
    if len(lines) < 2:
        return False
    return _markdown_table_separator_index(lines) >= 0


def _split_table_row(line: str) -> list[str]:
    """Split a markdown table row line into cell strings (shared helper)."""
    stripped = line.strip()
    if stripped.startswith("|"):
        stripped = stripped[1:]
    if stripped.endswith("|"):
        stripped = stripped[:-1]
    return [c.strip().replace("\\|", "|") for c in stripped.split("|")]


def _markdown_table_to_html(text: str) -> str:
    """
    Convert a simple markdown table (generated by _html_table_to_markdown)
    into an HTML <table> string.

    This is used in PDF HTML rebuild when we only have a translated markdown
    table body but still want HTML table output. When the separator row is at
    line index 1 (standard case), the original one-line-per-row logic is used
    so existing tables are unchanged. When the separator is later (e.g. cells
    contain newlines), a multi-line-aware parse is used.
    """
    if not _is_markdown_table(text):
        return text

    from html import escape

    lines = [ln.strip() for ln in str(text).splitlines() if ln.strip()]
    if len(lines) < 2:
        return text

    sep_idx = _markdown_table_separator_index(lines)
    if sep_idx < 0:
        return text

    col_count: int
    normalized_rows: list[list[str]]

    if sep_idx == 1:
        # Standard case: header at line 0, separator at 1, body from 2. Keep original behavior.
        header_cells = _split_table_row(lines[0])
        if not header_cells:
            return text
        col_count = len(header_cells)
        body_lines = lines[2:] if len(lines) > 2 else []
        body_rows = [_split_table_row(ln) for ln in body_lines]
        normalized_rows = []
        for row in body_rows:
            if len(row) < col_count:
                row = row + [""] * (col_count - len(row))
            elif len(row) > col_count:
                row = row[:col_count]
            normalized_rows.append(row)
    else:
        # Separator not at 1: header/rows may span multiple lines (e.g. newlines in cells).
        header_cells = _split_table_row("\n".join(lines[:sep_idx]))
        if not header_cells:
            return text
        col_count = len(header_cells)
        body_lines = lines[sep_idx + 1 :]
        normalized_rows = []
        accumulated: list[str] = []
        for line in body_lines:
            accumulated.append(line)
            cells = _split_table_row("\n".join(accumulated))
            if len(cells) == col_count:
                normalized_rows.append(cells)
                accumulated = []
            elif len(cells) > col_count:
                normalized_rows.append(cells[:col_count])
                accumulated = []
        if accumulated:
            cells = _split_table_row("\n".join(accumulated))
            normalized_rows.append((cells + [""] * col_count)[:col_count])

    parts: list[str] = []
    parts.append("<table>")

    # Header
    parts.append("<thead><tr>")
    for cell in header_cells:
        parts.append(f"<th>{escape(cell)}</th>")
    parts.append("</tr></thead>")

    # Body
    if normalized_rows:
        parts.append("<tbody>")
        for row in normalized_rows:
            parts.append("<tr>")
            for cell in row:
                parts.append(f"<td>{escape(cell)}</td>")
            parts.append("</tr>")
        parts.append("</tbody>")

    parts.append("</table>")
    return "".join(parts)


def _replace_table_cells_with_translations(
    table_html: str,
    table_block_idx: int,
    segments: List[Dict[str, Any]],
    block_index_to_type: Dict[int, str]
) -> Optional[str]:
    """
    Replace table cell content in HTML with translated text from segments.
    
    Args:
        table_html: Original HTML table string
        table_block_idx: Index of the table block in layout_document
        segments: List of translation segments with segment_info
        block_index_to_type: Mapping from block index to block type
        
    Returns:
        HTML table with translated cell content
    """
    try:
        # Build mapping from (table_idx, row_idx, cell_idx) to translated text
        # Collect all segments that belong to this table block
        cell_translations: Dict[Tuple[int, int, int], str] = {}
        for segment in segments:
            segment_info = segment.get("segment_info", {})
            if not segment_info.get("is_table_cell", False):
                continue
            
            # Check if this segment belongs to the same table block
            block_indices = segment.get("layout_block_indices", [])
            if table_block_idx not in block_indices:
                continue
            
            table_idx = segment_info.get("table_index")
            row_idx = segment_info.get("row_index")
            cell_idx = segment_info.get("cell_index")
            
            if table_idx is not None and row_idx is not None and cell_idx is not None:
                target_text = segment.get("modified_text") or segment.get("target_text", "")
                # CRITICAL: Even if segment is marked as failed, use target_text if it differs from source_text
                is_failed = segment.get("is_failed", False)
                source_text = segment.get("source_text", "")
                if is_failed and target_text and target_text.strip() != source_text.strip():
                    logger.debug(LogModule.RESTOR,
                        f"[HTML-REBUILD] Segment {segment.get('segment_index')} marked as FAILED, "
                        f"but using target_text for table cell: Table {table_idx}, Row {row_idx}, Cell {cell_idx}"
                    )
                
                if target_text:
                    cell_key = (table_idx, row_idx, cell_idx)
                    # If multiple segments map to same cell, concatenate them
                    if cell_key in cell_translations:
                        cell_translations[cell_key] += " " + target_text
                    else:
                        cell_translations[cell_key] = target_text
        
        if not cell_translations:
            # 对于当前 PDF 工作流，大多数情况下并没有单元格级别的 segment。
            # 如果这里直接返回原始 table_html，就会覆盖已经翻译好的 markdown 表格文本，
            # 导致导出的 HTML 表格还是源语言。
            #
            # 因此，当找不到任何单元格翻译时，返回 None，由调用方决定是否保留原有的
            # translated markdown 表格，而不是强制回退到原始 HTML。
            logger.warning(LogModule.RESTOR,
                f"[HTML-REBUILD] No translated segments found for table block {table_block_idx}, "
                f"will KEEP translated markdown table instead of original HTML. "
                f"Found {len([s for s in segments if s.get('segment_info', {}).get('is_table_cell')])} table cell segments total."
            )
            return None
        
        logger.info(
            LogModule.RESTOR,
            f"[HTML-REBUILD] Found {len(cell_translations)} translated cells for table block {table_block_idx}",
        )
        
        # Use BeautifulSoup if available for proper HTML parsing
        try:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(table_html, 'html.parser')
            
            # Find all table cells and replace content
            # We need to track row and cell positions as we iterate
            # CRITICAL: We need to identify which table this is (table_idx)
            # For now, we'll try to match by iterating through all tables and using the first matching one
            # In practice, we may need to track table indices more carefully
            tables = soup.find_all('table')
            if not tables:
                logger.warning(LogModule.RESTOR,f"[HTML-REBUILD] No <table> tags found in HTML, using original")
                return table_html
            
            # For now, assume the first table corresponds to table_idx=0
            # This may need to be improved if there are multiple tables
            table = tables[0] if len(tables) == 1 else tables[0]  # Use first table
            
            replaced_count = 0
            row_idx = 0
            for tr in table.find_all('tr'):
                cell_idx = 0
                for td in tr.find_all(['td', 'th']):
                    # Try to find matching translation
                    # Try table_idx=0 first (most common case)
                    cell_key = (0, row_idx, cell_idx)
                    if cell_key not in cell_translations:
                        # Try other table indices if available
                        found = False
                        for t_idx in range(1, 10):  # Try up to 10 tables
                            cell_key_alt = (t_idx, row_idx, cell_idx)
                            if cell_key_alt in cell_translations:
                                cell_key = cell_key_alt
                                found = True
                                break
                        if not found:
                            cell_idx += 1
                            continue
                    
                    translated_text = cell_translations[cell_key]
                    # Preserve existing HTML structure but replace text content
                    # Clear existing content and add translated text
                    original_text = td.get_text(strip=True)
                    td.clear()
                    td.string = translated_text
                    replaced_count += 1
                    logger.debug(LogModule.RESTOR,
                        f"[HTML-REBUILD] Replaced cell at Table {cell_key[0]}, Row {row_idx}, Cell {cell_idx}: "
                        f"'{original_text[:50]}...' -> '{translated_text[:50]}...'"
                    )
                    
                    cell_idx += 1
                row_idx += 1
            
            logger.info(
                LogModule.RESTOR,
                f"[HTML-REBUILD] Replaced {replaced_count} cells in table block {table_block_idx} "
                f"(out of {len(cell_translations)} available translations)",
            )
            return _close_unclosed_inline_tags(
                str(soup),
                log_context={"context": "table_cell", "table_block_idx": table_block_idx},
            )
        except ImportError:
            logger.warning(LogModule.RESTOR,
                "[HTML-REBUILD] BeautifulSoup not available, using original HTML table. "
                "Install beautifulsoup4 for table cell replacement."
            )
            return _close_unclosed_inline_tags(
                table_html,
                log_context={"context": "table_cell", "table_block_idx": table_block_idx},
            )
        except Exception as e:
            logger.error(LogModule.RESTOR,
                f"[HTML-REBUILD] Failed to replace table cell content: {e}",
                exc_info=True
            )
            return _close_unclosed_inline_tags(
                table_html,
                log_context={"context": "table_cell", "table_block_idx": table_block_idx},
            )

    except Exception as e:
        logger.error(LogModule.RESTOR,
            f"[HTML-REBUILD] Error replacing table cells: {e}",
            exc_info=True
        )
        if isinstance(table_html, str):
            return _close_unclosed_inline_tags(
                table_html,
                log_context={"context": "table_cell", "table_block_idx": table_block_idx},
            )
        return table_html


def _extract_equation_from_layout_block(block) -> tuple[Optional[str], Optional[str]]:
    """
    Extract equation LaTeX content and image path from layout block.
    
    Args:
        block: LayoutBlock instance
        
    Returns:
        Tuple of (equation_content, equation_image_path), both can be None
    """
    equation_content = None
    equation_image_path = None
    
    # Try block.text first (usually contains LaTeX)
    if hasattr(block, 'text') and block.text:
        equation_content = block.text.strip()
    
    # Extract from raw if available
    if hasattr(block, 'raw') and isinstance(block.raw, dict):
        raw_block = block.raw
        lines = raw_block.get("lines", [])
        for line in lines:
            if not isinstance(line, dict):
                continue
            spans = line.get("spans", [])
            for span in spans:
                if not isinstance(span, dict):
                    continue
                if span.get("type") == "interline_equation":
                    content = span.get("content")
                    if isinstance(content, str) and content.strip():
                        equation_content = content.strip()
                    img_path = span.get("image_path")
                    if img_path:
                        equation_image_path = str(img_path)
                    break
            if equation_content or equation_image_path:
                break
    
    # Use block.image_path as fallback
    if not equation_image_path and hasattr(block, 'image_path') and block.image_path:
        equation_image_path = block.image_path
    
    return equation_content, equation_image_path
