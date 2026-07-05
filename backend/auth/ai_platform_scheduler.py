# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

"""
Hourly job to test all configured AI platforms and persist status.
Backend keeps a single source of truth for platform availability.
"""

import asyncio
from typing import Any, Dict, Optional

from backend.logger import unified_logger as logger
from backend.logger.logger import LogModule


async def _test_one_platform(
    platform_type: str,
    base_url: str,
    model_name: str,
    api_key: str,
    requires_api_key: bool = True,
    test_connect_timeout: int = 30,
    test_request_timeout: int = 10,
) -> None:
    """Run connectivity test for one platform and persist result."""
    from .ai_platform_service import test_ai_platform_connectivity
    from backend.config.ai_platform_status import (
        platform_test_is_api_available,
        platform_test_status_error,
        update_platform_status,
    )

    result = await test_ai_platform_connectivity(
        platform_type, base_url, model_name or "", api_key, detect_max_tokens=False, requires_api_key=requires_api_key,
        test_connect_timeout=test_connect_timeout,
        test_request_timeout=test_request_timeout,
    )
    update_platform_status(
        platform_type,
        platform_test_is_api_available(result),
        platform_test_status_error(result),
    )
    logger.debug(
        LogModule.AUTH,
        f"[AI_PLATFORM_SCHEDULER] {platform_type}: success={result.get('success')}",
    )


async def run_one_round_ai_platform_tests() -> None:
    """
    Run one round of connectivity tests for all configured AI platforms and persist status.
    Called at startup (once) and then every hour by the scheduler loop.
    """
    from backend.config.secrets_manager import get_secrets_manager
    from backend.config.platforms_config import get_platforms_config
    from .mineru_service import test_mineru_connectivity
    from backend.config.ai_platform_status import update_platform_status

    logger.info(LogModule.AUTH, "[AI_PLATFORM_SCHEDULER] Running connectivity tests for all configured AI platforms...")
    print("[INFO] [STARTUP] Running AI platform connectivity tests for configured platforms...")

    secrets = get_secrets_manager()
    platforms_config = get_platforms_config()
    # Use get_api_keys_meta to check configured flag (not just key presence)
    api_keys_meta = secrets.get_api_keys_meta()

    # LLM-like platforms: need url, model, api_key (if required)
    for platform_key, platform_obj in platforms_config.platforms.items():
        if platform_key in ("mineru", "mineru_local"):
            continue
        
        # Check if platform requires API key
        requires_api_key = getattr(platform_obj, "requires_api_key", True)
        key_meta = api_keys_meta.get(platform_key, {})
        api_key = key_meta.get("key", "")
        is_configured = key_meta.get("configured", False)
        
        # For platforms requiring API key: must be marked as configured
        # The configured flag is set by user when they save a real API key
        if requires_api_key and not is_configured:
            logger.debug(LogModule.AUTH, f"[AI_PLATFORM_SCHEDULER] Skipping {platform_key}: not configured (configured={is_configured})")
            continue
        
        base_url = getattr(platform_obj, "url", "") or ""
        model_name = getattr(platform_obj, "model", "") or ""
        test_connect_timeout = getattr(platform_obj, "test_connect_timeout", 30) or 30
        test_request_timeout = getattr(platform_obj, "test_request_timeout", 10) or 10
        if not base_url or (not model_name and platform_key not in ("volcengine_ark", "doubao", "ark")):
            continue
        try:
            await _test_one_platform(
                platform_key, base_url, model_name or "", api_key,
                requires_api_key=requires_api_key,
                test_connect_timeout=test_connect_timeout,
                test_request_timeout=test_request_timeout,
            )
        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.warning(LogModule.AUTH, f"[AI_PLATFORM_SCHEDULER] Test {platform_key} failed: {e}")
            update_platform_status(platform_key, False, str(e))

    # MinerU cloud: separate token
    try:
        mineru_token = secrets.get_mineru_token()
        if mineru_token:
            result = await test_mineru_connectivity(mineru_token)
            update_platform_status("mineru", result.get("success", False), result.get("error"))
    except asyncio.CancelledError:
        raise
    except Exception as e:
        logger.warning(LogModule.AUTH, f"[AI_PLATFORM_SCHEDULER] MinerU test failed: {e}")
        update_platform_status("mineru", False, str(e))

    # Local MinerU: optional key, base_url from platform config
    try:
        from .mineru_service import test_mineru_local_connectivity
        mineru_local_cfg = platforms_config.get_platform_config("mineru_local")
        if mineru_local_cfg:
            base_url = (getattr(mineru_local_cfg, "url", None) or "").strip().rstrip("/") or "http://localhost:8080/api/v4"
            # Respect platform config: only require API key if explicitly marked as required
            requires_api_key = getattr(mineru_local_cfg, "requires_api_key", True)
            if requires_api_key:
                api_keys = secrets.get_api_keys()
                api_key = (api_keys.get("mineru_local") or "").strip()
            else:
                api_key = ""
            result = await test_mineru_local_connectivity(base_url, api_key or None)
            update_platform_status("mineru_local", result.get("success", False), result.get("message") or result.get("error"))
    except asyncio.CancelledError:
        raise
    except Exception as e:
        logger.warning(LogModule.AUTH, f"[AI_PLATFORM_SCHEDULER] Local MinerU test failed: {e}")
        update_platform_status("mineru_local", False, str(e))

    logger.info(LogModule.AUTH, "[AI_PLATFORM_SCHEDULER] Platform tests completed")


async def run_hourly_ai_platform_tests() -> None:
    """
    Loop: sleep 1 hour, then run one round of platform tests. The first round is run at startup
    before this task is started, so we only sleep then run here.
    Intended to be run as asyncio.create_task() from app lifespan.
    """
    while True:
        try:
            await asyncio.sleep(3600)  # 1 hour
            await run_one_round_ai_platform_tests()
        except asyncio.CancelledError:
            logger.info(LogModule.AUTH, "[AI_PLATFORM_SCHEDULER] Hourly task cancelled")
            return
        except Exception as e:
            logger.error(LogModule.AUTH, f"[AI_PLATFORM_SCHEDULER] Hourly run failed: {e}", exc_info=True)
