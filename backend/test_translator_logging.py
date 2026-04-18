#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

"""
Test translator logging and unified_logger usage.

Translator may use an injected logger; we also test unified_logger directly.
"""

import sys
import os

# Add backend directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from logger import unified_logger
from logger.logger import LogModule
from translator.ai_translator.md_translator import MDTranslator, MDTranslatorConfig
from ir.markdown_document import MarkdownDocument

# Test unified_logger directly
print("=== unified_logger and Translator Logging Test ===")

# Create a simple test document
test_doc = MarkdownDocument.from_bytes(
    content=b"# Test Document\n\nThis is a test document for logging.",
    suffix=".md",
    stem="test_doc"
)

# Test MDTranslator (uses its own logger instance)
print("\n=== Testing MDTranslator Logging ===")
md_config = MDTranslatorConfig(
    skip_translate=True,
    base_url="test",
    api_key="test",
    model_id="test"
)
md_translator = MDTranslator(md_config)
md_translator.translate(test_doc)

# Test with a task_id
print("\n=== Testing with Task ID ===")
md_translator._task_id = "test_task_123"
md_translator._get_excluded_segments("test_task_123")

# Test unified_logger explicitly (API: module, message)
print("\n=== Testing unified_logger Directly ===")
unified_logger.info(LogModule.SYSTEM, "Test with unified_logger and SYS module")
unified_logger.info(LogModule.TRANS, "Test with unified_logger and TRANS module")
unified_logger.debug(LogModule.TRANS, "Test debug with unified_logger and TRANS module")

print("\n=== Test Completed ===")
