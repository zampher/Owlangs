# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

"""
Request ID middleware for Owlangs.

This middleware adds a unique request ID to each request and manages logging context.
"""

import os
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from logger.logger import LoggerContext


class RequestIDMiddleware(BaseHTTPMiddleware):
    """Middleware to add request ID and manage logging context."""
    
    def __init__(self, app: ASGIApp):
        super().__init__(app)
    
    async def dispatch(self, request: Request, call_next):
        """Add request ID and manage logging context."""
        try:
            # Generate or get request ID
            req_id = request.headers.get("X-Request-ID") or os.urandom(8).hex()
            
            # Get user from request state (set by auth middleware)
            user = getattr(request.state, 'user', None)
            
            # Set logging context
            LoggerContext.set(
                request_id=req_id, 
                user=getattr(user, 'username', None) if user else None
            )
            
            # Process request
            response = await call_next(request)
            
            # Add request ID to response headers
            response.headers["X-Request-ID"] = req_id
            
            return response
        finally:
            # Clear logging context
            LoggerContext.clear()
