# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

import os
import json
from dataclasses import dataclass, asdict, field
from typing import Optional, Dict, Any
from pathlib import Path

from logger import unified_logger as logger
from logger.logger import LogModule

# Module-level cache to avoid reading local.json on every request (e.g. from middleware)
_local_config_cache: Optional["LocalConfig"] = None
_local_config_loading: bool = False  # Flag to prevent concurrent loading


@dataclass
class LDAPConfig:
    """LDAP configuration"""
    enabled: bool = False
    protocol: str = "ldap"
    host: str = "dc.example.com"
    port: int = 389
    bind_dn_template: str = "EXAMPLE\\{username}"
    base_dn: str = "OU=Users,DC=example,DC=com"
    user_filter: str = "(sAMAccountName={username})"
    tls: Dict[str, Any] = field(default_factory=lambda: {
        "cacertfile": None,
        "verify": True
    })
    groups: Dict[str, Any] = field(default_factory=lambda: {
        "admin_enabled": False,
        "glossary_enabled": False,
        "admin_group": "Owlangs-Admins",
        "glossary_group": "Owlangs-Glossary",
        "group_base_dn": "OU=Groups,DC=example,DC=com"
    })


@dataclass
class DefaultUserConfig:
    """Default user configuration"""
    username: str = "admin"


@dataclass
class SessionConfig:
    """Session configuration"""
    cookie_name: str = "owlangs_session"
    max_age: int = 604800
    secret_key: str = "your-secret-key-change-in-production"


@dataclass
class RedisConfig:
    """Redis configuration"""
    enabled: bool = True  # 默认启用Redis
    host: str = "localhost"
    port: int = 6379
    db: int = 0
    password: Optional[str] = None


@dataclass
class SecurityConfig:
    """Security configuration"""
    max_login_attempts: int = 5
    login_attempt_window: int = 300
    rate_limit_window: int = 300
    password_recovery: bool = False


@dataclass
class MessagesConfig:
    """Messages configuration"""
    login_banner: str = "Welcome"
    usage_message: str = "Drop file and translate"


@dataclass
class HTTPSConfig:
    """HTTPS configuration"""
    enabled: bool = False
    cert_file: Optional[str] = None
    key_file: Optional[str] = None
    force_redirect: bool = False


@dataclass
class LocalConfig:
    """Local configuration class, manages system-level settings"""
    
    # LDAP settings
    ldap: LDAPConfig = field(default_factory=LDAPConfig)
    
    # Default user settings
    default_user: DefaultUserConfig = field(default_factory=DefaultUserConfig)
    
    # Session settings
    session: SessionConfig = field(default_factory=SessionConfig)
    
    # Redis settings
    redis: RedisConfig = field(default_factory=RedisConfig)
    
    # Security settings
    security: SecurityConfig = field(default_factory=SecurityConfig)
    
    # Messages settings
    messages: MessagesConfig = field(default_factory=MessagesConfig)
    
    # HTTPS settings
    https: HTTPSConfig = field(default_factory=HTTPSConfig)
    
    @classmethod
    def load_from_file(cls, config_file: str = "local.json") -> "LocalConfig":
        """Load local configuration from JSON file"""
        try:
            from utils.path_utils import get_config_file_path
            
            # Use unified config path function (prioritizes configs directory)
            config_path = get_config_file_path(config_file)
            
            if config_path.exists():
                with open(config_path, 'r', encoding='utf-8-sig') as f:
                    config_data = json.load(f)

                # Merge template structure on upgrade without overwriting user values.
                try:
                    from utils.path_utils import get_template_file_path
                    from backend.utils.template_merge_utils import maybe_merge_json_file_with_template

                    template_path = get_template_file_path(f"{config_file}.template")
                    merged = maybe_merge_json_file_with_template(
                        current_path=config_path,
                        template_path=template_path,
                        write_back=True,
                    )
                    if isinstance(merged, dict) and merged != config_data:
                        logger.info(
                            LogModule.CONFIG,
                            f"Merged existing local.json with template structure: {config_path}",
                        )
                        config_data = merged
                except Exception as merge_err:
                    logger.warning(
                        LogModule.CONFIG,
                        f"Failed to merge local.json with template: {merge_err}",
                    )
                
                # Create configuration object
                config = cls()
                
                # Load LDAP configuration
                if 'ldap' in config_data:
                    config.ldap = LDAPConfig(**config_data['ldap'])
                
                # Load default user configuration
                if 'default_user' in config_data:
                    config.default_user = DefaultUserConfig(**config_data['default_user'])
                
                # Load session configuration
                if 'session' in config_data:
                    config.session = SessionConfig(**config_data['session'])
                
                # Load Redis configuration
                if 'redis' in config_data:
                    config.redis = RedisConfig(**config_data['redis'])
                
                # Load security configuration
                if 'security' in config_data:
                    config.security = SecurityConfig(**config_data['security'])
                
                # Load messages configuration
                if 'messages' in config_data:
                    config.messages = MessagesConfig(**config_data['messages'])
                
                # Load HTTPS configuration
                if 'https' in config_data:
                    config.https = HTTPSConfig(**config_data['https'])
                
                logger.debug(LogModule.CONFIG, f"Loaded local configuration from {config_path}")
                return config
            else:
                # Try to create from template
                from utils.path_utils import get_template_file_path
                template_path = get_template_file_path(f"{config_file}.template")
                if template_path.exists():
                    logger.info(LogModule.CONFIG, f"Local config file not found, creating from template: {template_path}")
                    import shutil
                    config_path.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(template_path, config_path)
                    # Load the newly created file
                    with open(config_path, 'r', encoding='utf-8-sig') as f:
                        config_data = json.load(f)
                        config = cls()
                        # Load all config sections
                        if 'ldap' in config_data:
                            config.ldap = LDAPConfig(**config_data['ldap'])
                        if 'default_user' in config_data:
                            config.default_user = DefaultUserConfig(**config_data['default_user'])
                        if 'session' in config_data:
                            config.session = SessionConfig(**config_data['session'])
                        if 'redis' in config_data:
                            config.redis = RedisConfig(**config_data['redis'])
                        if 'security' in config_data:
                            config.security = SecurityConfig(**config_data['security'])
                        if 'messages' in config_data:
                            config.messages = MessagesConfig(**config_data['messages'])
                        if 'https' in config_data:
                            config.https = HTTPSConfig(**config_data['https'])
                        logger.debug(LogModule.CONFIG, f"Loaded local configuration from template: {config_path}")
                        return config
                logger.warning(LogModule.CONFIG, f"Local configuration file not found at {config_path}, using defaults")
                return cls()
                
        except Exception as e:
            logger.error(LogModule.CONFIG, f"Error loading local configuration: {e}")
            return cls()

    @classmethod
    def get_config(cls, config_file: str = "local.json") -> "LocalConfig":
        """Return cached local config; load from file only on first access or after clear_local_config_cache()."""
        global _local_config_cache, _local_config_loading
        if _local_config_cache is None and not _local_config_loading:
            _local_config_loading = True
            try:
                _local_config_cache = cls.load_from_file(config_file)
            finally:
                _local_config_loading = False
        return _local_config_cache

    @classmethod
    def clear_cache(cls) -> None:
        """Clear cached config so next get_config() will reload from file."""
        global _local_config_cache
        _local_config_cache = None

    def save_to_file(self, config_file: str = "local.json") -> bool:
        """Save local configuration to JSON file"""
        try:
            from utils.path_utils import get_config_file_path
            
            config_dict = {
                'ldap': asdict(self.ldap),
                'default_user': asdict(self.default_user),
                'session': asdict(self.session),
                'redis': asdict(self.redis),
                'security': asdict(self.security),
                'messages': asdict(self.messages),
                'https': asdict(self.https)
            }
            
            # Use unified config path function
            target_path = get_config_file_path(config_file)
            
            # Ensure configs directory exists
            target_path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(target_path, 'w', encoding='utf-8') as f:
                json.dump(config_dict, f, indent=2, ensure_ascii=False)
            
            logger.info(LogModule.CONFIG, f"Saved local configuration to {target_path}")
            # Keep cache in sync: the saved instance is the current config
            global _local_config_cache
            _local_config_cache = self
            return True
            
        except Exception as e:
            logger.error(LogModule.CONFIG, f"Error saving local configuration: {e}")
            return False
    
    def get_config_dict(self) -> Dict[str, Any]:
        """Get configuration dictionary"""
        return {
            'ldap': asdict(self.ldap),
            'default_user': asdict(self.default_user),
            'session': asdict(self.session),
            'redis': asdict(self.redis),
            'security': asdict(self.security),
            'messages': asdict(self.messages),
            'https': asdict(self.https)
        }
    
    def update_from_dict(self, config_data: Dict[str, Any]) -> None:
        """Update configuration from dictionary"""
        try:
            # Update LDAP configuration
            if 'ldap' in config_data:
                for key, value in config_data['ldap'].items():
                    if hasattr(self.ldap, key):
                        setattr(self.ldap, key, value)
            
            # Update default user configuration
            if 'default_user' in config_data:
                for key, value in config_data['default_user'].items():
                    if hasattr(self.default_user, key):
                        setattr(self.default_user, key, value)
            
            # Update session configuration
            if 'session' in config_data:
                for key, value in config_data['session'].items():
                    if hasattr(self.session, key):
                        setattr(self.session, key, value)
            
            # Update Redis configuration
            if 'redis' in config_data:
                for key, value in config_data['redis'].items():
                    if hasattr(self.redis, key):
                        setattr(self.redis, key, value)
            
            # Update security configuration
            if 'security' in config_data:
                for key, value in config_data['security'].items():
                    if hasattr(self.security, key):
                        setattr(self.security, key, value)
            
            # Update messages configuration
            if 'messages' in config_data:
                for key, value in config_data['messages'].items():
                    if hasattr(self.messages, key):
                        setattr(self.messages, key, value)
            
            # Update HTTPS configuration
            if 'https' in config_data:
                for key, value in config_data['https'].items():
                    if hasattr(self.https, key):
                        setattr(self.https, key, value)
                        
        except Exception as e:
            logger.error(LogModule.CONFIG, f"Error updating local configuration: {e}")


def load_config(config_file: str = "local.json") -> LocalConfig:
    """Return cached local config (for redis_manager and other callers). Same as LocalConfig.get_config()."""
    return LocalConfig.get_config(config_file)
