# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations

import re
from html.parser import HTMLParser
from typing import List, Optional
from .base import Extractor, ExtractResult


class _StructuredHtmlParser(HTMLParser):
    """
    Minimal structured HTML parser to extract block-level texts:
    - Headings h1-h6 -> separate blocks
    - Paragraph p -> block
    - Lists ul/ol: aggregate li into one block (each item as a line)
    - Table: aggregate rows; each row joins cells with " | ", rows join with "\n"
    - Blockquote -> block
    - Pre/code -> keep inner text with line breaks
    - br -> line break within current block
    Other tags: ignored or treated as inline within current block.
    """

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.blocks: List[str] = []
        self._current: List[str] = []
        self._stack: List[str] = []
        # list aggregation
        self._in_list: Optional[str] = None  # 'ul' | 'ol'
        self._list_items: List[str] = []
        # table aggregation
        self._in_table: bool = False
        self._row_cells: List[str] = []
        self._table_rows: List[str] = []

    def _flush_current_block(self):
        if self._current:
            text = ''.join(self._current).strip()
            if text:
                self.blocks.append(text)
            self._current = []

    # HTML5 void elements – never push these onto the stack since they have no end tag.
    _VOID_ELEMENTS = frozenset({
        'area', 'base', 'br', 'col', 'embed', 'hr', 'img', 'input',
        'link', 'meta', 'param', 'source', 'track', 'wbr',
    })

    def handle_starttag(self, tag, attrs):
        tag = tag.lower()
        if tag == 'img':
            # Extract image URL as a standalone block so it appears in segments.
            # Prefer data-src (WeChat lazy-load) over src.
            attrs_dict = dict(attrs)
            src = attrs_dict.get('data-src', '') or attrs_dict.get('src', '')
            if src:
                self._flush_current_block()
                self.blocks.append(f'[Image: {src}]')
            return
        if tag not in self._VOID_ELEMENTS:
            self._stack.append(tag)
        if tag in ('p', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'blockquote', 'pre', 'code', 'div', 'section', 'article'):
            # Start a new potential block if current has content
            self._flush_current_block()
        elif tag in ('ul', 'ol'):
            self._flush_current_block()
            self._in_list = tag
            self._list_items = []
        elif tag == 'li':
            # new list item
            self._current = []
        elif tag == 'table':
            self._flush_current_block()
            self._in_table = True
            self._table_rows = []
            self._row_cells = []
        elif tag == 'tr':
            self._row_cells = []
        elif tag == 'br':
            self._current.append('\n')

    def handle_endtag(self, tag):
        tag = tag.lower()
        # pop stack safely
        if self._stack and self._stack[-1] == tag:
            self._stack.pop()
        if tag in ('p', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'blockquote', 'pre', 'code', 'div', 'section', 'article'):
            self._flush_current_block()
        elif tag == 'li':
            item = ''.join(self._current).strip()
            if item:
                self._list_items.append(item)
            self._current = []
        elif tag in ('ul', 'ol'):
            if self._list_items:
                self.blocks.append('\n'.join(self._list_items))
            self._in_list = None
            self._list_items = []
        elif tag == 'td' or tag == 'th':
            cell = ''.join(self._current).strip()
            self._row_cells.append(cell)
            self._current = []
        elif tag == 'tr':
            row_text = ' | '.join([c for c in self._row_cells if c])
            if row_text:
                self._table_rows.append(row_text)
            self._row_cells = []
        elif tag == 'table':
            if self._table_rows:
                self.blocks.append('\n'.join(self._table_rows))
            self._in_table = False
            self._table_rows = []

    def handle_data(self, data):
        # ignore inside script/style
        if any(t in ('script', 'style') for t in self._stack):
            return
        if data:
            self._current.append(data)

    def close(self):
        super().close()
        # flush remaining structures
        if self._row_cells:
            row_text = ' | '.join([c for c in self._row_cells if c])
            if row_text:
                self._table_rows.append(row_text)
            self._row_cells = []
        if self._table_rows:
            self.blocks.append('\n'.join(self._table_rows))
            self._table_rows = []
        if self._list_items:
            self.blocks.append('\n'.join(self._list_items))
        self._list_items = []
        self._flush_current_block()


class HtmlExtractor(Extractor):
    def __init__(self, html_text: str, chunk_size: int = 3000, deep_split: bool = False):
        self.html_text = html_text
        self.chunk_size = chunk_size
        self.deep_split = deep_split

    def _split_oversized_block(self, text: str) -> List[str]:
        """Split a large block into smaller chunks roughly under chunk_size (bytes),
        preferring paragraph/sentence boundaries and preserving newlines where possible.
        """
        max_bytes = self.chunk_size
        if len(text.encode('utf-8')) <= max_bytes:
            return [text]
        # First split by double newlines (paragraphs)
        paragraphs = re.split(r"\n{2,}", text)
        chunks: List[str] = []
        current = ''
        def fits(s: str) -> bool:
            return len(s.encode('utf-8')) <= max_bytes
        for para in paragraphs:
            piece = para.strip()
            if not piece:
                continue
            candidate = (current + ('\n\n' if current else '') + piece) if current else piece
            if fits(candidate):
                current = candidate
            else:
                # if paragraph itself is too big, split by sentences/lines
                if current:
                    chunks.append(current)
                    current = ''
                # sentence split (., !, ?, ;, Chinese 。！？；) keeping delimiter
                sentences = re.split(r"(?<=[\.!?；；。！？])\s+", piece)
                s_acc = ''
                for s in sentences:
                    s = s.strip()
                    if not s:
                        continue
                    cand2 = (s_acc + (' ' if s_acc else '') + s) if s_acc else s
                    if fits(cand2):
                        s_acc = cand2
                    else:
                        if s_acc:
                            chunks.append(s_acc)
                            s_acc = s
                        else:
                            # as a last resort, hard cut by bytes length
                            buf = s
                            while len(buf.encode('utf-8')) > max_bytes:
                                # approximate char cut by length
                                cut = max_bytes // 2
                                while len(buf[:cut].encode('utf-8')) < max_bytes and cut < len(buf):
                                    cut += 1
                                # step back to ensure <= max_bytes
                                while len(buf[:cut].encode('utf-8')) > max_bytes and cut > 1:
                                    cut -= 1
                                chunks.append(buf[:cut])
                                buf = buf[cut:]
                            if buf:
                                s_acc = buf
                if s_acc:
                    chunks.append(s_acc)
        if current:
            chunks.append(current)
        return chunks

    def extract(self) -> ExtractResult:
        parser = _StructuredHtmlParser()
        parser.feed(self.html_text.replace('\r\n', '\n'))
        parser.close()

        segments: List[str] = []
        separators_after: List[Optional[str]] = []

        if self.deep_split:
            # In deep split mode, each block becomes its own segment
            # If a block contains multiple paragraphs, split them
            for block in parser.blocks:
                if not block.strip():
                    continue
                
                # Split block by paragraphs (double newlines)
                paragraphs = re.split(r'\n{2,}', block)
                paragraphs = [p.strip() for p in paragraphs if p.strip()]
                
                # If no paragraph breaks, check for single newlines (might be multiple paragraphs)
                if len(paragraphs) == 1 and '\n' in paragraphs[0]:
                    lines = paragraphs[0].split('\n')
                    if len(lines) > 3:
                        paragraphs = [line.strip() for line in lines if line.strip()]
                
                # Each paragraph becomes its own segment (or split if too long)
                for para in paragraphs:
                    if not para:
                        continue
                    # If paragraph is too long, split it
                    if len(para.encode('utf-8')) > self.chunk_size:
                        sub_blocks = self._split_oversized_block(para)
                        for sub in sub_blocks:
                            if sub.strip():
                                segments.append(sub)
                                separators_after.append('\n\n')
                    else:
                        segments.append(para)
                        separators_after.append('\n\n')
            
            # Remove last separator
            if separators_after:
                separators_after[-1] = ''
        else:
            # Merge blocks into segments respecting chunk_size (bytes)
            current = ''
            for i, block in enumerate(parser.blocks):
                # pre-split oversized block first
                sub_blocks = self._split_oversized_block(block)
                for sub in sub_blocks:
                    append = sub if not current else current + '\n\n' + sub
                    if len(append.encode('utf-8')) > self.chunk_size and current:
                        segments.append(current)
                        separators_after.append('\n\n')
                        current = sub
                    else:
                        current = append if current else sub
            if current:
                segments.append(current)
                separators_after.append('')

        return ExtractResult(segments=segments, separators_after=separators_after)


