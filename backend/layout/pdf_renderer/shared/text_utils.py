# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

"""
Text processing utilities for PDF rendering.

This module provides shared text processing logic that can be used
by all PDF renderer implementations (ReportLab, HTML-to-PDF, etc.).
"""

import re
from typing import List, Tuple, Optional, Dict

try:
    from reportlab.pdfbase import pdfmetrics
    REPORTLAB_AVAILABLE = True
except ImportError:
    REPORTLAB_AVAILABLE = False


class TextUtils:
    """
    Text processing utilities.
    
    Provides methods for text wrapping, language detection, and
    text segmentation.
    """
    
    @staticmethod
    def detect_language(text: str) -> str:
        """
        Detect text language to determine appropriate font.
        
        Args:
            text: Text to analyze
            
        Returns:
            Language code: 'zh' for Chinese, 'ja' for Japanese, 'ko' for Korean, 'en' for English
        
        Note: If text contains Chinese characters, it returns 'zh' even if there are
        punctuation marks or symbols, ensuring Chinese fonts are used for proper rendering.
        """
        if not text:
            return 'en'
        
        # Check for Chinese characters first (including CJK unified ideographs)
        if re.search(r'[\u4e00-\u9fff]', text):
            return 'zh'  # Chinese - use Chinese font even if there are punctuation marks
        elif re.search(r'[\u3040-\u309f\u30a0-\u30ff]', text):
            return 'ja'  # Japanese
        elif re.search(r'[\uac00-\ud7a3]', text):
            return 'ko'  # Korean
        else:
            return 'en'  # English (default)
    
    @staticmethod
    def wrap_text_to_width(
        text: str,
        max_width: float,
        font_name: str = "Helvetica",
        font_size: float = 12,
        canvas_obj=None,
    ) -> List[str]:
        """
        Wrap text to fit within a given width using ReportLab's font metrics.
        
        Supports both word-based wrapping (for English) and character-based wrapping (for CJK).
        Uses ReportLab's accurate text width measurement.
        
        Args:
            text: Text to wrap
            max_width: Maximum width in points
            font_name: Font name
            font_size: Font size in points
            canvas_obj: Optional canvas object for accurate text measurement
            
        Returns:
            List of text lines
        """
        if not text or not text.strip():
            return []
        
        # Check if text contains CJK characters (Chinese, Japanese, Korean)
        has_cjk = bool(re.search(r'[\u4e00-\u9fff\u3040-\u309f\u30a0-\u30ff\uac00-\ud7a3]', text))
        
        # Use ReportLab's text measurement for accurate width calculation
        if canvas_obj and REPORTLAB_AVAILABLE:
            try:
                canvas_obj.setFont(font_name, font_size)
                space_width = pdfmetrics.stringWidth(" ", font_name, font_size)
            except Exception:
                space_width = font_size * 0.3
        else:
            # Fallback: approximate width
            space_width = font_size * 0.3
        
        lines = []
        
        if has_cjk:
            # Character-based wrapping for CJK text
            # CJK characters don't use spaces, so we wrap character by character
            current_line = ""
            current_width = 0
            
            for char in text:
                if canvas_obj and REPORTLAB_AVAILABLE:
                    try:
                        char_width = pdfmetrics.stringWidth(char, font_name, font_size)
                    except Exception:
                        char_width = font_size
                else:
                    # Approximate: CJK characters are typically square
                    char_width = font_size
                
                # Check if adding this character would exceed width
                # CRITICAL: Even for the first character, we must check if it fits
                if current_width + char_width <= max_width:
                    # Character fits on current line
                    current_line += char
                    current_width += char_width
                else:
                    # Current line is full, start new line
                    if current_line:
                        lines.append(current_line)
                    # Start new line with this character
                    # Even if this single character exceeds max_width, we add it
                    # (it's better to have it visible than to lose it)
                    current_line = char
                    current_width = char_width
            
            # Add remaining characters
            if current_line:
                lines.append(current_line)
            
            # Post-process: Verify and fix any lines that exceed max_width
            # This handles cases where font measurement might be inaccurate or font changed
            verified_lines = []
            for line in lines:
                if canvas_obj and REPORTLAB_AVAILABLE:
                    try:
                        line_width = pdfmetrics.stringWidth(line, font_name, font_size)
                    except Exception:
                        line_width = len(line) * font_size
                else:
                    line_width = len(line) * font_size
                
                if line_width <= max_width:
                    # Line fits, keep it
                    verified_lines.append(line)
                else:
                    # Line exceeds width, need to split further
                    # Split character by character until it fits
                    temp_line = ""
                    temp_width = 0
                    for char in line:
                        if canvas_obj and REPORTLAB_AVAILABLE:
                            try:
                                char_width = pdfmetrics.stringWidth(char, font_name, font_size)
                            except Exception:
                                char_width = font_size
                        else:
                            char_width = font_size
                        
                        if temp_width + char_width <= max_width:
                            temp_line += char
                            temp_width += char_width
                        else:
                            if temp_line:
                                verified_lines.append(temp_line)
                            temp_line = char
                            temp_width = char_width
                    
                    if temp_line:
                        verified_lines.append(temp_line)
            
            lines = verified_lines
        else:
            # Word-based wrapping for non-CJK text (English, etc.)
            words = text.split()
            if not words:
                return [text] if text else []
            
            current_line = []
            current_width = 0
            
            for word in words:
                if canvas_obj and REPORTLAB_AVAILABLE:
                    try:
                        word_width = pdfmetrics.stringWidth(word, font_name, font_size)
                    except Exception:
                        word_width = len(word) * font_size * 0.6
                else:
                    # Fallback: approximate width
                    word_width = len(word) * font_size * 0.6
                
                # Check if adding this word would exceed width
                # CRITICAL: Even for the first word, we must check if it fits
                # If a single word exceeds max_width, we need to split it
                if not current_line:
                    # First word on line
                    if word_width <= max_width:
                        # Word fits, add it
                        current_line.append(word)
                        current_width = word_width
                    else:
                        # Word itself exceeds max_width, need to split it character by character
                        # This handles very long words (URLs, etc.)
                        for char in word:
                            if canvas_obj and REPORTLAB_AVAILABLE:
                                try:
                                    char_width = pdfmetrics.stringWidth(char, font_name, font_size)
                                except Exception:
                                    char_width = font_size * 0.6
                            else:
                                char_width = font_size * 0.6
                            
                            if current_width + char_width <= max_width:
                                if not current_line:
                                    current_line.append(char)
                                    current_width = char_width
                                else:
                                    # Append to last word in current_line
                                    current_line[-1] += char
                                    current_width += char_width
                            else:
                                # Current line is full, start new line
                                if current_line:
                                    lines.append(" ".join(current_line))
                                current_line = [char]
                                current_width = char_width
                else:
                    # Not first word on line
                    # Check if adding space + word would exceed width
                    if canvas_obj and REPORTLAB_AVAILABLE:
                        try:
                            space_plus_word_width = pdfmetrics.stringWidth(" " + word, font_name, font_size)
                        except Exception:
                            space_plus_word_width = space_width + word_width
                    else:
                        space_plus_word_width = space_width + word_width
                    
                    if current_width + space_plus_word_width <= max_width:
                        # Word fits, add it
                        current_line.append(word)
                        current_width += space_plus_word_width
                    else:
                        # Word doesn't fit, start new line
                        lines.append(" ".join(current_line))
                        # Check if word itself exceeds max_width
                        if word_width <= max_width:
                            current_line = [word]
                            current_width = word_width
                        else:
                            # Word itself exceeds max_width, split it character by character
                            current_line = []
                            current_width = 0
                            for char in word:
                                if canvas_obj and REPORTLAB_AVAILABLE:
                                    try:
                                        char_width = pdfmetrics.stringWidth(char, font_name, font_size)
                                    except Exception:
                                        char_width = font_size * 0.6
                                else:
                                    char_width = font_size * 0.6
                                
                                if current_width + char_width <= max_width:
                                    if not current_line:
                                        current_line.append(char)
                                        current_width = char_width
                                    else:
                                        current_line[-1] += char
                                        current_width += char_width
                                else:
                                    if current_line:
                                        lines.append(" ".join(current_line))
                                    current_line = [char]
                                    current_width = char_width
            
            # Add remaining words
            if current_line:
                lines.append(" ".join(current_line))
            
            # Post-process: Verify and fix any lines that exceed max_width
            verified_lines = []
            for line in lines:
                if canvas_obj and REPORTLAB_AVAILABLE:
                    try:
                        line_width = pdfmetrics.stringWidth(line, font_name, font_size)
                    except Exception:
                        line_width = len(line) * font_size * 0.6
                else:
                    line_width = len(line) * font_size * 0.6
                
                if line_width <= max_width:
                    # Line fits, keep it
                    verified_lines.append(line)
                else:
                    # Line exceeds width, need to split further
                    # Split word by word, then character by character if needed
                    words_in_line = line.split()
                    temp_line = []
                    temp_width = 0
                    for word in words_in_line:
                        if canvas_obj and REPORTLAB_AVAILABLE:
                            try:
                                word_width = pdfmetrics.stringWidth(word, font_name, font_size)
                                space_plus_word_width = pdfmetrics.stringWidth(" " + word, font_name, font_size)
                            except Exception:
                                word_width = len(word) * font_size * 0.6
                                space_plus_word_width = space_width + word_width
                        else:
                            word_width = len(word) * font_size * 0.6
                            space_plus_word_width = space_width + word_width
                        
                        if not temp_line:
                            if word_width <= max_width:
                                temp_line.append(word)
                                temp_width = word_width
                            else:
                                # Word exceeds width, split character by character
                                for char in word:
                                    if canvas_obj and REPORTLAB_AVAILABLE:
                                        try:
                                            char_width = pdfmetrics.stringWidth(char, font_name, font_size)
                                        except Exception:
                                            char_width = font_size * 0.6
                                    else:
                                        char_width = font_size * 0.6
                                    
                                    if temp_width + char_width <= max_width:
                                        if not temp_line:
                                            temp_line.append(char)
                                            temp_width = char_width
                                        else:
                                            temp_line[-1] += char
                                            temp_width += char_width
                                    else:
                                        if temp_line:
                                            verified_lines.append(" ".join(temp_line))
                                        temp_line = [char]
                                        temp_width = char_width
                        else:
                            if temp_width + space_plus_word_width <= max_width:
                                temp_line.append(word)
                                temp_width += space_plus_word_width
                            else:
                                verified_lines.append(" ".join(temp_line))
                                if word_width <= max_width:
                                    temp_line = [word]
                                    temp_width = word_width
                                else:
                                    # Word exceeds width, split character by character
                                    temp_line = []
                                    temp_width = 0
                                    for char in word:
                                        if canvas_obj and REPORTLAB_AVAILABLE:
                                            try:
                                                char_width = pdfmetrics.stringWidth(char, font_name, font_size)
                                            except Exception:
                                                char_width = font_size * 0.6
                                        else:
                                            char_width = font_size * 0.6
                                        
                                        if temp_width + char_width <= max_width:
                                            if not temp_line:
                                                temp_line.append(char)
                                                temp_width = char_width
                                            else:
                                                temp_line[-1] += char
                                                temp_width += char_width
                                        else:
                                            if temp_line:
                                                verified_lines.append(" ".join(temp_line))
                                            temp_line = [char]
                                            temp_width = char_width
                    
                    if temp_line:
                        verified_lines.append(" ".join(temp_line))
            
            lines = verified_lines
        
        return lines
    
    @staticmethod
    def analyze_language_distribution(text: str) -> Dict[str, float]:
        """
        Analyze character-level language distribution in a text string.
        
        This is used for more precise font size adjustment in mixed-language blocks.
        
        Args:
            text: Text to analyze
            
        Returns:
            Mapping from language code to ratio in [0, 1].
            Language codes:
                - 'en': Latin letters / digits / basic ASCII
                - 'zh': Chinese
                - 'ja': Japanese
                - 'ko': Korean
                - 'other': All other characters (punctuation, symbols, etc.)
        """
        from typing import Dict
        
        if not text:
            return {}
        
        counts: Dict[str, int] = {"en": 0, "zh": 0, "ja": 0, "ko": 0, "other": 0}
        
        for ch in text:
            code = ord(ch)
            # Chinese
            if 0x4E00 <= code <= 0x9FFF:
                counts["zh"] += 1
            # Japanese Hiragana / Katakana
            elif 0x3040 <= code <= 0x309F or 0x30A0 <= code <= 0x30FF:
                counts["ja"] += 1
            # Korean Hangul
            elif 0xAC00 <= code <= 0xD7A3:
                counts["ko"] += 1
            # Basic Latin letters / digits / common ASCII
            elif (0x41 <= code <= 0x5A) or (0x61 <= code <= 0x7A) or (0x30 <= code <= 0x39):
                counts["en"] += 1
            else:
                counts["other"] += 1
        
        total = sum(counts.values())
        if total <= 0:
            return {}
        
        return {lang: count / total for lang, count in counts.items() if count > 0}
    
    @staticmethod
    def split_text_by_language_segments(text: str) -> List[Tuple[str, str]]:
        """
        Split text into segments by character-level language category.
        
        This is used to select fonts more precisely within a single block:
        each segment can use an appropriate font (e.g., Latin vs CJK),
        while keeping a single font size for the whole block.
        
        Args:
            text: Text to split
            
        Returns:
            List of (segment_text, lang_code) where lang_code is one of:
            'en', 'zh', 'ja', 'ko', 'other'.
        """
        segments: List[Tuple[str, str]] = []
        if not text:
            return segments
        
        # Check if text contains Chinese characters (for context-aware classification)
        has_chinese = any(0x4E00 <= ord(c) <= 0x9FFF for c in text)
        
        def classify_char(ch: str) -> str:
            code = ord(ch)
            # Chinese characters (CJK Unified Ideographs)
            if 0x4E00 <= code <= 0x9FFF:
                return "zh"
            # Chinese punctuation and symbols (common ranges)
            # CJK Symbols and Punctuation: U+3000-U+303F
            # CJK Compatibility Forms: U+FE30-U+FE4F
            # Fullwidth forms: U+FF00-U+FFEF
            # Common symbols that appear in Chinese text: U+25A0-U+25FF (geometric shapes like ■)
            if (0x3000 <= code <= 0x303F) or (0xFE30 <= code <= 0xFE4F) or (0xFF00 <= code <= 0xFFEF) or (0x25A0 <= code <= 0x25FF):
                # If text contains Chinese characters, treat punctuation/symbols as Chinese
                return "zh" if has_chinese else "other"
            # Japanese Hiragana / Katakana
            if 0x3040 <= code <= 0x309F or 0x30A0 <= code <= 0x30FF:
                return "ja"
            # Korean Hangul
            if 0xAC00 <= code <= 0xD7A3:
                return "ko"
            # Basic Latin letters / digits / common ASCII
            if (0x41 <= code <= 0x5A) or (0x61 <= code <= 0x7A) or (0x30 <= code <= 0x39):
                return "en"
            # For other characters, if text contains Chinese, treat as Chinese to use Chinese fonts
            if has_chinese:
                return "zh"  # Use Chinese font for symbols/punctuation in Chinese text
            return "other"
        
        current_lang = classify_char(text[0])
        current_segment = [text[0]]
        
        for ch in text[1:]:
            lang = classify_char(ch)
            if lang == current_lang:
                current_segment.append(ch)
            else:
                segments.append(("".join(current_segment), current_lang))
                current_segment = [ch]
                current_lang = lang
        
        if current_segment:
            segments.append(("".join(current_segment), current_lang))
        
        return segments
    
    @staticmethod
    def detect_text_alignment_from_layout(block_raw: dict, block_bbox: tuple) -> str:
        """
        Detect text alignment from layout.json data by analyzing span positions.
        
        Args:
            block_raw: Raw block data from layout.json (contains 'lines' and 'spans')
            block_bbox: Block bounding box tuple (x0, y0, x1, y1)
            
        Returns:
            Alignment string: 'left', 'center', or 'right'
        """
        if not block_raw or not block_bbox or len(block_bbox) < 4:
            return 'left'
        
        x0, y0, x1, y1 = block_bbox[:4]
        block_width = x1 - x0
        
        lines = block_raw.get("lines", [])
        if not lines:
            return 'left'
        
        # Check first line's spans
        first_line = lines[0]
        spans = first_line.get("spans", [])
        if not spans:
            return 'left'
        
        # Get first and last span positions
        first_span = spans[0]
        last_span = spans[-1]
        
        first_bbox = first_span.get("bbox", [])
        last_bbox = last_span.get("bbox", [])
        
        if len(first_bbox) >= 4 and len(last_bbox) >= 4:
            first_x0 = first_bbox[0]
            last_x1 = last_bbox[2]
            
            # Calculate text width
            text_width = last_x1 - first_x0
            
            # Calculate left and right margins
            left_margin = first_x0 - x0
            right_margin = x1 - last_x1
            
            # Determine alignment
            # Allow 5 points tolerance for center detection
            if abs(left_margin - right_margin) < 5:
                return 'center'
            elif right_margin > left_margin * 2:  # Right margin significantly larger than left
                return 'left'
            elif left_margin > right_margin * 2:  # Left margin significantly larger than right
                return 'right'
        
        return 'left'  # Default to left alignment
    
    @staticmethod
    def detect_text_alignment(
        text: str,
        text_width: float,
        block_width: float,
        font_name: str,
        font_size: float,
        canvas_obj,
        block_raw: dict = None,
        block_bbox: tuple = None,
    ) -> str:
        """
        Detect text alignment, preferring layout-based detection if available.
        
        Args:
            text: Text content
            text_width: Measured text width (may be 0 if not measured)
            block_width: Block bounding box width
            font_name: Font name
            font_size: Font size
            canvas_obj: ReportLab canvas object (for text measurement)
            block_raw: Optional raw block data from layout.json
            block_bbox: Optional block bounding box tuple (x0, y0, x1, y1)
            
        Returns:
            Alignment string: 'left', 'center', or 'right'
        """
        # Prefer layout-based detection if available
        if block_raw is not None and block_bbox is not None:
            alignment = TextUtils.detect_text_alignment_from_layout(block_raw, block_bbox)
            if alignment != 'left':  # If we detected center or right, use it
                return alignment
        
        # Fallback: measure text width and compare with block width
        if canvas_obj is not None and text:
            try:
                canvas_obj.setFont(font_name, font_size)
                measured_width = canvas_obj.stringWidth(text, font_name, font_size)
                
                # Calculate margins
                left_margin = 0  # Assume text starts at block left edge
                right_margin = block_width - measured_width
                
                # Determine alignment
                if abs(left_margin - right_margin) < 5:  # Allow 5 points tolerance
                    return 'center'
                elif right_margin > left_margin * 2:
                    return 'left'
                elif left_margin > right_margin * 2:
                    return 'right'
            except Exception:
                pass  # Fall through to default
        
        # Default to left alignment
        return 'left'

