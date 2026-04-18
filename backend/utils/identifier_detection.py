# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

"""
Identifier detection utilities for exclusion detection.

DEPRECATED: This module is deprecated. Please use the new exclusion module instead.

For backward compatibility, this module re-exports from exclusion.detection.identifier_detector:
- is_identifier_pattern
- _is_pure_number
- _is_url
- _is_email
- _is_serial_number
- _is_camel_case_identifier
- _is_uppercase_identifier
- _is_punctuation_only
- _is_digits_and_special_chars_only

New code should import from exclusion.detection.identifier_detector or exclusion.detection directly.
"""

# Backward compatibility: Re-export from new exclusion module
from exclusion.detection.identifier_detector import (
    is_identifier_pattern,
    _is_pure_number,
    _is_url,
    _is_email,
    _is_serial_number,
    _is_camel_case_identifier,
    _is_uppercase_identifier,
    _is_punctuation_only,
    _is_digits_and_special_chars_only
)

__all__ = [
    "is_identifier_pattern",
    "_is_pure_number",
    "_is_url",
    "_is_email",
    "_is_serial_number",
    "_is_camel_case_identifier",
    "_is_uppercase_identifier",
    "_is_punctuation_only",
    "_is_digits_and_special_chars_only",
]
