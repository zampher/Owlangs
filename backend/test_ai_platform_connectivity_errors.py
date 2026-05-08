# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

"""Connectivity error messages for LLM endpoints (not Owlangs HTTP routes)."""

import asyncio
import importlib.util
import sys
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import httpx

_OWLANGS_ROOT = Path(__file__).resolve().parents[1]
_SERVICE_PATH = _OWLANGS_ROOT / "backend" / "auth" / "ai_platform_service.py"


def _load_ai_platform_service():
    """Load ai_platform_service without importing backend.auth package (avoids ldap3 side effects)."""
    if str(_OWLANGS_ROOT) not in sys.path:
        sys.path.insert(0, str(_OWLANGS_ROOT))
    spec = importlib.util.spec_from_file_location("ai_platform_service_testmod", _SERVICE_PATH)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules["ai_platform_service_testmod"] = mod
    spec.loader.exec_module(mod)
    return mod


class TestAiPlatformConnectivityErrors(unittest.TestCase):
    def test_ollama_connect_error_message_clarifies_llm_endpoint(self):
        mod = _load_ai_platform_service()

        async def run():
            fake_client = MagicMock()

            async def boom(*_a, **_k):
                raise httpx.ConnectError("Connection refused", request=MagicMock())

            fake_client.get = boom
            fake_client.post = boom
            cm = MagicMock()
            cm.__aenter__ = AsyncMock(return_value=fake_client)
            cm.__aexit__ = AsyncMock(return_value=None)
            with patch.object(mod.httpx, "AsyncClient", return_value=cm):
                return await mod.test_ai_platform_connectivity(
                    "ollama",
                    "http://127.0.0.1:11434",
                    "translategemma:latest",
                    "",
                )

        r = asyncio.run(run())
        self.assertFalse(r["success"])
        self.assertIn("127.0.0.1:11434", r["message"])
        self.assertIn("not an Owlangs HTTP route", r["message"])


if __name__ == "__main__":
    unittest.main()
