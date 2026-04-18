# SPDX-FileCopyrightText: 2026 Zampherss
# SPDX-License-Identifier: MPL-2.0

"""
Segment exclusion management for translation segments.

DEPRECATED: This module is deprecated. Please use the new exclusion module instead.

For backward compatibility, this module re-exports from exclusion.core:
- ExclusionReason
- ExclusionManager
- detect_exclusion_reason

New code should import from exclusion.core or exclusion directly.
"""

# Backward compatibility: Re-export from new exclusion module
from exclusion.core import (
    ExclusionReason,
    ExclusionManager,
    detect_exclusion_reason
)

__all__ = ["ExclusionReason", "ExclusionManager", "detect_exclusion_reason"]
