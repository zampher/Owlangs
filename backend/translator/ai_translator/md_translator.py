# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0
import asyncio
import re
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Self

from agents import MDTranslateAgent
from agents.markdown_agent import MDTranslateAgentConfig
from context.md_mask_context import MDMaskUrisContext
from ir.markdown_document import MarkdownDocument
from translator.ai_translator.base import AiTranslatorConfig, AiTranslator
from logger.logger import LogModule
from utils.markdown_splitter import split_markdown_text, join_markdown_texts, split_markdown_text_with_placeholder_awareness
from utils.markdown_utils import (
    replace_placeholders_with_markers,
    remove_placeholders_for_translation,
    restore_placeholders_after_translation,
    PlaceholderTracker
)


@dataclass
class MDTranslatorConfig(AiTranslatorConfig):
    ...


class MDTranslator(AiTranslator):
    def __init__(self, config: MDTranslatorConfig):
        super().__init__(config=config)
        self.chunk_size = config.chunk_size
        self.translate_agent = None
        if not self.skip_translate:
            agent_config = MDTranslateAgentConfig(custom_prompt=config.custom_prompt,
                                                  to_lang=config.to_lang,
                                                  base_url=config.base_url,
                                                  api_key=config.api_key,
                                                  model_id=config.model_id,
                                                  api_type=getattr(config, 'api_type', None) or getattr(config, 'api_protocol', None) or 'openai',
                                                  temperature=config.temperature,
                                                  thinking=config.thinking,
                                                  concurrent=config.concurrent,
                                                  connect_timeout=getattr(config, 'connect_timeout', 15),
                                                  timeout=config.timeout,
                                                  logger=self.logger,
                                                  glossary_dict=config.glossary_dict,
                                                  retry=config.retry)
            self.translate_agent = MDTranslateAgent(agent_config)

    def translate(self, document: MarkdownDocument, progress_callback=None) -> Self:
        """
        Legacy synchronous markdown translation entrypoint.
        Only used in tests and non-workflow utility code; production PDF/markdown_based
        translation uses translate_async with the segment-based SEG-tag pipeline.
        """
        self.logger.info(LogModule.TRANS, "Translating markdown (sync)")
        with MDMaskUrisContext(document):
            content_str = (
                document.content.decode("utf-8")
                if isinstance(document.content, bytes)
                else document.content
            )
            chunks: list[str] = split_markdown_text(content_str, self.chunk_size)
            if self.glossary_agent:
                self.glossary_dict_gen = self.glossary_agent.send_segments(
                    chunks, self.chunk_size
                )
                if self.translate_agent:
                    self.translate_agent.update_glossary_dict(self.glossary_dict_gen)
            self.logger.info(
                LogModule.TRANS, f"Markdown divided into {len(chunks)} chunks"
            )
            if self.translate_agent:
                result: list[str] = self.translate_agent.send_chunks(
                    chunks, progress_callback, chunk_size=self.chunk_size
                )
            else:
                result = chunks
            content_out = join_markdown_texts(result)
            # Perform some robustness enhancement operations
            content_out = content_out.replace(r"\（", r"\(")
            content_out = content_out.replace(r"\）", r"\)")
            document.content = content_out.encode("utf-8")
        self.logger.info(LogModule.TRANS, "Translation completed")
        return self

    def _get_excluded_segments(self, task_id: str | None) -> set[int]:
        """
        Get excluded segment indices using ExclusionManager (single source of truth).
        This ensures that manually excluded segments from Extract phase are correctly identified.
        """
        if not task_id:
            self.logger.info(LogModule.TRANS, f"[MD_TRANSLATOR] Task {task_id}: No task_id provided, returning empty excluded_set")
            return set()
        try:
            from backend.app.services.task import task_manager
        except ImportError:
            self.logger.warning(LogModule.TRANS, f"[MD_TRANSLATOR] Task {task_id}: Failed to import task_manager")
            return set()
        task_state = task_manager.get_task(task_id)
        if not task_state:
            self.logger.error(LogModule.TRANS, f"[MD_TRANSLATOR] Task {task_id}: task_state not found in task_manager")
            return set()
        
        # CRITICAL: Use ExclusionManager.get_excluded_segments as the single source of truth
        # This ensures that manually excluded segments from Extract phase are correctly identified
        from exclusion.core import ExclusionManager
        
        # DEBUG: Log task_state structure before calling ExclusionManager
        segments_metadata = task_state.get("segments_metadata", {})
        excluded_segments_dict = segments_metadata.get("excluded_segments", {})
        excluded_indices_list = segments_metadata.get("excluded_segment_indices", [])
        self.logger.debug(LogModule.TRANS, f"[MD_TRANSLATOR] Task {task_id}: Before ExclusionManager.get_excluded_segments - "
            f"excluded_segments type: {type(excluded_segments_dict)}, count: {len(excluded_segments_dict) if isinstance(excluded_segments_dict, dict) else 0}, "
            f"excluded_segment_indices count: {len(excluded_indices_list) if isinstance(excluded_indices_list, list) else 0}")
        
        excluded_segments_with_reasons = ExclusionManager.get_excluded_segments(task_state)
        excluded_set = set(excluded_segments_with_reasons.keys())
        
        if excluded_set:
                self.logger.info(LogModule.TRANS, f"[MD_TRANSLATOR] Task {task_id}: Retrieved {len(excluded_set)} excluded_segments from ExclusionManager "
                f"(single source of truth). Excluded indices: {sorted(excluded_set)[:20]}{'...' if len(excluded_set) > 20 else ''}"
                )
        else:
            self.logger.warning(
                f"[MD_TRANSLATOR] Task {task_id}: No excluded_segments found from ExclusionManager. "
                f"segments_metadata.excluded_segments: {excluded_segments_dict}, "
                f"segments_metadata.excluded_segment_indices: {excluded_indices_list}")
        
        return excluded_set

    async def translate_async(self, document: MarkdownDocument, progress_callback=None, 
                             task_id: str = None, original_filename: str = None, 
                             workflow_type: str = None) -> Self:
        """
        Translate markdown document asynchronously with segment recording.
        Images (placeholders) are excluded from translation and restored after translation.
        
        Args:
            document: Markdown document to translate
            progress_callback: Progress callback function
            task_id: Task ID for recording translation segments (optional)
            original_filename: Original filename for format information (optional)
            workflow_type: Workflow type for format information (optional)
        """
        # Store task_id in translate_agent for dynamic glossary loading
        if task_id and self.translate_agent:
            self.translate_agent._task_id = task_id

        self.logger.info(LogModule.TRANS, "Translating markdown")

        # PDF / markdown_based（布局 PDF）统一走基于 SEG 标记的分段新管线，彻底弃用旧 chunk 分支。
        if workflow_type == "markdown_based" or (
            original_filename and str(original_filename).lower().endswith(".pdf")
        ):
            with MDMaskUrisContext(document) as mask_context:
                original_content_str = (
                    document.content.decode("utf-8")
                    if isinstance(document.content, bytes)
                    else document.content
                )
                await self._translate_pdf_segments_json(
                    document=document,
                    original_content_str=original_content_str,
                    task_id=task_id,
                    original_filename=original_filename,
                    workflow_type=workflow_type,
                    progress_callback=progress_callback,
                    mask_context=mask_context,
                )
            self.logger.info(
                LogModule.TRANS,
                "[MD_TRANSLATOR] PDF/markdown_based workflow completed with segment-based pipeline",
            )
            return self

        # 非 PDF 场景目前仅作为同步 translate 的异步封装，复用旧的简单逻辑，避免再维护一套复杂 chunk 代码。
        def _run_sync() -> None:
            self.translate(document, progress_callback=progress_callback)

        await asyncio.to_thread(_run_sync)
        self.logger.info(LogModule.TRANS, "Translation completed")
        return self

    async def _translate_pdf_segments_json(
        self,
        document: MarkdownDocument,
        original_content_str: str,
        task_id: str | None,
        original_filename: str | None,
        workflow_type: str | None,
        progress_callback=None,
        mask_context: MDMaskUrisContext | None = None,
    ) -> None:
        """
        Segment-based translation pipeline for PDF / markdown_based workflow.
        - Use source_chunks_cache.segments as the single source of truth for segment order.
        - Skip excluded segments based on ExclusionManager (no per-chunk exclusion).
        - Chunk by max size (self.chunk_size) over raw segment text, keep order, no duplication.
        - Build plain-text payloads using lightweight segment tags: [SEG i]\\n<text>\\n[/SEG i].
        - Send each tagged payload as one prompt via MDTranslateAgent.
        - Parse tagged responses back into an index -> translated_text map.
        - Record final per-segment translations with record_translation_segments at segment granularity.
        """
        if not task_id:
            # Without task_id we cannot access source_chunks_cache or record segments.
            self.logger.error(
                LogModule.TRANS,
                "[MD_TRANSLATOR] _translate_pdf_segments_json called without task_id, "
                "fallback to legacy pipeline is required but not implemented here.",
            )
            raise ValueError("_translate_pdf_segments_json requires task_id")

        # Load task_state and cached segments from Extract phase
        try:
            from backend.app.services.task import task_manager
        except ImportError as e:
            self.logger.error(LogModule.TRANS, f"[MD_TRANSLATOR] Failed to import task_manager: {e}")
            raise

        task_state = task_manager.get_task(task_id)
        if not task_state:
            self.logger.error(
                LogModule.TRANS,
                f"[MD_TRANSLATOR] Task {task_id}: task_state not found, cannot run segment-based pipeline",
            )
            raise ValueError(f"task_state not found for task_id={task_id}")

        cache_info = task_state.get("source_chunks_cache", {}) or {}
        raw_segments = cache_info.get("segments") or []
        segments: list[str] = [str(s) for s in raw_segments]

        if not segments:
            self.logger.error(
                LogModule.TRANS,
                f"[MD_TRANSLATOR] Task {task_id}: source_chunks_cache.segments is empty, "
                "cannot run segment-based pipeline",
            )
            raise ValueError(f"No segments found in source_chunks_cache for task_id={task_id}")

        total_segments = len(segments)
        self.logger.info(
            LogModule.TRANS,
            f"[MD_TRANSLATOR] Task {task_id}: Starting segment pipeline for PDF/markdown_based workflow "
            f"with {total_segments} segments",
        )

        # Get excluded segments (single source of truth)
        excluded_set = self._get_excluded_segments(task_id)
        if excluded_set:
            self.logger.info(
                LogModule.TRANS,
                f"[MD_TRANSLATOR] Task {task_id}: Excluded segments (will keep source text, skip translation): "
                f"{sorted(excluded_set)[:50]}{'...' if len(excluded_set) > 50 else ''}",
            )
        else:
            self.logger.info(
                LogModule.TRANS,
                f"[MD_TRANSLATOR] Task {task_id}: No excluded segments for segment pipeline",
            )

        # Build ordered list of indices to translate (skip excluded ones)
        indices_to_translate: list[int] = [
            i for i in range(total_segments) if i not in excluded_set
        ]

        if not indices_to_translate:
            self.logger.info(
                LogModule.TRANS,
                f"[MD_TRANSLATOR] Task {task_id}: All segments are excluded, skipping LLM calls",
            )
            # No translation needed, but still record segments as identity mapping.
            final_translated_texts = [s for s in segments]
        else:
            # Prepare glossary dictionary if glossary_agent is available
            if self.glossary_agent:
                texts_for_glossary = [segments[i] for i in indices_to_translate]
                try:
                    self.glossary_dict_gen = await self.glossary_agent.send_segments_async(
                        texts_for_glossary, self.chunk_size
                    )
                    if self.translate_agent:
                        self.translate_agent.update_glossary_dict(self.glossary_dict_gen)
                except Exception as e:
                    self.logger.warning(
                        LogModule.TRANS,
                        f"[MD_TRANSLATOR] Task {task_id}: Glossary generation failed in segment-based pipeline: {e}",
                    )

            # Chunk segments by approximate max size (self.chunk_size in characters)
            max_size = int(self.chunk_size) if getattr(self, "chunk_size", None) else 0
            if max_size <= 0:
                # Fallback to a large but finite value to keep behavior predictable
                max_size = 6000

            seg_prompts: list[str] = []
            chunk_index_groups: list[list[int]] = []

            current_indices: list[int] = []
            current_len = 0

            for seg_idx in indices_to_translate:
                text = segments[seg_idx] or ""
                text_len = len(text)
                if not text.strip():
                    # Empty text – nothing to send, but we still want it in final_translated_texts
                    continue

                # If adding this segment would exceed max_size, flush current chunk first
                if current_indices and (current_len + text_len) > max_size:
                    # Build one plain-text prompt with [SEG i] tags for all indices in this chunk
                    lines: list[str] = []
                    for i in current_indices:
                        lines.append(f"[SEG {i}]")
                        lines.append(segments[i] or "")
                        lines.append(f"[/SEG {i}]")
                    prompt_text = "\n".join(lines)
                    seg_prompts.append(prompt_text)
                    chunk_index_groups.append(list(current_indices))

                    current_indices = []
                    current_len = 0

                current_indices.append(seg_idx)
                current_len += text_len

            # Flush remaining indices
            if current_indices:
                lines: list[str] = []
                for i in current_indices:
                    lines.append(f"[SEG {i}]")
                    lines.append(segments[i] or "")
                    lines.append(f"[/SEG {i}]")
                prompt_text = "\n".join(lines)
                seg_prompts.append(prompt_text)
                chunk_index_groups.append(list(current_indices))

            self.logger.info(
                LogModule.TRANS,
                f"[MD_TRANSLATOR] Task {task_id}: Built {len(seg_prompts)} SEG-tag prompts "
                f"from {len(indices_to_translate)} translatable segments "
                f"(max_size={max_size}, groups_sample={chunk_index_groups[:3]}{'...' if len(chunk_index_groups) > 3 else ''})",
            )

            translated_chunks: list[str] = []
            if self.translate_agent and seg_prompts:
                # Call MDTranslateAgent directly with tagged prompts; we do NOT pass segment_indices,
                # because we parse tags ourselves and enforce index -> text mapping.
                translated_chunks = await self.translate_agent.send_prompts_async(
                    prompts=seg_prompts,
                    pre_send_handler=self.translate_agent._pre_send_handler,  # type: ignore[attr-defined]
                    progress_callback=progress_callback,
                )
            else:
                translated_chunks = seg_prompts

            if len(translated_chunks) != len(seg_prompts):
                self.logger.error(
                    LogModule.TRANS,
                    f"[MD_TRANSLATOR] Task {task_id}: translated_chunks count mismatch: "
                    f"{len(translated_chunks)} != {len(seg_prompts)}",
                )
                raise ValueError(
                    f"translated_chunks count mismatch: {len(translated_chunks)} != {len(seg_prompts)}"
                )

            # Parse tagged responses into index -> translated_text map
            index_to_translation: dict[int, str] = {}
            import re

            def _write_chunk_debug(
                _task_id: str | None,
                _chunk_idx: int,
                _prompt_indices: list[int],
                _prompt_input: str,
                _llm_output: str,
                _parse_ok: bool,
                _parse_error: Exception | None = None,
                _parsed_indices: list[int] | None = None,
                _parse_state: str = "",
                _parse_step_results: list[str] | None = None,
                _llm_structure_note: str | None = None,
            ) -> None:
                """Write debug file for one chunk (translation I/O + parse result). Always called.
                _parse_state: '' = first parse success; 'failed' = no success.
                """
                try:
                    tmp_dir = Path(tempfile.gettempdir()) / "owlangs_md_translator_debug"
                    tmp_dir.mkdir(parents=True, exist_ok=True)
                    safe_task_id = str(_task_id or "unknown")
                    name_suffix = f"_{_parse_state}" if _parse_state else ""
                    debug_path = tmp_dir / f"{safe_task_id}_chunk_{_chunk_idx}{name_suffix}.txt"
                    out_full = _llm_output if isinstance(_llm_output, str) else repr(_llm_output)
                    inp_full = _prompt_input if isinstance(_prompt_input, str) else repr(_prompt_input)
                    lines = [
                        f"Task ID: {safe_task_id}",
                        f"Chunk index: {_chunk_idx}",
                        f"Parse state: {_parse_state or 'direct'}",
                        f"Prompt indices: {list(_prompt_indices)}",
                        "Input format: tagged markdown text with [SEG n] ... [/SEG n] segments.",
                        "--- Translation input (prompt, full) ---",
                        inp_full,
                        "--- Translation output (raw LLM, full) ---",
                        out_full,
                    ]
                    if _llm_structure_note:
                        lines.append(f"LLM output structure note: {_llm_structure_note}")
                    lines.append("--- JSON parse (all fallback steps) ---")
                    if _parse_step_results:
                        lines.extend(_parse_step_results)
                    lines.append(f"Parse success: {_parse_ok}")
                    if _parse_ok and _parsed_indices is not None:
                        lines.append(f"Parsed segment indices: {_parsed_indices[:50]}{'...' if len(_parsed_indices) > 50 else ''}")
                    if not _parse_ok and _parse_error is not None:
                        lines.append(f"Parse error: {_parse_error}")
                    debug_path.write_text("\n".join(lines), encoding="utf-8", errors="replace")
                    self.logger.debug(
                        LogModule.TRANS,
                        f"[MD_TRANSLATOR] Task {_task_id}: Wrote debug file for chunk {_chunk_idx} to {debug_path}",
                    )
                except Exception as file_err:  # noqa: BLE001
                    self.logger.debug(
                        LogModule.TRANS,
                        f"[MD_TRANSLATOR] Task {_task_id}: Failed to write debug for chunk {_chunk_idx}: {file_err}",
                    )

            # Helper: parse [SEG n] ... [/SEG n] tagged output into index -> text mapping
            seg_start_re = re.compile(r"^\[SEG\s+(\d+)\]\s*$")
            seg_end_re = re.compile(r"^\[/SEG\s+(\d+)\]\s*$")

            for prompt_idx, (prompt_indices, llm_output) in enumerate(
                zip(chunk_index_groups, translated_chunks)
            ):
                prompt_input = seg_prompts[prompt_idx] if prompt_idx < len(seg_prompts) else "<unavailable>"
                llm_str = llm_output if isinstance(llm_output, str) else str(llm_output)

                parse_ok = False
                parsed_indices: list[int] = []
                llm_structure_note: str | None = None
                parse_state = "failed"
                first_error: Exception | None = None
                step_results: list[str] = []

                try:
                    current_idx: int | None = None
                    buffer_lines: list[str] = []
                    for line in llm_str.splitlines():
                        m_start = seg_start_re.match(line)
                        if m_start:
                            # Flush previous block if any (defensive)
                            if current_idx is not None:
                                text_block = "\n".join(buffer_lines)
                                index_to_translation[current_idx] = text_block
                                parsed_indices.append(current_idx)
                                buffer_lines = []
                            current_idx = int(m_start.group(1))
                            continue
                        m_end = seg_end_re.match(line)
                        if m_end and current_idx is not None:
                            end_idx = int(m_end.group(1))
                            if end_idx == current_idx:
                                text_block = "\n".join(buffer_lines)
                                index_to_translation[current_idx] = text_block
                                parsed_indices.append(current_idx)
                                current_idx = None
                                buffer_lines = []
                            else:
                                # Mismatched end tag, record and reset
                                step_results.append(
                                    f"Mismatched end tag [/SEG {end_idx}] while current_idx={current_idx}"
                                )
                                current_idx = None
                                buffer_lines = []
                            continue
                        if current_idx is not None:
                            buffer_lines.append(line)

                    # Flush trailing block if any
                    if current_idx is not None:
                        text_block = "\n".join(buffer_lines)
                        index_to_translation[current_idx] = text_block
                        parsed_indices.append(current_idx)

                    if parsed_indices:
                        parse_ok = True
                        parse_state = ""
                        step_results.append(
                            f"Step 1 (seg_tags parser): success, parsed_indices={parsed_indices[:20]}{'...' if len(parsed_indices) > 20 else ''}"
                        )
                    else:
                        llm_structure_note = (
                            "seg_tags parser ran but found no [SEG n] ... [/SEG n] blocks with content."
                        )
                        step_results.append("Step 1 (seg_tags parser): no segments parsed")
                except Exception as e:  # noqa: BLE001
                    first_error = e
                    step_results.append(f"Step 1 (seg_tags parser): failed - {e!s}")

                if not parse_ok:
                    self.logger.warning(
                        LogModule.TRANS,
                        f"[MD_TRANSLATOR] Task {task_id}: Failed to parse SEG-tag LLM output for chunk {prompt_idx} "
                        f"(indices={prompt_indices}). Will treat as untranslated for these segments.",
                    )

                _write_chunk_debug(
                    _task_id=task_id,
                    _chunk_idx=prompt_idx,
                    _prompt_indices=prompt_indices,
                    _prompt_input=prompt_input,
                    _llm_output=llm_output,
                    _parse_ok=parse_ok,
                    _parse_error=first_error if not parse_ok else None,
                    _parsed_indices=parsed_indices,
                    _parse_state=parse_state,
                    _parse_step_results=step_results,
                    _llm_structure_note=llm_structure_note,
                )

            # Build final per-segment translations
            final_translated_texts: list[str] = []
            for i in range(total_segments):
                if i in excluded_set:
                    # Excluded segments keep original source text
                    final_translated_texts.append(segments[i])
                else:
                    translated = index_to_translation.get(i)
                    if translated is None or not str(translated).strip():
                        # Missing translation: use source text as fallback, mark as potential failure later
                        final_translated_texts.append(segments[i])
                    else:
                        final_translated_texts.append(str(translated))

        # Record translation segments at segment granularity
        try:
            from utils.translation_segments import record_translation_segments

            platform_key = task_state.get("platform_key")
            excluded_segments_for_recording = sorted(excluded_set) if excluded_set else None
            if excluded_segments_for_recording:
                self.logger.info(
                    LogModule.TRANS,
                    f"[MD_TRANSLATOR] Task {task_id}: Recording with {len(excluded_segments_for_recording)} "
                    f"excluded_segments: {excluded_segments_for_recording[:50]}{'...' if len(excluded_segments_for_recording) > 50 else ''}",
                )

            record_translation_segments(
                task_id=task_id,
                source_chunks=segments,
                target_chunks=final_translated_texts,
                original_filename=original_filename,
                workflow_type=workflow_type,
                source_lang=None,
                target_lang=self.config.to_lang if hasattr(self.config, "to_lang") else None,
                platform_key=platform_key,
                task_state=task_state,
                original_content=original_content_str,
                excluded_segments=excluded_segments_for_recording,
                chunk_to_segment_map=None,  # Treat as pure segments (no legacy chunk mapping)
            )

            # Store translation image map for downstream use (frontend/export)
            if mask_context is not None:
                translation_image_map: dict[str, dict[str, str]] = {}
                if hasattr(mask_context, "mask_dict"):
                    for ph_id, image_markdown in getattr(mask_context.mask_dict, "_dict", {}).items():
                        match = re.match(r'!\[(.*?)\]\((.*?)\)', image_markdown)
                        if match:
                            translation_image_map[ph_id] = {
                                "alt": match.group(1),
                                "data": match.group(2),
                            }
                if translation_image_map:
                    task_state["translation_image_data_map"] = translation_image_map
        except Exception as e:
            # Log error but don't fail translation
            self.logger.warning(
                LogModule.TRANS,
                f"[MD_TRANSLATOR] Task {task_id}: Failed to record JSON segment translations: {e}",
                exc_info=True,
            )

        # Write translation results back to document
        def _run_update_document():
            content = join_markdown_texts(final_translated_texts)
            # Perform some robustness enhancement operations
            content = content.replace(r'\（', r'\(')
            content = content.replace(r'\）', r'\)')
            document.content = content.encode('utf-8')

        await asyncio.to_thread(_run_update_document)
