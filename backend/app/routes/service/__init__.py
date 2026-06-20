# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

"""
Service routes package.

This package contains all service API routes organized by functionality.
"""

from fastapi import APIRouter
from .app_routes_translation import router as translation_router
from .app_routes_batches import router as batches_router
from .app_routes_download import router as download_router
from .app_routes_status import router as status_router
from .app_routes_format_conversion import router as format_router
from .app_routes_glossary import router as glossary_router
from .app_routes_translation_segments import router as segments_router
from .app_routes_formula_check import router as formula_check_router
from .app_routes_debug import router as debug_router

router = APIRouter()
router.include_router(translation_router, tags=["Translation"])
router.include_router(batches_router, tags=["Upload Batches"])
router.include_router(download_router, tags=["Download"])
router.include_router(status_router, tags=["Status"])
router.include_router(format_router, tags=["Format Conversion"])
router.include_router(glossary_router, tags=["Glossary"])
router.include_router(segments_router, tags=["Translation Segments"])
router.include_router(formula_check_router, tags=["LaTeX Formula Check"])
router.include_router(debug_router, tags=["Debug"])

__all__ = ["router"]

