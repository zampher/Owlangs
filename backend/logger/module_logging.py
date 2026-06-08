# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

"""
Module logging extension for unified_logger.

This module provides optional module-based filtering through monkey patching
unified_logger. Module logging is disabled by default and can be enabled via configuration.
When enabled, only messages for modules enabled in module_log_manager are emitted.
"""

from .logger import unified_logger, LogModule
from .module_log_manager import module_log_manager

# Save original unified_logger methods (all take module, message, **kwargs)
_original_debug = unified_logger.debug
_original_info = unified_logger.info
_original_warning = unified_logger.warning
_original_error = unified_logger.error
_original_success = unified_logger.success
_original_trace = unified_logger.trace

# Track if module logging is enabled
_module_logging_enabled = False


def _require_two_args(method_name: str, args: tuple) -> tuple:
    """Require (module, message). Raise TypeError for single-arg so wrong calls are caught early."""
    if len(args) < 2:
        if len(args) == 1:
            raise TypeError(
                f"UnifiedLogger.{method_name}(module, message) requires two arguments. "
                f"You passed a single argument (message-only). "
                f"Use e.g. logger.{method_name}(LogModule.SYSTEM, 'your message') instead."
            )
        raise TypeError(
            f"UnifiedLogger.{method_name}(module, message) requires (module, message). "
            f"Got {len(args)} positional arguments."
        )
    if len(args) > 2:
        raise TypeError(
            f"UnifiedLogger.{method_name}(module, message) takes exactly 2 positional arguments, got {len(args)}."
        )
    module, message = args[0], args[1]
    if not isinstance(module, LogModule):
        raise TypeError(
            f"UnifiedLogger.{method_name}(module, message): first argument must be LogModule, got {type(module).__name__}. "
            f"Use e.g. logger.{method_name}(LogModule.SYSTEM, 'your message')."
        )
    return module, message


def _debug_with_module(*args, **kwargs):
    """Filter debug by module_log_manager then forward. Requires (module, message)."""
    module, message = _require_two_args("debug", args)
    if not module_log_manager.is_enabled(module, "DEBUG"):
        return
    _original_debug(module, message, **kwargs)


def _info_with_module(*args, **kwargs):
    """Filter info by module_log_manager then forward. Requires (module, message)."""
    module, message = _require_two_args("info", args)
    if not module_log_manager.is_enabled(module, "INFO"):
        return
    _original_info(module, message, **kwargs)


def _warning_with_module(*args, **kwargs):
    """Filter warning by module_log_manager then forward. Requires (module, message)."""
    module, message = _require_two_args("warning", args)
    if not module_log_manager.is_enabled(module, "WARNING"):
        return
    _original_warning(module, message, **kwargs)


def _error_with_module(*args, **kwargs):
    """Filter error by module_log_manager then forward. Requires (module, message)."""
    module, message = _require_two_args("error", args)
    if not module_log_manager.is_enabled(module, "ERROR"):
        return
    _original_error(module, message, **kwargs)


def _success_with_module(*args, **kwargs):
    """Filter success by module_log_manager then forward. Requires (module, message)."""
    module, message = _require_two_args("success", args)
    if not module_log_manager.is_enabled(module, "SUCCESS"):
        return
    _original_success(module, message, **kwargs)


def _trace_with_module(*args, **kwargs):
    """Filter trace by module_log_manager then forward. Requires (module, message)."""
    module, message = _require_two_args("trace", args)
    if not module_log_manager.is_enabled(module, "TRACE"):
        return
    _original_trace(module, message, **kwargs)


def enable_module_logging():
    """
    Enable module-based filtering by monkey patching unified_logger methods.

    Only log levels enabled per module in module_log_manager will be emitted.
    """
    global _module_logging_enabled

    if _module_logging_enabled:
        return

    unified_logger.debug = _debug_with_module
    unified_logger.info = _info_with_module
    unified_logger.warning = _warning_with_module
    unified_logger.error = _error_with_module
    unified_logger.success = _success_with_module
    unified_logger.trace = _trace_with_module

    _module_logging_enabled = True


def is_module_logging_enabled() -> bool:
    """Return whether module-based filtering is currently enabled."""
    return _module_logging_enabled
