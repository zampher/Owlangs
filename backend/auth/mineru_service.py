"""
MinerU connectivity testing service.
Supports both Cloud (mineru.net) and Local (v3.1+) deployments.
"""

from typing import Dict, Any, Optional
import httpx

from backend.auth.mineru_test_utils import (
    build_health_probe_urls,
    enrich_mineru_test_result,
    extract_version_from_health_payload,
    extract_version_from_payload,
    infer_cloud_api_version,
)

from backend.config.config_loader import get_unified_config
from backend.logger import unified_logger as logger
from backend.logger.logger import LogModule


# Language code mapping for local MinerU
LOCAL_MINERU_LANG_MAP = {
    "zh": "ch",
    "zh-cn": "ch",
    "zh-hans": "ch",
    "zh-hk": "chinese_cht",
    "zh-tw": "chinese_cht",
    "zh-hant": "chinese_cht",
    "en": "en",
    "en-us": "en",
    "en-gb": "en",
    "ja": "japan",
    "jp": "japan",
    "ko": "korean",
    "kr": "korean",
    "el": "el",
    "ar": "arabic",
    "hi": "devanagari",
    "auto": "ch",  # Default to Chinese for auto
}

# Model version migration map (old short names -> official names)
MIGRATION_MAP = {
    "vlm": "vlm-auto-engine",
    "hybrid": "hybrid-auto-engine",
}

# Model version to backend mapping
MODEL_TO_BACKEND = {
    "pipeline": "pipeline",
    "vlm-auto-engine": "vlm-auto-engine",
    "hybrid-auto-engine": "hybrid-auto-engine",
    "vlm-http-client": "vlm-http-client",
    "hybrid-http-client": "hybrid-http-client",
}


async def test_mineru_connectivity(
    mineru_token: Optional[str] = None, 
    base_url: Optional[str] = None,
    platform_key: str = "mineru"
) -> Dict[str, Any]:
    """
    Test MinerU connectivity using appropriate backend detection.
    
    Args:
        mineru_token: API token (optional for local deployments)
        base_url: Base URL for MinerU API (if None, uses platform config)
        platform_key: Platform key ('mineru' or 'mineru_local')
    
    Returns:
        Dict with 'success': bool and 'message': str
    """
    # Get config from platform config if not provided
    parser_subtype = None
    model_version = None
    if not base_url:
        config = get_unified_config()
        platform_config = config.ai_platforms.get(platform_key)
        if platform_config:
            if hasattr(platform_config, 'url'):
                base_url = platform_config.url
            else:
                base_url = platform_config.get('url')
            if hasattr(platform_config, 'parser_subtype'):
                parser_subtype = platform_config.parser_subtype
            else:
                parser_subtype = platform_config.get('parser_subtype')
            if hasattr(platform_config, 'model'):
                model_version = platform_config.model
            else:
                model_version = platform_config.get('model')

    if not base_url:
        return {"success": False, "message": f"No base URL configured for {platform_key}"}

    base_url = base_url.rstrip('/')

    # Detect backend type: platform_key and parser_subtype take priority over URL heuristics.
    is_cloud = platform_key == "mineru" or (
        parser_subtype == "cloud" and platform_key != "mineru_local"
    ) or (
        platform_key != "mineru_local"
        and base_url.startswith("https://mineru.net")
    )

    logger.info(
        LogModule.AUTH,
        f"[MINERU_TEST] platform={platform_key}, base_url={base_url}, "
        f"model={model_version or 'unknown'}, parser_subtype={parser_subtype or 'detected'}, "
        f"is_cloud={is_cloud}"
    )

    if is_cloud:
        result = await _test_cloud_connectivity(base_url, mineru_token)
        if not result.get("mineru_version"):
            probed = await _probe_mineru_version(base_url, mineru_token)
            if probed:
                result["mineru_version"] = probed
        return enrich_mineru_test_result(
            result,
            api_version=infer_cloud_api_version(base_url),
            model_version=model_version,
        )
    result = await _test_local_connectivity(base_url, mineru_token, platform_key)
    if result.get("success") and not result.get("mineru_version"):
        probed = await _probe_mineru_version(base_url, mineru_token)
        if probed:
            result["mineru_version"] = probed
    return enrich_mineru_test_result(result, model_version=model_version)


async def _probe_mineru_version(
    base_url: str,
    api_key: Optional[str] = None,
) -> Optional[str]:
    """Best-effort MinerU software version lookup via /health on likely base URLs."""
    headers: Dict[str, str] = {}
    if api_key and api_key.strip():
        headers["Authorization"] = f"Bearer {api_key.strip()}"

    async with httpx.AsyncClient(
        timeout=10.0,
        verify=False,
        proxy=None,
        mounts={"http://": None, "https://": None},
    ) as client:
        for health_url in build_health_probe_urls(base_url):
            try:
                response = await client.get(health_url, headers=headers)
            except httpx.RequestError:
                continue
            if response.status_code != 200:
                continue
            header_version = (
                response.headers.get("x-mineru-version")
                or response.headers.get("X-MinerU-Version")
            )
            if isinstance(header_version, str) and header_version.strip():
                return header_version.strip()
            try:
                payload = response.json()
            except Exception:
                payload = None
            version = extract_version_from_health_payload(payload)
            if version:
                logger.info(
                    LogModule.AUTH,
                    f"[MINERU_TEST] Resolved MinerU version={version} from {health_url}",
                )
                return version
    return None


def _attach_version_to_result(result: Dict[str, Any], version: Optional[str]) -> Dict[str, Any]:
    if not version or not result.get("success"):
        return result
    result["mineru_version"] = version
    message = result.get("message")
    if isinstance(message, str) and version not in message:
        result["message"] = f"{message} (version: {version})"
    return result


async def _test_cloud_connectivity(base_url: str, mineru_token: Optional[str]) -> Dict[str, Any]:
    """
    Test Cloud MinerU connectivity without consuming quota.
    
    Strategy:
    1. Try GET /api/v4/quota (quota query endpoint) - no quota consumption, verifies API key
    2. Fallback: Try GET /extract/task (should return 405) - verifies service is running
    3. Fallback: POST with invalid payload to get 400/422 - verifies API key without task creation
    """
    if not mineru_token:
        return {"success": False, "message": "Cloud MinerU requires an API key"}
    
    headers = {
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {mineru_token}',
    }

    async with httpx.AsyncClient(timeout=15.0, verify=False, proxy=None, mounts={'http://': None, 'https://': None}) as client:
        # Method 1: Try quota endpoint (GET /api/v4/quota) - no quota consumption
        try:
            quota_url = f"{base_url}/quota"
            quota_resp = await client.get(quota_url, headers=headers, timeout=10.0)
            
            if quota_resp.status_code == 200:
                quota_data = quota_resp.json()
                if quota_data.get('code') == 0:
                    # Quota query successful - connection is working
                    left_quota = quota_data.get('data', {}).get('user_left_quota', 'unknown')
                    version = extract_version_from_payload(quota_data)
                    result: Dict[str, Any] = {
                        "success": True,
                        "message": f"Cloud MinerU connection successful (quota: {left_quota})",
                        "quota": quota_data.get('data'),
                    }
                    return _attach_version_to_result(result, version)
            
            # Quota endpoint returned error but connection is working
            if quota_resp.status_code in (401, 403):
                # API Key invalid
                err_msg = 'MinerU API Key invalid or expired'
                try:
                    j = quota_resp.json()
                    msg_code = j.get('msgCode') or ''
                    if msg_code == 'A0211':
                        err_msg = 'MinerU API Key expired'
                    elif msg_code == 'A0202':
                        err_msg = 'MinerU API Key incorrect'
                except Exception:
                    pass
                return {"success": False, "message": err_msg}
                
        except httpx.RequestError:
            pass  # Fall through to next method
        except Exception:
            pass  # Fall through to next method
        
        # Method 2: Try GET to POST endpoint (should return 405 Method Not Allowed)
        # This verifies the service is running and API key format is valid
        try:
            task_url = f"{base_url}/extract/task"
            get_resp = await client.get(task_url, headers=headers, timeout=10.0)
            
            # 405 means the endpoint exists but requires POST - service is running
            if get_resp.status_code == 405:
                return {
                    "success": True, 
                    "message": "Cloud MinerU connection successful (service running)",
                    "detail": "GET request returned 405 Method Not Allowed (expected for POST-only endpoint)"
                }
            
            # 401/403 means API key is invalid
            if get_resp.status_code in (401, 403):
                err_msg = 'MinerU API Key invalid or expired'
                try:
                    j = get_resp.json()
                    msg_code = j.get('msgCode') or ''
                    if msg_code == 'A0211':
                        err_msg = 'MinerU API Key expired'
                    elif msg_code == 'A0202':
                        err_msg = 'MinerU API Key incorrect'
                except Exception:
                    pass
                return {"success": False, "message": err_msg}
                
        except httpx.RequestError:
            pass  # Fall through to next method
        except Exception:
            pass  # Fall through to next method
        
        # Method 3: POST with minimal/empty payload to get validation error
        # This should return 400/422 without creating a task (no quota consumption)
        try:
            task_url = f"{base_url}/extract/task"
            # Send empty payload - should fail validation without consuming quota
            empty_resp = await client.post(task_url, headers=headers, json={}, timeout=10.0)
            
            # 400/422 means the request reached the service and was validated
            # This confirms API key is valid (would get 401 if invalid)
            if empty_resp.status_code in (400, 422):
                return {
                    "success": True, 
                    "message": "Cloud MinerU connection successful",
                    "detail": f"Empty payload returned {empty_resp.status_code} (validation error, no quota consumed)"
                }
            
            if empty_resp.status_code == 401:
                err_msg = 'MinerU API Key invalid or expired'
                try:
                    j = empty_resp.json()
                    msg_code = j.get('msgCode') or ''
                    if msg_code == 'A0211':
                        err_msg = 'MinerU API Key expired'
                    elif msg_code == 'A0202':
                        err_msg = 'MinerU API Key incorrect'
                except Exception:
                    pass
                return {"success": False, "message": err_msg}
                
        except httpx.RequestError as req_err:
            return {"success": False, "message": f"Request failed: {str(req_err)}"}
        except Exception as e:
            return {"success": False, "message": f"Test failed: {str(e)}"}
        
        return {"success": False, "message": "All connection test methods failed"}


async def _test_local_connectivity(
    base_url: str, 
    api_key: Optional[str],
    platform_key: str
) -> Dict[str, Any]:
    """
    Test Local MinerU (v3.1+) connectivity.
    Uses /health endpoint if available, falls back to other endpoints.
    """
    headers = {}
    if api_key and api_key.strip():
        headers['Authorization'] = f'Bearer {api_key.strip()}'

    async with httpx.AsyncClient(timeout=15.0, verify=False, proxy=None, mounts={'http://': None, 'https://': None}) as client:
        # First try /health endpoint (new in v3.1+) on all likely URLs
        for health_url in build_health_probe_urls(base_url):
            try:
                response = await client.get(health_url, headers=headers)
                if response.status_code != 200:
                    continue
                try:
                    health_payload = response.json()
                except Exception:
                    health_payload = None
                version = extract_version_from_health_payload(health_payload)
                result = {
                    "success": True,
                    "message": f"Local MinerU server is running at {base_url}",
                    "status_code": 200,
                    "endpoint": health_url.replace(base_url.rstrip('/'), '').lstrip('/') or "/health",
                }
                return _attach_version_to_result(result, version)
            except httpx.RequestError:
                continue
        
        # Try main API endpoints
        endpoints_to_try = [
            (f"{base_url}/file_parse", "sync"),
            (f"{base_url}/tasks", "async"),
        ]
        
        for test_url, endpoint_type in endpoints_to_try:
            try:
                # Try GET request - should return 405 Method Not Allowed if server is running
                response = await client.get(test_url, headers=headers)
                
                if response.status_code == 405:
                    result = {
                        "success": True, 
                        "message": f"Local MinerU server is running at {base_url}",
                        "status_code": 405,
                        "endpoint": test_url,
                        "detail": "Server responded with 405 Method Not Allowed (expected for GET on POST endpoints)"
                    }
                    version = await _probe_mineru_version(base_url, api_key)
                    return _attach_version_to_result(result, version)
                
                if response.status_code == 422:
                    result = {
                        "success": True,
                        "message": f"Local MinerU server is running at {base_url}",
                        "status_code": 422,
                        "endpoint": test_url
                    }
                    version = await _probe_mineru_version(base_url, api_key)
                    return _attach_version_to_result(result, version)
                
                if response.status_code == 401:
                    return {"success": False, "message": "MinerU API Key invalid or expired"}
                
                if response.status_code in (502, 503, 504):
                    return {
                        "success": False, 
                        "message": f"Server returned {response.status_code}. The MinerU backend service may not be running properly.",
                    }
                
            except httpx.RequestError:
                continue
        
        # Try POST with minimal body
        for test_url, endpoint_type in endpoints_to_try:
            try:
                response = await client.post(test_url, headers=headers, content=b"")
                
                if response.status_code == 422:
                    result = {
                        "success": True,
                        "message": f"Local MinerU server is running at {base_url}",
                        "status_code": 422,
                        "endpoint": test_url,
                        "detail": "Server accepted POST request (422 = missing required fields, which is expected)"
                    }
                    version = await _probe_mineru_version(base_url, api_key)
                    return _attach_version_to_result(result, version)
                    
            except httpx.RequestError:
                continue
        
        return {
            "success": False, 
            "message": f"Cannot connect to local MinerU at {base_url}",
            "detail": "Server did not respond with expected status codes (200, 405 or 422)."
        }


def get_local_mineru_language(ocr_language: str) -> str:
    """Convert generic language code to local MinerU format."""
    lang = (ocr_language or "").strip().lower()
    return LOCAL_MINERU_LANG_MAP.get(lang, "ch")  # Default to Chinese


def get_local_mineru_backend(model_version: str) -> str:
    """Convert model version to local MinerU backend type, with migration for old names."""
    mv = model_version
    if mv in MIGRATION_MAP:
        mv = MIGRATION_MAP[mv]
    return MODEL_TO_BACKEND.get(mv, "hybrid-auto-engine")


# Keep legacy function for backward compatibility
async def test_mineru_local_connectivity_legacy(base_url: str, api_key: Optional[str] = None) -> Dict[str, Any]:
    """Legacy local MinerU test - kept for backward compatibility."""
    return await _test_local_connectivity(base_url, api_key, "mineru_local")


# Alias for new imports
test_mineru_local_connectivity = test_mineru_local_connectivity_legacy
