# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

"""
Services package for Owlangs.

This package contains all service modules for the application.
"""

# Import services for easier access
from .task import task_manager
from .version_service import version_service
from .format_conversion_service import format_conversion_service
from .glossary_generation_service import glossary_generation_service
from .smart_glossary_matching_service import smart_glossary_matching_service

# Import platform service
from .platform.platform_service import platform_service

__all__ = [
    "task_manager",
    "version_service",
    "format_conversion_service",
    "glossary_generation_service",
    "smart_glossary_matching_service",
    "platform_service"
]
