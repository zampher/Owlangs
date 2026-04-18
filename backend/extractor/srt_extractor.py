# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations

import re
from typing import List, Tuple, Optional
from .base import Extractor, ExtractResult


class SrtExtractor(Extractor):
    """Extract cues from SRT content as segments.

    Each segment is the cue text (can contain multiple lines). Index/time metadata
    can be re-associated later via the original SRT if needed.
    """

    def __init__(self, srt_text: str, chunk_size: int = 3000):
        self.srt_text = srt_text
        # chunk_size is in tokens, convert to bytes for comparison
        # Rough estimate: 1 token ≈ 4 characters (bytes for UTF-8)
        # Use a conservative estimate to avoid merging too many segments
        from utils.chunk_size_converter import get_text_content_token_limit
        # chunk_size is already in tokens, so we need to convert it to bytes
        # For SRT, we want to keep each subtitle as a separate segment if possible
        # Only merge when absolutely necessary (very long subtitles)
        # Estimate: 1 token ≈ 4 bytes for English, but can be more for other languages
        # Use a more conservative approach: don't merge unless really necessary
        # Convert token size to bytes: 1 token ≈ 3-4 bytes for UTF-8
        # Use a more conservative estimate (3 bytes per token) to avoid merging too aggressively
        # This ensures each subtitle stays as a separate segment unless really necessary
        self.chunk_size_bytes = chunk_size * 3  # Rough estimate: 1 token ≈ 3 bytes

    def extract(self) -> ExtractResult:
        text = self.srt_text.replace('\r\n', '\n').strip()
        # Split cues by blank lines
        raw_cues = re.split(r'\n{2,}', text)
        cues: List[Tuple[Optional[int], Optional[str], Optional[str], str]] = []

        time_re = re.compile(r'^(\d{2}:\d{2}:\d{2},\d{3}) --> (\d{2}:\d{2}:\d{2},\d{3})$')
        for cue in raw_cues:
            lines = [ln for ln in cue.split('\n') if ln.strip()]
            if not lines:
                continue
            idx: Optional[int] = None
            start: Optional[str] = None
            end: Optional[str] = None
            # index
            if re.match(r'^\d+$', lines[0]):
                try:
                    idx = int(lines[0])
                except Exception:
                    idx = None
                lines = lines[1:]
            # time
            if lines:
                m = time_re.match(lines[0])
                if m:
                    start, end = m.group(1), m.group(2)
                    lines = lines[1:]
            cue_text = '\n'.join(l for l in lines if l.strip()).strip()
            if cue_text:
                cues.append((idx, start, end, cue_text))

        # For SRT, keep each subtitle as a separate segment for better translation quality
        # This ensures better context preservation and translation accuracy
        # Only split when a single subtitle exceeds chunk_size_bytes
        merged_segments: List[str] = []
        merged_info: List[dict] = []
        
        for idx, start, end, seg in cues:
            seg_bytes = len(seg.encode('utf-8'))
            
            # If current segment alone exceeds chunk_size_bytes, split it by lines
            if seg_bytes > self.chunk_size_bytes:
                # Split very long subtitle by lines, but keep as separate segments
                lines = seg.split('\n')
                for line_idx, line in enumerate(lines):
                    if line.strip():
                        merged_segments.append(line.strip())
                        merged_info.append({'cues': [{'index': idx, 'start': start, 'end': end, 'line': line_idx}]})
            else:
                # Each subtitle is a separate segment (no merging)
                merged_segments.append(seg)
                merged_info.append({'cues': [{'index': idx, 'start': start, 'end': end}]})

        return ExtractResult(segments=merged_segments, segment_info=merged_info)


