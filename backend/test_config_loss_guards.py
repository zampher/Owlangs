# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

"""Tests for config-loss guards (secrets / platforms / user profile)."""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


class SecretsWipeGuardTests(unittest.TestCase):
    def test_refuse_save_empty_over_existing_keys(self) -> None:
        from backend.config.secrets_manager import SecretsManager

        with tempfile.TemporaryDirectory() as td:
            secrets_path = Path(td) / "secrets.json"
            secrets_path.write_text(
                json.dumps(
                    {
                        "api_keys": {
                            "deepseek": {"key": "sk-real", "configured": True},
                            "openai": {"key": "sk-other", "configured": True},
                        }
                    }
                ),
                encoding="utf-8",
            )
            mgr = SecretsManager.__new__(SecretsManager)
            mgr.secrets_file = secrets_path
            mgr._secrets_cache = None
            mgr._load_failed = False
            mgr._load_failed_reason = None

            ok = mgr.save_secrets({"api_keys": {}})
            self.assertFalse(ok)
            on_disk = json.loads(secrets_path.read_text(encoding="utf-8"))
            self.assertEqual(on_disk["api_keys"]["deepseek"]["key"], "sk-real")

    def test_skip_empty_platform_key_update(self) -> None:
        from backend.config.secrets_manager import SecretsManager

        with tempfile.TemporaryDirectory() as td:
            secrets_path = Path(td) / "secrets.json"
            secrets_path.write_text(
                json.dumps(
                    {
                        "api_keys": {
                            "deepseek": {"key": "sk-keep", "configured": True},
                        }
                    }
                ),
                encoding="utf-8",
            )
            mgr = SecretsManager.__new__(SecretsManager)
            mgr.secrets_file = secrets_path
            mgr._secrets_cache = None
            mgr._load_failed = False
            mgr._load_failed_reason = None

            # Force requires_api_key=True path
            with patch.object(
                SecretsManager, "_platform_allows_empty_api_key", return_value=False
            ):
                ok = mgr.update_platform_api_key("deepseek", "")
            self.assertTrue(ok)
            on_disk = json.loads(secrets_path.read_text(encoding="utf-8"))
            self.assertEqual(on_disk["api_keys"]["deepseek"]["key"], "sk-keep")

    def test_allow_empty_when_platform_optional(self) -> None:
        from backend.config.secrets_manager import SecretsManager

        with tempfile.TemporaryDirectory() as td:
            secrets_path = Path(td) / "secrets.json"
            secrets_path.write_text(
                json.dumps(
                    {
                        "api_keys": {
                            "ollama": {"key": "old", "configured": True},
                        }
                    }
                ),
                encoding="utf-8",
            )
            mgr = SecretsManager.__new__(SecretsManager)
            mgr.secrets_file = secrets_path
            mgr._secrets_cache = None
            mgr._load_failed = False
            mgr._load_failed_reason = None

            with patch.object(
                SecretsManager, "_platform_allows_empty_api_key", return_value=True
            ):
                ok = mgr.update_platform_api_key("ollama", "")
            self.assertTrue(ok)
            on_disk = json.loads(secrets_path.read_text(encoding="utf-8"))
            self.assertEqual(on_disk["api_keys"]["ollama"]["key"], "")
            self.assertTrue(on_disk["api_keys"]["ollama"]["configured"])

    def test_refuse_save_after_load_failure(self) -> None:
        from backend.config.secrets_manager import SecretsManager

        with tempfile.TemporaryDirectory() as td:
            secrets_path = Path(td) / "secrets.json"
            secrets_path.write_text("{not-json", encoding="utf-8")
            mgr = SecretsManager.__new__(SecretsManager)
            mgr.secrets_file = secrets_path
            mgr._secrets_cache = None
            mgr._load_failed = False
            mgr._load_failed_reason = None

            loaded = mgr.load_secrets()
            self.assertEqual(loaded, {})
            self.assertTrue(mgr._load_failed)
            ok = mgr.save_secrets({"api_keys": {"x": {"key": "y", "configured": True}}})
            self.assertFalse(ok)
            self.assertEqual(secrets_path.read_text(encoding="utf-8"), "{not-json")

    def test_key_check_summary_detects_required_loss(self) -> None:
        from backend.config.secrets_manager import SecretsManager

        mgr = SecretsManager.__new__(SecretsManager)
        mgr.secrets_file = Path("secrets.json")
        disk = {
            "api_keys": {
                "deepseek": {"key": "sk-keep", "configured": True},
                "ollama": {"key": "local", "configured": True},
            },
            "translator_mineru_token": {"key": "mt", "configured": True},
        }
        incoming = {
            "api_keys": {
                "deepseek": {"key": "", "configured": False},
                "ollama": {"key": "", "configured": False},
            },
            "translator_mineru_token": {"key": "mt", "configured": True},
        }
        with patch.object(
            SecretsManager,
            "_platform_allows_empty_api_key",
            side_effect=lambda p: p == "ollama",
        ):
            summary = mgr._build_api_key_save_summary(disk, incoming)
        self.assertEqual(summary["status"], "LOSS")
        self.assertEqual(summary["required_lost"], ["deepseek"])
        self.assertEqual(summary["optional_cleared"], ["ollama"])
        self.assertEqual(summary["mineru"], "kept")

    def test_key_check_summary_ok_when_optional_cleared(self) -> None:
        from backend.config.secrets_manager import SecretsManager

        mgr = SecretsManager.__new__(SecretsManager)
        mgr.secrets_file = Path("secrets.json")
        disk = {
            "api_keys": {
                "deepseek": {"key": "sk-keep", "configured": True},
                "ollama": {"key": "local", "configured": True},
            }
        }
        incoming = {
            "api_keys": {
                "deepseek": {"key": "sk-keep", "configured": True},
                "ollama": {"key": "", "configured": False},
            }
        }
        with patch.object(
            SecretsManager,
            "_platform_allows_empty_api_key",
            side_effect=lambda p: p == "ollama",
        ):
            summary = mgr._build_api_key_save_summary(disk, incoming)
        self.assertEqual(summary["status"], "OK")
        self.assertEqual(summary["required_lost"], [])
        self.assertEqual(summary["optional_cleared"], ["ollama"])


class PlatformsWipeGuardTests(unittest.TestCase):
    def test_refuse_empty_memory_over_disk(self) -> None:
        from backend.config.platforms_config import PlatformsConfig

        with tempfile.TemporaryDirectory() as td:
            target = Path(td) / "platforms.json"
            target.write_text(
                json.dumps(
                    {
                        "default_platform": "deepseek",
                        "platforms": {
                            "deepseek": {"name": "DeepSeek", "url": "https://x", "model": "m"},
                        },
                    }
                ),
                encoding="utf-8",
            )
            cfg = PlatformsConfig()
            cfg.platforms = {}
            with patch(
                "utils.path_utils.get_config_file_path",
                return_value=target,
            ):
                ok = cfg.save_to_file()
            self.assertFalse(ok)
            on_disk = json.loads(target.read_text(encoding="utf-8"))
            self.assertIn("deepseek", on_disk["platforms"])


class UserProfileCreateGuardTests(unittest.TestCase):
    def test_create_default_does_not_overwrite(self) -> None:
        from backend.auth.user_profile import UserProfileManager

        with tempfile.TemporaryDirectory() as td:
            mgr = UserProfileManager(profile_dir=td)
            path = os.path.join(td, "admin_profile.json")
            with open(path, "w", encoding="utf-8") as fh:
                json.dump({"ui_language": "zh", "translator_temperature": 0.7}, fh)

            profile = mgr.create_default_profile("admin")
            on_disk = json.loads(Path(path).read_text(encoding="utf-8"))
            self.assertEqual(on_disk.get("ui_language"), "zh")
            self.assertEqual(on_disk.get("translator_temperature"), 0.7)
            self.assertEqual(profile.ui_language, "zh")


if __name__ == "__main__":
    unittest.main()
