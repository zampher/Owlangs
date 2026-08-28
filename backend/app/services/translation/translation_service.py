# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

"""
Translation Service

Handles translation task processing, workflow management, and task lifecycle.
"""

import asyncio
import io
import os
from functools import partial
import shutil
import tempfile
import time
from typing import Any, Dict, List, Optional
from pathlib import Path

from fastapi import HTTPException

from logger import unified_logger as logger
from logger.logger import LogModule
from utils.translation_validator import log_segment_translation_stats
from backend.app.services.task import TaskManager, MSG_LEVEL_ERROR
from backend.app.services.translation.workflow_factory import WorkflowFactory
from backend.app.services.translation.workflow_config_builder import WorkflowConfigBuilder
from backend.app.services.translation.workflow_executor import WorkflowExecutor
from backend.app.services.translation.prompt_service import prompt_service
from backend.app.services.translation.source_preview_service import SourcePreviewService
from backend.app.services.translation.translation_segment_service import TranslationSegmentService
from backend.app.services.translation.chunk_size_service import chunk_size_service
from backend.app.services.download.output_generator import OutputGenerator
from backend.app.config.pagination_config import SOURCE_PREVIEW_SEGMENTS_LIMIT
from backend.config.app_config import get_app_config

# PDF page limit for MinerU; files exceeding this are rejected with a clear message
PDF_MAX_PAGES = 500


def _pdf_too_large_detail(page_count: int) -> str:
    return (
        f"This file is too large ({page_count} pages), exceeding {PDF_MAX_PAGES} pages. "
        "We recommend splitting the file before translation, e.g. using PDFsam."
    )


def _get_pdf_page_count(file_contents: bytes) -> int:
    """
    Get page count of a PDF from its bytes. Uses PyPDF2.
    Returns -1 if unable to read (e.g. not a valid PDF or library missing).
    """
    if not file_contents or len(file_contents) < 100:
        return -1
    try:
        import PyPDF2
        reader = PyPDF2.PdfReader(io.BytesIO(file_contents))
        return len(reader.pages)
    except Exception:
        return -1


class TranslationService:
    """Service for managing translation tasks."""
    
    def __init__(self, task_manager: TaskManager):
        """
        Initialize translation service.
        
        Args:
            task_manager: Task manager instance
        """
        self.task_manager = task_manager
        self.workflow_factory = WorkflowFactory()
        self.workflow_executor = WorkflowExecutor(task_manager)
        self.output_generator = OutputGenerator(task_manager)
        self.source_preview_service = SourcePreviewService(task_manager)
        self.translation_segment_service = TranslationSegmentService(task_manager)

    def _collect_failed_segment_indices_for_retry(self, task_state: Dict[str, Any]) -> List[int]:
        """Indices that need batch retranslation (aligned with frontend Retry filters)."""
        out: List[int] = []
        data = task_state.get("translation_segments") or {}
        segments = data.get("segments") if isinstance(data, dict) else data
        if not isinstance(segments, list):
            return out
        for seg in segments:
            if not isinstance(seg, dict):
                continue
            idx = seg.get("segment_index")
            if idx is None:
                continue
            is_failed = seg.get("is_failed", False)
            needs_retry = seg.get("needs_retry", False)
            is_excluded = seg.get("is_excluded", False)
            status = seg.get("status")
            if (is_failed or needs_retry) and not is_excluded and status != "cleared":
                try:
                    out.append(int(idx))
                except (TypeError, ValueError):
                    continue
        return out

    async def _auto_retry_failed_segments(
        self,
        task_id: str,
        task_state: Dict[str, Any],
        payload: Any,
    ) -> None:
        """
        After main translation completes, batch-retry failed segments automatically.
        Same API as frontend ``retranslateSegmentsBatch``.

        Rounds are controlled by ``segment_auto_retry_rounds`` (not chunk ``retry``).
        Works for both immediate (immersive) and queued execution modes.
        """
        from utils.translation_segments import retranslate_segments_batch
        from utils.translation_validator import refresh_task_state_segment_failure_flags

        seg_rounds_raw = getattr(payload, "segment_auto_retry_rounds", None)
        if seg_rounds_raw is None and isinstance(payload, dict):
            seg_rounds_raw = payload.get("segment_auto_retry_rounds")
        try:
            max_rounds = int(seg_rounds_raw) if seg_rounds_raw is not None else 3
        except (TypeError, ValueError):
            max_rounds = 3
        max_rounds = max(1, min(max_rounds, 10))

        log_segment_translation_stats(task_id, task_state, "before_auto_retry")

        platform_key = getattr(payload, "ai_platform", None) or getattr(payload, "platform_type", None)
        if isinstance(payload, dict):
            platform_key = platform_key or payload.get("ai_platform") or payload.get("platform_type")

        to_lang = getattr(payload, "to_lang", None) or getattr(payload, "target_language", None)
        if isinstance(payload, dict) and not to_lang:
            to_lang = payload.get("to_lang") or payload.get("target_language")

        for attempt in range(max_rounds):
            # Align with immersive Retry: re-validate source vs target before collecting indices.
            # Initial recording may omit flags; batch retry may clear flags when LLM returns
            # same-as-source that should_treat_as_failure still treats as failure on re-check.
            refreshed_failed = refresh_task_state_segment_failure_flags(task_state)
            if refreshed_failed:
                logger.info(
                    LogModule.TRANS,
                    f"[AUTO-RETRY] task={task_id} revalidated segments: "
                    f"{refreshed_failed} marked failed by should_treat_as_failure "
                    f"(before round {attempt + 1})",
                )
            log_segment_translation_stats(
                task_id,
                task_state,
                f"after_refresh_before_collect_round_{attempt + 1}",
            )
            indices = self._collect_failed_segment_indices_for_retry(task_state)
            if not indices:
                logger.info(
                    LogModule.TRANS,
                    f"[AUTO-RETRY] task={task_id} no failed segments left before round {attempt + 1}",
                )
                break
            logger.info(
                LogModule.TRANS,
                f"[AUTO-RETRY] task={task_id} round {attempt + 1}/{max_rounds} "
                f"batch-retry count={len(indices)}",
            )
            task_state["message"] = f"Auto-retry failed segments ({attempt + 1}/{max_rounds})..."
            try:
                self.task_manager.update_task(
                    task_id,
                    {"message": task_state["message"], "status": "processing"},
                )
            except Exception:
                pass
            try:
                await retranslate_segments_batch(
                    task_id,
                    indices,
                    platform_key=platform_key,
                    task_state=task_state,
                    user_prompt=None,
                    to_lang_from_frontend=to_lang,
                )
                # Batch retry mutates segment dicts in-place (same object as task_manager's task).
                # Explicit update_task so any merge/persist path and debugging see a write boundary.
                try:
                    ts_data = task_state.get("translation_segments")
                    self.task_manager.update_task(
                        task_id,
                        {"translation_segments": ts_data},
                    )
                    n_seg = 0
                    if isinstance(ts_data, dict):
                        seg_list = ts_data.get("segments")
                        if isinstance(seg_list, list):
                            n_seg = len(seg_list)
                    logger.info(
                        LogModule.TRANS,
                        f"[AUTO-RETRY] task={task_id} persisted translation_segments "
                        f"after round {attempt + 1} (segment count={n_seg})",
                    )
                    log_segment_translation_stats(
                        task_id,
                        task_state,
                        f"after_batch_retry_round_{attempt + 1}",
                    )
                except Exception as sync_exc:
                    logger.warning(
                        LogModule.TRANS,
                        f"[AUTO-RETRY] task={task_id} translation_segments persist failed: {sync_exc}",
                    )
            except Exception as exc:
                logger.error(
                    LogModule.TRANS,
                    f"[AUTO-RETRY] task={task_id} round {attempt + 1} error: {exc}",
                    exc_info=True,
                )
                break

        log_segment_translation_stats(task_id, task_state, "auto_retry_finished")
    
    async def _test_llm_connectivity(self, payload: Any, task_id: str, task_state: Dict[str, Any]) -> bool:
        """
        Test LLM platform connectivity before starting translation.
        
        Reuses the existing test_ai_platform_connectivity logic from auth/ai_platform_service,
        which handles different platform types (OpenAI, Ollama, Anthropic, Google, etc.).
        
        Returns True if connection is successful or if test is skipped (e.g. missing config).
        Returns False if connection fails; task_state is updated to 'failed' accordingly.
        """
        base_url = getattr(payload, "base_url", None) if hasattr(payload, "base_url") else None
        model_id = getattr(payload, "model_id", None) if hasattr(payload, "model_id") else None
        api_key = getattr(payload, "api_key", None) if hasattr(payload, "api_key") else None
        
        if not base_url or not model_id:
            logger.warning(
                LogModule.WORKFLOW,
                f"[LLM-TEST] Task {task_id}: Missing base_url or model_id, skipping connectivity test"
            )
            return True
        
        # Determine platform type (api_protocol) for test_ai_platform_connectivity
        platform_type = "openai"  # default fallback
        try:
            from backend.app.services.platform.platform_service import platform_service
            platform_key = platform_service.determine_platform_key(base_url, model_id)
            detected_type = platform_service.get_api_protocol(base_url, model_id, platform_key)
            if detected_type:
                platform_type = detected_type
        except Exception as e:
            logger.warning(
                LogModule.WORKFLOW,
                f"[LLM-TEST] Task {task_id}: Failed to determine platform type: {e}, using default 'openai'"
            )
        
        logger.info(
            LogModule.WORKFLOW,
            f"[LLM-TEST] Task {task_id}: Testing connectivity to {platform_type} platform "
            f"at {base_url} with model {model_id}"
        )
        
        # Determine platform key for updating QuickSettings/Settings status
        platform_key_for_status = None
        try:
            from backend.app.services.platform.platform_service import platform_service
            platform_key_for_status = platform_service.determine_platform_key(base_url, model_id)
        except Exception:
            pass
        if not platform_key_for_status:
            platform_key_for_status = platform_type  # fallback to api_protocol
        
        # Look up requires_api_key from platform config
        requires_api_key = True
        try:
            from backend.config.config_loader import get_unified_config
            unified_config = get_unified_config()
            pk = platform_key_for_status
            if pk:
                platform_cfg = unified_config.platforms.get_platform_config(pk)
                if platform_cfg:
                    requires_api_key = getattr(platform_cfg, 'requires_api_key', True)
        except Exception:
            pass

        # Frontend often omits api_key (non-admin / raw-secrets unavailable). Resolve
        # from secrets.json like Agent does — otherwise chat probe sends no Bearer and
        # DeepSeek returns 401, which looks like "API key lost".
        api_key_str = (api_key or "").strip() if isinstance(api_key, str) else ""
        if not api_key_str:
            try:
                from backend.config.config_loader import get_unified_config

                unified_config = get_unified_config()
                pk = platform_key_for_status
                if pk:
                    api_key_str = (unified_config.get_platform_api_key(pk) or "").strip()
                if not api_key_str:
                    # Fallback: secrets map by platform key
                    from backend.config.secrets_manager import get_secrets_manager

                    secrets = get_secrets_manager()
                    if pk:
                        api_key_str = (secrets.get_api_key(pk) or "").strip()
                logger.info(
                    LogModule.WORKFLOW,
                    f"[LLM-TEST] Task {task_id}: resolved api_key from secrets "
                    f"platform={pk!r} len={len(api_key_str)} empty={not bool(api_key_str)}",
                )
            except Exception as resolve_err:
                logger.warning(
                    LogModule.WORKFLOW,
                    f"[LLM-TEST] Task {task_id}: failed to resolve api_key from secrets: {resolve_err}",
                )

        # Read connectivity test timeout values from platform config
        test_connect_timeout = 30
        test_request_timeout = 10
        try:
            from backend.config.config_loader import get_unified_config
            unified_config = get_unified_config()
            pk = platform_key_for_status or platform_type
            if pk:
                platform_cfg = unified_config.platforms.get_platform_config(pk)
                if platform_cfg:
                    test_connect_timeout = getattr(platform_cfg, 'test_connect_timeout', 30) or 30
                    test_request_timeout = getattr(platform_cfg, 'test_request_timeout', 10) or 10
        except Exception:
            pass

        try:
            from backend.auth.ai_platform_service import test_ai_platform_connectivity
            result = await test_ai_platform_connectivity(
                platform_type=platform_type,
                base_url=base_url,
                model_name=model_id,
                api_key=api_key_str,
                detect_max_tokens=False,  # Keep test fast; max_tokens detection is optional
                requires_api_key=requires_api_key,
                test_connect_timeout=test_connect_timeout,
                test_request_timeout=test_request_timeout,
            )
            
            # Update QuickSettings / Settings LLM status regardless of success/failure
            try:
                from backend.config.ai_platform_status import update_platform_status
                update_platform_status(
                    platform_key_for_status,
                    result.get("success", False),
                    result.get("error"),
                )
                # Signal frontend that platform status has changed so it can refresh
                task_state["platform_status_changed"] = True
                logger.debug(
                    LogModule.WORKFLOW,
                    f"[LLM-TEST] Task {task_id}: Updated platform status for '{platform_key_for_status}' "
                    f"to isApiAvailable={result.get('success', False)}"
                )
            except Exception as status_err:
                logger.warning(
                    LogModule.WORKFLOW,
                    f"[LLM-TEST] Task {task_id}: Failed to update platform status: {status_err}"
                )
            
            if result.get("success"):
                logger.info(
                    LogModule.WORKFLOW,
                    f"[LLM-TEST] Task {task_id}: Connectivity test passed - {result.get('message', 'OK')}"
                )
                return True
            else:
                error_msg = result.get("error", "Unknown error")
                user_message = result.get("message", error_msg)
                logger.error(
                    LogModule.WORKFLOW,
                    f"[LLM-TEST] Task {task_id}: Connectivity test failed - {error_msg}"
                )
                task_state["status"] = "failed"
                task_state["error"] = error_msg
                task_state["message"] = f"LLM platform connection test failed: {user_message}"
                task_state["message_level"] = MSG_LEVEL_ERROR
                task_state["llm_error"] = error_msg
                self.task_manager.update_task(task_id, {
                    "status": "failed",
                    "error": error_msg,
                    "message": f"LLM platform connection test failed: {user_message}",
                    "message_level": MSG_LEVEL_ERROR,
                })
                return False

        except Exception as e:
            logger.error(
                LogModule.WORKFLOW,
                f"[LLM-TEST] Task {task_id}: Connectivity test threw exception: {e}",
                exc_info=True,
            )
            error_msg = str(e)
            # Also update status on exception
            try:
                from backend.config.ai_platform_status import update_platform_status
                update_platform_status(platform_key_for_status, False, error_msg)
                task_state["platform_status_changed"] = True
            except Exception:
                pass
            task_state["status"] = "failed"
            task_state["error"] = error_msg
            task_state["message"] = f"LLM platform connection test failed: {error_msg}"
            task_state["message_level"] = MSG_LEVEL_ERROR
            task_state["llm_error"] = error_msg
            self.task_manager.update_task(task_id, {
                "status": "failed",
                "error": error_msg,
                "message": f"LLM platform connection test failed: {error_msg}",
                "message_level": MSG_LEVEL_ERROR,
            })
            return False

    def _build_llm_config_for_repair(self, payload: Any) -> Dict[str, Any]:
        """
        Build LLM config for formula repair from payload.
        Gets API protocol from platform configuration.
        
        Args:
            payload: Task payload with translation parameters
            
        Returns:
            Dictionary with LLM configuration for repair
        """
        base_url = getattr(payload, "base_url", None) if hasattr(payload, "base_url") else None
        model_id = getattr(payload, "model_id", None) if hasattr(payload, "model_id") else None
        
        # Get API protocol from platform configuration
        api_type = "openai"  # default
        try:
            from backend.app.services.platform.platform_service import platform_service
            api_protocol = platform_service.get_api_protocol(base_url, model_id)
            logger.debug(LogModule.CONFIG, f"[REPAIR-CONFIG] Platform lookup: base_url={base_url}, model_id={model_id}, api_protocol={api_protocol}")
            if api_protocol:
                api_type = api_protocol
        except Exception as e:
            logger.warning(LogModule.CONFIG, f"[REPAIR-CONFIG] Failed to get api_protocol: {e}")
        
        logger.debug(LogModule.CONFIG, f"[REPAIR-CONFIG] Final config: api_type={api_type}, base_url={base_url}, model_id={model_id}")
        
        return {
            "base_url": base_url,
            "model_id": model_id,
            "api_key": getattr(payload, "api_key", None) if hasattr(payload, "api_key") else None,
            "api_type": api_type,
            "temperature": getattr(payload, "temperature", 0.3) if hasattr(payload, "temperature") else 0.3,
            "concurrent": getattr(payload, "concurrent", 1) if hasattr(payload, "concurrent") else 1,
            "connect_timeout": getattr(payload, "connect_timeout", 15) if hasattr(payload, "connect_timeout") else 15,
            "timeout": getattr(payload, "timeout", 120) if hasattr(payload, "timeout") else 120,
            "thinking": getattr(payload, "thinking", "default") if hasattr(payload, "thinking") else "default",
            "retry": getattr(payload, "retry", 3) if hasattr(payload, "retry") else 3,
        }
    
    async def _run_translation_task_wrapper(
        self,
        task_id: str,
        payload: Any,
        file_contents: bytes,
        original_filename: str,
        temp_dir: str,
    ) -> None:
        """Shared wrapper around process_translation_task with exception handling."""
        try:
            await self.process_translation_task(
                task_id=task_id,
                payload=payload,
                file_contents=file_contents,
                original_filename=original_filename,
                temp_dir=temp_dir,
            )
        except NotImplementedError as not_impl_error:
            task_state = self.task_manager.get_task(task_id)
            if task_state and task_state.get("status") not in ["completed"]:
                logger.warning(
                    LogModule.WORKFLOW,
                    f"Non-critical NotImplementedError in background task {task_id} (Windows limitation): {not_impl_error}",
                )
                if task_state.get("status") not in ["failed"]:
                    self.task_manager.add_log(
                        task_id,
                        "warning",
                        f"Non-critical cleanup error (Windows limitation): {str(not_impl_error)}",
                    )
            else:
                logger.warning(
                    LogModule.WORKFLOW,
                    f"[PLAYWRIGHT] Task {task_id}: NotImplementedError during cleanup (Windows asyncio limitation, non-critical): {not_impl_error}",
                )
        except Exception as e:
            logger.error(LogModule.WORKFLOW, f"Uncaught exception in background task {task_id}: {e}", exc_info=True)
            task_state = self.task_manager.get_task(task_id)
            if task_state and task_state.get("status") not in ["completed", "failed"]:
                error_text = str(e)
                if (
                    "UNEXPECTED_EOF_WHILE_READING" in error_text
                    or "EOF occurred in violation of protocol" in error_text
                ):
                    error_with_hint = (
                        f"{error_text}. Please check your network and try disabling VPN/proxy, then retry."
                    )
                elif "ReadTimeout" in error_text or "Read timed out" in error_text:
                    error_with_hint = (
                        "The MinerU service is taking too long to respond. "
                        "This may be caused by GPU unavailability or high server load. "
                        "Please check the MinerU server status and retry."
                    )
                elif "timed out after" in error_text.lower():
                    # asyncio.wait_for / task-level timeout
                    error_with_hint = error_text
                else:
                    error_with_hint = error_text
                task_state["status"] = "failed"
                task_state["error"] = error_text
                task_state["message_level"] = MSG_LEVEL_ERROR
                llm_error = task_state.get("llm_error")
                if llm_error:
                    task_state["message"] = f"Translation failed: {llm_error}"
                else:
                    task_state["message"] = f"Task error: {error_with_hint}"
                self.task_manager.add_log(task_id, "error", f"Uncaught exception: {error_text}")
    
    async def _auto_export_queued_task_outputs(
        self,
        task_id: str,
        task_state: Dict[str, Any],
    ) -> None:
        """Generate and stash all export formats for queued tasks (incl. both PDF variants)."""
        segs = task_state.get("translation_segments")
        if not isinstance(segs, dict) or not segs.get("segments"):
            logger.info(
                LogModule.WORKFLOW,
                f"[TRANSLATION-SERVICE] Task {task_id}: skip queued auto-export (no segments)",
            )
            return
        try:
            from backend.app.services.download.download_service import DownloadService

            download_service = DownloadService(self.task_manager)
            result = await download_service.persist_completed_task_outputs_to_stash(
                task_id,
                allow_processing_status=True,
                update_progress=True,
            )
            task_state["download_ready"] = True
            stashed = result.get("stashed") or []
            errors = result.get("errors") or []
            logger.info(
                LogModule.WORKFLOW,
                f"[TRANSLATION-SERVICE] Task {task_id}: queued auto-export stashed={stashed} "
                f"errors={len(errors)}",
            )
            if errors:
                self.task_manager.add_log(
                    task_id,
                    "warning",
                    f"Some export formats failed: {'; '.join(errors[:3])}",
                )
        except HTTPException as http_exc:
            logger.warning(
                LogModule.WORKFLOW,
                f"[TRANSLATION-SERVICE] Task {task_id}: queued auto-export skipped: {http_exc.detail}",
            )
        except Exception as exc:
            logger.warning(
                LogModule.WORKFLOW,
                f"[TRANSLATION-SERVICE] Task {task_id}: queued auto-export failed: {exc}",
                exc_info=True,
            )
            self.task_manager.add_log(
                task_id,
                "warning",
                f"Auto export failed: {exc}",
            )

    async def start_translation_task(
        self,
        task_id: str,
        payload: Any,
        file_contents: bytes,
        original_filename: str,
        *,
        execution_mode: str = "immediate",
        owner_username: Optional[str] = None,
        relative_path: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Start a translation task in the background.
        
        Args:
            task_id: Unique task identifier
            payload: Task payload (workflow config, translation params, etc.)
            file_contents: File content bytes
            original_filename: Original filename
            execution_mode: ``immediate`` runs as today; ``queued`` waits for in-process workers.
            owner_username: Authenticated username for task list filtering; None for guest submissions.
            
        Returns:
            Response dictionary with task_id and status
            
        Raises:
            HTTPException: If task creation fails
        """
        logger.info(LogModule.WORKFLOW, f"[TRANSLATION-SERVICE] Starting translation task: task_id={task_id}, filename={original_filename}, "
                   f"file_size={len(file_contents)} bytes")
        
        if self.task_manager.get_task(task_id) is not None:
            logger.error(LogModule.WORKFLOW, f"[TRANSLATION-SERVICE] Task ID already exists: task_id={task_id}")
            from fastapi import HTTPException
            raise HTTPException(status_code=429, detail=f"Task ID '{task_id}' already exists.")
        
        # Create task state
        try:
            task_state = self.task_manager.create_task(task_id)
            task_state["created_at"] = asyncio.get_event_loop().time()
            
            # Add initial log
            self.task_manager.add_log(task_id, "info", "Task created and initialized")
            logger.info(LogModule.WORKFLOW, f"[TRANSLATION-SERVICE] Task state created: task_id={task_id}")
        except Exception as e:
            logger.error(LogModule.WORKFLOW, f"[TRANSLATION-SERVICE] Failed to create task state: task_id={task_id}, error={e}", exc_info=True)
            from fastapi import HTTPException
            raise HTTPException(status_code=500, detail=f"Failed to create task state: {str(e)}")
        
        # Create temp directory and store file
        try:
            temp_dir = tempfile.mkdtemp(prefix=f"owlangs_{task_id}_")
            original_file_path = os.path.join(temp_dir, original_filename)
            logger.info(LogModule.WORKFLOW, f"[TRANSLATION-SERVICE] Created temp directory: task_id={task_id}, temp_dir={temp_dir}")
        except Exception as e:
            logger.error(LogModule.WORKFLOW, f"[TRANSLATION-SERVICE] Failed to create temp directory: task_id={task_id}, error={e}", exc_info=True)
            self.task_manager.cleanup_task_resources(task_id)
            from fastapi import HTTPException
            raise HTTPException(status_code=500, detail=f"Failed to create temp directory: {str(e)}")
        
        # Write file content to temp directory
        try:
            with open(original_file_path, 'wb') as f:
                f.write(file_contents)
            file_size_on_disk = os.path.getsize(original_file_path)
            logger.info(LogModule.WORKFLOW, f"[TRANSLATION-SERVICE] File written to disk: task_id={task_id}, path={original_file_path}, "
                       f"written_size={file_size_on_disk} bytes, expected_size={len(file_contents)} bytes")
            if file_size_on_disk != len(file_contents):
                logger.warning(LogModule.WORKFLOW, f"[TRANSLATION-SERVICE] File size mismatch: task_id={task_id}, written={file_size_on_disk}, expected={len(file_contents)}")
            # Keep a durable copy outside OS TEMP so Typst overlay survives Temp cleanup.
            if original_filename.lower().endswith(".pdf"):
                try:
                    from app.services.download.download_service import (
                        persist_original_pdf_durable,
                    )

                    persist_original_pdf_durable(
                        task_state, task_id, original_file_path
                    )
                except Exception as durable_err:
                    logger.warning(
                        LogModule.WORKFLOW,
                        f"[TRANSLATION-SERVICE] Task {task_id}: durable PDF persist "
                        f"skipped: {durable_err}",
                    )
            try:
                from layout.pdf_renderer.typst_overlay.segment_font_metrics import (
                    cache_overlay_source_image_size,
                )

                cache_overlay_source_image_size(task_state, original_file_path)
            except Exception as cache_err:
                logger.debug(
                    LogModule.WORKFLOW,
                    f"[TRANSLATION-SERVICE] overlay_source_image_size cache skipped: {cache_err}",
                )
        except Exception as e:
            logger.error(LogModule.WORKFLOW, f"[TRANSLATION-SERVICE] Failed to write file to disk: task_id={task_id}, path={original_file_path}, error={e}", exc_info=True)
            # Cleanup
            if os.path.exists(temp_dir):
                shutil.rmtree(temp_dir, ignore_errors=True)
            self.task_manager.cleanup_task_resources(task_id)
            from fastapi import HTTPException
            raise HTTPException(status_code=500, detail=f"Failed to write file to disk: {str(e)}")
        
        # Compute page count early for both validation and frontend warning
        page_count = 0
        if original_filename.lower().endswith(".pdf"):
            page_count = _get_pdf_page_count(file_contents)
        
        # Reject PDFs exceeding page limit (MinerU cannot handle very large files)
        # Exception: mineru/mineru_local engines support automatic PDF splitting in ConverterMineru.
        if page_count > PDF_MAX_PAGES:
            convert_engine = getattr(payload, 'convert_engine', 'mineru') or 'mineru'
            if convert_engine in ("mineru", "mineru_local"):
                logger.info(
                    LogModule.WORKFLOW,
                    f"[TRANSLATION-SERVICE] Large PDF allowed for splitting: task_id={task_id}, "
                    f"pages={page_count}, engine={convert_engine}, will be split by ConverterMineru"
                )
            else:
                if os.path.exists(temp_dir):
                    shutil.rmtree(temp_dir, ignore_errors=True)
                self.task_manager.cleanup_task_resources(task_id)
                from fastapi import HTTPException
                logger.warning(
                    LogModule.WORKFLOW,
                    f"[TRANSLATION-SERVICE] Rejected PDF: task_id={task_id}, pages={page_count}, max={PDF_MAX_PAGES}"
                )
                raise HTTPException(status_code=400, detail=_pdf_too_large_detail(page_count))
        
        # Update task state with all necessary fields
        task_state.update({
            "is_processing": execution_mode != "queued",
            "status_message": "Task initializing...",
            "error_flag": False,
            "download_ready": False,
            "workflow_instance": None,
            "original_filename_stem": Path(original_filename).stem,
            "original_filename": original_filename,
            "original_relative_path": relative_path or "",
            "task_start_time": time.time(),
            "task_end_time": 0,
            "current_task_ref": None,
            "temp_dir": temp_dir,
            "downloadable_files": {},
            "attachment_files": {},
            "convert_only": getattr(payload, 'skip_translate', False) if hasattr(payload, 'skip_translate') else False,
            "is_format_conversion": getattr(payload, 'skip_translate', False) if hasattr(payload, 'skip_translate') else False,
            "original_file_path": original_file_path,
            # Capture LLM platform config snapshot for downstream tools (e.g. LaTeX repair)
            # Get API protocol from platform configuration
            "llm_config_for_repair": self._build_llm_config_for_repair(payload),
            # Source preview placeholder
            "source_preview": {
                "segments": [],
                "total_segments": 0,
                "ready": False,
            },
            "execution_mode": execution_mode,
            "owner_username": owner_username,
            "output_suffix": get_app_config().converter_output_suffix if getattr(payload, 'skip_translate', False) else get_app_config().translator_output_suffix,
        })
        
        # Store page_count early so the frontend can show large-file warnings
        # before format conversion completes.
        if page_count > 0:
            task_state["page_count"] = page_count
            logger.info(
                LogModule.WORKFLOW,
                f"[TRANSLATION-SERVICE] Stored page_count={page_count} in task_state, "
                f"task_id={task_id}"
            )
        
        self.task_manager.add_log(task_id, "info", f"Created temporary directory: {temp_dir}")
        
        if execution_mode == "queued":
            task_state["queued_translation_payload"] = payload
            task_state["queued_at"] = time.time()
            task_state["status"] = "queued"
            task_state["progress"] = 0
            task_state["message"] = "Waiting in queue..."
            self.task_manager.add_log(task_id, "info", "Task queued for background execution")
            try:
                from backend.app.services.translation.translation_execution_queue import enqueue_translation_task

                await enqueue_translation_task(task_id)
            except Exception as e:
                logger.error(
                    LogModule.WORKFLOW,
                    f"[TRANSLATION-SERVICE] Failed to enqueue task: task_id={task_id}, error={e}",
                    exc_info=True,
                )
                self.task_manager.cleanup_task_resources(task_id)
                if os.path.exists(temp_dir):
                    shutil.rmtree(temp_dir, ignore_errors=True)
                from fastapi import HTTPException

                raise HTTPException(status_code=500, detail=f"Failed to enqueue translation task: {str(e)}")
            return {
                "task_started": True,
                "task_id": task_id,
                "execution_mode": "queued",
                "message": "Translation task accepted and queued.",
            }
        
        # Start background processing task (immediate mode)
        try:
            async def _task_wrapper():
                await self._run_translation_task_wrapper(
                    task_id=task_id,
                    payload=payload,
                    file_contents=file_contents,
                    original_filename=original_filename,
                    temp_dir=temp_dir,
                )

            task_ref = asyncio.create_task(_task_wrapper())

            def task_done_callback(task):
                """Callback to handle task completion and log any exceptions."""
                try:
                    if task.done():
                        if task.cancelled():
                            logger.info(LogModule.WORKFLOW, f"Background task {task_id} was cancelled")
                            return
                        exception = task.exception()
                        if exception:
                            logger.warning(LogModule.WORKFLOW, f"Background task {task_id} completed with exception: {exception}")
                except asyncio.CancelledError:
                    logger.info(LogModule.WORKFLOW, f"Background task {task_id} cancellation detected in callback")
                except Exception as callback_error:
                    logger.warning(LogModule.WORKFLOW, f"Error in task done callback for {task_id}: {callback_error}")

            task_ref.add_done_callback(task_done_callback)
            task_state["current_task_ref"] = task_ref
            task_state["is_processing"] = True
            task_state["started_at"] = asyncio.get_event_loop().time()

            return {
                "task_started": True,
                "task_id": task_id,
                "execution_mode": "immediate",
                "message": "Translation task started successfully, please wait...",
            }
        except Exception as e:
            # Clean up on error
            logger.error(LogModule.WORKFLOW, f"[TRANSLATION-SERVICE] Exception in start_translation_task: task_id={task_id}, filename={original_filename}, error={e}", exc_info=True)
            self.task_manager.cleanup_task_resources(task_id)
            if os.path.exists(temp_dir):
                try:
                    shutil.rmtree(temp_dir, ignore_errors=True)
                    logger.info(LogModule.WORKFLOW, f"[TRANSLATION-SERVICE] Cleaned up temp directory: task_id={task_id}, temp_dir={temp_dir}")
                except Exception as cleanup_error:
                    logger.warning(LogModule.WORKFLOW, f"[TRANSLATION-SERVICE] Failed to cleanup temp directory: task_id={task_id}, temp_dir={temp_dir}, error={cleanup_error}")
            from fastapi import HTTPException
            raise HTTPException(status_code=500, detail=f"Failed to start translation task: {str(e)}")
    
    async def process_queued_task(self, task_id: str) -> None:
        """
        Picked up by queue workers: transition from ``queued`` to the same background
        processing path as immediate mode, awaiting completion so the worker slot is released.
        """
        task_state = self.task_manager.get_task(task_id)
        if not task_state:
            logger.info(
                LogModule.WORKFLOW,
                f"[TRANSLATION-SERVICE] Queued runner: task {task_id} no longer exists (released or cancelled)",
            )
            return
        if task_state.get("status") != "queued":
            logger.info(
                LogModule.WORKFLOW,
                f"[TRANSLATION-SERVICE] Queued runner: task {task_id} has status {task_state.get('status')!r}, skip",
            )
            return
        payload = task_state.get("queued_translation_payload")
        original_filename = task_state.get("original_filename")
        temp_dir = task_state.get("temp_dir")
        original_file_path = task_state.get("original_file_path")
        if payload is None or not original_filename or not temp_dir or not original_file_path:
            logger.error(
                LogModule.WORKFLOW,
                f"[TRANSLATION-SERVICE] Queued runner: incomplete state for task_id={task_id}",
            )
            task_state["status"] = "failed"
            task_state["message"] = "Internal error: queued task payload missing"
            return
        try:
            with open(original_file_path, "rb") as f:
                file_contents = f.read()
        except Exception as e:
            logger.error(
                LogModule.WORKFLOW,
                f"[TRANSLATION-SERVICE] Queued runner: failed to read file for task_id={task_id}: {e}",
                exc_info=True,
            )
            task_state["status"] = "failed"
            task_state["message"] = f"Failed to read uploaded file: {e}"
            return

        task_state["status_message"] = "Task initializing..."
        task_state["message"] = "Translation in progress..."
        self.task_manager.add_log(task_id, "info", "Queue worker started processing")

        async def _task_wrapper():
            await self._run_translation_task_wrapper(
                task_id=task_id,
                payload=payload,
                file_contents=file_contents,
                original_filename=original_filename,
                temp_dir=temp_dir,
            )

        task_ref = asyncio.create_task(_task_wrapper())

        def task_done_callback(task):
            try:
                if task.done() and not task.cancelled():
                    exc = task.exception()
                    if exc:
                        logger.warning(
                            LogModule.WORKFLOW,
                            f"Background task {task_id} (queued) completed with exception: {exc}",
                        )
            except Exception as callback_error:
                logger.warning(
                    LogModule.WORKFLOW,
                    f"Error in task done callback for {task_id}: {callback_error}",
                )

        task_ref.add_done_callback(task_done_callback)
        task_state["current_task_ref"] = task_ref
        task_state["is_processing"] = True
        task_state["started_at"] = asyncio.get_event_loop().time()
        await task_ref

    async def process_translation_task(
        self,
        task_id: str,
        payload: Any,
        file_contents: bytes,
        original_filename: str,
        temp_dir: str
    ):
        """
        Process a translation task in the background.
        
        This method gradually migrates logic from app_routes_service._process_translation_task.
        Currently uses new services for workflow creation, but delegates execution to original implementation.
        
        Args:
            task_id: Unique task identifier
            payload: Task payload
            file_contents: File content bytes
            original_filename: Original filename
            temp_dir: Temporary directory path
        """
        import os
        import pathlib
        import asyncio
        from backend.config.translation_config import get_default_deep_split
        
        task_state = self.task_manager.get_task(task_id)
        if not task_state:
            logger.warning(LogModule.WORKFLOW, f"[TRANSLATION-SERVICE] Task {task_id} not found in task state")
            return

        # If this Translate task is linked to a previous Convert/Extract task, reuse cached assets.
        # This is critical for MOBI/EPUB image rendering: images are not translated and must be
        # carried over so Translate phase segments can include image placeholders consistently.
        try:
            convert_task_id = getattr(payload, "convert_task_id", None)
            if not convert_task_id and isinstance(payload, dict):
                convert_task_id = payload.get("convert_task_id")

            logger.info(
                LogModule.TRANS,
                f"[TRANSLATION-SERVICE] Task {task_id}: process_translation_task starting with convert_task_id={convert_task_id}"
            )

            if convert_task_id:
                convert_state = self.task_manager.get_task(convert_task_id)
                if isinstance(convert_state, dict):
                    import copy

                    # copy_source_only translate tasks mark every segment excluded; real Translate must
                    # inherit exclusion metadata from the upstream format-convert task instead.
                    exclusion_source = convert_state
                    effective_convert_task_id = convert_task_id
                    if convert_state.get("copy_source_only"):
                        upstream_id = convert_state.get("convert_task_id")
                        if upstream_id and upstream_id != convert_task_id:
                            upstream_state = self.task_manager.get_task(upstream_id)
                            if isinstance(upstream_state, dict):
                                effective_convert_task_id = upstream_id
                                if upstream_state.get("segments_metadata"):
                                    exclusion_source = upstream_state
                                logger.info(
                                    LogModule.TRANS,
                                    f"[TRANSLATION-SERVICE] Task {task_id}: convert_task_id={convert_task_id} "
                                    f"was copy_source_only; using exclusion metadata from upstream {upstream_id}",
                                )

                    copied_keys = []
                    for k in (
                        "image_data_map",
                        "mobi_image_data_map",
                        "mobi_html_templates",
                        "mobi_image_segments_info",
                    ):
                        if k in convert_state and k not in task_state:
                            task_state[k] = convert_state[k]
                            copied_keys.append(k)
                    
                    # CRITICAL: Copy segments_metadata to preserve excluded_segments and excluded_segment_indices
                    # This ensures user-selected exclusions from Convert phase are preserved in Translate phase
                    # Use deep copy to ensure nested dicts (excluded_segments) are properly copied
                    if "segments_metadata" in exclusion_source:
                        task_state["segments_metadata"] = copy.deepcopy(
                            exclusion_source["segments_metadata"]
                        )
                        excluded_segments_count = len(
                            exclusion_source.get("segments_metadata", {}).get("excluded_segments", {})
                        )
                        excluded_indices_count = len(
                            exclusion_source.get("segments_metadata", {}).get("excluded_segment_indices", [])
                        )
                        if excluded_segments_count > 0 or excluded_indices_count > 0:
                            logger.info(
                                LogModule.TRANS,
                                f"[TRANSLATION-SERVICE] Task {task_id}: Copied segments_metadata from "
                                f"convert_task_id={effective_convert_task_id}: "
                                f"{excluded_segments_count} excluded_segments (dict), "
                                f"{excluded_indices_count} excluded_segment_indices (list)",
                            )
                            copied_keys.append("segments_metadata")
                    
                    # CRITICAL: Copy source_chunks_cache from Convert phase to translation phase
                    # This ensures record_translation_segments uses the correct source_segments indexed by segment_index
                    if "source_chunks_cache" in convert_state:
                        task_state["source_chunks_cache"] = convert_state["source_chunks_cache"].copy()
                        cache_segments_count = len(convert_state.get("source_chunks_cache", {}).get("segments", []))
                        if cache_segments_count > 0:
                            logger.info(
                                LogModule.TRANS,
                                f"[TRANSLATION-SERVICE] Task {task_id}: Copied source_chunks_cache from convert_task_id={convert_task_id}: "
                                f"{cache_segments_count} segments (indexed by segment_index)"
                            )
                            copied_keys.append("source_chunks_cache")
                    
                    # CRITICAL: Copy chunk_to_segment_map so markdown translator can map chunks to segments.
                    # Without this, _prepare_markdown_based_preview would be run and would decode document_original
                    # as UTF-8, which fails when original file is binary (e.g. PNG image).
                    if "chunk_to_segment_map" in convert_state and convert_state["chunk_to_segment_map"]:
                        task_state["chunk_to_segment_map"] = convert_state["chunk_to_segment_map"]
                        map_len = len(convert_state["chunk_to_segment_map"])
                        logger.info(
                            LogModule.TRANS,
                            f"[TRANSLATION-SERVICE] Task {task_id}: Copied chunk_to_segment_map from convert_task_id={convert_task_id}: {map_len} chunks"
                        )
                        copied_keys.append("chunk_to_segment_map")
                    
                    # CRITICAL: Copy layout_prepared_chunks so Translate uses Extract-phase exclusion (no re-detection).
                    # Rebuilding chunks in workflow would drop is_excluded and segment_indices and cause wrong exclusions.
                    if "layout_prepared_chunks" in convert_state:
                        task_state["layout_prepared_chunks"] = convert_state["layout_prepared_chunks"]
                        chunk_count = len(convert_state["layout_prepared_chunks"])
                        logger.info(
                            LogModule.TRANS,
                            f"[TRANSLATION-SERVICE] Task {task_id}: Copied layout_prepared_chunks from convert_task_id={convert_task_id}: "
                            f"{chunk_count} chunks (preserving is_excluded and segment_indices from Extract)"
                        )
                        copied_keys.append("layout_prepared_chunks")
                    if "layout_chunk_block_map" in convert_state:
                        task_state["layout_chunk_block_map"] = convert_state["layout_chunk_block_map"]
                        copied_keys.append("layout_chunk_block_map")
                    if "segment_layout_block_map" in convert_state:
                        task_state["segment_layout_block_map"] = convert_state["segment_layout_block_map"]
                        copied_keys.append("segment_layout_block_map")
                    if "layout_chunk_block_texts" in convert_state:
                        task_state["layout_chunk_block_texts"] = convert_state["layout_chunk_block_texts"]
                        copied_keys.append("layout_chunk_block_texts")
                    if "layout_markdown_source" in convert_state:
                        task_state["layout_markdown_source"] = convert_state["layout_markdown_source"]
                        copied_keys.append("layout_markdown_source")
                    for layout_key in (
                        "layout_source_zip",
                        "layout_document",
                        "mineru_zip_path",
                        "mineru_extract_dir",
                        "paddle_zip_path",
                        "source_input_type",
                    ):
                        if layout_key in convert_state and convert_state.get(layout_key) is not None:
                            if layout_key not in task_state or task_state.get(layout_key) is None:
                                task_state[layout_key] = convert_state[layout_key]
                                copied_keys.append(layout_key)
                    # Disk paths from convert live under convert's temp_dir; copy into
                    # this task's temp so RELEASE/OS cleanup of convert temp cannot
                    # break Typst overlay / layout reuse later.
                    current_temp = task_state.get("temp_dir")
                    if current_temp and os.path.isdir(current_temp):
                        from app.services.download.download_service import (
                            _materialize_path_into_temp,
                        )

                        for disk_key in (
                            "mineru_zip_path",
                            "mineru_extract_dir",
                            "paddle_zip_path",
                        ):
                            if disk_key in copied_keys or disk_key in task_state:
                                _materialize_path_into_temp(
                                    task_state, task_id, disk_key, current_temp
                                )
                        # Also keep a durable copy of convert original PDF if ours vanishes later.
                        convert_pdf = convert_state.get("original_file_path")
                        own_pdf = task_state.get("original_file_path")
                        if (
                            convert_pdf
                            and os.path.isfile(convert_pdf)
                            and own_pdf
                            and os.path.isdir(current_temp)
                        ):
                            backup = os.path.join(
                                current_temp,
                                f"_convert_source_{Path(convert_pdf).name}",
                            )
                            try:
                                if not os.path.isfile(backup):
                                    shutil.copy2(convert_pdf, backup)
                                    task_state["_convert_original_file_backup"] = backup
                                from app.services.download.download_service import (
                                    persist_original_pdf_durable,
                                )

                                # Prefer own PDF when present; else convert PDF.
                                durable_src = (
                                    own_pdf
                                    if own_pdf and os.path.isfile(own_pdf)
                                    else convert_pdf
                                )
                                persist_original_pdf_durable(
                                    task_state, task_id, durable_src
                                )
                            except Exception as backup_err:
                                logger.debug(
                                    LogModule.TRANS,
                                    f"[TRANSLATION-SERVICE] Task {task_id}: "
                                    f"convert PDF backup skipped: {backup_err}",
                                )
                    # Copy ebook_metadata (title, author) so export uses it when generating MOBI/EPUB
                    if "ebook_metadata" in convert_state and convert_state["ebook_metadata"]:
                        task_state["ebook_metadata"] = convert_state["ebook_metadata"].copy()
                        copied_keys.append("ebook_metadata")
                    
                    if copied_keys:
                        # Store format-convert task id (not copy_source_only shell) for downstream inherits
                        task_state["convert_task_id"] = effective_convert_task_id
                        from utils.translation_segments import reconcile_excluded_segments_from_layout
                        if not getattr(payload, "copy_source_only", False) and reconcile_excluded_segments_from_layout(task_state, task_id):
                            logger.info(
                                LogModule.TRANS,
                                f"[TRANSLATION-SERVICE] Task {task_id}: Reconciled inherited exclusions "
                                f"from layout_prepared_chunks (convert_task_id={effective_convert_task_id})",
                            )
                        logger.info(
                            LogModule.TRANS,
                            f"[TRANSLATION-SERVICE] Task {task_id}: Inherited assets from convert_task_id={convert_task_id}: {copied_keys}"
                        )
                    else:
                        logger.info(
                            LogModule.TRANS,
                            f"[TRANSLATION-SERVICE] Task {task_id}: convert_task_id={convert_task_id} provided, but no new assets copied "
                            f"(either missing in convert_state or already present)."
                        )

                    # CRITICAL: If we have layout_prepared_chunks but segments_metadata has no excluded_segments
                    # (e.g. convert task state was not yet updated by layout-extract, or different worker),
                    # build excluded_segments from layout_prepared_chunks so Identifier and other excluded
                    # segments are not sent for translation and marked as "translation failed".
                    layout_chunks = task_state.get("layout_prepared_chunks") or []
                    sm = task_state.get("segments_metadata") or {}
                    excluded_in_meta = sm.get("excluded_segments") or {}
                    if layout_chunks and (not excluded_in_meta or len(excluded_in_meta) == 0):
                        from exclusion.core import ExclusionManager
                        from exclusion.core.exclusion_reason import ExclusionReason
                        excluded_from_chunks = {}
                        convert_sm = convert_state.get("segments_metadata") or {}
                        convert_excluded = convert_sm.get("excluded_segments") or {}
                        convert_detected = convert_sm.get("detected_exclusion_reasons") or {}
                        for item in layout_chunks:
                            if not item.get("is_excluded", False):
                                continue
                            for seg_idx in item.get("segment_indices") or []:
                                reason = ExclusionReason.REFERENCE
                                seg_str = str(seg_idx)
                                if seg_str in convert_excluded:
                                    info = convert_excluded[seg_str]
                                    if isinstance(info, dict) and info.get("reason"):
                                        try:
                                            reason = ExclusionReason(info["reason"])
                                        except ValueError:
                                            pass
                                elif seg_str in convert_detected:
                                    r = convert_detected[seg_str]
                                    if isinstance(r, dict) and r.get("reason"):
                                        try:
                                            reason = ExclusionReason(r["reason"])
                                        except ValueError:
                                            pass
                                excluded_from_chunks[int(seg_idx)] = reason
                        if excluded_from_chunks:
                            if "segments_metadata" not in task_state:
                                task_state["segments_metadata"] = {}
                            ExclusionManager.update_excluded_segments(
                                task_state=task_state,
                                excluded_segments=excluded_from_chunks,
                            )
                            logger.info(
                                LogModule.TRANS,
                                f"[TRANSLATION-SERVICE] Task {task_id}: Built excluded_segments from layout_prepared_chunks "
                                f"(fallback): {len(excluded_from_chunks)} segments so they are not sent for translation"
                            )
                else:
                    logger.warning(
                        LogModule.TRANS,
                        f"[TRANSLATION-SERVICE] Task {task_id}: convert_task_id={convert_task_id} provided but task not found in task_manager"
                    )
            else:
                logger.debug(
                    LogModule.TRANS,
                    f"[TRANSLATION-SERVICE] Task {task_id}: No convert_task_id provided; running without inherited extract assets"
                )
        except Exception as e:
            logger.warning(
                LogModule.TRANS,
                f"[TRANSLATION-SERVICE] Task {task_id}: Failed to inherit assets from convert_task_id: {e}",
                exc_info=True
            )
        
        # Store payload in task_state for later use (e.g., retranslation)
        if hasattr(payload, 'model_dump'):
            task_state["payload"] = payload.model_dump()
        elif hasattr(payload, 'dict'):
            task_state["payload"] = payload.dict()
        else:
            task_state["payload"] = payload
        
        # Save format settings from payload to task_state (if present)
        # This ensures format settings from Convert phase are preserved
        if isinstance(payload, dict):
            if "table_body_format" in payload:
                task_state["table_body_format"] = payload["table_body_format"]
                logger.info(LogModule.CONFIG, f"[TRANSLATION-SERVICE] Saved table_body_format from payload: {payload['table_body_format']}")
            if "equation_format" in payload:
                task_state["equation_format"] = payload["equation_format"]
                logger.info(LogModule.CONFIG, f"[TRANSLATION-SERVICE] Saved equation_format from payload: {payload['equation_format']}")
        elif hasattr(payload, 'table_body_format') or hasattr(payload, 'equation_format'):
            if hasattr(payload, 'table_body_format') and getattr(payload, 'table_body_format', None) is not None:
                task_state["table_body_format"] = getattr(payload, 'table_body_format')
                logger.info(LogModule.CONFIG, f"[TRANSLATION-SERVICE] Saved table_body_format from payload: {getattr(payload, 'table_body_format')}")
            if hasattr(payload, 'equation_format') and getattr(payload, 'equation_format', None) is not None:
                task_state["equation_format"] = getattr(payload, 'equation_format')
                logger.info(LogModule.CONFIG, f"[TRANSLATION-SERVICE] Saved equation_format from payload: {getattr(payload, 'equation_format')}")
        
        # Determine default deep_split based on file format
        workflow_type = getattr(payload, 'workflow_type', None)
        file_ext = pathlib.Path(original_filename).suffix.lower()
        default_deep_split = get_default_deep_split(original_filename, workflow_type)
        deep_split_enabled = default_deep_split
        
        # User-provided deep_split takes precedence
        try:
            user_deep_split = getattr(payload, 'deep_split', None)
            if isinstance(payload, dict):
                user_deep_split = payload.get('deep_split', user_deep_split)
            if user_deep_split is not None:
                deep_split_enabled = bool(user_deep_split)
        except Exception as e:
            logger.warning(LogModule.CONFIG, f"[TRANSLATION-SERVICE] Failed to get user deep_split: {e}")
        
        task_state["deep_split"] = deep_split_enabled
        
        # Synthesize prompt
        synthesized_prompt = prompt_service.synthesize_prompt(payload)
        
        # Build workflow configuration using new services
        # Handle both dict and object payloads
        if isinstance(payload, dict):
            workflow_type = payload.get('workflow_type')
        else:
            workflow_type = getattr(payload, 'workflow_type', None)
        
        if not workflow_type:
            logger.error(LogModule.WORKFLOW, f"[TRANSLATION-SERVICE] No workflow_type in payload for task {task_id}, payload type: {type(payload)}, payload keys/attrs: {list(payload.keys()) if isinstance(payload, dict) else dir(payload)[:10]}")
            task_state["status"] = "failed"
            task_state["error"] = "No workflow_type specified"
            task_state["message"] = "Translation failed: No workflow type specified"
            return
        
        logger.debug(LogModule.WORKFLOW, f"[TRANSLATION-SERVICE] Task {task_id}: Building workflow config for workflow_type={workflow_type}, type={type(workflow_type)}")
        config_builder = WorkflowConfigBuilder(task_id, task_state)
        workflow_config = config_builder.build_workflow_config(workflow_type, payload, synthesized_prompt)
        
        if not workflow_config:
            logger.error(LogModule.WORKFLOW, f"[TRANSLATION-SERVICE] Failed to build workflow config for {workflow_type} (type: {type(workflow_type)}, repr: {repr(workflow_type)})")
            task_state["status"] = "failed"
            task_state["error"] = f"Unsupported workflow type: {workflow_type}"
            task_state["message"] = f"Translation failed: Unsupported workflow type {workflow_type}"
            return
        
        # Create workflow using factory
        workflow = self.workflow_factory.create_workflow(workflow_type, config=workflow_config)
        
        if not workflow:
            logger.error(LogModule.WORKFLOW, f"[TRANSLATION-SERVICE] Failed to create workflow {workflow_type}")
            task_state["status"] = "failed"
            task_state["error"] = f"Failed to create workflow: {workflow_type}"
            task_state["message"] = f"Translation failed: Could not create workflow {workflow_type}"
            return
        
        # Store workflow in task_state (so original function can use it)
        task_state["workflow_instance"] = workflow
        
        # Read file content into workflow
        try:
            file_stem = pathlib.Path(original_filename).stem
            file_suffix = pathlib.Path(original_filename).suffix
            workflow.read_bytes(content=file_contents, stem=file_stem, suffix=file_suffix)
            workflow._file_read = True  # Mark as read to prevent duplicate reading
            logger.info(LogModule.WORKFLOW, f"[TRANSLATION-SERVICE] File read into workflow: task_id={task_id}")
        except Exception as read_error:
            logger.error(LogModule.WORKFLOW, f"[TRANSLATION-SERVICE] Failed to read file into workflow: task_id={task_id}, error={read_error}", exc_info=True)
            task_state["status"] = "failed"
            task_state["error"] = str(read_error)
            task_state["message"] = f"Failed to read file: {str(read_error)}"
            return
        
        # For markdown_based workflow, try to reuse MinerU results from Extract phase
        # This avoids re-uploading and re-downloading from MinerU server
        if workflow_type == "markdown_based":
            self._try_reuse_layout_results(task_id, workflow, payload, task_state, file_contents, original_filename)
        
        # For markdown_based workflow, set task_state for MinerU reuse
        # Always attach task_state so md_based_workflow can inspect MinerU paths, even
        # if the attribute was not pre-declared on the workflow instance.
        if workflow_type == "markdown_based":
            setattr(workflow, "_task_state", task_state)
        
        # Sync workflow attachments (e.g., MinerU ZIP) after file read
        self._sync_workflow_attachments(task_id, workflow, task_state, reason="file_read")
        
        # Prepare source preview for workflows that support immediate extraction
        # DOCX and PPTX can extract preview immediately from original file
        # Other workflows (HTML, SRT, TXT, JSON, XLSX, EPUB, MOBI, Qt TS) also support immediate extraction
        # PDF/Markdown-based workflows need to wait until after conversion/translation
        try:
            if workflow_type == "docx":
                self.source_preview_service.prepare_source_preview_for_docx(
                    task_id, file_contents, payload, task_state
                )
            elif workflow_type == "pptx":
                self.source_preview_service.prepare_source_preview_for_pptx(
                    task_id, file_contents, original_filename, payload, task_state, temp_dir
                )
            elif workflow_type == "html":
                self.source_preview_service.prepare_source_preview_for_html(
                    task_id, file_contents, payload, task_state
                )
            elif workflow_type == "srt":
                self.source_preview_service.prepare_source_preview_for_srt(
                    task_id, file_contents, payload, task_state
                )
            elif workflow_type == "txt":
                self.source_preview_service.prepare_source_preview_for_txt(
                    task_id, file_contents, payload, task_state
                )
            elif workflow_type == "json":
                self.source_preview_service.prepare_source_preview_for_json(
                    task_id, file_contents, payload, task_state
                )
            elif workflow_type == "xlsx":
                self.source_preview_service.prepare_source_preview_for_xlsx(
                    task_id, file_contents, payload, task_state
                )
            elif workflow_type == "epub":
                from extractor.epub_extractor import EpubExtractor
                self.source_preview_service.prepare_source_preview_for_extractor_based(
                    task_id, file_contents, payload, task_state, EpubExtractor, workflow_type
                )
            elif workflow_type == "mobi":
                from extractor.mobi_extractor import MobiExtractor
                self.source_preview_service.prepare_source_preview_for_extractor_based(
                    task_id, file_contents, payload, task_state, MobiExtractor, workflow_type
                )
            elif workflow_type == "qt_ts":
                from extractor.qt_ts_extractor import QtTsExtractor
                self.source_preview_service.prepare_source_preview_for_extractor_based(
                    task_id, file_contents, payload, task_state, QtTsExtractor, workflow_type
                )
            # PDF/Markdown-based workflows will generate preview after conversion/translation
        except Exception as preview_error:
            logger.warning(LogModule.EXTRACT, f"[TRANSLATION-SERVICE] Task {task_id}: Failed to prepare source preview: {preview_error}", exc_info=True)
            # Continue processing even if preview preparation fails
        
        # Determine if this is a format conversion task (skip translation)
        is_format_conversion = task_state.get("is_format_conversion", False) or getattr(payload, 'skip_translate', False)
        
        # Set initial progress to 10% after translation initialization is complete
        task_state["progress"] = 10
        task_state["message"] = "Translation initialized, starting processing..."
        
        # Execute workflow (convert and/or translate) using WorkflowExecutor
        if is_format_conversion:
            await self.workflow_executor.execute_convert(task_id, workflow, payload, task_state)
            
            # Sync workflow attachments after conversion
            self._sync_workflow_attachments(task_id, workflow, task_state, reason="post_convert")
            self._persist_layout_document(
                task_id, workflow, task_state, original_filename, is_format_conversion=True
            )
            
            # For PDF/Markdown-based workflows, generate preview from converted markdown
            if workflow_type == "markdown_based":
                self._prepare_markdown_based_preview(task_id, workflow, payload, task_state, original_filename, is_format_conversion)
            else:
                # For non-PDF workflows (DOCX, PPTX, HTML, etc.), ensure source_preview is still available after conversion
                # Preview was already prepared during file read, but we need to ensure it's still valid
                source_preview = task_state.get("source_preview", {})
                if not source_preview.get("ready", False):
                    # If preview is not ready, try to prepare it again (should not happen, but safety check)
                    logger.warning(LogModule.EXTRACT, f"[TRANSLATION-SERVICE] Task {task_id}: source_preview not ready after format conversion for {workflow_type}, attempting to prepare again")
                    try:
                        if workflow_type == "docx":
                            self.source_preview_service.prepare_source_preview_for_docx(
                                task_id, file_contents, payload, task_state
                            )
                        elif workflow_type == "pptx":
                            self.source_preview_service.prepare_source_preview_for_pptx(
                                task_id, file_contents, original_filename, payload, task_state, temp_dir
                            )
                        elif workflow_type == "html":
                            self.source_preview_service.prepare_source_preview_for_html(
                                task_id, file_contents, payload, task_state
                            )
                        elif workflow_type == "srt":
                            self.source_preview_service.prepare_source_preview_for_srt(
                                task_id, file_contents, payload, task_state
                            )
                        elif workflow_type == "txt":
                            self.source_preview_service.prepare_source_preview_for_txt(
                                task_id, file_contents, payload, task_state
                            )
                        elif workflow_type == "json":
                            self.source_preview_service.prepare_source_preview_for_json(
                                task_id, file_contents, payload, task_state
                            )
                        elif workflow_type == "xlsx":
                            self.source_preview_service.prepare_source_preview_for_xlsx(
                                task_id, file_contents, payload, task_state
                            )
                    except Exception as preview_retry_error:
                        logger.warning(LogModule.EXTRACT, f"[TRANSLATION-SERVICE] Task {task_id}: Failed to retry preview preparation: {preview_retry_error}")
                else:
                    # Verify that source_preview has segments
                    segments_count = len(source_preview.get("segments", []))
                    total_segments = source_preview.get("total_segments", 0)
                    if segments_count == 0 and total_segments > 0:
                        # Preview is marked as ready but has no segments in preview (may be in cache)
                        cache_info = task_state.get("source_chunks_cache", {})
                        cache_segments = cache_info.get("segments", [])
                        if cache_segments:
                            # Update source_preview with segments from cache
                            task_state["source_preview"] = {
                                "segments": cache_segments[:SOURCE_PREVIEW_SEGMENTS_LIMIT],
                                "total_segments": len(cache_segments),
                                "ready": True,
                            }
                            logger.info(LogModule.EXTRACT, f"[TRANSLATION-SERVICE] Task {task_id}: Restored source_preview segments from cache for {workflow_type}: {len(cache_segments)} segments")
                    elif segments_count > 0:
                        logger.debug(LogModule.EXTRACT, f"[TRANSLATION-SERVICE] Task {task_id}: source_preview is ready for {workflow_type}: {segments_count}/{total_segments} segments")
                    else:
                        logger.warning(LogModule.EXTRACT, f"[TRANSLATION-SERVICE] Task {task_id}: source_preview is ready but has no segments for {workflow_type} (total_segments={total_segments})")
                        # Try to restore from cache
                        cache_info = task_state.get("source_chunks_cache", {})
                        cache_segments = cache_info.get("segments", [])
                        if cache_segments:
                            task_state["source_preview"] = {
                                "segments": cache_segments[:SOURCE_PREVIEW_SEGMENTS_LIMIT],
                                "total_segments": len(cache_segments),
                                "ready": True,
                            }
                            logger.info(LogModule.EXTRACT, f"[TRANSLATION-SERVICE] Task {task_id}: Restored source_preview from cache for {workflow_type}: {len(cache_segments)} segments")
                        else:
                            logger.error(LogModule.EXTRACT, f"[TRANSLATION-SERVICE] Task {task_id}: No segments available in source_preview or cache for {workflow_type}")
        else:
            # Enter translation phase immediately so language-detection _join_and_finish does not overwrite with 100%
            task_state["progress"] = 10
            task_state["message"] = "Sending translation requests to AI platform..."
            self.task_manager.update_task(task_id, {"progress": 10, "message": "Sending translation requests to AI platform...", "status": "processing"})
            # CRITICAL: For markdown-based workflows, prepare preview BEFORE translation
            # This ensures source_chunks_cache and chunk_to_segment_map are available for translation
            if workflow_type == "markdown_based":
                # When we inherited from a convert task (e.g. image -> MinerU -> markdown), we already have
                # source_chunks_cache and chunk_to_segment_map. Do NOT run _prepare_markdown_based_preview:
                # workflow.document_original is still the raw file (e.g. PNG bytes), so decoding as UTF-8 would fail.
                has_cache = bool(task_state.get("source_chunks_cache", {}).get("segments"))
                has_map = bool(task_state.get("chunk_to_segment_map"))
                if has_cache and has_map:
                    logger.info(
                        LogModule.EXTRACT,
                        f"[TRANSLATION-SERVICE] Task {task_id}: Using inherited source_chunks_cache and chunk_to_segment_map from convert task; skipping markdown preview preparation (avoids decoding binary original file)"
                    )
                else:
                    # Single-phase mode (no convert_task_id): PDF files are still raw binary
                    # and haven't been converted by MinerU yet. Skip preview preparation —
                    # the full pipeline (conversion + translation) runs inside execute_translate.
                    import os
                    _is_binary_format = os.path.splitext(original_filename)[1].lower() in ('.pdf',)
                    if _is_binary_format:
                        logger.info(
                            LogModule.EXTRACT,
                            f"[TRANSLATION-SERVICE] Task {task_id}: Skipping markdown preview preparation for {original_filename} in single-phase mode (document is still raw binary, conversion happens inside execute_translate)"
                        )
                    else:
                        logger.info(LogModule.EXTRACT, f"[TRANSLATION-SERVICE] Task {task_id}: Preparing markdown preview from document_original before translation to ensure all segments (including images) are available")
                        self._prepare_markdown_based_preview(task_id, workflow, payload, task_state, original_filename, is_format_conversion=False)

            # Convert toolbar: copy source to target on translate task only (no LLM, no convert-task exclude-all)
            copy_source_only = bool(getattr(payload, "copy_source_only", False))
            if copy_source_only:
                task_state["copy_source_only"] = True
                from utils.translation_segments import apply_copy_source_only_exclusions
                apply_copy_source_only_exclusions(task_state, task_id)

            # When all segments are excluded, complete immediately with source as target (no AI call)
            # This is effectively a format conversion, so mark it as such.
            from utils.translation_segments import complete_translation_with_source_only
            if complete_translation_with_source_only(task_id, task_state):
                task_state["is_format_conversion"] = True
                task_state["convert_only"] = True
                task_state["status"] = "completed"
                task_state["progress"] = 100
                task_state["message"] = "Translation completed (all segments excluded, source used as target)"
                self.task_manager.update_task(task_id, {"status": "completed", "progress": 100, "message": task_state["message"], "is_format_conversion": True, "convert_only": True})
                logger.info(LogModule.WORKFLOW, f"[TRANSLATION-SERVICE] Task {task_id}: All segments excluded, completed immediately with source as target")
                # MOBI/EPUB: set mobi_translated_texts so ensure_translation_segments can add image segments
                if workflow_type == "mobi":
                    segs = task_state.get("translation_segments", {}).get("segments", [])
                    if segs:
                        task_state["mobi_translated_texts"] = [s.get("target_text", "") for s in segs]
                        task_state["mobi_original_texts"] = [s.get("source_text", "") for s in segs]
                # Record segments (e.g. MOBI image placeholder insertion) even when all excluded
                try:
                    result = self.translation_segment_service.ensure_translation_segments(
                        task_id=task_id,
                        workflow=workflow,
                        workflow_type=workflow_type,
                        file_contents=file_contents,
                        original_filename=original_filename,
                        payload=payload,
                        task_state=task_state,
                        is_format_conversion=is_format_conversion,
                    )
                    logger.info(LogModule.TRANS, f"[TRANSLATION-SERVICE] Task {task_id}: ensure_translation_segments (all-excluded) returned {result}")
                except Exception as seg_err:
                    logger.warning(LogModule.TRANS, f"[TRANSLATION-SERVICE] Task {task_id}: ensure_translation_segments (all-excluded) failed: {seg_err}")
                self._sync_workflow_attachments(task_id, workflow, task_state, reason="post_translate")
            else:
                # Test LLM connectivity before starting translation
                connectivity_ok = await self._test_llm_connectivity(payload, task_id, task_state)
                if not connectivity_ok:
                    logger.error(
                        LogModule.WORKFLOW,
                        f"[TRANSLATION-SERVICE] Task {task_id}: LLM connectivity test failed, aborting translation"
                    )
                    return
                
                logger.info(LogModule.WORKFLOW, f"[TRANSLATION-SERVICE] Task {task_id}: About to call execute_translate")
                await self.workflow_executor.execute_translate(task_id, workflow, payload, original_filename, temp_dir, task_state)
                logger.info(LogModule.TRANS, f"[TRANSLATION-SERVICE] Task {task_id}: execute_translate returned successfully (including _after_translate completion)")

                # Sync workflow attachments after translation (already done in execute_translate, but keep for compatibility)
                logger.debug(LogModule.WORKFLOW, f"[TRANSLATION-SERVICE] Task {task_id}: About to sync workflow attachments (post_translate)")
                self._sync_workflow_attachments(task_id, workflow, task_state, reason="post_translate")
                logger.debug(LogModule.WORKFLOW, f"[TRANSLATION-SERVICE] Task {task_id}: Workflow attachments synced")

                # For PDF/Markdown-based workflows, update preview from translated markdown (if needed)
                if workflow_type == "markdown_based":
                    pass  # Preview update can be done later if needed

                # Record translation segments for frontend preview (skip when already filled by complete_translation_with_source_only)
                logger.debug(LogModule.TRANS, f"[TRANSLATION-SERVICE] Task {task_id}: About to call ensure_translation_segments for workflow_type={workflow_type}")
                try:
                    result = self.translation_segment_service.ensure_translation_segments(
                        task_id=task_id,
                        workflow=workflow,
                        workflow_type=workflow_type,
                        file_contents=file_contents,
                        original_filename=original_filename,
                        payload=payload,
                        task_state=task_state,
                        is_format_conversion=is_format_conversion
                    )
                    logger.info(LogModule.TRANS, f"[TRANSLATION-SERVICE] Task {task_id}: ensure_translation_segments returned {result}")
                except Exception as seg_error:
                    logger.error(LogModule.TRANS, f"[TRANSLATION-SERVICE] Task {task_id}: ensure_translation_segments failed: {seg_error}", exc_info=True)
                    # Don't raise - segment recording failure shouldn't block task completion

                # Markdown-based: optional auto LLM repair for Pandoc DOCX / texmath fragment failures
                try:
                    from backend.config.system_config import get_system_config

                    _sys = get_system_config()
                    if workflow_type != "markdown_based":
                        if _sys.features.auto_docx_math_fragment_llm_repair:
                            logger.debug(
                                LogModule.RESTOR,
                                "[DOCX-MATH-LLM-REPAIR] Skip auto repair: "
                                f"workflow_type={workflow_type} (requires markdown_based) task_id={task_id}",
                            )
                    elif _sys.features.auto_docx_math_fragment_llm_repair:
                        llm_docx = task_state.get("llm_config_for_repair")
                        if (
                            isinstance(llm_docx, dict)
                            and llm_docx.get("base_url")
                            and llm_docx.get("model_id")
                        ):
                            try:
                                if int(task_state.get("progress", 0) or 0) >= 100:
                                    task_state["progress"] = 95
                                task_state["status"] = "processing"
                                task_state["message"] = (
                                    "Post-processing: DOCX formula repair (LLM)..."
                                )
                                self.task_manager.update_task(
                                    task_id,
                                    {
                                        "status": "processing",
                                        "progress": task_state.get("progress", 95),
                                        "message": task_state["message"],
                                    },
                                )
                            except Exception:
                                pass

                            from utils.docx_math_fragment_llm_repair import (
                                repair_docx_math_fragments_with_llm,
                            )

                            docx_summary = await asyncio.to_thread(
                                partial(
                                    repair_docx_math_fragments_with_llm,
                                    task_state,
                                    task_id,
                                    llm_docx,
                                    refresh_check_first=True,
                                    recheck_after=True,
                                    max_segments=None,
                                ),
                            )
                            logger.info(
                                LogModule.RESTOR,
                                "[DOCX-MATH-LLM-REPAIR] Auto post-translate finished "
                                "(task_id={tid}, success={ok}, updated={u}, issues_after={ia})",
                                tid=task_id,
                                ok=docx_summary.get("success"),
                                u=docx_summary.get("segments_updated"),
                                ia=docx_summary.get("issues_after"),
                            )
                        else:
                            _has_b = (
                                bool((llm_docx or {}).get("base_url"))
                                if isinstance(llm_docx, dict)
                                else False
                            )
                            _has_m = (
                                bool((llm_docx or {}).get("model_id"))
                                if isinstance(llm_docx, dict)
                                else False
                            )
                            logger.warning(
                                LogModule.RESTOR,
                                "[DOCX-MATH-LLM-REPAIR] Skip auto repair: llm_config_for_repair incomplete "
                                f"(need base_url and model_id on translation payload). task_id={task_id} "
                                f"has_dict={isinstance(llm_docx, dict)} has_base_url={_has_b} has_model_id={_has_m}",
                            )
                    else:
                        logger.debug(
                            LogModule.RESTOR,
                            "[DOCX-MATH-LLM-REPAIR] Skip auto repair: "
                            "auto_docx_math_fragment_llm_repair=false in system config (cached). task_id=%s",
                            task_id,
                        )
                except Exception as docx_repair_err:  # noqa: BLE001
                    logger.warning(
                        LogModule.RESTOR,
                        f"[DOCX-MATH-LLM-REPAIR] Auto repair failed (task {task_id}): {docx_repair_err}",
                        exc_info=False,
                    )

                log_segment_translation_stats(
                    task_id,
                    task_state,
                    "after_main_translation",
                )
                # Auto batch-retry failed segments (post-translation, for both modes)
                try:
                    await self._auto_retry_failed_segments(task_id, task_state, payload)
                except Exception as auto_retry_err:
                    logger.error(
                        LogModule.TRANS,
                        f"[AUTO-RETRY] task={task_id} fatal: {auto_retry_err}",
                        exc_info=True,
                    )

                # PDF workflow: auto normalize formula segments after retranslate using LLM (batched).
                # Runs after auto batch-retry so repairs target final segment text.
                try:
                    is_pdf_file = original_filename.lower().endswith(".pdf")
                    if is_pdf_file and workflow_type == "markdown_based":
                        from utils.latex_formula_batch_repair import (
                            apply_formula_repairs_to_task_state,
                            batch_repair_formulas_with_llm,
                            collect_formula_items,
                        )

                        items = collect_formula_items(task_state)
                        # Keep progress < 100 during post-processing so frontend
                        # does not stop polling before formula repair completes.
                        try:
                            if int(task_state.get("progress", 0) or 0) >= 100:
                                task_state["progress"] = 95
                                task_state["message"] = "Post-processing: preparing formula repair..."
                                self.task_manager.update_task(
                                    task_id,
                                    {"status": "processing", "progress": task_state["progress"], "message": task_state["message"]},
                                )
                        except Exception:
                            pass

                        def _on_formula_progress(evt: dict) -> None:
                            try:
                                if not isinstance(evt, dict):
                                    return
                                if evt.get("event") == "batch_start":
                                    bi = int(evt.get("batch_index") or 0)
                                    bn = int(evt.get("batch_total") or 0) or 1
                                    # Map formula repair to 95%..99% range
                                    p = 95 + int((max(0, min(bi - 1, bn)) / max(1, bn)) * 4)
                                    task_state["status"] = "processing"
                                    task_state["progress"] = min(99, max(95, p))
                                    task_state["message"] = f"Auto repairing formulas... batch {bi}/{bn}"
                                    self.task_manager.update_task(
                                        task_id,
                                        {"status": task_state["status"], "progress": task_state["progress"], "message": task_state["message"]},
                                    )
                                elif evt.get("event") == "batch_done":
                                    bi = int(evt.get("batch_index") or 0)
                                    bn = int(evt.get("batch_total") or 0) or 1
                                    p = 95 + int((max(0, min(bi, bn)) / max(1, bn)) * 4)
                                    task_state["status"] = "processing"
                                    task_state["progress"] = min(99, max(95, p))
                                    task_state["message"] = f"Auto repairing formulas... batch {bi}/{bn}"
                                    self.task_manager.update_task(
                                        task_id,
                                        {"status": task_state["status"], "progress": task_state["progress"], "message": task_state["message"]},
                                    )
                            except Exception:
                                return

                        fixes, notes = await asyncio.to_thread(
                            batch_repair_formulas_with_llm,
                            task_id=task_id,
                            items=items,
                            llm_config_dict=task_state.get("llm_config_for_repair"),
                            on_progress=_on_formula_progress,
                        )
                        summary = apply_formula_repairs_to_task_state(task_state, fixes)
                        logger.info(
                            LogModule.RESTOR,
                            "[FORMULA-REPAIR] Auto repair finished (task_id={tid}, notes={notes}, items={n}, updated={u}, skipped={s})",
                            tid=task_id,
                            notes=notes,
                            n=len(items),
                            u=summary.get("updated", 0),
                            s=summary.get("skipped", 0),
                        )
                except Exception as fr_err:  # noqa: BLE001
                    logger.warning(
                        LogModule.RESTOR,
                        f"[FORMULA-REPAIR] Auto repair failed (task {task_id}): {fr_err}",
                        exc_info=False,
                    )

                # Mark translation phase done; queued tasks defer "completed" until exports finish.
                is_queued = task_state.get("execution_mode") == "queued"
                if is_queued:
                    task_state["status"] = "processing"
                    task_state["progress"] = 90
                    if not task_state.get("llm_error"):
                        task_state["message"] = "Translation finished, generating export files..."
                    else:
                        task_state["message"] = (
                            f"Translation finished with errors, generating export files..."
                        )
                else:
                    task_state["status"] = "completed"
                    task_state["progress"] = 100
                    if not task_state.get("llm_error"):
                        task_state["message"] = "Translation completed successfully"
                    else:
                        task_state["message"] = f"Translation failed: {task_state['llm_error']}"
                logger.info(
                    LogModule.WORKFLOW,
                    f"[TRANSLATION-SERVICE] Task {task_id}: Translation phase finished "
                    f"(status={task_state['status']}, queued={is_queued}) after post-processing",
                )

        # Ensure export has a document when translate() was skipped (format conversion or all-excluded translation)
        try:
            doc_translated = getattr(workflow, 'document_translated', None)
            doc_original = getattr(workflow, 'document_original', None)
            if doc_translated is None and doc_original is not None:
                setattr(workflow, 'document_translated', doc_original)
                logger.debug(
                    LogModule.WORKFLOW,
                    f"[TRANSLATION-SERVICE] Task {task_id}: Set document_translated to document_original for export "
                    f"(is_format_conversion={is_format_conversion})"
                )
        except Exception:
            pass
        
        # Persist layout document (if available) for downstream layout-based features
        self._persist_layout_document(task_id, workflow, task_state, original_filename, is_format_conversion)
        
        # CRITICAL: Do NOT generate output files here - generate them on-demand when user clicks download/preview
        # This allows users to edit translation results before generating files
        # Files will be generated in DownloadService.download_file() when needed
        logger.debug(
            LogModule.WORKFLOW,
            f"[TRANSLATION-SERVICE] Task {task_id}: Skipping file generation - files will be generated on-demand when user downloads/previews"
        )
        # Store workflow and payload in task_state for on-demand file generation
        task_state["workflow_instance"] = workflow
        task_state["payload"] = payload
        task_state["temp_dir"] = temp_dir
        task_state["original_filename"] = original_filename
        
        # Extract token usage statistics before workflow is cleaned up
        try:
            if hasattr(workflow, 'translator') and workflow.translator:
                if hasattr(workflow.translator, 'token_usage'):
                    token_usage = workflow.translator.token_usage
                    if token_usage:
                        task_state["token_usage"] = token_usage
                        logger.info(LogModule.TRANS, f"[TRANSLATION-SERVICE] Token usage for task {task_id}: {token_usage}")
        except Exception as token_error:
            logger.debug(LogModule.TRANS, f"[TRANSLATION-SERVICE] Failed to extract token usage: {token_error}")
        
        # Verify source_preview is still available before marking as completed (for format conversion)
        if is_format_conversion:
            source_preview = task_state.get("source_preview", {})
            cache_info = task_state.get("source_chunks_cache", {})
            preview_ready = source_preview.get("ready", False)
            preview_segments_count = len(source_preview.get("segments", []))
            cache_segments_count = len(cache_info.get("segments", []))
            has_segments = preview_segments_count > 0 or cache_segments_count > 0
            if not preview_ready or not has_segments:
                logger.warning(
                    LogModule.EXTRACT,
                    f"[TRANSLATION-SERVICE] Task {task_id}: source_preview may be missing after format conversion "
                    f"(ready={preview_ready}, preview_segments={preview_segments_count}, cache_segments={cache_segments_count}, workflow_type={workflow_type})"
                )
            else:
                logger.debug(
                    LogModule.EXTRACT,
                    f"[TRANSLATION-SERVICE] Task {task_id}: source_preview verified after format conversion "
                    f"(preview_segments={preview_segments_count}, cache_segments={cache_segments_count}, workflow_type={workflow_type})"
                )
        
        # Mark completed before queued auto-export so the UI/API stay responsive while
        # heavy PDF/DOCX generation runs (export itself must not block the event loop).
        if task_state.get("status") != "completed":
            task_state["status"] = "completed"
        task_state["progress"] = 100
        task_state["task_end_time"] = time.time()
        if is_format_conversion:
            task_state["message"] = "Format conversion completed successfully"
            self.task_manager.add_log(task_id, "info", "Format conversion completed successfully")
        else:
            # Don't overwrite LLM platform error messages (e.g., insufficient balance)
            if not task_state.get("llm_error"):
                task_state["message"] = "Translation completed successfully"
                self.task_manager.add_log(task_id, "info", "Translation completed successfully")
            else:
                task_state["message"] = f"Translation failed: {task_state['llm_error']}"
                self.task_manager.add_log(
                    task_id,
                    "error",
                    f"Translation failed due to LLM platform error: {task_state['llm_error']}",
                )

            current_message = task_state.get("message", "")
            if "timeout" in current_message.lower() and "completed" not in current_message.lower():
                task_state["message"] = f"Translation completed (with timeout issues). {current_message}"

        logger.info(
            LogModule.WORKFLOW,
            f"[TRANSLATION-SERVICE] Task {task_id} completed. Status: {task_state['status']}",
        )

        if (
            task_state.get("execution_mode") == "queued"
            and (task_state.get("status") or "").lower() not in ("failed",)
        ):
            # Do not await: heavy layout MD/HTML export must not hold the queue
            # worker or starve /api/health while the UI is polling.
            task_state["queued_auto_export_pending"] = True
            export_task = asyncio.create_task(
                self._auto_export_queued_task_outputs(task_id, task_state),
                name=f"owlangs-queued-auto-export-{task_id}",
            )

            def _clear_export_pending(t: "asyncio.Task[None]") -> None:
                ts = self.task_manager.get_task(task_id)
                if isinstance(ts, dict):
                    ts["queued_auto_export_pending"] = False
                if t.cancelled():
                    return
                exc = t.exception()
                if exc is not None:
                    logger.warning(
                        LogModule.WORKFLOW,
                        f"[TRANSLATION-SERVICE] Task {task_id}: background auto-export "
                        f"finished with error: {exc}",
                    )

            export_task.add_done_callback(_clear_export_pending)
    
    def _sync_workflow_attachments(
        self,
        task_id: str,
        workflow: Any,
        task_state: Dict[str, Any],
        reason: str = "auto"
    ) -> None:
        """
        Persist workflow attachments (e.g., MinerU ZIP) into task_state.
        
        Args:
            task_id: Task identifier
            workflow: Workflow instance
            task_state: Task state dictionary
            reason: Reason for syncing (for logging)
        """
        try:
            if workflow is None:
                return

            layout_doc = getattr(workflow, "layout_document", None)
            if layout_doc is not None:
                try:
                    from layout.base import LayoutDocument as _LD

                    if isinstance(layout_doc, _LD):
                        task_state["layout_document"] = layout_doc
                        task_state["layout_engine"] = getattr(layout_doc, "engine", "unknown")
                        logger.debug(
                            LogModule.EXTRACT,
                            f"[ATTACHMENT] Stored layout_document for task {task_id} "
                            f"({layout_doc.page_count} pages, engine={task_state['layout_engine']}, reason={reason})",
                        )
                except Exception as layout_error:
                    logger.debug(
                        LogModule.EXTRACT,
                        f"[ATTACHMENT] Failed to persist layout_document: {layout_error}",
                    )

            if not hasattr(workflow, "attachment"):
                return
            attachment_manager = getattr(workflow, "attachment", None)
            if not attachment_manager:
                return
            attachment_dict = getattr(attachment_manager, "attachment_dict", {})
            if not attachment_dict:
                return
            
            # Store attachment documents in task_state for downstream usage
            task_state["attachments"] = dict(attachment_dict)
            mineru_doc = attachment_dict.get("mineru")
            if mineru_doc and hasattr(mineru_doc, "content") and mineru_doc.content:
                task_state["layout_source_zip"] = mineru_doc.content
                logger.debug(LogModule.EXTRACT, f"[ATTACHMENT] Stored MinerU ZIP bytes for task {task_id} (reason={reason})")

                # Extract MinerU ZIP to task's temp directory for easy access
                temp_dir = task_state.get("temp_dir")
                if temp_dir and os.path.isdir(temp_dir):
                    try:
                        import zipfile
                        import io
                        mineru_zip_path = os.path.join(temp_dir, "mineru_layout.zip")
                        mineru_extract_dir = os.path.join(temp_dir, "mineru_extracted")

                        # Save ZIP file to temp directory
                        with open(mineru_zip_path, 'wb') as f:
                            f.write(mineru_doc.content)
                        logger.debug(LogModule.EXTRACT, f"[ATTACHMENT] Saved MinerU ZIP to {mineru_zip_path}")

                        # Extract ZIP contents to mineru_extracted subdirectory
                        os.makedirs(mineru_extract_dir, exist_ok=True)
                        with zipfile.ZipFile(io.BytesIO(mineru_doc.content), 'r') as zip_ref:
                            zip_ref.extractall(mineru_extract_dir)
                        logger.debug(LogModule.EXTRACT, f"[ATTACHMENT] Extracted MinerU ZIP to {mineru_extract_dir}")

                        # Store paths in task_state for reference
                        task_state["mineru_zip_path"] = mineru_zip_path
                        task_state["mineru_extract_dir"] = mineru_extract_dir
                    except Exception as extract_error:
                        logger.warning(LogModule.EXTRACT, f"[ATTACHMENT] Failed to extract MinerU ZIP to temp directory: {extract_error}")

            # --- PaddleOCR layout ZIP ---
            paddle_doc = attachment_dict.get("paddle")
            if paddle_doc and hasattr(paddle_doc, "content") and paddle_doc.content:
                task_state["layout_source_zip"] = paddle_doc.content
                task_state.setdefault("layout_engine", "paddle")
                temp_dir = task_state.get("temp_dir")
                if temp_dir and os.path.isdir(temp_dir):
                    try:
                        paddle_zip_path = os.path.join(temp_dir, "paddle_layout.zip")
                        with open(paddle_zip_path, 'wb') as f:
                            f.write(paddle_doc.content)
                        task_state["paddle_zip_path"] = paddle_zip_path
                        logger.debug(LogModule.EXTRACT, f"[ATTACHMENT] Saved PaddleOCR ZIP to {paddle_zip_path}")
                    except Exception as extract_error:
                        logger.warning(LogModule.EXTRACT, f"[ATTACHMENT] Failed to save PaddleOCR ZIP: {extract_error}")
        except Exception as attachment_error:
            logger.debug(LogModule.WORKFLOW, f"[ATTACHMENT] Failed to sync workflow attachments ({reason}): {attachment_error}")
    
    def _try_reuse_layout_results(
        self,
        task_id: str,
        workflow: Any,
        payload: Any,
        task_state: Dict[str, Any],
        file_contents: bytes,
        original_filename: str
    ) -> None:
        """
        Try to reuse layout parsing results from Extract phase or Convert phase.
        This avoids re-running the OCR/layout parser (MinerU or PaddleOCR).

        When searching for reusable results from other tasks, the layout engine
        must match the currently requested convert_engine.  If the cached result
        was produced by a different engine, it is skipped so that a fresh parse
        with the current engine is performed.

        Args:
            task_id: Task identifier
            workflow: Workflow instance
            payload: Task payload
            task_state: Task state dictionary
            file_contents: File content bytes
            original_filename: Original filename
        """
        try:
            convert_engine = getattr(payload, 'convert_engine', 'mineru')
            is_format_conversion = task_state.get("is_format_conversion", False) or task_state.get("convert_only", False)
            is_pdf_file = original_filename.lower().endswith('.pdf')

            # Only try to reuse for PDF files with a known layout engine
            if not is_pdf_file:
                return

            # MinerU-specific engines have persistent artifacts (ZIP, extract dir)
            # that can be copied across tasks.  Other engines (e.g. Paddle) are
            # cloud-based and do not have persistent local artifacts to reuse yet.
            if convert_engine not in ("mineru", "mineru_local"):
                return
            
            import hashlib
            # Calculate file hash to find Extract phase task_state
            file_hash = hashlib.sha1(file_contents).hexdigest()
            
            # First, check if current task_state already has results from the same engine
            extract_task_state = None
            if (task_state.get("mineru_extract_dir") or
                task_state.get("mineru_zip_path") or
                task_state.get("layout_source_zip")):
                # Verify engine consistency — if task_state was populated by a
                # different engine, skip reuse so a fresh parse runs with the
                # currently requested engine.
                cached_engine = task_state.get("layout_engine")
                if cached_engine and cached_engine != convert_engine:
                    logger.info(
                        LogModule.EXTRACT,
                        f"[LAYOUT-REUSE] Skipping cached results in current task_state for task {task_id}: "
                        f"cached_engine={cached_engine}, requested_engine={convert_engine}",
                    )
                else:
                    extract_task_state = task_state
                    logger.info(
                        LogModule.EXTRACT,
                        f"[LAYOUT-REUSE] Found layout results in current task_state for task {task_id}: "
                        f"mineru_extract_dir={task_state.get('mineru_extract_dir')}, "
                        f"mineru_zip_path={task_state.get('mineru_zip_path')}, "
                        f"has_layout_source_zip={bool(task_state.get('layout_source_zip'))}, "
                        f"engine={cached_engine or 'unknown'}",
                    )
            else:
                # Search for Extract phase task_state with same file hash
                logger.debug(
                    LogModule.EXTRACT,
                    f"[LAYOUT-REUSE] Current task_state does not have MinerU results, "
                    f"searching other tasks for file hash: {file_hash[:16]}..., filename: {original_filename}"
                )
                
                # Get current file size for comparison
                current_file_size = len(file_contents)
                
                # Get all tasks from task manager
                all_tasks = self.task_manager.get_all_tasks()
                logger.debug(
                    LogModule.EXTRACT,
                    f"[LAYOUT-REUSE] Total tasks in tasks_state: {len(all_tasks)}, "
                    f"current task_id: {task_id}"
                )
                
                # First pass: Look for Extract phase tasks (convert_only=False)
                # Second pass: Look for Convert phase tasks (convert_only=True) if no Extract task found
                extract_task_candidates = []
                convert_task_candidates = []
                
                for other_task_id, other_task_state in all_tasks.items():
                    # Skip current task
                    if other_task_id == task_id:
                        continue
                    
                    # Check if it has layout results AND the engine matches
                    has_results = (
                        other_task_state.get("mineru_extract_dir") or
                        other_task_state.get("mineru_zip_path") or
                        other_task_state.get("layout_source_zip")
                    )
                    if not has_results:
                        logger.debug(
                            LogModule.EXTRACT,
                            f"[LAYOUT-REUSE] Skipping task {other_task_id}: no layout results"
                        )
                        continue

                    # Verify engine consistency — do not reuse results produced
                    # by a different layout engine (e.g. skip MinerU results when
                    # the user switched to Paddle).
                    cached_engine = other_task_state.get("layout_engine")
                    if cached_engine and cached_engine != convert_engine:
                        logger.debug(
                            LogModule.EXTRACT,
                            f"[LAYOUT-REUSE] Skipping task {other_task_id}: "
                            f"cached_engine={cached_engine}, requested_engine={convert_engine}",
                        )
                        continue
                    
                    # Categorize by task type
                    is_convert_only = other_task_state.get("convert_only", False)
                    if is_convert_only:
                        convert_task_candidates.append((other_task_id, other_task_state))
                    else:
                        extract_task_candidates.append((other_task_id, other_task_state))
                
                # Prioritize Extract phase tasks, but also consider Convert phase tasks
                candidates = extract_task_candidates + convert_task_candidates
                
                for other_task_id, other_task_state in candidates:
                    is_convert_only = other_task_state.get("convert_only", False)
                    task_type = "Convert" if is_convert_only else "Extract"
                    logger.debug(
                        LogModule.EXTRACT,
                        f"[LAYOUT-REUSE] Checking {task_type} task {other_task_id}: "
                        f"filename={other_task_state.get('original_filename')}, "
                        f"has_mineru_extract_dir={bool(other_task_state.get('mineru_extract_dir'))}, "
                        f"has_mineru_zip_path={bool(other_task_state.get('mineru_zip_path'))}, "
                        f"has_layout_source_zip={bool(other_task_state.get('layout_source_zip'))}"
                    )
                    
                    # Check if file hash matches (if available in task_state)
                    other_file_hash = None
                    other_file_size = None
                    if "original_file_path" in other_task_state:
                        try:
                            other_file_path = other_task_state["original_file_path"]
                            if os.path.exists(other_file_path):
                                other_file_size = os.path.getsize(other_file_path)
                                with open(other_file_path, 'rb') as f:
                                    other_file_contents = f.read()
                                    other_file_hash = hashlib.sha1(other_file_contents).hexdigest()
                        except Exception as e:
                            logger.debug(
                                LogModule.EXTRACT,
                                f"[LAYOUT-REUSE] Failed to read file from task {other_task_id}: {e}"
                            )
                            pass
                    
                    # Match criteria: hash matches OR (filename matches AND file size matches)
                    hash_matches = other_file_hash == file_hash if other_file_hash else False
                    filename_matches = other_task_state.get("original_filename") == original_filename
                    size_matches = other_file_size == current_file_size if other_file_size else False
                    
                    logger.debug(
                        LogModule.EXTRACT,
                        f"[LAYOUT-REUSE] Task {other_task_id} match check: "
                        f"hash_matches={hash_matches}, filename_matches={filename_matches}, "
                        f"size_matches={size_matches}, "
                        f"other_file_hash={other_file_hash[:16] if other_file_hash else 'None'}..., "
                        f"current_file_hash={file_hash[:16]}..., "
                        f"other_file_size={other_file_size}, current_file_size={current_file_size}"
                    )
                    
                    if hash_matches or (filename_matches and size_matches):
                        extract_task_state = other_task_state
                        task_type = "Convert" if is_convert_only else "Extract"
                        logger.info(
                            LogModule.EXTRACT,
                            f"[LAYOUT-REUSE] Found {task_type} phase task_state for task {task_id}: "
                            f"source_task_id={other_task_id}, "
                            f"match_reason={'hash' if hash_matches else 'filename+size'}, "
                            f"mineru_extract_dir={extract_task_state.get('mineru_extract_dir')}, "
                            f"mineru_zip_path={extract_task_state.get('mineru_zip_path')}, "
                            f"has_layout_source_zip={bool(extract_task_state.get('layout_source_zip'))}"
                        )
                        break
                    else:
                        logger.debug(
                            LogModule.EXTRACT,
                            f"[LAYOUT-REUSE] Task {other_task_id} does not match: "
                            f"hash_matches={hash_matches}, filename_matches={filename_matches}, "
                            f"size_matches={size_matches}"
                        )
                
                if not extract_task_state:
                    logger.info(
                        LogModule.EXTRACT,
                        f"[LAYOUT-REUSE] No matching Extract phase task_state found for task {task_id}. "
                        f"Will proceed with normal MinerU conversion (may re-upload/re-download)."
                    )
            
            # If found, copy MinerU results to current task_state
            # (Only copy if extract_task_state is different from current task_state)
            if extract_task_state and extract_task_state is not task_state:
                # Copy mineru_extract_dir if it exists and directory is still valid
                extract_dir = extract_task_state.get("mineru_extract_dir")
                if extract_dir and os.path.exists(extract_dir):
                    task_state["mineru_extract_dir"] = extract_dir
                    logger.info(
                        LogModule.EXTRACT,
                        f"[LAYOUT-REUSE] Copied mineru_extract_dir from Extract phase to translation phase: {extract_dir}"
                    )
                
                # Copy layout_source_zip if available
                layout_source_zip = extract_task_state.get("layout_source_zip")
                if layout_source_zip:
                    task_state["layout_source_zip"] = layout_source_zip
                    logger.info(
                        LogModule.EXTRACT,
                        f"[LAYOUT-REUSE] Copied layout_source_zip from Extract phase to translation phase "
                        f"(size: {len(layout_source_zip)} bytes)"
                    )
                    
                    # Also set workflow._layout_source_zip so md_based_workflow.py can use it
                    if hasattr(workflow, "_layout_source_zip"):
                        workflow._layout_source_zip = layout_source_zip
                        logger.debug(
                            LogModule.EXTRACT,
                            f"[LAYOUT-REUSE] Set workflow._layout_source_zip for task {task_id}"
                        )
                
                # Copy mineru_zip_path if available
                mineru_zip_path = extract_task_state.get("mineru_zip_path")
                if mineru_zip_path and os.path.exists(mineru_zip_path):
                    task_state["mineru_zip_path"] = mineru_zip_path
                    logger.info(
                        LogModule.EXTRACT,
                        f"[LAYOUT-REUSE] Copied mineru_zip_path from Extract phase to translation phase: {mineru_zip_path}"
                    )

                # Copy paddle_zip_path if available
                paddle_zip_path = extract_task_state.get("paddle_zip_path")
                if paddle_zip_path and os.path.exists(paddle_zip_path):
                    task_state["paddle_zip_path"] = paddle_zip_path
                    logger.info(
                        LogModule.EXTRACT,
                        f"[LAYOUT-REUSE] Copied paddle_zip_path from Extract phase to translation phase: {paddle_zip_path}"
                    )
                
                # Copy MinerU attachment if available
                extract_attachments = extract_task_state.get("attachments", {})
                if "mineru" in extract_attachments:
                    if "attachments" not in task_state:
                        task_state["attachments"] = {}
                    task_state["attachments"]["mineru"] = extract_attachments["mineru"]
                    logger.info(
                        LogModule.EXTRACT,
                        f"[LAYOUT-REUSE] Copied MinerU attachment from Extract phase to translation phase"
                    )
                    
                    # CRITICAL: Also restore MinerU attachment to workflow so it can be used
                    # This is needed for md_based_workflow.py to access MinerU results
                    if hasattr(workflow, "attachment") and workflow.attachment:
                        try:
                            mineru_attachment = extract_attachments["mineru"]
                            if hasattr(mineru_attachment, "document") and mineru_attachment.document:
                                workflow.attachment.add_document("mineru", mineru_attachment.document)
                                logger.info(
                                    LogModule.EXTRACT,
                                    f"[LAYOUT-REUSE] Restored MinerU attachment to workflow for task {task_id}"
                                )
                            elif layout_source_zip:
                                # Fallback: create document from layout_source_zip
                                from ir.document import Document
                                mineru_doc = Document.from_bytes(content=layout_source_zip, suffix=".zip", stem="mineru")
                                workflow.attachment.add_document("mineru", mineru_doc)
                                workflow._layout_source_zip = layout_source_zip
                                logger.info(
                                    LogModule.EXTRACT,
                                    f"[LAYOUT-REUSE] Restored MinerU ZIP to workflow from layout_source_zip for task {task_id}"
                                )
                        except Exception as restore_error:
                            logger.warning(
                                LogModule.EXTRACT,
                                f"[LAYOUT-REUSE] Failed to restore MinerU attachment to workflow: {restore_error}"
                            )
                
                # CRITICAL: Copy layout_prepared_chunks and related data from Extract phase
                # This ensures translation phase uses chunks that exclude excluded segments
                if "layout_prepared_chunks" in extract_task_state:
                    task_state["layout_prepared_chunks"] = extract_task_state["layout_prepared_chunks"]
                    logger.info(
                        LogModule.EXTRACT,
                        f"[LAYOUT-REUSE] Copied layout_prepared_chunks from Extract phase to translation phase: "
                        f"{len(extract_task_state['layout_prepared_chunks'])} chunks"
                    )
                if "layout_chunk_block_map" in extract_task_state:
                    task_state["layout_chunk_block_map"] = extract_task_state["layout_chunk_block_map"]
                    logger.debug(
                        LogModule.EXTRACT,
                        f"[LAYOUT-REUSE] Copied layout_chunk_block_map from Extract phase to translation phase"
                    )
                if "segment_layout_block_map" in extract_task_state:
                    task_state["segment_layout_block_map"] = extract_task_state["segment_layout_block_map"]
                    logger.debug(
                        LogModule.EXTRACT,
                        f"[LAYOUT-REUSE] Copied segment_layout_block_map from Extract phase to translation phase"
                    )
                if "layout_chunk_block_texts" in extract_task_state:
                    task_state["layout_chunk_block_texts"] = extract_task_state["layout_chunk_block_texts"]
                    logger.debug(
                        LogModule.EXTRACT,
                        f"[LAYOUT-REUSE] Copied layout_chunk_block_texts from Extract phase to translation phase"
                    )
                
                # Also copy segments_metadata to preserve excluded_segments and excluded_segment_indices.
                # IMPORTANT:
                # - If task_state already has segments_metadata (e.g. inherited from Convert phase),
                #   we MUST NOT overwrite it with Extract phase data, otherwise user-selected
                #   exclusions such as "Exclude All" will be lost and all-excluded detection
                #   in complete_translation_with_source_only() will fail.
                # - Only when segments_metadata is missing in task_state do we inherit it from
                #   Extract phase, and in that case we still filter out user_selected/unknown
                #   so a brand new translation does not accidentally start with all segments excluded.
                if "segments_metadata" not in task_state and "segments_metadata" in extract_task_state:
                    import copy
                    task_state["segments_metadata"] = copy.deepcopy(extract_task_state["segments_metadata"])
                    raw_excluded = task_state["segments_metadata"].get("excluded_segments", {})
                    if isinstance(raw_excluded, dict):
                        user_based_reasons = ("user_selected", "unknown")

                        def _exclusion_reason_str(info):
                            if isinstance(info, dict):
                                return info.get("reason", "unknown")
                            return info if isinstance(info, str) else "unknown"

                        filtered_excluded = {
                            k: v for k, v in raw_excluded.items()
                            if _exclusion_reason_str(v) not in user_based_reasons
                        }
                        if len(filtered_excluded) != len(raw_excluded):
                            removed = len(raw_excluded) - len(filtered_excluded)
                            task_state["segments_metadata"]["excluded_segments"] = filtered_excluded
                            task_state["segments_metadata"]["excluded_segment_indices"] = sorted(
                                int(k) for k in filtered_excluded.keys()
                            )
                            logger.info(
                                LogModule.EXTRACT,
                                f"[LAYOUT-REUSE] Filtered out user_selected/unknown from inherited exclusions: "
                                f"{removed} removed, {len(filtered_excluded)} content-based kept"
                            )
                    excluded_segments_count = len(task_state["segments_metadata"].get("excluded_segments", {}))
                    excluded_indices_count = len(task_state["segments_metadata"].get("excluded_segment_indices", []))
                    if excluded_segments_count > 0 or excluded_indices_count > 0:
                        logger.info(
                            LogModule.EXTRACT,
                            f"[LAYOUT-REUSE] Copied segments_metadata from Extract phase to translation phase: "
                            f"{excluded_segments_count} excluded_segments (dict), {excluded_indices_count} excluded_segment_indices (list)"
                        )
                
                # CRITICAL: Copy source_chunks_cache from Extract phase to translation phase
                # This ensures record_translation_segments uses the correct source_segments indexed by segment_index
                if "source_chunks_cache" in extract_task_state:
                    task_state["source_chunks_cache"] = extract_task_state["source_chunks_cache"].copy()
                    cache_segments_count = len(extract_task_state.get("source_chunks_cache", {}).get("segments", []))
                    logger.info(
                        LogModule.EXTRACT,
                        f"[LAYOUT-REUSE] Copied source_chunks_cache from Extract phase to translation phase: "
                        f"{cache_segments_count} segments (indexed by segment_index)"
                    )
                
                # CRITICAL: Copy format settings from Extract/Convert phase to translation phase
                # This ensures format settings (table_body_format, equation_format) are preserved
                # Only copy if not already set in task_state (payload takes precedence)
                if "table_body_format" in extract_task_state and "table_body_format" not in task_state:
                    task_state["table_body_format"] = extract_task_state["table_body_format"]
                    logger.info(
                        LogModule.EXTRACT,
                        f"[LAYOUT-REUSE] Copied table_body_format from Extract/Convert phase to translation phase: "
                        f"{extract_task_state['table_body_format']}"
                    )
                if "equation_format" in extract_task_state and "equation_format" not in task_state:
                    task_state["equation_format"] = extract_task_state["equation_format"]
                    logger.info(
                        LogModule.EXTRACT,
                        f"[LAYOUT-REUSE] Copied equation_format from Extract/Convert phase to translation phase: "
                        f"{extract_task_state['equation_format']}"
                    )
                
                # Also copy format settings from payload if available in extract_task_state
                extract_payload = extract_task_state.get("payload")
                if extract_payload:
                    if isinstance(extract_payload, dict):
                        if "table_body_format" in extract_payload and "table_body_format" not in task_state:
                            task_state["table_body_format"] = extract_payload["table_body_format"]
                        if "equation_format" in extract_payload and "equation_format" not in task_state:
                            task_state["equation_format"] = extract_payload["equation_format"]
                    elif hasattr(extract_payload, 'table_body_format') or hasattr(extract_payload, 'equation_format'):
                        if hasattr(extract_payload, 'table_body_format') and "table_body_format" not in task_state:
                            task_state["table_body_format"] = getattr(extract_payload, 'table_body_format', None)
                        if hasattr(extract_payload, 'equation_format') and "equation_format" not in task_state:
                            task_state["equation_format"] = getattr(extract_payload, 'equation_format', None)
                
                # Also update current payload with format settings if they exist in task_state
                if "table_body_format" in task_state or "equation_format" in task_state:
                    if payload:
                        if isinstance(payload, dict):
                            if "table_body_format" in task_state:
                                payload["table_body_format"] = task_state["table_body_format"]
                            if "equation_format" in task_state:
                                payload["equation_format"] = task_state["equation_format"]
                        elif hasattr(payload, 'table_body_format') or hasattr(payload, 'equation_format'):
                            try:
                                if "table_body_format" in task_state:
                                    setattr(payload, 'table_body_format', task_state["table_body_format"])
                                if "equation_format" in task_state:
                                    setattr(payload, 'equation_format', task_state["equation_format"])
                            except Exception as e:
                                logger.debug(LogModule.WORKFLOW, f"[LAYOUT-REUSE] Failed to update payload format settings: {e}")
        except Exception as reuse_error:
            logger.warning(
                LogModule.EXTRACT,
                f"[LAYOUT-REUSE] Failed to reuse MinerU results from Extract phase: {reuse_error}",
                exc_info=True
            )
    
    def _prepare_markdown_based_preview(
        self,
        task_id: str,
        workflow: Any,
        payload: Any,
        task_state: Dict[str, Any],
        original_filename: str,
        is_format_conversion: bool
    ) -> None:
        """
        Prepare preview for markdown-based workflows (PDF) from converted/translated markdown.
        
        Args:
            task_id: Task identifier
            workflow: Workflow instance
            payload: Task payload
            task_state: Task state dictionary
            original_filename: Original filename
            is_format_conversion: Whether this is a format conversion task
        """
        try:
            preview_ready = task_state.get("source_preview", {}).get("ready", False)
            if preview_ready:
                # Preview already exists, but check if source_chunks_cache and chunk_to_segment_map are available
                # These are needed for translation even if preview is ready
                has_cache = task_state.get("source_chunks_cache", {}).get("segments")
                has_map = task_state.get("chunk_to_segment_map")
                if has_cache and has_map:
                    logger.debug(LogModule.EXTRACT, f"[PREVIEW] Task {task_id}: Preview already ready with source_chunks_cache and chunk_to_segment_map")
                    return
                else:
                    logger.info(LogModule.EXTRACT, f"[PREVIEW] Task {task_id}: Preview ready but missing source_chunks_cache or chunk_to_segment_map, regenerating...")
            
            # Check if we can generate preview
            # For translation phase, we need to generate preview from original markdown (document_original)
            # For format conversion phase, we can use document_translated (which is the converted markdown)
            has_doc_original = hasattr(workflow, 'document_original') and workflow.document_original is not None
            has_doc_translated = hasattr(workflow, 'document_translated') and workflow.document_translated is not None
            
            # Use document_original for translation phase, document_translated for format conversion
            can_generate_preview = (is_format_conversion and has_doc_translated) or (not is_format_conversion and has_doc_original)
            
            if not can_generate_preview:
                logger.debug(LogModule.EXTRACT, f"[PREVIEW] Task {task_id}: Cannot generate preview - is_format_conversion={is_format_conversion}, has_doc_original={has_doc_original}, has_doc_translated={has_doc_translated}")
                return
            
            logger.info(LogModule.EXTRACT, f"[PREVIEW] Task {task_id}: Starting markdown-based preview generation...")
            self.task_manager.add_log(task_id, "info", "Starting preview generation...")
            
            from workflow.md_based_workflow import MarkdownBasedWorkflow
            
            if not isinstance(workflow, MarkdownBasedWorkflow):
                logger.warning(LogModule.EXTRACT, f"[PREVIEW] Task {task_id}: Workflow is not MarkdownBasedWorkflow")
                return
            
            # Check if this is a PDF file and markdown fallback is disabled
            is_pdf_file = original_filename.lower().endswith('.pdf')
            disable_markdown_fallback = False
            if is_pdf_file:
                try:
                    from backend.config.system_config import get_system_config
                    system_config = get_system_config()
                    disable_markdown_fallback = system_config.pdf.disable_markdown_fallback
                    if disable_markdown_fallback:
                        logger.info(LogModule.CONFIG, f"[PREVIEW] Task {task_id}: PDF markdown fallback is disabled in system config")
                except Exception as config_error:
                    logger.debug(LogModule.EXTRACT, f"[PREVIEW] Task {task_id}: Failed to check PDF config: {config_error}")
            
            # If PDF and markdown fallback is disabled, use layout-based preview
            if is_pdf_file and disable_markdown_fallback:
                logger.info(LogModule.EXTRACT, f"[PREVIEW] Task {task_id}: Using layout-based preview (markdown fallback disabled)")
                self.task_manager.add_log(task_id, "info", "PDF markdown fallback is disabled. Using layout-based preview.")

                layout_doc = task_state.get("layout_document")
                if layout_doc is None:
                    # Try to load from layout_source_zip
                    layout_source_zip = task_state.get("layout_source_zip")
                    if layout_source_zip:
                        try:
                            from layout.registry import load_layout_from_engine_zip
                            _raw_engine = task_state.get("layout_engine") or task_state.get("convert_engine") or "mineru"
                            _layout_engine = str(_raw_engine).strip().lower()
                            if _layout_engine.startswith("paddle"):
                                _layout_engine = "paddle"
                            elif _layout_engine.startswith("mineru"):
                                _layout_engine = "mineru"
                            layout_doc = load_layout_from_engine_zip(_layout_engine, layout_source_zip)
                            if layout_doc:
                                task_state["layout_document"] = layout_doc
                                logger.info(LogModule.EXTRACT, f"[PREVIEW] Task {task_id}: Loaded layout_document from layout_source_zip")
                        except Exception as load_error:
                            logger.warning(LogModule.EXTRACT, f"[PREVIEW] Task {task_id}: Failed to load layout_document: {load_error}")

                if layout_doc:
                    self.source_preview_service.prepare_layout_preview_from_layout(
                        task_id, layout_doc, payload, task_state, reason="markdown_fallback_disabled"
                    )
                    return

                # No layout available (e.g. single-phase immediate/queued mode without Extract phase).
                # Fall through to markdown-based preview generation to populate source_chunks_cache.
                logger.info(LogModule.EXTRACT, f"[PREVIEW] Task {task_id}: No layout document available, falling back to markdown-based preview")
            
            # Generate preview from markdown content
            try:
                from extractor.markdown_based_extractor import MarkdownBasedExtractor
                
                # Export markdown content
                # CRITICAL: For translation phase, use document_original (untranslated markdown)
                # For format conversion phase, use document_translated (converted markdown)
                markdown_content = None
                if is_format_conversion:
                    # Format conversion: use document_translated (converted markdown)
                    if hasattr(workflow, 'export_to_markdown'):
                        markdown_content = workflow.export_to_markdown()
                    elif hasattr(workflow, 'document_translated') and workflow.document_translated:
                        markdown_content = workflow.document_translated.content.decode('utf-8') if hasattr(workflow.document_translated.content, 'decode') else str(workflow.document_translated.content)
                else:
                    # Translation phase: use document_original (untranslated markdown)
                    # This ensures chunks match between Extract and Translation phases
                    if hasattr(workflow, 'document_original') and workflow.document_original:
                        # For markdown files, document_original is already markdown
                        if hasattr(workflow.document_original, 'content'):
                            markdown_content = workflow.document_original.content.decode('utf-8') if hasattr(workflow.document_original.content, 'decode') else str(workflow.document_original.content)
                        else:
                            markdown_content = str(workflow.document_original)
                    elif hasattr(workflow, 'export_to_markdown'):
                        markdown_content = workflow.export_to_markdown()
                
                if not markdown_content:
                    logger.warning(LogModule.EXTRACT, f"[PREVIEW] Task {task_id}: Cannot export markdown content from workflow")
                    return
                
                if not markdown_content:
                    logger.warning(LogModule.EXTRACT, f"[PREVIEW] Task {task_id}: Markdown content is empty")
                    return
                
                # Extract segments from markdown
                chunk_size = chunk_size_service.get_chunk_size(payload, task_id)
                deep_split_enabled = bool(task_state.get("deep_split", True))
                result = MarkdownBasedExtractor(markdown_content, chunk_size=chunk_size, deep_split=deep_split_enabled).extract()
                
                if result.total_segments > 0:
                    import hashlib
                    content_hash = hashlib.sha1(markdown_content.encode("utf-8")).hexdigest()
                    
                    task_state["source_preview"] = {
                        "segments": result.segments[:SOURCE_PREVIEW_SEGMENTS_LIMIT],
                        "total_segments": result.total_segments,
                        "ready": True,
                    }
                    task_state["source_chunks_cache"] = {
                        "content_hash": content_hash,
                        "chunk_size": chunk_size,
                        "segments": result.segments,
                        "total_segments": result.total_segments,
                        "created_at": time.time(),
                    }
                    workflow_type = getattr(payload, 'workflow_type', 'markdown_based')
                    
                    # CRITICAL: Update segments_metadata instead of completely overwriting it
                    # This preserves important data from Extract phase (excluded_segments, excluded_segment_indices, etc.)
                    # Only update fields that need to change (content_hash, chunk_size) or are specific to this preview generation
                    existing_segments_metadata = task_state.get("segments_metadata", {})
                    
                    # Initialize segments_metadata if it doesn't exist, otherwise update it
                    if not existing_segments_metadata:
                        task_state["segments_metadata"] = {
                            "source": "markdown_based",
                            "workflow_type": workflow_type,
                            "chunk_size": chunk_size,
                            "content_hash": content_hash,
                            "separators_after": result.separators_after,
                            "segment_info": result.segment_info,
                        }
                    else:
                        # Update only the fields that need to change
                        task_state["segments_metadata"].update({
                            "source": "markdown_based",  # Update source to indicate this is from markdown preview
                            "workflow_type": workflow_type,  # Update workflow_type
                            "chunk_size": chunk_size,  # Update chunk_size if it changed
                            "content_hash": content_hash,  # Update content_hash based on new markdown
                            "separators_after": result.separators_after,  # Update separators_after from new extraction
                            "segment_info": result.segment_info,  # Update segment_info from new extraction
                        })
                    
                    # Log preservation of excluded data
                    excluded_segments_count = len(task_state["segments_metadata"].get("excluded_segments", {}))
                    excluded_indices_count = len(task_state["segments_metadata"].get("excluded_segment_indices", []))
                    if excluded_segments_count > 0 or excluded_indices_count > 0:
                        logger.debug(
                            LogModule.EXCLUSION,
                            f"[PREVIEW] Task {task_id}: Preserved exclusion data from Extract phase: "
                            f"{excluded_segments_count} excluded_segments, {excluded_indices_count} excluded_segment_indices"
                        )
                    
                    # Build chunk_to_segment_map for chunks generation
                    # CRITICAL: Mark images, formulas, and tables as excluded (same as PDF workflow)
                    from utils.translation_segments import _is_image_segment, _is_formula_segment, _is_table_segment
                    excluded_segment_indices = []
                    
                    # CRITICAL: Extract and save image data for display (same as PDF workflow)
                    # Build image_data_map: {placeholder_id: {"data": base64_data_uri, "alt": "..."}}
                    image_data_map: Dict[str, Dict[str, str]] = {}
                    existing_image_map = task_state.get("image_data_map")
                    if isinstance(existing_image_map, dict):
                        image_data_map.update({
                            str(k): {
                                "data": (v or {}).get("data", ""),
                                "alt": (v or {}).get("alt", ""),
                            }
                            for k, v in existing_image_map.items()
                        })

                    from utils.mineru_image_data_map import (
                        lookup_image_data_entry,
                        populate_image_data_map_from_mineru_zip,
                    )
                    mineru_images_added = populate_image_data_map_from_mineru_zip(
                        image_data_map,
                        task_state,
                        layout_doc=task_state.get("layout_document"),
                    )
                    if mineru_images_added:
                        logger.info(
                            LogModule.EXTRACT,
                            f"[PREVIEW] Task {task_id}: Populated {mineru_images_added} MinerU ZIP "
                            f"image_data_map entries for markdown preview",
                        )
                    
                    # Extract image data from markdown segments
                    import re
                    import base64
                    import mimetypes
                    import os
                    
                    # Pattern for placeholder: <ph-xxx>
                    ph_pattern = r"<ph-([a-zA-Z0-9]+)>"
                    # Pattern for markdown image: ![alt](path)
                    markdown_image_pattern = r"!\[([^\]]*)\]\(([^)]+)\)"
                    # Pattern for base64 image in markdown: ![alt](data:image/...;base64,...)
                    base64_image_pattern = r"!\[([^\]]*)\]\(data:image/([^;]+);base64,([^)]+)\)"
                    
                    # Get target language from payload for language-based exclusion
                    target_lang = getattr(payload, 'to_lang', None) or getattr(payload, 'target_lang', None)
                    
                    # Use unified exclusion detection with ExclusionManager
                    from exclusion.core import ExclusionManager, ExclusionReason, detect_exclusion_reason
                    excluded_segments_with_reasons = {}
                    # When inheriting from convert task, preserve user's exclusion choices from Extract (do not re-detect)
                    use_inherited_exclusions = bool(
                        not is_format_conversion and task_state.get("convert_task_id")
                    )
                    if use_inherited_exclusions:
                        existing_excluded = task_state.get("segments_metadata", {}).get("excluded_segments", {})
                        if isinstance(existing_excluded, dict):
                            try:
                                excluded_segment_indices[:] = sorted(
                                    int(k) for k in existing_excluded.keys()
                                    if str(k).isdigit()
                                )
                            except (ValueError, TypeError):
                                excluded_segment_indices.clear()
                        logger.info(
                            LogModule.EXTRACT,
                            f"[PREVIEW] Task {task_id}: Preserving inherited exclusion state from Extract (convert_task_id={task_state.get('convert_task_id')}), "
                            f"excluded_segment_indices={excluded_segment_indices}"
                        )
                    
                    # Respect exclusion_defaults (e.g. language_match=false for image translation flow)
                    default_excluded = ExclusionReason.get_default_excluded()

                    for idx, seg_text in enumerate(result.segments):
                        is_image = _is_image_segment(seg_text)
                        is_formula = _is_formula_segment(seg_text)
                        is_table = _is_table_segment(seg_text)
                        
                        if not use_inherited_exclusions:
                            # CRITICAL: Only auto-exclude when reason is in exclusion_defaults (get_default_excluded).
                            # E.g. language_match=false means do not exclude by default for image/PDF translation flow.
                            # Tables are excluded only when exclusion_defaults.table is true.
                            detected_result = detect_exclusion_reason(
                                text=seg_text,
                                block_type="table" if is_table else None,
                                target_lang=target_lang,
                                is_image=is_image,
                                is_table=is_table
                            )
                            
                            if detected_result:
                                detected_reason, detected_metadata = detected_result
                                if detected_reason in default_excluded:
                                    excluded_segments_with_reasons[idx] = detected_reason
                                    excluded_segment_indices.append(idx)
                                    if idx < 5:
                                        logger.debug(
                                            LogModule.EXTRACT,
                                            f"[PREVIEW] Task {task_id}: Marked segment {idx} as excluded "
                                            f"(reason={detected_reason.value}): '{seg_text[:50]}...'",
                                        )
                                else:
                                    logger.trace(
                                        LogModule.EXTRACT,
                                        f"[PREVIEW] Task {task_id}: Detected segment {idx} as {detected_reason.value} (not auto-excluded by exclusion_defaults): '{seg_text[:50]}...'"
                                    )
                        
                        # Extract image data for image segments
                        if is_image:
                            placeholder_id = None
                            image_data_uri = None
                            alt_text = "Image"
                            
                            # Check for placeholder: <ph-xxx>
                            ph_match = re.search(ph_pattern, seg_text)
                            if ph_match:
                                placeholder_id = ph_match.group(1)
                                # Try to get image data from workflow attachment
                                if hasattr(workflow, 'attachment') and workflow.attachment:
                                    try:
                                        attachment_dict = workflow.attachment.attachment_dict
                                        if placeholder_id in attachment_dict:
                                            image_doc = attachment_dict[placeholder_id]
                                            if hasattr(image_doc, 'content') and image_doc.content:
                                                image_bytes = image_doc.content if isinstance(image_doc.content, bytes) else bytes(image_doc.content)
                                                # Determine MIME type from suffix or content
                                                suffix = getattr(image_doc, 'suffix', '') or '.png'
                                                mime = mimetypes.guess_type(f"image{suffix}")[0] or "image/png"
                                                image_data_uri = f"data:{mime};base64,{base64.b64encode(image_bytes).decode('ascii')}"
                                                alt_text = getattr(image_doc, 'stem', placeholder_id) or placeholder_id
                                                logger.debug(
                                                    LogModule.EXTRACT,
                                                    f"[PREVIEW] Task {task_id}: Extracted image data for placeholder {placeholder_id} "
                                                    f"from workflow attachment ({len(image_bytes)} bytes)"
                                                )
                                    except Exception as e:
                                        logger.debug(
                                            LogModule.EXTRACT,
                                            f"[PREVIEW] Task {task_id}: Failed to get image data for placeholder {placeholder_id} "
                                            f"from workflow attachment: {e}"
                                        )
                                
                                # If not found in attachment, try to get from layout_source_zip (for PDF-converted MD files)
                                if not image_data_uri:
                                    layout_source_zip = task_state.get("layout_source_zip")
                                    if layout_source_zip:
                                        try:
                                            import zipfile
                                            import io
                                            import zlib
                                            # Debug: Check data format and handle zlib compressed data
                                            if isinstance(layout_source_zip, bytes) and len(layout_source_zip) > 2:
                                                header = layout_source_zip[:2]
                                                # Check if it's zlib compressed data (0x78 0x9c or 0x78 0xda)
                                                if header == b'\x78\x9c' or header == b'\x78\xda':
                                                    logger.debug(
                                                        LogModule.EXTRACT,
                                                        f"[PREVIEW] Task {task_id}: layout_source_zip is zlib compressed, decompressing..."
                                                    )
                                                    try:
                                                        layout_source_zip = zlib.decompress(layout_source_zip)
                                                        logger.debug(
                                                            LogModule.EXTRACT,
                                                            f"[PREVIEW] Task {task_id}: Decompressed layout_source_zip to {len(layout_source_zip)} bytes"
                                                        )
                                                    except Exception as zlib_error:
                                                        logger.warning(
                                                            LogModule.EXTRACT,
                                                            f"[PREVIEW] Task {task_id}: Failed to decompress layout_source_zip: {zlib_error}"
                                                        )
                                                        raise
                                            zip_file = zipfile.ZipFile(io.BytesIO(layout_source_zip))
                                            zip_entries = zip_file.namelist()
                                            
                                            # Try to find image file matching placeholder_id
                                            for entry_name in zip_entries:
                                                # Check if entry name contains placeholder_id or matches image pattern
                                                if placeholder_id.lower() in entry_name.lower() or \
                                                   any(entry_name.lower().endswith(ext) for ext in ['.png', '.jpg', '.jpeg', '.gif', '.webp']):
                                                    try:
                                                        image_bytes = zip_file.read(entry_name)
                                                        mime = mimetypes.guess_type(entry_name)[0] or "image/png"
                                                        image_data_uri = f"data:{mime};base64,{base64.b64encode(image_bytes).decode('ascii')}"
                                                        alt_text = os.path.basename(entry_name) or placeholder_id
                                                        logger.debug(
                                                            LogModule.EXTRACT,
                                                            f"[PREVIEW] Task {task_id}: Extracted image data for placeholder {placeholder_id} "
                                                            f"from layout_source_zip entry {entry_name} ({len(image_bytes)} bytes)"
                                                        )
                                                        break
                                                    except Exception as e:
                                                        logger.debug(
                                                            LogModule.EXTRACT,
                                                            f"[PREVIEW] Task {task_id}: Failed to read image from zip entry {entry_name}: {e}"
                                                        )
                                            
                                            zip_file.close()
                                        except Exception as e:
                                            logger.debug(
                                                LogModule.EXTRACT,
                                                f"[PREVIEW] Task {task_id}: Failed to extract image from layout_source_zip: {e}"
                                            )
                            
                            # Check for base64 image in markdown: ![alt](data:image/...;base64,...)
                            if not image_data_uri:
                                base64_match = re.search(base64_image_pattern, seg_text)
                                if base64_match:
                                    alt_text = base64_match.group(1) or "Image"
                                    mime_type = base64_match.group(2) or "png"
                                    base64_data = base64_match.group(3)
                                    image_data_uri = f"data:image/{mime_type};base64,{base64_data}"
                                    placeholder_id = placeholder_id or f"img-{idx}"
                                    logger.debug(
                                        LogModule.EXTRACT,
                                        f"[PREVIEW] Task {task_id}: Extracted base64 image data from markdown segment {idx}"
                                    )
                            
                            # Check for markdown image path: ![alt](path)
                            if not image_data_uri:
                                markdown_match = re.search(markdown_image_pattern, seg_text)
                                if markdown_match:
                                    alt_text = markdown_match.group(1) or "Image"
                                    image_path = markdown_match.group(2)
                                    placeholder_id = placeholder_id or f"img-{idx}"

                                    zip_entry = lookup_image_data_entry(image_data_map, image_path)
                                    if zip_entry and zip_entry.get("data"):
                                        image_data_uri = zip_entry["data"]
                                        alt_text = zip_entry.get("alt") or alt_text
                                        logger.debug(
                                            LogModule.EXTRACT,
                                            f"[PREVIEW] Task {task_id}: Resolved markdown image from "
                                            f"image_data_map: {image_path}",
                                        )

                                    # Try to read image from file system (if path is absolute or relative to temp_dir)
                                    temp_dir = task_state.get("temp_dir")
                                    if temp_dir and os.path.isdir(temp_dir):
                                        # Try relative path from temp_dir
                                        potential_paths = [
                                            os.path.join(temp_dir, image_path),
                                            os.path.join(temp_dir, os.path.basename(image_path)),
                                        ]
                                        # Also try original file directory if available
                                        if original_filename:
                                            original_dir = os.path.dirname(original_filename)
                                            if original_dir:
                                                potential_paths.append(os.path.join(original_dir, image_path))
                                                potential_paths.append(os.path.join(original_dir, os.path.basename(image_path)))
                                        
                                        for potential_path in potential_paths:
                                            if os.path.isfile(potential_path):
                                                try:
                                                    with open(potential_path, 'rb') as f:
                                                        image_bytes = f.read()
                                                    mime = mimetypes.guess_type(potential_path)[0] or "image/png"
                                                    image_data_uri = f"data:{mime};base64,{base64.b64encode(image_bytes).decode('ascii')}"
                                                    logger.debug(
                                                        LogModule.EXTRACT,
                                                        f"[PREVIEW] Task {task_id}: Extracted image data from file {potential_path} "
                                                        f"({len(image_bytes)} bytes)"
                                                    )
                                                    break
                                                except Exception as e:
                                                    logger.debug(
                                                        LogModule.EXTRACT,
                                                        f"[PREVIEW] Task {task_id}: Failed to read image from {potential_path}: {e}"
                                                    )
                                    
                                    # If still not found, try absolute path
                                    if not image_data_uri and os.path.isabs(image_path) and os.path.isfile(image_path):
                                        try:
                                            with open(image_path, 'rb') as f:
                                                image_bytes = f.read()
                                            mime = mimetypes.guess_type(image_path)[0] or "image/png"
                                            image_data_uri = f"data:{mime};base64,{base64.b64encode(image_bytes).decode('ascii')}"
                                            logger.debug(
                                                LogModule.EXTRACT,
                                                f"[PREVIEW] Task {task_id}: Extracted image data from absolute path {image_path} "
                                                f"({len(image_bytes)} bytes)"
                                            )
                                        except Exception as e:
                                            logger.debug(
                                                LogModule.EXTRACT,
                                                f"[PREVIEW] Task {task_id}: Failed to read image from absolute path {image_path}: {e}"
                                            )
                            
                            # Save image data to image_data_map if found
                            if placeholder_id and image_data_uri:
                                image_data_map[placeholder_id] = {
                                    "data": image_data_uri,
                                    "alt": alt_text or "Image",
                                }
                                logger.debug(
                                    LogModule.EXTRACT,
                                    f"[PREVIEW] Task {task_id}: Saved image data for placeholder {placeholder_id} "
                                    f"(alt: {alt_text})"
                                )
                            elif placeholder_id:
                                # Placeholder found but no image data - still add entry with empty data
                                # Frontend can handle this by showing placeholder
                                image_data_map[placeholder_id] = {
                                    "data": "",
                                    "alt": alt_text or "Image",
                                }
                                logger.debug(
                                    LogModule.EXTRACT,
                                    f"[PREVIEW] Task {task_id}: Placeholder {placeholder_id} found but no image data available"
                                )
                    
                    # Save image_data_map to task_state
                    if image_data_map:
                        task_state["image_data_map"] = image_data_map
                        logger.info(
                            LogModule.EXTRACT,
                            f"[PREVIEW] Task {task_id}: Saved {len(image_data_map)} image entries to image_data_map"
                        )
                    
                    # CRITICAL: Update segments_metadata using ExclusionManager (unified exclusion management)
                    # When inheriting from convert task, do NOT overwrite - user's choices from Extract are already in segments_metadata
                    if not use_inherited_exclusions:
                        if excluded_segments_with_reasons:
                            ExclusionManager.update_excluded_segments(
                                task_state,
                                excluded_segments_with_reasons,
                                metadata=None
                            )
                            logger.info(
                                LogModule.EXTRACT,
                                f"[PREVIEW] Task {task_id}: Marked {len(excluded_segments_with_reasons)} segments as excluded "
                                f"during markdown extraction (using ExclusionManager): {sorted(excluded_segments_with_reasons.keys())[:10]}"
                                f"{'...' if len(excluded_segments_with_reasons) > 10 else ''}"
                            )
                        else:
                            logger.debug(LogModule.EXTRACT, f"[PREVIEW] Task {task_id}: No segments marked as excluded during markdown extraction")
                    
                    # CRITICAL: Build chunk_to_segment_map - this is required for translation
                    logger.info(
                        LogModule.EXTRACT,
                        f"[PREVIEW] Task {task_id}: Building chunk_to_segment_map: "
                        f"segments={len(result.segments)}, chunk_size={chunk_size}, "
                        f"excluded_segments={len(excluded_segment_indices)}"
                    )
                    try:
                        self.source_preview_service._build_chunk_to_segment_map(
                            task_id=task_id,
                            segments=result.segments,
                            chunk_size=chunk_size,
                            excluded_segment_indices=excluded_segment_indices,
                            task_state=task_state
                        )
                    except Exception as build_error:
                        logger.error(
                            LogModule.EXTRACT,
                            f"[PREVIEW] Task {task_id}: Failed to build chunk_to_segment_map: {build_error}",
                            exc_info=True
                        )
                        raise  # Re-raise to prevent silent failure
                    
                    # Verify chunk_to_segment_map was created
                    chunk_to_segment_map = task_state.get("chunk_to_segment_map")
                    if chunk_to_segment_map is None:
                        logger.error(
                            LogModule.EXTRACT,
                            f"[PREVIEW] Task {task_id}: CRITICAL - chunk_to_segment_map not created for markdown_based. "
                            f"This will cause translation to fail. "
                            f"source_chunks_cache exists: {'source_chunks_cache' in task_state}, "
                            f"segments_metadata exists: {'segments_metadata' in task_state}"
                        )
                        raise ValueError(
                            f"chunk_to_segment_map not created for markdown_based. "
                            f"This is required for translation. Please check _build_chunk_to_segment_map logs."
                        )
                    else:
                        logger.info(
                            LogModule.EXTRACT,
                            f"[PREVIEW] Task {task_id}: Markdown preview prepared successfully: "
                            f"chunks={len(chunk_to_segment_map)}, "
                            f"segments={len(result.segments)}, "
                            f"source_chunks_cache segments={len(task_state.get('source_chunks_cache', {}).get('segments', []))}"
                        )
                        
                        # Output segments and chunks to temporary folder for debugging
                        self.source_preview_service._output_extract_debug_files(
                            task_id=task_id,
                            task_state=task_state,
                            segments=result.segments,
                            chunk_to_segment_map=task_state.get("chunk_to_segment_map", [])
                        )
                    
                    # For convert_only mode, create translation_segments (with exclusion_reason for UI)
                    if task_state.get("convert_only", False):
                        # Get target language from payload for language-based exclusion
                        target_lang = getattr(payload, 'to_lang', None) or getattr(payload, 'target_lang', None)
                        from exclusion.core.exclusion_detector import detect_exclusion_reason
                        from exclusion.core.exclusion_reason import ExclusionReason
                        default_excluded = ExclusionReason.get_default_excluded()
                        ts_segments = []
                        for i, s in enumerate(result.segments):
                            is_image = _is_image_segment(s)
                            detected_result = detect_exclusion_reason(
                                text=s,
                                block_type=None,
                                target_lang=target_lang,
                                is_image=is_image,
                                is_table=False
                            )
                            # Only exclude when detected reason is in exclusion_defaults (system.json)
                            is_excluded = bool(detected_result and detected_result[0] in default_excluded)
                            reason_val = detected_result[0].value if detected_result else None
                            meta = detected_result[1] if detected_result and len(detected_result) > 1 else {}
                            seg = {
                                "segment_index": i,
                                "source_text": s,
                                "target_text": s,
                                "modified": False,
                                "separator_after": result.separators_after[i] if result.separators_after and i < len(result.separators_after) else "",
                                "is_image": is_image,
                                "is_excluded": is_excluded,
                            }
                            if is_excluded and reason_val:
                                seg["exclusion_reason"] = reason_val
                                if meta:
                                    seg["exclusion_metadata"] = meta
                            ts_segments.append(seg)
                        task_state["translation_segments"] = {
                            "segments": ts_segments,
                            "metadata": task_state.get("segments_metadata", {})
                        }
                    
                    self.task_manager.add_log(task_id, "success", f"Source preview prepared from converted Markdown: {min(result.total_segments, 200)}/{result.total_segments} segments")
                    logger.info(LogModule.EXTRACT, f"[PREVIEW] Task {task_id}: Preview generation completed successfully")
            except Exception as preview_error:
                logger.error(LogModule.EXTRACT, f"[PREVIEW] Task {task_id}: Failed to generate markdown-based preview: {preview_error}", exc_info=True)
                # Set empty preview as fallback
                task_state["source_preview"] = {
                    "segments": [],
                    "total_segments": 0,
                    "ready": False,
                }
        except Exception as e:
            logger.error(LogModule.EXTRACT, f"[PREVIEW] Task {task_id}: Failed to prepare markdown-based preview: {e}", exc_info=True)
    
    def _persist_layout_document(
        self,
        task_id: str,
        workflow: Any,
        task_state: Dict[str, Any],
        original_filename: str,
        is_format_conversion: bool
    ) -> None:
        """
        Persist layout document (if available) for downstream layout-based features.
        
        Args:
            task_id: Task identifier
            workflow: Workflow instance
            task_state: Task state dictionary
            original_filename: Original filename
            is_format_conversion: Whether this is a format conversion task
        """
        try:
            from layout.base import LayoutDocument as _LD
            layout_doc = getattr(workflow, "layout_document", None)
            if layout_doc is None:
                logger.debug(LogModule.EXTRACT, f"[LAYOUT] workflow.layout_document is None for task {task_id}")
                return
            
            if not isinstance(layout_doc, _LD):
                logger.warning(
                    LogModule.EXTRACT,
                    f"[LAYOUT] workflow.layout_document is not LayoutDocument instance for task {task_id}: "
                    f"{type(layout_doc)}"
                )
                return
            
            task_state["layout_document"] = layout_doc
            task_state["layout_engine"] = getattr(layout_doc, "engine", "unknown")
            total_blocks = sum(1 for _ in layout_doc.iter_blocks())
            logger.debug(
                LogModule.EXTRACT,
                f"[LAYOUT] Stored layout_document in task_state for task {task_id}: "
                f"{layout_doc.page_count} pages, {total_blocks} blocks, "
                f"engine={task_state['layout_engine']}, "
                f"is_format_conversion={is_format_conversion}"
            )

            # Write layout blocks debug JSON (page/block/bbox info) for diagnosis
            try:
                from utils.extract_segments_debug import write_layout_blocks_debug_json
                temp_dir = task_state.get("temp_dir")
                written = write_layout_blocks_debug_json(
                    temp_dir, layout_doc, task_id=task_id,
                )
                if written:
                    logger.debug(
                        LogModule.EXTRACT,
                        f"[LAYOUT] Wrote layout blocks debug: {written}",
                    )
            except Exception:
                pass

            # For PDF files, generate layout-based preview if not already generated
            is_pdf_file = original_filename.lower().endswith('.pdf')
            if is_pdf_file and not is_format_conversion:
                preview_ready = task_state.get("source_preview", {}).get("ready", False)
                if not preview_ready:
                    self.source_preview_service.prepare_layout_preview_from_layout(
                        task_id, layout_doc, task_state.get("payload", {}), task_state, reason="translation"
                    )
        except Exception as e:
            logger.error(
                LogModule.EXTRACT,
                f"[LAYOUT] Failed to persist layout_document for task {task_id}: {e}",
                exc_info=True
            )
    
    def cancel_translation(self, task_id: str) -> Dict[str, Any]:
        """
        Cancel an ongoing translation task.
        
        Args:
            task_id: Unique task identifier
            
        Returns:
            Response dictionary
            
        Raises:
            HTTPException: If task not found or cannot be cancelled
        """
        from fastapi import HTTPException
        
        task_state = self.task_manager.get_task(task_id)
        if not task_state:
            raise HTTPException(status_code=404, detail=f"Task ID '{task_id}' not found.")

        if task_state.get("status") == "queued":
            task_state.pop("queued_translation_payload", None)
            temp_dir = task_state.get("temp_dir")
            if temp_dir and os.path.isdir(temp_dir):
                shutil.rmtree(temp_dir, ignore_errors=True)
            self.task_manager.cleanup_task_resources(task_id)
            logger.info(LogModule.WORKFLOW, f"[TRANSLATION-SERVICE] Cancelled queued task {task_id} (removed from queue)")
            return {"cancelled": True, "message": f"Task '{task_id}' has been cancelled (removed from queue)."}

        if not task_state.get("is_processing"):
            raise HTTPException(status_code=400, detail=f"Task '{task_id}' is not currently processing.")

        # Cancel the background task
        task_ref = task_state.get("current_task_ref")
        if task_ref and not task_ref.done():
            task_ref.cancel()
            self.task_manager.add_log(task_id, "info", "Task cancellation requested")

        # Update task state
        task_state["is_processing"] = False
        task_state["status"] = "cancelled"
        task_state["message"] = "Task cancelled by user"

        return {"cancelled": True, "message": f"Task '{task_id}' has been cancelled."}

