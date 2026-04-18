# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

import os
import json
from dataclasses import dataclass
from typing import Optional
from pathlib import Path

from logger import unified_logger as logger
from logger.logger import LogModule

_AUTH_CONFIG_SINGLETON: Optional["AuthConfig"] = None

# Default session max age (in seconds) for authentication sessions.
# Keep this value in ONE place and reuse it for both the dataclass default
# and the from_env fallback, so behavior is consistent across code paths.
DEFAULT_SESSION_MAX_AGE_SECONDS: int = 3600 * 24 * 3  # 3 days


def _resolve_auth_config_path(config_file: str = "local.json") -> Path:
    """Resolve absolute path for local.json with deployment-aware priority.
    
    Uses unified config path resolution from utils.path_utils.
    """
    from utils.path_utils import get_config_file_path
    return get_config_file_path(config_file)


@dataclass
class AuthConfig:
    """Authentication configuration class"""
    
    # LDAP configuration
    ldap_enabled: bool = False
    ldap_protocol: str = "ldap"  # "ldap" or "ldaps"
    ldap_host: str = "dc.example.com"
    ldap_port: int = 389
    ldap_bind_dn_template: str = "EXAMPLE\\{username}"
    ldap_base_dn: str = "OU=Users,DC=example,DC=com"
    ldap_user_filter: str = "(sAMAccountName={username})"
    ldap_tls_cacertfile: Optional[str] = None
    ldap_tls_verify: bool = True  # Whether to verify TLS certificate
    
    # LDAP group configuration
    ldap_admin_group_enabled: bool = False  # Whether to enable admin group query
    ldap_glossary_group_enabled: bool = False   # Whether to enable glossary group query (new name)
    ldap_admin_group: str = "Owlangs-Admins"  # Admin group name
    ldap_glossary_group: str = "Owlangs-Glossary"    # Glossary group name (new name)
    ldap_group_base_dn: str = "OU=Groups,DC=example,DC=com"  # Group search base DN
    
    # Default user configuration (used when LDAP is disabled)
    default_username: str = "admin"
    
    # Session configuration
    session_secret_key: str = "your-secret-key-change-in-production"
    session_cookie_name: str = "owlangs_session"
    session_max_age: int = DEFAULT_SESSION_MAX_AGE_SECONDS
    
    # Redis configuration
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_db: int = 0
    redis_password: Optional[str] = None
    
    # Security configuration
    max_login_attempts: int = 5
    login_attempt_window: int = 300  # 5 minutes
    rate_limit_window: int = 300  # 5 minutes
    
    # Message configuration
    login_banner: str = "Welcome to document translation system."
    usage_message: str = "Please drop your file and click Translate."
    
    @classmethod
    def from_env(cls) -> "AuthConfig":
        """Create configuration from environment variables"""
        return cls(
            ldap_enabled=os.getenv("LDAP_ENABLED", "false").lower() == "true",
            ldap_protocol=os.getenv("LDAP_PROTOCOL", "ldap"),
            ldap_host=os.getenv("LDAP_HOST", "dc.example.com"),
            ldap_port=int(os.getenv("LDAP_PORT", "389")),
            ldap_bind_dn_template=os.getenv("LDAP_BIND_DN_TEMPLATE", "EXAMPLE\\{username}"),
            ldap_base_dn=os.getenv("LDAP_BASE_DN", "OU=Users,DC=example,DC=com"),
            ldap_user_filter=os.getenv("LDAP_USER_FILTER", "(sAMAccountName={username})"),
            ldap_tls_cacertfile=os.getenv("LDAP_TLS_CACERTFILE"),
            ldap_tls_verify=os.getenv("LDAP_TLS_VERIFY", "true").lower() == "true",
            ldap_admin_group_enabled=os.getenv("LDAP_ADMIN_GROUP_ENABLED", "false").lower() == "true",
            # Only support new environment variable names
            ldap_glossary_group_enabled=os.getenv("LDAP_GLOSSARY_GROUP_ENABLED", "false").lower() == "true",
            ldap_admin_group=os.getenv("LDAP_ADMIN_GROUP", "Owlangs-Admins"),
            ldap_glossary_group=os.getenv("LDAP_GLOSSARY_GROUP", "Owlangs-Users"),
            ldap_group_base_dn=os.getenv("LDAP_GROUP_BASE_DN", "OU=Groups,DC=example,DC=com"),
            default_username=os.getenv("DEFAULT_USERNAME", "admin"),
            session_secret_key=os.getenv("SESSION_SECRET_KEY", "your-secret-key-change-in-production"),
            session_cookie_name=os.getenv("SESSION_COOKIE_NAME", "owlangs_session"),
            session_max_age=int(
                os.getenv("SESSION_MAX_AGE", str(DEFAULT_SESSION_MAX_AGE_SECONDS))
            ),  # 3 days by default, can be overridden via env
            redis_host=os.getenv("REDIS_HOST", "localhost"),
            redis_port=int(os.getenv("REDIS_PORT", "6379")),
            redis_db=int(os.getenv("REDIS_DB", "0")),
            redis_password=os.getenv("REDIS_PASSWORD"),
            max_login_attempts=int(os.getenv("MAX_LOGIN_ATTEMPTS", "5")),
            login_attempt_window=int(os.getenv("LOGIN_ATTEMPT_WINDOW", "300")),
            rate_limit_window=int(os.getenv("RATE_LIMIT_WINDOW", "300")),
            login_banner=os.getenv("LOGIN_BANNER", "Welcome to document translation system."),
            usage_message=os.getenv("USAGE_MESSAGE", "Please drop your file and click Translate."),
        )
    
    def get_ldap_uri(self) -> str:
        """Get complete LDAP URI"""
        return f"{self.ldap_protocol}://{self.ldap_host}:{self.ldap_port}"
    
    @classmethod
    def load_from_file(cls, config_file: str = "local.json") -> "AuthConfig":
        """Load configuration from grouped local.json.
        Uses unified config path resolution.
        """
        from utils.path_utils import get_config_file_path, get_template_file_path
        
        # Resolve config path
        config_path = _resolve_auth_config_path(config_file)

        logger.debug(LogModule.AUTH, f"[AuthConfig] Attempting to read config from: {config_path}")
        if not config_path.exists():
            # Auto-create from template if available
            import shutil
            template_path = get_template_file_path(f"{config_file}.template")
            
            if template_path.exists():
                try:
                    config_path.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(template_path, config_path)
                    try:
                        os.chmod(config_path, 0o640)
                    except Exception:
                        pass
                    logger.info(LogModule.CONFIG, f"[AuthConfig] Created {config_path} from template {template_path}")
                except Exception as e:
                    logger.warning(LogModule.CONFIG, f"[AuthConfig] Failed to create config from template: {e}")

        # Load configuration from file or use defaults
        if config_path.exists():
            try:
                with open(config_path, 'r', encoding='utf-8-sig') as f:
                    grouped = json.load(f)
                logger.debug(LogModule.AUTH, f"[AuthConfig] Loaded grouped config from file: {config_path}")
                return cls._from_grouped_dict(grouped)
            except Exception as e:
                logger.error(LogModule.CONFIG, f"[AuthConfig] Failed to load config file: {e}, using default config")
        
        logger.info(LogModule.CONFIG, f"[AuthConfig] Config file {config_path} does not exist, using default config")
        return cls.from_env()

    @classmethod
    def _from_grouped_dict(cls, data: dict) -> "AuthConfig":
        """Create AuthConfig from grouped local.json dictionary."""
        ldap = data.get("ldap", {})
        tls = ldap.get("tls", {})
        groups = ldap.get("groups", {})
        default_user = data.get("default_user", {})
        session = data.get("session", {})
        redis = data.get("redis", {})
        security = data.get("security", {})
        messages = data.get("messages", {})

        return cls(
            ldap_enabled=ldap.get("enabled", False),
            ldap_protocol=ldap.get("protocol", "ldap"),
            ldap_host=ldap.get("host", "dc.example.com"),
            ldap_port=int(ldap.get("port", 389)),
            ldap_bind_dn_template=ldap.get("bind_dn_template", "EXAMPLE\\{username}"),
            ldap_base_dn=ldap.get("base_dn", "OU=Users,DC=example,DC=com"),
            ldap_user_filter=ldap.get("user_filter", "(sAMAccountName={username})"),
            ldap_tls_cacertfile=tls.get("cacertfile"),
            ldap_tls_verify=bool(tls.get("verify", True)),
            ldap_admin_group_enabled=bool(groups.get("admin_enabled", False)),
            ldap_glossary_group_enabled=bool(groups.get("glossary_enabled", False)),
            ldap_admin_group=groups.get("admin_group", "Owlangs-Admins"),
            ldap_glossary_group=groups.get("glossary_group", "Owlangs-Glossary"),
            ldap_group_base_dn=groups.get("group_base_dn", "OU=Groups,DC=example,DC=com"),
            default_username=default_user.get("username", "admin"),
            session_secret_key=session.get("secret_key", "your-secret-key-change-in-production"),
            session_cookie_name=session.get("cookie_name", "owlangs_session"),
            session_max_age=int(session.get("max_age", 604800)),
            redis_host=redis.get("host", "localhost"),
            redis_port=int(redis.get("port", 6379)),
            redis_db=int(redis.get("db", 0)),
            redis_password=redis.get("password"),
            max_login_attempts=int(security.get("max_login_attempts", 5)),
            login_attempt_window=int(security.get("login_attempt_window", 300)),
            rate_limit_window=int(security.get("rate_limit_window", 300)),
            login_banner=messages.get("login_banner", "Welcome to document translation system."),
            usage_message=messages.get("usage_message", "Please drop your file and click Translate."),
        )

    def to_grouped_dict(self) -> dict:
        """Serialize AuthConfig to grouped dictionary for local.json."""
        return {
            "ldap": {
                "enabled": self.ldap_enabled,
                "protocol": self.ldap_protocol,
                "host": self.ldap_host,
                "port": self.ldap_port,
                "bind_dn_template": self.ldap_bind_dn_template,
                "base_dn": self.ldap_base_dn,
                "user_filter": self.ldap_user_filter,
                "tls": {
                    "cacertfile": self.ldap_tls_cacertfile,
                    "verify": self.ldap_tls_verify,
                },
                "groups": {
                    "admin_enabled": self.ldap_admin_group_enabled,
                    "glossary_enabled": self.ldap_glossary_group_enabled,
                    "admin_group": self.ldap_admin_group,
                    "glossary_group": self.ldap_glossary_group,
                    "group_base_dn": self.ldap_group_base_dn,
                },
            },
            "default_user": {
                "username": self.default_username,
            },
            "session": {
                "secret_key": self.session_secret_key,
                "cookie_name": self.session_cookie_name,
                "max_age": self.session_max_age,
            },
            "redis": {
                "host": self.redis_host,
                "port": self.redis_port,
                "db": self.redis_db,
                "password": self.redis_password,
            },
            "security": {
                "max_login_attempts": self.max_login_attempts,
                "login_attempt_window": self.login_attempt_window,
                "rate_limit_window": self.rate_limit_window,
            },
            "messages": {
                "login_banner": self.login_banner,
                "usage_message": self.usage_message,
            },
        }
    
    
    def save_to_file(self, config_file: str = "local.json") -> bool:
        """Save grouped configuration to local.json (without secrets).
        
        Uses unified config path resolution.
        """
        from utils.path_utils import get_config_file_path
        
        grouped = self.to_grouped_dict()
        grouped.get("session", {}).pop("secret_key", None)
        grouped.get("redis", {}).pop("password", None)

        # Use unified config path resolution
        try:
            config_path = get_config_file_path(config_file)
        except Exception:
            config_path = _resolve_auth_config_path(config_file)

        try:
            config_path.parent.mkdir(parents=True, exist_ok=True)
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(grouped, f, indent=2, ensure_ascii=False)
            # Set conservative permissions
            try:
                os.chmod(config_path, 0o640)
            except Exception:
                pass
            logger.info(LogModule.CONFIG, f"[AuthConfig] Grouped config saved to {config_path}")
            return True
        except Exception as e:
            logger.error(LogModule.CONFIG, f"[AuthConfig] Failed to save grouped config to {config_path}: {e}")
            return False
    
    def update_from_dict(self, config_data: dict) -> None:
        """Update configuration from dictionary"""
        for key, value in config_data.items():
            if hasattr(self, key):
                # Special handling for boolean values
                if key == "ldap_enabled" and isinstance(value, str):
                    value = value.lower() in ("true", "1", "yes", "on")
                # Special handling for integers
                elif key in ["session_max_age", "max_login_attempts", "login_attempt_window", "rate_limit_window"]:
                    value = int(value)
                # Special handling for empty strings
                elif key == "ldap_tls_cacertfile" and value == "":
                    value = None
                
                setattr(self, key, value)
                logger.info(LogModule.CONFIG, f"Updated configuration {key} = {value}")
    
    @classmethod
    def get_config(cls, config_file: str = "local.json") -> "AuthConfig":
        """Get configuration (prioritize file, then environment variables)"""
        # First try to load from file
        config = cls.load_from_file(config_file)
        
        # If configuration in file is default value, check if environment variables have overrides
        env_config = cls.from_env()
        
        # Merge strategy: only override file values when corresponding environment variables are explicitly set
        # Build field to environment variable name mapping (including compatibility with old names)
        field_env_map = {
            'ldap_enabled': ['LDAP_ENABLED'],
            'ldap_protocol': ['LDAP_PROTOCOL'],
            'ldap_host': ['LDAP_HOST'],
            'ldap_port': ['LDAP_PORT'],
            'ldap_bind_dn_template': ['LDAP_BIND_DN_TEMPLATE'],
            'ldap_base_dn': ['LDAP_BASE_DN'],
            'ldap_user_filter': ['LDAP_USER_FILTER'],
            'ldap_tls_cacertfile': ['LDAP_TLS_CACERTFILE'],
            'ldap_tls_verify': ['LDAP_TLS_VERIFY'],
            'ldap_admin_group_enabled': ['LDAP_ADMIN_GROUP_ENABLED'],
            'ldap_admin_group': ['LDAP_ADMIN_GROUP'],
            # Only support new environment variable names
            'ldap_glossary_group_enabled': ['LDAP_GLOSSARY_GROUP_ENABLED'],
            'ldap_glossary_group': ['LDAP_GLOSSARY_GROUP'],
            'ldap_group_base_dn': ['LDAP_GROUP_BASE_DN'],
            'default_username': ['DEFAULT_USERNAME'],
            'session_secret_key': ['SESSION_SECRET_KEY'],
            'session_cookie_name': ['SESSION_COOKIE_NAME'],
            'session_max_age': ['SESSION_MAX_AGE'],
            'redis_host': ['REDIS_HOST'],
            'redis_port': ['REDIS_PORT'],
            'redis_db': ['REDIS_DB'],
            'redis_password': ['REDIS_PASSWORD'],
            'max_login_attempts': ['MAX_LOGIN_ATTEMPTS'],
            'login_attempt_window': ['LOGIN_ATTEMPT_WINDOW'],
            'rate_limit_window': ['RATE_LIMIT_WINDOW']
        }
        
        for field_name, env_vars in field_env_map.items():
            try:
                if any(os.getenv(var) is not None for var in env_vars):
                    env_value = getattr(env_config, field_name)
                    setattr(config, field_name, env_value)
                    logger.info(LogModule.CONFIG, f"Using environment variable override {field_name} = {env_value}")
            except Exception:
                continue
        
        return config


# Module-level singleton accessor for route single-item save calls
def get_auth_config(config_file: str = "local.json") -> "AuthConfig":
    global _AUTH_CONFIG_SINGLETON
    if _AUTH_CONFIG_SINGLETON is None:
        try:
            _AUTH_CONFIG_SINGLETON = AuthConfig.load_from_file(config_file)
        except Exception as e:
            logger.warning(LogModule.CONFIG, f"[AuthConfig] Failed to initialize authentication configuration singleton, using default values: {e}")
            _AUTH_CONFIG_SINGLETON = AuthConfig.from_env()
    return _AUTH_CONFIG_SINGLETON


def save_auth_config(config_file: str = "local.json") -> bool:
    try:
        global _AUTH_CONFIG_SINGLETON
        # Prefer in-memory singleton (which may have recent updates) to avoid stale writes
        cfg = _AUTH_CONFIG_SINGLETON if _AUTH_CONFIG_SINGLETON is not None else AuthConfig.get_config(config_file)
        result = cfg.save_to_file(config_file)
        logger.info(LogModule.CONFIG, f"[AuthConfig] save_auth_config write result: {result}")
        return result
    except Exception as e:
        logger.error(LogModule.CONFIG, f"[AuthConfig] Failed to save auth config: {e}")
        return False


def reload_auth_config(config_file: str = "local.json") -> "AuthConfig":
    """Force reload authentication configuration from disk and refresh singleton."""
    global _AUTH_CONFIG_SINGLETON
    try:
        _AUTH_CONFIG_SINGLETON = AuthConfig.load_from_file(config_file)
        logger.info(LogModule.CONFIG, "[AuthConfig] Reloaded authentication configuration from disk")
    except Exception as e:
        logger.error(LogModule.CONFIG, f"[AuthConfig] Failed to reload authentication configuration: {e}")
    return _AUTH_CONFIG_SINGLETON
