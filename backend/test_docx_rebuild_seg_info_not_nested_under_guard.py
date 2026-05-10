# SPDX-FileCopyrightText: 2026 Zamphersssss
# SPDX-License-Identifier: MPL-2.0

"""
Regression: segment locate + element assignment must run when seg_info is present.

Previously, para_index/element logic was over-indented under `if not seg_info:` after a
continue, so it only parsed as unreachable/dead code under that guard — at runtime the
interpreter still executed `current_element_text = element...` with element unset.
"""

import ast
import unittest
from pathlib import Path


class TestDocxRebuildSegInfoBranch(unittest.TestCase):
    def test_para_index_not_inside_if_not_seg_info(self) -> None:
        root = Path(__file__).resolve().parent
        path = root / "utils" / "document_rebuild" / "docx_rebuild.py"
        self.assertTrue(path.is_file(), msg=f"Missing {path}")
        tree = ast.parse(path.read_text(encoding="utf-8"))
        bad: list[tuple[int, str]] = []

        class V(ast.NodeVisitor):
            def visit_If(self, node: ast.If) -> None:
                test_src = ast.unparse(node.test) if hasattr(ast, "unparse") else ""
                if "not seg_info" in test_src or test_src.strip() == "not seg_info":
                    for n in ast.walk(node):
                        if isinstance(n, ast.Assign):
                            for t in n.targets:
                                if isinstance(t, ast.Name) and t.id == "para_index":
                                    bad.append((n.lineno, "para_index assign under if not seg_info"))
                self.generic_visit(node)

        V().visit(tree)
        self.assertEqual(
            bad,
            [],
            msg=f"para_index must not be nested under if not seg_info: {bad}",
        )


if __name__ == "__main__":
    unittest.main()
