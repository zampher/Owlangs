# SPDX-FileCopyrightText: 2026 Zampherss
# SPDX-License-Identifier: MPL-2.0
from dataclasses import dataclass
from pathlib import Path
from typing import Self

from exporter.base import ExporterConfig
from exporter.js.json2html_exporter import Json2HTMLExporterConfig, Json2HTMLExporter
from exporter.js.json2json_exporter import Json2JsonExporter
from glossary.glossary import Glossary
from ir.document import Document
from translator.ai_translator.json_translator import JsonTranslatorConfig, JsonTranslator
from workflow.base import Workflow, WorkflowConfig
from workflow.interfaces import HTMLExportable, JsonExportable


@dataclass(kw_only=True)
class JsonWorkflowConfig(WorkflowConfig):
    translator_config: JsonTranslatorConfig
    html_exporter_config: Json2HTMLExporterConfig


class JsonWorkflow(Workflow[JsonWorkflowConfig, Document, Document], HTMLExportable[Json2HTMLExporterConfig],
                   JsonExportable[ExporterConfig]):
    def __init__(self, config: JsonWorkflowConfig):
        super().__init__(config=config)
        if config.logger:
            for sub_config in [self.config.translator_config]:
                if sub_config:
                    sub_config.logger = config.logger

    def _pre_translate(self, document_original: Document):
        document = document_original.copy()
        translate_config = self.config.translator_config
        translator = JsonTranslator(translate_config)
        return document, translator

    def translate(self) -> Self:
        document, translator = self._pre_translate(self.document_original)
        translator.translate(document)
        if translator.glossary_dict_gen:
            self.attachment.add_document("glossary", Glossary.glossary_dict2csv(translator.glossary_dict_gen))
        self.document_translated = document
        return self

    async def translate_async(self, progress_callback=None, task_id: str = None, 
                              original_filename: str = None, workflow_type: str = None) -> Self:
        document, translator = self._pre_translate(self.document_original)
        
        # Store translator instance in workflow for token_counter access
        self.translator = translator
        
        # Set task_id and other attributes if provided (for segment recording and cached segments)
        if task_id:
            translator._task_id = task_id
        if original_filename:
            translator._original_filename = original_filename
        if workflow_type:
            translator._workflow_type = workflow_type
        if progress_callback is not None:
            translator._progress_callback = progress_callback

        await translator.translate_async(document)
        if translator.glossary_dict_gen:
            self.attachment.add_document("glossary", Glossary.glossary_dict2csv(translator.glossary_dict_gen))
        self.document_translated = document
        return self

    def export_to_html(self, config: Json2HTMLExporterConfig = None) -> str:
        config = config or self.config.html_exporter_config
        docu = self._export(Json2HTMLExporter(config))
        return docu.content.decode()

    def export_to_json(self, _: ExporterConfig | None = None) -> str:
        docu = self._export(Json2JsonExporter())
        return docu.content.decode()

    def save_as_html(self, name: str = None, output_dir: Path | str = "./output",
                     config: Json2HTMLExporter | None = None) -> Self:
        config = config or self.config.html_exporter_config
        self._save(exporter=Json2HTMLExporter(config), name=name, output_dir=output_dir)
        return self

    def save_as_json(self, name: str = None, output_dir: Path | str = "./output",
                     _: ExporterConfig | None = None) -> Self:
        self._save(exporter=Json2JsonExporter(), name=name, output_dir=output_dir)
        return self
