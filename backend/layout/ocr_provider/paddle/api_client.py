# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

"""
PaddleOCR HTTP API client.

Supports two deployment modes:

Cloud async (AI Studio):
1. POST ``/api/v2/ocr/jobs`` — multipart submit, receive job_id
2. GET  ``/api/v2/ocr/jobs/{job_id}`` — poll until done
3. GET  result URL — download JSONL payload

Local sync (official PaddleOCR service):
1. POST ``/layout-parsing`` (VL layout) or ``/ocr`` (text OCR) — JSON base64 ``file`` + ``fileType``
2. Response returns ``result.layoutParsingResults`` or ``result.ocrResults`` inline (no polling)
"""

import asyncio
import base64
import json
import threading
import time
from email.utils import formatdate
from pathlib import PurePath
from typing import Any, Dict, Optional

import httpx

from layout.ocr_provider.paddle.sync_infer_adapter import (
    is_sync_infer_submit_path,
    normalize_sync_infer_response,
)
from logger import unified_logger as logger
from logger.logger import LogModule

_INLINE_SYNC_JOB_ID = "__paddle_sync_inline__"


class PaddleOCRClient:
    """Async HTTP client for PaddleOCR v2 API.

    Mirrors the official ``paddleocr-api`` Python SDK request format:
    - Auth: ``Authorization: bearer {token}`` (lowercase)
    - Submit: multipart POST with ``model`` in data + ``file`` as raw bytes
    - Poll: GET ``/api/v2/ocr/jobs/{job_id}``, response nested under ``data``
    - Result: GET ``resultUrl.jsonUrl``, response is JSONL (newline-delimited JSON)
    """

    # Default document parsing model (PaddleOCR-VL-1.6)
    DEFAULT_MODEL = "PaddleOCR-VL-1.6"

    def __init__(
        self,
        token: str,
        base_url: str = "https://paddleocr.aistudio-app.com",
        api_endpoints: Optional[Dict[str, str]] = None,
        poll_interval: float = 3.0,
        max_wait: float = 1800.0,
        model: str = "",
        use_doc_orientation_classify: bool = False,
        restructure_pages: bool = False,
        cancel_event: Optional[threading.Event] = None,
    ):
        """
        Args:
            token: AI Studio access token for API authentication.
            base_url: Base URL of the PaddleOCR API.
            api_endpoints: Dict with "submit" and "result" endpoint paths
                           (for local / non-standard deployments).
            poll_interval: Seconds between status polls (default 3s).
            max_wait: Maximum total wait time in seconds (default 30 min).
            model: Document parsing model name (defaults to PaddleOCR-VL-1.6).
            use_doc_orientation_classify: If True, PaddleOCR auto-detects and
                corrects document orientation (may shift bbox coordinates).
            restructure_pages: If True, PaddleOCR restructures page layout.
            cancel_event: Optional threading.Event to signal cancellation
                          from another thread (e.g. Ctrl+C shutdown).
        """
        self.token = token
        self.base_url = base_url.rstrip("/")
        self.poll_interval = poll_interval
        self.max_wait = max_wait
        self.model = model if model and model != "default" else self.DEFAULT_MODEL
        self.use_doc_orientation_classify = use_doc_orientation_classify
        self.restructure_pages = restructure_pages
        self._cancel_event = cancel_event

        endpoints = api_endpoints or {}
        self._submit_path = endpoints.get("submit", "/api/v2/ocr/jobs")
        self._result_path = endpoints.get("result", "/api/v2/ocr/jobs/{job_id}")
        self._sync_infer_mode = is_sync_infer_submit_path(self._submit_path)
        self._inline_sync_raw: Optional[Dict[str, Any]] = None

        self._client: Optional[httpx.AsyncClient] = None

    @property
    def client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                timeout=httpx.Timeout(connect=30.0, read=300.0, write=300.0, pool=10.0),
            )
        return self._client

    def _auth_headers(self) -> Dict[str, str]:
        if self.token:
            # Official SDK uses lowercase "bearer"
            return {"Authorization": f"bearer {self.token}"}
        return {}

    async def close(self) -> None:
        if self._client is not None:
            try:
                # Guard close with a timeout so it doesn't block Ctrl+C shutdown.
                # httpx may try to drain lingering connections that won't complete.
                await asyncio.wait_for(self._client.aclose(), timeout=2.0)
            except (asyncio.TimeoutError, asyncio.CancelledError, Exception):
                # If graceful close times out, force-close the underlying transport.
                try:
                    await self._client.aclose()
                except Exception:
                    pass
            finally:
                self._client = None

    async def __aenter__(self) -> "PaddleOCRClient":
        _ = self.client  # ensure client is created
        return self

    async def __aexit__(self, *args: Any) -> None:
        await self.close()

    @staticmethod
    def _sync_file_type(filename: str) -> int:
        """Local sync API fileType: 0=PDF, 1=image."""
        suffix = PurePath(filename or "").suffix.lower()
        if suffix in (".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff", ".webp"):
            return 1
        return 0

    async def _submit_sync_infer(self, file_bytes: bytes, filename: str) -> str:
        """POST JSON /layout-parsing or /ocr with base64 file (local PaddleOCR serving)."""
        payload: Dict[str, Any] = {
            "file": base64.b64encode(file_bytes).decode("ascii"),
            "fileType": self._sync_file_type(filename),
            "useDocOrientationClassify": self.use_doc_orientation_classify,
        }
        response = await self.client.post(
            self._submit_path,
            json=payload,
            headers={**self._auth_headers(), "Content-Type": "application/json"},
        )
        if response.status_code != 200:
            logger.error(
                LogModule.LAYOUT,
                f"PaddleOCR sync infer failed: HTTP {response.status_code}\n"
                f"Request URL: {self.base_url}{self._submit_path}\n"
                f"Response body: {response.text[:2000]}",
            )
        response.raise_for_status()
        resp_json = response.json()
        if resp_json.get("errorCode") not in (None, 0):
            raise RuntimeError(
                f"PaddleOCR sync infer error: {resp_json.get('errorMsg') or resp_json}"
            )
        self._inline_sync_raw = resp_json
        sync_result = resp_json.get("result") or {}
        page_count = len(
            sync_result.get("layoutParsingResults")
            or sync_result.get("ocrResults")
            or []
        )
        logger.info(
            LogModule.LAYOUT,
            f"[PADDLEOCR-CONFIG] Sync infer completed inline "
            f"(endpoint={self._submit_path}, pages={page_count})",
        )
        return _INLINE_SYNC_JOB_ID

    async def submit_job(self, pdf_bytes: bytes, filename: str = "document.pdf") -> str:
        """
        Submit a PDF document for document parsing (layout analysis + OCR).

        Cloud async: multipart POST with model + optionalPayload + file bytes.
        Local sync: JSON POST /layout-parsing or /ocr with base64 file (result returned inline).
        """
        logger.info(
            LogModule.LAYOUT,
            f"[PADDLEOCR-CONFIG] Submitting job (mode="
            f"{'sync_infer' if self._sync_infer_mode else 'cloud_async'}, "
            f"model={self.model}, "
            f"use_doc_orientation_classify={self.use_doc_orientation_classify}, "
            f"restructure_pages={self.restructure_pages}, "
            f"size={len(pdf_bytes)} bytes)"
        )

        if self._sync_infer_mode:
            return await self._submit_sync_infer(pdf_bytes, filename)

        # Match official cloud SDK: data with model + optionalPayload, files as raw bytes
        optional_payload = {
            "useDocOrientationClassify": self.use_doc_orientation_classify,
            "restructurePages": self.restructure_pages,
        }
        data = {
            "model": self.model,
            "optionalPayload": json.dumps(optional_payload),
        }
        files = {"file": pdf_bytes}
        response = await self.client.post(
            self._submit_path,
            data=data,
            files=files,
            headers=self._auth_headers(),
        )
        if response.status_code != 200:
            logger.error(
                LogModule.LAYOUT,
                f"PaddleOCR submit failed: HTTP {response.status_code}\n"
                f"Request URL: {self.base_url}{self._submit_path}\n"
                f"Response body: {response.text[:2000]}",
            )
        response.raise_for_status()

        # Official SDK response: {"data": {"jobId": "..."}}
        resp_json = response.json()
        data_obj = resp_json.get("data", resp_json)
        job_id = data_obj.get("jobId") or data_obj.get("job_id") or data_obj.get("id")
        if not job_id:
            raise ValueError(f"PaddleOCR submit response missing job ID: {resp_json}")
        logger.info(LogModule.LAYOUT, f"PaddleOCR job submitted: {job_id}")
        return str(job_id)

    async def poll_job(self, job_id: str) -> Dict[str, Any]:
        """
        Poll job status until complete or failed.

        The official API wraps the job status inside a ``data`` envelope:
        ``{"data": {"state": "done", "resultUrl": {"jsonUrl": "..."}}}``

        Args:
            job_id: Job ID from submit_job.

        Returns:
            Job result dict (the ``data`` envelope).

        Raises:
            TimeoutError: If max_wait is exceeded.
            RuntimeError: If the job fails.
        """
        if job_id == _INLINE_SYNC_JOB_ID:
            if not self._inline_sync_raw:
                raise RuntimeError("PaddleOCR sync infer result missing after submit")
            return {"state": "done", "_sync_infer_raw": self._inline_sync_raw}

        started = time.monotonic()
        result_path = self._result_path.format(job_id=job_id)

        while True:
            # Allow external cancellation from another thread (e.g. Ctrl+C)
            if self._cancel_event and self._cancel_event.is_set():
                logger.info(LogModule.LAYOUT, f"PaddleOCR poll for job {job_id} cancelled via event")
                raise asyncio.CancelledError(f"PaddleOCR job {job_id} cancelled")

            elapsed = time.monotonic() - started
            if elapsed > self.max_wait:
                raise TimeoutError(f"PaddleOCR job {job_id} timed out after {self.max_wait}s")

            try:
                # Use a shorter timeout for polling to stay responsive to cancellation
                response = await self.client.get(
                    result_path,
                    headers=self._auth_headers(),
                    timeout=httpx.Timeout(connect=15.0, read=30.0, write=15.0, pool=5.0),
                )
            except asyncio.CancelledError:
                logger.info(LogModule.LAYOUT, f"PaddleOCR poll for job {job_id} cancelled")
                raise
            if response.status_code != 200:
                logger.error(
                    LogModule.LAYOUT,
                    f"PaddleOCR poll failed: HTTP {response.status_code} for job {job_id}\n"
                    f"Response body: {response.text[:2000]}",
                )
            response.raise_for_status()
            resp_json = response.json()

            # Response is wrapped in {"data": {...}} per official SDK
            data = resp_json.get("data", resp_json)
            state = str(data.get("state") or data.get("status") or "").lower()

            if state in ("done", "completed", "success", "succeeded"):
                logger.info(LogModule.LAYOUT, f"PaddleOCR job {job_id} completed ({elapsed:.0f}s)")
                return data
            elif state in ("failed", "error", "cancelled"):
                error_msg = data.get("errorMsg") or data.get("error") or data.get("message") or "unknown error"
                raise RuntimeError(f"PaddleOCR job {job_id} failed: {error_msg}")

            logger.debug(LogModule.LAYOUT, f"PaddleOCR job {job_id} state={state}, elapsed={elapsed:.0f}s")
            try:
                await asyncio.sleep(self.poll_interval)
            except asyncio.CancelledError:
                logger.info(LogModule.LAYOUT, f"PaddleOCR poll sleep for job {job_id} cancelled")
                raise

    async def download_result(self, result_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Download the JSONL result from the job completion response.

        The official API returns a JSONL file where each line is a JSON object
        with a ``result`` key containing the per-page layout data.

        Looks for ``resultUrl.jsonUrl``, ``jsonl_url``, or ``result_url``.

        Args:
            result_data: Job completion response (the ``data`` envelope).

        Returns:
            Parsed full result dict with ``layoutParsingResults`` list built
            from the JSONL lines.
        """
        sync_raw = result_data.get("_sync_infer_raw")
        if sync_raw is not None:
            return normalize_sync_infer_response(sync_raw)

        # Official SDK: resultUrl.jsonUrl
        url = (
            result_data.get("resultUrl", {}).get("jsonUrl")
            or result_data.get("jsonl_url")
            or result_data.get("result_url")
            or result_data.get("output_url")
        )
        if not url:
            raise ValueError(f"No result URL found in PaddleOCR response: {result_data}")

        logger.info(LogModule.LAYOUT, f"Downloading PaddleOCR result")

        # The result URL is a Baidu BOS pre-signed URL (already carries an
        # authorization query parameter).  Do NOT send the PaddleOCR API
        # bearer token; BOS requires a *Date* header instead.
        download_headers = {
            "Date": formatdate(timeval=time.time(), localtime=False, usegmt=True),
        }

        response = await self.client.get(url, headers=download_headers)
        if response.status_code != 200:
            logger.error(
                LogModule.LAYOUT,
                f"PaddleOCR result download failed: HTTP {response.status_code}\n"
                f"Request URL: {url}\n"
                f"Response body: {response.text[:2000]}",
            )
        response.raise_for_status()

        # Result is JSONL: one JSON object per line, each with a "result" key
        return self._parse_jsonl_result(response.text)

    @staticmethod
    def _parse_jsonl_result(text: str) -> Dict[str, Any]:
        """Parse JSONL result text into a dict with ``layoutParsingResults`` list."""
        pages: list[Dict[str, Any]] = []
        markdown_parts: list[str] = []
        for line in text.strip().split("\n"):
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
                # Each line: {"result": {...per-page layout...}, "markdown": {...}}
                page_result = obj.get("result", obj)
                pages.append(page_result)
                md_obj = obj.get("markdown", {})
                if md_obj.get("text"):
                    markdown_parts.append(md_obj["text"])
            except Exception:
                pages.append({})
        return {
            "layoutParsingResults": pages,
            "markdown": {"text": "\n\n".join(markdown_parts)},
        }
