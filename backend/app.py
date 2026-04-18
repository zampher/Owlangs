# SPDX-FileCopyrightText: 2025 QinHan
# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0
"""
Entry point for PyInstaller packaging.
This file is used by PyInstaller to create the executable.
It imports the app from the app package.
"""

import os
import sys
from pathlib import Path
from logger import unified_logger, LogModule

_IMPORT_DEBUG_ENABLED = os.environ.get("OWLANGS_DEBUG_IMPORTS", "").strip().lower() in (
    "1",
    "true",
    "yes",
)


def _debug_log(message: str):
    if _IMPORT_DEBUG_ENABLED:
        unified_logger.debug(LogModule.SYSTEM, "[IMPORT_DEBUG] {message}", message=message)


def _log_environment_state():
    _debug_log(f"backend.app __file__ = {__file__}")
    _debug_log(f"Current working directory: {os.getcwd()}")
    _debug_log(f"Python executable: {sys.executable}")
    _debug_log("sys.path (ordered):")
    for idx, path_entry in enumerate(sys.path):
        _debug_log(f"  [{idx}] {path_entry}")
    _debug_log("Environment variables (filtered, OWLANGS*):")
    for key, value in os.environ.items():
        if key.startswith("OWLANGS"):
            _debug_log(f"  {key}={value}")


if _IMPORT_DEBUG_ENABLED:
    _debug_log("==== backend.app import debug enabled ====")
_log_environment_state()

backend_dir = Path(__file__).resolve().parent
project_root = backend_dir.parent

if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))
    _debug_log(f"Inserted backend directory into sys.path: {backend_dir}")

if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))
    _debug_log(f"Inserted project root into sys.path: {project_root}")

# Import the app instance from the app package
# This allows PyInstaller to correctly bundle the application
try:
    _debug_log("Attempting to import app via `from app import app`")
    from app import app
    _debug_log("Successfully imported app via `from app import app`")
except ModuleNotFoundError as exc:
    _debug_log(f"Failed to import app via `from app import app`: {exc!r}")
    project_root = Path(__file__).resolve().parent.parent
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))
        _debug_log(f"Added project root to sys.path: {project_root}")
    _log_environment_state()
    raise

# Export for uvicorn
__all__ = ["app"]

# If running directly (not imported), start the server
# This allows PyInstaller-packaged executables to start the server automatically
if __name__ == "__main__":
    import uvicorn
    from logger.logger import get_uvicorn_log_config
    
    # Default port (can be overridden by environment variable)
    port = int(os.environ.get("OWLANGS_PORT", "8800"))
    
    unified_logger.info(
        LogModule.SYSTEM,
        "Starting Owlangs backend server on port {port}",
        port=port,
    )
    unified_logger.info(
        LogModule.SYSTEM,
        "Owlangs will be available at: http://localhost:{port}",
        port=port,
    )
    
    try:
        uvicorn.run(
            app,
            host="0.0.0.0",
            port=port,
            reload=False,  # Disable reload in packaged executable
            log_level="info",
            log_config=get_uvicorn_log_config()
        )
    except KeyboardInterrupt:
        unified_logger.info(LogModule.SYSTEM, "Server shutdown requested")
        sys.exit(0)

