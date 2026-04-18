#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

"""
Test unified_logger module logging functionality.

unified_logger API: method(module, message, **kwargs)
e.g. unified_logger.info(LogModule.SYSTEM, "message")
"""

import sys
import os

# Add backend directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from logger import unified_logger
from logger.logger import LogModule
from logger.module_logging import is_module_logging_enabled
from logger.module_log_manager import module_log_manager

# Test unified_logger with module parameter (first positional arg)
print("=== unified_logger Module Logging Test ===")

print(f"Module logging enabled (unified_logger): {is_module_logging_enabled()}")
print(f"Module status: {module_log_manager.get_module_status()}")

# Test each module's DEBUG level (unified_logger always accepts (module, message))
print("\n=== Testing unified_logger with LogModule ===")
for module in LogModule:
    enabled = module_log_manager.is_enabled(module, "DEBUG")
    print(f"{module.value}: DEBUG enabled = {enabled}")

# Test unified_logger: API is (module, message)
print("\n=== Testing unified_logger.debug(module, message) ===")
unified_logger.debug(LogModule.SYSTEM, "Test SYS debug log")
unified_logger.debug(LogModule.EXTRACT, "Test EXTRACT debug log")
unified_logger.debug(LogModule.TRANS, "Test TRANS debug log")
unified_logger.debug(LogModule.DETECT, "Test DETECT debug log")

print("\n=== Testing unified_logger.info(module, message) ===")
unified_logger.info(LogModule.SYSTEM, "Test SYS info log")
unified_logger.info(LogModule.EXTRACT, "Test EXTRACT info log")

print("\n=== Test Completed ===")
