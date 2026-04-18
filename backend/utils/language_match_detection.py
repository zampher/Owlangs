# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

"""
Language match detection utilities for exclusion detection.

DEPRECATED: This module is deprecated. Please use the new exclusion module instead.

For backward compatibility, this module re-exports from exclusion.detection.language_match_detector:
- is_language_match

New code should import from exclusion.detection.language_match_detector or exclusion.detection directly.
"""

# Backward compatibility: Re-export from new exclusion module
from exclusion.detection.language_match_detector import is_language_match

__all__ = ["is_language_match"]
