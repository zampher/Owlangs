# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0
import asyncio
import xml.etree.ElementTree as ET
import zipfile
from dataclasses import dataclass
from io import BytesIO
from typing import Self, Literal, List, Dict, Any, Tuple

from agents.segments_agent import SegmentsTranslateAgentConfig, SegmentsTranslateAgent
from ir.document import Document
from translator.ai_translator.base import AiTranslatorConfig, AiTranslator
from translator.ai_translator.html_translator import (
    NON_TRANSLATABLE_TAGS,
    SAFE_TAGS,
    _apply_html_translations,
)
from logger.logger import LogModule
from utils.epub_html_segments import (
    collect_epub_paragraph_segments,
    read_epub_all_files,
)


@dataclass
class EpubTranslatorConfig(AiTranslatorConfig):
    insert_mode: Literal["replace", "append", "prepend"] = "replace"
    separator: str = "\n"


class EpubTranslator(AiTranslator):
    """
    A translator for translating content in EPUB files.
    This version uses built-in `zipfile` and `xml` libraries, without depending on `ebooklib`.
    """

    def __init__(self, config: EpubTranslatorConfig):
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
                max_tokens=getattr(config, 'max_tokens', None),
                segment_limit=getattr(config, 'segment_limit', 100),
                use_seg_tags=True,
            )
            self.translate_agent = SegmentsTranslateAgent(agent_config)
        self.insert_mode = config.insert_mode
        self.separator = config.separator

    def _save_ebook_metadata(self, all_files: Dict[str, bytes]) -> None:
        try:
            from utils.ebook_metadata import extract_from_opf

            container_xml = all_files.get("META-INF/container.xml")
            if not container_xml:
                return
            root = ET.fromstring(container_xml)
            ns = {"cn": "urn:oasis:names:tc:opendocument:xmlns:container"}
            opf_path = root.find("cn:rootfiles/cn:rootfile", ns).get("full-path")
            opf_xml = all_files.get(opf_path)
            if not opf_xml:
                return
            opf_root = ET.fromstring(opf_xml)
            ns_opf = {"opf": "http://www.idpf.org/2007/opf"}
            ns_dc = {"opf": "http://www.idpf.org/2007/opf", "dc": "http://purl.org/dc/elements/1.1/"}
            meta = extract_from_opf(opf_root, ns_opf, ns_dc)
            if any(meta.get(k) for k in meta):
                task_id = getattr(self, "_task_id", None)
                if task_id:
                    from backend.app.services.task import task_manager
                    task_state = task_manager.get_task(task_id)
                    if task_state:
                        task_state["ebook_metadata"] = meta
        except Exception as meta_err:
            self.logger.debug(
                LogModule.TRANS,
                f"[EPUB_TRANSLATOR] Could not extract ebook metadata: {meta_err}",
            )

    def _extract_segments(
        self,
        document: Document,
        deep_split: bool = True,
    ) -> Tuple[Dict[str, bytes], List[Tuple[str, str, int, int]], List[str]]:
        """
        Extract paragraph segments using HtmlExtractor (same as Extract phase).

        Returns all_files, file_ranges (path, html_str, start, end), flat segment list.
        """
        all_files = read_epub_all_files(document.content)
        self._save_ebook_metadata(all_files)
        file_ranges, original_texts = collect_epub_paragraph_segments(
            all_files,
            chunk_size=self.chunk_size,
            deep_split=deep_split,
        )
        return all_files, file_ranges, original_texts

    def _apply_translations_to_files(
        self,
        all_files: Dict[str, bytes],
        file_ranges: List[Tuple[str, str, int, int]],
        original_texts: List[str],
        translated_texts: List[str],
    ) -> Dict[str, bytes]:
        for file_path, html_str, start_idx, end_idx in file_ranges:
            file_original = original_texts[start_idx:end_idx]
            file_translated = translated_texts[start_idx:end_idx]
            if not file_original:
                continue
            if self.insert_mode == "append":
                file_translated = [
                    orig + self.separator + trans
                    for orig, trans in zip(file_original, file_translated)
                ]
            elif self.insert_mode == "prepend":
                file_translated = [
                    trans + self.separator + orig
                    for orig, trans in zip(file_original, file_translated)
                ]
            updated_html = _apply_html_translations(
                html_str,
                file_original,
                file_translated,
                NON_TRANSLATABLE_TAGS,
                SAFE_TAGS,
            )
            all_files[file_path] = updated_html
        return all_files

    def _repackage_epub(self, all_files: Dict[str, bytes]) -> bytes:
        output_buffer = BytesIO()
        with zipfile.ZipFile(output_buffer, "w") as zf_out:
            if "mimetype" in all_files:
                zf_out.writestr("mimetype", all_files["mimetype"], compress_type=zipfile.ZIP_STORED)
            for filename, content in all_files.items():
                if filename != "mimetype":
                    zf_out.writestr(filename, content, compress_type=zipfile.ZIP_DEFLATED)
        return output_buffer.getvalue()

    def _filter_excluded_segments(
        self,
        original_texts: List[str],
        task_state: Dict[str, Any] | None,
        task_id: str | None,
    ) -> Tuple[List[int], List[str], List[str]]:
        excluded_indices: set[int] = set()
        if task_state:
            segments_metadata = task_state.get("segments_metadata", {})
            excluded_segment_indices = segments_metadata.get("excluded_segment_indices", [])
            if excluded_segment_indices:
                excluded_indices = {int(x) for x in excluded_segment_indices if x is not None}
                self.logger.info(
                    LogModule.TRANS,
                    f"[EPUB_TRANSLATOR] Task {task_id}: Found {len(excluded_indices)} excluded segments",
                )

        from utils.translation_segments import _is_image_segment

        included_indices: List[int] = []
        included_texts: List[str] = []
        image_skip_count = 0
        for idx, text in enumerate(original_texts):
            if idx in excluded_indices:
                continue
            if _is_image_segment(text):
                image_skip_count += 1
                continue
            included_indices.append(idx)
            included_texts.append(text)
        if image_skip_count:
            self.logger.info(
                LogModule.TRANS,
                f"[EPUB_TRANSLATOR] Task {task_id}: skipping {image_skip_count} image placeholder "
                f"segment(s) from LLM requests",
            )
        return included_indices, included_texts, list(original_texts)

    def translate(self, document: Document) -> Self:
        all_files, file_ranges, original_texts = self._extract_segments(document)
        if not original_texts:
            self.logger.info(LogModule.TRANS, "\nNo plain text content found in file that needs translation.")
            return self

        task_id = getattr(self, "_task_id", None)
        task_state = None
        if task_id:
            try:
                from backend.app.services.task import task_manager
                task_state = task_manager.get_task(task_id)
            except Exception:
                task_state = None

        included_indices, included_texts, _ = self._filter_excluded_segments(
            original_texts, task_state, task_id
        )

        if self.glossary_agent and included_texts:
            self.glossary_dict_gen = self.glossary_agent.send_segments(
                included_texts, self.chunk_size
            )
            if self.translate_agent:
                self.translate_agent.update_glossary_dict(self.glossary_dict_gen)

        if not included_texts:
            translated_texts = original_texts.copy()
        elif self.translate_agent:
            translated_included = self.translate_agent.send_segments(
                included_texts, self.chunk_size, segment_indices=included_indices
            )
            translated_texts = original_texts.copy()
            for i, idx in enumerate(included_indices):
                if i < len(translated_included):
                    translated_texts[idx] = translated_included[i]
        else:
            translated_texts = original_texts.copy()

        all_files = self._apply_translations_to_files(
            all_files, file_ranges, original_texts, translated_texts
        )
        document.content = self._repackage_epub(all_files)
        return self

    async def translate_async(self, document: Document, progress_callback=None) -> Self:
        task_id = getattr(self, "_task_id", None)
        task_state = None
        if task_id:
            try:
                from backend.app.services.task import task_manager
                task_state = task_manager.get_task(task_id)
            except Exception:
                task_state = None

        deep_split_enabled = bool(task_state.get("deep_split") if task_state else True)

        all_files, file_ranges, original_texts = await asyncio.to_thread(
            self._extract_segments, document, deep_split_enabled
        )
        if not original_texts:
            self.logger.info(LogModule.TRANS, "\nNo plain text content found in file that needs translation.")
            return self

        included_indices, included_texts, _ = self._filter_excluded_segments(
            original_texts, task_state, task_id
        )

        if self.glossary_agent and included_texts:
            self.glossary_dict_gen = await self.glossary_agent.send_segments_async(
                included_texts,
                self.chunk_size,
                progress_callback=progress_callback,
            )
            if self.translate_agent:
                self.translate_agent.update_glossary_dict(self.glossary_dict_gen)

        if self.translate_agent:
            if task_state:
                self.translate_agent.task_state = task_state
                self.translate_agent.task_id = task_id

            if not included_texts:
                translated_texts = original_texts.copy()
            else:
                translated_included = await self.translate_agent.send_segments_async(
                    included_texts,
                    self.chunk_size,
                    progress_callback=progress_callback,
                    segment_indices=included_indices,
                )
                translated_texts = original_texts.copy()
                for i, idx in enumerate(included_indices):
                    if i < len(translated_included):
                        translated_texts[idx] = translated_included[i]

            if task_id and task_state:
                try:
                    task_state["epub_original_texts"] = original_texts
                    task_state["epub_translated_texts"] = translated_texts
                    from utils.chunk_translation_helper import save_api_logs_to_temp_dir
                    save_api_logs_to_temp_dir(
                        task_state=task_state,
                        task_id=task_id,
                        subfolder="translation",
                        llm_api_input=task_state.get("llm_api_input"),
                        llm_api_output=task_state.get("llm_api_output"),
                        llm_api_system_prompt=task_state.get("llm_api_system_prompt"),
                    )
                except Exception as log_e:
                    self.logger.warning(
                        LogModule.TRANS,
                        f"[EPUB_TRANSLATOR] Failed to save texts or API logs: {log_e}",
                        exc_info=True,
                    )
        else:
            translated_texts = original_texts.copy()

        all_files = await asyncio.to_thread(
            self._apply_translations_to_files,
            all_files,
            file_ranges,
            original_texts,
            translated_texts,
        )
        document.content = await asyncio.to_thread(self._repackage_epub, all_files)
        return self
