# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

"""
HTTPS redirect middleware for Owlangs.

This middleware handles HTTPS redirection based on configuration.
"""

from fastapi import Request
from fastapi.responses import RedirectResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp


class HTTPSRedirectMiddleware(BaseHTTPMiddleware):
    """Middleware to handle HTTPS redirection."""
    
    def __init__(self, app: ASGIApp):
        super().__init__(app)
    
    async def dispatch(self, request: Request, call_next):
        """Handle HTTPS redirection if configured."""
        try:
            from backend.config.local_config import LocalConfig
            local_config = LocalConfig.get_config()
            
            # Check if HTTPS is enabled and force redirect is configured
            if local_config.https.enabled and local_config.https.force_redirect:
                proto = request.headers.get('x-forwarded-proto') or request.url.scheme
                host = request.headers.get('host')
                
                # Redirect HTTP to HTTPS
                if proto == 'http' and host:
                    https_url = str(request.url).replace('http://', 'https://', 1)
                    return RedirectResponse(url=https_url, status_code=308)
        except Exception:
            # If configuration loading fails, continue without redirect
            pass
        
        # Continue with normal request processing
        return await call_next(request)
