# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

"""
App routes package for Owlangs.

This package contains all route handlers organized by functionality.
"""

from .app_routes_main import router as main_router
from .settings import router as settings_router

# New modular service routes (replacing legacy service_router)
# Legacy service_router has been removed - all routes migrated to new_service_router
try:
    from .service import router as new_service_router
except ImportError as e:
    # No fallback - new routes are required
    print(f"[ERROR] Failed to import new service routes: {e}")
    new_service_router = None

# Import glossary and segments routers from service package for backward compatibility
try:
    from .service.app_routes_glossary import router as glossary_router
    from .service.app_routes_translation_segments import router as segments_router
except ImportError:
    # Fallback if not available
    glossary_router = None
    segments_router = None

__all__ = [
    "main_router",
    "new_service_router",  # New modular router (replaces legacy service_router)
    "glossary_router",
    "settings_router",
    "segments_router",
]
