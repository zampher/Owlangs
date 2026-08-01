# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

"""LLM connectivity must use chat probe (not /models alone)."""

from __future__ import annotations

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
    if str(_OWLANGS_ROOT) not in sys.path:
        sys.path.insert(0, str(_OWLANGS_ROOT))
    spec = importlib.util.spec_from_file_location(
        "ai_platform_service_chat_probe", _SERVICE_PATH
    )
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules["ai_platform_service_chat_probe"] = mod
    spec.loader.exec_module(mod)
    return mod


def _mock_client(*, get_resp=None, post_resp=None, post_side_effect=None):
    fake_client = MagicMock()
    if get_resp is not None:
        fake_client.get = AsyncMock(return_value=get_resp)
    else:
        fake_client.get = AsyncMock(
            side_effect=httpx.ConnectError("unused", request=MagicMock())
        )
    if post_side_effect is not None:
        fake_client.post = AsyncMock(side_effect=post_side_effect)
    else:
        fake_client.post = AsyncMock(return_value=post_resp)
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=fake_client)
    cm.__aexit__ = AsyncMock(return_value=None)
    return fake_client, cm


class TestAiPlatformChatProbe(unittest.TestCase):
    def test_empty_model_name_fails(self):
        mod = _load_ai_platform_service()

        async def run():
            return await mod.test_ai_platform_connectivity(
                "deepseek",
                "https://api.deepseek.com/v1",
                "",
                "sk-test",
                detect_max_tokens=False,
            )

        r = asyncio.run(run())
        self.assertFalse(r["success"])
        self.assertIn("Model name is required", r["message"])

    def test_openai_compatible_does_not_succeed_on_models_alone(self):
        """GET /models 200 must not short-circuit; chat failure means test fails."""
        mod = _load_ai_platform_service()
        models_ok = MagicMock()
        models_ok.status_code = 200
        models_ok.json = MagicMock(
            return_value={"data": [{"id": "deepseek-v4-flash"}]}
        )
        chat_fail = MagicMock()
        chat_fail.status_code = 400
        chat_fail.text = (
            '{"error":{"message":"Model Not Exist","type":"invalid_request_error"}}'
        )
        chat_fail.json = MagicMock(
            return_value={
                "error": {
                    "message": "Model Not Exist",
                    "type": "invalid_request_error",
                }
            }
        )
        fake_client, cm = _mock_client(get_resp=models_ok, post_resp=chat_fail)

        async def run():
            with patch.object(mod.httpx, "AsyncClient", return_value=cm):
                with patch.object(
                    mod, "detect_max_tokens_limit", new=AsyncMock(return_value=None)
                ):
                    return await mod.test_ai_platform_connectivity(
                        "deepseek",
                        "https://api.deepseek.com/v1",
                        "deepseek-chat",
                        "sk-test",
                        detect_max_tokens=False,
                    )

        r = asyncio.run(run())
        self.assertFalse(r["success"])
        fake_client.post.assert_awaited()
        post_kwargs = fake_client.post.await_args
        self.assertIn("/chat/completions", post_kwargs.args[0])
        self.assertEqual(post_kwargs.kwargs["json"]["model"], "deepseek-chat")

    def test_openai_compatible_chat_success(self):
        mod = _load_ai_platform_service()
        chat_ok = MagicMock()
        chat_ok.status_code = 200
        chat_ok.json = MagicMock(
            return_value={"choices": [{"message": {"content": "ok"}}]}
        )
        fake_client, cm = _mock_client(post_resp=chat_ok)

        async def run():
            with patch.object(mod.httpx, "AsyncClient", return_value=cm):
                with patch.object(
                    mod, "detect_max_tokens_limit", new=AsyncMock(return_value=None)
                ):
                    return await mod.test_ai_platform_connectivity(
                        "deepseek",
                        "https://api.deepseek.com/v1",
                        "deepseek-v4-flash",
                        "sk-test",
                        detect_max_tokens=False,
                    )

        r = asyncio.run(run())
        self.assertTrue(r["success"])
        self.assertIn("chat probe", r["message"])
        self.assertIn("deepseek-v4-flash", r["message"])
        fake_client.post.assert_awaited()

    def test_ollama_uses_chat_not_tags_alone(self):
        mod = _load_ai_platform_service()
        chat_ok = MagicMock()
        chat_ok.status_code = 200
        chat_ok.json = MagicMock(return_value={"message": {"content": "hi"}})
        fake_client, cm = _mock_client(post_resp=chat_ok)

        async def run():
            with patch.object(mod.httpx, "AsyncClient", return_value=cm):
                return await mod.test_ai_platform_connectivity(
                    "ollama",
                    "http://127.0.0.1:11434",
                    "translategemma:latest",
                    "",
                    requires_api_key=False,
                    detect_max_tokens=False,
                )

        r = asyncio.run(run())
        self.assertTrue(r["success"])
        post_url = fake_client.post.await_args.args[0]
        self.assertTrue(post_url.endswith("/api/chat"))
        self.assertEqual(
            fake_client.post.await_args.kwargs["json"]["model"],
            "translategemma:latest",
        )


if __name__ == "__main__":
    unittest.main()
