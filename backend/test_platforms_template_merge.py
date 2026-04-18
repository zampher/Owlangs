#!/usr/bin/env python3
"""
Test platforms.json template merge behavior.
"""

import json
import os
import tempfile
import unittest
from pathlib import Path
import sys


class PlatformsTemplateMergeTest(unittest.TestCase):
    def test_platforms_template_merge_adds_new_platform_and_preserves_user_values(self):
        # NOTE: backend logger may keep file handles on Windows; avoid auto-deleting temp dir.
        td = tempfile.mkdtemp()
        try:
            # Ensure repo root is importable (run as a script)
            repo_root = Path(__file__).resolve().parents[1]
            if str(repo_root) not in sys.path:
                sys.path.insert(0, str(repo_root))

            root = Path(td)
            os.environ["OWLANGS_CONFIG_PATH"] = str(root)
            cfg_dir = root / "configs"
            cfg_dir.mkdir(parents=True, exist_ok=True)

            # Disable file logging to avoid Windows file locks in temp directory.
            (cfg_dir / "system.json").write_text(
                json.dumps(
                    {"_schema_version": 1, "logging": {"file_enabled": False, "console_enabled": False}},
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )

            current = {
                "_schema_version": 1,
                "default_platform": "openai",
                "platforms": {
                    "openai": {
                        "name": "OpenAI",
                        "url": "https://api.openai.com/v1/",
                        "model": "gpt-4o",
                        "max_tokens": 128000,
                        "temperature": 0.9,
                    }
                },
            }
            (cfg_dir / "platforms.json").write_text(
                json.dumps(current, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )

            template = {
                "_schema_version": 1,
                "default_platform": "deepseek",
                "platforms": {
                    "openai": {
                        "name": "OpenAI",
                        "url": "https://api.openai.com/v1/",
                        "model": "gpt-4o",
                        "max_tokens": 128000,
                        "temperature": 0.3,
                        "temperature_min": 0.0,
                    },
                    "new_platform": {
                        "name": "New Platform",
                        "url": "http://localhost:1234/v1",
                        "model": "test",
                        "max_tokens": 4096,
                        "temperature": 0.3,
                    },
                },
            }
            (cfg_dir / "platforms.json.template").write_text(
                json.dumps(template, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )

            from backend.config.platforms_config import PlatformsConfig

            cfg = PlatformsConfig.load_from_file("platforms.json")
            self.assertIsNotNone(cfg.get_platform_config("new_platform"))
            self.assertIsNotNone(cfg.get_platform_config("openai"))
            self.assertEqual(cfg.get_platform_config("openai").temperature, 0.9)

            merged = json.loads((cfg_dir / "platforms.json").read_text(encoding="utf-8"))
            self.assertIn("new_platform", merged.get("platforms", {}))
            self.assertEqual(merged["platforms"]["openai"]["temperature"], 0.9)
            self.assertEqual(merged["platforms"]["openai"].get("temperature_min"), 0.0)
        finally:
            # Best-effort cleanup is intentionally skipped to avoid Windows file lock issues.
            pass


if __name__ == "__main__":
    unittest.main()

