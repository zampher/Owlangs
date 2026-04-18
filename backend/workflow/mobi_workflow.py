# SPDX-FileCopyrightText: 2026 Zampherssss
# SPDX-License-Identifier: MPL-2.0
import re
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
        """Export MOBI/EPUB to Markdown format by converting from HTML."""
        html_content = self.export_to_html()
        return self._html_to_markdown(html_content)
    
    def _html_to_markdown(self, html_content: str) -> str:
        """Convert HTML content to Markdown format."""
        from bs4 import BeautifulSoup
        
        # First, clean HTML: remove style, script, and other unwanted tags
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # Remove style, script, and meta tags completely
        for tag in soup(['style', 'script', 'meta', 'link']):
            tag.decompose()
        
        # Remove title tags that contain "Untitled" or empty
        for title in soup.find_all('title'):
            if title.string and ('Untitled' in title.string or not title.string.strip()):
                title.decompose()
        
        # Try using html2text if available (better formatting)
        try:
            import html2text
            # Convert cleaned HTML back to string
            cleaned_html = str(soup)
            
            h = html2text.HTML2Text()
            h.ignore_links = False
            h.ignore_images = False
            h.body_width = 0  # Don't wrap lines
            h.unicode_snob = True  # Use unicode characters
            h.escape_snob = True  # Escape special characters
            h.single_line_break = False  # Use double line breaks for paragraphs
            h.mark_code = False  # Don't mark code blocks
            markdown = h.handle(cleaned_html)
        except ImportError:
            # Fallback: manual conversion using BeautifulSoup
            markdown = self._soup_to_markdown(soup)
        
        # Post-process: clean up the markdown
        return self._clean_markdown(markdown)
    
    def _soup_to_markdown(self, soup) -> str:
        """Convert BeautifulSoup object to Markdown manually."""
        lines = []
        
        def process_element(elem, indent=0):
            """Recursively process HTML elements to Markdown."""
            if elem.name is None:  # Text node
                text = str(elem.string) if elem.string else ''
                if text.strip():
                    lines.append(text.strip())
            elif elem.name in ('h1', 'h2', 'h3', 'h4', 'h5', 'h6'):
                level = int(elem.name[1])
                text = elem.get_text(strip=True)
                if text:
                    lines.append('#' * level + ' ' + text)
                    lines.append('')  # Add blank line after heading
            elif elem.name == 'p':
                text = elem.get_text(separator=' ', strip=True)
                if text:
                    lines.append(text)
                    lines.append('')  # Add blank line after paragraph
            elif elem.name in ('div', 'section', 'article'):
                # Process children, add blank line if content
                has_content = False
                for child in elem.children:
                    if hasattr(child, 'name') and child.name:
                        process_element(child, indent)
                        has_content = True
                    elif isinstance(child, str) and child.strip():
                        lines.append(child.strip())
                        has_content = True
                if has_content:
                    lines.append('')  # Add blank line after block
            elif elem.name == 'br':
                lines.append('')
            elif elem.name == 'img':
                alt = elem.get('alt', '')
                src = elem.get('src', '')
                if src:
                    lines.append(f'![{alt}]({src})')
            elif elem.name == 'a':
                text = elem.get_text(strip=True)
                href = elem.get('href', '')
                if text and href:
                    lines.append(f'[{text}]({href})')
                elif text:
                    lines.append(text)
            elif elem.name in ('strong', 'b'):
                text = elem.get_text(strip=True)
                if text:
                    lines.append(f'**{text}**')
            elif elem.name in ('em', 'i'):
                text = elem.get_text(strip=True)
                if text:
                    lines.append(f'*{text}*')
            elif elem.name in ('ul', 'ol'):
                items = elem.find_all('li', recursive=False)
                for i, item in enumerate(items):
                    text = item.get_text(separator=' ', strip=True)
                    if text:
                        prefix = '- ' if elem.name == 'ul' else f'{i+1}. '
                        lines.append(prefix + text)
                lines.append('')
            elif elem.name == 'li':
                # Handled by parent ul/ol
                text = elem.get_text(separator=' ', strip=True)
                if text:
                    lines.append(text)
            else:
                # For other elements, just get text
                text = elem.get_text(separator=' ', strip=True)
                if text:
                    lines.append(text)
        
        # Process body or root
        body = soup.find('body') or soup
        for child in body.children:
            if hasattr(child, 'name'):
                process_element(child)
            elif isinstance(child, str) and child.strip():
                lines.append(child.strip())
        
        return '\n'.join(lines)
    
    def _clean_markdown(self, markdown: str) -> str:
        """Clean up markdown: remove unwanted content and fix formatting."""
        lines = markdown.split('\n')
        cleaned_lines = []
        skip_blank = False
        in_css_block = False
        
        for line in lines:
            stripped = line.strip()
            
            # Skip CSS/style blocks
            if stripped.startswith('body {') or stripped.startswith('h1 {') or stripped.startswith('.epub-content'):
                in_css_block = True
                continue
            if in_css_block:
                if stripped.endswith('}') or (stripped == '' and len(cleaned_lines) > 0 and cleaned_lines[-1].strip().endswith('}')):
                    in_css_block = False
                continue
            
            # Skip "Untitled" lines
            if stripped == 'Untitled' or (stripped.startswith('Untitled') and len(stripped) < 20):
                continue
            
            # Skip lines that are just CSS properties
            if re.match(r'^\s*[a-z-]+:\s*[^;]+;\s*$', stripped):
                continue
            
            # Handle blank lines
            if stripped == '':
                if not skip_blank:
                    cleaned_lines.append('')
                    skip_blank = True
            else:
                # Remove leading/trailing whitespace but preserve internal formatting
                cleaned_line = line.rstrip()
                cleaned_lines.append(cleaned_line)
                skip_blank = False
        
        # Remove leading and trailing blank lines
        while cleaned_lines and cleaned_lines[0].strip() == '':
            cleaned_lines.pop(0)
        while cleaned_lines and cleaned_lines[-1].strip() == '':
            cleaned_lines.pop()
        
        return '\n'.join(cleaned_lines)

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

