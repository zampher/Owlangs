# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations

import json
from typing import Any, List, Optional
from .base import Extractor, ExtractResult


class JsonExtractor(Extractor):
    """
    Extract text nodes from JSON by configured json_paths (jsonpath-like simple dot paths),
    fallback to extracting all string values if paths not provided.
    """

    def __init__(self, json_text: str, chunk_size: int = 3000, paths: Optional[List[str]] = None, json_paths: Optional[List[str]] = None):
        self.json_text = json_text
        # CRITICAL: chunk_size is in tokens, but JsonExtractor uses bytes for comparison
        # Convert tokens to bytes: 1 token ≈ 3-4 bytes for UTF-8
        # Use conservative estimate (3 bytes per token) to avoid merging too aggressively
        # This ensures each JSON string value stays as a separate segment unless really necessary
        self.chunk_size = chunk_size * 3  # Convert tokens to bytes
        # Support both 'paths' and 'json_paths' for backward compatibility and consistency
        self.paths = (json_paths or paths) or []

    def _iter_all_strings(self, node: Any, base_path: str = '$') -> List[tuple[str, str]]:
        result: List[tuple[str, str]] = []
        if isinstance(node, str):
            result.append((base_path, node))
        elif isinstance(node, dict):
            for k, v in node.items():
                path = f"{base_path}.{k}"
                result.extend(self._iter_all_strings(v, path))
        elif isinstance(node, list):
            for i, v in enumerate(node):
                path = f"{base_path}[{i}]"
                result.extend(self._iter_all_strings(v, path))
        return result

    def _get_by_path(self, node: Any, path: str) -> List[tuple[str, str]]:
        # very small path subset: $.a.b, $.arr[0].x
        if not path or not path.startswith('$.'):
            return []
        cur = node
        parts = path[2:].split('.')
        try:
            for part in parts:
                idx = None
                key = part
                if '[' in part and part.endswith(']'):
                    key, idx_str = part.split('[', 1)
                    idx = int(idx_str[:-1])
                if key:
                    cur = cur[key]
                if idx is not None:
                    cur = cur[idx]
            # collect strings under this node
            return self._iter_all_strings(cur, path)
        except Exception:
            return []

    def extract(self) -> ExtractResult:
        try:
            data = json.loads(self.json_text)
        except Exception:
            # not valid json, return whole text as one segment
            # CRITICAL: Even for invalid JSON, we must provide segment_info with path
            # Use root path '$' as fallback
            return ExtractResult(
                segments=[self.json_text],
                segment_info=[{'paths': ['$']}]
            )

        pairs: List[tuple[str, str]] = []
        if self.paths:
            for p in self.paths:
                pairs.extend(self._get_by_path(data, p))
        else:
            pairs.extend(self._iter_all_strings(data))

        # CRITICAL: Each JSON text field should be a separate segment
        # Do NOT merge fields - merging will be handled by segments2json_chunks later
        # Only split a single field if it exceeds chunk_size
        segments: List[str] = []
        segment_info: List[dict] = []
        
        for path, val in pairs:
            val_bytes = len(val.encode('utf-8'))
            
            # If a single field exceeds chunk_size, split it by lines
            if val_bytes > self.chunk_size:
                # Split large field by lines to create sub-segments
                lines = val.splitlines(keepends=True)
                current_sub_segment = ''
                current_sub_paths = []
                
                for line in lines:
                    line_bytes = len(line.encode('utf-8'))
                    next_sub_segment = current_sub_segment + line
                    next_bytes = len(next_sub_segment.encode('utf-8'))
                    
                    if next_bytes > self.chunk_size and current_sub_segment:
                        # Flush current sub-segment
                        segments.append(current_sub_segment)
                        segment_info.append({'paths': current_sub_paths})
                        current_sub_segment = line
                        current_sub_paths = [path]
                    else:
                        current_sub_segment = next_sub_segment
                        if not current_sub_paths:
                            current_sub_paths = [path]
                
                # Add remaining sub-segment
                if current_sub_segment:
                    segments.append(current_sub_segment)
                    segment_info.append({'paths': current_sub_paths})
            else:
                # Field fits in chunk_size, keep as single segment
                segments.append(val)
                segment_info.append({'paths': [path]})

        return ExtractResult(segments=segments, segment_info=segment_info)


