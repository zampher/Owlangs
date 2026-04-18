# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0
import logging
import json
import random
from typing import Any, Dict, Optional, overload
from contextlib import contextmanager
import contextvars
from pathlib import Path
from logging.handlers import TimedRotatingFileHandler, RotatingFileHandler
import os

try:
    from concurrent_log_handler import ConcurrentRotatingFileHandler
    RotatingHandlerClass = ConcurrentRotatingFileHandler
except ImportError:
    RotatingHandlerClass = RotatingFileHandler
from .log_messages import get_log_message, initialize_log_language
from enum import Enum


# NOTE:
# Avoid importing config.config_loader at module import time.
# During startup, config_loader may import logger; importing it here would create a cycle:
# config_loader -> logger (package) -> logger.py -> config_loader
_ctx_reading_unified_config: contextvars.ContextVar[bool] = contextvars.ContextVar(
    "reading_unified_config", default=False
)


def _get_unified_config():
    # Guard against recursive config reads:
    # system_config.load_from_file() may log, which calls unified_logger, which may
    # read logging config from unified_config again (infinite recursion).
    if _ctx_reading_unified_config.get():
        raise RuntimeError("Recursive unified_config read detected")
    token = _ctx_reading_unified_config.set(True)
    try:
        from config.config_loader import get_unified_config as _get
        return _get()
    finally:
        _ctx_reading_unified_config.reset(token)


# Custom log levels
class LogLevel(Enum):
    """Custom log levels for the application"""
    TRACE = "TRACE"
    INFO = "INFO"
    SUCCESS = "SUCCESS"
    WARNING = "WARNING"
    ERROR = "ERROR"
    DEBUG = "DEBUG"


class LogModule(Enum):
    """Log module categories.

    Naming principle: use directory name or its abbreviation (e.g. auth -> AUTH,
    converter -> CONVERT). All names must be 8 characters or less for compact log format.
    """
    # Directory/domain -> abbreviation
    AUTH = "AUTH"              # 4 chars - auth/
    ROUTE = "ROUTE"            # 5 chars - routes / API endpoints
    CONFIG = "CONFIG"          # 6 chars - config/
    CONVERT = "CONVERT"        # 7 chars - converter/
    WORKFLOW = "WORKFLOW"      # 8 chars - workflow/
    ANONY = "ANONY"            # 5 chars - anonymize/
    EXTRACT = "EXTRACT"        # 7 chars - extractor/
    TRANS = "TRANS"            # 5 chars - translator/, translation (app/services, utils)
    EXCLUSION = "EXCLUSION"    # 8 chars - exclusion/
    EXPORT = "EXPORT"          # 6 chars - exporter/, app/services/download
    LAYOUT = "LAYOUT"          # 6 chars - layout/
    RESTOR = "RESTOR"          # 6 chars - document restoration / PDF rendering
    GLOSSARY = "GLOSSARY"      # 8 chars - glossary/
    PROMPTS = "PROMPTS"        # 7 chars - prompts/
    # Feature/domain (no single top-level dir)
    UPLOAD = "UPLOAD"          # 6 chars - file upload
    DETECT = "DETECT"          # 6 chars - language detection
    ANONYMIZ = "ANONYMIZ"          # 8 chars - document analysis
    SYSTEM = "SYSTEM"             # 6 chars - system / app/services/platform, etc.
    FONT = "FONT"              # 4 chars - font (utils/font_utils)
    SPACY = "SPACY"            # 5 chars - spacy
    


def get_log_level_from_config():
    """Get log level from configuration file"""
    try:
        unified_config = _get_unified_config()
        level_str = unified_config.system.logging.level.upper()
        return getattr(logging, level_str, logging.INFO)
    except Exception:
        return logging.INFO


def get_log_json_enabled() -> bool:
    """Return whether JSON log output is enabled via config (optional)."""
    try:
        unified_config = _get_unified_config()
        return bool(getattr(unified_config.system.logging, 'json', False))
    except Exception:
        return False


def _get_logging_config_safe() -> Any:
    try:
        return _get_unified_config().system.logging
    except Exception:
        class _Empty:
            pass
        return _Empty()


def get_sampling_rates() -> Dict[str, float]:
    """Return sampling rates for debug/trace logs (0.0~1.0)."""
    lg = _get_logging_config_safe()
    try:
        sampling = getattr(lg, 'sampling', None) or {}
        debug_rate = float(getattr(sampling, 'debug', 1.0))
        trace_rate = float(getattr(sampling, 'trace', 1.0))
    except Exception:
        debug_rate = 1.0
        trace_rate = 1.0
    return {"debug": max(0.0, min(1.0, debug_rate)), "trace": max(0.0, min(1.0, trace_rate))}


def get_truncation_limits() -> Dict[str, Optional[int]]:
    """Return max message length per level; None means no limit."""
    lg = _get_logging_config_safe()
    default = {"trace": None, "debug": 4000, "info": 2000, "success": 2000, "warning": 2000, "error": 4000}
    try:
        trunc = getattr(lg, 'truncate', None) or {}
        for k in list(default.keys()):
            val = getattr(trunc, k, None)
            if isinstance(val, int) and val > 0:
                default[k] = val
            if val is None:
                # keep default
                pass
    except Exception:
        pass
    return default


# Backward-compatible alias within this module: ensure no direct import-time dependency on config_loader.
# Some parts of this module still call get_unified_config(); route them through the safe accessor.
get_unified_config = _get_unified_config


def get_content_display_mode() -> str:
    """Get content display mode from config: 'full', 'partial', or 'none'."""
    lg = _get_logging_config_safe()
    try:
        mode = getattr(lg, 'content_display', 'none')
        if mode in ('full', 'partial', 'none'):
            return mode
    except Exception:
        pass
    return 'none'  # Default: hide content


def format_content_for_log(content: str, max_length: int = 500) -> str:
    """
    Format content for logging based on content_display configuration.
    
    Args:
        content: The content to format
        max_length: Maximum length for partial display (default: 500). 
                   If None, return full content (only when mode is 'full')
    
    Returns:
        Formatted content string based on config:
        - 'full': Return full content (or truncated if max_length is set)
        - 'partial': Return truncated content with '...' suffix
        - 'none': Return '[Content hidden]'
    """
    mode = get_content_display_mode()
    
    if mode == 'none':
        return '[Content hidden]'
    elif mode == 'partial':
        if max_length is None:
            max_length = 500  # Default to 500 for partial mode
        if len(content) <= max_length:
            return content
        return f"{content[:max_length]}... [truncated, total {len(content)} chars]"
    else:  # mode == 'full'
        if max_length is not None and len(content) > max_length:
            return f"{content[:max_length]}... [truncated, total {len(content)} chars]"
        return content


# Add SUCCESS/TRACE levels to logging system
SUCCESS_LEVEL = 25  # Between INFO (20) and WARNING (30)
logging.addLevelName(SUCCESS_LEVEL, "SUCCESS")
TRACE_LEVEL = 5  # Below DEBUG (10)
logging.addLevelName(TRACE_LEVEL, "TRACE")

# Expose custom levels on logging module so config like "TRACE"/"SUCCESS" works
if not hasattr(logging, "SUCCESS"):
    logging.SUCCESS = SUCCESS_LEVEL  # type: ignore[attr-defined]
if not hasattr(logging, "TRACE"):
    logging.TRACE = TRACE_LEVEL  # type: ignore[attr-defined]

# Add trace() method to standard Logger class so all loggers can use logger.trace()
def trace(self, message, *args, **kwargs):
    """Log a message with severity 'TRACE' (more verbose than DEBUG)."""
    if self.isEnabledFor(TRACE_LEVEL):
        self._log(TRACE_LEVEL, message, args, **kwargs)

# Add trace method to Logger class if it doesn't exist
if not hasattr(logging.Logger, 'trace'):
    logging.Logger.trace = trace  # type: ignore[attr-defined]


class CompactFormatter(logging.Formatter):
    """Compact formatter for workflow logs"""
    
    def __init__(self, show_date=True, datefmt='%Y-%m-%d %H:%M:%S'):
        super().__init__()
        self.show_date = show_date
        self.datefmt = datefmt
    
    def format(self, record):
        # Get log_module from record, with fallback to SYSTEM
        # CRITICAL: extra['log_module'] should be set by module_logging functions
        # If it's not set, ModuleInfoFilter should have set it to 'SYSTEM'
        # Python logging adds extra dict keys as attributes to LogRecord
        # So extra['log_module'] becomes record.log_module
        module = getattr(record, 'log_module', 'SYSTEM')
        
        # Map log levels to compact format (no emoji heuristics)
        level_mapping = {
            'TRACE': 'TRACE',  # Fixed typo: was 'TARCE'
            'INFO': 'INFO',
            'SUCCESS': 'SUCC',
            'WARNING': 'WARN', 
            'ERROR': 'ERROR',
            'DEBUG': 'DEBUG'
        }
        level = level_mapping.get(record.levelname, 'INFO')
        
        # Format level and module with fixed width for alignment
        level_str = level.ljust(5)  # Fixed width: 5 characters
        module_str = module.ljust(8)  # Fixed width: 8 characters
        
        if self.show_date:
            timestamp = self.formatTime(record, self.datefmt)
            return f"{timestamp} [{level_str}] [{module_str}] {record.getMessage()}"
        else:
            timestamp = self.formatTime(record, '%H:%M:%S')
            return f"{timestamp} [{level_str}] [{module_str}] {record.getMessage()}"


class JSONFormatter(logging.Formatter):
    """JSON formatter for structured logging."""
    def format(self, record: logging.LogRecord) -> str:
        module = getattr(record, 'log_module', 'SYSTEM')
        payload: Dict[str, Any] = {
            "ts": self.formatTime(record, '%Y-%m-%d %H:%M:%S'),
            "level": record.levelname,
            "module": module,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        # Attach known context fields if present (from LoggerContext or extra)
        for key in ("request_id", "task_id", "user"):
            if hasattr(record, key):
                value = getattr(record, key)
                if value is not None:  # Only include non-None values
                    payload[key] = value
        return json.dumps(payload, ensure_ascii=False)


# ---- Context support ----
# NOTE: Keep typing compatible with Python 3.9 (no PEP 604 `X | Y`).
from typing import Optional

_ctx_request_id: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar("request_id", default=None)
_ctx_task_id: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar("task_id", default=None)
_ctx_user: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar("user", default=None)


class LoggerContext:
    """Context holder for correlating logs (request/task/user)."""
    @staticmethod
    def set(request_id: Optional[str] = None, task_id: Optional[str] = None, user: Optional[str] = None) -> None:
        if request_id is not None:
            _ctx_request_id.set(request_id)
        if task_id is not None:
            _ctx_task_id.set(task_id)
        if user is not None:
            _ctx_user.set(user)

    @staticmethod
    def clear() -> None:
        _ctx_request_id.set(None)
        _ctx_task_id.set(None)
        _ctx_user.set(None)

    @staticmethod
    def current() -> Dict[str, Any]:
        return {
            "request_id": _ctx_request_id.get(),
            "task_id": _ctx_task_id.get(),
            "user": _ctx_user.get(),
        }


class ModuleInfoFilter(logging.Filter):
    """Filter that ensures all log records have log_module field (default: SYSTEM)."""
    def filter(self, record: logging.LogRecord) -> bool:  # type: ignore[override]
        # Ensure log_module field exists (default: SYSTEM, matching LogModule.SYSTEM.value)
        # CRITICAL: Only set default if log_module doesn't exist - don't override existing values
        # Python logging adds extra dict keys as attributes to LogRecord, so check if it exists
        if not hasattr(record, 'log_module'):
            record.log_module = 'SYSTEM'
        elif getattr(record, 'log_module', None) is None:
            # If log_module exists but is None, set to SYSTEM
            record.log_module = 'SYSTEM'
        # If log_module already has a value (from extra parameter), keep it
        return True


class LevelRangeFilter(logging.Filter):
    """Filter logs by level range or explicit allowed levels."""
    def __init__(self, min_level: Optional[int] = None, max_level: Optional[int] = None, allow_levels: Optional[set[int]] = None):
        super().__init__()
        self.min_level = min_level
        self.max_level = max_level
        self.allow_levels = allow_levels

    def filter(self, record: logging.LogRecord) -> bool:  # type: ignore[override]
        lvl = record.levelno
        if self.allow_levels is not None:
            return lvl in self.allow_levels
        if self.min_level is not None and lvl < self.min_level:
            return False
        if self.max_level is not None and lvl > self.max_level:
            return False
        return True


# Initialize log language from config
initialize_log_language()


def _get_console_enabled() -> bool:
    try:
        return bool(get_unified_config().system.logging.console_enabled)
    except Exception:
        return True


def _get_file_enabled() -> bool:
    try:
        return bool(get_unified_config().system.logging.file_enabled)
    except Exception:
        return True


def _get_attach_to_root() -> bool:
    try:
        return bool(getattr(get_unified_config().system.logging, 'attach_to_root', False))
    except Exception:
        return False


def _get_max_file_size_mb() -> int:
    """Get max log file size in MB from config"""
    try:
        unified_config = get_unified_config()
        max_size = getattr(unified_config.system.logging, 'max_file_size_mb', 10)
        return int(max_size) if max_size else 10
    except Exception:
        return 10  # Default 10MB


def _get_backup_count() -> int:
    """Get backup count from config"""
    try:
        unified_config = get_unified_config()
        backup_count = getattr(unified_config.system.logging, 'backup_count', 7)
        return int(backup_count) if backup_count else 7
    except Exception:
        return 7  # Default 7 backups


# Unified log format - use CompactFormatter for consistent format
# All application logs use unified_logger with this format
_compact_formatter = CompactFormatter(show_date=True)
_json_formatter = JSONFormatter()

console_handler = None
if _get_console_enabled():
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(_json_formatter if get_log_json_enabled() else _compact_formatter)
    # Add filter to ensure all logs have log_module field
    console_handler.addFilter(ModuleInfoFilter())

# Output to file (with size and time rotation)
# Use unified logs directory path (C:\Users\Public\Owlangs\logs on Windows deployment)
try:
    if _get_file_enabled():
        from utils.path_utils import get_logs_dir
        logs_dir = get_logs_dir()
        logs_dir.mkdir(parents=True, exist_ok=True)
        log_file = logs_dir / "app.log"

        # Get configuration values
        max_file_size_mb = _get_max_file_size_mb()
        backup_count = _get_backup_count()
        max_bytes = max_file_size_mb * 1024 * 1024  # Convert MB to bytes

        # Use RotatingFileHandler for size-based rotation, combined with manual time-based cleanup
        file_handler = RotatingHandlerClass(
            filename=str(log_file),
            maxBytes=max_bytes,
            backupCount=backup_count,
            encoding="utf-8"
        )
        file_handler.setFormatter(_json_formatter if get_log_json_enabled() else _compact_formatter)
        file_handler.addFilter(ModuleInfoFilter())
        file_handler.addFilter(LevelRangeFilter(min_level=logging.INFO))
        file_handler.addFilter(LevelRangeFilter(allow_levels={SUCCESS_LEVEL, logging.INFO, logging.WARNING, logging.ERROR, logging.CRITICAL}))

        # extra debug/trace file
        debug_log_file = logs_dir / "app-debug.log"
        file_handler_debug = RotatingHandlerClass(
            filename=str(debug_log_file),
            maxBytes=max_bytes,
            backupCount=backup_count,
            encoding="utf-8"
        )
        file_handler_debug.setFormatter(_json_formatter if get_log_json_enabled() else _compact_formatter)
        file_handler_debug.addFilter(ModuleInfoFilter())
        file_handler_debug.addFilter(LevelRangeFilter(allow_levels={TRACE_LEVEL, logging.DEBUG}))
    else:
        file_handler = None
        file_handler_debug = None
except Exception:
    # If file handler initialization fails, keep only console output to avoid affecting main process
    file_handler = None
    file_handler_debug = None

# Handlers are attached by UnifiedLogger.__init__ (no global_logger; single unified_logger only)

# Sync to root logger, so loggers obtained by modules through logging.getLogger(__name__) also write to file
if _get_attach_to_root():
    root_logger = logging.getLogger()
    # Set root log level from configuration file
    config_log_level = get_log_level_from_config()
    if root_logger.level > config_log_level or root_logger.level == logging.NOTSET:
        root_logger.setLevel(config_log_level)
    root_existing = {type(h).__name__ for h in root_logger.handlers}
    if console_handler and 'StreamHandler' not in root_existing:
        root_logger.addHandler(console_handler)
    if _get_file_enabled():
        if file_handler and 'TimedRotatingFileHandler' not in root_existing:
            root_logger.addHandler(file_handler)
        if 'TimedRotatingFileHandler' not in root_existing:
            if 'file_handler_debug' in locals() and file_handler_debug:
                root_logger.addHandler(file_handler_debug)


class I18nLogger:
    """Logger wrapper that supports internationalized messages"""
    
    def __init__(self, logger_name: str = None):
        self.logger = logging.getLogger(logger_name or "TranslaterLogger")
    
    def _log_with_i18n(self, level: int, message_key: str, **kwargs):
        """Log message with internationalization"""
        try:
            message = get_log_message(message_key, **kwargs)
            self.logger.log(level, message)
        except Exception:
            # Fallback to original message key if i18n fails
            self.logger.log(level, message_key)
    
    def debug(self, message_key: str, **kwargs):
        """Log debug message with i18n"""
        self._log_with_i18n(logging.DEBUG, message_key, **kwargs)
    
    def info(self, message_key: str, **kwargs):
        """Log info message with i18n"""
        self._log_with_i18n(logging.INFO, message_key, **kwargs)
    
    def warning(self, message_key: str, **kwargs):
        """Log warning message with i18n"""
        self._log_with_i18n(logging.WARNING, message_key, **kwargs)
    
    def error(self, message_key: str, **kwargs):
        """Log error message with i18n"""
        self._log_with_i18n(logging.ERROR, message_key, **kwargs)
    
    def critical(self, message_key: str, **kwargs):
        """Log critical message with i18n"""
        self._log_with_i18n(logging.CRITICAL, message_key, **kwargs)

    def success(self, message_key: str, **kwargs):
        """Log success message with i18n"""
        self._log_with_i18n(SUCCESS_LEVEL, message_key, **kwargs)

    def trace(self, message_key: str, **kwargs):
        """Log trace message with i18n (more verbose than DEBUG)"""
        self._log_with_i18n(TRACE_LEVEL, message_key, **kwargs)


# Create global i18n logger instance
i18n_logger = I18nLogger()


class UnifiedLogger:
    """
    Unified logger: all log methods require (module, message). No message-only API.

    Use e.g. logger.debug(LogModule.SYSTEM, "message"). Single-arg logger.debug("message")
    raises TypeError so wrong call sites are caught early.
    """

    def __init__(self, name: str = "TranslaterLogger", show_date: bool = True):
        self.logger = logging.getLogger(name)
        self.logger.setLevel(get_log_level_from_config())
        self.show_date = show_date
        
        # Prevent propagation to avoid duplicate logs
        self.logger.propagate = False
        
        # Create formatter based on config (JSON or compact)
        if get_log_json_enabled():
            self.formatter = JSONFormatter()
        else:
            if show_date:
                datefmt = '%Y-%m-%d %H:%M:%S'
            else:
                datefmt = '%H:%M:%S'
            self.formatter = CompactFormatter(show_date=show_date, datefmt=datefmt)
        
        # Clear existing handlers and add our custom handler
        self.logger.handlers.clear()
        if _get_console_enabled():
            ch = logging.StreamHandler()
            ch.setFormatter(self.formatter)
            self.logger.addHandler(ch)
        # Also attach shared file handlers so unified logs are persisted
        if _get_file_enabled():
            if 'file_handler' in globals() and file_handler:
                self.logger.addHandler(file_handler)
            if 'file_handler_debug' in globals() and file_handler_debug:
                self.logger.addHandler(file_handler_debug)
    
    def set_show_date(self, show_date: bool):
        """Dynamically change date display"""
        self.show_date = show_date
        if isinstance(self.formatter, CompactFormatter):
            if show_date:
                datefmt = '%Y-%m-%d %H:%M:%S'
            else:
                datefmt = '%H:%M:%S'
            self.formatter.show_date = show_date
            self.formatter.datefmt = datefmt
        
        # Recreate handlers to apply the change
        self.logger.handlers.clear()
        if _get_console_enabled():
            ch = logging.StreamHandler()
            ch.setFormatter(self.formatter)
            self.logger.addHandler(ch)
        if _get_file_enabled():
            if 'file_handler' in globals() and file_handler:
                self.logger.addHandler(file_handler)
            if 'file_handler_debug' in globals() and file_handler_debug:
                self.logger.addHandler(file_handler_debug)

    def set_level(self, level_name: str):
        """Dynamically set logger level (e.g., TRACE/DEBUG/INFO)."""
        try:
            self.logger.setLevel(getattr(logging, level_name.upper(), logging.INFO))
        except Exception:
            self.logger.setLevel(logging.INFO)

    @property
    def level(self) -> int:
        """Delegate to underlying logger level (for code that checks logger.level <= logging.DEBUG)."""
        return self.logger.level

    def isEnabledFor(self, level: int) -> bool:
        """Delegate to underlying logger (for code that checks isEnabledFor(logging.DEBUG))."""
        return self.logger.isEnabledFor(level)

    @staticmethod
    def _require_module_message(method_name: str, args: tuple, kwargs: dict) -> tuple:
        """
        Enforce (module, message) signature. Raises TypeError for single-arg or wrong-type calls
        so mistakes are caught early instead of confusing 'missing argument' errors.
        Returns (module, message) for valid calls.
        """
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
            # PyInstaller/frozen env can load the same enum from different import paths,
            # so isinstance(module, LogModule) may be False even for LogModule.AUTH.
            # Accept any Enum with a .value that matches a LogModule member and normalize.
            if isinstance(module, Enum) and getattr(module, "value", None) is not None:
                try:
                    module = LogModule(module.value)
                except ValueError:
                    pass
            if not isinstance(module, LogModule):
                raise TypeError(
                    f"UnifiedLogger.{method_name}(module, message): first argument must be LogModule, got {type(module).__name__}. "
                    f"Use e.g. logger.{method_name}(LogModule.SYSTEM, 'your message')."
                )
        if not isinstance(message, str):
            message = str(message)
        return module, message

    def _log(self, level: LogLevel, module: LogModule, message: str, **kwargs):
        """Internal logging method with custom levels and module categories"""
        # Format message with kwargs
        if kwargs:
            try:
                formatted_message = message.format(**kwargs)
            except (KeyError, ValueError):
                formatted_message = message
        else:
            formatted_message = message
        
        # Sampling for DEBUG/TRACE
        if level in (LogLevel.DEBUG, LogLevel.TRACE):
            rates = get_sampling_rates()
            rate = rates['debug'] if level == LogLevel.DEBUG else rates['trace']
            if rate < 1.0 and random.random() > rate:
                return

        # Add icons for specific levels
        if level == LogLevel.SUCCESS:
            formatted_message = f"✅ {formatted_message}"
        elif level == LogLevel.WARNING:
            formatted_message = f"⚠️ {formatted_message}"
        elif level == LogLevel.ERROR:
            formatted_message = f"❌ {formatted_message}"
        
        # Map custom levels to standard logging levels
        level_mapping = {
            LogLevel.TRACE: TRACE_LEVEL,
            LogLevel.INFO: logging.INFO,
            LogLevel.SUCCESS: SUCCESS_LEVEL,  # Use custom SUCCESS level
            LogLevel.WARNING: logging.WARNING,
            LogLevel.ERROR: logging.ERROR,
            LogLevel.DEBUG: logging.DEBUG
        }
        
        log_level = level_mapping[level]

        # Truncation policy per level
        limits = get_truncation_limits()
        key = 'trace' if level == LogLevel.TRACE else (
            'debug' if level == LogLevel.DEBUG else (
            'success' if level == LogLevel.SUCCESS else (
            'warning' if level == LogLevel.WARNING else (
            'error' if level == LogLevel.ERROR else 'info'))))
        max_len = limits.get(key)
        if isinstance(max_len, int) and max_len > 0 and isinstance(formatted_message, str):
            if len(formatted_message) > max_len:
                formatted_message = formatted_message[:max_len] + " ...(truncated)"
        # Attach context fields
        extra = {'log_module': module.value}
        ctx = LoggerContext.current()
        for k, v in ctx.items():
            if v is not None:
                extra[k] = v
        self.logger.log(log_level, formatted_message, extra=extra)
    
    # Unified logging interface
    def log(self, level: LogLevel, module: LogModule, message: str, **kwargs):
        """Unified logging method with level and module parameters"""
        self._log(level, module, message, **kwargs)
    
    # Only (module, message) is supported. Single-arg e.g. debug("msg") raises TypeError at runtime.
    @overload
    def info(self, module: LogModule, message: str, **kwargs: Any) -> None: ...
    def info(self, *args: Any, **kwargs: Any) -> None:
        module, message = self._require_module_message("info", args, kwargs)
        self._log(LogLevel.INFO, module, message, **kwargs)

    @overload
    def success(self, module: LogModule, message: str, **kwargs: Any) -> None: ...
    def success(self, *args: Any, **kwargs: Any) -> None:
        module, message = self._require_module_message("success", args, kwargs)
        self._log(LogLevel.SUCCESS, module, message, **kwargs)

    @overload
    def warning(self, module: LogModule, message: str, **kwargs: Any) -> None: ...
    def warning(self, *args: Any, **kwargs: Any) -> None:
        module, message = self._require_module_message("warning", args, kwargs)
        self._log(LogLevel.WARNING, module, message, **kwargs)

    @overload
    def error(self, module: LogModule, message: str, **kwargs: Any) -> None: ...
    def error(self, *args: Any, **kwargs: Any) -> None:
        module, message = self._require_module_message("error", args, kwargs)
        self._log(LogLevel.ERROR, module, message, **kwargs)

    @overload
    def debug(self, module: LogModule, message: str, **kwargs: Any) -> None: ...
    def debug(self, *args: Any, **kwargs: Any) -> None:
        module, message = self._require_module_message("debug", args, kwargs)
        self._log(LogLevel.DEBUG, module, message, **kwargs)

    @overload
    def trace(self, module: LogModule, message: str, **kwargs: Any) -> None: ...
    def trace(self, *args: Any, **kwargs: Any) -> None:
        module, message = self._require_module_message("trace", args, kwargs)
        self._log(LogLevel.TRACE, module, message, **kwargs)


def configure_third_party_loggers():
    """Centralize third-party loggers level configuration."""
    try:
        ThirdPartyLoggerManager.apply_from_config()
    except Exception:
        pass


class HealthCheckFilter(logging.Filter):
    """Filter out /api/health access logs (or pass through)."""
    
    def __init__(self, enabled: bool = True):
        """
        Initialize the health check filter.

        Args:
            enabled: If True, completely hide /api/health logs. If False, allow all logs unchanged.
        """
        super().__init__()
        self.enabled = enabled
    
    def filter(self, record: logging.LogRecord) -> bool:  # type: ignore[override]
        """Filter out /api/health endpoint access logs if enabled."""
        # If special handling is disabled, allow all logs unchanged
        if not self.enabled:
            return True

        # 使用完整日志消息匹配 /api/health，避免依赖 uvicorn 的内部字段名
        try:
            msg = record.getMessage()
        except Exception:
            msg = str(getattr(record, "msg", ""))

        # 命中 /api/health 时直接丢弃该条日志
        if "/api/health" in msg:
            return False

        # 其他日志一律放行
        return True


class StatusAPIFilter(logging.Filter):
    """
    Filter to reduce log level for status API requests.
    
    Status API is polled frequently by frontend, so we downgrade these logs
    to DEBUG level to reduce log verbosity.
    """
    
    def filter(self, record: logging.LogRecord) -> bool:  # type: ignore[override]
        """Downgrade status API requests to DEBUG level so they can be hidden when INFO is used."""
        is_status_request = False

        # Prefer structured attribute if available (uvicorn access logs)
        if hasattr(record, "request_line"):
            if "/service/status/" in str(getattr(record, "request_line", "")):
                is_status_request = True

        # Fallback: inspect rendered message (covers other logging paths)
        if not is_status_request:
            try:
                msg = record.getMessage()
            except Exception:
                msg = str(getattr(record, "msg", ""))
            if "/service/status/" in msg:
                is_status_request = True

        if is_status_request:
            record.levelno = logging.DEBUG
            record.levelname = "DEBUG"
            # Discard status polling logs when logger level is INFO or higher
            uvicorn_access = logging.getLogger("uvicorn.access")
            if uvicorn_access.level > logging.DEBUG:
                return False

        return True


class AccessLogFormatter(CompactFormatter):
    """
    Custom formatter for uvicorn access logs using unified CompactFormatter format.
    Converts uvicorn access log format to unified format.
    
    If the log record is not an access log (missing request_line, client_addr, etc.),
    falls back to CompactFormatter to format it normally.
    """
    
    def format(self, record: logging.LogRecord) -> str:
        # Check if this is actually an access log (has request_line attribute)
        # If not, use parent CompactFormatter to format normally
        if not hasattr(record, 'request_line'):
            # Not an access log, use parent formatter
            return super().format(record)
        
        # Extract access log information from uvicorn access log record
        client_addr = getattr(record, 'client_addr', 'unknown')
        request_line = getattr(record, 'request_line', '')
        status_code = getattr(record, 'status_code', '')
        
        # If request_line is empty, this might not be a valid access log
        # Fall back to parent formatter to show the actual message
        if not request_line:
            return super().format(record)
        
        # Format message in unified format
        # Format: "GET /path HTTP/1.1" 200 from 127.0.0.1:port
        message = f'"{request_line}" {status_code} from {client_addr}'
        
        # Set log_module to SYSTEM for access logs (or could be WORKFLOW)
        module = getattr(record, 'log_module', 'SYSTEM')
        
        # Map log levels to compact format（保持原有行为：不再强制改写 /api/health 级别，交由 HealthCheckFilter 决定是否丢弃）
        level_mapping = {
            'TRACE': 'TRACE',
            'INFO': 'INFO',
            'SUCCESS': 'SUCC',
            'WARNING': 'WARN', 
            'ERROR': 'ERROR',
            'DEBUG': 'DEBUG'
        }
        level = level_mapping.get(record.levelname, 'INFO')
        
        # Format level and module with fixed width for alignment
        level_str = level.ljust(5)  # Fixed width: 5 characters
        module_str = module.ljust(8)  # Fixed width: 8 characters
        
        if self.show_date:
            timestamp = self.formatTime(record, self.datefmt)
            return f"{timestamp} [{level_str}] [{module_str}] {message}"
        else:
            timestamp = self.formatTime(record, '%H:%M:%S')
            return f"{timestamp} [{level_str}] [{module_str}] {message}"


def get_uvicorn_log_config():
    """Get uvicorn log configuration with timestamps for all logs."""
    import logging
    
    # Get configuration for health check filter
    filter_health_check = True  # Default: filter health check logs
    try:
        unified_config = get_unified_config()
        # Check if filter_health_check_logs is set in logging config
        if hasattr(unified_config.system.logging, 'filter_health_check_logs'):
            filter_health_check = bool(unified_config.system.logging.filter_health_check_logs)
    except Exception:
        # If config is not available, use default (filter enabled)
        pass
    
    # Create a formatter with timestamp
    formatter = logging.Formatter(
        fmt='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Configure uvicorn loggers
    # Add filters for health check, status API, and module info
    access_handler_config = {
        "formatter": "access_unified",
        "class": "logging.StreamHandler",
        "stream": "ext://sys.stdout",
    }
    filters_config = {}
    filters_list = []
    
    # Always add module info filter to ensure log_module is set
    filters_list.append("module_info_filter")
    filters_config["module_info_filter"] = {
        "()": "logger.logger.ModuleInfoFilter",
    }
    
    if filter_health_check:
        filters_list.append("health_check_filter")
        filters_config["health_check_filter"] = {
            "()": "logger.logger.HealthCheckFilter",
            "enabled": True,
        }
    
    # Always add status API filter to downgrade status API logs to DEBUG
    filters_list.append("status_api_filter")
    filters_config["status_api_filter"] = {
        "()": "logger.logger.StatusAPIFilter",
    }
    
    if filters_list:
        access_handler_config["filters"] = filters_list
    
    log_config = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "default": {
                "()": "uvicorn.logging.DefaultFormatter",
                "fmt": "%(asctime)s [%(levelname)s] %(message)s",
                "datefmt": "%Y-%m-%d %H:%M:%S",
                "use_colors": True,
            },
            "access": {
                "()": "uvicorn.logging.AccessFormatter",
                "fmt": '%(asctime)s - %(client_addr)s - "%(request_line)s" %(status_code)s',
                "datefmt": "%Y-%m-%d %H:%M:%S",
                "use_colors": True,
            },
            "access_unified": {
                "()": "logger.logger.AccessLogFormatter",
                "show_date": True,
                "datefmt": "%Y-%m-%d %H:%M:%S",
            },
        },
        "handlers": {
            "default": {
                "formatter": "default",
                "class": "logging.StreamHandler",
                "stream": "ext://sys.stdout",
            },
            "access": access_handler_config,
        },
        "filters": filters_config,
        "loggers": {
            "uvicorn": {
                "handlers": ["default"],
                "level": "INFO",
                "propagate": False,
            },
            "uvicorn.error": {
                "handlers": ["default"],
                "level": "INFO",
                "propagate": False,
            },
            "uvicorn.access": {
                "handlers": ["access"],
                "level": "INFO",  # Set to TRACE for detailed access logs
                "propagate": False,
            },
        },
    }
    
    return log_config


@contextmanager
def temporary_log_level(logger_name: str, level: int):
    """Temporarily set a specific logger's level and restore it after the block."""
    logger_obj = logging.getLogger(logger_name)
    original = logger_obj.level
    try:
        logger_obj.setLevel(level)
        yield
    finally:
        logger_obj.setLevel(original)


@contextmanager
def temporary_log_levels(levels: Dict[str, int]):
    """Temporarily set multiple loggers' levels and restore after the block.
    Example: with temporary_log_levels({'presidio-analyzer': logging.DEBUG}): ...
    """
    originals: Dict[str, int] = {}
    try:
        for name, lvl in levels.items():
            lg = logging.getLogger(name)
            originals[name] = lg.level
            lg.setLevel(lvl)
        yield
    finally:
        for name, lvl in originals.items():
            logging.getLogger(name).setLevel(lvl)


class ThirdPartyLoggerManager:
    """Manage third-party libraries' logger levels/handlers from config."""
    _handler_factories: Dict[str, Any] = {}

    @staticmethod
    def register_handler(name: str, factory: Any) -> None:
        ThirdPartyLoggerManager._handler_factories[name] = factory

    @staticmethod
    def apply_from_config() -> None:
        try:
            unified_config = get_unified_config()
            tp = getattr(unified_config.system.logging, 'third_party_loggers', None)
            if not tp:
                # default policy
                defaults = {
                    'presidio-analyzer': { 'level': 'INFO', 'propagate': False },
                    'spacy': { 'level': 'WARNING' },
                    'langdetect': { 'level': 'WARNING' },
                }
                ThirdPartyLoggerManager._apply_map(defaults)
                return
            # Convert mapping-like object to dict
            if hasattr(tp, 'items'):
                mapping = { k: v for k, v in tp.items() }
            else:
                mapping = dict(tp)
            ThirdPartyLoggerManager._apply_map(mapping)
        except Exception:
            # Fallback defaults if config not available
            ThirdPartyLoggerManager._apply_map({
                'presidio-analyzer': { 'level': 'INFO', 'propagate': False },
                'spacy': { 'level': 'WARNING' },
                'langdetect': { 'level': 'WARNING' },
            })

    @staticmethod
    def _apply_map(mapping: Dict[str, Any]) -> None:
        for name, spec in mapping.items():
            try:
                logger_obj = logging.getLogger(name)
                level_name = str(spec.get('level', 'WARNING')).upper()
                logger_obj.setLevel(getattr(logging, level_name, logging.WARNING))
                if 'propagate' in spec:
                    logger_obj.propagate = bool(spec['propagate'])
                # attach pre-registered handlers if requested
                attach = spec.get('attach_handlers') or []
                for handler_name in attach:
                    factory = ThirdPartyLoggerManager._handler_factories.get(handler_name)
                    if callable(factory):
                        handler = factory()
                        if handler and not ThirdPartyLoggerManager._has_same_handler(logger_obj, handler):
                            logger_obj.addHandler(handler)
            except Exception:
                continue

    @staticmethod
    def _has_same_handler(logger_obj: logging.Logger, handler: logging.Handler) -> bool:
        for h in logger_obj.handlers:
            if type(h) is type(handler):
                return True
        return False


# Create unified logger instances
unified_logger = UnifiedLogger()  # Default: shows date
unified_logger_frontend = UnifiedLogger(name="TranslaterLoggerFrontend", show_date=False)  # For frontend: no date