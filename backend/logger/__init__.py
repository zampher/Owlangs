# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

"""
Logger package initialization for Owlangs backend.

Older modules import logger helpers using ``from logger.logger import ...``.
When the project is executed via ``python -m backend.app`` or inside a
PyInstaller bundle, the real module path becomes ``backend.logger.*``.  To keep
legacy imports working, alias this package to the top-level name ``logger``.
"""

import sys as _sys

if __name__ != "logger":
    _sys.modules.setdefault("logger", _sys.modules[__name__])

__all__ = []
from .logger import unified_logger, unified_logger_frontend, LogLevel, LogModule, format_content_for_log
from .module_log_manager import module_log_manager
from .module_logging import enable_module_logging, is_module_logging_enabled

__all__ = [
    "unified_logger",
    "unified_logger_frontend",
    "LogLevel",
    "LogModule",
    "format_content_for_log",
    "module_log_manager",
    "enable_module_logging",
    "is_module_logging_enabled",
]