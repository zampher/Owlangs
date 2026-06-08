# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0
import asyncio
from dataclasses import dataclass
from typing import Self, Literal

import srt  # Import srt library to handle subtitle files

from agents.segments_agent import SegmentsTranslateAgentConfig, SegmentsTranslateAgent
from ir.document import Document
from translator.ai_translator.base import AiTranslatorConfig, AiTranslator
from logger.logger import LogModule


@dataclass
class SrtTranslatorConfig(AiTranslatorConfig):
    insert_mode: Literal["replace", "append", "prepend"] = "replace"
    separator: str = "\n"


class SrtTranslator(AiTranslator):
    """
    A translator for translating SRT (.srt) subtitle files.
    It extracts text content from each subtitle block, translates it, and writes the translation back according to configuration.
    """

    def __init__(self, config: SrtTranslatorConfig):
        super().__init__(config=config)
        self.chunk_size = config.chunk_size
        self.translate_agent = None
        if not self.skip_translate:
            agent_config = SegmentsTranslateAgentConfig(
                custom_prompt=config.custom_prompt,
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
                write_timeout=getattr(config, 'write_timeout', None),
                logger=self.logger,
                glossary_dict=config.glossary_dict,
                retry=config.retry,
                max_tokens=getattr(config, 'max_tokens', None),  # Get max_tokens from platform config
                segment_limit=getattr(config, 'segment_limit', 100),
            )
            self.translate_agent = SegmentsTranslateAgent(agent_config)
        self.insert_mode = config.insert_mode
        self.separator = config.separator

    def _pre_translate(self, document: Document):
        """
        Preprocessing step: Parse SRT file and extract subtitle text with proper chunking.

        Returns:
            tuple: (List of parsed subtitle objects, List of original texts to be translated (chunked))
        """
        try:
            # Use utf-8-sig decoding to handle possible BOM (Byte Order Mark)
            srt_content = document.content.decode('utf-8-sig')
        except (UnicodeDecodeError, AttributeError) as e:
            self.logger.error(LogModule.TRANS, f"Unable to decode SRT file content, please ensure file encoding is UTF-8: {e}")
            return [], []

        # Use srt library to parse content
        try:
            subtitles = list(srt.parse(srt_content))
        except srt.SRTParseError as e:
            self.logger.error(LogModule.TRANS, f"Failed to parse SRT file: {e}")
            return [], []

        # Use SrtExtractor to properly chunk subtitles according to chunk_size
        # This ensures proper segmentation instead of merging all text together
        from extractor.srt_extractor import SrtExtractor
        extractor = SrtExtractor(srt_content, chunk_size=self.chunk_size)
        extract_result = extractor.extract()
        
        # Extract chunked segments for translation
        original_texts = extract_result.segments
        
        # Store mapping from chunk index to subtitle indices for later reconstruction
        # This will be used in _after_translate to map translated chunks back to individual subtitles
        self._chunk_to_subtitle_map = []
        self._subtitle_list = subtitles
        
        # Build mapping: for each chunk, find which subtitles it contains
        for chunk_idx, chunk_segment in enumerate(extract_result.segments):
            chunk_subtitle_indices = []
            # Find subtitles that match this chunk segment
            # The chunk segment may contain multiple subtitle texts merged together
            chunk_text = chunk_segment.strip()
            for sub_idx, subtitle in enumerate(subtitles):
                if subtitle.content in chunk_text or chunk_text in subtitle.content:
                    chunk_subtitle_indices.append(sub_idx)
            self._chunk_to_subtitle_map.append(chunk_subtitle_indices)
        
        return subtitles, original_texts

    def _after_translate(self, subtitles: list[srt.Subtitle], translated_texts: list[str],
                         original_texts: list[str]) -> bytes:
        """
        Post-translation processing step: Write translations back to subtitle objects according to configuration mode and generate new SRT file content.
        
        Note: If chunks were used (via SrtExtractor), translated_texts contains chunked translations.
        We need to split chunks back to individual subtitles using the mapping stored in _chunk_to_subtitle_map.

        Returns:
            bytes: Byte stream of new SRT file content.
        """
        # Check if we used chunking (has _chunk_to_subtitle_map)
        if hasattr(self, '_chunk_to_subtitle_map') and self._chunk_to_subtitle_map:
            # Split translated chunks back to individual subtitles
            # Each chunk may contain multiple subtitles merged together
            subtitle_translations = {}
            for chunk_idx, translated_chunk in enumerate(translated_texts):
                chunk_subtitle_indices = self._chunk_to_subtitle_map[chunk_idx]
                original_chunk = original_texts[chunk_idx] if chunk_idx < len(original_texts) else ""
                
                # If chunk contains only one subtitle, use the translated chunk directly
                if len(chunk_subtitle_indices) == 1:
                    sub_idx = chunk_subtitle_indices[0]
                    subtitle_translations[sub_idx] = translated_chunk
                else:
                    # If chunk contains multiple subtitles, try to split the translated chunk
                    # by matching with original subtitle texts
                    translated_lines = translated_chunk.split('\n\n')
                    original_lines = original_chunk.split('\n\n')
                    
                    # Match translated lines with original subtitles
                    for i, sub_idx in enumerate(chunk_subtitle_indices):
                        if i < len(translated_lines):
                            subtitle_translations[sub_idx] = translated_lines[i].strip()
                        else:
                            # Fallback: use original subtitle content if no translation available
                            subtitle_translations[sub_idx] = subtitles[sub_idx].content
            
            # Update subtitles with translations
            for i, sub in enumerate(subtitles):
                if i in subtitle_translations:
                    translated_text = subtitle_translations[i]
                    original_text = sub.content

                    # Update subtitle content according to insert mode
                    if self.insert_mode == "replace":
                        sub.content = translated_text
                    elif self.insert_mode == "append":
                        sub.content = original_text.strip() + self.separator + translated_text.strip()
                    elif self.insert_mode == "prepend":
                        sub.content = translated_text.strip() + self.separator + original_text.strip()
                    else:
                        self.logger.error(LogModule.TRANS, f"Invalid SrtTranslatorConfig parameter: insert_mode='{self.insert_mode}'")
                        sub.content = translated_text
        else:
            # Original logic: one-to-one mapping (each subtitle is a separate segment)
            for i, sub in enumerate(subtitles):
                if i < len(translated_texts):
                    translated_text = translated_texts[i]
                    original_text = original_texts[i] if i < len(original_texts) else sub.content

                    # Update subtitle content according to insert mode
                    if self.insert_mode == "replace":
                        sub.content = translated_text
                    elif self.insert_mode == "append":
                        sub.content = original_text.strip() + self.separator + translated_text.strip()
                    elif self.insert_mode == "prepend":
                        sub.content = translated_text.strip() + self.separator + original_text.strip()
                    else:
                        self.logger.error(LogModule.TRANS, f"Invalid SrtTranslatorConfig parameter: insert_mode='{self.insert_mode}'")
                        sub.content = translated_text

        # Use srt library to recompose modified subtitle object list into SRT format string
        new_srt_content_str = srt.compose(subtitles)

        # Return UTF-8 encoded byte stream
        return new_srt_content_str.encode('utf-8')

    def translate(self, document: Document) -> Self:
        """
        Synchronously translate SRT document.
        """
        subtitles, original_texts = self._pre_translate(document)

        if not original_texts:
            self.logger.info(LogModule.TRANS, "\nNo subtitle content found in file that needs translation.")
            return self
        if self.glossary_agent:
            self.glossary_dict_gen = self.glossary_agent.send_segments(original_texts, self.chunk_size)
            if self.translate_agent:
                self.translate_agent.update_glossary_dict(self.glossary_dict_gen)
        # --- Step 2: Call translation Agent ---
        if self.translate_agent:
            translated_texts = self.translate_agent.send_segments(original_texts, self.chunk_size)
        else:
            translated_texts = original_texts
        # --- Step 3: Post-process and update document content ---
        document.content = self._after_translate(subtitles, translated_texts, original_texts)
        return self

    async def translate_async(self, document: Document, progress_callback=None) -> Self:
        """
        Asynchronously translate SRT document.
        """
        # I/O intensive operations run in thread
        subtitles, original_texts = await asyncio.to_thread(self._pre_translate, document)

        if not original_texts:
            self.logger.info(LogModule.TRANS, "\nNo subtitle content found in file that needs translation.")
            return self

        if self.glossary_agent:
            self.glossary_dict_gen = await self.glossary_agent.send_segments_async(original_texts, self.chunk_size, progress_callback=progress_callback)
            if self.translate_agent:
                self.translate_agent.update_glossary_dict(self.glossary_dict_gen)

        # --- Step 2: Call translation Agent (async) ---
        if self.translate_agent:
            # Set task_state on agent for API debug output
            task_id = getattr(self, '_task_id', None)
            if task_id:
                try:
                    from backend.app.services.task import task_manager
                    task_state = task_manager.get_task(task_id) if task_id else None
                    if task_state and self.translate_agent:
                        self.translate_agent.task_state = task_state
                        self.translate_agent.task_id = task_id
                except Exception as e:
                    self.logger.debug(LogModule.TRANS, f"[SRT_TRANSLATOR] Failed to set task_state on agent: {e}")
            
            translated_texts = await self.translate_agent.send_segments_async(original_texts, self.chunk_size, progress_callback=progress_callback)
            
            # Save API logs to temp directory
            if task_id:
                try:
                    from backend.app.services.task import task_manager
                    from utils.chunk_translation_helper import save_api_logs_to_temp_dir
                    task_state = task_manager.get_task(task_id) if task_id else None
                    if task_state:
                        save_api_logs_to_temp_dir(
                            task_state=task_state,
                            task_id=task_id,
                            subfolder="translation",
                            llm_api_input=task_state.get('llm_api_input'),
                            llm_api_output=task_state.get('llm_api_output'),
                            llm_api_system_prompt=task_state.get('llm_api_system_prompt'),
                        )
                except Exception as log_e:
                    self.logger.warning(LogModule.TRANS, f"[SRT_TRANSLATOR] Failed to save API logs: {log_e}", exc_info=True)
        else:
            translated_texts = original_texts
        # --- Step 3: Post-process and update document content (I/O intensive) ---
        document.content = await asyncio.to_thread(
            self._after_translate, subtitles, translated_texts, original_texts
        )
        return self
