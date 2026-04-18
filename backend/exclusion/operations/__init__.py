# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

"""User operations for exclusion management."""

from exclusion.operations.user_operations import (
    exclude_translation_segment,
    unexclude_translation_segment
)

__all__ = ["exclude_translation_segment", "unexclude_translation_segment"]
