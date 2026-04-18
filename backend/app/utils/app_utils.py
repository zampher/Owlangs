# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

"""
Application utility functions for Owlangs.

This module contains utilities for application startup and configuration.
"""

import os
import uvicorn
from pathlib import Path

from logger import unified_logger as logger
from logger.logger import LogModule, get_uvicorn_log_config
from app.utils.port import find_free_port


def run_app(port: int | None = None):
    """
    Run the Owlangs application.
    
    Args:
        port: Optional port number to run on. If None, will find a free port.
    """
    # Automatically create secrets.json file on first deployment
    # Configuration file priority:
    # Windows/Linux override:
    # 0) OWLANGS_CONFIG_PATH env dir if set (Windows default: C:\\Users\\Public\\Owlangs)
    # Linux:
    # 1) /etc/Owlangs/secrets.json (system configuration)
    # Common:
    # 2) secrets.json in executable directory (packaged configuration)
    # 3) secrets.json in current directory (development environment)

    # 0) Environment-configured directory
    env_dir = os.environ.get("OWLANGS_CONFIG_PATH")
    # Windows default runtime configuration directory
    if not env_dir and os.name == "nt":
        env_dir = r"C:\\Users\\Public\\Owlangs"
    secrets_path = None
    if env_dir:
        env_secrets = os.path.join(env_dir, "secrets.json")
        if os.path.exists(env_secrets):
            secrets_path = env_secrets
            logger.debug(LogModule.CONFIG, f"Using env secrets config: {secrets_path}")

    system_secrets_path = "/etc/Owlangs/secrets.json"
    system_dir_exists = os.path.exists("/etc/Owlangs")

    # Determine configuration file path
    if secrets_path is None and system_dir_exists and os.path.exists(system_secrets_path):
        secrets_path = system_secrets_path
        # Using system secrets config
    if secrets_path is None:
        # Try to load configuration file from executable program directory
        import sys
        if getattr(sys, 'frozen', False):
            # PyInstaller packaged environment
            exe_dir = os.path.dirname(sys.executable)
            exe_secrets_path = os.path.join(exe_dir, "secrets.json")
            if os.path.exists(exe_secrets_path):
                secrets_path = exe_secrets_path
                # Using executable secrets config

    # Try to load configuration file from current directory (development environment)
    if secrets_path is None:
        current_secrets_path = "secrets.json"
        if os.path.exists(current_secrets_path):
            secrets_path = current_secrets_path
            # Using current directory secrets config

    # If no configuration file is found, create a default one
    if secrets_path is None:
        # No configuration file found, creating default secrets.json
        try:
            # Create default configuration
            default_config = {
                "api_keys": {
                    "openai": "",
                    "anthropic": "",
                    "google": "",
                    "azure": "",
                    "mineru": ""
                },
                "default_models": {
                    "openai": "gpt-4o",
                    "anthropic": "claude-3-5-sonnet-20241022",
                    "google": "gemini-1.5-pro",
                    "azure": "gpt-4o"
                }
            }
            
            # Determine where to create the config file
            if env_dir:
                os.makedirs(env_dir, exist_ok=True)
                config_path = os.path.join(env_dir, "secrets.json")
            else:
                config_path = "secrets.json"
            
            import json
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(default_config, f, indent=2, ensure_ascii=False)
            
            # Created default configuration file
            # Please edit the configuration file to add your API keys
            
        except Exception as e:
            pass  # Failed to create default configuration file

    # Determine port
    if port is None:
        port = find_free_port(8800)
    
    # Starting Owlangs server
    # Access the application at: http://localhost:{port}
    
    # Start the server，配置日志格式确保所有日志都包含时间戳
    uvicorn.run(
        "app.app_main:app",
        host="0.0.0.0",
        port=port,
        reload=False,
        log_level="info",
        log_config=get_uvicorn_log_config()
    )
