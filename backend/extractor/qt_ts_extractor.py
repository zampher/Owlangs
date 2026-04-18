# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations

import xml.etree.ElementTree as ET
from typing import List, Optional
from .base import Extractor, ExtractResult


class QtTsExtractor(Extractor):
    """
    Extract text from Qt .ts translation source files.
    
    Qt .ts files are XML files with structure:
    <TS>
        <context>
            <name>ContextName</name>
            <message>
                <source>Original text</source>
                <translation>Translated text</translation>
            </message>
        </context>
    </TS>
    
    This extractor extracts all <source> text for translation preview.
    """

    def __init__(self, file_bytes: bytes, chunk_size: int = 3000):
        self.file_bytes = file_bytes
        self.chunk_size = chunk_size

    def extract(self) -> ExtractResult:
        """
        Extract all <source> text from Qt .ts file.
        
        Returns:
            ExtractResult with segments (source texts) and segment_info (metadata)
        """
        try:
            # Parse XML
            root = ET.fromstring(self.file_bytes)
            
            segments: List[str] = []
            segment_info: List[dict] = []
            
            # Traverse all context/message elements
            for context in root.findall('.//context'):
                # Get context name
                context_name_elem = context.find('name')
                context_name = context_name_elem.text if context_name_elem is not None else ''
                
                # Process all messages in this context
                for message in context.findall('message'):
                    source = message.find('source')
                    if source is None or not source.text:
                        continue
                    
                    source_text = source.text.strip()
                    if not source_text:
                        continue
                    
                    # Check translation status
                    translation = message.find('translation')
                    translation_type = translation.get('type') if translation is not None else None
                    has_translation = (
                        translation is not None and 
                        translation.text and 
                        translation.text.strip() and
                        translation_type not in ('unfinished', 'vanished', 'obsolete')
                    )
                    
                    segments.append(source_text)
                    segment_info.append({
                        "context_name": context_name,
                        "message_element_id": id(message),  # Use id as reference (element will be stored separately)
                        "source_text": source_text,
                        "has_translation": has_translation,
                        "translation_type": translation_type,
                    })
            
            # If no segments found, return empty result
            if not segments:
                return ExtractResult(segments=[], segment_info=[])
            
            # For very long segments, split them (though .ts files usually have short source texts)
            # Use markdown_splitter for consistency
            from utils.markdown_splitter import split_markdown_text
            
            # Split oversized segments
            final_segments: List[str] = []
            final_segment_info: List[dict] = []
            
            for i, segment in enumerate(segments):
                if len(segment.encode('utf-8')) > self.chunk_size:
                    # Split long segment
                    sub_segments = split_markdown_text(segment, max_block_size=self.chunk_size)
                    for sub_seg in sub_segments:
                        final_segments.append(sub_seg)
                        # Copy segment info for each sub-segment
                        final_segment_info.append(segment_info[i].copy())
                else:
                    final_segments.append(segment)
                    final_segment_info.append(segment_info[i])
            
            return ExtractResult(
                segments=final_segments,
                segment_info=final_segment_info,
            )
        except ET.ParseError as e:
            # Invalid XML, return empty result
            return ExtractResult(segments=[], segment_info=[])
        except Exception as e:
            # Other errors, return empty result to avoid breaking pipeline
            return ExtractResult(segments=[], segment_info=[])

