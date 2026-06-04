# SPDX-FileCopyrightText: 2026 Zamphers
# SPDX-License-Identifier: MPL-2.0
from dataclasses import dataclass
from pathlib import Path
from typing import Self, Dict, Any

from exporter.base import ExporterConfig
from exporter.docx.docx2docx_exporter import Docx2DocxExporter
from exporter.docx.docx2html_exporter import Docx2HTMLExporterConfig, Docx2HTMLExporter
from glossary.glossary import Glossary
from ir.document import Document
from logger.logger import LogModule
from translator.ai_translator.docx_translator import DocxTranslatorConfig, DocxTranslator
from workflow.base import Workflow, WorkflowConfig
from workflow.interfaces import HTMLExportable, DocxExportable


@dataclass(kw_only=True)
class DocxWorkflowConfig(WorkflowConfig):
    translator_config: DocxTranslatorConfig
    html_exporter_config: Docx2HTMLExporterConfig
    translate_headers_footers: bool = True
    translate_textboxes_sdts: bool = True


class DocxWorkflow(Workflow[DocxWorkflowConfig, Document, Document], HTMLExportable[Docx2HTMLExporterConfig],
                   DocxExportable[ExporterConfig]):
    def __init__(self, config: DocxWorkflowConfig):
        super().__init__(config=config)
        self._docx_extras_original: Dict[str, Any] = {}
        if config.logger:
            for sub_config in [self.config.translator_config]:
                if sub_config:
                    sub_config.logger = config.logger

    def _is_toc_content(self, text: str) -> bool:
        """Check if text content is a table of contents"""
        if not text:
            return False
        
        lines = text.split('\n')
        if len(lines) < 3:  # Less than 3 lines is unlikely to be a TOC
            return False
        
        # Check for TOC keywords (including Chinese "目录")
        toc_indicators = ['目录', 'contents', 'table of contents', 'toc']
        if any(indicator in text.lower() for indicator in toc_indicators):
            return True
        
        # Check for numbered pattern
        numbered_entries = 0
        for line in lines:
            line = line.strip()
            if line:
                # 排除版本号模式
                if any(keyword in line.lower() for keyword in ['版本', 'version', 'v']):
                    continue
                # 检查TOC模式：以数字结尾或包含省略号
                if line[-1].isdigit() or '...' in line:
                    numbered_entries += 1
        
        # If more than half the lines look like numbered TOC entries
        if numbered_entries >= len(lines) * 0.5:
            return True
        
        return False

    def _pre_translate(self, document_original: Document):
        document = document_original.copy()
        translate_config = self.config.translator_config
        translator = DocxTranslator(translate_config)
        return document, translator

    def translate(self) -> Self:
        document, translator = self._pre_translate(self.document_original)
        
        # 翻译文档主体内容
        translator.translate(document)
        
        # Translate headers/footers (if enabled)
        if self.config.translate_headers_footers:
            from converter.x2md.docx_extras import extract_headers_footers, apply_headers_footers
            try:
                # Extract headers/footers from current document content to avoid overwriting body translation
                items = extract_headers_footers(document.content)
                if items:
                    self.logger.info(LogModule.WORKFLOW,f"Extracted {len(items)} header/footer texts")
                    self._docx_extras_original["headers_footers"] = items
                    # Batch translation
                    texts = []
                    for item in items:
                        if isinstance(item, (list, tuple)) and len(item) == 2:
                            texts.append(item[1])
                        else:
                            self.logger.warning(LogModule.WORKFLOW, f"Invalid header/footer item format: {item!r}, skipping")
                    if translator.translate_agent:
                        translated_list = translator.translate_agent.send_segments(texts, translator.chunk_size)
                    else:
                        translated_list = texts
                    translated_map = {}
                    for item, translated_text in zip(items, translated_list):
                        if not isinstance(item, (list, tuple)) or len(item) != 2:
                            continue
                        key = item[0]
                        if translated_text and str(translated_text).strip():
                            translated_map[key] = translated_text
                    if translated_map:
                        # Write back to current document content
                        new_bytes = apply_headers_footers(document.content, translated_map)
                        document.content = new_bytes
                        self.logger.info(LogModule.WORKFLOW,"Header/footer translation completed")
            except Exception as e:
                self.logger.warning(LogModule.WORKFLOW,f"Header/footer translation failed: {e}")
        
        # Translate textboxes and SDTs (if enabled)
        if self.config.translate_textboxes_sdts:
            from converter.x2md.docx_extras import extract_text_in_textboxes_and_sdts, apply_text_in_textboxes_and_sdts
            try:
                items = extract_text_in_textboxes_and_sdts(document.content)
                if items:
                    self.logger.info(LogModule.WORKFLOW,f"Extracted {len(items)} textbox/SDT texts")
                    
                    # Filter out TOC content
                    filtered_items = []
                    skipped_toc_count = 0
                    
                    for i, item in enumerate(items):
                        if not isinstance(item, (list, tuple)) or len(item) != 2:
                            self.logger.warning(LogModule.WORKFLOW, f"  [{i}] Invalid item format in textbox/SDT extraction: {item!r}, skipping")
                            continue
                        key, text = item
                        # Check if it's TOC content
                        if self._is_toc_content(text):
                            self.logger.info(LogModule.WORKFLOW,f"  [{i}] {key}: Skipping TOC content - {text[:50]}...")
                            skipped_toc_count += 1
                        else:
                            filtered_items.append((key, text))
                            self.logger.info(LogModule.WORKFLOW,f"  [{i}] {key}: {text[:50]}...")
                    
                    if skipped_toc_count > 0:
                        self.logger.info(LogModule.WORKFLOW,f"Skipped {skipped_toc_count} TOC contents")
                    
                    if filtered_items:
                        self._docx_extras_original["textboxes_sdts"] = filtered_items
                        texts = []
                        for item in filtered_items:
                            if isinstance(item, (list, tuple)) and len(item) == 2:
                                texts.append(item[1])
                            else:
                                self.logger.warning(LogModule.WORKFLOW, f"Invalid textbox/SDT item format: {item!r}, skipping")
                        if translator.translate_agent:
                            translated_list = translator.translate_agent.send_segments(texts, translator.chunk_size)
                        else:
                            translated_list = texts
                        translated_map = {}
                        for item, translated_text in zip(filtered_items, translated_list):
                            if not isinstance(item, (list, tuple)) or len(item) != 2:
                                continue
                            key = item[0]
                            if translated_text and str(translated_text).strip():
                                translated_map[key] = translated_text
                        if translated_map:
                            new_bytes = apply_text_in_textboxes_and_sdts(document.content, translated_map)
                            document.content = new_bytes
                            self.logger.info(LogModule.WORKFLOW,"Textbox and SDT translation completed")
                            # Verify: re-extract textbox text to confirm translation was applied
                            try:
                                verify_items = extract_text_in_textboxes_and_sdts(document.content)
                                for v_item in verify_items:
                                    if isinstance(v_item, (list, tuple)) and len(v_item) == 2:
                                        v_key, v_text = v_item
                                        self.logger.info(
                                            LogModule.WORKFLOW,
                                            f"[TBX-VERIFY] After apply: {v_key} = '{str(v_text)[:80]}...'"
                                        )
                            except Exception as ve:
                                self.logger.warning(LogModule.WORKFLOW, f"[TBX-VERIFY] Verification failed: {ve}")
                    else:
                        self.logger.info(LogModule.WORKFLOW,"All SDT contents are TOC, skipping translation")
                else:
                    self.logger.info(LogModule.WORKFLOW,"No textbox/SDT texts found")
            except Exception as e:
                self.logger.warning(LogModule.WORKFLOW,f"Textbox/SDT translation failed: {e}")
        
        if translator.glossary_dict_gen:
            self.attachment.add_document("glossary", Glossary.glossary_dict2csv(translator.glossary_dict_gen))
        self.document_translated = document
        return self

    async def translate_async(self, progress_callback=None, task_id: str = None, 
                              original_filename: str = None, workflow_type: str = None) -> Self:
        document, translator = self._pre_translate(self.document_original)
        
        # Store translator as instance attribute so token stats can be extracted later
        self.translator = translator
        
        # Store task info in translator for segment recording
        if task_id:
            translator._task_id = task_id
            translator._original_filename = original_filename
            translator._workflow_type = workflow_type
            # Also store task_id in translate_agent for dynamic glossary loading
            if translator.translate_agent:
                translator.translate_agent._task_id = task_id
            self.logger.info(LogModule.WORKFLOW,f"Stored segment recording params: task_id={task_id}, filename={original_filename}, workflow={workflow_type}")
        
        # 翻译文档主体内容
        await translator.translate_async(document, progress_callback)
        
        # Save main body translation token stats before textbox/SDT translation resets the counter
        # Note: send_prompts_async resets token_counter, so we need to save stats before textbox/SDT translation
        main_body_token_stats = None
        if translator.translate_agent and translator.translate_agent.token_counter:
            main_body_token_stats = translator.translate_agent.token_counter.get_stats().copy()
            self.logger.info(LogModule.WORKFLOW,f"Saved main body translation token stats: total={main_body_token_stats.get('total_tokens', 0)}")
        
        # Translate headers/footers (if enabled)
        if self.config.translate_headers_footers:
            from converter.x2md.docx_extras import extract_headers_footers, apply_headers_footers
            try:
                # Extract headers/footers from current document content to avoid overwriting body translation
                items = extract_headers_footers(document.content)
                if items:
                    self.logger.info(LogModule.WORKFLOW,f"Extracted {len(items)} header/footer texts")
                    self._docx_extras_original["headers_footers"] = items
                    # Also save to task_state if task_id is available
                    if task_id:
                        from app.services.task import task_manager
                        ts = task_manager.get_task(task_id)
                        if ts:
                            ts.setdefault("docx_extras_original", {})["headers_footers"] = items
                    # Batch translation（异步）
                    texts = []
                    for item in items:
                        if isinstance(item, (list, tuple)) and len(item) == 2:
                            texts.append(item[1])
                        else:
                            self.logger.warning(LogModule.WORKFLOW, f"Invalid header/footer item format: {item!r}, skipping")
                    if translator.translate_agent:
                        translated_list = await translator.translate_agent.send_segments_async(texts, translator.chunk_size)
                    else:
                        translated_list = texts
                    translated_map = {}
                    for item, translated_text in zip(items, translated_list):
                        if not isinstance(item, (list, tuple)) or len(item) != 2:
                            continue
                        key = item[0]
                        if translated_text and str(translated_text).strip():
                            translated_map[key] = translated_text
                    if translated_map:
                        # Write back to current document content
                        new_bytes = apply_headers_footers(document.content, translated_map)
                        document.content = new_bytes
                        self.logger.info(LogModule.WORKFLOW,"Header/footer translation completed")
            except Exception as e:
                self.logger.warning(LogModule.WORKFLOW,f"Header/footer translation failed: {e}")
        
        # Translate textboxes and SDTs (if enabled)
        if self.config.translate_textboxes_sdts:
            from converter.x2md.docx_extras import extract_text_in_textboxes_and_sdts, apply_text_in_textboxes_and_sdts
            try:
                items = extract_text_in_textboxes_and_sdts(document.content)
                if items:
                    self.logger.info(LogModule.WORKFLOW,f"Extracted {len(items)} textbox/SDT texts")
                    
                    # Filter out TOC content
                    filtered_items = []
                    skipped_toc_count = 0
                    
                    for i, item in enumerate(items):
                        if not isinstance(item, (list, tuple)) or len(item) != 2:
                            self.logger.warning(LogModule.WORKFLOW, f"  [{i}] Invalid item format in textbox/SDT extraction: {item!r}, skipping")
                            continue
                        key, text = item
                        # Check if it's TOC content
                        if self._is_toc_content(text):
                            self.logger.info(LogModule.WORKFLOW,f"  [{i}] {key}: Skipping TOC content - {text[:50]}...")
                            skipped_toc_count += 1
                        else:
                            filtered_items.append((key, text))
                            self.logger.info(LogModule.WORKFLOW,f"  [{i}] {key}: {text[:50]}...")
                    
                    if skipped_toc_count > 0:
                        self.logger.info(LogModule.WORKFLOW,f"Skipped {skipped_toc_count} TOC contents")
                    
                    if filtered_items:
                        self._docx_extras_original["textboxes_sdts"] = filtered_items
                        # Also save to task_state if task_id is available
                        if task_id:
                            from app.services.task import task_manager
                            ts = task_manager.get_task(task_id)
                            if ts:
                                ts.setdefault("docx_extras_original", {})["textboxes_sdts"] = filtered_items
                        texts = []
                        for item in filtered_items:
                            if isinstance(item, (list, tuple)) and len(item) == 2:
                                texts.append(item[1])
                            else:
                                self.logger.warning(LogModule.WORKFLOW, f"Invalid textbox/SDT item format: {item!r}, skipping")
                        # Log pre-translation summary (before API call, avoids truncation)
                        self.logger.info(
                            LogModule.WORKFLOW,
                            f"[TBX-PRE] Translating {len(texts)} textbox/SDT texts, "
                            f"keys={[item[0] for item in filtered_items]}"
                        )
                        # Save snapshot before async call to isolate from any mutation
                        tb_items_snapshot = [tuple(item) if isinstance(item, (list, tuple)) else item for item in filtered_items]
                        if translator.translate_agent:
                            translated_list = await translator.translate_agent.send_segments_async(texts, translator.chunk_size)
                        else:
                            translated_list = texts
                        # Log raw API response structure immediately
                        self.logger.info(
                            LogModule.WORKFLOW,
                            f"[TBX-RAW] type={type(translated_list).__name__}, len={len(translated_list) if translated_list is not None else 0}, "
                            f"elem_type={type(translated_list[0]).__name__ if translated_list and len(translated_list) > 0 else 'N/A'}, "
                            f"first={str(translated_list[0])[:80] if translated_list and len(translated_list) > 0 else 'EMPTY'}"
                        )
                        translated_map = {}
                        for idx, (item, translated_text) in enumerate(zip(tb_items_snapshot, translated_list)):
                            if not isinstance(item, (list, tuple)) or len(item) != 2:
                                self.logger.warning(
                                    LogModule.WORKFLOW,
                                    f"[TBX-LOOP] idx={idx}: item type={type(item).__name__} is not a valid pair, skipping"
                                )
                                continue
                            key = item[0]
                            txt_type = type(translated_text).__name__
                            txt_val = str(translated_text)[:80] if translated_text is not None else 'None'
                            txt_ok = bool(translated_text and str(translated_text).strip())
                            self.logger.info(
                                LogModule.WORKFLOW,
                                f"[TBX-LOOP] idx={idx}: key={key!r}, txt_type={txt_type}, txt_val={txt_val!r}, txt_ok={txt_ok}"
                            )
                            if txt_ok:
                                translated_map[key] = translated_text
                        # Log whether translated_map is empty after building it
                        self.logger.info(
                            LogModule.WORKFLOW,
                            f"[TBX-MAP] translated_map size={len(translated_map)}, "
                            f"filtered_items len={len(filtered_items)}, "
                            f"translated_list len={len(translated_list) if translated_list else 0}"
                        )
                        if translated_map:
                            # Log short summary right after API response
                            self.logger.info(
                                LogModule.WORKFLOW,
                                f"[TBX-POST] Got {len(translated_list)} translations, "
                                f"mapped {len(translated_map)} keys, "
                                f"sample: next(iter(translated_map.values()))[:50]={str(next(iter(translated_map.values())))[:50]}"
                            )
                            # 应用翻译后的文本框和SDT
                            new_bytes = apply_text_in_textboxes_and_sdts(document.content, translated_map)
                            document.content = new_bytes
                            self.logger.info(LogModule.WORKFLOW,"Textbox and SDT translation completed")
                            # Save verification file (avoids 50k-char log truncation)
                            try:
                                import tempfile
                                vf = tempfile.NamedTemporaryFile(
                                    mode='wb', suffix='_after_tbx.docx', delete=False
                                )
                                vf.write(document.content)
                                vf.close()
                                self.logger.info(
                                    LogModule.WORKFLOW,
                                    f"[TBX-DEBUG] Saved verification file: {vf.name} ({len(document.content)} bytes)"
                                )
                            except Exception as save_err:
                                self.logger.warning(LogModule.WORKFLOW, f"[TBX-DEBUG] Failed to save verification file: {save_err}")
                            # Verify: re-extract textbox text to confirm translation was applied
                            try:
                                verify_items = extract_text_in_textboxes_and_sdts(document.content)
                                for v_item in verify_items:
                                    if isinstance(v_item, (list, tuple)) and len(v_item) == 2:
                                        v_key, v_text = v_item
                                        self.logger.info(
                                            LogModule.WORKFLOW,
                                            f"[TBX-VERIFY] After apply: {v_key} = '{str(v_text)[:80]}...'"
                                        )
                            except Exception as ve:
                                self.logger.warning(LogModule.WORKFLOW, f"[TBX-VERIFY] Verification failed: {ve}")
                            # Add textbox/SDT items to translation_segments for frontend display
                            try:
                                if task_id:
                                    from app.services.task import task_manager as _tb_tm
                                    _tb_ts = _tb_tm.get_task(task_id)
                                    if _tb_ts:
                                        _seg_data = _tb_ts.get("translation_segments")
                                        if isinstance(_seg_data, dict):
                                            _tb_segs = _seg_data.get("segments")
                                            if isinstance(_tb_segs, list):
                                                _max_idx = max((s.get("segment_index", -1) for s in _tb_segs if isinstance(s.get("segment_index"), int)), default=-1) + 1
                                                _added = 0
                                                for _i, _tb_item in enumerate(tb_items_snapshot):
                                                    if isinstance(_tb_item, (list, tuple)) and len(_tb_item) == 2:
                                                        _tb_key, _tb_source = _tb_item
                                                        _tb_target = translated_map.get(_tb_key, "")
                                                        _tb_segs.append({
                                                            "segment_index": _max_idx + _added,
                                                            "source_text": _tb_source,
                                                            "target_text": _tb_target,
                                                            "modified": False,
                                                            "is_excluded": False,
                                                            "is_image": False,
                                                            "is_failed": False,
                                                            "segment_type": "textbox_sdt",
                                                            "textbox_key": str(_tb_key),
                                                        })
                                                        _added += 1
                                                if _added > 0:
                                                    self.logger.info(
                                                        LogModule.WORKFLOW,
                                                        f"[TBX-SEGMENTS] Added {_added} textbox/SDT segments to translation_segments"
                                                    )
                            except Exception as _tb_seg_err:
                                self.logger.warning(LogModule.WORKFLOW, f"[TBX-SEGMENTS] Failed to add textbox segments: {_tb_seg_err}")
                    else:
                        self.logger.info(LogModule.WORKFLOW,"All SDT contents are TOC, skipping translation")
                else:
                    self.logger.info(LogModule.WORKFLOW,"No textbox/SDT texts found")
            except Exception as e:
                self.logger.warning(LogModule.WORKFLOW,f"Textbox/SDT translation failed: {e}")

        # Merge token stats: main body + textbox/SDT (and header/footer if enabled)
        # Note: send_prompts_async resets token_counter, so textbox/SDT stats are in the counter now
        # We need to merge with the saved main body stats
        if main_body_token_stats is not None and translator.translate_agent and translator.translate_agent.token_counter:
            textbox_token_stats = translator.translate_agent.token_counter.get_stats()
            # Merge the stats
            merged_stats = {
                'input_tokens': main_body_token_stats.get('input_tokens', 0) + textbox_token_stats.get('input_tokens', 0),
                'cached_tokens': main_body_token_stats.get('cached_tokens', 0) + textbox_token_stats.get('cached_tokens', 0),
                'output_tokens': main_body_token_stats.get('output_tokens', 0) + textbox_token_stats.get('output_tokens', 0),
                'reasoning_tokens': main_body_token_stats.get('reasoning_tokens', 0) + textbox_token_stats.get('reasoning_tokens', 0),
                'total_tokens': main_body_token_stats.get('total_tokens', 0) + textbox_token_stats.get('total_tokens', 0),
            }
            # Update the token_counter with merged stats
            translator.translate_agent.token_counter.input_tokens = merged_stats['input_tokens']
            translator.translate_agent.token_counter.cached_tokens = merged_stats['cached_tokens']
            translator.translate_agent.token_counter.output_tokens = merged_stats['output_tokens']
            translator.translate_agent.token_counter.reasoning_tokens = merged_stats['reasoning_tokens']
            translator.translate_agent.token_counter.total_tokens = merged_stats['total_tokens']
            self.logger.info(LogModule.WORKFLOW,f"Merged token stats: main_body={main_body_token_stats.get('total_tokens', 0)}, textbox={textbox_token_stats.get('total_tokens', 0)}, total={merged_stats['total_tokens']}")
        
        if translator.glossary_dict_gen:
            self.attachment.add_document("glossary", Glossary.glossary_dict2csv(translator.glossary_dict_gen))
        self.document_translated = document
        return self

    def export_to_html(self, config: Docx2HTMLExporterConfig = None) -> str:
        config = config or self.config.html_exporter_config
        docu = self._export(Docx2HTMLExporter(config))
        return docu.content.decode()

    def export_to_markdown(self, _: ExporterConfig | None = None) -> str:
        from workflow.html_to_markdown_export import html_content_to_markdown
        return html_content_to_markdown(self.export_to_html())

    def export_to_docx(self, _: ExporterConfig | None = None) -> bytes:
        docu = self._export(Docx2DocxExporter())
        return docu.content

    def save_as_html(self, name: str = None, output_dir: Path | str = "./output",
                     config: Docx2HTMLExporter | None = None) -> Self:
        config = config or self.config.html_exporter_config
        self._save(exporter=Docx2HTMLExporter(config), name=name, output_dir=output_dir)
        return self

    def save_as_docx(self, name: str = None, output_dir: Path | str = "./output",
                     _: ExporterConfig | None = None) -> Self:
        self._save(exporter=Docx2DocxExporter(), name=name, output_dir=output_dir)
        return self
