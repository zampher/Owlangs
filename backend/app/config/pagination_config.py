# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

"""
Pagination configuration constants.

This module provides centralized configuration for pagination limits across the application.
Modify these values to change pagination behavior globally.
"""

# Maximum number of items that can be requested in a single pagination request
# This is a safety limit to prevent excessive memory usage and API abuse
MAX_PAGINATION_LIMIT: int = 100000

# Default number of items to return when limit is not specified
DEFAULT_PAGINATION_LIMIT: int = 200

# Default limit for segment preview requests (used in frontend)
# This can be increased if needed, but should not exceed MAX_PAGINATION_LIMIT
DEFAULT_SEGMENT_PREVIEW_LIMIT: int = 1000

# Limit for source_preview segments (truncated for performance)
# This is used to limit the number of segments stored in source_preview for quick preview
# The full segments are always stored in source_chunks_cache
SOURCE_PREVIEW_SEGMENTS_LIMIT: int = 200
