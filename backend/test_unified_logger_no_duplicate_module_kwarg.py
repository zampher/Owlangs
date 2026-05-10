#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Zamphersssss
# SPDX-License-Identifier: MPL-2.0

"""
UnifiedLogger passes **kwargs to _log(); passing module= collides with the
positional module argument and raises TypeError. Doc rebuild trace calls must
not add module=LogModule.* alongside LogModule.RESTOR (first positional).
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from logger import unified_logger as logger
from logger.logger import LogModule


class TestUnifiedLoggerModuleKwarg(unittest.TestCase):
    def test_trace_duplicate_module_kwarg_raises(self):
        with self.assertRaises(TypeError) as ctx:
            logger.trace(LogModule.RESTOR, "msg", module=LogModule.EXPORT)
        self.assertIn("multiple values for argument 'module'", str(ctx.exception))

    def test_trace_two_positionals_ok(self):
        logger.trace(LogModule.RESTOR, "trace_two_positionals_ok")


if __name__ == "__main__":
    unittest.main()
