# SPDX-FileCopyrightText: 2025 QinHan
# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

import asyncio
import json
from dataclasses import dataclass
from json import JSONDecodeError
from logging import Logger

import json_repair

from agents import AgentConfig, Agent
from agents.agent import AgentResultError
from logger.logger import LogModule
from utils.json_utils import segments2json_chunks
from utils.language_utils import get_language_name_from_code


@dataclass
class GlossaryAgentConfig(AgentConfig):
    to_lang: str
    custom_prompt: str | None = None
    detection_mode: str = "uncertain"  # "uncertain" or "deep"


class GlossaryAgent(Agent):
    def __init__(self, config: GlossaryAgentConfig):
        super().__init__(config)
        self.to_lang = config.to_lang
        # Convert language code to full language name for better AI recognition
        self.to_lang_name = get_language_name_from_code(config.to_lang)
        self.task_state = None  # Will be set by caller if task_state is available
        self.detection_mode = config.detection_mode
        
        # Build system prompt based on detection mode
        if config.detection_mode == "uncertain":
            # Uncertain terms mode: Focus on terms that may have translation errors
            self.system_prompt = f"""
# Role
You are a professional glossary extractor specialized in identifying uncertain terms that may have translation errors.

# Task
Identify terms from JSON-formatted paragraphs that are likely to be mistranslated or need verification, and provide correct translations in {self.to_lang_name} ({self.to_lang}).
Output format: [{{"src": "<Original Term>", "dst": "<Translated Term>"}}]

# Requirements
- Target language: {self.to_lang_name} ({self.to_lang})
- Focus on terms that are likely to cause translation errors:
  * Technical terms with multiple possible translations
  * Proper nouns that may be transliterated incorrectly
  * Domain-specific abbreviations that need context
  * Terms with ambiguous meanings
  * Specialized terminology that requires expert knowledge
- DO NOT include:
  * Terms with very clear, standard translations (e.g., "the", "is", "and")
  * Common words that are unlikely to be mistranslated
  * UI text, navigation elements, generic labels
  * URLs, email addresses
  * People's Name, Organization, Address
  * Tags like `<ph-xxxxxx>`
- Return empty list [] if no uncertain terms found

# Examples
## Input
The patient was diagnosed with deep vein thrombosis (DVT) at Massachusetts General Hospital. The treatment protocol requires anticoagulation therapy.
## Output
{r'[{"src": "deep vein thrombosis", "dst": "深静脉血栓形成"}, {"src": "DVT", "dst": "深静脉血栓形成"}, {"src": "Massachusetts General Hospital", "dst": "马萨诸塞州总医院"}, {"src": "anticoagulation therapy", "dst": "抗凝治疗"}]'}
Note: Common words like "patient", "diagnosed", "treatment", "protocol", "requires" are excluded as they have standard translations.

## Input
<ph-img123>
## Output
[]
"""
        else:
            # Deep detection mode: Comprehensive domain-specific terms extraction (original behavior)
            self.system_prompt = f"""
# Role
You are a professional glossary extractor for academic and technical documents.

# Task
Extract domain-specific terms from JSON-formatted paragraphs and translate them into {self.to_lang_name} ({self.to_lang}).
Output format: [{{"src": "<Original Term>", "dst": "<Translated Term>"}}]

# Requirements
- Target language: {self.to_lang_name} ({self.to_lang})
- Extract: technical terms, proper nouns, abbreviations, domain-specific terminology
- Exclude: UI text, navigation elements, generic labels, common words, URLs/emails
- Do not include tags like `<ph-xxxxxx>` or duplicate terms
- Return empty list [] if no extractable terms

# Examples
## Input
Deep vein thrombosis (DVT) is a medical condition. The patient was diagnosed at Massachusetts General Hospital. Check for updates
## Output
{r'[{"src": "Deep vein thrombosis", "dst": "深静脉血栓形成"}, {"src": "DVT", "dst": "深静脉血栓形成"}, {"src": "Massachusetts General Hospital", "dst": "马萨诸塞州总医院"}]'}

## Input
<ph-img123>
## Output
[]
"""
        # Append custom prompt if provided by user
        self.custom_prompt = config.custom_prompt
        if config.custom_prompt:
            self.system_prompt += "\n# Important rules or background\n" + config.custom_prompt + "\nEND"

    def _result_handler(self, result: str, origin_prompt: str, logger: Logger):
        if result == "":
            if origin_prompt.strip()!="":
                logger.error(LogModule.TRANS, "Result is empty but original text is not empty")
                raise AgentResultError("Result is empty but original text is not empty")
            return []
        try:
            repaired_result = json_repair.loads(result)
            if not isinstance(repaired_result, list):
                raise AgentResultError(f"GlossaryAgent returned result is not in list JSON format, result: {result}")
            return repaired_result
        except (RuntimeError, JSONDecodeError) as e:
            # Wrap parsing error as ValueError to be caught by send method and retry
            raise AgentResultError(f"Result cannot be parsed correctly: {e.__repr__()}")

    def _error_result_handler(self, origin_prompt: str, logger: Logger):
        if origin_prompt == "":
            return []
        try:
            return json_repair.loads(origin_prompt)
        except (RuntimeError, JSONDecodeError):
            logger.error(LogModule.TRANS, f"Original prompt is also not valid JSON format: {origin_prompt}")
            return [] # If original prompt is also invalid, return empty list

    def send_segments(self, segments: list[str], chunk_size: int):
        self.logger.info(LogModule.TRANS, f"Starting glossary extraction, target language: {self.to_lang}")
        result = {}
        # Calculate text content token limit (excluding system prompt and overhead)
        from utils.chunk_size_converter import get_text_content_token_limit
        text_token_limit = get_text_content_token_limit(chunk_size)
        indexed_originals, chunks, merged_indices_list = segments2json_chunks(segments, text_token_limit)
        prompts = [json.dumps(chunk, ensure_ascii=False) for chunk in chunks]
        translated_chunks = super().send_prompts(prompts=prompts,
                                                 result_handler=self._result_handler,
                                                 error_result_handler=self._error_result_handler)
        for idx, chunk in enumerate(translated_chunks, 1):
            try:
                if not isinstance(chunk, list):
                    self.logger.error(LogModule.TRANS, f"[Chunk #{idx-1}] Received chunk is not a valid list, skipped: {chunk}")
                    continue
                glossary_dict = {d["src"]: d["dst"] for d in chunk if isinstance(d, dict) and "src" in d and "dst" in d}
                if glossary_dict:
                    self.logger.info(LogModule.TRANS, f"[Chunk #{idx-1}] Extracted {len(glossary_dict)} terms from chunk")
                    # Log sample terms from this chunk (first 5)
                    sample_items = list(glossary_dict.items())[:5]
                    for src, dst in sample_items:
                        self.logger.info(LogModule.TRANS, f"[Chunk #{idx-1}]   - {src} -> {dst}")
                    if len(glossary_dict) > 5:
                        self.logger.info(LogModule.TRANS, f"[Chunk #{idx-1}]   ... and {len(glossary_dict) - 5} more terms")
                else:
                    # Log chunk content preview when no terms extracted (for debugging)
                    if idx - 1 < len(chunks):
                        chunk_preview = chunks[idx - 1][:200].replace('\n', ' ') if chunks[idx - 1] else ""
                        self.logger.warning(LogModule.TRANS, f"[Chunk #{idx-1}] No valid terms extracted from chunk. Preview: {chunk_preview}...")
                    else:
                        self.logger.warning(LogModule.TRANS, f"[Chunk #{idx-1}] No valid terms extracted from chunk")
                # Merge with result (duplicate src keys will be overwritten by later chunks, which is desired for deduplication)
                # Use | operator: result | glossary_dict means glossary_dict values take precedence (later chunks override earlier ones)
                result = result | glossary_dict
            except (TypeError, KeyError) as e:
                self.logger.error(LogModule.TRANS, f"[Chunk #{idx-1}] Key or type error occurred while processing glossary chunk, skipped. Chunk: {chunk}, Error: {e.__repr__()}")
            except Exception as e:
                self.logger.error(LogModule.TRANS, f"[Chunk #{idx-1}] Unknown error occurred while processing glossary chunk: {e.__repr__()}")

        # Sort glossary by source term (src) for better readability and usability
        # Python 3.7+ dicts maintain insertion order, so we create a new sorted dict
        sorted_result = dict(sorted(result.items(), key=lambda x: x[0].lower()))
        
        self.logger.info(LogModule.TRANS, f"Glossary extraction completed: total {len(sorted_result)} unique terms extracted (after deduplication and sorting)")
        if sorted_result:
            self.logger.info(LogModule.TRANS, "Final glossary summary (first 20 terms, sorted):")
            for idx, (src, dst) in enumerate(list(sorted_result.items())[:20], 1):
                self.logger.info(LogModule.TRANS, f"  [{idx}] {src} -> {dst}")
            if len(sorted_result) > 20:
                self.logger.info(LogModule.TRANS, f"  ... and {len(sorted_result) - 20} more terms")
        return sorted_result

    async def send_chunks_async(self, chunks: list[str], progress_callback=None, task_id: str = None):
        """
        Send already-merged chunks for glossary extraction (no re-merging).
        
        This method is used when chunks come from Extract phase and are already merged.
        It directly processes chunks without calling segments2json_chunks.
        
        Args:
            chunks: List of already-merged chunk texts (from Extract phase)
            progress_callback: Optional callback function(completed: int, total: int, percent: int) for progress updates
            task_id: Optional task ID for debug file saving
            
        Returns:
            Dictionary mapping source terms to translated terms
        """
        self.logger.info(LogModule.TRANS, f"Starting glossary extraction from {len(chunks)} pre-merged chunks, target language: {self.to_lang}")
        result = {}
        
        # Convert chunks to JSON format expected by the agent
        # Each chunk is already merged, so we format it as a single-segment JSON object
        prompts = []
        for idx, chunk_text in enumerate(chunks):
            # Log chunk content preview for debugging (first 200 chars)
            chunk_preview = chunk_text[:200].replace('\n', ' ') if chunk_text else ""
            self.logger.debug(LogModule.TRANS, f"[Chunk #{idx}] Preview: {chunk_preview}...")
            
            # Format as JSON: {"0": "chunk_text"} for consistency with send_segments_async format
            chunk_dict = {str(idx): chunk_text}
            prompts.append(json.dumps(chunk_dict, ensure_ascii=False))
        
        # Save prompts to task_state for debug file saving
        if hasattr(self, 'task_state') and self.task_state:
            self.task_state['llm_api_input'] = prompts
            self.task_state['llm_api_system_prompt'] = self.system_prompt
        
        self.logger.info(LogModule.TRANS, f"Glossary extraction: {len(chunks)} pre-merged chunks (no re-merging needed)")
        translated_chunks = await super().send_prompts_async(prompts=prompts,
                                                             result_handler=self._result_handler,
                                                             error_result_handler=self._error_result_handler,
                                                             progress_callback=progress_callback)
        
        # Save translated_chunks to task_state for debug file saving
        if hasattr(self, 'task_state') and self.task_state:
            self.task_state['llm_api_output'] = translated_chunks
        
        for idx, chunk in enumerate(translated_chunks, 1):
            try:
                if not isinstance(chunk, list):
                    self.logger.error(LogModule.TRANS, f"[Chunk #{idx-1}] Received chunk is not a valid list, skipped: {chunk}")
                    continue
                glossary_dict = {d["src"]: d["dst"] for d in chunk if isinstance(d, dict) and "src" in d and "dst" in d}
                if glossary_dict:
                    self.logger.info(LogModule.TRANS, f"[Chunk #{idx-1}] Extracted {len(glossary_dict)} terms from chunk")
                    # Log sample terms from this chunk (first 5)
                    sample_items = list(glossary_dict.items())[:5]
                    for src, dst in sample_items:
                        self.logger.info(LogModule.TRANS, f"[Chunk #{idx-1}]   - {src} -> {dst}")
                    if len(glossary_dict) > 5:
                        self.logger.info(LogModule.TRANS, f"[Chunk #{idx-1}]   ... and {len(glossary_dict) - 5} more terms")
                else:
                    # Log chunk content preview when no terms extracted (for debugging)
                    if idx - 1 < len(chunks):
                        chunk_preview = chunks[idx - 1][:200].replace('\n', ' ') if chunks[idx - 1] else ""
                        self.logger.warning(LogModule.TRANS, f"[Chunk #{idx-1}] No valid terms extracted from chunk. Preview: {chunk_preview}...")
                    else:
                        self.logger.warning(LogModule.TRANS, f"[Chunk #{idx-1}] No valid terms extracted from chunk")
                # Merge with result (duplicate src keys will be overwritten by later chunks, which is desired for deduplication)
                # Use | operator: result | glossary_dict means glossary_dict values take precedence (later chunks override earlier ones)
                result = result | glossary_dict
            except (TypeError, KeyError) as e:
                self.logger.error(LogModule.TRANS, f"[Chunk #{idx-1}] Key or type error occurred while processing glossary chunk, skipped. Chunk: {chunk}, Error: {e.__repr__()}")
            except Exception as e:
                self.logger.error(LogModule.TRANS, f"[Chunk #{idx-1}] Unknown error occurred while processing glossary chunk: {e.__repr__()}")
        
        # Final deduplication and sorting: ensure all src keys are unique and sorted
        # Sort glossary by source term (src) for better readability and usability
        # Python 3.7+ dicts maintain insertion order, so we create a new sorted dict
        sorted_result = dict(sorted(result.items(), key=lambda x: x[0].lower()))
        
        self.logger.info(LogModule.TRANS, f"Glossary extraction completed: total {len(sorted_result)} unique terms extracted (after deduplication and sorting)")
        if sorted_result:
            self.logger.info(LogModule.TRANS, "Final glossary summary (first 20 terms, sorted):")
            for idx, (src, dst) in enumerate(list(sorted_result.items())[:20], 1):
                self.logger.info(LogModule.TRANS, f"  [{idx}] {src} -> {dst}")
            if len(sorted_result) > 20:
                self.logger.info(LogModule.TRANS, f"  ... and {len(sorted_result) - 20} more terms")
        
        # Save debug files if DEBUG mode is enabled
        import logging
        import os
        import tempfile
        is_debug_enabled = self.logger.isEnabledFor(logging.DEBUG) or self.logger.level <= logging.DEBUG
        if is_debug_enabled and hasattr(self, 'task_state') and self.task_state:
            try:
                # Use task_state temp_dir if available
                debug_dir = None
                temp_dir = self.task_state.get("temp_dir")
                if temp_dir and os.path.isdir(temp_dir):
                    debug_dir = os.path.join(temp_dir, "debug", "glossary")
                    os.makedirs(debug_dir, exist_ok=True)
                    # Store debug directory path in task_state
                    if "debug_files" not in self.task_state:
                        self.task_state["debug_files"] = {}
                    self.task_state["debug_files"]["glossary_debug_dir"] = debug_dir
                
                # Fallback: create independent debug directory if task_state temp_dir not available
                if not debug_dir:
                    debug_dir = tempfile.mkdtemp(prefix=f"glossary_debug_{task_id or 'unknown'}_")
                
                # Save chunks comparison
                chunks_comparison_file = os.path.join(debug_dir, "chunks_comparison.txt")
                with open(chunks_comparison_file, 'w', encoding='utf-8') as f:
                    max_idx = max(len(chunks), len(translated_chunks))
                    for idx in range(max_idx):
                        f.write(f"{'='*80}\n")
                        f.write(f"Chunk {idx}\n")
                        f.write(f"{'='*80}\n")
                        f.write("ORIGINAL:\n")
                        f.write("-" * 80 + "\n")
                        if idx < len(chunks):
                            f.write(chunks[idx])
                        else:
                            f.write("(missing)")
                        f.write("\n\n")
                        f.write("EXTRACTED TERMS:\n")
                        f.write("-" * 80 + "\n")
                        if idx < len(translated_chunks):
                            f.write(str(translated_chunks[idx]))
                        else:
                            f.write("(missing)")
                        f.write("\n\n")
                
                # Save LLM API input and output if available
                llm_api_input = self.task_state.get('llm_api_input')
                llm_api_output = self.task_state.get('llm_api_output')
                llm_api_system_prompt = self.task_state.get('llm_api_system_prompt')
                if llm_api_input and llm_api_output:
                    llm_api_comparison_file = os.path.join(debug_dir, "llm_api_comparison.txt")
                    with open(llm_api_comparison_file, 'w', encoding='utf-8') as f:
                        # Write API parameters for diagnosis
                        f.write(f"{'='*80}\n")
                        f.write("LLM API PARAMETERS:\n")
                        f.write(f"{'='*80}\n")
                        config = getattr(self, 'config', None)
                        if config:
                            f.write(f"  model_id: {getattr(config, 'model_id', 'N/A')}\n")
                            f.write(f"  temperature: {getattr(config, 'temperature', 'N/A')}\n")
                            f.write(f"  thinking: {getattr(config, 'thinking', 'N/A')}\n")
                            f.write(f"  to_lang: {self.to_lang}\n")
                        f.write(f"{'='*80}\n\n")

                        # Write system prompt at the beginning if available
                        if llm_api_system_prompt:
                            f.write(f"{'='*80}\n")
                            f.write("SYSTEM PROMPT:\n")
                            f.write(f"{'='*80}\n")
                            f.write(llm_api_system_prompt)
                            f.write("\n\n")
                            f.write("Note: This system prompt is used for glossary extraction.\n")
                            f.write(f"Target language: {self.to_lang}\n")
                            f.write(f"{'='*80}\n\n")
                        
                        max_idx = max(len(llm_api_input), len(llm_api_output))
                        for idx in range(max_idx):
                            f.write(f"{'='*80}\n")
                            f.write(f"LLM API Request {idx}\n")
                            f.write(f"{'='*80}\n")
                            f.write("INPUT:\n")
                            f.write("-" * 80 + "\n")
                            if idx < len(llm_api_input):
                                f.write(llm_api_input[idx])
                            else:
                                f.write("(missing)")
                            f.write("\n\n")
                            f.write("OUTPUT:\n")
                            f.write("-" * 80 + "\n")
                            if idx < len(llm_api_output):
                                f.write(str(llm_api_output[idx]))
                            else:
                                f.write("(missing)")
                            f.write("\n\n")
                    self.logger.debug(LogModule.TRANS, f"[GLOSSARY] Saved LLM API comparison to {llm_api_comparison_file}")
                
                self.logger.info(LogModule.TRANS, f"[GLOSSARY] Debug mode enabled: Saved {len(chunks)} chunks to debug folder: {debug_dir}")
            except Exception as e:
                self.logger.warning(LogModule.TRANS, f"[GLOSSARY] Failed to save debug files: {e}", exc_info=True)
        
        return sorted_result

    async def send_segments_async(self, segments: list[str], chunk_size: int, progress_callback=None, task_id: str = None):
        """
        Send segments for glossary extraction with chunk splitting and progress tracking.
        
        Args:
            segments: List of text segments to extract glossary from
            chunk_size: Maximum chunk size in tokens (will be converted to text_token_limit)
            progress_callback: Optional callback function(completed: int, total: int, percent: int) for progress updates
            task_id: Optional task ID for debug file saving
        """
        self.logger.info(LogModule.TRANS, f"Starting glossary extraction, target language: {self.to_lang}")
        result = {}
        # Calculate text content token limit (excluding system prompt and overhead)
        # This matches the sync version's behavior
        from utils.chunk_size_converter import get_text_content_token_limit
        text_token_limit = get_text_content_token_limit(chunk_size)
        indexed_originals, chunks, merged_indices_list = await asyncio.to_thread(segments2json_chunks, segments,
                                                                                 text_token_limit)
        prompts = [json.dumps(chunk, ensure_ascii=False) for chunk in chunks]
        
        # Save prompts to task_state for debug file saving
        if hasattr(self, 'task_state') and self.task_state:
            self.task_state['llm_api_input'] = prompts
            self.task_state['llm_api_system_prompt'] = self.system_prompt
        
        self.logger.info(LogModule.TRANS, f"Glossary extraction: {len(segments)} segments merged into {len(chunks)} chunks (chunk_size={chunk_size}, text_token_limit={text_token_limit})")
        translated_chunks = await super().send_prompts_async(prompts=prompts,
                                                             result_handler=self._result_handler,
                                                             error_result_handler=self._error_result_handler,
                                                             progress_callback=progress_callback)
        
        # Save translated_chunks to task_state for debug file saving
        if hasattr(self, 'task_state') and self.task_state:
            self.task_state['llm_api_output'] = translated_chunks
        for idx, chunk in enumerate(translated_chunks, 1):
            try:
                if not isinstance(chunk, list):
                    self.logger.error(LogModule.TRANS, f"[Chunk #{idx-1}] Received chunk is not a valid list, skipped: {chunk}")
                    continue
                glossary_dict = {d["src"]: d["dst"] for d in chunk if isinstance(d, dict) and "src" in d and "dst" in d}
                if glossary_dict:
                    self.logger.info(LogModule.TRANS, f"[Chunk #{idx-1}] Extracted {len(glossary_dict)} terms from chunk")
                    # Log sample terms from this chunk (first 5)
                    sample_items = list(glossary_dict.items())[:5]
                    for src, dst in sample_items:
                        self.logger.info(LogModule.TRANS, f"[Chunk #{idx-1}]   - {src} -> {dst}")
                    if len(glossary_dict) > 5:
                        self.logger.info(LogModule.TRANS, f"[Chunk #{idx-1}]   ... and {len(glossary_dict) - 5} more terms")
                else:
                    # Log chunk content preview when no terms extracted (for debugging)
                    if idx - 1 < len(chunks):
                        chunk_preview = chunks[idx - 1][:200].replace('\n', ' ') if chunks[idx - 1] else ""
                        self.logger.warning(LogModule.TRANS, f"[Chunk #{idx-1}] No valid terms extracted from chunk. Preview: {chunk_preview}...")
                    else:
                        self.logger.warning(LogModule.TRANS, f"[Chunk #{idx-1}] No valid terms extracted from chunk")
                # Merge with result (duplicate src keys will be overwritten by later chunks, which is desired for deduplication)
                # Use | operator: result | glossary_dict means glossary_dict values take precedence (later chunks override earlier ones)
                result = result | glossary_dict
            except (TypeError, KeyError) as e:
                self.logger.error(LogModule.TRANS, f"[Chunk #{idx-1}] Key or type error occurred while processing glossary chunk, skipped. Chunk: {chunk}, Error: {e.__repr__()}")
            except Exception as e:
                self.logger.error(LogModule.TRANS, f"[Chunk #{idx-1}] Unknown error occurred while processing glossary chunk: {e.__repr__()}")
        
        # Final deduplication and sorting: ensure all src keys are unique and sorted
        # Sort glossary by source term (src) for better readability and usability
        # Python 3.7+ dicts maintain insertion order, so we create a new sorted dict
        sorted_result = dict(sorted(result.items(), key=lambda x: x[0].lower()))
        
        self.logger.info(LogModule.TRANS, f"Glossary extraction completed: total {len(sorted_result)} unique terms extracted (after deduplication and sorting)")
        if sorted_result:
            self.logger.info(LogModule.TRANS, "Final glossary summary (first 20 terms, sorted):")
            for idx, (src, dst) in enumerate(list(sorted_result.items())[:20], 1):
                self.logger.info(LogModule.TRANS, f"  [{idx}] {src} -> {dst}")
            if len(sorted_result) > 20:
                self.logger.info(LogModule.TRANS, f"  ... and {len(sorted_result) - 20} more terms")
        return sorted_result
