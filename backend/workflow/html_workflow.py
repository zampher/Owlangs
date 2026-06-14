# SPDX-FileCopyrightText: 2026 Zampherss
# SPDX-License-Identifier: MPL-2.0
from dataclasses import dataclass
from pathlib import Path
from typing import Self

from exporter.base import ExporterConfig
from exporter.html.html2html_exporter import Html2HtmlExporter
from glossary.glossary import Glossary

from ir.document import Document
from logger.logger import LogModule
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

    @staticmethod
    def _wrap_html_with_css(html_body: str) -> str:
        """Wrap HTML content in a minimal document with centering/image-friendly CSS.

        URL-fetched content has all original styles stripped during extraction.
        This adds lightweight defaults to ensure reasonable rendering offline.
        """
        return f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<style>
body {{
    max-width: 800px;
    margin: 1.5em auto;
    padding: 0 1em;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
    font-size: 16px;
    line-height: 1.6;
    color: #222;
}}
img {{
    max-width: 90%;
    height: auto;
    display: block;
    margin: 1.2em auto;
}}
p {{
    margin: 0.6em 0;
}}
h1, h2, h3, h4, h5, h6 {{
    margin: 1em 0 0.5em;
    line-height: 1.3;
}}
a {{
    color: #0066cc;
}}
table {{
    border-collapse: collapse;
    margin: 1em auto;
}}
td, th {{
    border: 1px solid #ccc;
    padding: 0.4em 0.6em;
}}
</style>
</head>
<body>
{html_body}
</body>
</html>"""

    def export_to_html(self, _: ExporterConfig = None) -> str:
        docu = self._export(Html2HtmlExporter())
        html = docu.content.decode('utf-8')
        # Fix lazy-loaded images: copy data-src to src if src is empty/missing.
        # This ensures DOCX/MD exports (which rely on Pandoc/html2text reading src)
        # can embed images correctly even for convert-only workflows.
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, 'html.parser')
        img_tags = soup.find_all('img')
        for img in img_tags:
            src = img.get('src', '').strip()
            data_src = img.get('data-src', '').strip()
            if not src and data_src:
                img['src'] = data_src
        if img_tags and self.logger:
            img_with_src = sum(1 for img in img_tags if img.get('src', '').strip())
            self.logger.info(
                LogModule.WORKFLOW,
                f"[HTML_WORKFLOW] export_to_html: {len(img_tags)} <img> tag(s), {img_with_src} with valid src"
            )
        return self._wrap_html_with_css(str(soup))

    def export_to_markdown(self, _: ExporterConfig | None = None) -> str:
        from workflow.html_to_markdown_export import html_content_to_markdown

        return html_content_to_markdown(self.export_to_html())

    def save_as_html(self, name: str = None, output_dir: Path | str = "./output",
                     _: ExporterConfig | None = None) -> Self:
        html = self.export_to_html()
        name = name or self.document_translated.name
        output_path = Path(output_dir) / Path(name).with_suffix('.html')
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(html, encoding='utf-8')
        if self.logger:
            self.logger.info(LogModule.WORKFLOW, f"File saved to {output_path.resolve()}")
        return self
