# SPDX-FileCopyrightText: 2025 QinHan
# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

"""
Owlangs application package.

This package contains the refactored application structure with modular
components for better maintainability and organization.
"""

import sys as _sys
from pathlib import Path as _Path

# PyInstaller packages this module as backend.app.*. However, large parts of the
# codebase still import modules using the bare "app.*" path (e.g.
# `from app.middleware import ...`). In the regular source tree this works
# because `backend` is already on `PYTHONPATH`, but once packaged we lose the
# "app" top-level name. By aliasing the current package object to `sys.modules
# ['app']`, we make sure those imports continue to work both in development and
# in the bundled executable.
# Always set the app module alias, regardless of the current module name
_sys.modules.setdefault("app", _sys.modules[__name__])

# Mimic backend.cli's behavior by ensuring the backend directory itself is on
# sys.path. This allows legacy imports like `import logger` or `import utils`
# (which expect backend directory to be treated as sys.path root) to continue
# working when running `python -m backend.app`.
_backend_dir = _Path(__file__).resolve().parent  # backend/app
_project_root = _backend_dir.parent  # backend/

def _ensure_path(path: _Path):
    str_path = str(path)
    if str_path not in _sys.path:
        _sys.path.insert(0, str_path)

_ensure_path(_project_root)
_ensure_path(_backend_dir)

# Set up app.* aliases for compatibility with imports like "from app.utils import ..."
# This is needed because PyInstaller packages modules as backend.app.* but code uses app.*
# IMPORTANT: This must be done before importing any other modules
for module_path in [
    ("backend.app", "app"),
    ("backend.app.services", "app.services"),
    ("backend.app.services.task", "app.services.task"),
    ("backend.app.services.translation", "app.services.translation"),
    ("backend.app.services.translation.chunk_size_service", "app.services.translation.chunk_size_service"),
    ("backend.app.utils", "app.utils"),
    ("backend.app.utils.encoding_utils", "app.utils.encoding_utils"),
    ("backend.app.config", "app.config"),
    ("backend.app.config.pagination_config", "app.config.pagination_config"),
    ("backend.app.models", "app.models"),
    ("backend.app.models.service", "app.models.service"),
    ("backend.app.models.translation_segment", "app.models.translation_segment"),
]:
    src, dst = module_path
    try:
        import importlib
        module = importlib.import_module(src)
        _sys.modules.setdefault(dst, module)
    except ModuleNotFoundError:
        # Frozen runtime fallback: PyInstaller may only keep the app.* namespace
        try:
            alt_src = src.replace("backend.", "", 1)  # e.g., backend.app.models -> app.models
            if alt_src != src:
                module = importlib.import_module(alt_src)
                _sys.modules.setdefault(dst, module)
        except ModuleNotFoundError:
            pass

# Ensure backend.utils is imported early so that its own aliasing logic
# (registering itself as `utils`) is executed before other modules request it.
# This prevents ModuleNotFoundError for `utils.*` when running via
# `python -m backend.app` or in packaged environments.
for _module_name in ("backend.utils", "backend.logger"):
    try:  # noqa: F401 - imported for side effects
        __import__(_module_name)
    except ModuleNotFoundError:
        pass

# When invoked as `python -m backend.app`, Python expects a __main__ module.
# Provide a minimal proxy that delegates to backend.cli.main for consistency
# with the CLI entry point.
if __name__ == "__main__":
    from backend.cli import main as _cli_main

    _cli_main()

from .app_main import app
from .factory import create_app

__all__ = [
    "app",
    "create_app",
]
