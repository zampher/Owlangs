#!/usr/bin/env python3
"""
Tests for json template merge behavior (system/ui/local/translation/app_config).
"""

import json
import os
import tempfile
import unittest
from pathlib import Path
import sys


class ConfigTemplateMergeTest(unittest.TestCase):
    def test_system_local_merge_adds_missing_keys_without_overwrite(self):
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

            # system.json: user customized auth.required; template adds new features.show_ads
            (cfg_dir / "system.json").write_text(
                json.dumps(
                    {
                        "_schema_version": 1,
                        "logging": {"file_enabled": False, "console_enabled": False},
                        "auth": {"required": False, "session_timeout": 3600},
                        "features": {"smart_glossary_matching_enabled": True},
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )
            (cfg_dir / "system.json.template").write_text(
                json.dumps(
                    {
                        "_schema_version": 1,
                        "auth": {"required": True, "session_timeout": 3600},
                        "features": {
                            "smart_glossary_matching_enabled": True,
                            "default_language": "en",
                            "show_ads": False,
                        },
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )

            # local.json: user has ldap; template adds messages section
            (cfg_dir / "local.json").write_text(
                json.dumps({"ldap": {"enabled": False}}, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            (cfg_dir / "local.json.template").write_text(
                json.dumps(
                    {"ldap": {"enabled": True}, "messages": {"login_banner": "Welcome", "usage_message": "Hello"}},
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )

            from backend.config.system_config import SystemConfig
            from backend.config.local_config import LocalConfig

            sys_cfg = SystemConfig.load_from_file("system.json")
            self.assertFalse(sys_cfg.auth.required)
            # show_ads should be added via merge + update_from_dict defaulting
            merged_sys = json.loads((cfg_dir / "system.json").read_text(encoding="utf-8"))
            self.assertEqual(merged_sys["auth"]["required"], False)
            self.assertIn("show_ads", merged_sys.get("features", {}))

            loc_cfg = LocalConfig.load_from_file("local.json")
            self.assertFalse(loc_cfg.ldap.enabled)
            merged_local = json.loads((cfg_dir / "local.json").read_text(encoding="utf-8"))
            self.assertIn("messages", merged_local)
        finally:
            # Best-effort cleanup is intentionally skipped to avoid Windows file lock issues.
            pass

    def test_translation_config_load_never_returns_none(self):
        td = tempfile.mkdtemp()
        try:
            repo_root = Path(__file__).resolve().parents[1]
            if str(repo_root) not in sys.path:
                sys.path.insert(0, str(repo_root))

            root = Path(td)
            os.environ["OWLANGS_CONFIG_PATH"] = str(root)
            cfg_dir = root / "configs"
            cfg_dir.mkdir(parents=True, exist_ok=True)

            # Disable file logging to avoid file locks in temp dir.
            (cfg_dir / "system.json").write_text(
                json.dumps(
                    {"_schema_version": 1, "logging": {"file_enabled": False, "console_enabled": False}},
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )

            (cfg_dir / "translation_config.json").write_text(
                json.dumps({"deep_split_defaults": {"default": True}}, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            (cfg_dir / "translation_config.json.template").write_text(
                json.dumps({"deep_split_defaults": {"default": False, "pdf": False}}, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )

            from backend.config.translation_config import TranslationConfig, get_default_deep_split

            cfg = TranslationConfig.load_from_file("translation_config.json")
            self.assertIsNotNone(cfg)
            self.assertTrue(hasattr(cfg, "get_default_deep_split"))
            _ = get_default_deep_split("a.pdf", "markdown_based")
        finally:
            pass


if __name__ == "__main__":
    unittest.main()

