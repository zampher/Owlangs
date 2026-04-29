# SPDX-FileCopyrightText: 2026 Zampherss
# SPDX-License-Identifier: MPL-2.0

"""
MinerU Converter - Supports both Cloud and Local deployments.

Architecture:
    - MinerUBackend: Abstract base class defining the interface
    - MinerUCloudBackend: Cloud API implementation (mineru.net)
    - MinerULocalBackend: Local API implementation (v3.1+)
    - BackendFactory: Factory to create appropriate backend based on config

API Differences:
    Cloud (mineru.net):
        - POST /file-urls/batch - Request pre-signed upload URLs
        - PUT <pre-signed-url> - Upload file directly
        - GET /extract-results/batch/{batch_id} - Poll for results
        - Returns: ZIP file URL
        - Fields: enable_formula, enable_table, language, model_version

    Local (v3.1+):
        - POST /file_parse - Synchronous file parsing (multipart/form-data)
        - POST /tasks - Asynchronous task submission (multipart/form-data)
        - GET /tasks/{task_id} - Get task status
        - GET /tasks/{task_id}/result - Get task result
        - Returns: Direct ZIP file content or JSON
        - Fields: formula_enable, table_enable, lang_list[], backend, response_format_zip
"""

import asyncio
import time
import zipfile
import io
import re
import json
import os
import glob
import tempfile
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Hashable, Literal, Optional, Dict, Any, Tuple, List, Callable
from pathlib import Path

import httpx

from logger import unified_logger as logger
from logger.logger import LogModule


def _translate_error_message(error_msg: str) -> str:
    """Translate common Chinese error messages to English for i18n support."""
    translations = {
        r'\[WinError\s+\d+\]\s*由于连接方在一段时间后没有正确答复或连接的主机没有反应，连接尝试失败。':
        '[WinError] Connection attempt failed because the connected party did not properly respond.',
        r'由于连接方在一段时间后没有正确答复或连接的主机没有反应，连接尝试失败。':
        'Connection attempt failed because the connected party did not properly respond.',
        r'连接尝试失败': 'Connection attempt failed',
    }
    
    if any('\u4e00' <= char <= '\u9fff' for char in error_msg):
        for pattern, replacement in translations.items():
            error_msg = re.sub(pattern, replacement, error_msg, flags=re.IGNORECASE)
        
        if any('\u4e00' <= char <= '\u9fff' for char in error_msg):
            winerror_match = re.search(r'\[WinError\s+(\d+)\]', error_msg)
            if winerror_match:
                error_code = winerror_match.group(1)
                return f'[WinError {error_code}] Connection failed. Please check your network connection.'
            else:
                return 'Network connection error. Please check your network connection.'
    
    return error_msg


from converter.x2md.base import X2MarkdownConverter, X2MarkdownConverterConfig
from ir.attachment_manager import AttachMent
from ir.document import Document
from ir.markdown_document import MarkdownDocument
from utils.markdown_utils import embed_inline_image_from_zip
from layout.base import LayoutDocument
from layout.registry import load_layout_from_engine_zip


# Default cloud API base
MINERU_CLOUD_BASE = 'https://mineru.net/api/v4'

# Returned by MinerULocalBackend.upload* when /file_parse returns ZIP bytes; payload is stored
# on the backend instance (avoids hex-encoding the entire ZIP into task_id, which doubled RAM use).
_LOCAL_MINERU_SYNC_TASK_ID = "__LOCAL_MINERU_SYNC__"


# Language code mapping for local MinerU
LOCAL_MINERU_LANG_MAP = {
    "zh": "ch", "zh-cn": "ch", "zh-hans": "ch",
    "zh-hk": "chinese_cht", "zh-tw": "chinese_cht", "zh-hant": "chinese_cht",
    "en": "en", "en-us": "en", "en-gb": "en",
    "ja": "japan", "jp": "japan",
    "ko": "korean", "kr": "korean",
    "el": "el", "el-gr": "el",
    "ar": "arabic", "ar-sa": "arabic",
    "hi": "devanagari", "hi-in": "devanagari",
    "auto": "ch",
}


# Model version to backend mapping for local MinerU
MODEL_TO_BACKEND = {
    "pipeline": "pipeline",
    "vlm": "vlm-auto-engine",
    "hybrid": "hybrid-auto-engine",
}


@dataclass(kw_only=True)
class ConverterMineruConfig(X2MarkdownConverterConfig):
    """Configuration for MinerU converter."""
    mineru_token: str
    formula_ocr: bool = True
    table_ocr: bool = True
    model_version: Literal["pipeline", "vlm", "hybrid"] = "vlm"
    ocr_language: Optional[str] = "auto"
    base_url: Optional[str] = None
    # API endpoint configuration (from platforms.json)
    api_endpoints: Optional[Dict[str, str]] = None
    # PDF split configuration (for large PDFs exceeding MinerU limits)
    pdf_split_enabled: bool = True
    pdf_split_max_pages: int = 100
    pdf_split_max_workers: int = 2  # Max concurrent workers for split PDF conversion
    request_retry_count: int = 2  # Number of retries for MinerU API requests

    def gethash(self) -> Hashable:
        return (
            self.formula_ocr, 
            self.table_ocr,
            self.model_version, 
            (self.ocr_language or "auto"), 
            self.base_url or MINERU_CLOUD_BASE,
            self.pdf_split_enabled,
            self.pdf_split_max_pages,
            self.pdf_split_max_workers,
        )


# HTTP Client Configuration
# Increased connect timeout for large-file SSL handshakes on slow networks.
# Increased pool timeout to avoid exhaustion during frequent polling.
timeout = httpx.Timeout(connect=60.0, read=300.0, write=300.0, pool=30.0)

import ssl
ssl_context = ssl.create_default_context()
ssl_context.check_hostname = False
ssl_context.verify_mode = ssl.CERT_NONE

limits = httpx.Limits(max_connections=50, max_keepalive_connections=20)
# Disable proxy completely for LAN connections (trust_env=False to prevent reading system proxy)
client = httpx.Client(limits=limits, trust_env=False, timeout=timeout, verify=False, proxy=None, mounts={'http://': None, 'https://': None})
client_async = httpx.AsyncClient(limits=limits, trust_env=False, timeout=timeout, verify=False, proxy=None, mounts={'http://': None, 'https://': None})

import atexit
def cleanup_clients():
    try:
        client.close()
    except Exception:
        pass
    try:
        import asyncio
        loop = asyncio.get_event_loop()
        if loop.is_running():
            asyncio.create_task(client_async.aclose())
        else:
            loop.run_until_complete(client_async.aclose())
    except Exception:
        pass

atexit.register(cleanup_clients)


class MinerUBackend(ABC):
    """Abstract base class for MinerU API backends."""
    
    def __init__(
        self,
        base_url: str,
        mineru_token: str,
        formula_ocr: bool = True,
        table_ocr: bool = True,
        model_version: str = "vlm",
        ocr_language: str = "auto",
        api_endpoints: Optional[Dict[str, str]] = None,
        retry_count: int = 2,
    ):
        self.base_url = base_url.rstrip('/')
        self.mineru_token = (mineru_token or "").strip()
        self.formula = formula_ocr
        self.table = table_ocr
        self.model_version = model_version
        self.ocr_language = ocr_language or "auto"
        self.api_endpoints = api_endpoints or {}
        self.retry_count = max(0, int(retry_count))
    
    def _get_auth_header(self) -> Dict[str, str]:
        """Get authorization header if token is available."""
        if self.mineru_token:
            return {"Authorization": f"Bearer {self.mineru_token}"}
        return {}
    
    @abstractmethod
    def upload(self, document: Document) -> str:
        """Upload document and return task/batch ID."""
        pass
    
    @abstractmethod
    async def upload_async(self, document: Document) -> str:
        """Async upload document and return task/batch ID."""
        pass
    
    @abstractmethod
    def get_result(self, task_id: str) -> Tuple[str, bytes]:
        """Get parsing result. Returns (markdown_content, zip_bytes)."""
        pass
    
    @abstractmethod
    async def get_result_async(self, task_id: str) -> Tuple[str, bytes]:
        """Async get parsing result. Returns (markdown_content, zip_bytes)."""
        pass
    
    @abstractmethod
    def test_connection(self) -> Dict[str, Any]:
        """Test backend connectivity."""
        pass


class MinerUCloudBackend(MinerUBackend):
    """
    Cloud MinerU backend (mineru.net).
    Uses URL-based async workflow with pre-signed URLs.
    """
    
    API_VERSION = "cloud-v4"
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Validate required token for cloud
        if not self.mineru_token:
            raise ValueError("MinerU Cloud API requires an API key. Please configure in Settings -> AI Platform -> MinerU.")
    
    def _get_upload_url_endpoint(self) -> str:
        endpoint = self.api_endpoints.get('upload', '/file-urls/batch')
        return f"{self.base_url}{endpoint}"
    
    def _get_result_endpoint(self, batch_id: str) -> str:
        endpoint = self.api_endpoints.get('result', '/extract-results/batch/{batch_id}')
        return f"{self.base_url}{endpoint.format(batch_id=batch_id)}"
    
    def _build_upload_payload(self, document: Document) -> Dict:
        """Build upload request payload for cloud API."""
        model_version = self.model_version
        if model_version == "hybrid":
            logger.warning(
                LogModule.CONVERT,
                "[MINERU] model_version 'hybrid' is not supported by MinerU cloud, falling back to 'vlm'."
            )
            model_version = "vlm"
        
        # Map language codes
        lang = (self.ocr_language or "").strip().lower()
        mineru_lang_map = {
            "zh": "ch", "zh-cn": "ch", "zh-hans": "ch",
            "zh-hk": "chinese_cht", "zh-tw": "chinese_cht", "zh-hant": "chinese_cht",
            "en": "en", "en-us": "en", "en-gb": "en",
            "ja": "japan", "jp": "japan",
            "ko": "korean", "kr": "korean",
            "el": "el", "el-gr": "el",
            "ar": "arabic", "ar-sa": "arabic",
            "hi": "devanagari", "hi-in": "devanagari",
            "auto": "auto",
        }
        language = mineru_lang_map.get(lang, "auto")
        
        return {
            "enable_formula": self.formula,
            "language": language,
            "enable_table": self.table,
            "model_version": model_version,
            "files": [{"name": document.name, "is_ocr": True}]
        }
    
    def _make_request_with_retry(self, method: str, url: str, **kwargs) -> httpx.Response:
        """Make HTTP request with retry logic."""
        headers = kwargs.pop('headers', {})
        headers['Content-Type'] = 'application/json'
        headers.update(self._get_auth_header())
        
        max_attempts = self.retry_count + 1
        for attempt in range(1, max_attempts + 1):
            try:
                with httpx.Client(trust_env=False, timeout=timeout, verify=False, limits=limits, proxy=None, mounts={'http://': None, 'https://': None}) as client:
                    response = client.request(method, url, headers=headers, **kwargs)
                    response.raise_for_status()
                    return response
            except (httpx.ConnectError, httpx.ReadTimeout, httpx.WriteTimeout, ssl.SSLError) as e:
                if attempt < max_attempts:
                    wait_s = 2 ** attempt
                    logger.warning(LogModule.CONVERT, f"[MINERU] Request failed (attempt {attempt}), retrying in {wait_s}s: {e}")
                    time.sleep(wait_s)
                else:
                    raise
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 401:
                    raise ValueError(
                        "MinerU API authentication failed (401). "
                        "Please check your API key in Settings -> AI Platform -> MinerU."
                    )
                raise
    
    async def _make_request_with_retry_async(self, method: str, url: str, **kwargs) -> httpx.Response:
        """Async make HTTP request with retry logic."""
        headers = kwargs.pop('headers', {})
        headers['Content-Type'] = 'application/json'
        headers.update(self._get_auth_header())
        
        max_attempts = self.retry_count + 1
        for attempt in range(1, max_attempts + 1):
            try:
                async with httpx.AsyncClient(trust_env=False, timeout=timeout, verify=False, limits=limits, proxy=None, mounts={'http://': None, 'https://': None}) as client:
                    response = await client.request(method, url, headers=headers, **kwargs)
                    response.raise_for_status()
                    return response
            except (httpx.ConnectError, httpx.ReadTimeout, httpx.WriteTimeout, ssl.SSLError) as e:
                if attempt < max_attempts:
                    wait_s = 2 ** attempt
                    logger.warning(LogModule.CONVERT, f"[MINERU] Request failed (attempt {attempt}), retrying in {wait_s}s: {e}")
                    await asyncio.sleep(wait_s)
                else:
                    raise
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 401:
                    raise ValueError(
                        "MinerU API authentication failed (401). "
                        "Please check your API key in Settings -> AI Platform -> MinerU."
                    )
                raise
    
    def upload(self, document: Document) -> str:
        """Upload document to cloud MinerU."""
        url = self._get_upload_url_endpoint()
        payload = self._build_upload_payload(document)
        
        response = self._make_request_with_retry('POST', url, json=payload)
        result = response.json()
        
        if result.get("code") != 0:
            raise Exception(f"Failed to get upload URL: {result.get('msg', 'Unknown error')}")
        
        batch_id = result["data"]["batch_id"]
        upload_url = result["data"]["file_urls"][0]
        
        # Upload file directly to pre-signed URL
        max_attempts = self.retry_count + 1
        for attempt in range(1, max_attempts + 1):
            try:
                with httpx.Client(trust_env=False, timeout=timeout, verify=False, limits=limits, proxy=None, mounts={'http://': None, 'https://': None}) as client:
                    upload_response = client.put(upload_url, content=document.content)
                    upload_response.raise_for_status()
                return batch_id
            except (httpx.ConnectError, httpx.ReadTimeout, httpx.WriteTimeout, ssl.SSLError) as e:
                if attempt < max_attempts:
                    wait_s = 2 ** attempt
                    logger.warning(LogModule.CONVERT, f"[MINERU] File upload failed (attempt {attempt}), retrying: {e}")
                    time.sleep(wait_s)
                else:
                    raise
        
        raise Exception(f"Failed to upload file after {max_attempts} attempts")
    
    async def upload_async(self, document: Document) -> str:
        """Async upload document to cloud MinerU."""
        url = self._get_upload_url_endpoint()
        payload = self._build_upload_payload(document)
        
        response = await self._make_request_with_retry_async('POST', url, json=payload)
        result = response.json()
        
        if result.get("code") != 0:
            raise Exception(f"Failed to get upload URL: {result.get('msg', 'Unknown error')}")
        
        batch_id = result["data"]["batch_id"]
        upload_url = result["data"]["file_urls"][0]
        
        # Upload file directly to pre-signed URL
        max_attempts = self.retry_count + 1
        for attempt in range(1, max_attempts + 1):
            try:
                async with httpx.AsyncClient(trust_env=False, timeout=timeout, verify=False, limits=limits, proxy=None, mounts={'http://': None, 'https://': None}) as client:
                    upload_response = await client.put(upload_url, content=document.content)
                    upload_response.raise_for_status()
                return batch_id
            except (httpx.ConnectError, httpx.ReadTimeout, httpx.WriteTimeout, ssl.SSLError) as e:
                if attempt < max_attempts:
                    wait_s = 2 ** attempt
                    logger.warning(LogModule.CONVERT, f"[MINERU] File upload failed (attempt {attempt}), retrying: {e}")
                    await asyncio.sleep(wait_s)
                else:
                    raise
        
        raise Exception(f"Failed to upload file after {max_attempts} attempts")
    
    def get_result(self, batch_id: str) -> Tuple[str, bytes]:
        """Poll for result and download ZIP."""
        url = self._get_result_endpoint(batch_id)
        start_time = time.time()
        max_wait_seconds = 1800  # 30 minutes max
        
        while True:
            elapsed = time.time() - start_time
            if elapsed > max_wait_seconds:
                raise Exception(
                    f"MinerU Cloud processing timeout after {max_wait_seconds / 60:.0f} minutes. "
                    "The file may be too large or the server is overloaded. Please try again later."
                )
            
            response = self._make_request_with_retry('GET', url)
            result = response.json()
            
            if result.get("code") != 0:
                raise Exception(f"Failed to get result: {result.get('msg', 'Unknown error')}")
            
            fileinfo = result["data"]["extract_result"][0]
            state = fileinfo["state"]
            if state == "done":
                zip_url = fileinfo["full_zip_url"]
                # Download ZIP
                zip_response = self._make_request_with_retry('GET', zip_url)
                zip_bytes = zip_response.content
                logger.info(LogModule.CONVERT, f"[MINERU Cloud] Downloaded ZIP: {len(zip_bytes)} bytes from {zip_url[:50]}...")
                # Extract markdown
                markdown_content = self._extract_markdown_from_zip(zip_bytes)
                return markdown_content, zip_bytes
            elif state == "failed":
                raise Exception(
                    f"MinerU Cloud processing failed: {fileinfo.get('msg', 'Unknown error')}"
                )
            else:
                # Adaptive polling interval: faster at start, slower for long-running tasks
                if elapsed < 60:
                    sleep_interval = 3
                elif elapsed < 300:
                    sleep_interval = 5
                else:
                    sleep_interval = 15
                logger.debug(
                    LogModule.CONVERT,
                    f"[MINERU] Task not done yet, waiting {sleep_interval}s... (state: {state}, elapsed: {elapsed:.0f}s)"
                )
                time.sleep(sleep_interval)
    
    async def get_result_async(self, batch_id: str) -> Tuple[str, bytes]:
        """Async poll for result and download ZIP."""
        url = self._get_result_endpoint(batch_id)
        start_time = time.time()
        max_wait_seconds = 1800  # 30 minutes max
        
        while True:
            elapsed = time.time() - start_time
            if elapsed > max_wait_seconds:
                raise Exception(
                    f"MinerU Cloud processing timeout after {max_wait_seconds / 60:.0f} minutes. "
                    "The file may be too large or the server is overloaded. Please try again later."
                )
            
            response = await self._make_request_with_retry_async('GET', url)
            result = response.json()
            
            if result.get("code") != 0:
                raise Exception(f"Failed to get result: {result.get('msg', 'Unknown error')}")
            
            fileinfo = result["data"]["extract_result"][0]
            state = fileinfo["state"]
            if state == "done":
                zip_url = fileinfo["full_zip_url"]
                # Download ZIP
                zip_response = await self._make_request_with_retry_async('GET', zip_url)
                zip_bytes = zip_response.content
                logger.info(LogModule.CONVERT, f"[MINERU Cloud] Async downloaded ZIP: {len(zip_bytes)} bytes from {zip_url[:50]}...")
                # Extract markdown
                markdown_content = self._extract_markdown_from_zip(zip_bytes)
                return markdown_content, zip_bytes
            elif state == "failed":
                raise Exception(
                    f"MinerU Cloud processing failed: {fileinfo.get('msg', 'Unknown error')}"
                )
            else:
                # Adaptive polling interval: faster at start, slower for long-running tasks
                if elapsed < 60:
                    sleep_interval = 3
                elif elapsed < 300:
                    sleep_interval = 5
                else:
                    sleep_interval = 15
                logger.debug(
                    LogModule.CONVERT,
                    f"[MINERU] Task not done yet, waiting {sleep_interval}s... (state: {state}, elapsed: {elapsed:.0f}s)"
                )
                await asyncio.sleep(sleep_interval)
    
    def _extract_markdown_from_zip(self, zip_bytes: bytes) -> str:
        """Extract markdown from ZIP content."""
        import tempfile
        import os
        
        # Save ZIP to temp directory for debugging
        debug_dir = os.path.join(tempfile.gettempdir(), "owlangs_debug")
        os.makedirs(debug_dir, exist_ok=True)
        zip_path = os.path.join(debug_dir, f"mineru_response_{int(time.time())}.zip")
        with open(zip_path, 'wb') as f:
            f.write(zip_bytes)
        logger.info(LogModule.CONVERT, f"[MINERU] Saved ZIP to: {zip_path} ({len(zip_bytes)} bytes)")
        
        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
            # List all files in ZIP for debugging
            file_list = zf.namelist()
            logger.info(LogModule.CONVERT, f"[MINERU] ZIP contents: {file_list}")
            
            # Try to find markdown file - local MinerU may use different names
            md_files = [f for f in file_list if f.endswith('.md')]
            if not md_files:
                raise Exception(f"No markdown file found in ZIP. Contents: {file_list}")
            
            # Prefer full.md, otherwise use first .md file
            md_file = 'full.md' if 'full.md' in md_files else md_files[0]
            logger.info(LogModule.CONVERT, f"[MINERU] Using markdown file: {md_file}")
            
            with zf.open(md_file) as f:
                return f.read().decode("utf-8")
    
    def test_connection(self) -> Dict[str, Any]:
        """Test cloud API connectivity."""
        test_payload = {
            'url': 'https://cdn-mineru.openxlab.org.cn/demo/example.pdf',
            'is_ocr': True,
            'enable_formula': False,
        }
        test_url = f"{self.base_url}/extract/task"
        
        try:
            with httpx.Client(trust_env=False, timeout=15.0, verify=False, limits=limits, proxy=None, mounts={'http://': None, 'https://': None}) as client:
                headers = self._get_auth_header()
                headers['Content-Type'] = 'application/json'
                response = client.post(test_url, headers=headers, json=test_payload)
                
                body = response.json() if response.status_code == 200 else None
                
                if response.status_code == 200 and isinstance(body, dict) and body.get('code') == 0:
                    return {"success": True, "message": "Cloud MinerU connection successful"}
                elif response.status_code == 401:
                    return {"success": False, "message": "API Key invalid or expired"}
                else:
                    return {"success": False, "message": f"Unexpected response: {response.status_code}"}
        except httpx.RequestError as e:
            return {"success": False, "message": f"Connection failed: {str(e)}"}


class MinerULocalBackend(MinerUBackend):
    """
    Local MinerU backend (v3.1+).
    Uses multipart/form-data file upload with synchronous workflow.
    """
    
    API_VERSION = "local-v3.1"

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._pending_sync_zip_bytes: Optional[bytes] = None
    
    def _get_upload_sync_endpoint(self) -> str:
        endpoint = self.api_endpoints.get('upload_sync', '/file_parse')
        return f"{self.base_url}{endpoint}"
    
    def _get_upload_async_endpoint(self) -> str:
        endpoint = self.api_endpoints.get('upload_async', '/tasks')
        return f"{self.base_url}{endpoint}"
    
    def _get_status_endpoint(self, task_id: str) -> str:
        endpoint = self.api_endpoints.get('status', '/tasks/{task_id}')
        return f"{self.base_url}{endpoint.format(task_id=task_id)}"
    
    def _get_result_endpoint(self, task_id: str) -> str:
        endpoint = self.api_endpoints.get('result', '/tasks/{task_id}/result')
        return f"{self.base_url}{endpoint.format(task_id=task_id)}"
    
    def _get_health_endpoint(self) -> str:
        return f"{self.base_url}/health"
    
    def _convert_language(self) -> List[str]:
        """Convert generic language code to local MinerU format."""
        lang = (self.ocr_language or "").strip().lower()
        mapped = LOCAL_MINERU_LANG_MAP.get(lang, "ch")
        return [mapped]
    
    def _convert_backend(self) -> str:
        """Convert model version to local MinerU backend type."""
        return MODEL_TO_BACKEND.get(self.model_version, "hybrid-auto-engine")
    
    def _build_multipart_request(self, document: Document, return_zip: bool = True) -> Tuple[Dict, bytes, str]:
        """
        Build multipart form data for local API.
        
        Returns: (headers, body_bytes, content_type)
        """
        import secrets
        boundary = f"----FormBoundary{secrets.token_hex(8)}"
        content_type = f"multipart/form-data; boundary={boundary}"
        
        headers = self._get_auth_header()
        
        # Build form fields using correct field names for local MinerU
        lang_list = self._convert_language()
        backend = self._convert_backend()
        
        # Build body parts as list of bytes to avoid encoding issues
        body_parts: List[bytes] = []
        
        # Add lang_list items first
        for lang in lang_list:
            body_parts.append(f"--{boundary}\r\n".encode('utf-8'))
            body_parts.append('Content-Disposition: form-data; name="lang_list"\r\n'.encode('utf-8'))
            body_parts.append('\r\n'.encode('utf-8'))
            body_parts.append(f"{lang}\r\n".encode('utf-8'))
        
        # Add form fields (v3.1+ style). Older mineru-api builds may reject optional keys;
        # if local parse fails with 422, try disabling parse_method / return_middle_json in config later.
        form_fields = {
            'formula_enable': str(self.formula).lower(),
            'table_enable': str(self.table).lower(),
            'backend': backend,
            'parse_method': 'auto',
            'return_md': 'true',
            'return_images': 'true',  # Include images in ZIP
            'return_middle_json': 'true',  # Include middle_json for layout
            'response_format_zip': str(return_zip).lower(),
        }
        
        for key, value in form_fields.items():
            body_parts.append(f"--{boundary}\r\n".encode('utf-8'))
            body_parts.append(f'Content-Disposition: form-data; name="{key}"\r\n'.encode('utf-8'))
            body_parts.append('\r\n'.encode('utf-8'))
            body_parts.append(f"{value}\r\n".encode('utf-8'))
        
        # Add file - field name is "files"
        body_parts.append(f"--{boundary}\r\n".encode('utf-8'))
        body_parts.append(f'Content-Disposition: form-data; name="files"; filename="{document.name}"\r\n'.encode('utf-8'))
        body_parts.append("Content-Type: application/octet-stream\r\n".encode('utf-8'))
        body_parts.append('\r\n'.encode('utf-8'))
        
        # Join parts and add file content
        body_bytes = b''.join(body_parts)
        body_bytes += document.content
        body_bytes += f"\r\n--{boundary}--\r\n".encode('utf-8')
        
        headers['Content-Type'] = content_type
        
        return headers, body_bytes, content_type
    
    def upload(self, document: Document) -> str:
        """Upload document to local MinerU using sync parsing."""
        url = self._get_upload_sync_endpoint()
        headers, body_bytes, _ = self._build_multipart_request(document, return_zip=True)
        
        logger.debug(LogModule.CONVERT, f"[MINERU Local] Uploading to {url}")
        
        with httpx.Client(trust_env=False, timeout=timeout, verify=False, limits=limits, proxy=None, mounts={'http://': None, 'https://': None}) as client:
            response = client.post(url, headers=headers, content=body_bytes)
            
            if response.status_code != 200:
                raise Exception(f"Upload failed: {response.status_code} - {response.text[:500]}")
            
            # Response should be ZIP file
            content_type = response.headers.get('content-type', '')
            if 'zip' in content_type or response.content[:2] == b'PK':
                # Got ZIP directly
                zip_size = len(response.content)
                logger.info(LogModule.CONVERT, f"[MINERU Local] Received ZIP response: {zip_size} bytes, content-type={content_type}")
                
                # Save ZIP to task temp directory if available, otherwise to system temp
                zip_bytes = response.content
                temp_dir = tempfile.gettempdir()
                logger.info(LogModule.CONVERT, f"[MINERU Local] Temp directory: {temp_dir}")
                
                # Try to find current task directory (owlangs_*)
                task_dirs = [d for d in glob.glob(os.path.join(temp_dir, "owlangs_*")) if os.path.isdir(d)]
                logger.info(LogModule.CONVERT, f"[MINERU Local] Found {len(task_dirs)} task directories: {task_dirs[:3]}")
                
                if task_dirs:
                    # Use most recent task directory
                    task_dir = max(task_dirs, key=os.path.getmtime)
                    zip_path = os.path.join(task_dir, "mineru_response.zip")
                    logger.info(LogModule.CONVERT, f"[MINERU Local] Using task directory: {task_dir}")
                else:
                    zip_path = os.path.join(temp_dir, f"mineru_response_{int(time.time())}.zip")
                    logger.info(LogModule.CONVERT, f"[MINERU Local] No task directory found, using temp: {zip_path}")
                
                logger.info(LogModule.CONVERT, f"[MINERU Local] Attempting to save ZIP to: {zip_path}")
                try:
                    # Check if it's really a ZIP (starts with PK)
                    if zip_bytes[:2] != b'PK':
                        logger.error(LogModule.CONVERT, f"[MINERU Local] Response is not a ZIP file! First 100 bytes: {zip_bytes[:100]}")
                        try:
                            # Try to decode as JSON for error message
                            error_json = json.loads(zip_bytes.decode('utf-8'))
                            logger.error(LogModule.CONVERT, f"[MINERU Local] Error response: {error_json}")
                        except:
                            pass
                    
                    with open(zip_path, 'wb') as f:
                        f.write(zip_bytes)
                    logger.info(LogModule.CONVERT, f"[MINERU Local] SUCCESS: Saved ZIP to: {zip_path} ({os.path.getsize(zip_path)} bytes)")
                    
                    # Log ZIP contents with detailed file sizes
                    try:
                        with zipfile.ZipFile(zip_path, 'r') as zf:
                            file_list = zf.namelist()
                            logger.info(LogModule.CONVERT, f"[MINERU Local] ZIP contents ({len(file_list)} files):")
                            for f in file_list:
                                info = zf.getinfo(f)
                                logger.info(LogModule.CONVERT, f"  - {f} ({info.file_size} bytes)")
                    except Exception as e:
                        logger.error(LogModule.CONVERT, f"[MINERU Local] Failed to read ZIP contents: {e}")
                        
                except Exception as e:
                    logger.error(LogModule.CONVERT, f"[MINERU Local] FAILED to save ZIP: {e}")

                self._pending_sync_zip_bytes = zip_bytes
                return _LOCAL_MINERU_SYNC_TASK_ID
            else:
                # Got JSON response
                try:
                    result = response.json()
                    # Check if there's a task ID for async
                    if 'task_id' in result:
                        return result['task_id']
                    else:
                        raise Exception(f"Unexpected response: {result}")
                except json.JSONDecodeError:
                    raise Exception(f"Unexpected response format: {response.text[:500]}")
    
    async def upload_async(self, document: Document) -> str:
        """Async upload document to local MinerU."""
        url = self._get_upload_sync_endpoint()
        headers, body_bytes, _ = self._build_multipart_request(document, return_zip=True)
        
        logger.debug(LogModule.CONVERT, f"[MINERU Local] Async uploading to {url}")
        
        async with httpx.AsyncClient(trust_env=False, timeout=timeout, verify=False, limits=limits, proxy=None, mounts={'http://': None, 'https://': None}) as client:
            response = await client.post(url, headers=headers, content=body_bytes)
            
            if response.status_code != 200:
                raise Exception(f"Upload failed: {response.status_code} - {response.text[:500]}")
            
            # Response should be ZIP file
            content_type = response.headers.get('content-type', '')
            if 'zip' in content_type or response.content[:2] == b'PK':
                # Got ZIP directly
                zip_size = len(response.content)
                logger.info(LogModule.CONVERT, f"[MINERU Local] Async received ZIP response: {zip_size} bytes, content-type={content_type}")
                self._pending_sync_zip_bytes = response.content
                return _LOCAL_MINERU_SYNC_TASK_ID
            else:
                try:
                    result = response.json()
                    if 'task_id' in result:
                        return result['task_id']
                    else:
                        raise Exception(f"Unexpected response: {result}")
                except json.JSONDecodeError:
                    raise Exception(f"Unexpected response format: {response.text[:500]}")
    
    def get_result(self, task_id: str) -> Tuple[str, bytes]:
        """Get parsing result."""
        if task_id == _LOCAL_MINERU_SYNC_TASK_ID:
            zip_bytes = self._pending_sync_zip_bytes
            self._pending_sync_zip_bytes = None
            if zip_bytes is None:
                raise RuntimeError(
                    "Local MinerU sync ZIP missing after upload; retry conversion or check MinerU logs."
                )
            markdown_content = self._extract_markdown_from_zip(zip_bytes)
            return markdown_content, zip_bytes
        # Legacy: hex-encoded ZIP in task_id (avoid — doubles memory)
        if task_id.startswith("__zip__"):
            try:
                zip_bytes = bytes.fromhex(task_id[7:])
            except ValueError as e:
                raise ValueError(f"Invalid legacy __zip__ payload in task_id: {e}") from e
            markdown_content = self._extract_markdown_from_zip(zip_bytes)
            return markdown_content, zip_bytes
        
        # Otherwise, poll for async result
        # TODO: Implement async result polling
        raise NotImplementedError("Async result polling not yet implemented for local MinerU")
    
    async def get_result_async(self, task_id: str) -> Tuple[str, bytes]:
        """Async get parsing result."""
        if task_id == _LOCAL_MINERU_SYNC_TASK_ID:
            zip_bytes = self._pending_sync_zip_bytes
            self._pending_sync_zip_bytes = None
            if zip_bytes is None:
                raise RuntimeError(
                    "Local MinerU sync ZIP missing after upload; retry conversion or check MinerU logs."
                )
            markdown_content = self._extract_markdown_from_zip(zip_bytes)
            return markdown_content, zip_bytes
        if task_id.startswith("__zip__"):
            try:
                zip_bytes = bytes.fromhex(task_id[7:])
            except ValueError as e:
                raise ValueError(f"Invalid legacy __zip__ payload in task_id: {e}") from e
            markdown_content = self._extract_markdown_from_zip(zip_bytes)
            return markdown_content, zip_bytes
        
        raise NotImplementedError("Async result polling not yet implemented for local MinerU")
    
    def _extract_markdown_from_zip(self, zip_bytes: bytes) -> str:
        """Extract markdown from ZIP content."""
        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
            # List all files in ZIP for debugging
            file_list = zf.namelist()
            logger.info(LogModule.CONVERT, f"[MINERU Local] ZIP contents: {file_list}")
            
            # Try to find markdown file - local MinerU may use different names
            md_files = [f for f in file_list if f.endswith('.md')]
            if not md_files:
                raise Exception(f"No markdown file found in ZIP. Contents: {file_list}")
            
            # Prefer full.md, otherwise use first .md file
            md_file = 'full.md' if 'full.md' in md_files else md_files[0]
            logger.info(LogModule.CONVERT, f"[MINERU Local] Using markdown file: {md_file}")
            
            with zf.open(md_file) as f:
                return f.read().decode("utf-8")
    
    def test_connection(self) -> Dict[str, Any]:
        """Test local API connectivity using /health endpoint."""
        # Try /health endpoint first
        try:
            health_url = self._get_health_endpoint()
            with httpx.Client(trust_env=False, timeout=15.0, verify=False, limits=limits, proxy=None, mounts={'http://': None, 'https://': None}) as client:
                headers = self._get_auth_header()
                response = client.get(health_url, headers=headers)
                
                if response.status_code == 200:
                    return {
                        "success": True,
                        "message": f"Local MinerU server is running at {self.base_url}",
                        "status_code": 200,
                        "endpoint": "/health"
                    }
        except httpx.RequestError:
            pass
        
        # Fallback to API endpoints
        endpoints_to_try = [
            self._get_upload_sync_endpoint(),
            self._get_upload_async_endpoint(),
        ]
        
        for test_url in endpoints_to_try:
            try:
                with httpx.Client(trust_env=False, timeout=15.0, verify=False, limits=limits, proxy=None, mounts={'http://': None, 'https://': None}) as client:
                    headers = self._get_auth_header()
                    response = client.get(test_url, headers=headers)
                    
                    if response.status_code == 405:
                        return {
                            "success": True,
                            "message": f"Local MinerU server is running at {self.base_url}",
                            "status_code": 405,
                            "endpoint": test_url
                        }
                    elif response.status_code == 422:
                        return {
                            "success": True,
                            "message": f"Local MinerU server is running at {self.base_url}",
                            "status_code": 422,
                            "endpoint": test_url
                        }
            except httpx.RequestError:
                continue
        
        return {
            "success": False,
            "message": f"Cannot connect to local MinerU at {self.base_url}",
        }


class BackendFactory:
    """Factory to create appropriate MinerU backend based on configuration."""
    
    @staticmethod
    def create_backend(config: ConverterMineruConfig) -> MinerUBackend:
        """
        Create appropriate backend based on base_url and api_endpoints.
        
        Detection logic:
        - https://mineru.net -> Cloud API only (even if api_endpoints accidentally lists local paths).
        - Any other base_url -> Local MinerU HTTP API (self-hosted).
        """
        base_url = (config.base_url or MINERU_CLOUD_BASE).rstrip('/')
        api_endpoints = config.api_endpoints or {}
        
        is_cloud_host = base_url.startswith('https://mineru.net')
        
        if is_cloud_host:
            logger.debug(LogModule.CONVERT, f"[MINERU] Using Cloud backend for {base_url}")
            return MinerUCloudBackend(
                base_url=base_url,
                mineru_token=config.mineru_token,
                formula_ocr=config.formula_ocr,
                table_ocr=config.table_ocr,
                model_version=config.model_version,
                ocr_language=config.ocr_language,
                api_endpoints=api_endpoints,
                retry_count=config.request_retry_count,
            )
        logger.debug(LogModule.CONVERT, f"[MINERU] Using Local backend for {base_url}")
        return MinerULocalBackend(
            base_url=base_url,
            mineru_token=config.mineru_token,
            formula_ocr=config.formula_ocr,
            table_ocr=config.table_ocr,
            model_version=config.model_version,
            ocr_language=config.ocr_language,
            api_endpoints=api_endpoints,
            retry_count=config.request_retry_count,
        )


class ConverterMineru(X2MarkdownConverter):
    """MinerU converter with backend abstraction."""
    
    def __init__(self, config: ConverterMineruConfig):
        super().__init__(config=config)
        self.config = config
        self.backend = BackendFactory.create_backend(config)
        self.attachments: list[AttachMent] = []
        self.layout_document: LayoutDocument | None = None
        # Optional callback for split-PDF progress reporting: (current_part, total_parts, message)
        self.progress_callback: Optional[Callable[[int, int, str], None]] = None
        
        if hasattr(config, 'logger') and config.logger:
            if config.mineru_token:
                config.logger.debug(LogModule.WORKFLOW, f"ConverterMineru initialized with API Key (length: {len(config.mineru_token)})")
            elif isinstance(self.backend, MinerULocalBackend):
                config.logger.debug(LogModule.WORKFLOW, "ConverterMineru initialized for local deployment (no API key).")
            else:
                config.logger.warning(LogModule.WORKFLOW, "[WARNING] ConverterMineru initialized without API Key!")
    
    def upload(self, document: Document) -> str:
        """Upload document using appropriate backend."""
        return self.backend.upload(document)
    
    async def upload_async(self, document: Document) -> str:
        """Async upload document using appropriate backend."""
        return await self.backend.upload_async(document)
    
    def get_file_url(self, batch_id: str) -> str:
        """Legacy method - returns batch_id as URL identifier."""
        return batch_id
    
    async def get_file_url_async(self, batch_id: str) -> str:
        """Legacy async method."""
        return batch_id
    
    def convert(self, document: Document) -> MarkdownDocument:
        """Convert document to markdown."""
        self.logger.info(LogModule.WORKFLOW, f"Converting document with MinerU, backend: {type(self.backend).__name__}")
        time1 = time.time()

        # Check if PDF splitting is needed
        if (
            document.suffix == ".pdf"
            and getattr(self.config, "pdf_split_enabled", True)
        ):
            from utils.pdf_splitter import split_pdf_by_pages
            max_pages = getattr(self.config, "pdf_split_max_pages", 100)
            pdf_parts = split_pdf_by_pages(document.content, max_pages_per_split=max_pages)
            if len(pdf_parts) > 1:
                result = self._convert_split_pdf(document, pdf_parts)
                self.logger.info(LogModule.WORKFLOW, f"Split PDF converted, time taken: {time.time() - time1:.2f}s")
                return result

        # Fallback to single-file conversion
        result = self._convert_single(document)
        self.logger.info(LogModule.WORKFLOW, f"Document converted, time taken: {time.time() - time1:.2f}s")
        return result

    def _convert_single(self, document: Document) -> MarkdownDocument:
        """Original single-file conversion logic."""
        task_id = self.upload(document)
        markdown_content, zip_bytes = self.backend.get_result(task_id)

        # Process result
        if zip_bytes:
            self.attachments.append(AttachMent("mineru", Document.from_bytes(
                content=zip_bytes, suffix=".zip", stem="mineru"
            )))
            try:
                self.layout_document = load_layout_from_engine_zip("mineru", zip_bytes)
            except Exception as e:
                self.logger.debug(LogModule.WORKFLOW, f"[LAYOUT] Failed to parse MinerU layout: {e}")

            # For Local MinerU, embed images from ZIP
            if isinstance(self.backend, MinerULocalBackend):
                try:
                    md_file_path = self._find_md_file_in_zip(zip_bytes)
                    if md_file_path:
                        self.logger.info(LogModule.WORKFLOW, f"[MINERU Local] Embedding images from {md_file_path}")
                        markdown_content = embed_inline_image_from_zip(
                            zip_bytes,
                            filename_in_zip=md_file_path,
                            encoding="utf-8"
                        )
                except Exception as e:
                    self.logger.warning(LogModule.WORKFLOW, f"[MINERU Local] Failed to embed images: {e}")

        return MarkdownDocument.from_bytes(content=markdown_content.encode("utf-8"), suffix=".md", stem=document.stem)

    def _convert_split_pdf(self, original_document: Document, pdf_parts: List[bytes]) -> MarkdownDocument:
        """
        Convert split PDF parts with controlled concurrency and merge results.
        """
        from utils.layout_merger import merge_layout_documents
        from utils.mineru_zip_merger import merge_mineru_zips
        from concurrent.futures import ThreadPoolExecutor

        max_workers = getattr(self.config, "pdf_split_max_workers", 2)

        def _process_part(i: int, part_bytes: bytes) -> Tuple[int, str, bytes, Optional[LayoutDocument]]:
            self.logger.info(LogModule.WORKFLOW, f"[MINERU SPLIT] Processing part {i + 1}/{len(pdf_parts)}")
            if self.progress_callback:
                self.progress_callback(i + 1, len(pdf_parts), f"Extracting PDF part {i + 1}/{len(pdf_parts)}...")

            part_doc = Document.from_bytes(
                content=part_bytes,
                suffix=".pdf",
                stem=f"{original_document.stem}_part{i + 1}"
            )

            task_id = self.backend.upload(part_doc)
            markdown_content, zip_bytes = self.backend.get_result(task_id)

            # For Local backend: embed inline images before merging
            if isinstance(self.backend, MinerULocalBackend):
                try:
                    md_file_path = self._find_md_file_in_zip(zip_bytes)
                    if md_file_path:
                        markdown_content = embed_inline_image_from_zip(
                            zip_bytes,
                            filename_in_zip=md_file_path,
                            encoding="utf-8"
                        )
                except Exception as e:
                    self.logger.warning(LogModule.WORKFLOW, f"[MINERU Local] Failed to embed images for part {i + 1}: {e}")

            layout_doc = load_layout_from_engine_zip("mineru", zip_bytes)
            if not layout_doc:
                self.logger.warning(LogModule.WORKFLOW, f"[MINERU SPLIT] No layout document parsed for part {i + 1}")

            return i, markdown_content, zip_bytes, layout_doc

        results: List[Tuple[int, str, bytes, Optional[LayoutDocument]]] = []
        if max_workers > 1 and len(pdf_parts) > 1:
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                futures = [executor.submit(_process_part, i, part) for i, part in enumerate(pdf_parts)]
                results = [f.result() for f in futures]
        else:
            results = [_process_part(i, part) for i, part in enumerate(pdf_parts)]

        # Sort by index to preserve order
        results.sort(key=lambda x: x[0])

        merged_markdown_parts = [r[1] for r in results]
        merged_zip_bytes = [r[2] for r in results]
        merged_layout_docs = [r[3] for r in results if r[3] is not None]

        # Merge markdown
        final_markdown = "\n\n".join(merged_markdown_parts)

        # Merge layout documents
        if merged_layout_docs:
            self.layout_document = merge_layout_documents(merged_layout_docs)
            self.logger.info(
                LogModule.WORKFLOW,
                f"[MINERU SPLIT] Merged layout: {self.layout_document.page_count} pages, "
                f"{sum(1 for _ in self.layout_document.iter_blocks())} blocks"
            )

        # Build merged ZIP
        zip_parts_with_layout = list(zip(merged_zip_bytes, merged_layout_docs))
        merged_zip = merge_mineru_zips(zip_parts_with_layout, self.layout_document, final_markdown)
        self.attachments.append(AttachMent("mineru", Document.from_bytes(
            content=merged_zip, suffix=".zip", stem="mineru"
        )))
        self.logger.info(LogModule.WORKFLOW, f"[MINERU SPLIT] Merged ZIP size: {len(merged_zip)} bytes")

        return MarkdownDocument.from_bytes(
            content=final_markdown.encode("utf-8"),
            suffix=".md",
            stem=original_document.stem
        )
    
    def _find_md_file_in_zip(self, zip_bytes: bytes) -> Optional[str]:
        """Find the markdown file path in ZIP."""
        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
            md_files = [f for f in zf.namelist() if f.endswith('.md')]
            if not md_files:
                return None
            # Prefer full.md (Cloud), otherwise use first .md file
            return 'full.md' if 'full.md' in md_files else md_files[0]
    
    async def convert_async(self, document: Document) -> MarkdownDocument:
        """Async convert document to markdown."""
        self.logger.info(LogModule.WORKFLOW, f"Converting document with MinerU (async), backend: {type(self.backend).__name__}")
        time1 = time.time()

        # Check if PDF splitting is needed
        if (
            document.suffix == ".pdf"
            and getattr(self.config, "pdf_split_enabled", True)
        ):
            from utils.pdf_splitter import split_pdf_by_pages
            max_pages = getattr(self.config, "pdf_split_max_pages", 100)
            pdf_parts = split_pdf_by_pages(document.content, max_pages_per_split=max_pages)
            if len(pdf_parts) > 1:
                result = await self._convert_split_pdf_async(document, pdf_parts)
                self.logger.info(LogModule.WORKFLOW, f"Split PDF converted (async), time taken: {time.time() - time1:.2f}s")
                return result

        # Fallback to single-file conversion
        result = await self._convert_single_async(document)
        self.logger.info(LogModule.WORKFLOW, f"Document converted (async), time taken: {time.time() - time1:.2f}s")
        return result

    async def _convert_single_async(self, document: Document) -> MarkdownDocument:
        """Original single-file async conversion logic."""
        task_id = await self.upload_async(document)
        markdown_content, zip_bytes = await self.backend.get_result_async(task_id)

        # Process result
        if zip_bytes:
            self.attachments.append(AttachMent("mineru", Document.from_bytes(
                content=zip_bytes, suffix=".zip", stem="mineru"
            )))
            try:
                self.layout_document = load_layout_from_engine_zip("mineru", zip_bytes)
            except Exception as e:
                self.logger.debug(LogModule.WORKFLOW, f"[LAYOUT] Failed to parse MinerU layout (async): {e}")

            # For Local MinerU, embed images from ZIP
            if isinstance(self.backend, MinerULocalBackend):
                try:
                    md_file_path = self._find_md_file_in_zip(zip_bytes)
                    if md_file_path:
                        self.logger.info(LogModule.WORKFLOW, f"[MINERU Local] Embedding images from {md_file_path}")
                        markdown_content = await asyncio.to_thread(
                            embed_inline_image_from_zip,
                            zip_bytes,
                            filename_in_zip=md_file_path,
                            encoding="utf-8"
                        )
                except Exception as e:
                    self.logger.warning(LogModule.WORKFLOW, f"[MINERU Local] Failed to embed images (async): {e}")

        return MarkdownDocument.from_bytes(content=markdown_content.encode("utf-8"), suffix=".md", stem=document.stem)

    async def _convert_split_pdf_async(self, original_document: Document, pdf_parts: List[bytes]) -> MarkdownDocument:
        """
        Async convert split PDF parts with controlled concurrency and merge results.
        """
        from utils.layout_merger import merge_layout_documents
        from utils.mineru_zip_merger import merge_mineru_zips

        max_workers = getattr(self.config, "pdf_split_max_workers", 2)

        async def _process_part(i: int, part_bytes: bytes) -> Tuple[int, str, bytes, Optional[LayoutDocument]]:
            self.logger.info(LogModule.WORKFLOW, f"[MINERU SPLIT] Processing part {i + 1}/{len(pdf_parts)} (async)")
            if self.progress_callback:
                self.progress_callback(i + 1, len(pdf_parts), f"Extracting PDF part {i + 1}/{len(pdf_parts)}...")

            part_doc = Document.from_bytes(
                content=part_bytes,
                suffix=".pdf",
                stem=f"{original_document.stem}_part{i + 1}"
            )

            task_id = await self.upload_async(part_doc)
            markdown_content, zip_bytes = await self.backend.get_result_async(task_id)

            # For Local backend: embed inline images before merging
            if isinstance(self.backend, MinerULocalBackend):
                try:
                    md_file_path = self._find_md_file_in_zip(zip_bytes)
                    if md_file_path:
                        markdown_content = await asyncio.to_thread(
                            embed_inline_image_from_zip,
                            zip_bytes,
                            filename_in_zip=md_file_path,
                            encoding="utf-8"
                        )
                except Exception as e:
                    self.logger.warning(LogModule.WORKFLOW, f"[MINERU Local] Failed to embed images for part {i + 1} (async): {e}")

            layout_doc = load_layout_from_engine_zip("mineru", zip_bytes)
            if not layout_doc:
                self.logger.warning(LogModule.WORKFLOW, f"[MINERU SPLIT] No layout document parsed for part {i + 1} (async)")

            return i, markdown_content, zip_bytes, layout_doc

        results: List[Tuple[int, str, bytes, Optional[LayoutDocument]]] = []
        if max_workers > 1 and len(pdf_parts) > 1:
            semaphore = asyncio.Semaphore(max_workers)

            async def _process_with_limit(i: int, part_bytes: bytes) -> Tuple[int, str, bytes, Optional[LayoutDocument]]:
                async with semaphore:
                    return await _process_part(i, part_bytes)

            results = await asyncio.gather(*[_process_with_limit(i, part) for i, part in enumerate(pdf_parts)])
        else:
            results = []
            for i, part in enumerate(pdf_parts):
                results.append(await _process_part(i, part))

        # Sort by index to preserve order
        results.sort(key=lambda x: x[0])

        merged_markdown_parts = [r[1] for r in results]
        merged_zip_bytes = [r[2] for r in results]
        merged_layout_docs = [r[3] for r in results if r[3] is not None]

        # Merge markdown
        final_markdown = "\n\n".join(merged_markdown_parts)

        # Merge layout documents
        if merged_layout_docs:
            self.layout_document = merge_layout_documents(merged_layout_docs)
            self.logger.info(
                LogModule.WORKFLOW,
                f"[MINERU SPLIT] Merged layout (async): {self.layout_document.page_count} pages, "
                f"{sum(1 for _ in self.layout_document.iter_blocks())} blocks"
            )

        # Build merged ZIP
        zip_parts_with_layout = list(zip(merged_zip_bytes, merged_layout_docs))
        merged_zip = merge_mineru_zips(zip_parts_with_layout, self.layout_document, final_markdown)
        self.attachments.append(AttachMent("mineru", Document.from_bytes(
            content=merged_zip, suffix=".zip", stem="mineru"
        )))
        self.logger.info(LogModule.WORKFLOW, f"[MINERU SPLIT] Merged ZIP size (async): {len(merged_zip)} bytes")

        return MarkdownDocument.from_bytes(
            content=final_markdown.encode("utf-8"),
            suffix=".md",
            stem=original_document.stem
        )
    
    def support_format(self) -> list[str]:
        return [".pdf", ".doc", ".docx", ".ppt", ".pptx", ".png", ".jpg", ".jpeg"]


# Keep backward compatibility for utility functions
def get_md_from_zip_url_with_inline_images(
        zip_url: str = None,
        filename_in_zip: str = "full.md",
        encoding: str = "utf-8",
        zip_file_obj: io.BytesIO = None
) -> tuple[str, bytes]:
    """Download and extract content from ZIP file URL or file object."""
    import tempfile
    import os
    try:
        if zip_file_obj:
            zip_file_obj.seek(0)
            zip_bytes = zip_file_obj.read()
            return embed_inline_image_from_zip(zip_bytes, filename_in_zip=filename_in_zip, encoding=encoding), zip_bytes
        
        if not zip_url:
            raise ValueError("Either zip_url or zip_file_obj must be provided")
        
        for attempt in range(1, 4):
            try:
                response = client.get(zip_url)
                response.raise_for_status()
                return embed_inline_image_from_zip(response.content, filename_in_zip=filename_in_zip, encoding=encoding), response.content
            except httpx.RequestError as e:
                if attempt < 3:
                    wait_s = 2 ** attempt
                    time.sleep(wait_s)
                else:
                    raise
    except Exception as e:
        raise Exception(f"Error processing ZIP: {e}")


async def get_md_from_zip_url_with_inline_images_async(
        zip_url: str,
        filename_in_zip: str = "full.md",
        encoding: str = "utf-8"
) -> tuple[str, bytes]:
    """Async download and extract content from ZIP file URL."""
    for attempt in range(1, 4):
        try:
            response = await client_async.get(zip_url)
            response.raise_for_status()
            return await asyncio.to_thread(embed_inline_image_from_zip, response.content, filename_in_zip=filename_in_zip, encoding=encoding), response.content
        except httpx.RequestError as e:
            if attempt < 3:
                wait_s = 2 ** attempt
                await asyncio.sleep(wait_s)
            else:
                raise


if __name__ == '__main__':
    pass
