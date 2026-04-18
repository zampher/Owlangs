# SPDX-FileCopyrightText: 2025 QinHan
# SPDX-License-Identifier: MPL-2.0

"""
Main application entry point for Owlangs.

This module serves as the main entry point for the FastAPI application.
"""

from .factory import app

# Export the app instance for uvicorn
__all__ = ["app"]
