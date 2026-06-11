"""
Utilities for generating Markdown text and translation chunks directly from
layout documents. This allows PDF inputs to reuse the same chunk order for
translation and high-fidelity PDF reconstruction without relying on the
original Markdown exported by MinerU.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Literal, Optional
import re
from html.parser import HTMLParser

from layout.base import LayoutDocument
from logger import unified_logger as logger
from logger.logger import LogModule


ChunkType = Literal["text", "image", "table_body", "chart_body"]


@dataclass(frozen=True)
class LayoutChunk:
    """Represents a translation chunk derived from layout blocks."""

    text: str
    chunk_type: ChunkType
    block_indices: List[int]
    block_texts: Optional[List[str]] = None  # Text content per block index (in order)
    image_path: Optional[str] = None
    image_placeholder: Optional[str] = None
    image_alt: Optional[str] = None


@dataclass(frozen=True)
class LayoutMarkdownResult:
    """Markdown text plus chunk metadata derived from layout."""

    markdown_text: str
    chunks: List[LayoutChunk]


class LayoutMarkdownBuilder:
    """
    Build Markdown text and translation chunks directly from LayoutDocument.
    
    The builder preserves reading order (page -> y -> x) and groups small
    blocks together to honour the desired chunk size so that the translation
    agent can process the text efficiently while we retain the mapping between
    chunks and layout blocks.
    """

    def __init__(
        self,
        max_chunk_chars: int = 2000,
        include_images: bool = True,
        deep_split: bool = True,
        equation_format: str = "text",  # "text" or "image" for interline_equation blocks
        table_body_format: str = "html",  # "html" or "image" for table blocks
        chart_body_format: str = "image",  # "image" or "html" for chart blocks (default: image for safety)
        include_structural_blocks: bool = False,  # If True, include header/footer/page_number blocks (for Extract phase)
    ):
        self.max_chunk_chars = max_chunk_chars
        self.include_images = include_images
        self.deep_split = deep_split
        self.equation_format = equation_format
        self.table_body_format = table_body_format
        self.chart_body_format = chart_body_format
        self.include_structural_blocks = include_structural_blocks
        self._image_counter = 0

    def _next_image_placeholder(self) -> str:
        placeholder = f"layoutimg{self._image_counter}"
        self._image_counter += 1
        return placeholder


class _TableCell:
    """Represents a table cell with rowspan and colspan information."""
    def __init__(self, text: str, rowspan: int = 1, colspan: int = 1):
        self.text = text
        self.rowspan = rowspan
        self.colspan = colspan


class _TableHTMLParser(HTMLParser):
    """HTML parser to extract table rows and cells, handling rowspan and colspan."""

    def __init__(self) -> None:
        super().__init__()
        self._in_cell = False
        self._current_cell_parts: List[str] = []
        self._current_rowspan = 1
        self._current_colspan = 1
        # Store cells as they are parsed (row by row)
        self._raw_rows: List[List[_TableCell]] = []
        self._current_row: List[_TableCell] = []

    def handle_starttag(self, tag, attrs):
        if tag in ("td", "th"):
            self._in_cell = True
            self._current_cell_parts = []
            # Extract rowspan and colspan attributes
            self._current_rowspan = 1
            self._current_colspan = 1
            for attr_name, attr_value in attrs:
                if attr_name == "rowspan":
                    try:
                        self._current_rowspan = int(attr_value)
                    except (ValueError, TypeError):
                        self._current_rowspan = 1
                elif attr_name == "colspan":
                    try:
                        self._current_colspan = int(attr_value)
                    except (ValueError, TypeError):
                        self._current_colspan = 1
        elif tag == "tr":
            # Start new row: save previous row if it exists and has cells
            if self._current_row:
                self._raw_rows.append(self._current_row)
            self._current_row = []

    def handle_endtag(self, tag):
        if tag in ("td", "th"):
            self._in_cell = False
            cell_text = "".join(self._current_cell_parts).strip()
            # Create cell with rowspan/colspan info
            cell = _TableCell(cell_text, self._current_rowspan, self._current_colspan)
            self._current_row.append(cell)
        elif tag == "tr":
            # End of row: save it if it has cells
            if hasattr(self, '_current_row') and self._current_row:
                self._raw_rows.append(self._current_row)
            self._current_row = []

    def handle_data(self, data):
        if self._in_cell:
            self._current_cell_parts.append(data)
    
    def _expand_table(self) -> List[List[str]]:
        """Expand table cells considering rowspan and colspan to create a 2D grid."""
        if not self._raw_rows:
            return []
        
        # First pass: determine maximum columns needed
        max_cols = 0
        for row in self._raw_rows:
            col_count = sum(cell.colspan for cell in row)
            max_cols = max(max_cols, col_count)
        
        # Create expanded grid: grid[row][col] = cell text or None if occupied by rowspan
        expanded: List[List[Optional[str]]] = []
        # Track which positions are occupied by rowspans from previous rows
        # occupied[row][col] = True if this position is occupied by a rowspan
        occupied: List[List[bool]] = []
        
        for row_idx, row in enumerate(self._raw_rows):
            # Initialize row if needed
            while len(expanded) <= row_idx:
                expanded.append([None] * max_cols)
                occupied.append([False] * max_cols)
            
            col_idx = 0
            for cell in row:
                # Skip columns already occupied by rowspan from previous rows
                while col_idx < max_cols and occupied[row_idx][col_idx]:
                    col_idx += 1
                
                # Place cell with colspan expansion
                for c in range(cell.colspan):
                    if col_idx + c < max_cols:
                        expanded[row_idx][col_idx + c] = cell.text
                        
                        # If rowspan > 1, mark subsequent rows as occupied
                        if cell.rowspan > 1:
                            for r in range(1, cell.rowspan):
                                target_row = row_idx + r
                                # Ensure target row exists
                                while len(expanded) <= target_row:
                                    expanded.append([None] * max_cols)
                                    occupied.append([False] * max_cols)
                                # Mark position as occupied and fill with cell text
                                if col_idx + c < max_cols:
                                    occupied[target_row][col_idx + c] = True
                                    expanded[target_row][col_idx + c] = cell.text
                
                col_idx += cell.colspan
        
        # Convert to list of lists of strings, replacing None with empty string
        result: List[List[str]] = []
        for row in expanded:
            result.append([cell if cell is not None else "" for cell in row])
        
        return result
    
    @property
    def rows(self) -> List[List[str]]:
        """Get expanded table rows as list of string lists."""
        return self._expand_table()


    # Note: _TableHTMLParser is only responsible for parsing table HTML.
    # The main build logic for LayoutDocument lives on LayoutMarkdownBuilder below.


    # -------------------------------------------------------------------------
    # LayoutMarkdownBuilder.build
    # -------------------------------------------------------------------------

    # Attach the main build routine to LayoutMarkdownBuilder so callers such as
    # MarkdownBasedWorkflow and preview generation can use `builder.build(...)`.

def _extract_text_from_block(block) -> str:
    """
    Extract text from a layout block.

    优先使用 block.text；如果为空，则从 block.raw 的 lines/spans/content 里提取，
    避免像图注这类只存在于 raw 里的文本被完全跳过。
    """
    text = (getattr(block, "text", None) or "").strip()
    if text:
        # Log caption-like blocks for debugging (e.g. image_caption)
        if getattr(block, "type", "") in ("image_caption", "caption"):
            logger.info(LogModule.LAYOUT, "[LAYOUT] Caption text extracted from block "
                f"index={getattr(block, 'index', None)}, "
                f"page={getattr(block, 'page_index', None)}, "
                f"type={getattr(block, 'type', None)}, "
                f"text_preview={text[:120]!r}"
            )
        return text

    raw = getattr(block, "raw", None)
    if not isinstance(raw, dict):
        return ""

    # 尝试从 raw.text 直接拿
    raw_text = raw.get("text")
    if isinstance(raw_text, str) and raw_text.strip():
        text = raw_text.strip()
        if getattr(block, "type", "") in ("image_caption", "caption"):
            logger.info(LogModule.LAYOUT, "[LAYOUT] Caption raw.text extracted from block "
                f"index={getattr(block, 'index', None)}, "
                f"page={getattr(block, 'page_index', None)}, "
                f"type={getattr(block, 'type', None)}, "
                f"text_preview={text[:120]!r}"
            )
        return text
    if isinstance(raw_text, list):
        joined = " ".join(str(t) for t in raw_text if str(t).strip())
        if joined.strip():
            text = joined.strip()
            if getattr(block, "type", "") in ("image_caption", "caption"):
                logger.info(LogModule.LAYOUT, "[LAYOUT] Caption raw.text(list) extracted from block "
                    f"index={getattr(block, 'index', None)}, "
                    f"page={getattr(block, 'page_index', None)}, "
                    f"type={getattr(block, 'type', None)}, "
                    f"text_preview={text[:120]!r}"
                )
            return text

    # 从 lines -> spans -> content 聚合（当前 block 自己）
    lines = raw.get("lines") or []
    parts: list[str] = []
    for line in lines:
        if not isinstance(line, dict):
            continue
        spans = line.get("spans") or []
        for span in spans:
            if not isinstance(span, dict):
                continue
            content = span.get("content")
            if isinstance(content, str) and content.strip():
                parts.append(content.strip())
            elif span.get("type") == "text":
                span_text = span.get("text")
                if isinstance(span_text, str) and span_text.strip():
                    parts.append(span_text.strip())
    merged = " ".join(parts).strip()
    if merged:
        if getattr(block, "type", "") in ("image_caption", "caption"):
            logger.info(LogModule.LAYOUT, "[LAYOUT] Caption text merged from lines/spans for block "
                f"index={getattr(block, 'index', None)}, "
                f"page={getattr(block, 'page_index', None)}, "
                f"type={getattr(block, 'type', None)}, "
                f"text_preview={merged[:120]!r}"
            )
        return merged

    # 对于像参考文献这种结构，文本往往藏在 raw.blocks[*].lines[*].spans[*].content 里
    # 例如：外层 type=list，内层 type=ref_text。
    blocks = raw.get("blocks") or []
    nested_block_texts: list[str] = []
    for sub in blocks:
        if not isinstance(sub, dict):
            continue
        sub_lines = sub.get("lines") or []
        sub_parts: list[str] = []
        for line in sub_lines:
            if not isinstance(line, dict):
                continue
            spans = line.get("spans") or []
            for span in spans:
                if not isinstance(span, dict):
                    continue
                content = span.get("content")
                if isinstance(content, str) and content.strip():
                    sub_parts.append(content.strip())
                elif span.get("type") == "text":
                    span_text = span.get("text")
                    if isinstance(span_text, str) and span_text.strip():
                        sub_parts.append(span_text.strip())
        sub_merged = " ".join(sub_parts).strip()
        if sub_merged:
            nested_block_texts.append(sub_merged)

    if nested_block_texts:
        nested_merged = "\n".join(nested_block_texts)
        block_type = getattr(block, "type", "")
        if block_type in ("list", "ref_list", "references"):
            logger.info(LogModule.LAYOUT, "[LAYOUT] Nested reference-like text extracted from block "
                f"index={getattr(block, 'index', None)}, "
                f"page={getattr(block, 'page_index', None)}, "
                f"type={block_type}, "
                f"nested_count={len(nested_block_texts)}, "
                f"first_preview={nested_merged.splitlines()[0][:120]!r}"
            )
        return nested_merged

    return ""


def _split_block_text_for_builder(text: str, max_chunk_chars: int) -> List[str]:
    """Split a long block of text into sub-pieces under max_chunk_chars."""
    if len(text) <= max_chunk_chars:
        return [text]

    pieces: List[str] = []
    start = 0
    text_len = len(text)
    while start < text_len:
        remaining = text_len - start
        if remaining <= max_chunk_chars:
            pieces.append(text[start:].strip())
            break

        tentative_end = start + max_chunk_chars
        split_pos = max(
            text.rfind("\n\n", start, tentative_end),
            text.rfind(". ", start, tentative_end),
            text.rfind(" ", start, tentative_end),
        )
        if split_pos == -1 or split_pos <= start + int(max_chunk_chars * 0.5):
            split_pos = tentative_end

        pieces.append(text[start:split_pos].strip())
        start = split_pos
    return [p for p in pieces if p]


def _html_table_to_markdown(html_str: str) -> str:
    """Convert HTML table string to a simple markdown-style table."""
    parser = _TableHTMLParser()
    try:
        parser.feed(html_str)
    except Exception as e:  # pragma: no cover - defensive
        logger.warning(LogModule.LAYOUT, f"[LAYOUT] Failed to parse table HTML for markdown conversion: {e}")
        return html_str
    rows = parser.rows
    if not rows:
        return html_str
    md_lines: List[str] = []
    for i, row in enumerate(rows):
        # Escape pipe
        safe_cells = [cell.replace("|", "\\|") for cell in row]
        md_lines.append("| " + " | ".join(safe_cells) + " |")
        if i == 0:
            md_lines.append("| " + " | ".join(["---"] * len(row)) + " |")
    return "\n".join(md_lines)


def _sorted_layout_blocks(layout_doc: LayoutDocument):
    """Sort blocks by (page_index, y, x) to preserve reading order."""
    return sorted(
        layout_doc.iter_blocks(),
        key=lambda block: (
            getattr(block, "page_index", 0),
            block.bbox[1] if block.bbox else 0.0,
            block.bbox[0] if block.bbox else 0.0,
        ),
    )


def _paragraph_split(text: str) -> List[str]:
    """Heuristic paragraph splitter used when deep_split is enabled."""
    import re

    paragraphs = re.split(r"\n{2,}", text)
    paragraphs = [p.strip() for p in paragraphs if p.strip()]

    if len(paragraphs) == 1 and "\n" in paragraphs[0]:
        lines = paragraphs[0].split("\n")
        lines = [line.strip() for line in lines if line.strip()]

        if len(lines) > 1:
            detected_paragraphs: List[str] = []
            current_para: List[str] = []

            for i, line in enumerate(lines):
                current_para.append(line)

                is_break = False
                if i < len(lines) - 1:
                    next_line = lines[i + 1]

                    if re.search(r"[.!?。！？]\s*$", line):
                        if (
                            next_line
                            and (
                                next_line[0].isupper()
                                or next_line[0].isdigit()
                                or next_line[0] in "（("
                            )
                        ):
                            is_break = True

                    if re.search(r"[:;：；]\s*$", line):
                        if next_line and next_line[0].isupper():
                            is_break = True

                    if len(line) < 40 and i > 0 and len(next_line) > 50:
                        is_break = True

                    if len(line) > 150 and next_line and next_line[0].isupper():
                        is_break = True

                if is_break or i == len(lines) - 1:
                    para_text = " ".join(current_para).strip()
                    if para_text:
                        detected_paragraphs.append(para_text)
                    current_para = []

            if len(detected_paragraphs) > 1:
                paragraphs = detected_paragraphs
            elif len(lines) >= 2:
                independent_lines: List[str] = []
                for line in lines:
                    if re.search(r"[.!?。！？]\s*$", line) or len(line) > 80:
                        independent_lines.append(line)
                    else:
                        if independent_lines:
                            independent_lines[-1] += " " + line
                        else:
                            independent_lines.append(line)

                if len(independent_lines) > 1:
                    paragraphs = independent_lines
                elif len(lines) > 3:
                    paragraphs = lines

    return paragraphs


def _flush_text_chunk(
    chunks: List[LayoutChunk],
    current_text_parts: List[str],
    current_block_sequence: List[int],
) -> None:
    if not current_text_parts:
        return

    text_content = "\n".join(part for part in current_text_parts if part).strip()
    if not text_content:
        current_text_parts.clear()
        current_block_sequence.clear()
        return

    block_text_pairs: List[tuple[int, List[str]]] = []
    for idx, piece in zip(current_block_sequence, current_text_parts):
        if idx < 0:
            continue
        if block_text_pairs and block_text_pairs[-1][0] == idx:
            block_text_pairs[-1][1].append(piece)
        else:
            block_text_pairs.append((idx, [piece]))

    block_indices_compact: List[int] = []
    block_texts_compact: List[str] = []
    for idx, pieces in block_text_pairs:
        normalized_text = "\n".join(p for p in pieces if p).strip()
        if not normalized_text:
            continue
        block_indices_compact.append(idx)
        block_texts_compact.append(normalized_text)

    chunks.append(
        LayoutChunk(
            text=text_content,
            chunk_type="text",
            block_indices=block_indices_compact,
            block_texts=block_texts_compact,
            image_path=None,
        )
    )

    current_text_parts.clear()
    current_block_sequence.clear()


def _append_text_piece_for_builder(
    piece: str,
    block_index: int,
    max_chunk_chars: int,
    current_text_parts: List[str],
    current_block_sequence: List[int],
    current_chars_ref: List[int],
    chunks: List[LayoutChunk],
) -> None:
    if not piece:
        return
    piece_len = len(piece)
    current_chars = current_chars_ref[0]
    if current_text_parts and current_chars + piece_len + 1 > max_chunk_chars:
        _flush_text_chunk(chunks, current_text_parts, current_block_sequence)
        current_chars = 0

    current_text_parts.append(piece)
    current_block_sequence.append(block_index)
    current_chars_ref[0] = current_chars + piece_len + 1


def _build_layout_markdown(
    builder: LayoutMarkdownBuilder, layout_doc: LayoutDocument
) -> LayoutMarkdownResult:
    chunks: List[LayoutChunk] = []

    # Use layout blocks in their original order (optimized by layout algorithm)
    # Do not apply additional sorting - layout order is already optimized
    blocks = list(layout_doc.iter_blocks())

    current_text_parts: List[str] = []
    current_block_sequence: List[int] = []
    current_chars_ref = [0]
    last_page_index: int | None = None

    for block in blocks:
        block_index = block.index if block.index is not None else -1

        # Skip header, footer, and page_number blocks when exporting to markdown
        # Unless include_structural_blocks is True (for Extract phase, where user can choose to exclude them)
        if not builder.include_structural_blocks and block.type in ("header", "footer", "page_number"):
            logger.debug(LogModule.LAYOUT, f"[LAYOUT] Skipping {block.type} block: "
                f"page={block.page_index}, block_index={block_index}"
            )
            continue
        
        # Log when including structural blocks (for debugging header/footer detection)
        if builder.include_structural_blocks and block.type in ("header", "footer", "page_number"):
            logger.info(LogModule.LAYOUT, f"[LAYOUT] Including {block.type} block: "
                f"page={block.page_index}, block_index={block_index}, "
                f"text_preview={block.text[:50] if block.text else 'empty'}..."
            )

        if last_page_index is not None and block.page_index != last_page_index:
            _flush_text_chunk(chunks, current_text_parts, current_block_sequence)
            current_chars_ref[0] = 0
        last_page_index = block.page_index

        if builder.deep_split and current_text_parts:
            _flush_text_chunk(chunks, current_text_parts, current_block_sequence)
            current_chars_ref[0] = 0

        if block.type == "image" and builder.include_images:
            _flush_text_chunk(chunks, current_text_parts, current_block_sequence)
            current_chars_ref[0] = 0

            placeholder_id = builder._next_image_placeholder()
            image_text = f"<ph-{placeholder_id}>"

            raw_block = block.raw or {}
            image_alt = raw_block.get("text") if isinstance(raw_block, dict) else None

            caption_text = None
            if isinstance(raw_block, dict):
                nested_blocks = raw_block.get("blocks") or []
                for sub in nested_blocks:
                    if not isinstance(sub, dict):
                        continue
                    sub_type = str(sub.get("type", ""))
                    if sub_type in ("image_caption", "caption"):
                            lines = sub.get("lines") or []
                            line_texts: list[str] = []
                            for line in lines:
                                if not isinstance(line, dict):
                                    continue
                                spans = line.get("spans") or []
                                line_parts: list[str] = []
                                for span in spans:
                                    if not isinstance(span, dict):
                                        continue
                                    content = span.get("content")
                                    if isinstance(content, str) and content.strip():
                                        line_parts.append(content.strip())
                                    elif span.get("type") == "text":
                                        span_text = span.get("text")
                                        if isinstance(span_text, str) and span_text.strip():
                                            line_parts.append(span_text.strip())
                                if line_parts:
                                    # Join spans within the same line with space
                                    line_text = " ".join(line_parts).strip()
                                    if line_text:
                                        line_texts.append(line_text)
                            # Join different lines with newline to preserve multi-line structure
                            merged_caption = "\n".join(line_texts).strip()
                            if merged_caption:
                                caption_text = merged_caption
                                logger.debug(LogModule.LAYOUT, "[LAYOUT] Image caption extracted from nested block "
                                    f"page={block.page_index}, block_index={block_index}, "
                                    f"text_preview={caption_text[:120]!r}"
                                )
                                break

            if not caption_text and isinstance(image_alt, str):
                lines = [ln.strip() for ln in image_alt.splitlines() if ln.strip()]
                non_path_lines = [
                    ln
                    for ln in lines
                    if not re.search(r"\.(png|jpe?g|gif|webp|svg)\b", ln, re.IGNORECASE)
                ]
                joined = " ".join(non_path_lines).strip()
                if joined:
                    caption_text = joined

            chunks.append(
                LayoutChunk(
                    text=image_text,
                    chunk_type="image",
                    block_indices=[block_index] if block_index >= 0 else [],
                    image_path=block.image_path,
                    image_placeholder=placeholder_id,
                    image_alt=image_alt.strip() if isinstance(image_alt, str) else None,
                )
            )

            if caption_text:
                logger.debug(LogModule.LAYOUT, "[LAYOUT] Image caption will be added as separate text segment: "
                    f"block_index={block_index}, page={block.page_index}, "
                    f"text_preview={caption_text[:120]!r}"
                )
                _append_text_piece_for_builder(
                    caption_text,
                    block_index,
                    builder.max_chunk_chars,
                    current_text_parts,
                    current_block_sequence,
                    current_chars_ref,
                    chunks,
                )
                _flush_text_chunk(chunks, current_text_parts, current_block_sequence)
                current_chars_ref[0] = 0

            continue

        if block.type == "table":
            _flush_text_chunk(chunks, current_text_parts, current_block_sequence)
            current_chars_ref[0] = 0

            raw_block = block.raw or {}
            nested_blocks = (
                raw_block.get("blocks") or [] if isinstance(raw_block, dict) else []
            )

            # Extract table components in order: caption first, then body, then footnotes
            caption_text = None
            for sub in nested_blocks:
                if not isinstance(sub, dict):
                    continue
                sub_type = str(sub.get("type", ""))
                if sub_type == "table_caption":
                    lines = sub.get("lines") or []
                    line_texts: list[str] = []
                    for line in lines:
                        if not isinstance(line, dict):
                            continue
                        spans = line.get("spans") or []
                        line_parts: list[str] = []
                        for span in spans:
                            if not isinstance(span, dict):
                                continue
                            content = span.get("content")
                            if isinstance(content, str) and content.strip():
                                line_parts.append(content.strip())
                            elif span.get("type") == "text":
                                span_text = span.get("text")
                                if isinstance(span_text, str) and span_text.strip():
                                    line_parts.append(span_text.strip())
                        if line_parts:
                            # Join spans within the same line with space
                            line_text = " ".join(line_parts).strip()
                            if line_text:
                                line_texts.append(line_text)
                    # Join different lines with newline to preserve multi-line structure
                    merged_caption = "\n".join(line_texts).strip()
                    if merged_caption:
                        caption_text = merged_caption
                        logger.debug(LogModule.LAYOUT, "[LAYOUT] Table caption extracted from nested block "
                            f"page={block.page_index}, block_index={block_index}, "
                            f"text_preview={caption_text[:120]!r}"
                        )
                        break

            # Extract table body (HTML and image_path)
            table_html: Optional[str] = None
            table_image_path_from_span: Optional[str] = None
            for sub in nested_blocks:
                if not isinstance(sub, dict):
                    continue
                if str(sub.get("type", "")) != "table_body":
                    continue
                lines = sub.get("lines") or []
                for line in lines:
                    if not isinstance(line, dict):
                        continue
                    spans = line.get("spans") or []
                    for span in spans:
                        if not isinstance(span, dict):
                            continue
                        if span.get("type") == "table":
                            # Extract HTML format
                            html = span.get("html")
                            if isinstance(html, str) and html.strip():
                                table_html = html
                            # Extract image_path (for image format)
                            img_path = span.get("image_path")
                            if isinstance(img_path, str) and img_path.strip():
                                table_image_path_from_span = img_path
                            if table_html or table_image_path_from_span:
                                break
                    if table_html or table_image_path_from_span:
                        break
                if table_html or table_image_path_from_span:
                    break

            # Extract table footnotes
            footnote_texts: list[str] = []
            for sub in nested_blocks:
                if not isinstance(sub, dict):
                    continue
                sub_type = str(sub.get("type", ""))
                if sub_type == "table_footnote":
                    lines = sub.get("lines") or []
                    line_texts: list[str] = []
                    for line in lines:
                        if not isinstance(line, dict):
                            continue
                        spans = line.get("spans") or []
                        line_parts: list[str] = []
                        for span in spans:
                            if not isinstance(span, dict):
                                continue
                            content = span.get("content")
                            if isinstance(content, str) and content.strip():
                                line_parts.append(content.strip())
                            elif span.get("type") == "text":
                                span_text = span.get("text")
                                if isinstance(span_text, str) and span_text.strip():
                                    line_parts.append(span_text.strip())
                        if line_parts:
                            # Join spans within the same line with space
                            line_text = " ".join(line_parts).strip()
                            if line_text:
                                line_texts.append(line_text)
                    # Join different lines with newline to preserve multi-line structure
                    merged_footnote = "\n".join(line_texts).strip()
                    if merged_footnote:
                        footnote_texts.append(merged_footnote)
                        logger.info(LogModule.LAYOUT, "[LAYOUT] Table footnote extracted from nested block "
                            f"page={block.page_index}, block_index={block_index}, "
                            f"text_preview={merged_footnote[:120]!r}"
                        )

            # Add table components in correct order: caption -> body -> footnotes
            # 1. Table caption (first)
            if caption_text:
                logger.info(LogModule.LAYOUT, "[LAYOUT] Table caption will be added as separate text segment (before table body): "
                    f"block_index={block_index}, page={block.page_index}, "
                    f"text_preview={caption_text[:120]!r}"
                )
                _append_text_piece_for_builder(
                    caption_text,
                    block_index,
                    builder.max_chunk_chars,
                    current_text_parts,
                    current_block_sequence,
                    current_chars_ref,
                    chunks,
                )
                _flush_text_chunk(chunks, current_text_parts, current_block_sequence)
                current_chars_ref[0] = 0

            # 2. Table body (middle)
            # Check table format preference (image vs html/text)
            table_body_format = builder.table_body_format
            # Try to get image_path from nested spans first, fallback to block.image_path
            table_image_path = table_image_path_from_span or block.image_path
            
            if table_body_format == "image" and table_image_path:
                # Use image format for table
                placeholder_id = builder._next_image_placeholder()
                image_text = f"![Table]({placeholder_id})"
                logger.info(LogModule.LAYOUT, "[LAYOUT] Table body will be rendered as image: "
                    f"page={block.page_index}, block_index={block_index}, "
                    f"image_path={table_image_path}"
                )
                chunks.append(
                    LayoutChunk(
                        text=image_text,
                        chunk_type="image",
                        block_indices=[block_index] if block_index >= 0 else [],
                        image_path=table_image_path,
                        image_placeholder=placeholder_id,
                        image_alt="Table",
                    )
                )
            elif table_html:
                # Use HTML/text format for table (convert to markdown).
                # For translation, keep the entire table body as a single segment so that
                # the Translate view and downstream rebuild logic treat the table as one unit.
                table_markdown = _html_table_to_markdown(table_html)
                lines = table_markdown.splitlines()

                # Log basic preview for debugging
                first_line_preview = lines[0][:120] if lines else ""
                logger.debug(
                    LogModule.LAYOUT,
                    "[LAYOUT] Table body converted to markdown-like text: "
                    f"page={block.page_index}, block_index={block_index}, "
                    f"text_preview={first_line_preview!r}"
                )

                # Keep entire table body as a single segment (one block = one segment).
                # Use chunk_type="table_body" so downstream (status_service, exclusion) can trust
                # layout instead of string-based table detection (e.g. tables with newlines in cells).
                _flush_text_chunk(chunks, current_text_parts, current_block_sequence)
                current_chars_ref[0] = 0
                chunks.append(
                    LayoutChunk(
                        text=table_markdown,
                        chunk_type="table_body",
                        block_indices=[block_index] if block_index >= 0 else [],
                        block_texts=[table_markdown],
                        image_path=None,
                    )
                )

            # 3. Table footnotes (last)
            for footnote_text in footnote_texts:
                logger.info(LogModule.LAYOUT, "[LAYOUT] Table footnote will be added as separate text segment (after table body): "
                    f"block_index={block_index}, page={block.page_index}, "
                    f"text_preview={footnote_text[:120]!r}"
                )
                _append_text_piece_for_builder(
                    footnote_text,
                    block_index,
                    builder.max_chunk_chars,
                    current_text_parts,
                    current_block_sequence,
                    current_chars_ref,
                    chunks,
                )
                _flush_text_chunk(chunks, current_text_parts, current_block_sequence)
                current_chars_ref[0] = 0

            continue

        # Handle chart blocks (similar to table handling)
        if block.type == "chart":
            _flush_text_chunk(chunks, current_text_parts, current_block_sequence)
            current_chars_ref[0] = 0

            raw_block = block.raw or {}
            nested_blocks = (
                raw_block.get("blocks") or [] if isinstance(raw_block, dict) else []
            )

            # Extract chart components: caption, body (with markdown table content and image), footnotes
            caption_text = None
            for sub in nested_blocks:
                if not isinstance(sub, dict):
                    continue
                sub_type = str(sub.get("type", ""))
                if sub_type == "chart_caption":
                    lines = sub.get("lines") or []
                    line_texts: list[str] = []
                    for line in lines:
                        if not isinstance(line, dict):
                            continue
                        spans = line.get("spans") or []
                        line_parts: list[str] = []
                        for span in spans:
                            if not isinstance(span, dict):
                                continue
                            content = span.get("content")
                            if isinstance(content, str) and content.strip():
                                line_parts.append(content.strip())
                            elif span.get("type") == "text":
                                span_text = span.get("text")
                                if isinstance(span_text, str) and span_text.strip():
                                    line_parts.append(span_text.strip())
                        if line_parts:
                            line_text = " ".join(line_parts).strip()
                            if line_text:
                                line_texts.append(line_text)
                    merged_caption = "\n".join(line_texts).strip()
                    if merged_caption:
                        caption_text = merged_caption
                        logger.debug(LogModule.LAYOUT, "[LAYOUT] Chart caption extracted from nested block "
                            f"page={block.page_index}, block_index={block_index}, "
                            f"text_preview={caption_text[:120]!r}"
                        )
                        break

            # Extract chart body (markdown table content and image_path)
            chart_content: Optional[str] = None
            chart_image_path: Optional[str] = None
            for sub in nested_blocks:
                if not isinstance(sub, dict):
                    continue
                if str(sub.get("type", "")) != "chart_body":
                    continue
                lines = sub.get("lines") or []
                for line in lines:
                    if not isinstance(line, dict):
                        continue
                    spans = line.get("spans") or []
                    for span in spans:
                        if not isinstance(span, dict):
                            continue
                        if span.get("type") == "chart":
                            # Extract markdown table content
                            content = span.get("content")
                            if isinstance(content, str) and content.strip():
                                chart_content = content
                            # Extract image_path
                            img_path = span.get("image_path")
                            if isinstance(img_path, str) and img_path.strip():
                                chart_image_path = img_path
                            if chart_content or chart_image_path:
                                break
                    if chart_content or chart_image_path:
                        break
                if chart_content or chart_image_path:
                    break

            # Use block.image_path as fallback
            if not chart_image_path and block.image_path:
                chart_image_path = block.image_path

            # Add chart components in order: caption -> body
            # 1. Chart caption (first, always translated)
            if caption_text:
                logger.info(LogModule.LAYOUT, "[LAYOUT] Chart caption will be added as separate text segment (before chart body): "
                    f"block_index={block_index}, page={block.page_index}, "
                    f"text_preview={caption_text[:120]!r}"
                )
                _append_text_piece_for_builder(
                    caption_text,
                    block_index,
                    builder.max_chunk_chars,
                    current_text_parts,
                    current_block_sequence,
                    current_chars_ref,
                    chunks,
                )
                _flush_text_chunk(chunks, current_text_parts, current_block_sequence)
                current_chars_ref[0] = 0

            # 2. Chart body (based on chart_body_format)
            chart_body_format = builder.chart_body_format
            if chart_body_format == "image" and chart_image_path:
                # Use image format for chart
                placeholder_id = builder._next_image_placeholder()
                image_text = f"![Chart]({placeholder_id})"
                logger.info(LogModule.LAYOUT, "[LAYOUT] Chart body will be rendered as image: "
                    f"page={block.page_index}, block_index={block_index}, "
                    f"image_path={chart_image_path}"
                )
                chunks.append(
                    LayoutChunk(
                        text=image_text,
                        chunk_type="chart_body",  # Keep as chart_body for exclusion detection, even when rendered as image
                        block_indices=[block_index] if block_index >= 0 else [],
                        image_path=chart_image_path,
                        image_placeholder=placeholder_id,
                        image_alt="Chart",
                    )
                )
            elif chart_content:
                # Use HTML/text format for chart (treat as markdown table)
                # For translation, keep the entire chart body as a single segment
                logger.debug(
                    LogModule.LAYOUT,
                    "[LAYOUT] Chart body kept as markdown table text: "
                    f"page={block.page_index}, block_index={block_index}, "
                    f"text_preview={chart_content[:120]!r}"
                )
                _flush_text_chunk(chunks, current_text_parts, current_block_sequence)
                current_chars_ref[0] = 0
                chunks.append(
                    LayoutChunk(
                        text=chart_content,
                        chunk_type="chart_body",
                        block_indices=[block_index] if block_index >= 0 else [],
                        block_texts=[chart_content],
                        image_path=None,
                    )
                )

            continue

        # Handle interline_equation blocks (similar to table handling)
        if block.type == "interline_equation":
            _flush_text_chunk(chunks, current_text_parts, current_block_sequence)
            current_chars_ref[0] = 0

            # Extract equation content and image path from block
            raw_block = block.raw or {}
            equation_content = None
            equation_image_path = None
            
            # Extract from lines -> spans -> content/image_path
            lines = raw_block.get("lines", [])
            for line in lines:
                if not isinstance(line, dict):
                    continue
                spans = line.get("spans", [])
                for span in spans:
                    if not isinstance(span, dict):
                        continue
                    if span.get("type") == "interline_equation":
                        # Get LaTeX content
                        content = span.get("content")
                        if isinstance(content, str) and content.strip():
                            equation_content = content.strip()
                        # Get image path
                        img_path = span.get("image_path")
                        if img_path:
                            equation_image_path = str(img_path)
                        break
                if equation_content or equation_image_path:
                    break
            
            # Use block.text as fallback for content
            if not equation_content and block.text:
                equation_content = block.text.strip()
            
            # Use block.image_path as fallback for image
            if not equation_image_path and block.image_path:
                equation_image_path = block.image_path
            
            # Get equation format from builder config
            equation_format = builder.equation_format
            
            if equation_format == "image" and equation_image_path:
                # Render as image (markdown image syntax)
                image_markdown = f"![Equation]({equation_image_path})"
                logger.info(LogModule.LAYOUT, "[LAYOUT] Interline equation rendered as image: "
                    f"page={block.page_index}, block_index={block_index}, "
                    f"image_path={equation_image_path}"
                )
                _append_text_piece_for_builder(
                    image_markdown,
                    block_index,
                    builder.max_chunk_chars,
                    current_text_parts,
                    current_block_sequence,
                    current_chars_ref,
                    chunks,
                )
            elif equation_content:
                # Render as text (LaTeX formula)
                # Wrap in math block for markdown rendering
                equation_markdown = f"$$\n{equation_content}\n$$"
                logger.info(LogModule.LAYOUT, "[LAYOUT] Interline equation rendered as text: "
                    f"page={block.page_index}, block_index={block_index}, "
                    f"content_preview={equation_content[:120]!r}"
                )
                _append_text_piece_for_builder(
                    equation_markdown,
                    block_index,
                    builder.max_chunk_chars,
                    current_text_parts,
                    current_block_sequence,
                    current_chars_ref,
                    chunks,
                )
            else:
                logger.warning(LogModule.LAYOUT, "[LAYOUT] Interline equation block has no content or image: "
                    f"page={block.page_index}, block_index={block_index}"
                )
            
            _flush_text_chunk(chunks, current_text_parts, current_block_sequence)
            current_chars_ref[0] = 0
            continue

        text = _extract_text_from_block(block)
        if not text:
            continue

        # Convert title blocks to markdown heading format
        # Use heading level inferred from MinerU font size data.
        # heading_level=0 means false-positive title (body text) — no heading prefix.
        # Only self-hosted MinerU (middle.json) provides font size in layout.json;
        # Cloud API titles all default to H1.
        is_title = block.type == "title"
        if is_title:
            # Convert to markdown heading: remove existing # if present, then add correct level
            text_stripped = text.strip()
            # Remove any existing markdown heading markers
            text_stripped = re.sub(r'^#+\s*', '', text_stripped)
            # Safety net: reject blocks that are clearly body text
            level = getattr(block, "heading_level", None)
            if level == 0:
                formatted_text = text_stripped
            elif level is None or not isinstance(level, int) or level < 1 or level > 6:
                level = 1
                formatted_text = f"{'#' * level} {text_stripped}"
            else:
                # Add markdown heading format with correct level
                formatted_text = f"{'#' * level} {text_stripped}"
        else:
            formatted_text = text.strip()

        # CRITICAL: For PDF files, segmentation should always be one block = one segment
        # Chunking (merging multiple segments) is handled separately by chunk merging logic
        # deep_split only controls whether to split a single block's text by paragraphs

        # Collect cross-page paired block indices so both blocks map to the same segment
        raw = getattr(block, "raw", None) or {}
        pair_indices: List[int] = []
        if isinstance(raw, dict):
            for pair in raw.get("_cross_page_pairs", []):
                if isinstance(pair, dict):
                    pidx = pair.get("index")
                    if pidx is not None:
                        pair_indices.append(pidx)

        def _make_block_indices(base_idx: int) -> List[int]:
            if base_idx < 0:
                return list(pair_indices)
            return [base_idx] + pair_indices

        def _make_block_texts(base_text: str) -> List[str]:
            texts = [base_text] if block_index >= 0 else []
            texts.extend([""] * len(pair_indices))
            return texts

        if builder.deep_split:
            # Split block text by paragraphs, but each paragraph becomes a separate segment
            # For titles, don't split by paragraphs (titles should remain as single segments)
            if is_title:
                chunks.append(
                    LayoutChunk(
                        text=formatted_text,
                        chunk_type="text",
                        block_indices=_make_block_indices(block_index),
                        block_texts=_make_block_texts(formatted_text),
                        image_path=None,
                    )
                )
            else:
                paragraphs = _paragraph_split(text)
                for para in paragraphs:
                    if not para:
                        continue
                    # Even if paragraph is longer than max_chunk_chars, keep it as one segment
                    # The chunk merging logic will handle splitting if needed
                    chunks.append(
                        LayoutChunk(
                            text=para.strip(),
                            chunk_type="text",
                            block_indices=_make_block_indices(block_index),
                            block_texts=_make_block_texts(para.strip()),
                            image_path=None,
                        )
                    )
        else:
            # For non-deep-split, one block = one segment (no paragraph splitting)
            # Flush any accumulated text from previous blocks first
            _flush_text_chunk(chunks, current_text_parts, current_block_sequence)
            current_chars_ref[0] = 0
            
            # Create one segment per block
            chunks.append(
                LayoutChunk(
                    text=formatted_text,
                    chunk_type="text",
                    block_indices=_make_block_indices(block_index),
                    block_texts=_make_block_texts(formatted_text),
                    image_path=None,
                )
            )

    _flush_text_chunk(chunks, current_text_parts, current_block_sequence)

    markdown_text = "\n\n".join(chunk.text for chunk in chunks if chunk.text)

    return LayoutMarkdownResult(markdown_text=markdown_text, chunks=chunks)


def _layout_markdown_builder_build(
    self: LayoutMarkdownBuilder, layout_doc: LayoutDocument
) -> LayoutMarkdownResult:
    return _build_layout_markdown(self, layout_doc)


# Bind the implementation to LayoutMarkdownBuilder so callers can simply do
# `LayoutMarkdownBuilder(...).build(layout_doc)`.
setattr(LayoutMarkdownBuilder, "build", _layout_markdown_builder_build)

