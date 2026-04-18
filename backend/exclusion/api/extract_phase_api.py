# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

"""
Unified API for Extract phase exclusion detection and storage.

This module provides a unified interface for all document formats to detect
and store exclusions during the Extract phase, ensuring consistency.
"""

from typing import Dict, List, Optional, Union, Any, Tuple
import time

from logger import unified_logger as logger
from logger.logger import LogModule
from exclusion.core.exclusion_reason import ExclusionReason
from exclusion.detection.batch_detector import ExclusionDetectionBatch
from exclusion.extractors.base import FormatMetadataExtractor


class ExclusionExtractAPI:
    """Unified API for Extract phase exclusion detection and storage."""
    
    @staticmethod
    def detect_and_store_exclusions(
        workflow_type: str,
        segments: List[Union[str, dict]],
        task_state: dict,
        target_lang: Optional[str] = None,
        format_specific_data: Optional[Dict[int, dict]] = None,
        metadata_extractor: Optional[FormatMetadataExtractor] = None,
        **kwargs
    ) -> Tuple[Dict[int, ExclusionReason], Dict[int, ExclusionReason]]:
        """
        Unified Extract phase exclusion detection and storage interface.
        
        All formats' Extract phase should call this interface to ensure:
        1. Consistent detection logic
        2. Consistent storage format
        3. Consistent data structure
        
        Args:
            workflow_type: Workflow type ('docx', 'pdf', 'pptx', 'json', etc.)
            segments: List of segments
            task_state: Task state dictionary
            target_lang: Target language
            format_specific_data: Format-specific data for each segment
            metadata_extractor: Metadata extractor (if None, will be created based on workflow_type)
            **kwargs: Other format-specific parameters
        
        Returns:
            Tuple of (excluded_segments, all_detected_reasons)
        """
        # Create or use provided metadata_extractor
        if metadata_extractor is None:
            metadata_extractor = ExclusionExtractAPI._create_extractor(workflow_type, **kwargs)
        
        # Batch detect exclusions
        excluded_segments, all_detected_reasons = ExclusionDetectionBatch.detect_exclusions_batch(
            segments=segments,
            metadata_extractor=metadata_extractor,
            task_state=task_state,
            target_lang=target_lang,
            format_specific_data=format_specific_data,
            preserve_existing=True,
            auto_exclude_optional=False
        )
        
        # Prepare segment_metadata
        segment_metadata = ExclusionExtractAPI._prepare_segment_metadata(
            workflow_type, excluded_segments, **kwargs
        )
        
        # Store exclusions
        ExclusionDetectionBatch.store_exclusions(
            task_state=task_state,
            excluded_segments=excluded_segments,
            segment_metadata=segment_metadata,
            source=f"{workflow_type}_extraction",
            all_detected_reasons=all_detected_reasons
        )
        
        # CRITICAL: Ensure excluded_segments are correctly stored in segments_metadata
        # This is the key step that DOCX workflow may be missing
        ExclusionExtractAPI._ensure_excluded_segments_in_metadata(task_state)
        
        return excluded_segments, all_detected_reasons
    
    @staticmethod
    def _create_extractor(workflow_type: str, **kwargs) -> FormatMetadataExtractor:
        """Create metadata extractor based on workflow_type."""
        if workflow_type == 'pdf':
            from exclusion.extractors.pdf_extractor import PDFMetadataExtractor
            return PDFMetadataExtractor(
                block_type_map=kwargs.get('block_type_map', {}),
                block_image_map=kwargs.get('block_image_map', {})
            )
        elif workflow_type == 'docx':
            from exclusion.extractors.docx_extractor import DOCXMetadataExtractor
            return DOCXMetadataExtractor(
                segment_info=kwargs.get('segment_info', [])
            )
        elif workflow_type == 'pptx':
            from exclusion.extractors.pptx_extractor import PPTXMetadataExtractor
            return PPTXMetadataExtractor(
                element_type_map=kwargs.get('element_type_map', {})
            )
        else:
            from exclusion.extractors.markdown_extractor import MarkdownMetadataExtractor
            return MarkdownMetadataExtractor()
    
    @staticmethod
    def _prepare_segment_metadata(workflow_type: str, excluded_segments: Dict[int, ExclusionReason], **kwargs) -> Optional[Dict[int, dict]]:
        """Prepare segment_metadata for storage."""
        if workflow_type == 'docx':
            segment_info = kwargs.get('segment_info', [])
            return {
                idx: {"block_type": "table" if segment_info[idx].get("is_table_cell", False) else None}
                for idx in excluded_segments.keys()
                if idx < len(segment_info)
            }
        elif workflow_type == 'pdf':
            all_segments = kwargs.get('all_segments', [])
            return {
                idx: {"block_type": all_segments[idx].get("block_type")}
                for idx in excluded_segments.keys()
                if idx < len(all_segments)
            }
        return None
    
    @staticmethod
    def _ensure_excluded_segments_in_metadata(task_state: dict):
        """
        CRITICAL: Ensure excluded_segments are correctly stored in segments_metadata.
        
        This is the key step that DOCX workflow may be missing.
        PDF workflow explicitly reads and stores, but DOCX may not.
        """
        segments_metadata = task_state.get("segments_metadata", {})
        excluded_segments = segments_metadata.get("excluded_segments", {})
        
        # If excluded_segments already exists and is in correct format, no need to do anything
        if excluded_segments and isinstance(excluded_segments, dict):
            return
        
        # Otherwise, read from ExclusionManager and store
        from exclusion.core.exclusion_manager import ExclusionManager
        excluded_dict = ExclusionManager.get_excluded_segments(task_state)
        if excluded_dict:
            # Convert to storage format
            excluded_segments_dict = {
                str(idx): {
                    "reason": reason.value,
                    "detected_at": time.time()
                }
                for idx, reason in excluded_dict.items()
            }
            segments_metadata["excluded_segments"] = excluded_segments_dict
            task_state["segments_metadata"] = segments_metadata
            logger.debug(
                LogModule.EXCLUSION,
                f"ExclusionExtractAPI: Ensured excluded_segments are stored in segments_metadata "
                f"({len(excluded_segments_dict)} segments)"
            )
