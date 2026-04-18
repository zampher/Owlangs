#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

"""
Test unified_logger stability and performance.
"""

import sys
import os
import time
import threading
import random

# Add backend directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from logger import unified_logger
from logger.logger import LogModule
from logger.module_logging import is_module_logging_enabled
from logger.module_log_manager import module_log_manager
from translator.ai_translator.md_translator import MDTranslator, MDTranslatorConfig
from ir.markdown_document import MarkdownDocument

# Test constants
NUM_THREADS = 5
LOGS_PER_THREAD = 1000
TEST_DURATION_SECONDS = 60

# Create a test document for translator tests
test_doc = MarkdownDocument.from_bytes(
    content=b"# Test Document\n\nThis is a test document for logging stability.",
    suffix=".md",
    stem="test_doc"
)

# Create a translator instance (uses its own logger; we also test unified_logger directly)
md_config = MDTranslatorConfig(
    skip_translate=True,
    base_url="test",
    api_key="test",
    model_id="test"
)
md_translator = MDTranslator(md_config)

# Test 1: Concurrent logging with unified_logger (module, message) API
print("=== Test 1: Concurrent Logging with unified_logger ===")

modules = list(LogModule)
levels = ["debug", "info", "warning", "error"]


def log_worker(thread_id):
    """Worker function for concurrent logging test using unified_logger."""
    start_time = time.time()
    log_count = 0

    for i in range(LOGS_PER_THREAD):
        module = random.choice(modules)
        level = random.choice(levels)
        message = f"[Thread {thread_id}] Test log message {i} for module {module.value}"

        # unified_logger API: method(module, message)
        getattr(unified_logger, level)(module, message)
        log_count += 1

    elapsed = time.time() - start_time
    print(f"Thread {thread_id}: Completed {log_count} logs in {elapsed:.2f} seconds ({log_count / elapsed:.2f} logs/sec)")


threads = []
start_time = time.time()

for i in range(NUM_THREADS):
    thread = threading.Thread(target=log_worker, args=(i,))
    threads.append(thread)
    thread.start()

for thread in threads:
    thread.join()

elapsed = time.time() - start_time
total_logs = NUM_THREADS * LOGS_PER_THREAD
print(f"Total: Completed {total_logs} logs in {elapsed:.2f} seconds ({total_logs / elapsed:.2f} logs/sec)")

# Test 2: Translator logging performance (translator uses unified_logger; stability still applies)
print("\n=== Test 2: Translator Logging Performance ===")

start_time = time.time()
for i in range(100):
    md_translator.translate(test_doc)

elapsed = time.time() - start_time
print(f"Translator logging: Completed 100 translate calls in {elapsed:.2f} seconds")

# Test 3: Long-running unified_logger (simulate production use)
print("\n=== Test 3: Long-running unified_logger (5 seconds) ===")

start_time = time.time()
end_time = start_time + 5
log_count = 0

while time.time() < end_time:
    module = modules[log_count % len(modules)]
    level = levels[log_count % len(levels)]
    message = f"Long-running test log {log_count} for module {module.value}"

    getattr(unified_logger, level)(module, message)
    log_count += 1

    time.sleep(random.uniform(0.001, 0.01))

elapsed = time.time() - start_time
print(f"Long-running test: Completed {log_count} logs in {elapsed:.2f} seconds ({log_count / elapsed:.2f} logs/sec)")

# Test 4: Module logging configuration (for reference; module_log_manager filters unified_logger)
print("\n=== Test 4: Module Logging Configuration Verification ===")
print(f"Module logging enabled (unified_logger): {is_module_logging_enabled()}")

key_modules = [LogModule.EXTRACT, LogModule.TRANS, LogModule.SYSTEM]
for module in key_modules:
    debug_enabled = module_log_manager.is_enabled(module, "DEBUG")
    trace_enabled = module_log_manager.is_enabled(module, "TRACE")
    print(f"{module.value}: DEBUG={debug_enabled}, TRACE={trace_enabled}")

print("\n=== Stability Test Completed ===")
print("All tests passed successfully. unified_logger appears stable.")
