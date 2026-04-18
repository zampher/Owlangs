# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

"""
Test script to verify model_manager logging with SPACY module
"""

import sys
import os

# Add backend to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Ensure module_logging is enabled BEFORE importing model_manager
from logger.module_logging import is_module_logging_enabled, enable_module_logging

if not is_module_logging_enabled():
    print("Enabling module_logging...")
    try:
        from config.config_loader import get_unified_config
        config = get_unified_config()
        if getattr(config.system.logging, 'enable_module_logging', False):
            enable_module_logging()
            print(f"Module logging enabled: {is_module_logging_enabled()}")
    except Exception as e:
        print(f"Failed to enable module_logging: {e}")

# Now import model_manager (after module_logging is enabled)
from anonymize.model_manager import PresidioModelManager

print("=" * 60)
print("Testing model_manager logging with SPACY module")
print("=" * 60)

# Test print_model_status
print("\nCalling PresidioModelManager.print_model_status()...")
print("-" * 60)
PresidioModelManager.print_model_status()
print("-" * 60)

print("\n" + "=" * 60)
print("Test completed. Check the log output above.")
print("Expected: Logs should show [SPACY] for SPACY module logs")
print("=" * 60)
