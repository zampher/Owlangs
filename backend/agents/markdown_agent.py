# SPDX-FileCopyrightText: 2025 QinHan
# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

from dataclasses import dataclass

from .agent import Agent, AgentConfig
from .seg_prompt_utils import build_seg_system_prompt, build_seg_user_prompt_from_texts, parse_seg_output
from glossary.glossary import Glossary
from logger import unified_logger
from logger.logger import LogModule


@dataclass
class MDTranslateAgentConfig(AgentConfig):
    to_lang: str
    custom_prompt: str | None = None
    glossary_dict: dict[str, str] | None = None


class MDTranslateAgent(Agent):
    def __init__(self, config: MDTranslateAgentConfig):
        super().__init__(config)
        # Build shared SEG-tag system prompt with extra markdown / LaTeX notes
        self.system_prompt = build_seg_system_prompt(config.to_lang, mention_markdown=True)
        self.custom_prompt = config.custom_prompt
        if config.custom_prompt:
            self.system_prompt += "\n# Domain rules\n" + config.custom_prompt + "\nEND"
        self.glossary_dict = config.glossary_dict
        self._task_id = None  # Will be set by translator if available for dynamic glossary loading

    def _pre_send_handler(self, system_prompt, prompt):
        # CRITICAL: Check for applied glossary in task_state dynamically (handles late glossary application)
        # This ensures glossary is loaded even if it was applied after workflow config was built
        # Always check task_state for latest glossary, even if glossary_dict was already set
        if self._task_id:
            try:
                from backend.app.services.task import task_manager
                task_state = task_manager.get_task(self._task_id)
                if task_state:
                    applied_glossary = task_state.get("applied_glossary")
                    if applied_glossary and isinstance(applied_glossary, dict):
                        glossary_dict = applied_glossary.get("glossary_dict", {})
                        if glossary_dict:
                            # Update self.glossary_dict with latest from task_state
                            if self.glossary_dict is None:
                                self.glossary_dict = {}
                            # Merge: task_state glossary takes precedence (it's more recent)
                            old_size = len(self.glossary_dict)
                            self.glossary_dict.update(glossary_dict)
                            if len(self.glossary_dict) > old_size:
                                self.logger.info(LogModule.TRANS, f"[MD_TRANSLATE_AGENT] Task {self._task_id}: Loaded {len(glossary_dict)} glossary entries from task_state in _pre_send_handler (total: {len(self.glossary_dict)})")
            except Exception as e:
                self.logger.debug(LogModule.TRANS, f"[MD_TRANSLATE_AGENT] Task {self._task_id}: Failed to load glossary from task_state in _pre_send_handler: {e}")
        
        # Use the glossary_dict (either from config or dynamically loaded)
        if self.glossary_dict:
            glossary = Glossary(glossary_dict=self.glossary_dict)
            append_text, _, _ = glossary.build_append_prompt_with_stats(prompt, max_items=100)
            if append_text:
                system_prompt += append_text
                self.logger.debug(LogModule.TRANS, f"[MD_TRANSLATE_AGENT] Task {self._task_id}: Added glossary to system prompt ({len(self.glossary_dict)} entries)")
        return system_prompt, prompt

    def send_chunks(self, prompts: list[str], progress_callback=None, chunk_size: int = None):
        """
        Send markdown chunks for translation, with optional merging to reduce API calls.
        
        Args:
            prompts: List of markdown text chunks to translate
            progress_callback: Optional progress callback
            chunk_size: Optional chunk size for merging. If provided and > 0, small chunks
                       will be merged together to reduce API calls and system prompt repetition.
        """
        if chunk_size and chunk_size > 0 and len(prompts) > 1:
            # Merge small chunks together to reduce API calls
            from utils.markdown_chunk_merger import chunks2merged_chunks, split_merged_chunks
            
            merged_chunks, merged_indices_list = chunks2merged_chunks(prompts, chunk_size)
            
            if len(merged_chunks) < len(prompts):
                # Merging occurred, translate merged chunks
                translated_merged = super().send_prompts(
                    prompts=merged_chunks, 
                    pre_send_handler=self._pre_send_handler, 
                    progress_callback=progress_callback
                )
                
                # Split back to original chunk structure
                return split_merged_chunks(translated_merged, merged_indices_list, len(prompts))
        
        # No merging or merging not beneficial, translate directly
        # Note: For sync version, we don't have segment_indices parameter, so we can't add index prefix
        # This is OK because sync version is less commonly used and merging is usually beneficial
        return super().send_prompts(prompts=prompts, pre_send_handler=self._pre_send_handler, progress_callback=progress_callback)

    async def send_chunks_async(self, prompts: list[str], progress_callback=None, chunk_size: int = None, segment_indices: list[int] = None):
        """
        Send markdown chunks for translation asynchronously.

        NOTE: This method now uses SEG-tag format ([SEG n]) for each chunk
        to be consistent with the main markdown/PDF pipeline. It does NOT use JSON any more.

        Args:
            prompts: List of markdown text chunks to translate
            progress_callback: Optional progress callback
            chunk_size: Ignored (kept for backward compatibility; no extra merging here)
            segment_indices: Optional indices for each chunk (ignored for formatting; kept for API compatibility)
        """
        import re

        # Build one SEG-tagged prompt per chunk; each chunk uses local [SEG 0]
        seg_prompts: list[str] = []
        for text in prompts:
            seg_prompts.append(build_seg_user_prompt_from_texts([text or ""]))

        translated = await super().send_prompts_async(
            prompts=seg_prompts,
            pre_send_handler=self._pre_send_handler,
            progress_callback=progress_callback,
        )

        # Save LLM API input and output for debugging
        if hasattr(self, 'task_state') and self.task_state:
            self.task_state['llm_api_input'] = seg_prompts
            self.task_state['llm_api_output'] = translated
            self.task_state['llm_api_system_prompt'] = self.system_prompt

        # Parse SEG-tag responses back to plain text list, keeping prompts order
        result: list[str] = []
        for idx, raw in enumerate(translated):
            if not isinstance(raw, str):
                result.append(str(raw))
                continue
            llm_str = raw
            parsed = parse_seg_output(llm_str)
            if idx in parsed:
                result.append(parsed[idx])
            elif parsed:
                # Found segments but not our idx — take first available
                result.append(next(iter(parsed.values())))
            else:
                # Fallback: strip the header line and return the rest
                cleaned = re.sub(r'^\[SEG\s+\d+\]:?\s*\n?', '', llm_str, flags=re.MULTILINE)
                result.append(cleaned.strip() if cleaned.strip() else llm_str)

        return result

    async def send_prompts_async(
        self,
        prompts: list[str],
        system_prompt: str | None = None,
        max_concurrent: int | None = None,
        pre_send_handler=None,
        result_handler=None,
        error_result_handler=None,
        progress_callback=None,
    ):
        """Override to save API input/output to task_state for retry debugging."""
        translated = await super().send_prompts_async(
            prompts=prompts,
            system_prompt=system_prompt,
            max_concurrent=max_concurrent,
            pre_send_handler=pre_send_handler,
            result_handler=result_handler,
            error_result_handler=error_result_handler,
            progress_callback=progress_callback,
        )
        if hasattr(self, 'task_state') and self.task_state:
            self.task_state['llm_api_input'] = prompts
            self.task_state['llm_api_output'] = translated
            self.task_state['llm_api_system_prompt'] = self.system_prompt
        return translated

    def update_glossary_dict(self, update_dict: dict | None):
        if self.glossary_dict is None:
            self.glossary_dict = {}
        if update_dict is not None:
            self.glossary_dict = update_dict | self.glossary_dict
