#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

"""
Logging configuration management tool
Used to modify system log levels and other logging-related settings
"""

import sys
import json
import argparse
from pathlib import Path
from backend.config.global_config import get_global_config, save_global_config


def get_log_levels():
    """Get available log levels"""
    return ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]


def show_current_config():
    """Show current logging configuration"""
    config = get_global_config()
    logging_config = config.logging
    
    print("Current logging configuration:")
    print(f"  Level: {logging_config.level}")
    print(f"  Console output: {'Enabled' if logging_config.console_enabled else 'Disabled'}")
    print(f"  File output: {'Enabled' if logging_config.file_enabled else 'Disabled'}")
    print(f"  Max file size: {logging_config.max_file_size_mb} MB")
    print(f"  Backup count: {logging_config.backup_count}")


def set_log_level(level: str):
    """Set log level"""
    if level.upper() not in get_log_levels():
        print(f"Error: Invalid log level '{level}'")
        print(f"Available levels: {', '.join(get_log_levels())}")
        return False
    
    config = get_global_config()
    config.logging.level = level.upper()
    
    if save_global_config():
        # Use i18n for success messages
        from backend.logger.logger import i18n_logger
        i18n_logger.info("backend.logging.config.level_changed", level=level.upper())
        print("💡 Restart service to take effect")
        return True
    else:
        print("❌ Failed to save configuration")
        return False


def toggle_console_output(enabled: bool):
    """Toggle console output"""
    config = get_global_config()
    config.logging.console_enabled = enabled
    
    if save_global_config():
        status = "enabled" if enabled else "disabled"
        print(f"✅ Console output {status}")
        print("💡 Restart service to take effect")
        return True
    else:
        print("❌ Failed to save configuration")
        return False


def toggle_file_output(enabled: bool):
    """Toggle file output"""
    config = get_global_config()
    config.logging.file_enabled = enabled
    
    if save_global_config():
        status = "enabled" if enabled else "disabled"
        print(f"✅ File output {status}")
        print("💡 Restart service to take effect")
        return True
    else:
        print("❌ Failed to save configuration")
        return False


def set_file_size(max_size_mb: int):
    """Set maximum file size"""
    if max_size_mb <= 0:
        print("Error: File size must be greater than 0")
        return False
    
    config = get_global_config()
    config.logging.max_file_size_mb = max_size_mb
    
    if save_global_config():
        print(f"✅ Maximum file size set to: {max_size_mb} MB")
        print("💡 Restart service to take effect")
        return True
    else:
        print("❌ Failed to save configuration")
        return False


def set_backup_count(count: int):
    """Set backup file count"""
    if count < 0:
        print("Error: Backup count cannot be negative")
        return False
    
    config = get_global_config()
    config.logging.backup_count = count
    
    if save_global_config():
        print(f"✅ Backup file count set to: {count}")
        print("💡 Restart service to take effect")
        return True
    else:
        print("❌ Failed to save configuration")
        return False


def main():
    parser = argparse.ArgumentParser(description="Logging configuration management tool")
    parser.add_argument("--show", action="store_true", help="Show current configuration")
    parser.add_argument("--level", choices=get_log_levels(), help="Set log level")
    parser.add_argument("--console", choices=["on", "off"], help="Enable/disable console output")
    parser.add_argument("--file", choices=["on", "off"], help="Enable/disable file output")
    parser.add_argument("--max-size", type=int, help="Set maximum file size (MB)")
    parser.add_argument("--backup-count", type=int, help="Set backup file count")
    
    args = parser.parse_args()
    
    # If no arguments provided, show help
    if len(sys.argv) == 1:
        parser.print_help()
        print("\nExamples:")
        print("  python manage_logging.py --show                    # Show current configuration")
        print("  python manage_logging.py --level DEBUG             # Set to DEBUG level")
        print("  python manage_logging.py --level INFO              # Set to INFO level")
        print("  python manage_logging.py --console off             # Disable console output")
        print("  python manage_logging.py --file on                 # Enable file output")
        print("  python manage_logging.py --max-size 20             # Set max file size to 20MB")
        print("  python manage_logging.py --backup-count 10         # Set backup count to 10")
        return
    
    success = True
    
    if args.show:
        show_current_config()
    
    if args.level:
        success &= set_log_level(args.level)
    
    if args.console:
        success &= toggle_console_output(args.console == "on")
    
    if args.file:
        success &= toggle_file_output(args.file == "on")
    
    if args.max_size is not None:
        success &= set_file_size(args.max_size)
    
    if args.backup_count is not None:
        success &= set_backup_count(args.backup_count)
    
    if not success:
        sys.exit(1)


if __name__ == "__main__":
    main()
