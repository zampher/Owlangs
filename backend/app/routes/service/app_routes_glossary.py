# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

"""
Glossary generation API routes for Owlangs.

This module provides API endpoints for standalone glossary generation.
"""

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from auth.models import User
from auth.routes import get_current_user
from backend.app.models.service import GenerateGlossaryRequest, GenerateGlossaryResponse
from backend.app.services.glossary_generation_service import GlossaryGenerationService
from logger import unified_logger as logger

try:
    from logger.logger import LogModule
except Exception:
    LogModule = None  # avoid NameError if logger.logger fails to load (e.g. circular import)

# Safe module tag for logging when LogModule may be unavailable
_LOG_ROUTE = getattr(LogModule, "ROUTE", "ROUTE")

router = APIRouter(tags=["Glossary"])


@router.post("/generate-glossary", response_model=GenerateGlossaryResponse)
async def generate_glossary(
    request: GenerateGlossaryRequest,
    user: User = Depends(get_current_user)
):
    """
    Generate glossary from document.
    
    This endpoint extracts text from uploaded documents and generates
    a terminology glossary using AI, reusing translation parameters
    for consistency.
    
    Args:
        request: Glossary generation request with document and parameters
        user: Authenticated user
        
    Returns:
        GenerateGlossaryResponse with generated glossary data
    """
    try:
        logger.info(
            _LOG_ROUTE,
            f"User {user.username} requested glossary generation for file: {request.file_name}"
        )
        
        # Validate required parameters
        if not request.base_url or not request.model_id:
            raise HTTPException(
                status_code=400, 
                detail="base_url and model_id are required for glossary generation"
            )
        
        # Initialize glossary generation service
        service = GlossaryGenerationService()
        
        # Generate glossary
        result = await service.generate_glossary(request, user.username)
        
        if result.success:
            logger.info(
                _LOG_ROUTE,
                f"Glossary generation completed for user {user.username}: {result.item_count} terms"
            )
            if result.glossary and len(result.glossary) > 0:
                logger.info(
                    _LOG_ROUTE,
                    f"Glossary content preview (first 10 terms):"
                )
                for idx, (src, dst) in enumerate(list(result.glossary.items())[:10], 1):
                    logger.info(
                        _LOG_ROUTE,
                        f"  [{idx}] {src} -> {dst}"
                    )
                if result.item_count > 10:
                    logger.info(
                        _LOG_ROUTE,
                        f"  ... and {result.item_count - 10} more terms"
                    )
        else:
            logger.warning(
                _LOG_ROUTE,
                f"Glossary generation failed for user {user.username}: {result.message}"
            )
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            _LOG_ROUTE,
            f"Glossary generation API error: {e}"
        )
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.get("/download-glossary/{filename}")
async def download_glossary(
    filename: str,
    user: User = Depends(get_current_user)
):
    """
    Download generated glossary as CSV file.
    
    Args:
        filename: Name of the glossary file to download
        user: Authenticated user
        
    Returns:
        CSV file download
    """
    try:
        # In a real implementation, you would:
        # 1. Validate the filename belongs to the user
        # 2. Retrieve the file from secure storage
        # 3. Return the file
        
        # For now, return a placeholder response
        raise HTTPException(
            status_code=501, 
            detail="Glossary download not yet implemented"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            _LOG_ROUTE,
            f"Glossary download error: {e}"
        )
        raise HTTPException(status_code=500, detail=f"Download failed: {str(e)}")

