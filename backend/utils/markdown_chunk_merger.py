# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0
"""
Utilities for merging markdown chunks to reduce API calls and system prompt repetition.
Similar to segments2json_chunks but for markdown text chunks.
"""

from typing import List, Tuple, Optional

from backend.logger import unified_logger as logger
from logger.logger import LogModule


def chunks2merged_chunks(chunks: List[str], chunk_size_max: int, segment_indices: Optional[List] = None) -> Tuple[List[str], List[Tuple[int, int]]]:
    """
    Merge multiple small markdown chunks into larger chunks to reduce API calls.
    
    This function is similar to segments2json_chunks but works with plain markdown text
    instead of JSON dicts. It merges small chunks together until reaching chunk_size_max,
    which helps reduce the number of API calls and system prompt repetitions.
    
    NOTE:
    - The MDTranslateAgent now sends JSON arrays like:
        [{"index": 2, "text": "chunk text"}, ...]
      and split_merged_chunks is responsible for mapping JSON results back.
    - chunks2merged_chunks itself still only operates on raw text chunks here; the JSON
      envelope is added by MDTranslateAgent.send_chunks_async.
    
        Args:
        chunks: List of markdown text chunks to merge
        chunk_size_max: Maximum size (in characters) for a merged chunk
        segment_indices: Optional list of segment indices for each chunk. Can be:
                        - List[int]: One segment index per chunk
                        - List[List[int]]: Multiple segment indices per chunk (for MD translation with indexed segments)
                        If provided, uses these indices; otherwise uses chunk position as index.
        
    Returns:
        Tuple containing:
        - merged_chunks: List of merged chunks (each chunk may contain multiple original chunks)
          Format: "{index1}: {text1}\n{index2}: {text2}\n..."
        - merged_indices_list: List of (start, end) tuples indicating which original chunks
          were merged together. Used to split the translated result back to original chunks.
          
    Example:
        chunks = ["Hello", "World", "Foo", "Bar"]
        segment_indices = [0, 1, 2, 3]  # Each chunk corresponds to one segment
        merged_chunks, merged_indices = chunks2merged_chunks(chunks, chunk_size_max=20, segment_indices)
        # If "0: Hello\n1: World" fits in 20 chars, merged_chunks might be:
        # ["0: Hello\n1: World", "2: Foo\n3: Bar"]
        # merged_indices = [(0, 2), (2, 4)]
    """
    if not chunks:
        return [], []
    
    logger.info(LogModule.TRANS,
        f"[CHUNKS2MERGED] Starting merge: {len(chunks)} chunks, "
        f"chunk_size_max={chunk_size_max} bytes"
    )
    
    merged_chunks: List[str] = []
    merged_indices_list: List[Tuple[int, int]] = []
    
    current_chunk_parts: List[tuple[int, str]] = []  # Store (segment_index, chunk_text) tuples
    current_segment_indices: List[int] = []  # Track segment indices for current merged chunk
    current_start_idx = 0
    
    for idx, chunk in enumerate(chunks):
        # Check if chunk already contains indexed segments (format: "0: text\n1: text")
        # This happens when chunks are built from segments with indices in MD translation
        import re
        has_indexed_segments = bool(re.search(r'^\d+:\s', chunk, re.MULTILINE))
        
        if has_indexed_segments:
            # Chunk already contains indexed segments - use as-is
            # Don't add another index prefix to avoid double indexing
            indexed_chunk = chunk
            # Extract the first segment index for tracking
            first_index_match = re.match(r'^(\d+):', chunk)
            seg_idx = int(first_index_match.group(1)) if first_index_match else idx
            logger.debug(LogModule.TRANS,
                f"[CHUNKS2MERGED] Chunk {idx} already contains indexed segments. "
                f"First segment index: {seg_idx}, chunk preview: {chunk[:100]}..."
            )
        else:
            # Get segment index for this chunk (if provided)
            # CRITICAL: segment_indices may be a list of integers or a list of lists
            if segment_indices and idx < len(segment_indices):
                seg_idx_or_list = segment_indices[idx]
                if isinstance(seg_idx_or_list, list):
                    # Multiple segments per chunk - use first segment index for chunk-level tracking
                    seg_idx = seg_idx_or_list[0] if seg_idx_or_list else idx
                    logger.debug(LogModule.TRANS,
                        f"[CHUNKS2MERGED] Chunk {idx} has multiple segment indices {seg_idx_or_list[:5]}..."
                        f"{'...' if len(seg_idx_or_list) > 5 else ''}. Using first index {seg_idx} for chunk-level tracking."
                    )
                else:
                    # Single segment per chunk
                    seg_idx = seg_idx_or_list
            else:
                seg_idx = idx
            
            # Format chunk with index prefix: "{index}: {chunk_text}"
            # This preserves leading spaces in chunk_text
            indexed_chunk = f"{seg_idx}: {chunk}"
            logger.debug(LogModule.TRANS,
                f"[CHUNKS2MERGED] Chunk {idx} needs index prefix. "
                f"Segment index: {seg_idx}, chunk size: {len(chunk)} chars, "
                f"chunk preview: {chunk[:100]}..."
            )
        
        # Estimate size if we add this chunk (with separator)
        separator = "\n" if current_chunk_parts else ""
        # CRITICAL: Build prospective text correctly based on whether chunks already contain indexed segments
        # If chunk already contains indexed segments (has_indexed_segments=True), indexed_chunk is the chunk itself
        # Otherwise, indexed_chunk is formatted as "{seg_idx}: {chunk}"
        prospective_parts = []
        for si, ct in current_chunk_parts:
            # CRITICAL: If si is None, it means the chunk already contains indexed segments
            # Don't add chunk-level index prefix
            if si is None:
                # Already indexed - use as-is
                prospective_parts.append(ct)
            elif isinstance(ct, str) and re.search(r'^\d+:\s', ct, re.MULTILINE):
                # Already indexed - use as-is (backward compatibility check)
                prospective_parts.append(ct)
            else:
                # Needs index prefix
                prospective_parts.append(f"{si}: {ct}")
        # Add current chunk
        # CRITICAL: If has_indexed_segments, indexed_chunk already contains indexed segments
        # Don't add chunk-level index prefix
        if has_indexed_segments:
            prospective_parts.append(indexed_chunk)
        else:
            prospective_parts.append(indexed_chunk)
        prospective_text = separator.join(prospective_parts)
        prospective_size = len(prospective_text.encode('utf-8'))
        
        logger.debug(LogModule.TRANS,
            f"[CHUNKS2MERGED] Chunk {idx}: prospective_size={prospective_size} bytes, "
            f"chunk_size_max={chunk_size_max} bytes, "
            f"current_chunk_parts={len(current_chunk_parts)}, "
            f"will_merge={prospective_size <= chunk_size_max}"
        )
        
        if prospective_size > chunk_size_max and current_chunk_parts:
            # Current chunk is full, save it and start a new one
            # Format: each part as "{index}: {text}", separated by newlines
            # CRITICAL: If chunks already contain indexed segments, use them directly
            merged_parts = []
            for si, ct in current_chunk_parts:
                # CRITICAL: If si is None, it means the chunk already contains indexed segments
                # Don't add chunk-level index prefix
                if si is None:
                    # Already indexed - use as-is
                    merged_parts.append(ct)
                elif isinstance(ct, str) and re.search(r'^\d+:\s', ct, re.MULTILINE):
                    # Already indexed - use as-is (backward compatibility check)
                    merged_parts.append(ct)
                else:
                    # Needs index prefix
                    merged_parts.append(f"{si}: {ct}")
            merged_text = "\n".join(merged_parts)
            logger.debug(LogModule.TRANS,
                f"[CHUNKS2MERGED] Merged chunk {len(merged_chunks)}: "
                f"{len(current_chunk_parts)} parts, "
                f"text_preview={merged_text[:200]}..."
            )
            
            merged_chunks.append(merged_text)
            
            # Record which original chunks were merged
            current_end_idx = idx
            if current_end_idx > current_start_idx:
                merged_indices_list.append((current_start_idx, current_end_idx))
            
            # Start new chunk
            # CRITICAL: Store indexed_chunk (which may already contain indexed segments)
            # If chunk already contains indexed segments, store it with a special marker
            # to avoid adding chunk-level index prefix during merging
            if has_indexed_segments:
                # Store with None as seg_idx to indicate it's already indexed
                # The chunk itself contains all segment indices: "0: text1\n1: text2\n2: text3"
                current_chunk_parts = [(None, indexed_chunk)]
                logger.debug(LogModule.TRANS,
                    f"[CHUNKS2MERGED] Starting new merged chunk with pre-indexed chunk {idx}. "
                    f"Chunk preview: {indexed_chunk[:150]}..."
                )
            else:
                current_chunk_parts = [(seg_idx, indexed_chunk)]
                logger.debug(LogModule.TRANS,
                    f"[CHUNKS2MERGED] Starting new merged chunk with indexed chunk {idx} (seg_idx={seg_idx}). "
                    f"Chunk preview: {indexed_chunk[:150]}..."
                )
            current_segment_indices = [seg_idx]
            current_start_idx = idx
        else:
            # Add to current chunk
            # CRITICAL: Store indexed_chunk (which may already contain indexed segments)
            # If chunk already contains indexed segments, store it with a special marker
            # to avoid adding chunk-level index prefix during merging
            if has_indexed_segments:
                # Store with None as seg_idx to indicate it's already indexed
                # The chunk itself contains all segment indices: "0: text1\n1: text2\n2: text3"
                current_chunk_parts.append((None, indexed_chunk))
                logger.debug(LogModule.TRANS,
                    f"[CHUNKS2MERGED] Adding pre-indexed chunk {idx} to current merged chunk. "
                    f"Chunk preview: {indexed_chunk[:150]}..."
                )
            else:
                current_chunk_parts.append((seg_idx, indexed_chunk))
                logger.debug(LogModule.TRANS,
                    f"[CHUNKS2MERGED] Adding indexed chunk {idx} (seg_idx={seg_idx}) to current merged chunk. "
                    f"Chunk preview: {indexed_chunk[:150]}..."
                )
            current_segment_indices.append(seg_idx)
    
    # Don't forget the last chunk
    if current_chunk_parts:
        # Format: each part as "{index}: {text}", separated by newlines
        # CRITICAL: If chunks already contain indexed segments, use them directly
        merged_parts = []
        for si, ct in current_chunk_parts:
            # CRITICAL: If si is None, it means the chunk already contains indexed segments
            # Don't add chunk-level index prefix
            if si is None:
                # Already indexed - use as-is
                merged_parts.append(ct)
            elif isinstance(ct, str) and re.search(r'^\d+:\s', ct, re.MULTILINE):
                # Already indexed - use as-is (backward compatibility check)
                merged_parts.append(ct)
            else:
                # Needs index prefix
                merged_parts.append(f"{si}: {ct}")
        merged_text = "\n".join(merged_parts)
        logger.debug(LogModule.TRANS,
            f"[CHUNKS2MERGED] Final merged chunk {len(merged_chunks)}: "
            f"{len(current_chunk_parts)} parts, "
            f"text_preview={merged_text[:200]}..."
        )
        
        merged_chunks.append(merged_text)
        
        # Record which original chunks were merged
        current_end_idx = len(chunks)
        if current_end_idx > current_start_idx:
            merged_indices_list.append((current_start_idx, current_end_idx))
    
    logger.info(LogModule.TRANS,
        f"[CHUNKS2MERGED] Completed merge: {len(chunks)} input chunks -> {len(merged_chunks)} merged chunks, "
        f"merged_indices_list={merged_indices_list}"
    )
    
    return merged_chunks, merged_indices_list


def parse_merged_indexed_text(merged_text: str) -> List[Tuple[int, str]]:
    """
    Parse a merged chunk string in "index: text" format into a list of (index, text) pairs.
    Used to build JSON payloads for LLM: each segment becomes {"index": i, "text": t}.

    Format: lines starting with "\\d+: " start a new segment; following lines until
    the next "\\d+: " are continuation of that segment's text.
    """
    import re
    if not merged_text or not merged_text.strip():
        return []
    lines = merged_text.split("\n")
    result: List[Tuple[int, str]] = []
    current_idx: Optional[int] = None
    current_lines: List[str] = []

    for line in lines:
        match = re.match(r"^\s*(\d+):\s*(.*)$", line)
        if match:
            if current_idx is not None:
                result.append((current_idx, "\n".join(current_lines)))
            current_idx = int(match.group(1))
            current_lines = [match.group(2)] if match.group(2) else []
        else:
            if current_idx is not None:
                current_lines.append(line)

    if current_idx is not None:
        result.append((current_idx, "\n".join(current_lines)))
    return result


def _flatten_segment_indices(seg_indices: List) -> List[int]:
    """Flatten segment_indices so that list-of-lists becomes list of ints (hashable for set ops)."""
    out: List[int] = []
    for x in seg_indices:
        if isinstance(x, list):
            out.extend(x)
        else:
            out.append(int(x))
    return out


def split_merged_chunks(translated_merged_chunks: List[str], merged_indices_list: List[Tuple[int, int]], 
                       original_chunk_count: int, segment_indices_map: Optional[dict] = None,
                       segment_indices: Optional[List] = None) -> List[str]:
    """
    Split merged translated chunks back to individual chunks.
    
    This function reverses the merging process. It takes translated merged chunks
    and splits them back to match the original chunk structure.
    
    CRITICAL: The function supports two formats:
    1. New indexed format: "{index}: {text}" (one per line) - preferred format
    2. Old format: "<seg:0,1,2>\n{text}" - for backward compatibility
    
    The new format allows accurate splitting even if translation changes the number of lines,
    because each segment is identified by its index prefix.
    
    Args:
        translated_merged_chunks: List of translated merged chunks
        merged_indices_list: List of (start, end) tuples from chunks2merged_chunks
        original_chunk_count: Total number of original chunks
        segment_indices_map: Optional dict mapping segment index to chunk index.
                            If provided, uses it for accurate mapping.
        
    Returns:
        List of individual translated chunks matching the original chunk structure
        
    Example:
        translated_merged = ["0: 你好\n1: 世界", "2: Foo\n3: Bar"]
        merged_indices = [(0, 2), (2, 4)]
        segment_indices_map = {0: 0, 1: 1, 2: 2, 3: 3}  # segment_idx -> chunk_idx
        result = split_merged_chunks(translated_merged, merged_indices, 4, segment_indices_map)
        # result = ["你好", "世界", "Foo", "Bar"]
    """
    if not translated_merged_chunks:
        return []
    
    # If no merging occurred, return as-is (after removing index prefix if present)
    if not merged_indices_list:
        cleaned_chunks = []
        import re
        for chunk in translated_merged_chunks:
            # Try to remove index prefix: "{index}: {text}" -> "{text}"
            # Also handle old format: "<seg:...>\n{text}" -> "{text}"
            match = re.match(r'^\s*\d+:\s*(.*)$', chunk, re.DOTALL)
            if match:
                cleaned = match.group(1)
            else:
                # Fallback: remove old segment marker if present
                cleaned = _remove_segment_marker(chunk)
            cleaned_chunks.append(cleaned)
        return cleaned_chunks
    
    import re
    # Use module-level logger (already defined at top of file)
    
    # Try to parse indexed format: "{index}: {text}" (one per line)
    result: List[Optional[str]] = [None] * original_chunk_count
    merged_idx = 0
    
    for start_idx, end_idx in merged_indices_list:
        if merged_idx >= len(translated_merged_chunks):
            break
            
        merged_text = translated_merged_chunks[merged_idx]
        
        # Try to parse indexed format: "{index}: {text}"
        # Format: each segment starts with "{index}: " on a new line
        # Text may contain newlines, so we need to identify segment boundaries by the "{index}: " pattern
        # CRITICAL: The first segment may not have an index prefix (e.g., "# Title\n1: Text")
        # In this case, we need to infer the first segment index from expected_segment_indices
        indexed_lines = []
        lines = merged_text.split('\n')
        
        current_seg_idx = None
        current_text_lines = []
        first_line_handled = False
        
        for line_idx, line in enumerate(lines):
            # Match pattern: "{index}: {text}" at start of line
            # Allow optional whitespace before index for robustness
            match = re.match(r'^\s*(\d+):\s*(.*)$', line)
            if match:
                # Save previous segment if exists
                if current_seg_idx is not None:
                    indexed_lines.append((current_seg_idx, '\n'.join(current_text_lines)))
                
                # Start new segment
                current_seg_idx = int(match.group(1))
                text_part = match.group(2)
                current_text_lines = [text_part] if text_part else []
                first_line_handled = True
            else:
                # Continuation of current segment's text (may contain newlines)
                if current_seg_idx is not None:
                    current_text_lines.append(line)
                elif not first_line_handled and line_idx == 0:
                    # CRITICAL: First line doesn't have index prefix - this is the first segment
                    # We need to infer the segment index from expected_segment_indices
                    # For now, collect the text and we'll assign the index later
                    current_text_lines.append(line)
                    first_line_handled = True
                # If no current segment and not first line, this might be old format or malformed - skip for now
        
        # CRITICAL: Handle the case where first segment doesn't have index prefix
        # If we collected text for the first segment but didn't assign an index, assign it now
        if current_text_lines and current_seg_idx is None:
            # First segment doesn't have index prefix - infer from expected_segment_indices
            if segment_indices and start_idx < len(segment_indices) and end_idx <= len(segment_indices):
                expected_slice = segment_indices[start_idx:end_idx]
                expected_flat = _flatten_segment_indices(expected_slice)
                if expected_flat:
                    # Use the first expected segment index (int, not list)
                    first_seg_idx = expected_flat[0]
                    indexed_lines.insert(0, (first_seg_idx, '\n'.join(current_text_lines)))
                    logger.debug(LogModule.TRANS,
                        f"[SPLIT_MERGED] First segment in merged chunk {merged_idx} doesn't have index prefix. "
                        f"Inferred index {first_seg_idx} from expected segment indices. "
                        f"Text preview: {current_text_lines[0][:100] if current_text_lines else ''}..."
                    )
                    current_text_lines = []
        
        # Don't forget the last segment
        # CRITICAL: Even if current_text_lines is empty (empty segment like "94: "), 
        # we must add it to maintain index continuity and prevent misalignment
        if current_seg_idx is not None:
            indexed_lines.append((current_seg_idx, '\n'.join(current_text_lines)))
        
        if indexed_lines and segment_indices_map:
            # Successfully parsed indexed format
            logger.info(LogModule.TRANS,
                f"[SPLIT_MERGED] Found indexed format in merged chunk {merged_idx}: "
                f"parsed {len(indexed_lines)} indexed segments, "
                f"expected {end_idx - start_idx} chunks, "
                f"segment_indices_map has {len(segment_indices_map)} entries, "
                f"text_preview={merged_text[:300]!r}"
            )
            # Log first few indexed lines for debugging
            if indexed_lines:
                logger.debug(LogModule.TRANS,
                    f"[SPLIT_MERGED] First 5 indexed segments: "
                    f"{[(seg_idx, text[:50]) for seg_idx, text in indexed_lines[:5]]}"
                )
            
            # Map each indexed line to its chunk
            # CRITICAL: Use actual segment_indices if provided, not range(start_idx, end_idx)
            # This handles cases where segments are excluded (e.g., [57, 58, 59, 60] instead of [0, 1, 2, 3])
            # segment_indices contains the original segment indices for chunks at positions [start_idx:end_idx]
            # May be list of ints or list of lists (one list per chunk); flatten for set ops and iteration
            if segment_indices and start_idx < len(segment_indices) and end_idx <= len(segment_indices):
                expected_segment_indices = segment_indices[start_idx:end_idx]
                expected_segment_indices_flat = _flatten_segment_indices(expected_segment_indices)
            else:
                # Fallback: use chunk positions as segment indices
                expected_segment_indices = list(range(start_idx, end_idx))
                expected_segment_indices_flat = expected_segment_indices
            found_segment_indices = [seg_idx for seg_idx, _ in indexed_lines]
            
            # CRITICAL: Map found segment indices directly to chunk indices using segment_indices_map
            # Don't rely on expected_segment_indices matching - just map what we found
            # This ensures correct mapping even if some segments are excluded or indices don't match exactly
            # CRITICAL: For MD translation, multiple segments may map to the same chunk
            # We need to combine them back into indexed format: "0: text1\n1: text2\n2: text3"
            chunk_segments_map = {}  # chunk_idx -> list of (seg_idx, text) tuples
            mapped_count = 0
            for seg_idx, text in indexed_lines:
                if seg_idx in segment_indices_map:
                    chunk_idx = segment_indices_map[seg_idx]
                    if chunk_idx < len(result):
                        # Group segments by chunk_idx
                        if chunk_idx not in chunk_segments_map:
                            chunk_segments_map[chunk_idx] = []
                        chunk_segments_map[chunk_idx].append((seg_idx, text))
                        mapped_count += 1
                        logger.debug(LogModule.TRANS,
                            f"[SPLIT_MERGED] Mapped segment {seg_idx} -> chunk {chunk_idx}, "
                            f"text_preview={text[:80]!r}..."
                        )
                    else:
                        logger.warning(LogModule.TRANS,
                            f"[SPLIT_MERGED] Segment {seg_idx} mapped to chunk {chunk_idx} which is out of bounds "
                            f"(result length: {len(result)}). Skipping."
                        )
                else:
                    logger.warning(LogModule.TRANS,
                        f"[SPLIT_MERGED] Segment {seg_idx} not found in segment_indices_map. "
                        f"This may indicate a mapping error. segment_indices_map has {len(segment_indices_map)} entries. "
                        f"Sample keys: {sorted(list(segment_indices_map.keys()))[:20]}..."
                    )
            
            # CRITICAL: Combine segments for each chunk back into indexed format
            # If a chunk contains multiple segments, format as "0: text1\n1: text2\n2: text3"
            # If a chunk contains only one segment, just use the text (no index prefix needed)
            for chunk_idx, segments_list in chunk_segments_map.items():
                if len(segments_list) > 1:
                    # Multiple segments - combine with indexed format
                    # Sort by segment index to ensure correct order
                    segments_list.sort(key=lambda x: x[0])
                    combined_text = "\n".join([f"{seg_idx}: {text}" for seg_idx, text in segments_list])
                    result[chunk_idx] = combined_text
                    logger.debug(LogModule.TRANS,
                        f"[SPLIT_MERGED] Chunk {chunk_idx} contains {len(segments_list)} segments. "
                        f"Combined into indexed format (length: {len(combined_text)}). "
                        f"Segment indices: {[seg_idx for seg_idx, _ in segments_list][:10]}..."
                    )
                else:
                    # Single segment - use text directly (no index prefix)
                    seg_idx, text = segments_list[0]
                    result[chunk_idx] = text
                    logger.debug(LogModule.TRANS,
                        f"[SPLIT_MERGED] Chunk {chunk_idx} contains 1 segment (index {seg_idx}). "
                        f"Using text directly (length: {len(text)})."
                    )
            
            logger.info(LogModule.TRANS,
                f"[SPLIT_MERGED] Mapped {mapped_count}/{len(indexed_lines)} segments to {len(chunk_segments_map)} chunks in merged chunk {merged_idx}"
            )
            
            # Check for missing segments (segments that should be in this merged chunk but weren't found)
            # CRITICAL: Don't overwrite chunks that already have content from chunk_segments_map
            if expected_segment_indices_flat:
                missing = set(expected_segment_indices_flat) - set(found_segment_indices)
                if missing:
                    logger.warning(LogModule.TRANS,
                        f"[SPLIT_MERGED] Missing segments in merged chunk {merged_idx}: "
                        f"expected segments {expected_segment_indices_flat}, "
                        f"found segments {found_segment_indices}. "
                        f"Missing: {missing}. "
                        f"Marking missing segments as failed (empty string)."
                    )
                    # Mark missing segments as failed
                    # CRITICAL: Only mark chunks as failed if they don't already have content
                    # If a chunk already has segments from chunk_segments_map, don't overwrite it
                    for seg_idx in missing:
                        if seg_idx in segment_indices_map:
                            chunk_idx = segment_indices_map[seg_idx]
                            if chunk_idx < len(result):
                                # Only set to empty if chunk doesn't already have content
                                if result[chunk_idx] is None or result[chunk_idx] == "":
                                    result[chunk_idx] = ""
                                else:
                                    logger.debug(LogModule.TRANS,
                                        f"[SPLIT_MERGED] Chunk {chunk_idx} already has content from other segments, "
                                        f"not overwriting with empty for missing segment {seg_idx}."
                                    )
            
            # Check for extra segments (segments found but not expected in this merged chunk)
            if expected_segment_indices_flat:
                extra = set(found_segment_indices) - set(expected_segment_indices_flat)
                if extra:
                    logger.debug(LogModule.TRANS,
                        f"[SPLIT_MERGED] Extra segments in merged chunk {merged_idx}: "
                        f"expected segments {expected_segment_indices_flat}, "
                        f"found segments {found_segment_indices}. "
                        f"Extra: {extra}. "
                        f"These segments may belong to a different merged chunk, but will be mapped if in segment_indices_map."
                    )
        else:
            # Fallback: Try old format with <seg:...> marker (for backward compatibility)
            segment_marker_match = re.match(r'<seg:([0-9,]+)>\n?', merged_text)
            if segment_marker_match and segment_indices_map:
                logger.debug(LogModule.TRANS,
                    f"[SPLIT_MERGED] Found old segment marker format in merged chunk {merged_idx}: "
                    f"marker={segment_marker_match.group(0)}, "
                    f"expected_chunks={end_idx - start_idx}, "
                    f"text_preview={merged_text[:200]!r}"
                )
                # Use segment markers for accurate mapping
                segment_indices_str = segment_marker_match.group(1)
                segment_indices = [int(s) for s in segment_indices_str.split(',')]
                
                # Remove marker from text
                text_without_marker = merged_text[segment_marker_match.end():]
                
                # Split by double newline
                split_parts = text_without_marker.split("\n\n")
                
                # Map each part to its segment index
                if len(split_parts) == len(segment_indices):
                    for seg_idx, part in zip(segment_indices, split_parts):
                        if seg_idx in segment_indices_map:
                            chunk_idx = segment_indices_map[seg_idx]
                            if chunk_idx < len(result):
                                result[chunk_idx] = part
                else:
                    # Mismatch - mark all as failed
                    logger.warning(LogModule.TRANS,
                        f"[SPLIT_MERGED] Cannot split merged chunk {merged_idx} (old format): "
                        f"expected {len(segment_indices)} segments but got {len(split_parts)} parts. "
                        f"Marking segments {segment_indices} as failed (empty string). "
                        f"User can retranslate via 'Translate Failed' feature."
                    )
                    for seg_idx in segment_indices:
                        if seg_idx in segment_indices_map:
                            chunk_idx = segment_indices_map[seg_idx]
                            if chunk_idx < len(result):
                                result[chunk_idx] = ""
            else:
                # No recognizable format - fall back to simple splitting by double newline
                text_without_marker = _remove_segment_marker(merged_text)
                split_parts = text_without_marker.split("\n\n")
                
                expected_parts = end_idx - start_idx
                logger.debug(LogModule.TRANS,
                    f"[SPLIT_MERGED] No indexed format or segment marker in merged chunk {merged_idx}: "
                    f"expected_parts={expected_parts}, "
                    f"actual_parts={len(split_parts)}, "
                    f"text_preview={merged_text[:200]!r}"
                )
                
                # Ensure we have the right number of parts
                if len(split_parts) == expected_parts:
                    for i, chunk_idx in enumerate(range(start_idx, end_idx)):
                        if chunk_idx < len(result):
                            result[chunk_idx] = split_parts[i]
                else:
                    # Mismatch - mark all as failed
                    logger.warning(LogModule.TRANS,
                        f"[SPLIT_MERGED] Cannot split merged chunk {merged_idx}: "
                        f"expected {expected_parts} chunks but got {len(split_parts)} parts. "
                        f"Marking chunks {start_idx}-{end_idx-1} as failed (empty string). "
                        f"User can retranslate via 'Translate Failed' feature.\n"
                        f"  Translated merged chunk: {merged_text[:500]!r}"
                    )
                    for chunk_idx in range(start_idx, end_idx):
                        if chunk_idx < len(result):
                            result[chunk_idx] = ""
        
        merged_idx += 1
    
    # Fill None values with empty strings and ensure correct length
    final_result = [text if text is not None else "" for text in result]
    while len(final_result) < original_chunk_count:
        final_result.append("")
    
    return final_result[:original_chunk_count]


def _remove_segment_marker(text: str) -> str:
    """Remove segment marker from text if present."""
    import re
    # Match segment marker at the beginning: <seg:0,1,2> or <seg:0,1,2>\n
    return re.sub(r'^<seg:[0-9,]+\>\n?', '', text, count=1)

