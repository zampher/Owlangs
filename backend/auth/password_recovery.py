# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

import json
import logging
from pathlib import Path
from typing import Optional

from logger.logger import LogModule
from backend.logger import unified_logger as logger

# Default password after recovery (documented in PASSWORD_RECOVERY_PROCESS.md)
RECOVERY_PASSWORD = "Changeme"


def reset_admin_password_if_recovery_enabled() -> bool:
    """
    Reset default admin password to RECOVERY_PASSWORD if password recovery is enabled.
    Uses the same user file and default_username as auth so login works after reset.
    """
    try:
        from backend.config.local_config import LocalConfig
        local_config = LocalConfig.load_from_file()
        if not local_config.security.password_recovery:
            logger.debug(LogModule.AUTH, "Password recovery is disabled")
            return False

        from .config import AuthConfig
        from .unified_user_store import get_unified_user_store
        config = AuthConfig.get_config()
        default_username = config.default_username
        store = get_unified_user_store()

        if not store.file_path.exists():
            logger.error(LogModule.AUTH, f"Unified user file not found: {store.file_path}")
            return False

        data = store._load()
        if default_username not in data.get("users", {}):
            logger.error(LogModule.AUTH, f"Default admin user not found: {default_username}")
            return False

        from .password_manager import password_manager
        new_hash = password_manager.hash_password(RECOVERY_PASSWORD, skip_validation=True)
        data["users"][default_username]["password_hash"] = new_hash

        if not store._save(data):
            return False

        store._cache = None  # Force next login to read new hash from file
        logger.info(LogModule.AUTH, f"Admin password reset successfully to: {RECOVERY_PASSWORD}")

        local_config.security.password_recovery = False
        local_config.save_to_file()
        logger.info(LogModule.AUTH, "Password recovery disabled after successful reset")
        return True

    except Exception as e:
        logger.error(LogModule.AUTH, f"Failed to reset admin password: {e}")
        return False


def enable_password_recovery() -> bool:
    """
    Enable password recovery in configuration.
    
    Returns:
        bool: True if enabled successfully, False otherwise
    """
    try:
        from backend.config.local_config import LocalConfig
        local_config = LocalConfig.load_from_file()
        local_config.security.password_recovery = True
        local_config.save_to_file()
        logger.info(LogModule.AUTH, "Password recovery enabled in configuration")
        return True
    except Exception as e:
        logger.error(LogModule.AUTH, f"Failed to enable password recovery: {e}")
        return False


def disable_password_recovery() -> bool:
    """
    Disable password recovery in configuration.
    
    Returns:
        bool: True if disabled successfully, False otherwise
    """
    try:
        from backend.config.local_config import LocalConfig
        local_config = LocalConfig.load_from_file()
        local_config.security.password_recovery = False
        local_config.save_to_file()
        logger.info(LogModule.AUTH, "Password recovery disabled in configuration")
        return True
    except Exception as e:
        logger.error(LogModule.AUTH, f"Failed to disable password recovery: {e}")
        return False
