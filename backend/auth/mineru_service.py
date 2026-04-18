"""
MinerU connectivity testing service.
Supports both Cloud (mineru.net) and Local (v3.1+) deployments.
"""

from typing import Dict, Any, Optional
import httpx

from backend.config.config_loader import get_unified_config


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

# Model version to backend mapping
MODEL_TO_BACKEND = {
    "pipeline": "pipeline",
    "vlm": "vlm-auto-engine",
    "hybrid": "hybrid-auto-engine",
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
    
    if not base_url:
        return {"success": False, "message": f"No base URL configured for {platform_key}"}
    
    base_url = base_url.rstrip('/')
    
    # Detect backend type: prefer parser_subtype, fallback to URL detection
    is_cloud = parser_subtype == "cloud" or base_url.startswith('https://mineru.net')
    
    if is_cloud:
        return await _test_cloud_connectivity(base_url, mineru_token)
    else:
        return await _test_local_connectivity(base_url, mineru_token, platform_key)


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
                    # Note: user_left_quota=0 doesn't necessarily mean no quota,
                    # it's just what the API returns
                    left_quota = quota_data.get('data', {}).get('user_left_quota', 'unknown')
                    return {
                        "success": True, 
                        "message": f"Cloud MinerU connection successful (quota: {left_quota})",
                        "quota": quota_data.get('data')
                    }
            
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
        # First try /health endpoint (new in v3.1+)
        try:
            health_url = f"{base_url}/health"
            response = await client.get(health_url, headers=headers)
            
            if response.status_code == 200:
                return {
                    "success": True,
                    "message": f"Local MinerU server is running at {base_url}",
                    "status_code": 200,
                    "endpoint": "/health"
                }
        except httpx.RequestError:
            pass  # Fall back to other endpoints
        
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
                    return {
                        "success": True, 
                        "message": f"Local MinerU server is running at {base_url}",
                        "status_code": 405,
                        "endpoint": test_url,
                        "detail": "Server responded with 405 Method Not Allowed (expected for GET on POST endpoints)"
                    }
                
                if response.status_code == 422:
                    return {
                        "success": True,
                        "message": f"Local MinerU server is running at {base_url}",
                        "status_code": 422,
                        "endpoint": test_url
                    }
                
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
                    return {
                        "success": True,
                        "message": f"Local MinerU server is running at {base_url}",
                        "status_code": 422,
                        "endpoint": test_url,
                        "detail": "Server accepted POST request (422 = missing required fields, which is expected)"
                    }
                    
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
    """Convert model version to local MinerU backend type."""
    return MODEL_TO_BACKEND.get(model_version, "hybrid-auto-engine")


# Keep legacy function for backward compatibility
async def test_mineru_local_connectivity_legacy(base_url: str, api_key: Optional[str] = None) -> Dict[str, Any]:
    """Legacy local MinerU test - kept for backward compatibility."""
    return await _test_local_connectivity(base_url, api_key, "mineru_local")


# Alias for new imports
test_mineru_local_connectivity = test_mineru_local_connectivity_legacy
