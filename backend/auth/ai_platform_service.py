from typing import Dict, Any, Optional
import json

import httpx
from logger import unified_logger as logger
from logger.logger import LogModule


def _format_test_error(status_code: int, response_text: str) -> str:
    """Convert HTTP test response into a user-friendly error message."""
    text_lower = response_text.lower()
    if status_code == 402:
        return "Insufficient balance on LLM platform. Please check your account and add funds."
    if status_code == 429 and any(
        k in text_lower
        for k in ("余额不足", "insufficient balance", "quota", "exceeded your quota", "无可用资源包")
    ):
        return "Insufficient balance or quota exceeded on LLM platform. Please check your account."
    if status_code == 401 and any(
        k in text_lower
        for k in ("invalid api key", "authentication", "unauthorized", "词元密钥已过期", "验证不正确")
    ):
        return "Invalid API key or authentication failed. Please check your API key in Settings."
    return f"API returned status {status_code}: {response_text[:500]}"


def _is_anthropic_family_platform(platform_type: str) -> bool:
    """True for anthropic, anthropic_local, claude_*, etc."""
    p = (platform_type or "").lower()
    return p == "anthropic" or p.startswith("anthropic_") or "claude" in p


def _is_zhipu_bigmodel_anthropic_endpoint(base_url: str) -> bool:
    """Zhipu GLM Anthropic-compatible base (no OpenAI-style GET /models list)."""
    u = (base_url or "").lower()
    return "bigmodel.cn" in u and "anthropic" in u


# Known GLM model ids for Anthropic-compatible endpoint (docs change; refresh when adding new SKUs).
_ZHIPU_GLM_ANTHROPIC_COMPAT_MODELS = [
    "glm-5",
    "glm-4.6v",
    "glm-4.6",
    "glm-4.5",
    "glm-4.5-air",
    "glm-4.5-x",
    "glm-4-flash",
    "glm-4-plus",
    "glm-4-air",
    "glm-4-airx",
    "glm-4",
    "glm-z1-flash",
    "glm-z1-air",
]

_ANTHROPIC_OFFICIAL_STATIC_MODELS = [
    "claude-3-5-sonnet-20241022",
    "claude-3-opus-20240229",
    "claude-3-sonnet-20240229",
    "claude-3-haiku-20240307",
]


def _parse_models_from_openai_list_json(models_data: object) -> list[str]:
    """Parse OpenAI-style GET /models JSON into model id strings."""
    models: list[str] = []
    if isinstance(models_data, dict) and "data" in models_data:
        for model_info in models_data["data"]:
            if isinstance(model_info, dict):
                model_id = model_info.get("id")
                if model_id:
                    models.append(str(model_id))
    elif isinstance(models_data, list):
        for model_info in models_data:
            if isinstance(model_info, str):
                models.append(model_info)
            elif isinstance(model_info, dict):
                model_id = model_info.get("id") or model_info.get("name")
                if model_id:
                    models.append(str(model_id))
    return models


async def _fetch_paddle_openapi_info(client: httpx.AsyncClient, base: str) -> Dict[str, Any]:
    """Best-effort OpenAPI fetch to detect sync /layout-parsing vs cloud async jobs API."""
    from layout.ocr_provider.paddle.capability_probe import analyze_openapi_paths

    for spec_path in ("/openapi.json", "/docs/openapi.json"):
        try:
            resp = await client.get(f"{base}{spec_path}")
            if resp.status_code == 200:
                data = resp.json()
                if isinstance(data, dict):
                    return analyze_openapi_paths(data.get("paths"))
        except Exception:
            continue
    return analyze_openapi_paths(None)


def _paddle_capability_test_result(
    *,
    platform: str,
    base: str,
    capability: Dict[str, Any],
    api_style: str,
) -> Dict[str, Any]:
    from layout.ocr_provider.paddle.capability_probe import build_paddle_test_user_message

    message = build_paddle_test_user_message(
        platform=platform,
        base=base,
        capability=capability,
        api_style=api_style,
        reachable=True,
    )
    return {
        "success": True,
        "meets_requirements": bool(capability.get("document_parsing_capable")),
        "document_parsing_capable": bool(capability.get("document_parsing_capable")),
        "capability_level": capability.get("capability_level"),
        "warning_code": capability.get("warning_code"),
        "api_style": api_style,
        "layout_block_labels": capability.get("layout_block_labels") or [],
        "message": message,
    }


async def _test_paddleocr_connectivity(
    base_url: str,
    api_key: str,
    platform: str,
) -> Dict[str, Any]:
    """Test PaddleOCR API connectivity and document-parsing capability.

    PaddleOCR is a parser platform, not an LLM. Besides reachability, we probe
    whether the deployment supports VL layout parsing (titles/tables/formulas),
    not plain line OCR only.
    """
    try:
        import base64

        from layout.ocr_provider.paddle.capability_probe import (
            CAPABILITY_CLOUD_ASYNC,
            analyze_probe_payload,
            build_probe_pdf_bytes,
        )
        from layout.ocr_provider.paddle.sync_infer_adapter import is_sync_infer_submit_path

        base = (base_url or '').strip().rstrip('/')
        if not base:
            return {"success": False, "error": "No base URL configured for PaddleOCR"}

        from backend.config.config_loader import get_unified_config
        config = get_unified_config()
        platform_cfg = config.get_ai_platform_config(platform)
        api_endpoints = (platform_cfg or {}).get('api_endpoints', {})
        submit_path = api_endpoints.get('submit', '/api/v2/ocr/jobs')
        probe_url = f"{base}{submit_path}"

        async with httpx.AsyncClient(timeout=120.0, proxy=None, mounts={'http://': None, 'https://': None}) as client:
            headers: Dict[str, str] = {}
            if api_key and api_key.strip():
                headers["Authorization"] = f"bearer {api_key}"

            openapi_info = await _fetch_paddle_openapi_info(client, base)
            api_style = str(openapi_info.get("api_style") or "unknown")
            use_sync_probe = is_sync_infer_submit_path(submit_path) or api_style == "sync_infer"

            if use_sync_probe:
                sync_submit = probe_url
                health_resp = await client.get(f"{base}/health", headers=headers)
                if health_resp.status_code not in (200, 404):
                    return {
                        "success": False,
                        "error": (
                            f"PaddleOCR local health check failed at {base}/health "
                            f"(HTTP {health_resp.status_code}): {health_resp.text[:300]}"
                        ),
                        "message": f"PaddleOCR local health check failed (HTTP {health_resp.status_code})",
                    }

                file_bytes = build_probe_pdf_bytes()
                payload = {
                    "file": base64.b64encode(file_bytes).decode("ascii"),
                    "fileType": 0,
                    "useDocOrientationClassify": False,
                }
                resp = await client.post(
                    sync_submit,
                    json=payload,
                    headers={**headers, "Content-Type": "application/json"},
                )
                if resp.status_code != 200:
                    return {
                        "success": False,
                        "error": (
                            f"PaddleOCR local sync API rejected request at {sync_submit} "
                            f"(HTTP {resp.status_code}): {resp.text[:500]}"
                        ),
                        "message": f"PaddleOCR local sync test failed (HTTP {resp.status_code})",
                    }

                body = resp.json()
                capability = analyze_probe_payload(body)
                logger.info(
                    LogModule.AUTH,
                    f"PaddleOCR capability probe: platform={platform} "
                    f"level={capability.get('capability_level')} "
                    f"labels={capability.get('layout_block_labels')}",
                )
                return _paddle_capability_test_result(
                    platform=platform,
                    base=base,
                    capability=capability,
                    api_style=api_style if api_style != "unknown" else "sync_infer",
                )

            # Cloud async: GET /api/v2/ocr/jobs often returns 405 (method not
            # allowed) even with a bad token, so a GET probe falsely reports
            # success. Real conversion uses multipart POST — probe the same way.
            if platform == "paddle" and not (api_key or "").strip():
                return {
                    "success": False,
                    "error": (
                        "PaddleOCR cloud API key is empty. Configure a valid "
                        "AI Studio access token before testing."
                    ),
                    "message": "PaddleOCR cloud API key is empty",
                }

            if openapi_info.get("has_sync_infer_api") and not openapi_info.get("has_cloud_jobs_api"):
                capability = analyze_probe_payload({})
                capability["capability_level"] = CAPABILITY_TEXT_OCR_ONLY
                capability["document_parsing_capable"] = False
                capability["warning_code"] = "paddle_text_ocr_only"
                return _paddle_capability_test_result(
                    platform=platform,
                    base=base,
                    capability=capability,
                    api_style="sync_infer",
                )

            paddle_model = (platform_cfg or {}).get("model") or "PaddleOCR-VL-1.6"
            if not paddle_model or paddle_model == "default":
                paddle_model = "PaddleOCR-VL-1.6"
            file_bytes = build_probe_pdf_bytes()
            optional_payload = {
                "useDocOrientationClassify": False,
                "restructurePages": False,
            }
            post_resp = await client.post(
                probe_url,
                data={
                    "model": paddle_model,
                    "optionalPayload": json.dumps(optional_payload),
                },
                files={"file": ("probe.pdf", file_bytes, "application/pdf")},
                headers=headers,
            )
            if post_resp.status_code in (401, 403):
                return {
                    "success": False,
                    "error": (
                        f"PaddleOCR cloud auth failed at {probe_url} "
                        f"(HTTP {post_resp.status_code}). The AI Studio access "
                        f"token is missing, expired, or invalid. "
                        f"Response: {post_resp.text[:300]}"
                    ),
                    "message": (
                        f"PaddleOCR cloud auth failed "
                        f"(HTTP {post_resp.status_code})"
                    ),
                }
            if post_resp.status_code == 404:
                return {
                    "success": False,
                    "error": (
                        f"PaddleOCR API endpoint not found at {probe_url} "
                        f"(HTTP 404). Check the base URL in Settings."
                    ),
                    "message": (
                        f"PaddleOCR API endpoint not found at {probe_url} "
                        f"(HTTP 404)."
                    ),
                }
            if post_resp.status_code not in (200, 201, 202):
                return {
                    "success": False,
                    "error": (
                        f"PaddleOCR cloud job submit failed at {probe_url} "
                        f"(HTTP {post_resp.status_code}): "
                        f"{post_resp.text[:500]}"
                    ),
                    "message": (
                        f"PaddleOCR cloud submit failed "
                        f"(HTTP {post_resp.status_code})"
                    ),
                }

            # Auth + endpoint OK; do not wait for the probe job to finish.
            capability = {
                "capability_level": CAPABILITY_CLOUD_ASYNC,
                "document_parsing_capable": True,
                "warning_code": None,
                "layout_block_labels": [],
            }
            logger.info(
                LogModule.AUTH,
                f"PaddleOCR cloud auth probe OK: platform={platform} "
                f"model={paddle_model} status={post_resp.status_code}",
            )
            return _paddle_capability_test_result(
                platform=platform,
                base=base,
                capability=capability,
                api_style=api_style if api_style != "unknown" else "cloud_async",
            )

    except httpx.ConnectError as e:
        message = f"Cannot connect to PaddleOCR at {base_url!r}: {e}."
        payload: Dict[str, Any] = {
            "success": False,
            "error": (
                f"{message} Check that the service is running and the URL is correct."
            ),
            "message": message,
        }
        if platform == "paddle_local":
            payload["warning_code"] = "paddle_unreachable"
        return payload
    except httpx.TimeoutException:
        return {
            "success": False,
            "error": f"Connection to PaddleOCR at {base_url!r} timed out. Check the service status and network.",
            "message": f"Connection to PaddleOCR at {base_url!r} timed out.",
        }
    except Exception as e:
        return {"success": False, "error": f"PaddleOCR test failed: {e}", "message": f"PaddleOCR test failed: {e}"}


async def detect_max_tokens_limit(
    platform_type: str,
    base_url: str,
    model_name: str,
    api_key: str,
    requires_api_key: bool = True,
) -> Optional[int]:
    """
    Detect max_tokens limit for a platform by trying different values.
    
    Returns:
        Detected max_tokens limit, or None if detection failed
    """
    platform = (platform_type or '').lower()
    
    # Try to get from models API first (OpenAI-compatible)
    try:
        async with httpx.AsyncClient(timeout=10.0, proxy=None, mounts={'http://': None, 'https://': None}) as client:
            headers = {"Content-Type": "application/json"}
            if requires_api_key and api_key and api_key.strip():
                headers["Authorization"] = f"Bearer {api_key}"
            
            # Try /v1/models endpoint (OpenAI-compatible)
            models_url = f"{base_url.rstrip('/')}/models"
            resp = await client.get(models_url, headers=headers)
            
            if resp.status_code == 200:
                models_data = resp.json()
                if isinstance(models_data, dict) and "data" in models_data:
                    # Find the model in the list
                    for model_info in models_data["data"]:
                        if model_info.get("id") == model_name:
                            # Check if model has context_length or max_output_tokens
                            if "context_length" in model_info:
                                # max_tokens is typically less than context_length
                                # Use a conservative estimate (e.g., 80% of context_length)
                                context_length = model_info["context_length"]
                                estimated_max = int(context_length * 0.8)
                                logger.info(LogModule.AUTH,f"[MAX_TOKENS_DETECT] Found context_length={context_length} for {model_name}, estimated max_tokens={estimated_max}")
                                return estimated_max
                            elif "max_output_tokens" in model_info:
                                max_output = model_info["max_output_tokens"]
                                logger.info(LogModule.AUTH,f"[MAX_TOKENS_DETECT] Found max_output_tokens={max_output} for {model_name}")
                                return max_output
    except Exception as e:
        logger.debug(LogModule.AUTH, f"[MAX_TOKENS_DETECT] Models API detection failed: {e}")
    
    # Fallback: Try testing different values to find the limit
    # Test values: 8192, 16384, 32768, 65536, 128000, 200000
    test_values = [8192, 16384, 32768, 65536, 128000, 200000]
    
    try:
        async with httpx.AsyncClient(timeout=10.0, proxy=None, mounts={'http://': None, 'https://': None}) as client:
            # Find the highest valid max_tokens value
            max_valid = None
            for test_value in test_values:
                try:
                    if platform == 'anthropic':
                        payload = {
                            "model": model_name,
                            "max_tokens": test_value,
                            "messages": [
                                {"role": "user", "content": "test"}
                            ],
                        }
                        headers_anthropic = {
                            "Content-Type": "application/json",
                            "x-api-key": api_key,
                            "anthropic-version": "2023-06-01",
                        }
                        resp = await client.post(f"{base_url}/messages", json=payload, headers=headers_anthropic, timeout=5.0)
                    elif platform == 'google':
                        payload = {
                            "contents": [
                                {"parts": [{"text": "test"}]}
                            ],
                            "generationConfig": {"maxOutputTokens": test_value},
                        }
                        resp = await client.post(
                            f"{base_url}/models/{model_name}:generateContent?key={api_key}",
                            json=payload,
                            headers={"Content-Type": "application/json"},
                            timeout=5.0,
                        )
                    else:
                        # OpenAI-compatible
                        headers = {"Content-Type": "application/json"}
                        if requires_api_key and api_key and api_key.strip():
                            headers["Authorization"] = f"Bearer {api_key}"
                        payload = {
                            "model": model_name,
                            "messages": [
                                {"role": "user", "content": "test"}
                            ],
                            "max_tokens": test_value,
                        }
                        resp = await client.post(f"{base_url}/chat/completions", json=payload, headers=headers, timeout=5.0)
                    
                    if resp.status_code == 200:
                        max_valid = test_value
                        # Continue to test higher values
                    elif resp.status_code == 400:
                        # Check if error is about max_tokens
                        try:
                            error_data = resp.json()
                            error_msg = str(error_data.get("error", {})).lower()
                            if "max_tokens" in error_msg or "maxoutputtokens" in error_msg or "invalid max" in error_msg:
                                # Try to extract the limit from error message
                                import re
                                # Priority: match range upper bound [1, 8192] first, then standalone numbers
                                # Avoid matching the lower bound (1) in ranges
                                match = re.search(r'\[.*?,\s*(\d+)\]|max.*?(\d+)|limit.*?(\d+)', error_msg)
                                if match:
                                    limit_str = match.group(1) or match.group(2) or match.group(3)
                                    if limit_str:
                                        limit = int(limit_str)
                                        # Validate: reject suspiciously low values (< 1024)
                                        if limit < 1024:
                                            logger.warning(LogModule.AUTH, f"[MAX_TOKENS_DETECT] Extracted suspiciously low limit for {model_name}: {limit}, ignoring")
                                        else:
                                            logger.info(LogModule.AUTH,f"[MAX_TOKENS_DETECT] Extracted limit from error for {model_name}: {limit}")
                                            return limit
                                # Found the limit, return the previous valid value
                                if max_valid:
                                    logger.info(LogModule.AUTH,f"[MAX_TOKENS_DETECT] Detected limit for {model_name}: {max_valid}")
                                    return max_valid
                                # If no valid value found yet, this might be the first test, skip
                                break
                        except Exception:
                            pass
                        # If max_tokens error and we have a valid value, return it
                        if max_valid:
                            return max_valid
                        # Otherwise, stop searching
                        break
                    else:
                        # Other errors, continue testing
                        continue
                except httpx.TimeoutException:
                    # Timeout, skip this value
                    continue
                except Exception as e:
                    logger.debug(LogModule.AUTH, f"[MAX_TOKENS_DETECT] Error testing {test_value}: {e}")
                    continue
            
            if max_valid:
                logger.info(LogModule.AUTH,f"[MAX_TOKENS_DETECT] Detected max_tokens limit for {model_name}: {max_valid}")
                return max_valid
    except Exception as e:
        logger.debug(LogModule.AUTH, f"[MAX_TOKENS_DETECT] Detection failed: {e}")
    
    return None


async def test_ai_platform_connectivity(
    platform_type: str,
    base_url: str,
    model_name: str,
    api_key: str,
    detect_max_tokens: bool = True,
    requires_api_key: bool = True,
    test_connect_timeout: int = 30,
    test_request_timeout: int = 10,
) -> Dict[str, Any]:
    """Unified AI 平台连通性测试。

    返回：{"success": bool, "message"?: str, "error"?: str, "max_tokens"?: int, ...}
    """
    platform = (platform_type or '').lower()

    logger.info(
        LogModule.AUTH,
        f"[CONNECTIVITY_TEST] platform={platform}, model={model_name}, "
        f"test_connect_timeout={test_connect_timeout}s, test_request_timeout={test_request_timeout}s"
    )

    # MinerU cloud: dedicated test (create minimal task)
    if platform == 'mineru':
        try:
            from .mineru_service import test_mineru_connectivity
            return await test_mineru_connectivity(api_key)
        except Exception as e:
            return {"success": False, "error": f"MinerU test failed: {e}"}

    # Local MinerU: same API shape, base_url from request, API key optional
    if platform == 'mineru_local':
        try:
            from .mineru_service import test_mineru_local_connectivity
            base = (base_url or '').strip().rstrip('/') or 'http://localhost:8080/api/v4'
            return await test_mineru_local_connectivity(base, api_key or '')
        except Exception as e:
            return {"success": False, "error": f"Local MinerU test failed: {e}"}

    # PaddleOCR cloud / local: parser platform, check API endpoint reachability
    if platform in ('paddle', 'paddle_local'):
        return await _test_paddleocr_connectivity(base_url, api_key or '', platform)

    # LLM platforms: use models list API for connectivity test (no token consumption)
    result: Dict[str, Any] = {}

    try:
        # Disable proxy for local/remote direct connections
        async with httpx.AsyncClient(timeout=float(test_connect_timeout), proxy=None, mounts={'http://': None, 'https://': None}) as client:
            if platform == 'anthropic':
                # Anthropic: use /v1/models endpoint (beta) or fallback to minimal request
                headers = {
                    "Content-Type": "application/json",
                    "x-api-key": api_key,
                    "anthropic-version": "2023-06-01",
                }
                # Try models endpoint first (no token consumption)
                try:
                    models_resp = await client.get(f"{base_url}/v1/models", headers=headers, timeout=float(test_request_timeout))
                    if models_resp.status_code == 200:
                        result["success"] = True
                        result["message"] = "Anthropic API connection successful (models endpoint)"
                        return result
                except Exception:
                    pass
                # Fallback: minimal API call with max_tokens=1 to minimize consumption
                payload = {
                    "model": model_name,
                    "max_tokens": 1,
                    "messages": [{"role": "user", "content": "Hi"}],
                }
                resp = await client.post(f"{base_url}/messages", json=payload, headers=headers)

            elif platform == 'google':
                # Google: use /v1/models endpoint to list available models
                headers = {"Content-Type": "application/json"}
                models_url = f"{base_url}/models?key={api_key}"
                try:
                    models_resp = await client.get(models_url, headers=headers, timeout=float(test_request_timeout))
                    if models_resp.status_code == 200:
                        result["success"] = True
                        result["message"] = "Google AI connection successful (models endpoint)"
                        # Try to detect max tokens if requested
                        if detect_max_tokens:
                            try:
                                detected_max = await detect_max_tokens_limit(platform_type, base_url, model_name, api_key, requires_api_key=requires_api_key)
                                if detected_max:
                                    result["max_tokens"] = detected_max
                                    result["message"] += f" (max_tokens: {detected_max})"
                            except Exception as e:
                                logger.debug(LogModule.AUTH, f"[TEST_AI_PLATFORM] Failed to detect max_tokens: {e}")
                        return result
                except Exception:
                    pass
                # Fallback: minimal request
                payload = {
                    "contents": [{"parts": [{"text": "Hi"}]}],
                    "generationConfig": {"maxOutputTokens": 1},
                }
                resp = await client.post(
                    f"{base_url}/models/{model_name}:generateContent?key={api_key}",
                    json=payload,
                    headers=headers,
                )

            elif platform == 'ollama':
                # Ollama: use /api/tags to list local models (no token consumption)
                # Strip OpenAI-style path prefixes (/v1, /api/v1) from base_url.
                # Ollama native API serves /api/tags and /api/chat at the server root.
                _ollama_base = base_url.rstrip('/')
                for _suffix in ('/v1', '/api/v1', '/api'):
                    if _ollama_base.endswith(_suffix):
                        _ollama_base = _ollama_base[:-len(_suffix)]
                        break
                try:
                    tags_resp = await client.get(f"{_ollama_base}/api/tags", timeout=float(test_request_timeout))
                    if tags_resp.status_code == 200:
                        result["success"] = True
                        result["message"] = "Ollama connection successful (tags endpoint)"
                        return result
                except Exception:
                    pass
                # Fallback: minimal chat request
                payload = {
                    "model": model_name,
                    "messages": [{"role": "user", "content": "Hi"}],
                    "stream": False,
                    "options": {"num_predict": 1},
                }
                headers = {"Content-Type": "application/json"}
                resp = await client.post(f"{_ollama_base}/api/chat", json=payload, headers=headers)

            elif platform == 'local':
                # Local (OpenAI-compatible): use /v1/models endpoint
                headers = {"Content-Type": "application/json"}
                if requires_api_key and api_key and api_key.strip():
                    headers["Authorization"] = f"Bearer {api_key}"
                try:
                    models_resp = await client.get(f"{base_url}/models", headers=headers, timeout=float(test_request_timeout))
                    if models_resp.status_code == 200:
                        result["success"] = True
                        result["message"] = "Local API connection successful (models endpoint)"
                        # Try to detect max tokens if requested
                        if detect_max_tokens:
                            try:
                                detected_max = await detect_max_tokens_limit(platform_type, base_url, model_name, api_key, requires_api_key=requires_api_key)
                                if detected_max:
                                    result["max_tokens"] = detected_max
                                    result["message"] += f" (max_tokens: {detected_max})"
                            except Exception as e:
                                logger.debug(LogModule.AUTH, f"[TEST_AI_PLATFORM] Failed to detect max_tokens: {e}")
                        return result
                except Exception:
                    pass
                # Fallback: minimal request with max_tokens=1
                payload = {
                    "model": model_name,
                    "messages": [{"role": "user", "content": "Hi"}],
                    "max_tokens": 1,
                    "stream": False,
                }
                resp = await client.post(f"{base_url}/chat/completions", json=payload, headers=headers)

            else:
                # Default: OpenAI-compatible cloud (DeepSeek, OpenAI, etc.)
                # Use /v1/models endpoint (no token consumption)
                headers = {"Content-Type": "application/json"}
                if requires_api_key and api_key and api_key.strip():
                    headers["Authorization"] = f"Bearer {api_key}"
                
                # Special handling for platforms with public /models endpoint (e.g., OpenRouter)
                # These platforms return model list without authentication, so we need to
                # verify the API key by making an actual chat request
                skip_models_endpoint = platform in ("openrouter",)
                
                if not skip_models_endpoint:
                    try:
                        models_resp = await client.get(f"{base_url}/models", headers=headers, timeout=float(test_request_timeout))
                        if models_resp.status_code == 200:
                            # Validate response content - some platforms return 200 with error
                            try:
                                models_data = models_resp.json()
                                # Check for Baidu-style error response
                                if isinstance(models_data, dict) and models_data.get("error_code"):
                                    error_msg = models_data.get("error_msg", "Unknown error")
                                    logger.info(
                                        LogModule.AUTH,
                                        f"[TEST_AI_PLATFORM] {platform_type} /models returned error_code={models_data.get('error_code')}: {error_msg}",
                                    )
                                    # Don't return success, fall through to chat/completions test
                                else:
                                    # Check for valid OpenAI-style model list
                                    if isinstance(models_data, dict) and "data" in models_data:
                                        result["success"] = True
                                        result["message"] = f"{platform_type} connection successful (models endpoint)"
                                        # Try to detect max tokens if requested
                                        if detect_max_tokens:
                                            try:
                                                detected_max = await detect_max_tokens_limit(platform_type, base_url, model_name, api_key, requires_api_key=requires_api_key)
                                                if detected_max:
                                                    result["max_tokens"] = detected_max
                                                    result["message"] += f" (max_tokens: {detected_max})"
                                            except Exception as e:
                                                logger.debug(LogModule.AUTH, f"[TEST_AI_PLATFORM] Failed to detect max_tokens: {e}")
                                        return result
                                    else:
                                        # Response doesn't look like a valid model list
                                        # Fall through to chat/completions test to verify key
                                        logger.debug(
                                            LogModule.AUTH,
                                            f"[TEST_AI_PLATFORM] {platform_type} /models response doesn't contain 'data' field, falling back to chat test",
                                        )
                            except Exception:
                                # Invalid JSON response, fall through to chat/completions test
                                pass
                    except Exception:
                        pass
                else:
                    logger.debug(
                        LogModule.AUTH,
                        f"[TEST_AI_PLATFORM] {platform_type} has public /models endpoint, skipping to chat/completions test",
                    )
                
                # Fallback: minimal request with max_tokens=1
                payload = {
                    "model": model_name,
                    "messages": [{"role": "user", "content": "Hi"}],
                    "max_tokens": 1,
                    "stream": False,
                }
                resp = await client.post(f"{base_url}/chat/completions", json=payload, headers=headers)

        if resp.status_code == 200:
            # Validate response content - some platforms (e.g., Baidu) return 200 with error_code
            try:
                resp_data = resp.json()
                # Check for Baidu-style error response in chat/completions
                if isinstance(resp_data, dict) and resp_data.get("error_code"):
                    error_msg = resp_data.get("error_msg", "Unknown error")
                    logger.info(
                        LogModule.AUTH,
                        f"[TEST_AI_PLATFORM] {platform_type} chat/completions returned error_code={resp_data.get('error_code')}: {error_msg}",
                    )
                    err_msg = _format_test_error(401, resp.text)  # Treat as auth error
                    return {
                        "success": False,
                        "error": err_msg,
                        "message": err_msg,
                    }
                # Check for OpenAI-style error response
                if isinstance(resp_data, dict) and resp_data.get("error"):
                    error_info = resp_data.get("error", {})
                    error_msg = error_info.get("message", "Unknown error") if isinstance(error_info, dict) else str(error_info)
                    logger.info(
                        LogModule.AUTH,
                        f"[TEST_AI_PLATFORM] {platform_type} chat/completions returned error: {error_msg}",
                    )
                    err_msg = _format_test_error(401, resp.text)  # Treat as auth error
                    return {
                        "success": False,
                        "error": err_msg,
                        "message": err_msg,
                    }
            except Exception:
                # Not JSON or can't parse, assume success
                pass
            result["success"] = True
            result["message"] = result.get("message", "AI platform connection test successful")
            return result
        else:
            error_text = resp.text
            logger.info(
                LogModule.AUTH,
                f"[TEST_AI_PLATFORM] {platform_type} failed: status={resp.status_code}, body={error_text[:500]!r}",
            )
            # Try to extract max_tokens limit from error message
            if detect_max_tokens and resp.status_code == 400:
                try:
                    error_data = resp.json()
                    error_msg = str(error_data.get("error", {})).lower()
                    if "max_tokens" in error_msg or "maxoutputtokens" in error_msg:
                        # Try to extract the limit from error message
                        import re
                        # Look for patterns like "valid range is [1, 8192]" or "max is 8192"
                        # Priority: match range upper bound [1, 8192] first, then standalone numbers
                        # Avoid matching the lower bound (1) in ranges
                        match = re.search(r'\[.*?,\s*(\d+)\]|max.*?(\d+)|limit.*?(\d+)', error_msg)
                        if match:
                            # Prefer group 1 (upper bound in range), then group 2, then group 3
                            limit_str = match.group(1) or match.group(2) or match.group(3)
                            if limit_str:
                                limit = int(limit_str)
                                # Validate: reject suspiciously low values (< 1024)
                                if limit < 1024:
                                    logger.warning(LogModule.AUTH, f"[TEST_AI_PLATFORM] Extracted suspiciously low max_tokens limit: {limit}, ignoring")
                                else:
                                    result["max_tokens"] = limit
                                    logger.info(LogModule.AUTH,f"[TEST_AI_PLATFORM] Extracted max_tokens limit from error: {limit}")
                except Exception:
                    pass
            
            err_msg = _format_test_error(resp.status_code, error_text)
            return {
                "success": False,
                "error": err_msg,
                "message": err_msg,
            }

    except httpx.TimeoutException as e:
        err = (
            f"LLM endpoint timeout ({base_url!r}, {platform_type}): {e!s}. "
            "Check network latency and the API URL in translator settings."
        )
        logger.warning(
            LogModule.AUTH,
            f"[TEST_AI_PLATFORM] Timeout url={base_url!r} platform={platform_type}: {e}",
        )
        return {"success": False, "error": err, "message": err}
    except httpx.ConnectError as e:
        err = (
            f"Cannot connect to LLM endpoint {base_url!r} ({platform_type}): {e!s}. "
            "This is not an Owlangs HTTP route failure — start Ollama or your LLM service, "
            "or correct base_url/model in settings."
        )
        logger.warning(
            LogModule.AUTH,
            f"[TEST_AI_PLATFORM] ConnectError url={base_url!r} platform={platform_type}: {e}",
        )
        return {"success": False, "error": err, "message": err}
    except Exception as e:
        err = f"Test failed: {e}"
        logger.info(LogModule.AUTH, f"[TEST_AI_PLATFORM] {platform_type} exception: {e}")
        return {"success": False, "error": err, "message": err}


async def list_platform_models(
    platform_type: str,
    base_url: str,
    api_key: str,
    api_protocol: Optional[str] = None,
    requires_api_key: bool = True,
) -> list[str]:
    """
    List available models for an AI platform.

    ``api_protocol`` (e.g. ``openai``, ``anthropic``) comes from the request body or
    unified ``ai_platforms`` config. Generic ``platform_type`` values such as ``llm``
    rely on ``api_protocol`` to choose listing behavior.

    Returns:
        List of model IDs/names
    """
    platform = (platform_type or '').lower()
    proto = (api_protocol or '').lower()

    try:
        async with httpx.AsyncClient(timeout=30.0, proxy=None, mounts={'http://': None, 'https://': None}) as client:
            headers = {
                "Content-Type": "application/json",
            }
            
            # Ollama: use /api/tags without Authorization header
            if platform == 'ollama':
                tags_url = f"{base_url.rstrip('/')}/api/tags"
                logger.info(LogModule.AUTH, f"[LIST_MODELS DEBUG] Requesting Ollama models from: {tags_url}")
                print(f"[LIST_MODELS DEBUG] Requesting Ollama models from: {tags_url}")
                resp = await client.get(tags_url, headers=headers)
                logger.info(LogModule.AUTH, f"[LIST_MODELS DEBUG] Ollama response status: {resp.status_code}")
                print(f"[LIST_MODELS DEBUG] Ollama response status: {resp.status_code}")
                if resp.status_code == 200:
                    models_data = resp.json()
                    models: list[str] = []
                    if isinstance(models_data, dict) and "models" in models_data:
                        for model in models_data["models"]:
                            if isinstance(model, dict):
                                name = model.get("name")
                                if name:
                                    models.append(name)
                    logger.info(LogModule.AUTH, f"[LIST_MODELS] Found {len(models)} Ollama models")
                    return sorted(models)
                logger.warning(LogModule.AUTH, f"[LIST_MODELS] Ollama /api/tags failed: HTTP {resp.status_code}")
                return []
            else:
                # Zhipu Anthropic-compatible gateway: no OpenAI-shaped GET /models; avoid bogus "HTTP 200" failure.
                if _is_zhipu_bigmodel_anthropic_endpoint(base_url):
                    models = list(_ZHIPU_GLM_ANTHROPIC_COMPAT_MODELS)
                    logger.info(
                        LogModule.AUTH,
                        f"[LIST_MODELS] Zhipu Anthropic-compatible URL: returning static GLM list ({len(models)} models)",
                    )
                    return sorted(models)

                # Official Anthropic host (platform key may be generic e.g. "llm" if api_protocol is anthropic)
                if (
                    proto == "anthropic" or _is_anthropic_family_platform(platform_type)
                ) and "api.anthropic.com" in (base_url or "").lower():
                    models = list(_ANTHROPIC_OFFICIAL_STATIC_MODELS)
                    logger.info(
                        LogModule.AUTH,
                        f"[LIST_MODELS] Anthropic official host: returning static model list ({len(models)} models)",
                    )
                    return sorted(models)

                # Anthropic protocol (e.g. platform_type=llm, api_protocol=anthropic): try GET /models once, then static Claude IDs
                if proto == "anthropic":
                    models_url = f"{base_url.rstrip('/')}/models"
                    if requires_api_key and api_key and api_key.strip():
                        headers["Authorization"] = f"Bearer {api_key}"
                    resp = await client.get(models_url, headers=headers)
                    if resp.status_code == 200:
                        parsed = _parse_models_from_openai_list_json(resp.json())
                        if parsed:
                            logger.info(
                                LogModule.AUTH,
                                f"[LIST_MODELS] api_protocol=anthropic: parsed {len(parsed)} models from GET /models",
                            )
                            return sorted(parsed)
                    logger.info(
                        LogModule.AUTH,
                        "[LIST_MODELS] api_protocol=anthropic: no OpenAI-shaped model list; using static Claude model IDs",
                    )
                    return sorted(_ANTHROPIC_OFFICIAL_STATIC_MODELS)

                # OpenAI-compatible /v1/models or /models endpoint
                models_url = f"{base_url.rstrip('/')}/models"
                if requires_api_key and api_key and api_key.strip():
                    headers["Authorization"] = f"Bearer {api_key}"
                resp = await client.get(models_url, headers=headers)
            
            if resp.status_code == 200:
                models_data = resp.json()
                parsed = _parse_models_from_openai_list_json(models_data)
                if parsed:
                    logger.info(LogModule.AUTH,f"[LIST_MODELS] Found {len(parsed)} models for platform '{platform_type}'")
                    return sorted(parsed)
                # HTTP 200 but JSON is not an OpenAI model list (e.g. provider error envelope or HTML)
                if _is_zhipu_bigmodel_anthropic_endpoint(base_url):
                    models = list(_ZHIPU_GLM_ANTHROPIC_COMPAT_MODELS)
                    logger.info(
                        LogModule.AUTH,
                        f"[LIST_MODELS] GET /models returned non-OpenAI shape; using Zhipu GLM static list ({len(models)} models)",
                    )
                    return sorted(models)
                if proto == "anthropic" or _is_anthropic_family_platform(platform_type):
                    models = list(_ANTHROPIC_OFFICIAL_STATIC_MODELS)
                    logger.info(
                        LogModule.AUTH,
                        f"[LIST_MODELS] GET /models returned non-OpenAI shape; using Anthropic static list ({len(models)} models)",
                    )
                    return sorted(models)
            
            # If OpenAI-compatible endpoint failed, try platform-specific endpoints
            if proto == "anthropic" or _is_anthropic_family_platform(platform_type):
                # Anthropic family often has no public models list compatible with GET /models
                return sorted(_ANTHROPIC_OFFICIAL_STATIC_MODELS)
            elif platform == 'google':
                # Google doesn't have a public models list endpoint
                # Return common models
                return ["gemini-pro", "gemini-pro-vision", "gemini-1.5-pro", "gemini-1.5-flash"]
            
            # If request failed, return empty list
            logger.warning(LogModule.AUTH, f"[LIST_MODELS] Failed to list models for platform '{platform_type}': HTTP {resp.status_code}")
            return []
    
    except httpx.TimeoutException as e:
        logger.warning(LogModule.AUTH, f"[LIST_MODELS] Timeout while listing models for platform '{platform_type}'")
        raise Exception(f"Connection timeout: {e}")
    except httpx.ConnectError as e:
        logger.warning(LogModule.AUTH, f"[LIST_MODELS] Connection failed while listing models for platform '{platform_type}'")
        raise Exception(f"Connection failed: {e}")
    except Exception as e:
        logger.error(LogModule.AUTH, f"[LIST_MODELS] Failed to list models for platform '{platform_type}': {e}", exc_info=True)
        raise Exception(f"{e}")



