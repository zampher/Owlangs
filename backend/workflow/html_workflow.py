# SPDX-FileCopyrightText: 2026 Zampherss
# SPDX-License-Identifier: MPL-2.0
from dataclasses import dataclass
from pathlib import Path
from typing import Self

from exporter.base import ExporterConfig
from exporter.html.html2html_exporter import Html2HtmlExporter
from glossary.glossary import Glossary

from ir.document import Document
from translator.ai_translator.html_translator import HtmlTranslatorConfig, HtmlTranslator
from workflow.base import Workflow, WorkflowConfig
from workflow.interfaces import HTMLExportable


@dataclass(kw_only=True)
class HtmlWorkflowConfig(WorkflowConfig):
    translator_config: HtmlTranslatorConfig



class HtmlWorkflow(Workflow[HtmlWorkflowConfig, Document, Document], HTMLExportable):
    def __init__(self, config: HtmlWorkflowConfig):
        super().__init__(config=config)
        if config.logger:
            for sub_config in [self.config.translator_config]:
                if sub_config:
                    sub_config.logger = config.logger

    def _pre_translate(self, document_original: Document):
        document = document_original.copy()
        translate_config = self.config.translator_config
        translator = HtmlTranslator(translate_config)
        return document, translator

    def translate(self) -> Self:
        document, translator = self._pre_translate(self.document_original)
        translator.translate(document)
        if translator.glossary_dict_gen:
            self.attachment.add_document("glossary", Glossary.glossary_dict2csv(translator.glossary_dict_gen))
        self.document_translated = document
        return self

    async def translate_async(self, task_id: str = None, task_state: dict = None, progress_callback=None) -> Self:
        document, translator = self._pre_translate(self.document_original)
        await translator.translate_async(document, task_id=task_id, task_state=task_state, progress_callback=progress_callback)
        if translator.glossary_dict_gen:
            self.attachment.add_document("glossary", Glossary.glossary_dict2csv(translator.glossary_dict_gen))
        # Store translation segments for later use in _record_html_segments
        if hasattr(translator, 'original_texts') and hasattr(translator, 'translated_texts'):
            if task_state is not None:
                task_state["html_original_texts"] = translator.original_texts
                task_state["html_translated_texts"] = translator.translated_texts
        self.document_translated = document
        return self

    def export_to_html(self, _: ExporterConfig = None) -> str:
        docu = self._export(Html2HtmlExporter())
        html = docu.content.decode('utf-8')
        # Fix lazy-loaded images: copy data-src to src if src is empty/missing.
        # This ensures DOCX/MD exports (which rely on Pandoc/html2text reading src)
        # can embed images correctly even for convert-only workflows.
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, 'html.parser')
        for img in soup.find_all('img'):
            src = img.get('src', '').strip()
            data_src = img.get('data-src', '').strip()
            if not src and data_src:
                img['src'] = data_src
        return str(soup)

    def export_to_markdown(self, _: ExporterConfig | None = None) -> str:
        from workflow.html_to_markdown_export import html_content_to_markdown

        return html_content_to_markdown(self.export_to_html())

    def save_as_html(self, name: str = None, output_dir: Path | str = "./output",
                     _: ExporterConfig | None = None) -> Self:
        self._save(exporter=Html2HtmlExporter(), name=name, output_dir=output_dir)
        return self
