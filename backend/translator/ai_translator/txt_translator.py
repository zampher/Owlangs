# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0
import asyncio
import re
from dataclasses import dataclass
from typing import Self, Literal, List

from agents.segments_agent import SegmentsTranslateAgentConfig, SegmentsTranslateAgent
from backend.app.utils.encoding_utils import decode_with_detection
from ir.document import Document
from translator.ai_translator.base import AiTranslatorConfig, AiTranslator
from logger.logger import LogModule


@dataclass
class TXTTranslatorConfig(AiTranslatorConfig):
    """
    Configuration class for TXTTranslator.

    Attributes:
        insert_mode (Literal["replace", "append", "prepend"]):
            Specify the mode for inserting translated text.
            - "replace": Replace original text with translation.
            - "append": Append translation after original text.
            - "prepend": Prepend translation before original text.
            Default is "replace".
        separator (str):
            String used to separate original and translated text in "append" or "prepend" mode.
            Default is newline "\n".
    """
    insert_mode: Literal["replace", "append", "prepend"] = "replace"
    separator: str = "\n"


class TXTTranslator(AiTranslator):
    """
    A translator for translating plain text (.txt) files.
    It reads file content line by line, translates each line, and writes the translation back according to configuration.
    """

    def __init__(self, config: TXTTranslatorConfig):
        """
        Initialize TXTTranslator.

        Args:
            config (TxtTranslatorConfig): Translator configuration.
        """
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
                use_seg_tags=True,  # Use SEG-tag format for TXT segments
            )
            self.translate_agent = SegmentsTranslateAgent(agent_config)
        self.insert_mode = config.insert_mode
        self.separator = config.separator

    def _pre_translate(self, document: Document) -> List[str]:
        """
        Preprocessing step: Parse TXT file and split text by natural paragraphs.

        Splits by blank lines first (paragraph-first segmentation), so each
        segment is a meaningful paragraph rather than a single line.
        If a paragraph exceeds the chunk token limit, segments2json_chunks()
        will further split it by lines automatically during chunk assembly.

        For large TXT files, prefers segments from source_chunks_cache
        (pre-split by split_markdown_text during import) over raw paragraph splitting
        to maintain consistency with the import phase.

        Args:
            document (Document): Document object to be processed.

        Returns:
            List[str]: List of original text segments to be translated.
        """
        # Try to use source_chunks_cache segments first (consistent with import phase)
        task_id = getattr(self, '_task_id', None)
        if task_id:
            try:
                from backend.app.services.task import task_manager
                task_state = task_manager.get_task(task_id)
                if task_state:
                    cache_info = task_state.get("source_chunks_cache", {})
                    cached_segments = cache_info.get("segments")
                    if cached_segments and len(cached_segments) > 0:
                        self.logger.info(
                            LogModule.TRANS,
                            f"[TXT_TRANSLATOR] Task {task_id}: Using {len(cached_segments)} segments from source_chunks_cache",
                        )
                        return [str(s) for s in cached_segments]
            except Exception as e:
                self.logger.debug(
                    LogModule.TRANS,
                    f"[TXT_TRANSLATOR] Failed to read source_chunks_cache: {e}",
                )

        # Fallback: decode and split by lines
        try:
            raw = document.content
            if raw is None:
                return []
            if not isinstance(raw, (bytes, bytearray)):
                self.logger.error(LogModule.TRANS, "TXT document.content is not bytes; cannot decode.")
                return []
            txt_content = decode_with_detection(bytes(raw))
        except Exception as e:
            self.logger.error(LogModule.TRANS, f"Unable to decode TXT file content: {e}", exc_info=True)
            return []

        # Use paragraph-first segmentation: splits by blank lines into paragraphs,
        # or by individual lines if no blank lines are found.
        # Consistent with split_text_into_paragraphs() used during import/preview.
        from utils.markdown_splitter import split_text_into_paragraphs
        original_texts = split_text_into_paragraphs(txt_content, max_block_size=self.chunk_size)

        return original_texts

    def _after_translate(self, translated_texts: List[str], original_texts: List[str]) -> bytes:
        """
        Post-translation processing step: Merge translated text with original text according to configuration mode and generate new TXT file content.

        Args:
            translated_texts (List[str]): List of translated text lines.
            original_texts (List[str]): List of original text lines.

        Returns:
            bytes: Byte stream of new TXT file content.
        """
        processed_lines = []
        for i, original_text in enumerate(original_texts):
            # If original text is empty line or only contains whitespace, keep it directly without translation processing
            if not original_text.strip():
                processed_lines.append(original_text)
                continue

            translated_text = translated_texts[i]

            # Update content according to insert mode
            if self.insert_mode == "replace":
                processed_lines.append(translated_text)
            elif self.insert_mode == "append":
                # strip() to avoid extra whitespace between original and translated text
                processed_lines.append(original_text.strip() + self.separator + translated_text.strip())
            elif self.insert_mode == "prepend":
                processed_lines.append(translated_text.strip() + self.separator + original_text.strip())
            else:
                self.logger.error(LogModule.TRANS, f"Invalid TxtTranslatorConfig parameter: insert_mode='{self.insert_mode}'")
                # Default fallback to replace mode to avoid program interruption
                processed_lines.append(translated_text)

        # Recombine all processed lines into a single string, separated by newlines
        new_txt_content_str = "\n".join(processed_lines)

        # Return UTF-8 encoded byte stream
        return new_txt_content_str.encode('utf-8')

    def translate(self, document: Document) -> Self:
        """
        Synchronously translate TXT document.

        Args:
            document (Document): Document object to be translated.

        Returns:
            Self: Returns translator instance to support chaining.
        """
        original_texts = self._pre_translate(document)

        if not original_texts:
            self.logger.info(LogModule.TRANS, "\nNo text content found in file that needs translation.")
            return self

        # Filter out lines containing only whitespace characters to avoid unnecessary translation API calls
        texts_to_translate = [text for text in original_texts if text.strip()]

        # --- Step 1: (Optional) Glossary extraction ---
        if self.glossary_agent and texts_to_translate:
            self.glossary_dict_gen = self.glossary_agent.send_segments(texts_to_translate, self.chunk_size)
            if self.translate_agent:
                self.translate_agent.update_glossary_dict(self.glossary_dict_gen)

        # --- Step 2: Call translation Agent ---
        translated_texts_map = {}
        if self.translate_agent and texts_to_translate:
            translated_segments = self.translate_agent.send_segments(texts_to_translate, self.chunk_size)
            translated_texts_map = dict(zip(texts_to_translate, translated_segments))

        # Map translation results back to original line list, non-translated lines remain unchanged
        final_translated_texts = [translated_texts_map.get(text, text) for text in original_texts]

        # Save for segment recording access
        self._original_texts = original_texts
        self._translated_texts = final_translated_texts

        # --- Step 3: Post-process and update document content ---
        document.content = self._after_translate(final_translated_texts, original_texts)
        return self

    async def translate_async(self, document: Document, progress_callback=None) -> Self:
        """
        Asynchronously translate TXT document.

        Args:
            document (Document): Document object to be translated.

        Returns:
            Self: Returns translator instance to support chaining.
        """
        # I/O intensive operations run in thread
        original_texts = await asyncio.to_thread(self._pre_translate, document)

        if not original_texts:
            self.logger.info(LogModule.TRANS, "\nNo text content found in file that needs translation.")
            return self

        # Filter out lines containing only whitespace characters
        texts_to_translate = [text for text in original_texts if text.strip()]

        # --- Step 1: (Optional) Glossary extraction (async) ---
        if self.glossary_agent and texts_to_translate:
            self.glossary_dict_gen = await self.glossary_agent.send_segments_async(texts_to_translate, self.chunk_size)
            if self.translate_agent:
                self.translate_agent.update_glossary_dict(self.glossary_dict_gen)

        # --- Step 2: Call translation Agent (async) ---
        translated_texts_map = {}
        if self.translate_agent and texts_to_translate:
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
                    self.logger.debug(LogModule.TRANS, f"[TXT_TRANSLATOR] Failed to set task_state on agent: {e}")
            
            translated_segments = await self.translate_agent.send_segments_async(texts_to_translate, self.chunk_size)
            translated_texts_map = dict(zip(texts_to_translate, translated_segments))
            
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
                    self.logger.warning(LogModule.TRANS, f"[TXT_TRANSLATOR] Failed to save API logs: {log_e}", exc_info=True)

        # Map translation results back to original line list
        final_translated_texts = [translated_texts_map.get(text, text) for text in original_texts]

        # Save for segment recording access (instance attributes + task_state)
        self._original_texts = original_texts
        self._translated_texts = final_translated_texts

        # Save translated segments to task_state for segment recording
        if task_id:
            try:
                from backend.app.services.task import task_manager
                task_state = task_manager.get_task(task_id) if task_id else None
                if task_state:
                    task_state["txt_translated_texts"] = final_translated_texts
            except Exception as e:
                self.logger.debug(LogModule.TRANS, f"[TXT_TRANSLATOR] Failed to save translated texts: {e}")

        # --- Step 3: Post-process and update document content (I/O intensive) ---
        document.content = await asyncio.to_thread(
            self._after_translate, final_translated_texts, original_texts
        )
        return self