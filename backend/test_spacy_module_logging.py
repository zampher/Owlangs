# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

"""
Test script to verify unified_logger works correctly with SPACY module.

unified_logger API: method(module, message) e.g. unified_logger.info(LogModule.SPACY, "msg")
"""

import sys
import os

# Add backend to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from logger import unified_logger
from logger.logger import LogModule
from logger.module_logging import is_module_logging_enabled, enable_module_logging


def test_spacy_unified_logger():
    """Test unified_logger with SPACY and SYS modules."""

    print("=" * 60)
    print("Testing unified_logger with SPACY Module")
    print("=" * 60)

    print(f"\n1. Module logging enabled: {is_module_logging_enabled()}")

    if not is_module_logging_enabled():
        print("   Attempting to enable module_logging (affects unified_logger)...")
        try:
            from config.config_loader import get_unified_config
            config = get_unified_config()
            if getattr(config.system.logging, "enable_module_logging", False):
                enable_module_logging()
                print(f"   Module logging enabled: {is_module_logging_enabled()}")
            else:
                print("   enable_module_logging is False in config")
        except Exception as e:
            print(f"   Failed to enable module_logging: {e}")

    # unified_logger API: (module, message)
    print(f"\n2. unified_logger signature: method(module, message)")
    print("   Example: unified_logger.info(LogModule.SPACY, 'message')")

    print(f"\n3. Testing unified_logger with SPACY module:")
    unified_logger.info(LogModule.SPACY, "Test INFO message with SPACY module")
    unified_logger.debug(LogModule.SPACY, "Test DEBUG message with SPACY module")

    print(f"\n4. Testing unified_logger with SYS module (control):")
    unified_logger.info(LogModule.SYSTEM, "Test INFO message with SYSTEM module")
    unified_logger.debug(LogModule.SYSTEM, "Test DEBUG message with SYSTEM module")

    print("\n" + "=" * 60)
    print("Test completed. Check the log output above.")
    print("Expected: [SPACY] or [SYSTEM] in log lines per module.")
    print("=" * 60)


if __name__ == "__main__":
    test_spacy_unified_logger()
