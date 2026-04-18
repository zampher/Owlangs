# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

import asyncio
import json
from dataclasses import dataclass
from json import JSONDecodeError
from logging import Logger

from json_repair import json_repair

from agents import AgentConfig, Agent
from agents.agent import PartialAgentResultError, AgentResultError
from glossary.glossary import Glossary
from logger.logger import LogModule
from typing import Optional
from utils.json_utils import segments2json_chunks, fix_json_string
from utils.language_utils import get_language_name_from_code


@dataclass
class SegmentsTranslateAgentConfig(AgentConfig):
    to_lang: str
    custom_prompt: str | None = None
    glossary_dict: dict[str, str] | None = None
    # When True, max one segment per chunk (segment-per-request) to avoid one bad segment breaking a chunk
    segment_per_request: bool = False
    # When True, use SEG-tag ([SEG n] ... [/SEG n]) prompts instead of JSON dicts.
    # This is primarily for DOCX/PPTX/HTML/TXT/EPUB/MOBI style workflows where we want
    # a more LLM-friendly format than JSON while still preserving segment indices.
    use_seg_tags: bool = False


class SegmentsTranslateAgent(Agent):
    def __init__(self, config: SegmentsTranslateAgentConfig):
        super().__init__(config)
        self.config = config  # Keep reference for segment_per_request and other subclass options
        # Store target language for use in result handler
        self.to_lang = config.to_lang
        # Convert language code to full language name for prompt
        self.to_lang_name = get_language_name_from_code(config.to_lang)
        # Log target language for debugging
        self.use_seg_tags = getattr(config, "use_seg_tags", False)
        self.logger.debug(
            LogModule.TRANS,
            f"[SEGMENTS_AGENT] Initializing with to_lang={config.to_lang} ({self.to_lang_name}), use_seg_tags={self.use_seg_tags}",
        )

        if self.use_seg_tags:
            # SEG-tag based prompt
            self.system_prompt = f"""
# Task
Translate plain text segments from source language to {self.to_lang_name} ({config.to_lang}).

# Segment Format (CRITICAL)
Input and output are plain text with explicit segment markers:

- Start marker: [SEG n]
- End marker:   [/SEG n]

Where n is an integer segment id (e.g., 0, 1, 2, 10). Each id uniquely identifies one segment.

Your job is:
- Translate ONLY the content between [SEG n] and [/SEG n] into {self.to_lang_name}.
- KEEP the marker lines themselves EXACTLY as they are. Do NOT translate or modify them.
- Do NOT add, remove, or reorder any [SEG n] / [/SEG n] pairs.
- For every input [SEG n] ... [/SEG n] block, output ONE corresponding [SEG n] ... [/SEG n] block with the same n.

Example (input → output structure, only inner text is translated):
- Input:
  [SEG 0]
  原文 0
  [/SEG 0]
  [SEG 3]
  原文 3
  [/SEG 3]

- Output:
  [SEG 0]
  <translated 0>
  [/SEG 0]
  [SEG 3]
  <translated 3>
  [/SEG 3]

Rules:
- **MANDATORY**: Preserve EVERY segment id n exactly as in the input. If input has [SEG 0], [SEG 3], your output MUST use the same ids and order.
- **MANDATORY**: Do NOT merge multiple segments into one. Never generate a single big block that combines several [SEG n] segments.
- **MANDATORY**: Do NOT create new segment ids and do NOT drop any segment.
- **CRITICAL**: The number of [SEG n] / [/SEG n] pairs and their ids MUST match the input exactly.

# Translation Requirements
- Natural, fluent translation. Preserve meaning and technical accuracy.
- Preserve ALL formatting characters, line breaks, indentation, punctuation and inline markup inside segments.
- Preserve proper nouns, codes, brand names, citations [1] Author. "Title". Journal, Year.
- No explanations or meta-commentary.

# Output
Return ONLY the translated text with the SAME [SEG n] / [/SEG n] markers and segment ids as the input.
"""
        else:
            # Legacy JSON-based prompt
            self.system_prompt = f"""
# Task
Translate JSON text segments from source language to {self.to_lang_name} ({config.to_lang}).

# Critical Rules
1. **MUST TRANSLATE**: If text is NOT in {self.to_lang_name}, translate it. Do NOT return original text unchanged.
2. **Format Preservation**: Preserve all whitespace, line breaks, indentation, punctuation exactly as input.
3. **JSON Structure**: Output must be valid JSON with ALL input keys present. No missing/extra keys.

# Output Format
Valid JSON object (not code block): {{"<id>": "<translated_text>", ...}}
- **CRITICAL**: Return COMPLETE JSON with ALL input keys. Do NOT truncate or omit any keys.
- All input keys must exist in output (same count, same keys)
- Preserve formatting within each segment
- Translate text content only, keep structure unchanged
- **JSON Escaping**: Escape special characters in JSON strings:
  * Double quotes in text: use \\" (e.g., "He said \\"Hello\\"" → {{"0": "He said \\"Hello\\""}})
  * Backslashes: use \\\\ (e.g., "C:\\\\path" → {{"0": "C:\\\\path"}})
  * Line breaks: use \\n, tabs: use \\t
  * Ensure output is valid JSON that can be parsed
- **Complete Output**: If input has N keys, output must have exactly N keys. Return the entire JSON object, not just the first key-value pair.

# Example (target: English)
Input: {{"0": "苹果", "1": "Error", "2": "Tom said: \\"Hello\\""}}
Output: {{"0": "Apple", "1": "Error", "2": "Tom said: \\"Hello\\""}}
Note: Translate Chinese→English, keep English as-is, preserve formatting. Escape double quotes in text as \\" for valid JSON.
"""
        self.custom_prompt = config.custom_prompt
        if config.custom_prompt:
            self.system_prompt += "\n# **Important rules or background** \n" + self.custom_prompt + '\nEND\n'
        self.glossary_dict = config.glossary_dict
        self._task_id = None  # Will be set by translator if available for dynamic glossary loading

    def _pre_send_handler(self, system_prompt, prompt):
        # CRITICAL: Check for applied glossary in task_state dynamically (handles late glossary application)
        # This ensures glossary is loaded even if it was applied after workflow config was built
        # Always check task_state for latest glossary, even if glossary_dict was already set
        self.logger.debug(LogModule.TRANS, f"[SEGMENTS_AGENT] _pre_send_handler called: _task_id={self._task_id}, current glossary_dict size={len(self.glossary_dict) if self.glossary_dict else 0}")
        if self._task_id:
            try:
                from backend.app.services.task import task_manager
                task_state = task_manager.get_task(self._task_id)
                self.logger.debug(LogModule.TRANS, f"[SEGMENTS_AGENT] Task {self._task_id}: task_state exists: {task_state is not None}")
                if task_state:
                    applied_glossary = task_state.get("applied_glossary")
                    self.logger.debug(LogModule.TRANS, f"[SEGMENTS_AGENT] Task {self._task_id}: applied_glossary exists: {applied_glossary is not None}, type: {type(applied_glossary)}")
                    if applied_glossary and isinstance(applied_glossary, dict):
                        glossary_dict = applied_glossary.get("glossary_dict", {})
                        self.logger.debug(LogModule.TRANS, f"[SEGMENTS_AGENT] Task {self._task_id}: glossary_dict exists: {glossary_dict is not None}, size: {len(glossary_dict) if glossary_dict else 0}")
                        if glossary_dict:
                            # Update self.glossary_dict with latest from task_state
                            if self.glossary_dict is None:
                                self.glossary_dict = {}
                            # Merge: task_state glossary takes precedence (it's more recent)
                            old_size = len(self.glossary_dict)
                            self.glossary_dict.update(glossary_dict)
                            if len(self.glossary_dict) > old_size:
                                self.logger.info(
                                    LogModule.TRANS,
                                    f"[SEGMENTS_AGENT] Task {self._task_id}: Loaded {len(glossary_dict)} glossary entries from task_state in _pre_send_handler (total: {len(self.glossary_dict)})",
                                )
                            else:
                                self.logger.debug(
                                    LogModule.TRANS,
                                    f"[SEGMENTS_AGENT] Task {self._task_id}: Glossary already loaded (size unchanged: {old_size})",
                                )
                    else:
                        self.logger.debug(LogModule.TRANS, f"[SEGMENTS_AGENT] Task {self._task_id}: applied_glossary is not a dict or is None")
                else:
                    self.logger.debug(LogModule.TRANS, f"[SEGMENTS_AGENT] Task {self._task_id}: task_state not found")
            except Exception as e:
                self.logger.warning(
                    LogModule.TRANS,
                    f"[SEGMENTS_AGENT] Task {self._task_id}: Failed to load glossary from task_state in _pre_send_handler: {e}",
                    exc_info=True,
                )
        else:
            self.logger.debug(LogModule.TRANS, f"[SEGMENTS_AGENT] _pre_send_handler: No _task_id available, cannot check task_state for glossary")
        
        # Use the glossary_dict (either from config or dynamically loaded)
        glossary_added = False
        if self.glossary_dict:
            glossary = Glossary(glossary_dict=self.glossary_dict)
            append_text, _, _ = glossary.build_append_prompt_with_stats(prompt, max_items=100)
            if append_text:
                system_prompt += append_text
                glossary_added = True
                self.logger.info(
                    LogModule.TRANS,
                    f"[SEGMENTS_AGENT] Task {self._task_id}: Added glossary to system prompt ({len(self.glossary_dict)} entries), system prompt length: {len(system_prompt)}",
                )
            else:
                self.logger.debug(LogModule.TRANS, f"[SEGMENTS_AGENT] Task {self._task_id}: Glossary dict exists but build_append_prompt_with_stats returned empty append_text")
        else:
            self.logger.debug(LogModule.TRANS, f"[SEGMENTS_AGENT] Task {self._task_id}: No glossary_dict available, system prompt length: {len(system_prompt)}")
        
        # CRITICAL: Save the modified system prompt (with glossary) to task_state for debug file
        # Strategy: Only update if glossary was added, or if this is the first time (no existing value)
        # This ensures llm_api_comparison.txt contains the system prompt WITH glossary (if glossary was applied)
        if self._task_id:
            try:
                from backend.app.services.task import task_manager
                task_state = task_manager.get_task(self._task_id)
                if task_state:
                    existing_prompt = task_state.get('llm_api_system_prompt')
                    # Update if: 1) glossary was added (prefer version with glossary), or 2) no existing prompt
                    if glossary_added or existing_prompt is None:
                        task_state['llm_api_system_prompt'] = system_prompt
                        if glossary_added:
                            self.logger.debug(LogModule.TRANS, f"[SEGMENTS_AGENT] Task {self._task_id}: Saved system prompt WITH glossary to task_state (length: {len(system_prompt)})")
                        else:
                            self.logger.debug(LogModule.TRANS, f"[SEGMENTS_AGENT] Task {self._task_id}: Saved initial system prompt to task_state (length: {len(system_prompt)})")
                    else:
                        # Keep existing prompt (which may already have glossary from a previous chunk)
                        self.logger.debug(LogModule.TRANS, f"[SEGMENTS_AGENT] Task {self._task_id}: Keeping existing system prompt in task_state (length: {len(existing_prompt) if existing_prompt else 0})")
            except Exception as e:
                self.logger.debug(LogModule.TRANS, f"[SEGMENTS_AGENT] Task {self._task_id}: Failed to save system prompt to task_state: {e}")
        
        return system_prompt, prompt

    def _result_handler(self, result: str, origin_prompt: str, logger: Logger):
        """
        Handle successful API response.
        - If keys match completely, return translation result.
        - If keys don't match, construct a partially successful result and throw PartialTranslationError exception to trigger retry.
        - Other errors (such as JSON parsing failure, model laziness) throw regular ValueError to trigger retry.
        """
        if result == "":
            if origin_prompt.strip() != "":
                raise AgentResultError("Result is empty but original text is not empty")
            return {}
        try:
            # Clean and prepare result string
            # Note: strip() only removes whitespace at the start/end of the entire JSON string,
            # it does NOT affect whitespace inside JSON values (e.g., "0": "  text  " preserves spaces)
            result = result.strip()
            # Remove markdown code blocks if present
            if result.startswith("```"):
                # Extract JSON from markdown code block
                lines = result.split('\n')
                result = '\n'.join(lines[1:-1]) if len(lines) > 2 else result
                # Strip again after removing markdown wrapper (safe, only affects outer whitespace)
                result = result.strip()
            
            result = fix_json_string(result)
            original_chunk = json.loads(origin_prompt)
            expected_keys = set(original_chunk.keys())
            expected_key_count = len(expected_keys)
            
            # Try standard json.loads first, then json_repair if needed
            try:
                repaired_result = json.loads(result)
            except (json.JSONDecodeError, ValueError) as e:
                # If standard parsing fails, use json_repair
                logger.debug(LogModule.TRANS,
                    f"[SEGMENTS_AGENT] Standard JSON parsing failed, using json_repair. "
                    f"Error: {e}, Result length: {len(result)}, preview: {result[:200]}"
                )
                try:
                    repaired_result = json_repair.loads(result)
                except Exception as repair_error:
                    logger.error(LogModule.TRANS,
                        f"[SEGMENTS_AGENT] Both json.loads and json_repair.loads failed. "
                        f"Result length: {len(result)}, Result preview: {result[:500]}"
                    )
                    raise AgentResultError(f"JSON parsing failed: {repair_error}")
            
            # Validate parsed result
            if not isinstance(repaired_result, dict):
                logger.error(LogModule.TRANS,
                    f"[SEGMENTS_AGENT] Parsed result is not a dict: type={type(repaired_result)}, "
                    f"value={str(repaired_result)[:200]}"
                )
                raise AgentResultError(f"Agent returned result is not in dict JSON format, result: {result[:500]}")
            
            # Log parsed result info and validate key count
            actual_keys = set(repaired_result.keys())
            actual_key_count = len(actual_keys)
            missing_keys = expected_keys - actual_keys
            extra_keys = actual_keys - expected_keys
            
            logger.debug(LogModule.TRANS,
                f"[SEGMENTS_AGENT] Parsed JSON: {actual_key_count} keys (expected: {expected_key_count}). "
                f"Sample keys: {sorted(list(actual_keys), key=lambda k: int(k) if k.isdigit() else float('inf'))[:10]}"
            )
            
            if missing_keys:
                logger.warning(LogModule.TRANS,
                    f"[SEGMENTS_AGENT] Missing keys in parsed result: {sorted(list(missing_keys), key=lambda k: int(k) if k.isdigit() else float('inf'))[:10]} "
                    f"(total missing: {len(missing_keys)})"
                )
            if extra_keys:
                logger.debug(LogModule.TRANS,
                    f"[SEGMENTS_AGENT] Extra keys in parsed result: {sorted(list(extra_keys), key=lambda k: int(k) if k.isdigit() else float('inf'))[:10]} "
                    f"(total extra: {len(extra_keys)})"
                )
            
            # If key count doesn't match, log full result for debugging
            if actual_key_count != expected_key_count:
                logger.warning(LogModule.TRANS,
                    f"[SEGMENTS_AGENT] Key count mismatch: expected {expected_key_count}, got {actual_key_count}. "
                    f"Result length: {len(result)}, Result preview (first 500 chars): {result[:500]}"
                )

            if repaired_result == original_chunk:
                # When result is identical to original, check if it's a real failure
                # This is especially important when target language is English and source is already in English
                # Use translation validator to determine if this should be treated as failure
                from utils.translation_validator import should_treat_as_failure
                
                # Check all segments in the chunk
                all_segments_ok = True
                failed_segments = []
                sample_items = list(original_chunk.items())[:3]
                total_segments = len(original_chunk)
                
                for key, original_text in original_chunk.items():
                    translated_text = repaired_result.get(key, "")
                    is_failure, reason = should_treat_as_failure(str(original_text), str(translated_text))
                    if is_failure:
                        all_segments_ok = False
                        failed_segments.append((key, reason))
                        if len(failed_segments) <= 3:  # Log first 3 failed segments
                            logger.warning(LogModule.TRANS,
                                f"[SEGMENTS_AGENT] Segment '{key}' translation failed: {reason}. "
                                f"Original: '{str(original_text)[:50]}...'"
                            )
                
                if all_segments_ok:
                    # All segments are likely already in target language or don't need translation
                    # This is acceptable, especially when target language is English
                    logger.info(LogModule.TRANS,
                        f"[SEGMENTS_AGENT] Translation result is identical to original text, "
                        f"but content likely doesn't need translation (target_lang={self.to_lang}). "
                        f"Sample items: {dict(sample_items)}"
                    )
                    # Accept the result (return as-is)
                else:
                    # Some segments failed translation
                    failed_count = len(failed_segments)
                    failure_rate = failed_count / total_segments if total_segments > 0 else 1.0
                    
                    # CRITICAL: Only retry if failure rate is high (>= 50%)
                    # If failure rate is low, accept partial result and let user manually retry failed segments
                    # This prevents unnecessary retries when most segments are already translated correctly
                    RETRY_THRESHOLD = 0.5  # Retry if >= 50% of segments failed
                    
                    if failure_rate >= RETRY_THRESHOLD:
                        # High failure rate - retry the entire chunk
                        logger.warning(LogModule.TRANS,
                            f"[SEGMENTS_AGENT] Translation result is identical to original text, "
                            f"but {failed_count}/{total_segments} segment(s) ({failure_rate*100:.1f}%) should have been translated! "
                            f"Failure rate >= {RETRY_THRESHOLD*100:.0f}%, will retry entire chunk. "
                            f"Sample items: {dict(sample_items)}"
                        )
                        raise AgentResultError(
                            f"Translation result is identical to original text, but {failed_count}/{total_segments} "
                            f"segment(s) ({failure_rate*100:.1f}%) failed translation (target_lang={self.to_lang}), will retry."
                        )
                    else:
                        # Low failure rate - accept partial result, mark failed segments for manual retry
                        logger.info(LogModule.TRANS,
                            f"[SEGMENTS_AGENT] Translation result is identical to original text, "
                            f"but {failed_count}/{total_segments} segment(s) ({failure_rate*100:.1f}%) failed translation. "
                            f"Failure rate < {RETRY_THRESHOLD*100:.0f}%, accepting partial result. "
                            f"Failed segments will be marked for manual retry. "
                            f"Sample failed items: {dict(list(failed_segments[:3]))}"
                        )
                        # Accept the result as-is - failed segments will be detected in record_translation_segments
                        # when target_text == source_text and marked as failed, allowing user to manually retry
                        # This is consistent with the behavior when keys don't match (partial result acceptance)

            original_keys = set(original_chunk.keys())
            result_keys = set(repaired_result.keys())
            
            # Log successful translation sample (first 3 items) for debugging
            if original_keys == result_keys:
                sample_items = list(repaired_result.items())[:3]
                sample_original = {k: original_chunk.get(k, '')[:50] for k, _ in sample_items}
                sample_translated = {k: str(v)[:50] for k, v in sample_items}
                logger.debug(LogModule.TRANS,
                    f"[SEGMENTS_AGENT] Translation successful - Sample (first 3): "
                    f"Original: {sample_original}, Translated: {sample_translated}"
                )

            # If keys don't match completely
            if original_keys != result_keys:
                # Construct partial result: accept translated keys, use original text for missing keys
                # This allows partial results to be accepted without automatic retry
                # Missing segments will be marked as failed and can be retried manually by user
                final_chunk = {}
                common_keys = original_keys.intersection(result_keys)
                missing_keys = original_keys - result_keys
                extra_keys = result_keys - original_keys

                # Log partial result information
                logger.info(LogModule.TRANS,
                    f"[SEGMENTS_AGENT] Partial translation result received: "
                    f"{len(common_keys)}/{len(original_keys)} segments translated. "
                    f"Missing {len(missing_keys)} segments will use original text and can be retried manually."
                )
                if missing_keys:
                    # Log first 10 missing keys for debugging
                    missing_keys_sorted = sorted(list(missing_keys), key=lambda k: int(k) if k.isdigit() else float('inf'))[:10]
                    logger.warning(LogModule.TRANS,f"[SEGMENTS_AGENT] Missing keys (first 10): {missing_keys_sorted}")
                if extra_keys:
                    logger.debug(LogModule.TRANS,f"[SEGMENTS_AGENT] Extra keys (ignored): {sorted(list(extra_keys), key=lambda k: int(k) if k.isdigit() else float('inf'))[:10]}")

                # Accept partial result: use translated text for common keys, original text for missing keys
                # This ensures we accept what we got and let user manually retry missing segments
                for key in common_keys:
                    final_chunk[key] = str(repaired_result[key])
                for key in missing_keys:
                    # Use original text for missing keys - these will be marked as failed in record_translation_segments
                    # and can be retried manually by user via the Retry button
                    final_chunk[key] = str(original_chunk[key])

                # Log partial translation results (first 5 items) for debugging
                if final_chunk:
                    sample_items = list(final_chunk.items())[:5]
                    logger.debug(LogModule.TRANS,
                        f"[SEGMENTS_AGENT] Partial translation result (first 5 items): "
                        f"{dict(sample_items)}"
                    )
                    # Log sample original vs translated for comparison
                    sample_original = {k: original_chunk.get(k, '')[:50] for k, _ in sample_items if k in original_chunk}
                    sample_translated = {k: repaired_result.get(k, '')[:50] for k, _ in sample_items if k in repaired_result}
                    logger.debug(LogModule.TRANS,
                        f"[SEGMENTS_AGENT] Sample comparison - Original: {sample_original}, "
                        f"Translated: {sample_translated}"
                    )

                # Accept partial result instead of throwing exception
                # Missing segments will be detected in record_translation_segments when target_text == source_text
                # and marked as failed, allowing user to manually retry via Retry button
                logger.info(LogModule.TRANS,
                    f"[SEGMENTS_AGENT] Accepting partial result ({len(common_keys)}/{len(original_keys)} segments). "
                    f"Missing segments can be retried manually via Retry button."
                )
                return final_chunk

            # If keys match completely (ideal case), return normally
            for key, value in repaired_result.items():
                repaired_result[key] = str(value)

            return repaired_result

        except (RuntimeError, JSONDecodeError) as e:
            # For hard errors like JSON parsing, continue throwing regular ValueError
            raise AgentResultError(f"Result processing failed: {e.__repr__()}")

    def _error_result_handler(self, origin_prompt: str, logger: Logger):
        """
        Handle requests that still fail after all retries.
        As a fallback, return original content and convert all values to strings.
        """
        if origin_prompt == "":
            return {}
        try:
            original_chunk = json.loads(origin_prompt)
            # This logic is preserved as the final fallback solution
            for key, value in original_chunk.items():
                original_chunk[key] = f"{value}"
            return original_chunk
        except (RuntimeError, JSONDecodeError):
            logger.error(LogModule.TRANS,f"Original prompt is also not valid JSON format: {origin_prompt}")
            # If original prompt itself is also invalid, return a clear error object
            return {"error": f"{origin_prompt}"}

    def send_segments(self, segments: list[str], chunk_size: int, progress_callback=None, segment_indices: Optional[list[int]] = None) -> list[str]:
        self.logger.debug(LogModule.TRANS, f"[SEGMENTS_AGENT] send_segments: {len(segments)} segments, chunk_size={chunk_size}, segment_indices={'provided' if segment_indices else 'None'}")
        # Calculate text content token limit (excluding system prompt and overhead)
        from utils.chunk_size_converter import get_text_content_token_limit
        text_token_limit = get_text_content_token_limit(chunk_size)
        max_segments_per_chunk = 1 if getattr(self.config, 'segment_per_request', False) else None
        indexed_originals, chunks, merged_indices_list = segments2json_chunks(
            segments, text_token_limit, segment_indices=segment_indices, max_segments_per_chunk=max_segments_per_chunk
        )
        self.logger.debug(LogModule.TRANS, f"[SEGMENTS_AGENT] Built {len(chunks)} chunks from {len(segments)} segments")
        
        # Log chunk format to verify segments have indices
        if chunks:
            sample_chunk = chunks[0]
            sample_keys = list(sample_chunk.keys())[:5]  # First 5 keys
            self.logger.debug(LogModule.TRANS,
                f"[SEGMENTS_AGENT] Sample chunk format (first chunk, first 5 keys): {sample_keys}, "
                f"total keys in chunk: {len(sample_chunk.keys())}"
            )
            # Log sample chunk content (first 200 chars)
            sample_prompt = json.dumps(sample_chunk, ensure_ascii=False, indent=0)
            self.logger.debug(LogModule.TRANS,
                f"[SEGMENTS_AGENT] Sample chunk JSON (first 200 chars): {sample_prompt[:200]}..."
            )
        
        prompts = [json.dumps(chunk, ensure_ascii=False, indent=0) for chunk in chunks]
        
        # Log system prompt preview
        if self.system_prompt:
            self.logger.debug(LogModule.TRANS,
                f"[SEGMENTS_AGENT] System prompt preview (first 300 chars): {self.system_prompt[:300]}..."
            )
        else:
            self.logger.warning(LogModule.TRANS, "[SEGMENTS_AGENT] System prompt is empty!")

        translated_chunks = super().send_prompts(prompts=prompts, pre_send_handler=self._pre_send_handler,
                                                 result_handler=self._result_handler,
                                                 error_result_handler=self._error_result_handler,
                                                 progress_callback=progress_callback)
        
        # Save LLM API input and output for debugging
        if hasattr(self, 'task_state') and self.task_state:
            self.task_state['llm_api_input'] = prompts
            self.task_state['llm_api_output'] = translated_chunks
            # Save system prompt (may be modified by pre_send_handler with glossary)
            # Only update if not already set by _pre_send_handler (which saves the modified version)
            if 'llm_api_system_prompt' not in self.task_state or not self.task_state.get('llm_api_system_prompt'):
                self.task_state['llm_api_system_prompt'] = self.system_prompt
        
        # CRITICAL: Save llm_api_comparison.txt file directly in agent to ensure it's always created
        # This ensures files are saved even if called directly without chunk_translation_helper
        # IMPORTANT: Save even if task_state is None (use fallback directory)
        try:
            from logger.logger import TRACE_LEVEL
            import logging
            import os
            import tempfile
            
            # Check if debug mode is enabled
            is_debug_enabled = (
                self.logger.level <= logging.DEBUG or 
                self.logger.isEnabledFor(logging.DEBUG) or 
                self.logger.isEnabledFor(TRACE_LEVEL)
            )
            
            # Also check config file directly
            try:
                from logger.logger import get_log_level_from_config
                config_level = get_log_level_from_config()
                if config_level <= logging.DEBUG:
                    is_debug_enabled = True
            except Exception:
                pass
            
            if is_debug_enabled:
                # Get debug directory from task_state (or fallback)
                debug_dir = None
                if hasattr(self, 'task_state') and self.task_state:
                    temp_dir = self.task_state.get("temp_dir")
                    if temp_dir and os.path.isdir(temp_dir):
                        debug_dir = os.path.join(temp_dir, "debug", "translation")
                        os.makedirs(debug_dir, exist_ok=True)
                
                # Fallback: create independent debug directory if task_state is None or temp_dir is invalid
                if not debug_dir:
                    task_id = getattr(self, '_task_id', None) or getattr(self, 'task_id', None)
                    debug_dir = tempfile.mkdtemp(prefix=f"translation_debug_{task_id or 'unknown'}_")
                
                # Save llm_api_comparison.txt
                llm_api_comparison_file = os.path.join(debug_dir, "llm_api_comparison.txt")
                
                # Compute key count per chunk so debug file shows total segments (all chunks)
                key_counts = []
                for p in prompts:
                    try:
                        obj = json.loads(p) if isinstance(p, str) else p
                        key_counts.append(len(obj) if isinstance(obj, dict) else 0)
                    except Exception:
                        key_counts.append(-1)
                total_keys = sum(c for c in key_counts if c > 0)
                
                with open(llm_api_comparison_file, 'a', encoding='utf-8') as f:  # Use append mode to accumulate
                    # Add separator if file already has content
                    file_size_before = os.path.getsize(llm_api_comparison_file) if os.path.exists(llm_api_comparison_file) else 0
                    if file_size_before > 0:
                        f.write(f"\n{'='*80}\n")
                        f.write(f"CHUNK {len(prompts)} (Appended from send_segments)\n")
                        f.write(f"{'='*80}\n\n")
                    
                    # Write summary so user can verify all chunks are in the file (total requests, keys per chunk)
                    f.write(f"[SUMMARY] Total API requests (chunks): {len(prompts)}. ")
                    f.write(f"Segment keys per chunk: {key_counts}. Total segment keys: {total_keys}\n\n")
                    
                    # Write system prompt if available (only for first chunk)
                    if file_size_before == 0:
                        llm_api_system_prompt = None
                        if hasattr(self, 'task_state') and self.task_state:
                            llm_api_system_prompt = self.task_state.get('llm_api_system_prompt')
                        if not llm_api_system_prompt:
                            llm_api_system_prompt = self.system_prompt
                        if llm_api_system_prompt:
                            f.write(f"{'='*80}\n")
                            f.write("SYSTEM PROMPT:\n")
                            f.write(f"{'='*80}\n")
                            f.write(llm_api_system_prompt)
                            f.write("\n\n")
                    
                    # Write API input and output
                    max_idx = max(len(prompts), len(translated_chunks))
                    for idx in range(max_idx):
                        keys_in_req = key_counts[idx] if idx < len(key_counts) else -1
                        f.write(f"{'='*80}\n")
                        f.write(f"LLM API Request {idx}\n")
                        if keys_in_req >= 0:
                            f.write(f"[Keys in this request: {keys_in_req}]\n")
                        f.write(f"{'='*80}\n")
                        f.write("INPUT:\n")
                        f.write("-" * 80 + "\n")
                        if idx < len(prompts):
                            f.write(prompts[idx])
                        else:
                            f.write("(missing)")
                        f.write("\n\n")
                        f.write("OUTPUT:\n")
                        f.write("-" * 80 + "\n")
                        if idx < len(translated_chunks):
                            f.write(str(translated_chunks[idx]))
                        else:
                            f.write("(missing)")
                        f.write("\n\n")
                
                self.logger.info(
                    LogModule.TRANS,
                    f"[SEGMENTS_AGENT] Successfully created LLM API comparison file: {llm_api_comparison_file} "
                    f"(total chunks={len(prompts)}, total keys={total_keys})",
                )
        except Exception as e:
            self.logger.warning(
                LogModule.TRANS,
                f"[SEGMENTS_AGENT] Failed to save llm_api_comparison.txt: {e}",
                exc_info=True,
            )

        indexed_translated = indexed_originals.copy()
        total_keys_updated = 0
        for chunk_idx, chunk in enumerate(translated_chunks):
            try:
                if not isinstance(chunk, dict):
                    self.logger.error(LogModule.TRANS, f"[SEGMENTS_AGENT] Chunk {chunk_idx} is not a valid dictionary, skipped: {chunk}")
                    continue
                
                chunk_keys = list(chunk.keys())
                self.logger.debug(LogModule.TRANS,
                    f"[SEGMENTS_AGENT] Processing chunk {chunk_idx}: {len(chunk_keys)} keys - "
                    f"Sample keys: {chunk_keys[:5] if len(chunk_keys) > 5 else chunk_keys}"
                )
                
                keys_updated_in_chunk = 0
                for key, val in chunk.items():
                    if key in indexed_translated:
                        indexed_translated[key] = val
                        keys_updated_in_chunk += 1
                        total_keys_updated += 1
                    else:
                        self.logger.warning(LogModule.TRANS,
                            f"[SEGMENTS_AGENT] Unknown key '{key}' found in chunk {chunk_idx}, ignored. "
                            f"Available keys in indexed_translated: {list(indexed_translated.keys())[:10]}..."
                        )
                
                if keys_updated_in_chunk == 0:
                    self.logger.warning(LogModule.TRANS,
                        f"[SEGMENTS_AGENT] Chunk {chunk_idx} updated 0 keys! "
                        f"Chunk keys: {chunk_keys}, "
                        f"Sample indexed_translated keys: {list(indexed_translated.keys())[:10]}"
                    )
                else:
                    self.logger.debug(LogModule.TRANS,
                        f"[SEGMENTS_AGENT] Chunk {chunk_idx} updated {keys_updated_in_chunk} keys successfully"
                    )
            except (AttributeError, TypeError) as e:
                self.logger.error(LogModule.TRANS,
                    f"[SEGMENTS_AGENT] Type or attribute error occurred while processing chunk {chunk_idx}, skipped. "
                    f"Chunk: {chunk}, Error: {e.__repr__()}"
                )
            except Exception as e:
                self.logger.error(LogModule.TRANS,
                    f"[SEGMENTS_AGENT] Unknown error occurred while processing chunk {chunk_idx}: {e.__repr__()}"
                )
        
        # Log summary
        expected_keys = len(indexed_originals)
        if total_keys_updated < expected_keys:
            missing_keys = set(indexed_originals.keys()) - set(
                k for k, v in indexed_translated.items() 
                if v != indexed_originals.get(k)
            )
            if missing_keys:
                self.logger.warning(LogModule.TRANS,
                    f"[SEGMENTS_AGENT] Only {total_keys_updated}/{expected_keys} keys were updated. "
                    f"Missing keys (first 10): {list(missing_keys)[:10]}"
                )
        else:
            self.logger.debug(LogModule.TRANS,
                f"[SEGMENTS_AGENT] Successfully updated {total_keys_updated}/{expected_keys} keys from {len(translated_chunks)} chunks"
            )

        # Rebuild final list
        # CRITICAL: Sort keys numerically to ensure correct order (e.g., "0", "1", "2", ..., "10", not "0", "1", "10", "2")
        sorted_keys = sorted(indexed_translated.keys(), key=lambda k: int(k) if k.isdigit() else float('inf'))
        ls = [indexed_translated[k] for k in sorted_keys]
        
        result = []
        last_end = 0
        for start, end in merged_indices_list:
            result.extend(ls[last_end:start])
            merged_item = "".join(map(str, ls[start:end]))
            result.append(merged_item)
            last_end = end

        result.extend(ls[last_end:])
        return result

    async def send_segments_async(self, segments: list[str], chunk_size: int, progress_callback=None, segment_indices: Optional[list[int]] = None) -> list[str]:
        self.logger.debug(LogModule.TRANS, f"[SEGMENTS_AGENT] send_segments_async: {len(segments)} segments, chunk_size={chunk_size}, segment_indices={'provided' if segment_indices else 'None'}, use_seg_tags={self.use_seg_tags}")
        # Calculate text content token limit (excluding system prompt and overhead)
        from utils.chunk_size_converter import get_text_content_token_limit
        text_token_limit = get_text_content_token_limit(chunk_size)
        max_segments_per_chunk = 1 if getattr(self.config, 'segment_per_request', False) else None
        indexed_originals, chunks, merged_indices_list = await asyncio.to_thread(
            segments2json_chunks,
            segments,
            text_token_limit,
            False,
            segment_indices,
            max_segments_per_chunk,
        )
        self.logger.debug(LogModule.TRANS, f"[SEGMENTS_AGENT] Built {len(chunks)} chunks from {len(segments)} segments")

        # Branch: use SEG-tag format instead of JSON dicts (for DOCX/PPTX/HTML/TXT/EPUB/MOBI when enabled)
        if self.use_seg_tags:
            import re

            prompts: list[str] = []
            for chunk_dict in chunks:
                # chunk_dict: {"idx": "text", ...}
                lines: list[str] = []
                for key in sorted(chunk_dict.keys(), key=int):
                    text = chunk_dict[key] or ""
                    lines.append(f"[SEG {key}]")
                    lines.append(text)
                    lines.append(f"[/SEG {key}]")
                prompts.append("\n".join(lines))

            translated_raw = await super().send_prompts_async(
                prompts=prompts,
                pre_send_handler=self._pre_send_handler,
                progress_callback=progress_callback,
            )

            # Save LLM API input and output for debugging
            if hasattr(self, 'task_state') and self.task_state:
                self.task_state['llm_api_input'] = prompts
                self.task_state['llm_api_output'] = translated_raw
                # Save system prompt (may be modified by pre_send_handler with glossary)
                if 'llm_api_system_prompt' not in self.task_state or not self.task_state.get('llm_api_system_prompt'):
                    self.task_state['llm_api_system_prompt'] = self.system_prompt

            # Parse SEG-tag responses back into dict chunks {id: text}
            translated_chunks: list[dict[str, str]] = []
            seg_start_re = re.compile(r"^\[SEG\s+(\d+)\]\s*$")
            seg_end_re = re.compile(r"^\[/SEG\s+(\d+)\]\s*$")

            for raw in translated_raw:
                text = raw if isinstance(raw, str) else str(raw)
                current_id: str | None = None
                buf: list[str] = []
                chunk_result: dict[str, str] = {}
                for line in text.splitlines():
                    m_start = seg_start_re.match(line)
                    if m_start:
                        # flush previous
                        if current_id is not None:
                            chunk_result[current_id] = "\n".join(buf)
                            buf = []
                        current_id = m_start.group(1)
                        continue
                    m_end = seg_end_re.match(line)
                    if m_end and current_id is not None:
                        end_id = m_end.group(1)
                        if end_id == current_id:
                            chunk_result[current_id] = "\n".join(buf)
                        else:
                            self.logger.warning(
                                LogModule.TRANS,
                                f"[SEGMENTS_AGENT] Mismatched SEG end tag [/SEG {end_id}] while current_id={current_id}",
                            )
                        current_id = None
                        buf = []
                        continue
                    if current_id is not None:
                        buf.append(line)
                if current_id is not None:
                    chunk_result[current_id] = "\n".join(buf)
                translated_chunks.append(chunk_result)
        else:
            # Original JSON-based path
            prompts = [json.dumps(chunk, ensure_ascii=False, indent=0) for chunk in chunks]

            translated_chunks = await super().send_prompts_async(
                prompts=prompts,
                pre_send_handler=self._pre_send_handler,
                result_handler=self._result_handler,
                error_result_handler=self._error_result_handler,
                progress_callback=progress_callback,
            )
            
            # Save LLM API input and output for debugging
            if hasattr(self, 'task_state') and self.task_state:
                self.task_state['llm_api_input'] = prompts
                self.task_state['llm_api_output'] = translated_chunks
                # Save system prompt (may be modified by pre_send_handler with glossary)
                # Only update if not already set by _pre_send_handler (which saves the modified version)
                if 'llm_api_system_prompt' not in self.task_state or not self.task_state.get('llm_api_system_prompt'):
                    self.task_state['llm_api_system_prompt'] = self.system_prompt

        indexed_translated = indexed_originals.copy()
        total_keys_updated = 0
        for chunk_idx, chunk in enumerate(translated_chunks):
            try:
                if not isinstance(chunk, dict):
                    self.logger.error(LogModule.TRANS, f"[SEGMENTS_AGENT] Chunk {chunk_idx} is not a valid dictionary, skipped: {chunk}")
                    continue
                
                chunk_keys = list(chunk.keys())
                self.logger.debug(LogModule.TRANS,
                    f"[SEGMENTS_AGENT] Processing chunk {chunk_idx}: {len(chunk_keys)} keys - "
                    f"Sample keys: {chunk_keys[:5] if len(chunk_keys) > 5 else chunk_keys}"
                )
                
                # Debug: Log first few key-value pairs from chunk to verify translation
                if chunk_idx < 2 and len(chunk_keys) > 0:
                    sample_items = [(k, str(chunk[k])[:50]) for k in chunk_keys[:3]]
                    self.logger.debug(LogModule.TRANS,
                        f"[SEGMENTS_AGENT] Chunk {chunk_idx} sample values (first 50 chars): {sample_items}"
                    )
                
                keys_updated_in_chunk = 0
                for key, val in chunk.items():
                    if key in indexed_translated:
                        # str(val) is no longer needed here, as _result_handler has already handled it
                        old_val = indexed_translated[key]
                        indexed_translated[key] = val
                        keys_updated_in_chunk += 1
                        total_keys_updated += 1
                        # Debug: Log first few updates to verify translation
                        if keys_updated_in_chunk <= 3 and chunk_idx < 2:
                            self.logger.debug(LogModule.TRANS,
                                f"[SEGMENTS_AGENT] Updated key '{key}': "
                                f"old (first 30 chars)='{str(old_val)[:30]}...', "
                                f"new (first 30 chars)='{str(val)[:30]}...'"
                            )
                    else:
                        self.logger.warning(LogModule.TRANS,
                            f"[SEGMENTS_AGENT] Unknown key '{key}' found in chunk {chunk_idx}, ignored. "
                            f"Available keys in indexed_translated: {list(indexed_translated.keys())[:10]}..."
                        )
                
                if keys_updated_in_chunk == 0:
                    self.logger.warning(LogModule.TRANS,
                        f"[SEGMENTS_AGENT] Chunk {chunk_idx} updated 0 keys! "
                        f"Chunk keys: {chunk_keys}, "
                        f"Sample indexed_translated keys: {list(indexed_translated.keys())[:10]}"
                    )
                else:
                    self.logger.debug(LogModule.TRANS,
                        f"[SEGMENTS_AGENT] Chunk {chunk_idx} updated {keys_updated_in_chunk} keys successfully"
                    )
            except (AttributeError, TypeError) as e:
                self.logger.error(LogModule.TRANS,
                    f"[SEGMENTS_AGENT] Type or attribute error occurred while processing chunk {chunk_idx}, skipped. "
                    f"Chunk: {chunk}, Error: {e.__repr__()}"
                )
            except Exception as e:
                self.logger.error(LogModule.TRANS,
                    f"[SEGMENTS_AGENT] Unknown error occurred while processing chunk {chunk_idx}: {e.__repr__()}"
                )
        
        # Log summary
        expected_keys = len(indexed_originals)
        if total_keys_updated < expected_keys:
            missing_keys = set(indexed_originals.keys()) - set(
                k for k, v in indexed_translated.items() 
                if v != indexed_originals.get(k)
            )
            if missing_keys:
                self.logger.warning(LogModule.TRANS,
                    f"[SEGMENTS_AGENT] Only {total_keys_updated}/{expected_keys} keys were updated. "
                    f"Missing keys (first 10): {list(missing_keys)[:10]}"
                )
        else:
            self.logger.debug(LogModule.TRANS,
                f"[SEGMENTS_AGENT] Successfully updated {total_keys_updated}/{expected_keys} keys from {len(translated_chunks)} chunks"
            )

        # Rebuild final list
        # CRITICAL: Sort keys numerically to ensure correct order (e.g., "0", "1", "2", ..., "10", not "0", "1", "10", "2")
        sorted_keys = sorted(indexed_translated.keys(), key=lambda k: int(k) if k.isdigit() else float('inf'))
        ls = [indexed_translated[k] for k in sorted_keys]
        
        result = []
        last_end = 0
        for start, end in merged_indices_list:
            result.extend(ls[last_end:start])
            merged_item = "".join(map(str, ls[start:end]))
            result.append(merged_item)
            last_end = end

        result.extend(ls[last_end:])
        return result

    def update_glossary_dict(self, update_dict: dict | None):
        if self.glossary_dict is None:
            self.glossary_dict = {}
        if update_dict is not None:
            self.glossary_dict = update_dict | self.glossary_dict
