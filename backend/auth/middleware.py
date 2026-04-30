# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

from fastapi import Request, Response, HTTPException
from fastapi.responses import RedirectResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from .session_manager import AuthSessionManager
from .config import AuthConfig
from backend.config.config_loader import get_unified_config
from logger import unified_logger as logger

try:
    from logger.logger import LogModule
except Exception:
    LogModule = None
_LOG_AUTH = getattr(LogModule, "AUTH", "AUTH")


def _is_desktop_localhost(request: Request) -> bool:
    """True if request is from localhost with X-Client: desktop (desktop app → no redirect)."""
    client = getattr(request, "client", None)
    if not client or not isinstance(client, tuple):
        return False
    host = client[0] if len(client) > 0 else None
    if host not in ("127.0.0.1", "::1"):
        return False
    return (request.headers.get("x-client") or "").strip().lower() == "desktop"


class AuthMiddleware(BaseHTTPMiddleware):
    """Authentication middleware"""
    
    def __init__(self, app: ASGIApp, session_manager: AuthSessionManager, config: AuthConfig):
        super().__init__(app)
        self.session_manager = session_manager
        self.config = config
        
        # Paths that don't require authentication
        self.exempt_paths = {
            "/",
            "/login",
            "/logout",
            "/static",
            "/i18n",
            "/docs",
            "/redoc",
            "/openapi.json",
            "/favicon.ico",
            "/export",
            "/preview",
            "/select",
            "/legacy",
        }
        
        # API paths that don't require authentication (SPA gets JSON, not 302).
        # Desktop app may call these without a session; exempt so route runs (returns guest user).
        self.exempt_api_paths = {
            "/api/v1/auth/login",
            "/api/v1/auth/logout",
            "/api/v1/config/app",
            "/api/v1/auth/message-config",
            "/api/v1/auth/user",
            "/api/v1/auth/user/permissions",
            "/api/v1/auth/app-config",
            "/api/v1/auth/app-config/setting",
            "/api/v1/auth/config",
            "/api/v1/auth/donor/status",
            "/api/v1/auth/test-ai-platform",
            "/api/v1/auth/mineru/test-connection",
            "/api/v1/auth/settings/batch",
            "/api/v1/auth/ai-platform-status",
            "/api/v1/api/settings/update-check",
            "/api/v1/api/settings/system",
            "/api/v1/api/settings/static-json",
            "/auth/login",
            "/auth/logout",
            "/auth/message-config",
            "/auth/config",
            "/auth/app-config",
            "/auth/app-config/public",
            "/auth/app-config/raw-secrets",
            "/auth/donor/status",
            "/auth/user",
            "/auth/user/permissions",
            "/auth/test-ai-platform",
            "/auth/mineru/test-connection",
            "/auth/settings/batch",
            "/auth/ai-platform-status",
            "/api/settings/update-check",
            "/api/settings/system",
            "/api/settings/static-json",
            "/api/settings/paths",
        }
        # API path prefixes: any path starting with these is exempt (e.g. desktop guest can use glossaries).
        self.exempt_api_path_prefixes = (
            "/auth/glossaries",
            "/api/v1/auth/glossaries",
        )
        
        # API paths that require authentication but should be handled by API
        self.api_paths = {
            "/api/anonymize",
            "/service/generate-glossary",
        }
    
    async def dispatch(self, request: Request, call_next):
        """Handle request"""
        # If system auth is disabled, bypass checks
        try:
            unified_config = get_unified_config()
            if unified_config.auth_required is False:
                return await call_next(request)
        except Exception as e:
            logger.warning(_LOG_AUTH, f"Failed to check auth_required in middleware: {e}")
            # If we can't check auth_required, allow the request to proceed
            # This prevents 401 errors when config loading fails
            return await call_next(request)
        path = request.url.path
        method = request.method
        
        # Handle CORS preflight requests (OPTIONS)
        if method == "OPTIONS":
            return await call_next(request)
        
        # Check if it's an exempt path
        if self._is_exempt_path(path):
            return await call_next(request)
        
        # Check if it's an exempt API path (GET requests only)
        if self._is_exempt_api_path(path, method):
            return await call_next(request)
        
        # Check if it's an API path that requires authentication
        if self._is_api_path(path):
            # For API paths, return JSON error instead of redirect
            if not await self.session_manager.is_authenticated(request):
                from fastapi.responses import JSONResponse
                return JSONResponse(
                    status_code=401,
                    content={"error": "Authentication required", "detail": "Please login first"}
                )
            return await call_next(request)
        
        # Desktop app from localhost with X-Client: desktop → allow without redirect (get_current_user will return admin)
        if _is_desktop_localhost(request):
            return await call_next(request)
        
        # Check if user is authenticated
        if not await self.session_manager.is_authenticated(request):
            # Build login URL with next parameter
            login_url = f"/login?next={path}"
            return RedirectResponse(url=login_url, status_code=302)
        
        # User is authenticated, continue processing request
        return await call_next(request)
    
    def _is_exempt_path(self, path: str) -> bool:
        """Check if path is exempt from authentication"""
        # Exact match
        if path in self.exempt_paths:
            return True
        
        # Static file path matching
        if path.startswith("/static/") or path.startswith("/i18n/"):
            return True
        
        # API documentation path matching
        if path.startswith("/docs") or path.startswith("/redoc"):
            return True
        
        # Export and preview path matching
        if path.startswith("/export/") or path.startswith("/preview/"):
            return True
        
        return False
    
    def _is_exempt_api_path(self, path: str, method: str) -> bool:
        """Check if API path is exempt from authentication"""
        if path in self.exempt_api_paths:
            return True
        for prefix in self.exempt_api_path_prefixes:
            if path.startswith(prefix):
                return True
        # Allow OPTIONS requests for all API paths (CORS preflight)
        if method == "OPTIONS":
            return True
        return False
    
    def _is_api_path(self, path: str) -> bool:
        """Check if path is an API path that requires authentication"""
        for api_path in self.api_paths:
            if path.startswith(api_path):
                return True
        return False
