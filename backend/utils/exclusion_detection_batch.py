# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

"""
Batch exclusion detection service for all document formats.

DEPRECATED: This module is deprecated. Please use the new exclusion module instead.

For backward compatibility, this module re-exports from exclusion.detection:
- ExclusionDetectionBatch

New code should import from exclusion.detection.batch_detector or exclusion directly.
"""

# Backward compatibility: Re-export from new exclusion module
from exclusion.detection.batch_detector import ExclusionDetectionBatch

__all__ = ["ExclusionDetectionBatch"]
