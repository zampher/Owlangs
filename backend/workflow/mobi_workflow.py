# SPDX-FileCopyrightText: 2026 Zampherssss
# SPDX-License-Identifier: MPL-2.0
from dataclasses import dataclass
from pathlib import Path
from typing import Self, Protocol, TypeVar, runtime_checkable

from exporter.base import ExporterConfig
from exporter.mobi.mobi2mobi_exporter import Mobi2MobiExporter
from exporter.mobi.mobi2html_exporter import Mobi2HTMLExporterConfig, Mobi2HTMLExporter
from glossary.glossary import Glossary

from ir.document import Document
from translator.ai_translator.mobi_translator import MobiTranslatorConfig, MobiTranslator
from workflow.base import Workflow, WorkflowConfig
from workflow.interfaces import HTMLExportable, MDFormatsExportable
from logger.logger import LogModule

T_ExporterConfig = TypeVar("T_ExporterConfig", bound=ExporterConfig)


@runtime_checkable
class MobiExportable(Protocol[T_ExporterConfig]):
    def export_to_mobi(self, config: T_ExporterConfig | None = None) -> bytes:
        ...

    def save_as_mobi(self, name: str, output_dir: Path | str, config: T_ExporterConfig | None = None) -> Self:
        ...


@dataclass(kw_only=True)
class MobiWorkflowConfig(WorkflowConfig):
    translator_config: MobiTranslatorConfig
    html_exporter_config: Mobi2HTMLExporterConfig


class MobiWorkflow(Workflow[MobiWorkflowConfig, Document, Document], 
                   HTMLExportable[Mobi2HTMLExporterConfig],
                   MDFormatsExportable[ExporterConfig],
                   MobiExportable[ExporterConfig]):
    def __init__(self, config: MobiWorkflowConfig):
        super().__init__(config=config)
        if config.logger:
            for sub_config in [self.config.translator_config]:
                if sub_config:
                    sub_config.logger = config.logger

    def _pre_translate(self, document_original: Document):
        document = document_original.copy()
        translate_config = self.config.translator_config
        translator = MobiTranslator(translate_config)
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
        # CRITICAL: Log whether progress_callback is received in MobiWorkflow
        if progress_callback:
            if hasattr(self, 'config') and self.config.logger:
                self.config.logger.info(LogModule.WORKFLOW, f"[MOBI_WORKFLOW] translate_async: progress_callback received: {progress_callback}")
        else:
            if hasattr(self, 'config') and self.config.logger:
                self.config.logger.warning(LogModule.WORKFLOW, f"[MOBI_WORKFLOW] translate_async: progress_callback is None!")
        
        document, translator = self._pre_translate(self.document_original)
        
        # Store translator instance in workflow for token_counter access
        self.translator = translator
        
        # Set task_id and other attributes if provided (for segment recording and API logs)
        if task_id:
            translator._task_id = task_id
        if original_filename:
            translator._original_filename = original_filename
        if workflow_type:
            translator._workflow_type = workflow_type
        
        # CRITICAL: Pass progress_callback to translator.translate_async
        # This allows workflow_executor's translation_progress_callback to be called
        if hasattr(self, 'config') and self.config.logger:
            if progress_callback:
                self.config.logger.info(LogModule.WORKFLOW, f"[MOBI_WORKFLOW] Passing progress_callback to translator.translate_async: {progress_callback}")
            else:
                self.config.logger.warning(LogModule.WORKFLOW, f"[MOBI_WORKFLOW] progress_callback is None when calling translator.translate_async!")
        
        await translator.translate_async(document, progress_callback=progress_callback)
        if translator.glossary_dict_gen:
            self.attachment.add_document("glossary", Glossary.glossary_dict2csv(translator.glossary_dict_gen))
        self.document_translated = document
        return self

    def export_to_html(self, config: Mobi2HTMLExporterConfig = None) -> str:
        config = config or self.config.html_exporter_config
        docu = self._export(Mobi2HTMLExporter(config))
        return docu.content.decode()

    def export_to_markdown(self, _: ExporterConfig | None = None) -> str:
        """Export MOBI to Markdown by converting translated HTML."""
        from workflow.html_to_markdown_export import html_content_to_markdown

        return html_content_to_markdown(self.export_to_html())

    def export_to_mobi(self, _: ExporterConfig | None = None) -> bytes:
        docu = self._export(Mobi2MobiExporter())
        return docu.content

    def save_as_html(self, name: str = None, output_dir: Path | str = "./output",
                     config: Mobi2HTMLExporter | None = None) -> Self:
        config = config or self.config.html_exporter_config
        self._save(exporter=Mobi2HTMLExporter(config), name=name, output_dir=output_dir)
        return self

    def save_as_mobi(self, name: str = None, output_dir: Path | str = "./output",
                     _: ExporterConfig | None = None) -> Self:
        self._save(exporter=Mobi2MobiExporter(), name=name, output_dir=output_dir)
        return self

