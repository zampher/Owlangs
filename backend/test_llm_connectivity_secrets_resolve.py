# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0
"""LLM preflight must resolve API keys from secrets when payload omits them."""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

BACKEND_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BACKEND_DIR.parent
for _p in (str(BACKEND_DIR), str(PROJECT_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import backend.utils as _backend_utils  # noqa: E402

sys.modules["utils"] = _backend_utils

from app.services.translation.translation_service import TranslationService  # noqa: E402


def test_llm_connectivity_resolves_empty_payload_key_from_secrets() -> None:
    svc = TranslationService(task_manager=MagicMock())
    payload = SimpleNamespace(
        base_url="https://api.deepseek.com/v1",
        model_id="deepseek-chat",
        api_key="",
    )
    task_state: dict = {}

    async def _run() -> None:
        with patch(
            "backend.app.services.platform.platform_service.platform_service.determine_platform_key",
            return_value="deepseek",
        ), patch(
            "backend.app.services.platform.platform_service.platform_service.get_api_protocol",
            return_value="openai",
        ), patch(
            "backend.config.config_loader.get_unified_config",
        ) as mock_cfg, patch(
            "backend.auth.ai_platform_service.test_ai_platform_connectivity",
            new_callable=AsyncMock,
        ) as mock_test, patch(
            "backend.config.ai_platform_status.update_platform_status",
        ):
            platforms = MagicMock()
            platforms.get_platform_config.return_value = SimpleNamespace(
                requires_api_key=True,
                test_connect_timeout=30,
                test_request_timeout=10,
            )
            unified = MagicMock()
            unified.platforms = platforms
            unified.get_platform_api_key.return_value = "sk-from-secrets-xxxxxxxx"
            mock_cfg.return_value = unified
            mock_test.return_value = {"success": True, "message": "ok"}

            ok = await svc._test_llm_connectivity(payload, "t1", task_state)
            assert ok is True
            mock_test.assert_awaited_once()
            kwargs = mock_test.await_args.kwargs
            assert kwargs["api_key"] == "sk-from-secrets-xxxxxxxx"
            assert kwargs["platform_type"] == "openai"

    import asyncio

    asyncio.run(_run())
