# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

"""
Main page routes for Owlangs.

This module contains routes for the main application pages,
including the home page, settings, admin, and documentation.
"""

import os
from pathlib import Path
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import HTMLResponse, FileResponse, RedirectResponse, Response
from fastapi.openapi.docs import get_swagger_ui_html, get_swagger_ui_oauth2_redirect_html, get_redoc_html

from backend import __version__
from utils.resource_utils import resource_path
from backend.app.services.system_dependency_service import check_system_dependencies

router = APIRouter()

# Get static directory path
STATIC_DIR = resource_path("static")


@router.get("/api/health")
async def health_check():
    """Health check endpoint for monitoring backend status."""
    return {"status": "ok", "version": __version__}


@router.get(
    "/api/system/dependencies",
    summary="Check system dependencies",
    description="Check availability of important third-party dependencies (Pandoc, XeLaTeX, Redis, Calibre, Playwright). Returns installation guidance for missing dependencies.",
    responses={
        200: {
            "description": "Dependency check results",
            "content": {
                "application/json": {
                    "schema": {
                        "type": "object",
                        "properties": {
                            "platform": {"type": "string"},
                            "is_macos": {"type": "boolean"},
                            "all_ok": {"type": "boolean"},
                            "dependencies": {"type": "array"},
                            "missing_count": {"type": "integer"},
                            "missing_required_count": {"type": "integer"},
                            "missing_optional_count": {"type": "integer"},
                            "macos_guidance": {"type": "object"},
                        },
                    }
                }
            }
        }
    }
)
async def system_dependencies_check():
    """Check system dependencies and return installation guidance."""
    return check_system_dependencies()


@router.get("/no-cdn-fonts/{path:path}", include_in_schema=False)
async def no_cdn_fonts_stub(path: str):
    """
    Stub for Flutter fontFallbackBaseUrl='/no-cdn-fonts/'.
    Returns 204 so the client does not get 404; fonts fall back to defaults.
    """
    return Response(status_code=204)


@router.get("/favicon.ico")
async def favicon():
    """Serve favicon.ico file."""
    from fastapi.responses import FileResponse
    favicon_path = Path(STATIC_DIR) / "favicon.ico"
    if favicon_path.exists():
        return FileResponse(favicon_path)
    else:
        from fastapi.responses import Response
        return Response(status_code=204)


def _serve_flutter_index():
    """Return Flutter Web index.html response with no-cache headers, or None if not found.
    
    Also fixes the base href to point to /static/flutter-web/ so resources load correctly.
    Supports East Asian language environments by handling various encodings.
    """
    no_cache_headers = {
        "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
        "Pragma": "no-cache",
        "Expires": "0"
    }
    flutter_web_path = Path(STATIC_DIR) / "flutter-web" / "index.html"
    if flutter_web_path.exists():
        content = None
        # Try multiple encodings common in East Asian environments
        encodings = ['utf-8', 'utf-8-sig', 'gbk', 'gb2312', 'gb18030', 'big5', 'shift_jis', 'euc-kr', 'latin-1']
        for encoding in encodings:
            try:
                content = flutter_web_path.read_text(encoding=encoding)
                break
            except UnicodeDecodeError:
                continue
        
        # If all text encodings fail, read as binary and decode with replacement
        if content is None:
            try:
                raw_bytes = flutter_web_path.read_bytes()
                content = raw_bytes.decode('utf-8', errors='replace')
            except Exception:
                return None
        
        # Fix base href from "/" to "/static/flutter-web/" so resources load correctly
        content = content.replace('<base href="/">', '<base href="/static/flutter-web/">')
        
        # Fix CanvasKit path to use local files (critical for offline/LAN support and mainland China)
        # Replace any Google CDN references with local path
        content = content.replace("canvasKitBaseUrl: '/canvaskit/'", "canvasKitBaseUrl: '/static/flutter-web/canvaskit/'")
        content = content.replace('canvasKitBaseUrl: "/canvaskit/"', "canvasKitBaseUrl: '/static/flutter-web/canvaskit/'")
        content = content.replace("canvasKitBaseUrl: 'https://www.gstatic.com/flutter-canvaskit/'", "canvasKitBaseUrl: '/static/flutter-web/canvaskit/'")
        content = content.replace('canvasKitBaseUrl: "https://www.gstatic.com/flutter-canvaskit/"', "canvasKitBaseUrl: '/static/flutter-web/canvaskit/'")
        
        # If no canvasKitBaseUrl is set but we see initializeEngine, inject it
        if "canvasKitBaseUrl" not in content and "initializeEngine" in content:
            # Inject canvasKitBaseUrl before fontFallbackBaseUrl or after config: {
            content = content.replace(
                "config: {",
                "config: {\n              canvasKitBaseUrl: '/static/flutter-web/canvaskit/',"
            )
        
        # Ensure fontFallbackBaseUrl is set to prevent Google Fonts CDN calls
        if "fontFallbackBaseUrl" not in content and "initializeEngine" in content:
            content = content.replace(
                "canvasKitBaseUrl: '/static/flutter-web/canvaskit/',",
                "canvasKitBaseUrl: '/static/flutter-web/canvaskit/',\n              fontFallbackBaseUrl: '/no-cdn-fonts/',"
            )
        
        # Fix broken HTML structure: add missing </body> tag if absent
        # Some Flutter builds may produce malformed HTML that causes rendering issues
        if "<body>" in content and "</body>" not in content:
            content = content.replace("</html>", "</body>\n</html>")
        
        return HTMLResponse(content=content, headers=no_cache_headers)
    return None


@router.get("/", response_class=HTMLResponse, include_in_schema=False)
async def main_page(request: Request):
    """Serve the main application page - Flutter Web frontend by default."""
    res = _serve_flutter_index()
    if res is not None:
        return res
    # Priority 2: Check if Vue frontend is available
    vue_frontend_path = Path(__file__).parent.parent.parent.parent / "vue-frontend" / "dist" / "index.html"
    if vue_frontend_path.exists():
        no_cache_headers = {
            "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
            "Pragma": "no-cache",
            "Expires": "0"
        }
        return FileResponse(vue_frontend_path, headers=no_cache_headers)
    return RedirectResponse(url="/select", status_code=302)


@router.get("/static/flutter-web", response_class=HTMLResponse, include_in_schema=False)
@router.get("/static/flutter-web/", response_class=HTMLResponse, include_in_schema=False)
async def flutter_web_spa_fallback(request: Request):
    """SPA fallback: serve Flutter index for base-href /static/flutter-web/ so client-side routes work."""
    res = _serve_flutter_index()
    if res is not None:
        return res
    raise HTTPException(status_code=404, detail="Flutter Web frontend not found")


@router.get("/legacy", response_class=HTMLResponse, include_in_schema=False)
async def legacy_frontend(request: Request):
    """Serve the legacy frontend (traditional HTML/JS)."""
    # Temporarily disable authentication check for debugging
    # TODO: Re-enable authentication once auth module is working
    # try:
    #     from auth import get_session_manager
    #     session_manager = get_session_manager()
    #     if not await session_manager.is_authenticated(request):
    #         return RedirectResponse(url="/login?next=/legacy", status_code=302)
    # except Exception:
    #     pass

    index_path = Path(STATIC_DIR) / "index.html"
    if not index_path.exists():
        raise HTTPException(status_code=404, detail="Legacy frontend not found")
    
    no_cache_headers = {
        "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
        "Pragma": "no-cache",
        "Expires": "0"
    }
    return FileResponse(index_path, headers=no_cache_headers)


@router.get("/select", response_class=HTMLResponse, include_in_schema=False)
async def frontend_selector():
    """Serve the frontend selection page."""
    selector_path = Path(STATIC_DIR) / "frontend-selector.html"
    if not selector_path.exists():
        raise HTTPException(status_code=404, detail="Frontend selector not found")
    
    return FileResponse(selector_path)


@router.get("/test-auth", response_class=HTMLResponse, include_in_schema=False)
async def test_auth():
    """Test authentication module availability."""
    try:
        from auth import get_session_manager
        session_manager = get_session_manager()
        return HTMLResponse(f"<h1>Auth module loaded successfully!</h1><p>Session manager: {type(session_manager)}</p>")
    except Exception as e:
        return HTMLResponse(f"<h1>Auth module failed to load!</h1><p>Error: {e}</p>")


@router.get("/test", response_class=HTMLResponse, include_in_schema=False)
async def test_route():
    """Test route to verify routing is working."""
    return HTMLResponse("<h1>Test route working!</h1><p>Main router is properly registered.</p>")


@router.get("/settings", response_class=HTMLResponse, include_in_schema=False)
async def settings_page(request: Request):
    """Serve the settings page."""
    # Redirect to login page if not authenticated
    try:
        from auth import get_session_manager
        session_manager = get_session_manager()
        if not await session_manager.is_authenticated(request):
            return RedirectResponse(url="/login?next=/settings", status_code=302)
    except Exception:
        # Continue directly when authentication module is unavailable
        pass

    settings_path = Path(STATIC_DIR) / "settings.html"
    if not settings_path.exists():
        raise HTTPException(status_code=404, detail="settings.html not found")
    
    no_cache_headers = {
        "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
        "Pragma": "no-cache",
        "Expires": "0"
    }
    return FileResponse(settings_path, headers=no_cache_headers)


@router.get("/admin", response_class=HTMLResponse, include_in_schema=False)
async def main_page_admin(request: Request):
    """Serve the admin page."""
    # Redirect to login page if not authenticated
    try:
        from auth import get_session_manager
        session_manager = get_session_manager()
        if not await session_manager.is_authenticated(request):
            return RedirectResponse(url="/login?next=/admin", status_code=302)
    except Exception:
        # Continue directly when authentication module is unavailable
        pass

    index_path = Path(STATIC_DIR) / "index.html"
    if not index_path.exists():
        raise HTTPException(status_code=404, detail="index.html not found")
    
    no_cache_headers = {
        "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
        "Pragma": "no-cache",
        "Expires": "0"
    }
    return FileResponse(index_path, headers=no_cache_headers)


@router.get("/docs", include_in_schema=False)
async def custom_swagger_ui_html():
    """Serve custom Swagger UI documentation."""
    # Use FastAPI's default Swagger UI assets (bundled with FastAPI)
    # This avoids needing to manually provide swagger-ui-bundle.js and swagger-ui.css
    return get_swagger_ui_html(
        openapi_url="/openapi.json",
        title="Owlangs API Documentation",
    )


@router.get("/swagger-ui-oauth2-redirect.html", include_in_schema=False)
async def swagger_ui_redirect():
    """Handle Swagger UI OAuth2 redirect."""
    return get_swagger_ui_oauth2_redirect_html()


@router.get("/redoc", include_in_schema=False)
async def redoc_html():
    """Serve ReDoc documentation."""
    # Use FastAPI's default ReDoc assets (bundled with FastAPI)
    # This avoids needing to manually provide redoc.standalone.js
    return get_redoc_html(
        openapi_url="/openapi.json",
        title="Owlangs API Documentation",
    )
