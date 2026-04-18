# SPDX-FileCopyrightText: 2025 QinHan
# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

"""
Application factory for Owlangs.

This module provides a factory function to create and configure the FastAPI application
with all necessary middleware, routes, and dependencies.
"""

import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

try:
    # Prefer importing version from backend package when available
    from backend import __version__  # type: ignore[import]
except Exception:  # pragma: no cover - fallback for unusual import contexts
    __version__ = "unknown"  # type: ignore[assignment]
from utils.resource_utils import resource_path
from logger import unified_logger
from logger.logger import LogModule
# Delay import of routes to reduce startup time - import only when needed
# from app.routes import main_router, service_router, glossary_router, settings_router
# from app.routes.export import router as export_router
from backend.app.middleware import RequestIDMiddleware, HTTPSRedirectMiddleware
# Delay import of anonymize router - import only when registering routes
# from anonymize.routes import router as anonymize_router

# Enable module logging as early as possible, before importing any modules that use logging
# This ensures that module-specific log tags (like [SPACY]) are correctly applied
# Note: Config will be loaded in lifespan, avoid loading here to prevent duplicate loading
try:
    from logger.module_logging import is_module_logging_enabled, enable_module_logging
    # Module logging will be enabled in lifespan after config is loaded
    # Skip loading config here to avoid duplicate loading
except Exception:
    # Module logging initialization failed, continue without it
    pass

# Import authentication modules
try:
    from auth import AuthConfig, AuthMiddleware, auth_router, auth_compat_router, init_auth
    AUTH_AVAILABLE = True
except ImportError as e:
    print(f"[ERROR] AUTH ImportError: {e}")
    AUTH_AVAILABLE = False
    # Authentication module unavailable, skipping auth features
except Exception as e:
    print(f"[ERROR] AUTH Exception: {e}")
    import traceback
    traceback.print_exc()
    AUTH_AVAILABLE = False
    # Authentication module initialization failed, skipping auth features


def _cleanup_owlangs_temp_files():
    """Clean up owlangs temporary files in user's temp directory."""
    try:
        import tempfile
        import shutil
        
        # Get user's temp directory
        temp_dir = Path(tempfile.gettempdir())
        
        # Find all owlangs* folders
        owlangs_folders = list(temp_dir.glob("owlangs*"))
        
        if owlangs_folders:
            unified_logger.info(LogModule.SYSTEM, f"[STARTUP] Found {len(owlangs_folders)} owlangs temp folder(s) to clean up")
            for folder in owlangs_folders:
                try:
                    if folder.is_dir():
                        shutil.rmtree(folder, ignore_errors=True)
                        unified_logger.info(LogModule.SYSTEM, f"[STARTUP] Cleaned up temp folder: {folder}")
                except Exception as e:
                    unified_logger.warning(LogModule.SYSTEM, f"[STARTUP] Failed to clean up {folder}: {e}")
        else:
            unified_logger.debug(LogModule.SYSTEM, "[STARTUP] No owlangs temp folders found to clean up")
    except Exception as e:
        # Don't fail startup if cleanup fails
        try:
            unified_logger.warning(LogModule.SYSTEM, f"[STARTUP] Failed to clean up owlangs temp files: {e}")
        except Exception:
            pass  # Logger might not be available yet


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    import asyncio
    
    # Initialize variables for shutdown cleanup
    _ai_platform_task = None
    _version_check_task = None
    
    # Startup
    unified_logger.info(LogModule.SYSTEM, "[STARTUP] Application lifespan startup initiated")

    # Ensure config/data dirs exist (e.g. ~/Library/Application Support/Owlangs when frozen on macOS)
    try:
        from utils.path_utils import ensure_directories
        ensure_directories()
    except Exception as e:
        unified_logger.warning(LogModule.SYSTEM, f"[STARTUP] Failed to ensure directories: {e}")

    # Clean up owlangs temporary files
    try:
        unified_logger.info(LogModule.SYSTEM, "[STARTUP] Cleaning up temporary files...")
        _cleanup_owlangs_temp_files()
        unified_logger.info(LogModule.SYSTEM, "[STARTUP] Temporary files cleanup completed")
    except Exception as e:
        unified_logger.warning(LogModule.SYSTEM, f"[STARTUP] Failed to clean up temporary files: {e}")
    
    # Reload logging config from file and re-apply level so configs/system.json (e.g. DEBUG) is respected
    try:
        import logging
        from backend.config.config_loader import get_unified_config
        from utils.path_utils import get_config_file_path

        # Use existing config if already loaded, avoid clearing cache to prevent duplicate loading
        config = get_unified_config()
        level_str = (getattr(config.system.logging, "level", None) or "INFO").upper()
        unified_logger.set_level(level_str)
        system_json_path = get_config_file_path("system.json")
        log_level = logging.getLevelName(unified_logger.logger.level)
        unified_logger.info(LogModule.SYSTEM, f"[STARTUP] Backend log level: {log_level} (from {system_json_path}, logging.level={level_str})")
        print(f"[INFO] [STARTUP] Backend log level: {log_level} (from {system_json_path})")
        print("[INFO] [STARTUP] Configuration loaded with caching (optimized to avoid duplicate loading)")
    except Exception as e:
        print(f"[WARNING] [STARTUP] Failed to apply log level from config: {e}")
    
    # Initialize authentication if available
    if AUTH_AVAILABLE:
        try:
            print("[INFO] [STARTUP] Initializing authentication...")
            auth_config = AuthConfig.get_config()
            init_auth(auth_config)
            ldap_status = "enabled" if auth_config.ldap_enabled else "disabled"
            print(f"[INFO] [STARTUP] Authentication initialized (LDAP: {ldap_status})")
            # Run password recovery if enabled in local.json (resets default admin to Changeme)
            try:
                from backend.auth.password_recovery import reset_admin_password_if_recovery_enabled
                if reset_admin_password_if_recovery_enabled():
                    print("[INFO] [STARTUP] Password recovery completed: admin password was reset")
            except Exception as pr_err:
                print(f"[WARNING] [STARTUP] Password recovery check failed: {pr_err}")
            # First install: if no users exist, create default admin with password Changeme
            try:
                from backend.auth.unified_user_store import get_unified_user_store
                store = get_unified_user_store()
                if store.ensure_default_admin_if_empty(auth_config.default_username):
                    print("[INFO] [STARTUP] First install: default admin created with password Changeme")
            except Exception as ei_err:
                print(f"[WARNING] [STARTUP] First-install default admin check failed: {ei_err}")
        except Exception as e:
            print(f"[WARNING] [STARTUP] Authentication module initialization failed: {e}")
    
    # Initialize third-party loggers
    try:
        print("[INFO] [STARTUP] Configuring third-party loggers...")
        from logger.logger import configure_third_party_loggers
        configure_third_party_loggers()
        print("[INFO] [STARTUP] Third-party loggers configured")
    except Exception as e:
        print(f"[WARNING] [STARTUP] Failed to configure third-party loggers: {e}")
    
    # Initialize module logging based on config (moved from module import time to avoid duplicate config loading)
    try:
        from logger.module_logging import is_module_logging_enabled, enable_module_logging
        if not is_module_logging_enabled():
            config = get_unified_config()
            if getattr(config.system.logging, 'enable_module_logging', False):
                enable_module_logging()
                print("[INFO] [STARTUP] Module logging enabled")
    except Exception as e:
        print(f"[WARNING] [STARTUP] Failed to enable module logging: {e}")
    
    # Initialize static.json from template if missing
    try:
        print("[INFO] [STARTUP] Checking static.json...")
        from utils.path_utils import get_config_file_path, get_template_file_path
        import json
        import shutil
        
        static_json_path = get_config_file_path("static.json")
        static_json_template_path = get_template_file_path("static.json.template")
        
        # Check if static.json exists
        if not static_json_path.exists():
            print(f"[INFO] [STARTUP] static.json not found at {static_json_path}, creating from template...")
            
            # Ensure configs directory exists
            static_json_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Check if template exists
            if static_json_template_path.exists():
                # Copy template to static.json
                shutil.copy2(static_json_template_path, static_json_path)
                print(f"[INFO] [STARTUP] Created static.json from template at {static_json_path}")
            else:
                # Create default static.json if template doesn't exist (no app version in file; injected on read)
                default_data = {
                    "_schema_version": 1,
                    "translation_stats": {
                        "document_count": 0,
                        "page_count": 0,
                        "last_updated": None
                    }
                }
                with open(static_json_path, 'w', encoding='utf-8') as f:
                    json.dump(default_data, f, ensure_ascii=False, indent=2)
                print(f"[INFO] [STARTUP] Created default static.json at {static_json_path}")
        else:
            print(f"[INFO] [STARTUP] static.json already exists at {static_json_path}")
    except Exception as e:
        print(f"[WARNING] [STARTUP] Failed to initialize static.json: {e}")
        import traceback
        traceback.print_exc()
    
    # Initialize Presidio model manager in background thread (non-blocking startup)
    # This avoids slow model checks blocking the startup process
    try:
        print("[INFO] [STARTUP] Starting Presidio model status check in background...")
        import threading
        from anonymize.model_manager import PresidioModelManager
        
        def _check_presidio_models():
            try:
                PresidioModelManager.print_model_status()
                print("[INFO] [STARTUP] Presidio model manager status checked (background)")
            except Exception as e:
                print(f"[WARNING] [STARTUP] Presidio model manager check failed: {e}")
        
        presidio_thread = threading.Thread(target=_check_presidio_models, daemon=True)
        presidio_thread.start()
        print("[INFO] [STARTUP] Presidio model check started in background thread")
    except Exception as e:
        print(f"[WARNING] [STARTUP] Presidio model manager unavailable (anonymization disabled): {e}")
    
    # Start font registration in background thread (non-blocking startup)
    # This ensures fonts are available when PDF generation is needed
    try:
        print("[INFO] [STARTUP] Starting font registration in background...")
        from utils.font_utils import FontUtils
        FontUtils.register_all_fonts(background=True)
        print("[INFO] [STARTUP] Font registration started in background thread")
    except Exception as e:
        print(f"[WARNING] [STARTUP] Failed to start font registration: {e}")
    
    # Preload translation configuration to ensure it's loaded at startup
    try:
        print("[INFO] [STARTUP] Preloading translation configuration...")
        from backend.config.translation_config import get_translation_config
        config = get_translation_config()
        defaults = config.deep_split_defaults
        unified_logger.info(
            LogModule.CONFIG,
            f"[STARTUP] [TRANSLATION_CONFIG] Preloaded deep_split defaults: "
            f"pdf={defaults.pdf}, docx={defaults.docx}, txt={defaults.txt}, "
            f"md={defaults.md}, html={defaults.html}, default={defaults.default}"
        )
        print("[INFO] [STARTUP] Translation configuration preloaded")
    except Exception as e:
        # Do not fail startup if translation_config has issues; log and continue.
        try:
            unified_logger.warning(LogModule.CONFIG, f"[STARTUP] [TRANSLATION_CONFIG] Failed to preload config: {e}")
        finally:
            print(f"[WARNING] [STARTUP] Failed to preload translation config: {e}")
    
    # Run one round of AI platform tests at startup so status is populated before first request
    if AUTH_AVAILABLE:
        try:
            from auth.ai_platform_scheduler import run_one_round_ai_platform_tests, run_hourly_ai_platform_tests
            from backend.config.config_loader import get_unified_config
            
            # Check if startup AI platform tests are enabled in config
            config = get_unified_config()
            startup_tests_enabled = getattr(config.system, 'ai_platform_startup_tests', True)
            
            if startup_tests_enabled:
                print("[INFO] [STARTUP] Testing configured AI platforms (this may take a moment)...")
                # Run startup tests asynchronously (non-blocking)
                asyncio.create_task(run_one_round_ai_platform_tests())
                print("[INFO] [STARTUP] AI platform status tests started in background")
            else:
                print("[INFO] [STARTUP] Skipping AI platform startup tests (disabled in config)")
            
            # Start hourly task regardless
            _ai_platform_task = asyncio.create_task(run_hourly_ai_platform_tests())
            print("[INFO] [STARTUP] Hourly AI platform status task started")
        except Exception as e:
            print(f"[WARNING] [STARTUP] Failed to run AI platform tests or start hourly task: {e}")
    
    # macOS launch complete signal is now sent from font_utils.py after font registration
    # This ensures the signal is sent immediately after font registration completes
    print("[DEBUG] [STARTUP] macOS launch signal will be sent after font registration")

    # Start background version update check (non-blocking; logs result when completed)
    try:
        from backend.app.services.version_service import (
            check_update as check_update_service,
            run_daily_version_check,
        )

        async def _run_update_check_once():
            try:
                result = await check_update_service()
                if result.get("ok"):
                    current = result.get("current_version")
                    latest = result.get("latest_version")
                    update_available = result.get("update_available")
                    release_url = result.get("release_url")
                    if update_available:
                        unified_logger.info(
                            LogModule.SYSTEM,
                            f"[UPDATE-CHECK] New version available: {latest} "
                            f"(current: {current}). See: {release_url}",
                        )
                    else:
                        unified_logger.info(
                            LogModule.SYSTEM,
                            f"[UPDATE-CHECK] You are running the latest version: {current}",
                        )
                else:
                    unified_logger.warning(
                        LogModule.SYSTEM,
                        "[UPDATE-CHECK] Failed to fetch latest version from GitHub "
                        f"(error={result.get('error')})",
                    )
            except Exception as e:
                unified_logger.error(
                    LogModule.SYSTEM,
                    f"[UPDATE-CHECK] Unexpected error during update check: {e}",
                    exc_info=True,
                )

        asyncio.create_task(_run_update_check_once())
        print("[INFO] [STARTUP] Scheduled background update check task")
        
        # Start daily version check loop (runs every 24 hours)
        _version_check_task = asyncio.create_task(run_daily_version_check())
        print("[INFO] [STARTUP] Daily version check task started")
    except Exception as e:
        print(f"[WARNING] [STARTUP] Failed to schedule update check task: {e}")
    
    yield
    
    # Shutdown
    print("\n[INFO] Application shutdown initiated, cleaning up resources...")
    
    # Cancel hourly AI platform task
    try:
        if _ai_platform_task is not None and not _ai_platform_task.done():
            _ai_platform_task.cancel()
            try:
                await _ai_platform_task
            except asyncio.CancelledError:
                pass
    except Exception:
        pass
    
    # Cancel daily version check task
    try:
        if _version_check_task is not None and not _version_check_task.done():
            _version_check_task.cancel()
            try:
                await _version_check_task
            except asyncio.CancelledError:
                pass
    except Exception:
        pass

    # Cleanup Redis if it was initialized
    try:
        from utils.redis_manager import _redis_manager
        if _redis_manager is not None:
            _redis_manager.cleanup()
    except Exception as e:
        pass  # Redis cleanup failed
    
    # Cleanup any other resources
    try:
        # Cancel any running translation tasks
        from backend.app.services.task import task_manager
        for task_id, task_state in list(task_manager.get_all_tasks().items()):
            if task_state.get("is_processing"):
                task_ref = task_state.get("current_task_ref")
                if task_ref and not task_ref.done():
                    task_ref.cancel()
                    try:
                        await task_ref
                    except asyncio.CancelledError:
                        pass
                    except Exception:
                        pass
    except Exception as e:
        pass  # Task cleanup failed
    
    print("[INFO] Application shutdown complete")


def create_app() -> FastAPI:
    """
    Create and configure the FastAPI application.
    
    Returns:
        Configured FastAPI application instance
    """
    # API tags metadata
    tags_metadata = [
        {
            "name": "Service API",
            "description": "Core service API for submitting, managing, and downloading translation tasks.",
        },
        {
            "name": "Application",
            "description": "Application-related endpoints such as metadata and default parameters.",
        },
        {
            "name": "Temp",
            "description": "Test interfaces.",
        },
    ]

    # Log application version early in startup
    unified_logger.info(
        LogModule.SYSTEM,
        f"[STARTUP] Owlangs backend version: {__version__}",
    )

    # Log current license / trial status early in startup
    try:
        from backend.config.secrets_manager import get_secrets_manager
        from backend.utils.donor_trial import is_effective_activated
        from backend.utils.donor_license import decode_license_payload
        from backend.utils.machine_id import get_machine_id

        secrets_manager = get_secrets_manager()
        donor_activation = secrets_manager.get_donor_activation()
        activated = donor_activation.get("activated", False)
        license_token = donor_activation.get("license_token")
        trial_start_date = donor_activation.get("trial_start_date")

        license_edition_internal = None
        license_expiry = None
        if license_token and not str(license_token).startswith("SIMPLE_"):
            payload, _ = decode_license_payload(str(license_token))
            if payload:
                license_edition_internal = (payload.get("license_key") or "").strip() or None
                license_expiry = (payload.get("expiry") or "").strip() or None

        # Map to human-readable edition:
        # - Desktop deployment (PRO): Standard / Professional / Enterprise (if license_key == PRO-WEB)
        # - Web deployment (PRO-WEB): always treated as Enterprise from product perspective,
        #   regardless of activation state; activation only affects trial / feature state.
        deployment_edition = (os.environ.get("DONOR_EDITION") or "PRO").strip().upper()
        if deployment_edition == "PRO-WEB":
            edition_label = "Enterprise"
        else:
            if not activated and not license_edition_internal:
                edition_label = "Standard"
            elif license_edition_internal == "PRO":
                edition_label = "Professional"
            elif license_edition_internal == "PRO-WEB":
                edition_label = "Enterprise"
            else:
                edition_label = license_edition_internal or "Standard"

        effective_activated, trial_ends_at, trial_expired = is_effective_activated(
            activated, trial_start_date
        )

        # Log current machine_id used for donor license binding (helps debugging activation issues)
        machine_id = get_machine_id()

        unified_logger.info(
            LogModule.SYSTEM,
            "[LICENSE] Startup license status: edition={edition}, activated={activated}, "
            "effective_activated={effective}, trial_start_date={trial_start}, "
            "trial_ends_at={trial_end}, trial_expired={trial_expired}, license_expiry={license_expiry}, "
            "machine_id={machine_id}",
            edition=edition_label,
            activated=activated,
            effective=effective_activated,
            trial_start=trial_start_date,
            trial_end=trial_ends_at,
            trial_expired=trial_expired,
            license_expiry=license_expiry,
            machine_id=machine_id,
        )
    except Exception as e:  # pragma: no cover - logging helper failure should not break startup
        unified_logger.warning(
            LogModule.SYSTEM,
            f"[LICENSE] Failed to log startup license status: {e}",
        )

    # Create FastAPI app
    app = FastAPI(
        docs_url=None,
        redoc_url=None,
        lifespan=lifespan,
        title="Owlangs API",
        description=f"""
        Owlangs backend service API, providing document translation, status query, result download and other functions.

        **Note**: All task states are stored in the service process memory, service restart will cause all task information to be lost.

        ### Main workflow:
        1.  **`POST /service/translate`**: Submit files and translation parameters containing `workflow_type` to start a background task. The service will automatically generate and return a unique `task_id`.
        2.  **`GET /service/status/{{task_id}}`**: Use the obtained `task_id` to poll this endpoint to get real-time task status.
        3.  **`GET /service/logs/{{task_id}}`**: (Optional) Get real-time translation logs.
        4.  **`GET /service/download/{{task_id}}/{{file_type}}`**: After task completion (when `download_ready` is `true`), download result files through this endpoint.
        5.  **`GET /service/attachment/{{task_id}}/{{identifier}}`**: (Optional) If the task generates attachments (such as glossaries), download through this endpoint.
        6.  **`GET /service/content/{{task_id}}/{{file_type}}`**: After task completion (when `download_ready` is `true`), get file content in JSON format.
        7.  **`POST /service/cancel/{{task_id}}`**: (Optional) Cancel an ongoing task.
        8.  **`POST /service/release/{{task_id}}`**: (Optional) When the task is no longer needed, release all resources it occupies on the server, including temporary files.

        **Version**: {__version__}
        """,
        version=__version__,
        openapi_tags=tags_metadata,
    )

    # Add middleware (order matters - first added is outermost)
    # CORS must be first to handle preflight requests
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # Allow all origins for development
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # Add authentication middleware and routes if available
    if AUTH_AVAILABLE:
        try:
            # Initialize authentication first
            from auth import AuthConfig, init_auth, get_session_manager, get_auth_config
            
            auth_config = AuthConfig.get_config()
            init_auth(auth_config)
            
            # Get session manager and configuration after initialization
            session_manager = get_session_manager()
            auth_config = get_auth_config()
            
            # Add authentication middleware (after CORS)
            app.add_middleware(AuthMiddleware, session_manager=session_manager, config=auth_config)
            
            # Add authentication routes
            # Import routers again to ensure they're in scope
            from auth.routes import auth_router, auth_compat_router
            app.include_router(auth_router)
            app.include_router(auth_compat_router)
        except Exception as e:
            print(f"[ERROR] Authentication module initialization failed: {e}")
            import traceback
            traceback.print_exc()
            pass  # Authentication module initialization failed
    
    # Add other middleware after authentication
    app.add_middleware(RequestIDMiddleware)
    app.add_middleware(HTTPSRedirectMiddleware)

    # Main router (/) and SPA fallback (/static/flutter-web, /static/flutter-web/) before static mount
    from backend.app.routes import main_router
    app.include_router(main_router)
    unified_logger.info(
        LogModule.SYSTEM,
        "[ROUTER] Main router registered successfully",
    )

    # Add static files (after main_router so /static/flutter-web and /static/flutter-web/ return index.html)
    static_dir = resource_path("static")
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

    # Include routers (order matters - auth routes must be registered before main_router)
    from backend.app.routes import settings_router
    from backend.app.routes.export import router as export_router
    try:
        from anonymize.routes import router as anonymize_router
        _anonymize_available = True
    except Exception:
        anonymize_router = None
        _anonymize_available = False
    
    # Register new modular service routes (replacing legacy service_router)
    # Note: glossary_router and segments_router are now included in new_service_router
    # Legacy service_router has been removed - all routes migrated to new_service_router
    try:
        from backend.app.routes import new_service_router
        if new_service_router:
            app.include_router(new_service_router, prefix="/service", tags=["Service API"])
            # Use unified_logger (accepts module as first arg)
            unified_logger.info(
                LogModule.SYSTEM,
                "[ROUTER] New modular service routes registered successfully",
            )
        else:
            raise ImportError("new_service_router is None")
    except ImportError as e:
        # No fallback - new routes are required
        unified_logger.error(
            LogModule.SYSTEM,
            f"[ROUTER] Failed to import new service routes: {e}",
        )
        raise RuntimeError("Service routes are required but not available. Please check routes/service/__init__.py")
    
    app.include_router(settings_router)
    app.include_router(export_router, tags=["Export & Preview"])
    if _anonymize_available and anonymize_router is not None:
        app.include_router(anonymize_router, tags=["Anonymization"])
    
    # Add API v1 routes for frontend compatibility
    if AUTH_AVAILABLE:
        try:
            # Add API v1 routes with proper prefixes
            from auth.routes import auth_router
            app.include_router(auth_router, prefix="/api/v1")
            
            # Add settings router with API v1 prefix
            app.include_router(settings_router, prefix="/api/v1")
            
            # Add service router with API v1 prefix (use new router)
            try:
                from backend.app.routes import new_service_router
                if new_service_router:
                    app.include_router(new_service_router, prefix="/api/v1/service", tags=["Service API"])
                    unified_logger.info(
                        LogModule.SYSTEM,
                        "[ROUTER] API v1 service routes registered successfully",
                    )
                else:
                    raise ImportError("new_service_router is None")
            except ImportError as e:
                unified_logger.error(
                    LogModule.SYSTEM,
                    f"[ROUTER] Failed to import new service routes for API v1: {e}",
                )
                # No fallback - new routes are required
            
        except Exception as e:
            pass  # API v1 routes initialization failed

    return app


# Create the app instance
app = create_app()
