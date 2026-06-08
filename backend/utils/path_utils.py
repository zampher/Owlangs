# SPDX-FileCopyrightText: 2026 Zamphersss
# SPDX-License-Identifier: MPL-2.0

import os
import sys
import platform
from pathlib import Path
from typing import Dict, Optional

# Log once when OWLANGS_CONFIG_PATH overrides config location (avoids confusion with another repo).
_configs_dir_env_logged: bool = False


def _log_configs_dir_from_env(resolved: Path) -> None:
    global _configs_dir_env_logged
    if _configs_dir_env_logged:
        return
    _configs_dir_env_logged = True
    raw = os.environ.get("OWLANGS_CONFIG_PATH", "")
    try:
        from logger import unified_logger as _logger
        from logger.logger import LogModule as _LM

        _logger.info(
            _LM.CONFIG,
            f"[CONFIG-PATH] OWLANGS_CONFIG_PATH is set ({raw!r}); using configs directory: {resolved}",
        )
    except Exception:
        pass


def get_system_data_dir() -> str:
    """Get system-appropriate data directory for Owlangs
    
    Returns:
        str: Platform-specific data directory path
    """
    system = platform.system().lower()
    
    if system == "windows":
        # Windows: Check for OWLANGS_CONFIG_PATH first
        env_dir = os.environ.get("OWLANGS_CONFIG_PATH")
        if env_dir:
            # Use env dir even if it doesn't exist yet (will be created on first use)
            return str(Path(env_dir))
        
        # Windows default: C:\ProgramData\Owlangs (standard shared app data)
        program_data = Path(os.environ.get("PROGRAMDATA", r"C:\ProgramData")) / "Owlangs"
        return str(program_data)
    elif system == "darwin":  # macOS
        # macOS: Use ~/Library/Application Support/Owlangs
        return os.path.join(os.path.expanduser("~"), "Library", "Application Support", "Owlangs")
    else:  # Linux and others
        # Linux: Use ~/.local/share/Owlangs (following XDG Base Directory)
        xdg_data_home = os.environ.get("XDG_DATA_HOME")
        if xdg_data_home:
            return os.path.join(xdg_data_home, "Owlangs")
        else:
            return os.path.join(os.path.expanduser("~"), ".local", "share", "Owlangs")


def get_system_config_dir() -> str:
    """Get system-appropriate config directory for Owlangs
    
    Returns:
        str: Platform-specific config directory path
    """
    system = platform.system().lower()
    
    if system == "windows":
        # Windows: Use %APPDATA%\Owlangs\config
        return os.path.join(get_system_data_dir(), "config")
    elif system == "darwin":  # macOS
        # macOS: Use ~/Library/Application Support/Owlangs/config
        return os.path.join(get_system_data_dir(), "config")
    else:  # Linux and others
        # Linux: Use ~/.config/Owlangs (following XDG Base Directory)
        xdg_config_home = os.environ.get("XDG_CONFIG_HOME")
        if xdg_config_home:
            return os.path.join(xdg_config_home, "Owlangs")
        else:
            return os.path.join(os.path.expanduser("~"), ".config", "Owlangs")


def get_system_cache_dir() -> str:
    """Get system-appropriate cache directory for Owlangs
    
    Returns:
        str: Platform-specific cache directory path
    """
    system = platform.system().lower()
    
    if system == "windows":
        # Windows: Use %LOCALAPPDATA%\Owlangs\cache
        return os.path.join(os.environ.get("LOCALAPPDATA", ""), "Owlangs", "cache")
    elif system == "darwin":  # macOS
        # macOS: Use ~/Library/Caches/Owlangs
        return os.path.join(os.path.expanduser("~"), "Library", "Caches", "Owlangs")
    else:  # Linux and others
        # Linux: Use ~/.cache/Owlangs (following XDG Base Directory)
        xdg_cache_home = os.environ.get("XDG_CACHE_HOME")
        if xdg_cache_home:
            return os.path.join(xdg_cache_home, "Owlangs")
        else:
            return os.path.join(os.path.expanduser("~"), ".cache", "Owlangs")


def get_project_root() -> Path:
    """Get project root directory
    
    Returns:
        Path: Project root directory path
    """
    # Try to find project root by looking for configs directory or setup.py/pyproject.toml
    current = Path(__file__).resolve()
    
    # Go up from utils/ to backend/ to project root
    while current.parent != current:
        if (current / "configs").exists() or (current / "pyproject.toml").exists() or (current / "setup.py").exists():
            return current
        current = current.parent
    
    # Fallback: assume we're in backend/utils, so go up 2 levels
    return Path(__file__).resolve().parents[2]


def get_configs_dir() -> Path:
    """Get configs directory path with priority order
    
    Priority:
    1. OWLANGS_CONFIG_PATH/configs (if env var set)
    2. Project root/configs (development - if exists)
    3. C:\\ProgramData\\Owlangs\\configs (Windows deployment - if no project configs)
    4. System config directory (runtime/deployment)
    5. Executable directory/configs (packaged)
    6. Current directory/configs (fallback)
    
    Returns:
        Path: Configs directory path
    """
    # 1. Environment-configured directory (highest priority)
    env_dir = os.environ.get("OWLANGS_CONFIG_PATH")
    if env_dir:
        # Use env dir even if it doesn't exist yet (will be created on first use)
        resolved = Path(env_dir) / "configs"
        _log_configs_dir_from_env(resolved)
        return resolved
    
    # 2. Project root configs directory (development - check first before Windows default)
    # In frozen (packaged) environments, avoid treating the temporary bundle directory
    # as a development project root, so we skip this branch when sys.frozen is set.
    if not getattr(sys, "frozen", False):
        proj_root = get_project_root()
        proj_configs = proj_root / "configs"
        if proj_configs.exists():
            return proj_configs
    
    # 3. Windows default runtime directory (preferred for deployment)
    if os.name == "nt":
        return Path(get_system_data_dir()) / "configs"
    
    # 4. System config directory (runtime/deployment)
    system_config_dir = Path(get_system_config_dir())
    if system_config_dir.exists():
        return system_config_dir
    # When frozen on macOS/Linux, prefer system config dir even if not yet created
    # (avoid using exe_dir so configs live in ~/Library/Application Support/Owlangs/config etc.)
    if getattr(sys, 'frozen', False) and os.name != 'nt':
        return system_config_dir

    # 5. Executable directory (packaged, Windows or when system dir not chosen)
    if getattr(sys, 'frozen', False):
        exe_dir = Path(sys.executable).parent
        exe_configs = exe_dir / "configs"
        if exe_configs.exists():
            return exe_configs
        return exe_dir

    # 6. Current directory (fallback)
    return Path.cwd() / "configs"


def get_config_file_path(filename: str) -> Path:
    """Get configuration file path with priority order
    
    Args:
        filename: Configuration filename (e.g., 'system.json', 'platforms.json')
    
    Returns:
        Path: Configuration file path
    """
    configs_dir = get_configs_dir()
    config_file = configs_dir / filename
    
    # If file exists in configs, return it
    if config_file.exists():
        return config_file
    
    # Otherwise, return the path for creation (will be created in configs)
    return config_file


def get_template_file_path(filename: str) -> Path:
    """Get template file path

    When frozen (production), prefers the bundled template from the current
    build so that schema upgrades always use the latest template version.
    In development mode, prefers the project configs directory.

    Args:
        filename: Template filename (e.g., 'local.json.template')

    Returns:
        Path: Template file path
    """
    # When frozen, bundled template is authoritative (always matches current version)
    if getattr(sys, "frozen", False):
        mei = getattr(sys, "_MEIPASS", None)
        if mei:
            for sub in ("config/templates", "config"):
                bundle_path = Path(mei) / sub / filename
                if bundle_path.exists():
                    return bundle_path

    # Config dir (development, or deployed templates as fallback)
    configs_dir = get_configs_dir()
    template_file = configs_dir / filename
    if template_file.exists():
        return template_file

    # Fallback to project root configs (development)
    proj_root = get_project_root()
    proj_template = proj_root / "configs" / filename
    if proj_template.exists():
        return proj_template

    return configs_dir / filename


def get_owlangs_paths() -> Dict[str, str]:
    """Get all Owlangs-related paths for the current system
    
    Returns:
        Dict[str, str]: Dictionary containing all path types
    """
    data_dir = get_system_data_dir()
    cache_dir = get_system_cache_dir()
    configs_dir = get_configs_dir()
    
    logs_dir = get_logs_dir()
    
    return {
        "data_dir": str(data_dir),
        "config_dir": str(configs_dir),
        "cache_dir": str(cache_dir),
        "logs_dir": str(logs_dir),
        "user_profiles": os.path.join(data_dir, "user_profiles"),
        "prompts": os.path.join(data_dir, "prompts"),
        "glossaries": os.path.join(data_dir, "glossaries"),
        # New config structure
        "system_config": str(get_config_file_path("system.json")),
        "platforms_config": str(get_config_file_path("platforms.json")),
        "secrets_config": str(get_config_file_path("secrets.json")),
        "local_config": str(get_config_file_path("local.json")),
        "app_config": str(get_config_file_path("app_config.json")),
        "local_users": str(get_config_file_path("local_users.json")),
    }


def get_logs_dir() -> Path:
    r"""Get logs directory path with priority order
    
    Priority:
    1. OWLANGS_CONFIG_PATH/logs (if env var set)
    2. C:\\ProgramData\\Owlangs\\logs (Windows deployment - preferred)
    3. Project root/logs (development - if exists)
    4. System data directory/logs (runtime/deployment)
    5. Executable directory/logs (packaged)
    6. Current directory/logs (fallback)
    
    Returns:
        Path: Logs directory path
    """
    # 1. Environment-configured directory (highest priority)
    env_dir = os.environ.get("OWLANGS_CONFIG_PATH")
    if env_dir:
        # Use env dir even if it doesn't exist yet (will be created on first use)
        return Path(env_dir) / "logs"
    
    # 2. Windows default runtime directory (preferred for deployment)
    if os.name == "nt":
        return Path(get_system_data_dir()) / "logs"
    
    # 3. Project root logs directory (development - check if exists)
    proj_root = get_project_root()
    proj_logs = proj_root / "logs"
    if proj_logs.exists():
        return proj_logs
    
    # 4. System data directory (runtime/deployment)
    system_data_dir = Path(get_system_data_dir())
    system_logs = system_data_dir / "logs"
    # On macOS/Linux, prefer system logs dir even if it doesn't exist yet.
    # The logger will create the directory when initializing file handlers.
    if os.name != "nt":
        return system_logs
    if system_logs.exists():
        return system_logs
    
    # 5. Executable directory (packaged)
    if getattr(sys, 'frozen', False):
        exe_dir = Path(sys.executable).parent
        exe_logs = exe_dir / "logs"
        if exe_logs.exists():
            return exe_logs
        # If no logs dir, use exe dir directly
        return exe_dir / "logs"
    
    # 6. Current directory (fallback)
    return Path.cwd() / "logs"


def ensure_directories() -> None:
    """Ensure all Owlangs directories exist"""
    paths = get_owlangs_paths()
    
    # Create main directories
    for key, path in paths.items():
        if key.endswith("_dir") or key in ["user_profiles", "prompts", "glossaries"]:
            os.makedirs(path, exist_ok=True)
    
    # Ensure logs directory exists
    logs_dir = get_logs_dir()
    logs_dir.mkdir(parents=True, exist_ok=True)
