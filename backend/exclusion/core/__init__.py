# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

"""Core exclusion management classes and functions."""

from exclusion.core.exclusion_reason import ExclusionReason
from exclusion.core.exclusion_manager import ExclusionManager
from exclusion.core.exclusion_detector import detect_exclusion_reason

__all__ = ["ExclusionReason", "ExclusionManager", "detect_exclusion_reason"]

# For backward compatibility, also export from exclusion_manager
# This allows existing code to import from exclusion.core.exclusion_manager
from exclusion.core.exclusion_manager import ExclusionManager as _EM
from exclusion.core.exclusion_detector import detect_exclusion_reason as _DER
