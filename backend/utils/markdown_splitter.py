# SPDX-FileCopyrightText: 2026 Zampherss
# SPDX-License-Identifier: MPL-2.0
import re
from typing import List, Tuple, Optional




class MarkdownBlockSplitter:
    def __init__(self, max_block_size: int = 5000, deep_split: bool = False):
        """
        Initialize Markdown splitter

        Args:
            max_block_size: Maximum bytes per block
            deep_split: If True, each logical block (paragraph) becomes its own segment
        """
        self.max_block_size = max_block_size
        self.deep_split = deep_split

    @staticmethod
    def _get_bytes(text: str) -> int:
        return len(text.encode('utf-8'))

    def split_markdown(self, markdown_text: str) -> List[str]:
        """
        Split Markdown text into blocks of specified size
        Ensure original text can be reconstructed by simple concatenation (except for split code blocks)
        Try to keep headers and their corresponding content in the same block
        """
        # 1. Split text into logical blocks
        logical_blocks = self._split_into_logical_blocks(markdown_text)

        # In deep split mode, each logical block becomes its own segment (or split if too long)
        if self.deep_split:
            chunks = []
            for block in logical_blocks:
                block_size = self._get_bytes(block)
                if block_size > self.max_block_size:
                    # Split oversized block
                    chunks.extend(self._split_large_block(block))
                else:
                    # Each block becomes its own chunk
                    if block.strip():
                        chunks.append(block)
            return chunks

        # 2. Merge logical blocks so they don't exceed max_block_size
        chunks = []
        current_chunk_parts = []
        current_size = 0

        for block in logical_blocks:
            block_size = self._get_bytes(block)

            # Case 1: Block itself is too large
            if block_size > self.max_block_size:
                # First output currently accumulated blocks
                if current_chunk_parts:
                    chunks.append("".join(current_chunk_parts))
                    current_chunk_parts = []
                    current_size = 0

                # Split this oversized block and add directly to results
                chunks.extend(self._split_large_block(block))
                continue

            # Case 2: Adding this block to current chunk would exceed limit
            if current_size + block_size > self.max_block_size:
                if current_chunk_parts:
                    chunks.append("".join(current_chunk_parts))

                current_chunk_parts = [block]
                current_size = block_size
            # Case 3: Normal addition
            else:
                current_chunk_parts.append(block)
                current_size += block_size

        # Add the last remaining chunk
        if current_chunk_parts:
            chunks.append("".join(current_chunk_parts))

        return chunks

    def _split_into_logical_blocks(self, markdown_text: str) -> List[str]:
        """
        Split Markdown text into logical blocks (headers, paragraphs, code blocks, empty line separators, etc.)
        """
        # Normalize line breaks
        text = markdown_text.replace('\r\n', '\n')

        # Split code blocks and other content
        code_block_pattern = r'(```[\s\S]*?```|~~~[\s\S]*?~~~)'
        parts = re.split(code_block_pattern, text)

        blocks = []
        for i, part in enumerate(parts):
            if not part:
                continue

            if i % 2 == 1:  # This is a code block
                blocks.append(part)
            else:  # This is regular Markdown content
                # Split by one or more empty lines and preserve separators
                # This effectively separates paragraphs, lists, headers, etc., and preserves empty lines between them
                sub_parts = re.split(r'(\n{2,})', part)
                # Filter out empty strings that re.split might produce
                blocks.extend([p for p in sub_parts if p])

        return blocks

    def _split_large_block(self, block: str) -> List[str]:
        """
        Split a single block that exceeds max_block_size
        """
        # Prioritize code blocks
        if block.startswith(('```', '~~~')):
            fence = '```' if block.startswith('```') else '~~~'
            lines = block.split('\n')
            header = lines[0]
            footer = lines[-1]
            content_lines = lines[1:-1]

            chunks = []
            current_chunk_lines = [header]
            current_size = self._get_bytes(header) + 1

            for line in content_lines:
                line_size = self._get_bytes(line) + 1
                if current_size + line_size + self._get_bytes(footer) > self.max_block_size:
                    current_chunk_lines.append(footer)
                    chunks.append('\n'.join(current_chunk_lines))
                    current_chunk_lines = [header, line]
                    current_size = self._get_bytes(header) + 1 + line_size
                else:
                    current_chunk_lines.append(line)
                    current_size += line_size

            if len(current_chunk_lines) > 1:
                current_chunk_lines.append(footer)
                chunks.append('\n'.join(current_chunk_lines))
            return chunks

        # Split regular large text by lines
        lines = block.split('\n')
        chunks = []
        current_chunk = []
        current_size = 0
        for line in lines:
            line_size = self._get_bytes(line) + 1
            if current_size + line_size > self.max_block_size and current_chunk:
                chunks.append('\n'.join(current_chunk))
                current_chunk = [line]
                current_size = line_size - 1  # -1 for the first line does not have a leading '\n'
            else:
                current_chunk.append(line)
                current_size += line_size

        if current_chunk:
            chunks.append('\n'.join(current_chunk))

        return chunks


def split_markdown_text(markdown_text: str, max_block_size=5000, deep_split: bool = False) -> List[str]:
    """
    Split Markdown string into blocks not exceeding max_block_size

    Args:
        markdown_text: Markdown text to split
        max_block_size: Maximum bytes per block
        deep_split: If True, each logical block (paragraph) becomes its own segment
    """
    splitter = MarkdownBlockSplitter(max_block_size=max_block_size, deep_split=deep_split)
    chunks = splitter.split_markdown(markdown_text)
    # Filter out blocks consisting only of whitespace characters
    chunks = [chunk for chunk in chunks if chunk.strip()]

    # When deep_split is requested and the text has no markdown-specific
    # syntax (headers, code blocks), it's likely plain text (e.g. text_input.md).
    # Fall back to paragraph splitting so each line becomes its own segment
    # instead of arbitrary byte-size chunks.
    if deep_split and not re.search(r'#{1,6}\s|```|~~~', markdown_text):
        chunks = split_text_into_paragraphs(markdown_text, max_block_size=max_block_size)

    return chunks


def split_text_into_paragraphs(text: str, max_block_size: int = 5000) -> List[str]:
    """
    Split plain text by natural paragraphs, then by lines if oversized.

    Uses a heuristic: if blank lines (\\n\\n) are found, splits by blank lines
    into paragraph blocks. Otherwise, falls back to line-by-line splitting
    (each non-empty line is its own paragraph).

    If a paragraph exceeds max_block_size, it is further split by individual
    lines within that paragraph.

    Args:
        text: Plain text content
        max_block_size: Maximum bytes per segment

    Returns:
        List of text segments (paragraphs or sub-paragraph lines)
    """
    # Normalize line endings
    text = text.replace('\r\n', '\n')

    # Try blank-line split first (natural paragraph boundaries)
    blank_line_paras = re.split(r'\n\s*\n', text)
    blank_line_paras = [p.strip() for p in blank_line_paras if p.strip()]

    if len(blank_line_paras) > 1:
        # File has blank-line paragraph boundaries — use them
        raw_paragraphs = blank_line_paras
    else:
        # No blank lines — each line is its own paragraph
        raw_paragraphs = [line.strip() for line in text.split('\n') if line.strip()]

    result: List[str] = []
    for para in raw_paragraphs:
        para_bytes = len(para.encode('utf-8'))
        if para_bytes > max_block_size:
            # Split oversized paragraph by individual lines
            lines = para.split('\n')
            current_chunk: List[str] = []
            current_size = 0
            for line in lines:
                line_size = len(line.encode('utf-8')) + 1
                if current_size + line_size > max_block_size and current_chunk:
                    result.append('\n'.join(current_chunk))
                    current_chunk = [line]
                    current_size = line_size - 1
                else:
                    current_chunk.append(line)
                    current_size += line_size
            if current_chunk:
                result.append('\n'.join(current_chunk))
        else:
            result.append(para)

    return result


def _needs_single_newline_join(prev_chunk: str, next_chunk: str) -> bool:
    """
    Determine if two blocks should be joined with a single newline
    This usually happens between consecutive lines of lists, tables, quote blocks
    """
    if not prev_chunk.strip() or not next_chunk.strip():
        return False

    last_line_prev = prev_chunk.rstrip().split('\n')[-1].lstrip()
    first_line_next = next_chunk.lstrip().split('\n')[0].lstrip()

    # Tables
    if last_line_prev.startswith('|') and last_line_prev.endswith('|') and \
            first_line_next.startswith('|') and first_line_next.endswith('|'):
        return True

    # Lists (unordered and ordered)
    list_markers = r'^\s*([-*+]|\d+\.)\s+'
    if re.match(list_markers, last_line_prev) and re.match(list_markers, first_line_next):
        return True

    # Quotes
    if last_line_prev.startswith('>') and first_line_next.startswith('>'):
        return True

    return False


def join_markdown_texts(markdown_texts: List[str]) -> str:
    """
    Intelligently join Markdown block list
    """
    if not markdown_texts:
        return ""

    joined_text = markdown_texts[0]
    for i in range(1, len(markdown_texts)):
        prev_chunk = markdown_texts[i - 1]
        current_chunk = markdown_texts[i]

        # Determine whether to use single or double newline
        if _needs_single_newline_join(prev_chunk, current_chunk):
            separator = "\n"
        else:
            # Default to double newline to separate different blocks
            separator = "\n\n"

        joined_text += separator + current_chunk

    return joined_text


def split_markdown_text_with_placeholder_awareness(
    markdown_text: str,
    max_block_size: int = 5000,
    show_images_as_separate_chunks: bool = True,
    deep_split: bool = False
) -> Tuple[List[str], Optional[object]]:
    """
    Split Markdown text into chunks with placeholder awareness.
    Placeholders (<ph-xxx>) are excluded from size calculation and can be shown as separate chunks.
    
    Args:
        markdown_text: Markdown text with <ph-xxx> placeholders
        max_block_size: Maximum bytes per block (excluding placeholders)
        show_images_as_separate_chunks: If True, each image placeholder becomes a separate chunk
        deep_split: If True, each logical block (paragraph) becomes its own segment
    
    Returns:
        (chunks, tracker): List of chunks and placeholder tracker (None if no placeholders)
    """
    # Import here to avoid circular dependency
    from utils.markdown_utils import PlaceholderTracker
    
    if not markdown_text or not markdown_text.strip():
        return [], None
    
    # Find all placeholders
    ph_pattern = r"<ph-([a-zA-Z0-9]+)>"
    placeholder_matches = list(re.finditer(ph_pattern, markdown_text))
    
    if not placeholder_matches:
        # No placeholders, use regular split
        return split_markdown_text(markdown_text, max_block_size, deep_split=deep_split), None
    
    tracker = PlaceholderTracker()
    
    if show_images_as_separate_chunks:
        # Strategy: Extract placeholders as separate chunks
        chunks = []
        last_pos = 0
        
        for match in placeholder_matches:
            placeholder_id = match.group(1)
            start_pos = match.start()
            end_pos = match.end()
            placeholder_text = match.group(0)
            
            # Add text before placeholder as a chunk (if any)
            text_before = markdown_text[last_pos:start_pos].strip()
            if text_before:
                # Split text_before using regular splitter (excluding placeholders from size)
                text_before_clean = re.sub(ph_pattern, "", text_before)
                if text_before_clean.strip():
                    # Use regular splitter for text without placeholders
                    try:
                        sub_chunks = split_markdown_text(text_before_clean, max_block_size, deep_split=deep_split)
                        chunks.extend(sub_chunks)
                    except Exception as e:
                        # If splitting fails, add the text as a single chunk
                        import logging
                        logging.warning(f"Failed to split text before placeholder: {e}")
                        chunks.append(text_before_clean)
            
            # Add placeholder as a separate chunk
            chunks.append(placeholder_text)
            tracker.record(placeholder_id, placeholder_text, start_pos, len(chunks) - 1)
            
            last_pos = end_pos
        
        # Add remaining text after last placeholder
        text_after = markdown_text[last_pos:].strip()
        if text_after:
            text_after_clean = re.sub(ph_pattern, "", text_after)
            if text_after_clean.strip():
                try:
                    sub_chunks = split_markdown_text(text_after_clean, max_block_size, deep_split=deep_split)
                    chunks.extend(sub_chunks)
                except Exception as e:
                    # If splitting fails, add the text as a single chunk
                    import logging
                    logging.warning(f"Failed to split text after placeholder: {e}")
                    chunks.append(text_after_clean)
        
        # Filter out empty chunks
        chunks = [chunk for chunk in chunks if chunk.strip()]
        
        return chunks, tracker
    else:
        # Strategy: Exclude placeholders from size calculation but keep them in chunks
        # Replace placeholders with temporary markers for size calculation
        temp_marker = " " * 10  # Average placeholder length
        text_for_sizing = re.sub(ph_pattern, temp_marker, markdown_text)
        
        # Use regular splitter on text with temporary markers
        chunks = split_markdown_text(text_for_sizing, max_block_size, deep_split=deep_split)
        
        # Restore original placeholders in chunks
        restored_chunks = []
        for chunk_idx, chunk in enumerate(chunks):
            # Replace temp markers back to placeholders
            restored_chunk = chunk
            # Find placeholders that should be in this chunk
            chunk_start = sum(len(c.encode('utf-8')) for c in chunks[:chunk_idx])
            chunk_end = chunk_start + len(chunk.encode('utf-8'))
            
            # Find placeholders in original text that fall within this chunk's range
            for match in placeholder_matches:
                ph_start = match.start()
                if chunk_start <= ph_start < chunk_end:
                    placeholder_id = match.group(1)
                    placeholder_text = match.group(0)
                    # Replace temp marker with actual placeholder
                    restored_chunk = restored_chunk.replace(temp_marker, placeholder_text, 1)
                    tracker.record(placeholder_id, placeholder_text, ph_start, chunk_idx)
            
            restored_chunks.append(restored_chunk)
        
        return restored_chunks, tracker


if __name__ == '__main__':
    from pathlib import Path
    from utils.markdown_utils import clean_markdown_math_block
    content=Path(r"C:\Users\jxgm\Desktop\3a8d8999-3e9d-4f32-a32c-5b0830bb4320\full.md").read_text()
    content=split_markdown_text(content)
    content=join_markdown_texts(content)

