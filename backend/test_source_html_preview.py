# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

"""Regression: source-html preview must not deepcopy task_state (may hold asyncio.Task)."""

from __future__ import annotations

import ast
import unittest
from pathlib import Path


class TestSourceHtmlPreview(unittest.TestCase):
    def test_source_html_avoids_deepcopy_on_task_state(self) -> None:
        backend_root = Path(__file__).resolve().parent
        path = backend_root / "app" / "services" / "download" / "download_service.py"
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if not isinstance(node, ast.FunctionDef):
                continue
            if node.name != "_source_html_file_response_from_segments":
                continue
            fn_source = ast.get_source_segment(source, node) or ""
            self.assertNotIn(
                "deepcopy(task_state",
                fn_source,
                msg="source-html must shallow-copy export keys, not deepcopy task_state",
            )
            self.assertIn(
                "export_keys",
                fn_source,
                msg="source-html should build temp_state from an export key allowlist",
            )
            return
        self.fail("_source_html_file_response_from_segments not found")


if __name__ == "__main__":
    unittest.main()
