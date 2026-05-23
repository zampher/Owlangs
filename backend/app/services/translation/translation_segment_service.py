# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

"""
Translation Segment Service

Handles recording translation segments for different workflow types.
This service migrates logic from _process_translation_task related to:
- Translation segment recording (after translation)
- Workflow-specific segment extraction and matching
"""

from __future__ import annotations
from typing import Any, Dict, Optional, List, TYPE_CHECKING
from pathlib import Path

from logger import unified_logger as logger
from logger.logger import LogModule
from backend.app.services.translation.chunk_size_service import chunk_size_service

if TYPE_CHECKING:
    from backend.app.services.task import TaskManager


class TranslationSegmentService:
    """Service for recording translation segments."""
    
    def __init__(self, task_manager: "TaskManager"):
        """
        Initialize translation segment service.
        
        Args:
            task_manager: Task manager instance
        """
        self.task_manager = task_manager

    # -----------------------------------------------------------------------
    # Internal helper
    # -----------------------------------------------------------------------

    @staticmethod
    def _record_segments(**kwargs) -> None:
        """
        Thin wrapper around utils.translation_segments.record_translation_segments.

        IMPORTANT:
        - Import is done lazily inside this method to avoid circular import
          during application startup when service routes are being imported.
        """
        from utils.translation_segments import record_translation_segments

        record_translation_segments(**kwargs)
    
    def ensure_translation_segments(
        self,
        task_id: str,
        workflow: Any,
        workflow_type: str,
        file_contents: bytes,
        original_filename: str,
        payload: Any,
        task_state: Dict[str, Any],
        is_format_conversion: bool = False
    ) -> bool:
        """
        Ensure translation_segments exist for frontend preview (all workflows).
        
        Args:
            task_id: Task identifier
            workflow: Workflow instance
            workflow_type: Workflow type name
            file_contents: Original file content bytes
            original_filename: Original filename
            payload: Task payload
            task_state: Task state dictionary
            is_format_conversion: Whether this is a format conversion task
            
        Returns:
            True if segments were recorded or already exist, False otherwise
        """
        # Debug logging for segment recording
        has_existing_segments = bool(task_state.get("translation_segments"))
        logger.info(
            LogModule.TRANS,
            f"[TRANSLATION-SEGMENT-SERVICE] Task {task_id}: ensure_translation_segments STARTED - "
            f"workflow_type={workflow_type}, has_existing_segments={has_existing_segments}, "
            f"is_format_conversion={is_format_conversion}"
        )
        
        if has_existing_segments or is_format_conversion:
            if has_existing_segments:
                existing_segments = task_state.get("translation_segments", {})
                if isinstance(existing_segments, dict):
                    segments_list = existing_segments.get("segments", [])
                    segments_count = len(segments_list)
                    # MOBI: if we have text-only segments (no image placeholders), inject image segments
                    if workflow_type == "mobi" and isinstance(segments_list, list):
                        cache_segments = (task_state.get("source_chunks_cache") or {}).get("segments", [])
                        image_info = task_state.get("mobi_image_segments_info") or []
                        if cache_segments and image_info and segments_count == len(cache_segments):
                            logger.info(
                                LogModule.TRANS,
                                f"[TRANSLATION-SEGMENT-SERVICE] Task {task_id}: MOBI segments exist ({segments_count}) but no image segments; injecting {len(image_info)} image segments"
                            )
                            self._inject_mobi_image_segments(task_id, task_state)
                        else:
                            logger.info(
                                LogModule.TRANS,
                                f"[TRANSLATION-SEGMENT-SERVICE] Task {task_id}: ensure_translation_segments COMPLETED - "
                                f"Translation segments already exist ({segments_count} segments), skipping recording"
                            )
                    else:
                        logger.info(
                            LogModule.TRANS,
                            f"[TRANSLATION-SEGMENT-SERVICE] Task {task_id}: ensure_translation_segments COMPLETED - "
                            f"Translation segments already exist ({segments_count} segments), skipping recording"
                        )
                else:
                    logger.info(
                        LogModule.TRANS,
                        f"[TRANSLATION-SEGMENT-SERVICE] Task {task_id}: ensure_translation_segments COMPLETED - "
                        f"Translation segments already exist (old format), skipping recording"
                    )
            return True
        
        try:
            # Get excluded segments from payload first
            excluded_segments = self._get_excluded_segments(payload, task_state, task_id)
            
            chunk_size = chunk_size_service.get_chunk_size(payload, task_id)
            
            # Route to workflow-specific recording method
            if workflow_type == "html" and hasattr(workflow, 'export_to_html'):
                return self._record_html_segments(
                    task_id, workflow, file_contents, chunk_size, payload, task_state, excluded_segments
                )
            elif workflow_type == "docx" and hasattr(workflow, 'export_to_docx'):
                # CRITICAL: DOCX workflow: record_translation_segments is called by DocxTranslator.translate_async()
                # So we don't need to call it here (similar to XLSX workflow)
                # The translator already records segments with correct excluded_segments and failure detection
                logger.info(LogModule.TRANS, f"[TRANSLATION-SEGMENT-SERVICE] Task {task_id}: ensure_translation_segments COMPLETED - DOCX workflow - segments already recorded by DocxTranslator, skipping _record_docx_segments")
                return True
            elif workflow_type == "json" and hasattr(workflow, 'export_to_json'):
                # CRITICAL: JSON workflow: record_translation_segments is called by JsonTranslator.translate_async()
                # So we don't need to call it here (similar to DOCX/XLSX workflow)
                # The translator already records segments with correct excluded_segments and failure detection
                logger.info(LogModule.TRANS, f"[TRANSLATION-SEGMENT-SERVICE] Task {task_id}: ensure_translation_segments COMPLETED - JSON workflow - segments already recorded by JsonTranslator, skipping _record_json_segments")
                return True
            elif workflow_type == "xlsx" and hasattr(workflow, 'export_to_xlsx'):
                # XLSX workflow: record_translation_segments is called by XlsxTranslator.translate()
                # So we don't need to call it here
                logger.info(LogModule.TRANS, f"[TRANSLATION-SEGMENT-SERVICE] Task {task_id}: ensure_translation_segments COMPLETED - XLSX workflow - segments already recorded by XlsxTranslator, skipping _record_xlsx_segments")
                return True
            elif workflow_type == "pptx":
                return self._record_pptx_segments(
                    task_id, workflow, file_contents, original_filename, payload, task_state, excluded_segments
                )
            elif workflow_type == "srt" and hasattr(workflow, 'export_to_srt'):
                return self._record_srt_segments(
                    task_id, workflow, file_contents, chunk_size, original_filename, payload, task_state, excluded_segments
                )
            elif workflow_type == "txt" and hasattr(workflow, 'export_to_txt'):
                return self._record_txt_segments(
                    task_id, workflow, file_contents, original_filename, payload, task_state, excluded_segments
                )
            elif workflow_type == "qt_ts" and hasattr(workflow, 'export_to_ts'):
                return self._record_qt_ts_segments(
                    task_id, workflow, file_contents, original_filename, payload, task_state, excluded_segments
                )
            elif workflow_type == "epub":
                return self._record_epub_segments(
                    task_id, workflow, file_contents, original_filename, payload, task_state, excluded_segments
                )
            elif workflow_type == "mobi":
                logger.info(LogModule.TRANS, f"[TRANSLATION] Task {task_id}: Calling _record_mobi_segments for MOBI workflow")
                result = self._record_mobi_segments(
                    task_id, workflow, file_contents, original_filename, payload, task_state, excluded_segments
                )
                logger.info(LogModule.TRANS, f"[TRANSLATION] Task {task_id}: _record_mobi_segments returned {result}")
                if result:
                    logger.info(LogModule.TRANS, f"[TRANSLATION-SEGMENT-SERVICE] Task {task_id}: ensure_translation_segments COMPLETED - MOBI segments recorded successfully")
                else:
                    logger.warning(LogModule.TRANS, f"[TRANSLATION-SEGMENT-SERVICE] Task {task_id}: ensure_translation_segments COMPLETED - MOBI segments recording failed")
                return result
            else:
                logger.debug(LogModule.TRANS, f"[TRANSLATION] Task {task_id}: No segment recording method for workflow_type={workflow_type}")
                logger.info(LogModule.TRANS, f"[TRANSLATION-SEGMENT-SERVICE] Task {task_id}: ensure_translation_segments COMPLETED - No workflow-specific recording method found, returning False")
                return False
        except Exception as e:
            logger.error(LogModule.TRANS, f"[TRANSLATION-SEGMENT-SERVICE] Task {task_id}: ensure_translation_segments FAILED - Recording translation segments failed: {e}", exc_info=True)
            return False
    
    def _get_excluded_segments(
        self,
        payload: Any,
        task_state: Dict[str, Any],
        task_id: str
    ) -> Optional[List[int]]:
        """
        Get excluded segments from payload or segments_metadata.
        
        Args:
            payload: Task payload
            task_state: Task state dictionary
            task_id: Task identifier
            
        Returns:
            List of excluded segment indices, or None
        """
        excluded_segments = None
        
        # Try to get from payload first
        if hasattr(payload, 'excluded_segments'):
            excluded_segments = getattr(payload, 'excluded_segments', None)
        elif isinstance(payload, dict):
            excluded_segments = payload.get('excluded_segments', None)
        
        # If not in payload, try to get from segments_metadata
        if not excluded_segments:
            segments_metadata = task_state.get("segments_metadata", {})
            excluded_segment_indices = segments_metadata.get("excluded_segment_indices")
            if excluded_segment_indices:
                excluded_segments = excluded_segment_indices
                logger.info(LogModule.TRANS, f"[TRANSLATION] Task {task_id}: Found {len(excluded_segments)} excluded_segment_indices in segments_metadata")
        
        # Ensure excluded_segments is a list of integers
        if excluded_segments:
            if isinstance(excluded_segments, list):
                excluded_segments = [int(x) for x in excluded_segments if x is not None]
            else:
                excluded_segments = None
            if excluded_segments:
                logger.info(LogModule.TRANS, f"[TRANSLATION] Task {task_id}: Using {len(excluded_segments)} excluded_segments")
        
        return excluded_segments
    
    def _record_html_segments(
        self,
        task_id: str,
        workflow: Any,
        file_contents: bytes,
        chunk_size: int,
        payload: Any,
        task_state: Dict[str, Any],
        excluded_segments: Optional[List[int]]
    ) -> bool:
        """Record translation segments for HTML workflow."""
        try:
            # CRITICAL: Use the actual segments used during translation (from HtmlTranslator)
            # instead of re-extracting with HtmlExtractor, which uses different logic
            html_original_texts = task_state.get("html_original_texts")
            html_translated_texts = task_state.get("html_translated_texts")
            
            if html_original_texts and html_translated_texts:
                # Use the actual segments from translation
                logger.info(
                    LogModule.TRANS,
                    f"[TRANSLATION] Task {task_id}: Using translation segments from HtmlTranslator "
                    f"({len(html_original_texts)} segments) instead of re-extracting"
                )
                
                n = min(len(html_original_texts), len(html_translated_texts))
                if n > 0:
                    # Decode original HTML for original_content parameter
                    try:
                        original_html = file_contents.decode('utf-8')
                    except UnicodeDecodeError:
                        original_html = file_contents.decode('utf-8', errors='replace')
                    
                    self._record_segments(
                        task_id=task_id,
                        source_chunks=html_original_texts[:n],
                        target_chunks=html_translated_texts[:n],
                        original_filename=None,  # Will be set from task_state if needed
                        workflow_type=payload.workflow_type,
                        task_state=task_state,
                        original_content=original_html,
                        excluded_segments=excluded_segments,
                    )
                    
                    # Output debug files for HTML translation
                    self._output_html_translation_debug_files(
                        task_id=task_id,
                        task_state=task_state,
                        original_texts=html_original_texts[:n],
                        translated_texts=html_translated_texts[:n]
                    )
                    
                    self.task_manager.add_log(task_id, "success", f"Recorded HTML translation segments: {n} (from HtmlTranslator)")
                    return True
                else:
                    logger.warning(LogModule.TRANS, f"[TRANSLATION] Task {task_id}: No segments to record (original={len(html_original_texts)}, translated={len(html_translated_texts)})")
                    return False
            else:
                # Fallback: Use HtmlExtractor (for backward compatibility or if segments not saved)
                logger.warning(
                    LogModule.TRANS,
                    f"[TRANSLATION] Task {task_id}: html_original_texts/html_translated_texts not found in task_state, "
                    f"falling back to HtmlExtractor (may cause segment mismatch)"
                )
                from extractor.html_extractor import HtmlExtractor
                
                # Decode original HTML
                try:
                    original_html = file_contents.decode('utf-8')
                except UnicodeDecodeError:
                    original_html = file_contents.decode('utf-8', errors='replace')
                
                translated_html = workflow.export_to_html()
                
                # Get deep_split setting
                deep_split_enabled = bool(task_state.get("deep_split") or getattr(payload, 'deep_split', True))
                source = "task_state" if task_state.get("deep_split") is not None else "payload"
                logger.info(
                    LogModule.TRANS,
                    f"[TRANSLATION] Task {task_id}: Using deep_split={deep_split_enabled} "
                    f"(from {source}) for html translation comparison (chunk_size={chunk_size})"
                )
                
                # Extract segments from both original and translated HTML
                src_res = HtmlExtractor(original_html, chunk_size=chunk_size, deep_split=deep_split_enabled).extract()
                tgt_res = HtmlExtractor(translated_html, chunk_size=chunk_size, deep_split=deep_split_enabled).extract()
                
                n = min(len(src_res.segments), len(tgt_res.segments))
                if n > 0:
                    self._record_segments(
                        task_id=task_id,
                        source_chunks=src_res.segments[:n],
                        target_chunks=tgt_res.segments[:n],
                        original_filename=None,  # Will be set from task_state if needed
                        workflow_type=payload.workflow_type,
                        task_state=task_state,
                        original_content=original_html,
                        excluded_segments=excluded_segments,
                    )
                    self.task_manager.add_log(task_id, "success", f"Recorded HTML translation segments: {n} (from HtmlExtractor fallback)")
                    return True
                return False
        except Exception as e:
            logger.error(LogModule.TRANS, f"[TRANSLATION] Task {task_id}: Failed to record HTML translation segments: {e}", exc_info=True)
            return False
    
    def _record_docx_segments(
        self,
        task_id: str,
        workflow: Any,
        file_contents: bytes,
        chunk_size: int,
        original_filename: str,
        payload: Any,
        task_state: Dict[str, Any]
    ) -> bool:
        """Record translation segments for DOCX workflow."""
        try:
            from extractor.docx_extractor import DocxExtractor
            
            # Extract segments from original DOCX
            src_res = DocxExtractor(file_contents, chunk_size=chunk_size).extract()
            
            # Extract segments from translated DOCX
            translated_docx_bytes = workflow.export_to_docx()
            tgt_res = DocxExtractor(translated_docx_bytes, chunk_size=chunk_size).extract()
            
            n = min(len(src_res.segments), len(tgt_res.segments))
            if n > 0:
                self._record_segments(
                    task_id=task_id,
                    source_chunks=src_res.segments[:n],
                    target_chunks=tgt_res.segments[:n],
                    original_filename=original_filename,
                    workflow_type=payload.workflow_type,
                    task_state=task_state,
                    original_content=file_contents,
                )
                self.task_manager.add_log(task_id, "success", f"Recorded DOCX translation segments: {n}")
                return True
            return False
        except Exception as e:
            logger.error(LogModule.TRANS, f"[TRANSLATION] Task {task_id}: Failed to record DOCX translation segments: {e}", exc_info=True)
            return False
    
    def _record_json_segments(
        self,
        task_id: str,
        workflow: Any,
        file_contents: bytes,
        chunk_size: int,
        payload: Any,
        task_state: Dict[str, Any],
        excluded_segments: Optional[List[int]]
    ) -> bool:
        """Record translation segments for JSON workflow."""
        try:
            from extractor.json_extractor import JsonExtractor
            
            # Decode original JSON
            try:
                original_json = file_contents.decode('utf-8')
            except UnicodeDecodeError:
                original_json = file_contents.decode('utf-8', errors='replace')
            
            translated_json = workflow.export_to_json()
            
            # Extract segments from both original and translated JSON
            json_paths = getattr(payload, 'json_paths', None) or []
            src_res = JsonExtractor(original_json, json_paths=json_paths, chunk_size=chunk_size).extract()
            tgt_res = JsonExtractor(translated_json, json_paths=json_paths, chunk_size=chunk_size).extract()
            
            n = min(len(src_res.segments), len(tgt_res.segments))
            if n > 0:
                self._record_segments(
                    task_id=task_id,
                    source_chunks=src_res.segments[:n],
                    target_chunks=tgt_res.segments[:n],
                    original_filename=None,  # Will be set from task_state if needed
                    workflow_type=payload.workflow_type,
                    task_state=task_state,
                    original_content=original_json,
                    excluded_segments=excluded_segments,
                )
                self.task_manager.add_log(task_id, "success", f"Recorded JSON translation segments: {n}")
                return True
            return False
        except Exception as e:
            logger.error(LogModule.TRANS, f"[TRANSLATION] Task {task_id}: Failed to record JSON translation segments: {e}", exc_info=True)
            return False
    
    def _record_pptx_segments(
        self,
        task_id: str,
        workflow: Any,
        file_contents: bytes,
        original_filename: str,
        payload: Any,
        task_state: Dict[str, Any],
        excluded_segments: Optional[List[int]]
    ) -> bool:
        """Record translation segments for PPTX workflow."""
        try:
            from translator.ai_translator.pptx_translator import PptxTranslator, PptxTranslatorConfig
            from ir.document import Document
            from logger import unified_logger
            
            # Get original segments from task_state (already extracted during import)
            # CRITICAL: Use source_chunks_cache instead of source_preview, because source_preview
            # only stores first 200 segments for preview, but we need ALL segments for recording
            cache_info = task_state.get("source_chunks_cache", {})
            source_segments = cache_info.get("segments", [])
            
            # Fallback to source_preview if cache not available (should not happen in normal flow)
            if not source_segments:
                source_segments = task_state.get("source_preview", {}).get("segments", [])
            
            if not source_segments:
                # Fallback: extract from original file
                extractor_config = PptxTranslatorConfig(
                    skip_translate=True,
                    translate_notes=getattr(payload, 'translate_notes', False),
                    translate_master=getattr(payload, 'translate_master', False),
                    translate_tables=getattr(payload, 'translate_tables', True),
                    translate_textboxes=getattr(payload, 'translate_textboxes', True),
                    logger=unified_logger
                )
                extractor = PptxTranslator(extractor_config)
                file_stem = Path(original_filename).stem
                file_suffix = Path(original_filename).suffix
                document = Document.from_bytes(content=file_contents, stem=file_stem, suffix=file_suffix)
                _, _, source_segments, _ = extractor._pre_translate(document, temp_dir=None)
            
            # Get translated segments from task_state (saved during translate_async)
            target_segments = task_state.get("pptx_translated_segments", [])
            
            if not target_segments:
                # Fallback: extract from translated PPTX if not available in task_state
                logger.warning(LogModule.TRANS, f"[TRANSLATION] Task {task_id}: pptx_translated_segments not found in task_state, falling back to extraction from translated PPTX")
                if hasattr(workflow, 'document_translated') and workflow.document_translated and workflow.document_translated.content:
                    translated_pptx_bytes = workflow.document_translated.content
                    extractor_config = PptxTranslatorConfig(
                        skip_translate=True,
                        translate_notes=getattr(payload, 'translate_notes', False),
                        translate_master=getattr(payload, 'translate_master', False),
                        translate_tables=getattr(payload, 'translate_tables', True),
                        translate_textboxes=getattr(payload, 'translate_textboxes', True),
                        logger=unified_logger
                    )
                    extractor = PptxTranslator(extractor_config)
                    file_stem = Path(original_filename).stem
                    file_suffix = Path(original_filename).suffix
                    document_translated = Document.from_bytes(content=translated_pptx_bytes, stem=file_stem, suffix=file_suffix)
                    _, _, target_segments, _ = extractor._pre_translate(document_translated, temp_dir=None)
                else:
                    logger.warning(LogModule.TRANS, f"[TRANSLATION] Task {task_id}: PPTX workflow completed but document_translated.content is not available, cannot record translation segments")
                    target_segments = []
            
            n = min(len(source_segments), len(target_segments))
            if n > 0:
                logger.debug(
                    LogModule.TRANS,
                    f"[TRANSLATION] Task {task_id}: Recording PPTX translation segments: "
                    f"source_segments={len(source_segments)}, target_segments={len(target_segments)}, "
                    f"recording {n} segments"
                )
                self._record_segments(
                    task_id=task_id,
                    source_chunks=source_segments[:n],
                    target_chunks=target_segments[:n],
                    original_filename=original_filename,
                    workflow_type=payload.workflow_type,
                    task_state=task_state,
                    original_content=None,  # PPTX is binary format, no text content for separator extraction
                    excluded_segments=excluded_segments,
                    chunk_to_segment_map=None,  # PPTX passes segments directly, not chunks
                )
                self.task_manager.add_log(task_id, "success", f"Recorded PPTX translation segments: {n}")
                return True
            else:
                logger.warning(LogModule.TRANS, f"[TRANSLATION] Task {task_id}: No segments to record (source={len(source_segments)}, target={len(target_segments)})")
                return False
        except Exception as e:
            logger.error(LogModule.TRANS, f"[TRANSLATION] Task {task_id}: Failed to record PPTX translation segments: {e}", exc_info=True)
            return False
    
    def _record_srt_segments(
        self,
        task_id: str,
        workflow: Any,
        file_contents: bytes,
        chunk_size: int,
        original_filename: str,
        payload: Any,
        task_state: Dict[str, Any],
        excluded_segments: Optional[List[int]]
    ) -> bool:
        """Record translation segments for SRT workflow."""
        try:
            from extractor.srt_extractor import SrtExtractor
            
            # Decode original SRT
            try:
                original_srt = file_contents.decode('utf-8')
            except UnicodeDecodeError:
                original_srt = file_contents.decode('utf-8', errors='replace')
            
            translated_srt = workflow.export_to_srt()
            
            # Extract segments from both original and translated SRT
            src_res = SrtExtractor(original_srt, chunk_size=chunk_size).extract()
            tgt_res = SrtExtractor(translated_srt, chunk_size=chunk_size).extract()
            
            n = min(len(src_res.segments), len(tgt_res.segments))
            if n > 0:
                self._record_segments(
                    task_id=task_id,
                    source_chunks=src_res.segments[:n],
                    target_chunks=tgt_res.segments[:n],
                    original_filename=original_filename,
                    workflow_type=payload.workflow_type,
                    task_state=task_state,
                    original_content=original_srt,
                    excluded_segments=excluded_segments,
                )
                self.task_manager.add_log(task_id, "success", f"Recorded SRT translation segments: {n}")
                return True
            return False
        except Exception as e:
            logger.error(LogModule.TRANS, f"[TRANSLATION] Task {task_id}: Failed to record SRT translation segments: {e}", exc_info=True)
            return False
    
    def _record_txt_segments(
        self,
        task_id: str,
        workflow: Any,
        file_contents: bytes,
        original_filename: str,
        payload: Any,
        task_state: Dict[str, Any],
        excluded_segments: Optional[List[int]]
    ) -> bool:
        """Record translation segments for TXT workflow."""
        try:
            # CRITICAL: Use source_chunks_cache segments as source (consistent with extraction phase)
            cache_info = task_state.get("source_chunks_cache", {})
            cache_segments = cache_info.get("segments", [])

            # Get translated texts from task_state (saved by TXTTranslator.translate_async)
            txt_translated_texts = task_state.get('txt_translated_texts')

            if not cache_segments:
                logger.warning(
                    LogModule.TRANS,
                    f"[TRANSLATION] Task {task_id}: TXT source_chunks_cache segments not found. "
                    f"Available keys: {list(task_state.keys())}"
                )
                return False

            if txt_translated_texts is None:
                # Try to get from workflow's translator instance (saved as _translated_texts)
                if hasattr(workflow, 'translator') and hasattr(workflow.translator, '_translated_texts'):
                    txt_translated_texts = workflow.translator._translated_texts
                    logger.info(
                        LogModule.TRANS,
                        f"[TRANSLATION] Task {task_id}: Using TXT translated texts from translator instance: "
                        f"{len(txt_translated_texts)} segments."
                    )

            if txt_translated_texts is None:
                logger.warning(
                    LogModule.TRANS,
                    f"[TRANSLATION] Task {task_id}: TXT translated texts not found. "
                    f"Falling back to raw text split."
                )
                # Fallback: decode and split translated text directly
                translated_txt = workflow.export_to_txt()
                source_segs = [str(s) for s in cache_segments]
                # For replace mode, translated text is "\n".join(translated segments)
                # Split by newline to recover individual segments
                tgt_lines = translated_txt.split('\n')
                tgt_segs = [s.strip() for s in tgt_lines if s.strip()]
                n = min(len(source_segs), len(tgt_segs))
                if n > 0:
                    self._record_segments(
                        task_id=task_id,
                        source_chunks=source_segs[:n],
                        target_chunks=tgt_segs[:n],
                        original_filename=original_filename,
                        workflow_type=payload.workflow_type,
                        task_state=task_state,
                        original_content=file_contents.decode('utf-8', errors='replace'),
                        excluded_segments=excluded_segments,
                    )
                    self.task_manager.add_log(task_id, "success", f"Recorded TXT translation segments (fallback): {n}")
                    return True
                return False

            # Use cached segments as source and saved translated texts as target
            source_segs = [str(s) for s in cache_segments]
            n = min(len(source_segs), len(txt_translated_texts))
            if n > 0:
                self._record_segments(
                    task_id=task_id,
                    source_chunks=source_segs[:n],
                    target_chunks=txt_translated_texts[:n],
                    original_filename=original_filename,
                    workflow_type=payload.workflow_type,
                    task_state=task_state,
                    original_content=file_contents.decode('utf-8', errors='replace'),
                    excluded_segments=excluded_segments,
                )
                self.task_manager.add_log(task_id, "success", f"Recorded TXT translation segments: {n}")
                return True
            return False
        except Exception as e:
            logger.error(LogModule.TRANS, f"[TRANSLATION] Task {task_id}: Failed to record TXT translation segments: {e}", exc_info=True)
            return False
    
    def _record_epub_segments(
        self,
        task_id: str,
        workflow: Any,
        file_contents: bytes,
        original_filename: str,
        payload: Any,
        task_state: Dict[str, Any],
        excluded_segments: Optional[List[int]]
    ) -> bool:
        """Record translation segments for EPUB workflow."""
        try:
            # CRITICAL: For EPUB, we MUST use source_chunks_cache segments as source
            # because they match the segments shown in source_preview API (0-based indexing)
            # epub_original_texts from EpubTranslator may have different order/count than extractor segments
            cache_info = task_state.get("source_chunks_cache", {})
            cache_segments = cache_info.get("segments", [])
            
            # Get translated_texts from task_state (saved by EpubTranslator)
            epub_translated_texts = task_state.get('epub_translated_texts')
            
            if not cache_segments:
                logger.warning(
                    LogModule.TRANS,
                    f"[TRANSLATION] Task {task_id}: EPUB source_chunks_cache segments not found. "
                    f"Available keys: {list(task_state.keys())}"
                )
                return False
            
            if epub_translated_texts is None:
                logger.warning(
                    LogModule.TRANS,
                    f"[TRANSLATION] Task {task_id}: EPUB translated_texts not found in task_state. "
                    f"Available keys: {list(task_state.keys())}"
                )
                return False
            
            # CRITICAL: Use cache_segments as source (these match source_preview API segments with 0-based indexing)
            # Map epub_translated_texts to cache_segments by index
            # Since both are ordered lists, we can map by index directly
            n = min(len(cache_segments), len(epub_translated_texts))
            if n == 0:
                logger.warning(
                    LogModule.TRANS,
                    f"[TRANSLATION] Task {task_id}: No segments to record "
                    f"(cache_segments={len(cache_segments)}, translated={len(epub_translated_texts)})"
                )
                return False
            
            if len(cache_segments) != len(epub_translated_texts):
                logger.warning(
                    LogModule.TRANS,
                    f"[TRANSLATION] Task {task_id}: EPUB segment count mismatch: "
                    f"cache_segments={len(cache_segments)}, translated={len(epub_translated_texts)}, "
                    f"recording {n} segments"
                )
            
            # Use cache_segments as source to ensure correct 0-based indexing
            # This ensures segment_index 0, 1, 2, ... matches source_preview API
            self._record_segments(
                task_id=task_id,
                source_chunks=cache_segments[:n],  # Use cache segments (0-based indexing)
                target_chunks=epub_translated_texts[:n],  # Map translated texts by index
                original_filename=original_filename,
                workflow_type=payload.workflow_type,
                task_state=task_state,
                original_content=None,  # EPUB is binary format, no text content for separator extraction
                excluded_segments=excluded_segments,
                chunk_to_segment_map=None,  # EPUB passes segments directly, not chunks
            )
            self.task_manager.add_log(task_id, "success", f"Recorded EPUB translation segments: {n} (using source_chunks_cache for correct indexing)")
            return True
        except Exception as e:
            logger.error(LogModule.TRANS, f"[TRANSLATION] Task {task_id}: Failed to record EPUB translation segments: {e}", exc_info=True)
            return False
    
    def _inject_mobi_image_segments(self, task_id: str, task_state: Dict[str, Any]) -> None:
        """
        Insert MOBI image placeholder segments into existing translation_segments.
        Used when segments already exist (e.g. all-excluded) but image segments were never added.
        """
        image_segments_info = task_state.get("mobi_image_segments_info") or []
        if not image_segments_info:
            return
        translation_segments_data = task_state.get("translation_segments")
        if not isinstance(translation_segments_data, dict):
            return
        segments_list = translation_segments_data.get("segments", [])
        if not isinstance(segments_list, list):
            return
        sorted_image_segments = sorted(image_segments_info, key=lambda x: x.get("insert_index", 0))
        images_inserted_count = 0
        for img_seg_info in sorted_image_segments:
            insert_idx = img_seg_info.get("insert_index", len(segments_list) + images_inserted_count)
            placeholder_text = img_seg_info.get("placeholder_text", "")
            placeholder_id = img_seg_info.get("placeholder_id", "")
            image_path = img_seg_info.get("image_path", "")
            image_data = img_seg_info.get("image_data", "")
            image_segment = {
                "segment_index": insert_idx + images_inserted_count,
                "source_text": placeholder_text,
                "target_text": placeholder_text,
                "modified_text": placeholder_text,
                "modified": False,
                "separator_after": "",
                "is_image": True,
                "is_excluded": True,
                "exclusion_reason": "image",
                "block_type": "image",
                "placeholder_id": placeholder_id,
                "image_path": image_path,
                "image_data": image_data,
                "status": "translated",
                "reviewed": False,
            }
            adjusted_insert_idx = insert_idx + images_inserted_count
            actual_insert_idx = min(max(0, adjusted_insert_idx), len(segments_list))
            segments_list.insert(actual_insert_idx, image_segment)
            images_inserted_count += 1
        for idx, seg in enumerate(segments_list):
            if isinstance(seg, dict):
                seg["segment_index"] = idx
        translation_segments_data["segments"] = segments_list
        task_state["translation_segments"] = translation_segments_data
        logger.info(
            LogModule.TRANS,
            f"[TRANSLATION] Task {task_id}: _inject_mobi_image_segments added {len(image_segments_info)} image segments; total segments: {len(segments_list)}"
        )

    def _record_mobi_segments(
        self,
        task_id: str,
        workflow: Any,
        file_contents: bytes,
        original_filename: str,
        payload: Any,
        task_state: Dict[str, Any],
        excluded_segments: Optional[List[int]]
    ) -> bool:
        """Record translation segments for MOBI workflow."""
        try:
            logger.debug(LogModule.TRANS, f"[TRANSLATION] Task {task_id}: Starting _record_mobi_segments")
            
            # CRITICAL: For MOBI, we MUST use source_chunks_cache segments as source
            # because they match the segments shown in source_preview API (0-based indexing)
            # mobi_original_texts from MobiTranslator may have different order/count than extractor segments
            cache_info = task_state.get("source_chunks_cache", {})
            cache_segments = cache_info.get("segments", [])
            
            logger.debug(
                LogModule.TRANS,
                f"[TRANSLATION] Task {task_id}: MOBI segment recording - "
                f"cache_segments count={len(cache_segments) if cache_segments else 0}"
            )
            
            # Get translated_texts from task_state (saved by MobiTranslator)
            mobi_translated_texts = task_state.get('mobi_translated_texts')
            
            logger.debug(
                LogModule.TRANS,
                f"[TRANSLATION] Task {task_id}: MOBI segment recording - "
                f"mobi_translated_texts count={len(mobi_translated_texts) if mobi_translated_texts else 0}"
            )
            
            if not cache_segments:
                logger.warning(
                    LogModule.TRANS,
                    f"[TRANSLATION] Task {task_id}: MOBI source_chunks_cache segments not found. "
                    f"Available keys: {list(task_state.keys())}"
                )
                return False
            
            if mobi_translated_texts is None:
                logger.warning(
                    LogModule.TRANS,
                    f"[TRANSLATION] Task {task_id}: MOBI translated_texts not found in task_state. "
                    f"Available keys: {list(task_state.keys())}"
                )
                return False
            
            # CRITICAL: Use cache_segments as source (these match source_preview API segments with 0-based indexing)
            # Map mobi_translated_texts to cache_segments by index
            # Since both are ordered lists, we can map by index directly
            n = min(len(cache_segments), len(mobi_translated_texts))
            if n == 0:
                logger.warning(
                    LogModule.TRANS,
                    f"[TRANSLATION] Task {task_id}: No segments to record "
                    f"(cache_segments={len(cache_segments)}, translated={len(mobi_translated_texts)})"
                )
                return False
            
            if len(cache_segments) != len(mobi_translated_texts):
                logger.warning(
                    LogModule.TRANS,
                    f"[TRANSLATION] Task {task_id}: MOBI segment count mismatch: "
                    f"cache_segments={len(cache_segments)}, translated={len(mobi_translated_texts)}, "
                    f"recording {n} segments"
                )
            
            # Use cache_segments as source to ensure correct 0-based indexing
            # This ensures segment_index 0, 1, 2, ... matches source_preview API
            # CRITICAL: chunk_to_segment_map=None indicates that source_chunks are actually segments
            # The function will detect this and use one-to-one mapping automatically
            self._record_segments(
                task_id=task_id,
                source_chunks=cache_segments[:n],  # Use cache segments (0-based indexing)
                target_chunks=mobi_translated_texts[:n],  # Map translated texts by index
                original_filename=original_filename,
                workflow_type=payload.workflow_type,
                task_state=task_state,
                original_content=None,  # MOBI is binary format, no text content for separator extraction
                excluded_segments=excluded_segments,
                chunk_to_segment_map=None,  # MOBI passes segments directly, not chunks (None triggers segment detection)
            )
            
            # CRITICAL: Add image segments to translation_segments after recording text segments
            # Image segments are dynamically created in get_source_preview and/or mobi_translator._pre_translate
            # and saved to task_state. If not available, we try to pull them (and image_data_map) from the
            # linked Convert/Extract task via convert_task_id, then, as a last resort, generate them here.

            # Step 1: Ensure task_state has image_data_map / mobi_image_segments_info.
            image_segments_info = task_state.get("mobi_image_segments_info", [])
            image_data_map = task_state.get("image_data_map") or task_state.get("mobi_image_data_map")

            # If current translation task has no image data but payload is linked to a Convert task,
            # try to inherit assets directly here as an extra safeguard.
            if (not image_segments_info or not image_data_map) and hasattr(payload, "convert_task_id"):
                convert_task_id = getattr(payload, "convert_task_id", None)
                if convert_task_id:
                    convert_state = self.task_manager.get_task(convert_task_id)
                    if isinstance(convert_state, dict):
                        copied_keys: List[str] = []
                        for k in (
                            "image_data_map",
                            "mobi_image_data_map",
                            "mobi_html_templates",
                            "mobi_image_segments_info",
                        ):
                            if k in convert_state and k not in task_state:
                                task_state[k] = convert_state[k]
                                copied_keys.append(k)
                        logger.info(
                            LogModule.TRANS,
                            f"[TRANSLATION] Task {task_id}: _record_mobi_segments inherited assets from convert_task_id={convert_task_id}: {copied_keys}"
                        )
                        # Refresh local references after copy
                        image_segments_info = task_state.get("mobi_image_segments_info", [])
                        image_data_map = task_state.get("image_data_map") or task_state.get("mobi_image_data_map")
            
            logger.info(
                LogModule.TRANS,
                f"[TRANSLATION] Task {task_id}: Checking for image segments info. "
                f"Found {len(image_segments_info)} image segments in mobi_image_segments_info. "
                f"cache_segments count: {len(cache_segments)}, mobi_translated_texts count: {len(mobi_translated_texts)}, "
                f"n (text segments to record): {n}. "
                f"has_image_data_map={bool(image_data_map)}. "
                f"task_state keys: {list(task_state.keys())[:20]}"
            )
            
            # If image segments info not found, generate it now (same logic as get_source_preview)
            if not image_segments_info:
                # CRITICAL: Initialize image_segments_info as empty list before generation
                image_segments_info = []
                logger.info(
                    LogModule.TRANS,
                    f"[TRANSLATION] Task {task_id}: mobi_image_segments_info not found, generating it now"
                )
                try:
                    html_templates = task_state.get("mobi_html_templates", {})
                    image_data_map_raw = task_state.get("image_data_map", {})
                    
                    if html_templates and image_data_map_raw and cache_segments:
                        from bs4 import BeautifulSoup
                        import os
                        
                        mobi_image_segments = []  # List of (insert_index, placeholder_id, image_path, context_text) tuples
                        
                        # Check each HTML template for img tags
                        for item_id, html_content in html_templates.items():
                            try:
                                soup = BeautifulSoup(html_content, 'html.parser')
                                img_tags = soup.find_all('img')
                                
                                # Extract text nodes in order (same as MobiExtractor does)
                                text_nodes_in_order = []
                                for text_node in soup.find_all(string=True):
                                    if (
                                        text_node.parent.name not in ['style', 'script', 'head', 'title', 'meta', '[document]']
                                        and not text_node.isspace()
                                    ):
                                        text = text_node.get_text(strip=True)
                                        if text:
                                            text_nodes_in_order.append({
                                                'text': text,
                                                'node': text_node,
                                            })
                                
                                for img in img_tags:
                                    src = img.get('src', '')
                                    if not src:
                                        continue
                                    
                                    # Try to match src with image_data_map keys
                                    matched_image_path = None
                                    for image_path in image_data_map_raw.keys():
                                        if src == image_path:
                                            matched_image_path = image_path
                                            break
                                        src_filename = os.path.basename(src)
                                        image_filename = os.path.basename(image_path)
                                        if src_filename == image_filename:
                                            matched_image_path = image_path
                                            break
                                        if src in image_path or image_path in src:
                                            matched_image_path = image_path
                                            break
                                        src_fixed = src.replace('一', 'i').replace('mages', 'images')
                                        if src_fixed in image_path or image_path in src_fixed:
                                            matched_image_path = image_path
                                            break
                                    
                                    if matched_image_path:
                                        placeholder_id = matched_image_path
                                        
                                        # Try to find the position of this img tag relative to text segments
                                        insert_index = None
                                        context_before = None
                                        context_after = None
                                        
                                        try:
                                            before_text_nodes = []
                                            after_text_nodes = []
                                            
                                            # Strategy 1: Check siblings within parent
                                            parent = img.parent
                                            if parent:
                                                siblings = list(parent.children)
                                                img_sibling_index = None
                                                for i, sibling in enumerate(siblings):
                                                    if sibling == img:
                                                        img_sibling_index = i
                                                        break
                                                
                                                if img_sibling_index is not None:
                                                    for i in range(img_sibling_index - 1, -1, -1):
                                                        sibling = siblings[i]
                                                        if isinstance(sibling, str) and sibling.strip():
                                                            before_text_nodes.insert(0, sibling.strip())
                                                        elif hasattr(sibling, 'get_text'):
                                                            text = sibling.get_text(strip=True)
                                                            if text:
                                                                before_text_nodes.insert(0, text)
                                                    
                                                    for i in range(img_sibling_index + 1, len(siblings)):
                                                        sibling = siblings[i]
                                                        if isinstance(sibling, str) and sibling.strip():
                                                            after_text_nodes.append(sibling.strip())
                                                        elif hasattr(sibling, 'get_text'):
                                                            text = sibling.get_text(strip=True)
                                                            if text:
                                                                after_text_nodes.append(text)
                                            
                                            # Strategy 2: If no text found in siblings, check body-level adjacent elements
                                            if not before_text_nodes and not after_text_nodes:
                                                body = soup.find('body')
                                                if body and parent:
                                                    body_children = list(body.children)
                                                    parent_index = None
                                                    for i, child in enumerate(body_children):
                                                        if child == parent:
                                                            parent_index = i
                                                            break
                                                    
                                                    if parent_index is not None:
                                                        for i in range(parent_index - 1, -1, -1):
                                                            prev_elem = body_children[i]
                                                            if hasattr(prev_elem, 'get_text'):
                                                                text = prev_elem.get_text(strip=True)
                                                                if text:
                                                                    before_text_nodes.insert(0, text)
                                                                    if len(before_text_nodes) > 0:
                                                                        before_text_nodes = [before_text_nodes[-1]]
                                                                        break
                                                        
                                                        for i in range(parent_index + 1, len(body_children)):
                                                            next_elem = body_children[i]
                                                            if hasattr(next_elem, 'get_text'):
                                                                text = next_elem.get_text(strip=True)
                                                                if text:
                                                                    after_text_nodes.append(text)
                                                                    if len(after_text_nodes) > 0:
                                                                        after_text_nodes = [after_text_nodes[0]]
                                                                        break
                                            
                                            # Try to match before_text_nodes to segments
                                            if before_text_nodes:
                                                sorted_before_texts = sorted(before_text_nodes, key=len, reverse=True)
                                                for before_text in sorted_before_texts:
                                                    if not before_text:
                                                        continue
                                                    context_before = before_text[:100]
                                                    for seg_idx, seg_text in enumerate(cache_segments):
                                                        if isinstance(seg_text, str):
                                                            if before_text == seg_text.strip():
                                                                insert_index = seg_idx + 1
                                                                break
                                                            elif before_text in seg_text:
                                                                insert_index = seg_idx + 1
                                                                break
                                                            elif len(before_text) > 20 and seg_text.strip() in before_text:
                                                                insert_index = seg_idx + 1
                                                                break
                                                        if insert_index is not None:
                                                            break
                                                    if insert_index is not None:
                                                        break
                                            
                                            # If not found, try matching after_text_nodes
                                            if insert_index is None and after_text_nodes:
                                                sorted_after_texts = sorted(after_text_nodes, key=len)
                                                for after_text in sorted_after_texts:
                                                    if not after_text:
                                                        continue
                                                    context_after = after_text[:100]
                                                    for seg_idx, seg_text in enumerate(cache_segments):
                                                        if isinstance(seg_text, str):
                                                            if after_text == seg_text.strip():
                                                                insert_index = seg_idx
                                                                break
                                                            elif after_text in seg_text:
                                                                insert_index = seg_idx
                                                                break
                                                            elif len(after_text) > 20 and seg_text.strip() in after_text:
                                                                insert_index = seg_idx
                                                                break
                                                        if insert_index is not None:
                                                            break
                                                    if insert_index is not None:
                                                        break
                                            
                                            # Fallback: append to end
                                            if insert_index is None:
                                                insert_index = len(cache_segments) + len(mobi_image_segments)
                                        except Exception as pos_error:
                                            insert_index = len(cache_segments) + len(mobi_image_segments)
                                        
                                        image_info = image_data_map_raw.get(matched_image_path, {})
                                        data_uri = image_info.get("data", "")
                                        placeholder_text = f"<ph-{placeholder_id}>"
                                        
                                        mobi_image_segments.append((
                                            insert_index,
                                            placeholder_id,
                                            matched_image_path,
                                            {'context_before': context_before, 'context_after': context_after}
                                        ))
                                        
                                        # Also save to image_segments_info for later use
                                        image_segments_info.append({
                                            "insert_index": insert_index,
                                            "placeholder_id": placeholder_id,
                                            "image_path": matched_image_path,
                                            "placeholder_text": placeholder_text,
                                            "image_data": data_uri,
                                        })
                                        
                                        logger.debug(
                                            LogModule.TRANS,
                                            f"[TRANSLATION] Task {task_id}: Generated image segment info - "
                                            f"insert_index={insert_index}, placeholder_id={placeholder_id}, image_path={matched_image_path}"
                                        )
                            except Exception as e:
                                logger.warning(
                                    LogModule.TRANS,
                                    f"[TRANSLATION] Task {task_id}: Failed to parse HTML template for item_id={item_id}: {e}",
                                    exc_info=True
                                )
                                continue
                        
                        # Save to task_state for future use
                        if image_segments_info:
                            task_state["mobi_image_segments_info"] = image_segments_info
                            logger.info(
                                LogModule.TRANS,
                                f"[TRANSLATION] Task {task_id}: Generated and saved {len(image_segments_info)} image segments info to task_state. "
                                f"Sample: {[img.get('placeholder_id', 'N/A') for img in image_segments_info[:3]]}"
                            )
                        else:
                            logger.warning(
                                LogModule.TRANS,
                                f"[TRANSLATION] Task {task_id}: Generated image_segments_info is empty after generation. "
                                f"html_templates count: {len(html_templates)}, image_data_map count: {len(image_data_map_raw)}, cache_segments count: {len(cache_segments)}"
                            )
                    else:
                        logger.warning(
                            LogModule.TRANS,
                            f"[TRANSLATION] Task {task_id}: Cannot generate image segments info - missing data. "
                            f"html_templates: {bool(html_templates)}, image_data_map: {bool(image_data_map_raw)}, cache_segments: {bool(cache_segments)}"
                        )
                except Exception as gen_error:
                    logger.warning(
                        LogModule.TRANS,
                        f"[TRANSLATION] Task {task_id}: Failed to generate image segments info: {gen_error}",
                        exc_info=True
                    )
                # CRITICAL: Re-read image_segments_info from task_state after generation attempt
                # This ensures we use the newly generated data if generation was successful
                image_segments_info = task_state.get("mobi_image_segments_info", [])
                logger.info(
                    LogModule.TRANS,
                    f"[TRANSLATION] Task {task_id}: After generation attempt, image_segments_info has {len(image_segments_info)} items"
                )
            
            if image_segments_info:
                logger.info(
                    LogModule.TRANS,
                    f"[TRANSLATION] Task {task_id}: Processing {len(image_segments_info)} image segments. "
                    f"Sample image segments: {[img.get('placeholder_id', 'N/A') for img in image_segments_info[:3]]}"
                )
                # CRITICAL: Get translation_segments directly from task_state, not through get_translation_segments
                # This ensures we're working with the actual data structure, not a reference that might be stale
                translation_segments_data = task_state.get("translation_segments")
                if translation_segments_data is None:
                    logger.warning(
                        LogModule.TRANS,
                        f"[TRANSLATION] Task {task_id}: translation_segments not found in task_state after record_translation_segments"
                    )
                elif isinstance(translation_segments_data, dict):
                    segments_list = translation_segments_data.get("segments", [])
                    logger.info(
                        LogModule.TRANS,
                        f"[TRANSLATION] Task {task_id}: Found translation_segments with {len(segments_list)} segments. "
                        f"segments_list type: {type(segments_list).__name__}, is_list: {isinstance(segments_list, list)}"
                    )
                    if isinstance(segments_list, list):
                        # Sort image segments by insert_index to ensure correct insertion order
                        sorted_image_segments = sorted(image_segments_info, key=lambda x: x.get("insert_index", 0))
                        
                        # Track how many images we've inserted to adjust subsequent indices
                        images_inserted_count = 0
                        
                        for img_seg_info in sorted_image_segments:
                            insert_idx = img_seg_info.get("insert_index", len(segments_list) + images_inserted_count)
                            placeholder_text = img_seg_info.get("placeholder_text", "")
                            placeholder_id = img_seg_info.get("placeholder_id", "")
                            image_path = img_seg_info.get("image_path", "")
                            image_data = img_seg_info.get("image_data", "")
                            
                            # Create image segment object
                            image_segment = {
                                "segment_index": insert_idx + images_inserted_count,
                                "source_text": placeholder_text,
                                "target_text": placeholder_text,  # Images are not translated
                                "modified_text": placeholder_text,
                                "modified": False,
                                "separator_after": "",
                                "is_image": True,
                                "is_excluded": True,  # Images are excluded from translation
                                "exclusion_reason": "image",
                                "block_type": "image",
                                "placeholder_id": placeholder_id,
                                "image_path": image_path,
                                "image_data": image_data,
                                "status": "translated",  # Images are considered "translated" (no translation needed)
                                "reviewed": False,
                            }
                            
                            # Insert at calculated position, or append if position is beyond current segments
                            # CRITICAL: insert_idx is the position where image should be inserted relative to text segments
                            # We need to account for images already inserted to avoid index shifting
                            adjusted_insert_idx = insert_idx + images_inserted_count
                            # Ensure insert index is within valid range (0 to len(segments_list))
                            actual_insert_idx = min(max(0, adjusted_insert_idx), len(segments_list))
                            segments_list.insert(actual_insert_idx, image_segment)
                            images_inserted_count += 1
                            
                            logger.debug(
                                LogModule.TRANS,
                                f"[TRANSLATION] Task {task_id}: Inserted image segment at index {actual_insert_idx}: "
                                f"placeholder_id={placeholder_id}, image_path={image_path}"
                            )
                        
                        # CRITICAL: Re-index all segments after insertion to ensure segment_index is correct
                        # This ensures that segment_index matches the actual position in the list
                        image_segments_count_after_reindex = 0
                        for idx, seg in enumerate(segments_list):
                            if isinstance(seg, dict):
                                is_image_seg = seg.get("is_image", False)
                                seg["segment_index"] = idx
                                if is_image_seg:
                                    image_segments_count_after_reindex += 1
                        
                        # Verify that all image segments have valid segment_index
                        image_segments_with_none_index = [
                            idx for idx, seg in enumerate(segments_list)
                            if isinstance(seg, dict) and seg.get("is_image", False) and seg.get("segment_index") is None
                        ]
                        if image_segments_with_none_index:
                            logger.error(
                                LogModule.TRANS,
                                f"[TRANSLATION] Task {task_id}: Found {len(image_segments_with_none_index)} image segments "
                                f"with None segment_index after re-indexing: {image_segments_with_none_index}"
                            )
                        
                        # CRITICAL: Update translation_segments in task_state
                        # We modify the existing translation_segments_data dict (which is a reference from get_translation_segments)
                        # This ensures that our changes are preserved even if record_translation_segments was called
                        translation_segments_data["segments"] = segments_list
                        # CRITICAL: Explicitly update task_state to ensure changes are persisted
                        # This is necessary because record_translation_segments may have created a new dict
                        task_state["translation_segments"] = translation_segments_data
                        
                        # Verify the update was successful
                        verify_segments = task_state.get("translation_segments", {}).get("segments", [])
                        verify_image_count = sum(1 for seg in verify_segments if isinstance(seg, dict) and seg.get("is_image", False))
                        
                        logger.info(
                            LogModule.TRANS,
                            f"[TRANSLATION] Task {task_id}: Added {len(image_segments_info)} image segments to translation_segments. "
                            f"Total segments: {len(segments_list)} (text: {n}, images: {len(image_segments_info)}). "
                            f"Expected total: {n + len(image_segments_info)}. "
                            f"After re-indexing: {image_segments_count_after_reindex} image segments found in list. "
                            f"Verification: task_state now has {len(verify_segments)} segments with {verify_image_count} image segments. "
                            f"Image segments sample: {[{'idx': seg.get('segment_index'), 'placeholder': seg.get('placeholder_id', 'N/A')[:30]} for seg in segments_list if isinstance(seg, dict) and seg.get('is_image', False)][:3]}"
                        )
                        
                        if verify_image_count != len(image_segments_info):
                            logger.error(
                                LogModule.TRANS,
                                f"[TRANSLATION] Task {task_id}: Image segments count mismatch! "
                                f"Expected {len(image_segments_info)} images, but task_state has {verify_image_count} images. "
                                f"This indicates the update may have been overwritten."
                            )
                    else:
                        logger.warning(
                            LogModule.TRANS,
                            f"[TRANSLATION] Task {task_id}: translation_segments.segments is not a list, cannot add image segments. "
                            f"Type: {type(segments_list).__name__}, value: {segments_list}"
                        )
                else:
                    logger.warning(
                        LogModule.TRANS,
                        f"[TRANSLATION] Task {task_id}: translation_segments not found or not a dict after record_translation_segments, cannot add image segments. "
                        f"Type: {type(translation_segments_data).__name__}, value: {translation_segments_data}"
                    )
            else:
                logger.info(
                    LogModule.TRANS,
                    f"[TRANSLATION] Task {task_id}: No image segments info found in task_state (mobi_image_segments_info). "
                    f"This is expected if images were not detected during Extract phase."
                )
            
            # CRITICAL: Log final segment count including images
            final_segment_count = len(task_state.get("translation_segments", {}).get("segments", []))
            image_count = sum(1 for seg in task_state.get("translation_segments", {}).get("segments", []) 
                            if isinstance(seg, dict) and seg.get("is_image", False))
            self.task_manager.add_log(
                task_id, "success", 
                f"Recorded MOBI translation segments: {final_segment_count} total "
                f"(text: {n}, images: {image_count})"
            )
            logger.info(
                LogModule.TRANS,
                f"[TRANSLATION] Task {task_id}: _record_mobi_segments completed. "
                f"Final translation_segments count: {final_segment_count} (text: {n}, images: {image_count})"
            )
            return True
        except Exception as e:
            logger.error(LogModule.TRANS, f"[TRANSLATION] Task {task_id}: Failed to record MOBI translation segments: {e}", exc_info=True)
            return False
    
    def _record_qt_ts_segments(
        self,
        task_id: str,
        workflow: Any,
        file_contents: bytes,
        original_filename: str,
        payload: Any,
        task_state: Dict[str, Any],
        excluded_segments: Optional[List[int]]
    ) -> bool:
        """Record translation segments for Qt .ts workflow."""
        try:
            import xml.etree.ElementTree as ET
            
            # Decode original TS
            try:
                original_ts = file_contents.decode('utf-8')
            except UnicodeDecodeError:
                original_ts = file_contents.decode('utf-8', errors='replace')
            
            # Extract source texts from original XML
            original_root = ET.fromstring(file_contents)
            source_texts = []
            for context in original_root.findall('.//context'):
                for message in context.findall('message'):
                    source = message.find('source')
                    if source is not None and source.text:
                        source_text = source.text.strip()
                        if source_text:
                            source_texts.append(source_text)
            
            # Extract translated texts from translated XML
            translated_ts = workflow.export_to_ts()
            translated_root = ET.fromstring(translated_ts.encode('utf-8'))
            translated_texts = []
            for context in translated_root.findall('.//context'):
                for message in context.findall('message'):
                    translation = message.find('translation')
                    if translation is not None and translation.text:
                        translated_text = translation.text.strip()
                        translated_texts.append(translated_text)
                    else:
                        # If no translation, use source text as fallback
                        source = message.find('source')
                        if source is not None and source.text:
                            translated_texts.append(source.text.strip())
            
            # Match source and translated texts by index
            n = min(len(source_texts), len(translated_texts))
            if n > 0:
                source_chunks = source_texts[:n]
                target_chunks = translated_texts[:n]
                
                self._record_segments(
                    task_id=task_id,
                    source_chunks=source_chunks,
                    target_chunks=target_chunks,
                    original_filename=original_filename,
                    workflow_type=payload.workflow_type,
                    task_state=task_state,
                    original_content=original_ts,
                    excluded_segments=excluded_segments,
                )
                self.task_manager.add_log(task_id, "success", f"Recorded Qt .ts translation segments: {n}")
                return True
            else:
                self.task_manager.add_log(task_id, "warning", f"No translatable segments found in Qt .ts file")
                return False
        except Exception as e:
            logger.error(LogModule.TRANS, f"[TRANSLATION] Task {task_id}: Failed to record Qt .ts translation segments: {e}", exc_info=True)
            return False
    
    def _output_html_translation_debug_files(
        self,
        task_id: str,
        task_state: Dict[str, Any],
        original_texts: List[str],
        translated_texts: List[str]
    ) -> None:
        """
        Output HTML translation segments to debug files for troubleshooting.
        
        Args:
            task_id: Task identifier
            task_state: Task state dictionary
            original_texts: List of original text segments used in translation
            translated_texts: List of translated text segments
        """
        try:
            import os
            
            # Get temp_dir from task_state
            temp_dir = task_state.get("temp_dir")
            if not temp_dir or not os.path.isdir(temp_dir):
                logger.debug(LogModule.TRANS, f"[TRANSLATION-DEBUG] Task {task_id}: temp_dir not available, skipping debug file output")
                return
            
            # Create debug directory following the unified output folder rule
            # Rule: temp_dir/debug/translation/
            debug_dir = os.path.join(temp_dir, "debug", "translation")
            os.makedirs(debug_dir, exist_ok=True)
            
            # Store debug directory path in task_state
            if "debug_files" not in task_state:
                task_state["debug_files"] = {}
            task_state["debug_files"]["translation_debug_dir"] = debug_dir
            
            # Output original and translated segments side by side
            segments_file = os.path.join(debug_dir, "html_translation_segments.txt")
            with open(segments_file, 'w', encoding='utf-8') as f:
                f.write(f"Total segments: {len(original_texts)}\n")
                f.write("=" * 80 + "\n\n")
                for idx, (orig, trans) in enumerate(zip(original_texts, translated_texts)):
                    f.write(f"Segment {idx}:\n")
                    f.write(f"Original: {orig}\n")
                    f.write(f"Translated: {trans}\n")
                    f.write(f"Match: {'✓' if orig == trans else '✗'}\n")
                    f.write("-" * 80 + "\n\n")
            
            logger.debug(LogModule.TRANS, f"[TRANSLATION-DEBUG] Task {task_id}: Saved {len(original_texts)} translation segments to {segments_file}")
            
            # Output API call information (if available)
            api_info_file = os.path.join(debug_dir, "api_call_info.txt")
            with open(api_info_file, 'w', encoding='utf-8') as f:
                f.write("HTML Translation API Call Information\n")
                f.write("=" * 80 + "\n\n")
                f.write(f"Task ID: {task_id}\n")
                f.write(f"Total segments sent to API: {len(original_texts)}\n")
                f.write(f"Total segments received from API: {len(translated_texts)}\n")
                f.write(f"Segments match: {len(original_texts) == len(translated_texts)}\n\n")
                
                # Output API request/response if available (similar to PDF workflow)
                # CRITICAL: Check both task_state and segments_agent's task_state
                llm_api_input = task_state.get("llm_api_input")
                llm_api_output = task_state.get("llm_api_output")
                llm_api_system_prompt = task_state.get("llm_api_system_prompt")
                
                # If not found in task_state, try to get from segments_agent (if available)
                if not llm_api_input and not llm_api_output:
                    # Try to get from workflow's translator if available
                    # This is a fallback in case task_state wasn't properly updated
                    logger.debug(LogModule.TRANS, f"[TRANSLATION-DEBUG] Task {task_id}: API info not found in task_state, checking workflow translator")
                
                if llm_api_input or llm_api_output:
                    f.write("API Request/Response Details:\n")
                    f.write("-" * 80 + "\n\n")
                    
                    if llm_api_system_prompt:
                        f.write(f"System Prompt (length: {len(llm_api_system_prompt)}):\n")
                        f.write(f"{llm_api_system_prompt[:500]}...\n\n")
                    
                    if llm_api_input:
                        f.write(f"Total API Requests: {len(llm_api_input)}\n\n")
                        for idx, request in enumerate(llm_api_input):
                            f.write(f"LLM API Request {idx + 1}:\n")
                            f.write(f"{request}\n")
                            f.write("-" * 80 + "\n\n")
                    
                    if llm_api_output:
                        f.write(f"Total API Responses: {len(llm_api_output)}\n\n")
                        for idx, response in enumerate(llm_api_output):
                            f.write(f"LLM API Response {idx + 1}:\n")
                            if isinstance(response, dict):
                                import json
                                f.write(f"{json.dumps(response, ensure_ascii=False, indent=2)}\n")
                            else:
                                f.write(f"{response}\n")
                            f.write("-" * 80 + "\n\n")
                else:
                    f.write("Note: API request/response details not available in task_state.\n")
                    f.write("This may occur if:\n")
                    f.write("  1. Translation was skipped or failed before API calls\n")
                    f.write("  2. task_state was not properly passed to HtmlTranslator\n")
                    f.write("  3. SegmentsTranslateAgent did not save API info to task_state\n")
                    f.write(f"\nDebug info:\n")
                    f.write(f"  task_state keys: {list(task_state.keys())}\n")
                    f.write(f"  Has llm_api_input: {'llm_api_input' in task_state}\n")
                    f.write(f"  Has llm_api_output: {'llm_api_output' in task_state}\n")
                    f.write(f"  Has llm_api_system_prompt: {'llm_api_system_prompt' in task_state}\n")
                    # Log to console for debugging
                    logger.debug(
                        LogModule.TRANS,
                        f"[TRANSLATION-DEBUG] Task {task_id}: API info not found in task_state. "
                        f"Keys: {list(task_state.keys())}"
                    )
            
            logger.debug(LogModule.TRANS, f"[TRANSLATION-DEBUG] Task {task_id}: Saved API call info to {api_info_file}")
            
        except Exception as e:
            logger.debug(LogModule.TRANS, f"[TRANSLATION-DEBUG] Task {task_id}: Failed to output debug files: {e}")

