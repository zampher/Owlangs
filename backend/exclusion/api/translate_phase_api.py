# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

"""
Unified API for Translate phase exclusion reading.

This module provides a unified interface for all document formats to read
exclusions during the Translate phase, ensuring consistency.

CRITICAL: Translate phase only reads, does NOT detect.
"""

from typing import Dict

from logger import unified_logger as logger
from logger.logger import LogModule
from exclusion.core.exclusion_reason import ExclusionReason
from exclusion.core.exclusion_manager import ExclusionManager


class ExclusionTranslateAPI:
    """Unified API for Translate phase exclusion reading (no detection)."""
    
    @staticmethod
    def get_excluded_segments(task_state: dict) -> Dict[int, ExclusionReason]:
        """
        Unified Translate phase exclusion reading interface.
        
        CRITICAL: Translate phase only reads, does NOT detect.
        All formats' Translate phase should call this interface.
        
        Args:
            task_state: Task state dictionary
        
        Returns:
            Dict mapping segment_index -> ExclusionReason
        """
        return ExclusionManager.get_excluded_segments(task_state)
    
    @staticmethod
    def validate_exclusion_consistency(task_state: dict, total_segments: int) -> bool:
        """
        Validate exclusion consistency between Extract and Translate phases.
        
        If inconsistency is found, log ERROR.
        
        Args:
            task_state: Task state dictionary
            total_segments: Total number of segments
        
        Returns:
            True if consistent, False otherwise
        """
        excluded_segments = ExclusionManager.get_excluded_segments(task_state)
        
        # Validate segment indices are in valid range
        invalid_indices = [idx for idx in excluded_segments.keys() if idx >= total_segments]
        if invalid_indices:
            logger.error(
                LogModule.EXCLUSION,
                f"ExclusionTranslateAPI: Found {len(invalid_indices)} invalid excluded segment indices "
                f"(out of range): {invalid_indices[:10]}{'...' if len(invalid_indices) > 10 else ''}. "
                f"Total segments: {total_segments}. "
                f"This indicates Extract and Translate phases have different segment counts."
            )
            return False
        
        return True
