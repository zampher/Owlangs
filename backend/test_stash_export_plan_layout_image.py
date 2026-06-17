# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

"""Regression: immersive layout-image persist supports primary_only export scope."""

import unittest
from pathlib import Path


class TestStashExportPlanLayoutImage(unittest.TestCase):
    def test_download_service_defines_primary_only_scope(self) -> None:
        backend_root = Path(__file__).resolve().parent
        path = backend_root / "app" / "services" / "download" / "download_service.py"
        text = path.read_text(encoding="utf-8")
        self.assertIn('EXPORT_SCOPE_PRIMARY_ONLY = "primary_only"', text)
        self.assertIn("export_scope: str = EXPORT_SCOPE_FULL", text)
        self.assertIn("_filter_stash_export_plan_for_scope", text)
        self.assertIn(
            'if export_scope != EXPORT_SCOPE_PRIMARY_ONLY:\n        return plan',
            text,
        )
        self.assertIn('if execution_mode == "queued":\n        return plan', text)

    def test_persist_route_accepts_export_scope_query(self) -> None:
        backend_root = Path(__file__).resolve().parent
        path = backend_root / "app" / "routes" / "service" / "app_routes_translation.py"
        text = path.read_text(encoding="utf-8")
        self.assertIn("export_scope: str = Query", text)
        self.assertIn("export_scope=export_scope", text)


if __name__ == "__main__":
    unittest.main()
