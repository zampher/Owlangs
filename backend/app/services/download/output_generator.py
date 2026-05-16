# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

"""
Output Generator Service

Handles generation of output files (HTML, MD, DOCX, PDF, PPTX, XLSX, etc.) after translation.
"""

import asyncio
import os
import re
import sys
import base64
import hashlib
import mimetypes
from typing import Any, Dict, Optional
from pathlib import Path

from logger import unified_logger as logger
from logger.logger import LogModule
from app.services.task import TaskManager


def _run_ebook_convert_sync(cmd: str, *args: str, timeout: int = 300):
    """
    Run calibre ebook-convert in a blocking way. Intended to be called via
    asyncio.to_thread() so the event loop is not blocked (conversion can take tens of seconds).
    Uses encoding='utf-8', errors='replace' to avoid UnicodeDecodeError on Windows when
    Calibre outputs non-GBK bytes to stderr/stdout.
    """
    import subprocess
    return subprocess.run(
        [cmd, *args],
        capture_output=True,
        text=True,
        timeout=timeout,
        encoding="utf-8",
        errors="replace",
    )


def _calibre_cmd_path() -> Optional[str]:
    """Return path to calibre ebook-convert if available, else None."""
    import shutil
    cmd = shutil.which("ebook-convert")
    if cmd:
        return cmd
    if os.name == "nt":
        for path in (
            r"C:\Program Files\Calibre2\ebook-convert.exe",
            r"C:\Program Files (x86)\Calibre2\ebook-convert.exe",
        ):
            if os.path.exists(path):
                return path
    # macOS: GUI/frozen app has minimal PATH; check common install locations
    if sys.platform == "darwin":
        for path in (
            "/Applications/calibre.app/Contents/MacOS/ebook-convert",
            "/Applications/Calibre.app/Contents/MacOS/ebook-convert",
            "/opt/homebrew/bin/ebook-convert",
            "/usr/local/bin/ebook-convert",
        ):
            if os.path.isfile(path) and os.access(path, os.X_OK):
                return path
    return None


def _ebook_title_from_stem(file_stem: str) -> str:
    """Build a human-readable book title from file stem for EPUB/MOBI metadata."""
    if not file_stem or not str(file_stem).strip():
        return "Untitled"
    # Replace common separators with space, collapse multiple spaces, strip
    s = str(file_stem).replace("_", " ").replace("-", " ").strip()
    while "  " in s:
        s = s.replace("  ", " ")
    return s or "Untitled"


def get_ebook_converters_availability() -> Dict[str, bool]:
    """
    Check whether Pandoc and Calibre are available for EPUB/MOBI export.
    Used by the download API so the frontend can show engine choice when both are available.
    """
    from utils.format_convert_utils import _get_pandoc_path
    pandoc_path = _get_pandoc_path()
    calibre_cmd = _calibre_cmd_path()
    return {"pandoc": pandoc_path is not None, "calibre": calibre_cmd is not None}


class OutputGenerator:
    """Service for generating output files after translation."""
    
    def __init__(self, task_manager: TaskManager):
        """
        Initialize output generator.
        
        Args:
            task_manager: Task manager instance
        """
        self.task_manager = task_manager
    
    async def generate_all_outputs(
        self,
        task_id: str,
        workflow: Any,
        payload: Any,
        task_state: Dict[str, Any],
        output_dir: Path,
        file_stem: str,
        is_format_conversion: bool = False
    ):
        """
        Generate all output files for a translation task.
        
        Args:
            task_id: Task identifier
            workflow: Workflow instance
            payload: Task payload
            task_state: Task state dictionary
            output_dir: Output directory path
            file_stem: File stem (without extension)
            is_format_conversion: Whether this is a format conversion task
        """
        logger.info(
            LogModule.EXPORT,
            f"[OUTPUT-GENERATOR] Task {task_id}: generate_all_outputs STARTED - "
            f"workflow_type={getattr(payload, 'workflow_type', None)}, "
            f"is_format_conversion={is_format_conversion}, output_dir={output_dir}, file_stem={file_stem}"
        )
        
        # Ensure output directory exists
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize downloadable_files if not exists
        if "downloadable_files" not in task_state:
            task_state["downloadable_files"] = {}
        
        workflow_type = getattr(payload, 'workflow_type', None)
        
        # OPTIMIZATION: For MOBI workflow, generate DOM from templates if delayed DOM generation was used
        if workflow_type == "mobi":
            await self._generate_mobi_with_delayed_dom(task_id, workflow, task_state, output_dir, file_stem)
        
        # Generate format-specific outputs
        # For JSON workflow, only generate HTML and JSON formats
        if workflow_type == "json":
            logger.info(LogModule.EXPORT, f"[OUTPUT-GENERATOR] Task {task_id}: Generating HTML output...")
            await self.generate_html(task_id, workflow, task_state, output_dir, file_stem)
            logger.info(LogModule.EXPORT, f"[OUTPUT-GENERATOR] Task {task_id}: Generating JSON output...")
            await self.generate_json(task_id, workflow, task_state, output_dir, file_stem)
        else:
            # For format conversion tasks, also generate HTML and DOCX (user may want to download these formats)
            # Generate HTML (for both translation and format conversion)
            logger.info(LogModule.EXPORT, f"[OUTPUT-GENERATOR] Task {task_id}: Generating HTML output...")
            await self.generate_html(task_id, workflow, task_state, output_dir, file_stem)
            
            # Generate DOCX (for both translation and format conversion)
            logger.info(LogModule.EXPORT, f"[OUTPUT-GENERATOR] Task {task_id}: Generating DOCX output...")
            await self.generate_docx(task_id, workflow, payload, task_state, output_dir, file_stem)
        
        # Generate PPTX (for PPTX workflow, both translation and format conversion)
        if workflow_type == "pptx":
            logger.info(LogModule.EXPORT, f"[OUTPUT-GENERATOR] Task {task_id}: Generating PPTX output...")
            await self.generate_pptx(task_id, workflow, task_state, output_dir, file_stem)
        
        # Generate XLSX (for XLSX workflow, both translation and format conversion)
        if workflow_type == "xlsx":
            logger.info(LogModule.EXPORT, f"[OUTPUT-GENERATOR] Task {task_id}: Generating XLSX output...")
            await self.generate_xlsx(task_id, workflow, task_state, output_dir, file_stem)
        
        # Generate MOBI (for MOBI workflow). Never from PDF; from workflow EPUB content or HTML fallback.
        if workflow_type == "mobi":
            logger.info(LogModule.EXPORT, f"[OUTPUT-GENERATOR] Task {task_id}: Generating MOBI output...")
            await self.generate_mobi(task_id, workflow, task_state, output_dir, file_stem)
        
        # Generate EPUB (for EPUB workflow). Never from PDF; from workflow content or HTML fallback.
        if workflow_type == "epub":
            logger.info(LogModule.EXPORT, f"[OUTPUT-GENERATOR] Task {task_id}: Generating EPUB output...")
            await self.generate_epub(task_id, workflow, task_state, output_dir, file_stem)
        
        # Generate additional formats (skip for JSON workflow as it's already handled above)
        if workflow_type != "json":
            logger.info(LogModule.EXPORT, f"[OUTPUT-GENERATOR] Task {task_id}: Generating additional output formats...")
            self.task_manager.add_log(task_id, "info", "Generating additional output formats...")
            
            # Generate Markdown
            await self.generate_markdown(task_id, workflow, task_state, output_dir, file_stem)
            
            # Generate TXT
            await self.generate_txt(task_id, workflow, task_state, output_dir, file_stem)
            
            # Generate JSON
            await self.generate_json(task_id, workflow, task_state, output_dir, file_stem)
        
        # Generate TS (for qt_ts workflow)
        if workflow_type == "qt_ts":
            await self.generate_ts(task_id, workflow, task_state, output_dir, file_stem)
        
        # Generate SRT (for srt workflow)
        if workflow_type == "srt":
            await self.generate_srt(task_id, workflow, task_state, output_dir, file_stem)
        
        # Generate PDF (for markdown_based workflow and MOBI/EPUB, only after translation)
        # NOTE: PDF generation for MOBI/EPUB uses HTML-to-PDF conversion which may take time
        # It's generated here so it's available when user requests download
        if workflow_type in ("markdown_based", "mobi", "epub") and hasattr(workflow, 'export_to_html') and not is_format_conversion:
            logger.info(LogModule.EXPORT, f"[OUTPUT-GENERATOR] Task {task_id}: Generating PDF output...")
            try:
                await self.generate_pdf(task_id, workflow, payload, task_state, output_dir, file_stem)
            except Exception as pdf_error:
                # Log error but don't fail entire task - PDF generation is optional
                logger.warning(LogModule.EXPORT, f"[OUTPUT-GENERATOR] Task {task_id}: PDF generation failed (non-critical): {pdf_error}", exc_info=True)
                self.task_manager.add_log(task_id, "warning", f"PDF generation failed: {str(pdf_error)}. Other files are still available.")
        
        # Log final downloadable files
        downloadable_files = list(task_state.get('downloadable_files', {}).keys())
        logger.info(
            LogModule.EXPORT,
            f"[OUTPUT-GENERATOR] Task {task_id}: generate_all_outputs COMPLETED - "
            f"Generated {len(downloadable_files)} files: {downloadable_files}",
        )
        self.task_manager.add_log(task_id, "info", f"Final downloadable files: {downloadable_files}")
        self.task_manager.add_log(task_id, "success", "Output files generated successfully")

    async def generate_output_for_file_type(
        self,
        task_id: str,
        file_type: str,
        workflow: Any,
        payload: Any,
        task_state: Dict[str, Any],
        output_dir: Path,
        file_stem: str,
        is_format_conversion: bool = False,
        ebook_engine: Optional[str] = None,
    ) -> None:
        """
        Generate only the requested output format (on-demand). Used when user downloads
        a single format so we do not generate PDF/DOCX etc. unnecessarily (avoid extra PDF
        work when only HTML is requested). ebook_engine: 'pandoc' or 'calibre' for epub/mobi only.
        """
        output_dir.mkdir(parents=True, exist_ok=True)
        if "downloadable_files" not in task_state:
            task_state["downloadable_files"] = {}

        workflow_type = getattr(payload, "workflow_type", None)

        # MOBI delayed DOM must run first so workflow has content for HTML/DOCX/PDF etc.
        if workflow_type == "mobi":
            await self._generate_mobi_with_delayed_dom(task_id, workflow, task_state, output_dir, file_stem)

        logger.info(
            LogModule.EXPORT,
            f"[OUTPUT-GENERATOR] Task {task_id}: Generating single output on-demand: file_type={file_type}, workflow_type={workflow_type}, ebook_engine={ebook_engine}",
        )

        single_generators = {
            "html": self.generate_html,
            "docx": self.generate_docx,
            "pdf": self.generate_pdf,
            "mobi": self.generate_mobi,
            "epub": self.generate_epub,
            "md": self.generate_markdown,
            "txt": self.generate_txt,
            "json": self.generate_json,
            "arb": self.generate_arb,
            "pptx": self.generate_pptx,
            "xlsx": self.generate_xlsx,
            "ts": self.generate_ts,
            "srt": self.generate_srt,
        }

        gen = single_generators.get(file_type)
        if gen is not None:
            if file_type in ("docx", "pdf"):
                await gen(task_id, workflow, payload, task_state, output_dir, file_stem)
            elif file_type == "epub":
                await gen(task_id, workflow, task_state, output_dir, file_stem, epub_engine=ebook_engine)
            elif file_type == "mobi":
                await gen(task_id, workflow, task_state, output_dir, file_stem, mobi_engine=ebook_engine)
            else:
                await gen(task_id, workflow, task_state, output_dir, file_stem)
            self.task_manager.add_log(task_id, "info", f"Generated {file_type} on-demand")
        else:
            # Unknown or unsupported file_type (e.g. csv): fall back to full generation
            logger.info(LogModule.EXPORT, f"[OUTPUT-GENERATOR] Task {task_id}: file_type={file_type} has no single generator, running generate_all_outputs")
            await self.generate_all_outputs(
                task_id, workflow, payload, task_state, output_dir, file_stem, is_format_conversion
            )

    async def _generate_mobi_with_delayed_dom(
        self,
        task_id: str,
        workflow: Any,
        task_state: Dict[str, Any],
        output_dir: Path,
        file_stem: str
    ):
        """
        Generate MOBI/EPUB file using delayed DOM generation (template-based replacement).
        This is called when translation phase skipped _after_translate for performance.
        """
        # Check if delayed DOM generation data exists
        html_templates = task_state.get('mobi_html_templates')
        segment_mapping = task_state.get('mobi_segment_mapping')
        mobi_book = task_state.get('mobi_book')
        translated_texts = task_state.get('mobi_translated_texts')
        
        if not all([html_templates, segment_mapping, mobi_book, translated_texts]):
            logger.info(
                LogModule.EXPORT,
                f"[OUTPUT-GENERATOR] Task {task_id}: Delayed DOM generation data not found, "
                f"using existing document_translated.content",
            )
            return
        
        logger.info(
            LogModule.EXPORT,
            f"[OUTPUT-GENERATOR] Task {task_id}: Generating MOBI/EPUB using delayed DOM generation "
            f"(template-based replacement), items={len(html_templates)}, segments={len(segment_mapping)}",
        )
        
        try:
            # Build translated_segments dictionary from translated_texts
            translated_segments = {
                i: translated_texts[i] if i < len(translated_texts) else ""
                for i in range(len(segment_mapping))
            }
            
            # Check for user-edited segments (from translation_segments)
            revised_segments = task_state.get('revised_segments', {})
            if revised_segments:
                logger.info(
                    LogModule.EXPORT,
                    f"[OUTPUT-GENERATOR] Task {task_id}: Found {len(revised_segments)} user-edited segments, "
                    f"applying revisions",
                )
                # Update translated_segments with user edits
                for seg_id, seg_data in revised_segments.items():
                    if isinstance(seg_data, dict):
                        target_text = seg_data.get('target_text')
                        if target_text:
                            try:
                                seg_id_int = int(seg_id)
                                translated_segments[seg_id_int] = target_text
                            except (ValueError, TypeError):
                                pass
            
            # Generate EPUB content using template-based replacement
            from translator.ai_translator.mobi_translator import MobiTranslator
            epub_content = MobiTranslator.generate_dom_from_segments_template(
                book=mobi_book,
                html_templates=html_templates,
                segment_mapping=segment_mapping,
                translated_segments=translated_segments,
                task_id=task_id,
                task_state=task_state,
            )
            
            # Update workflow's document_translated.content
            if hasattr(workflow, 'document_translated') and workflow.document_translated:
                from ir.document import Document
                # CRITICAL: Ensure epub_content is bytes
                if isinstance(epub_content, str):
                    epub_content = epub_content.encode('utf-8')
                elif not isinstance(epub_content, bytes):
                    epub_content = bytes(epub_content)
                
                workflow.document_translated = Document.from_bytes(
                    content=epub_content,
                    suffix='.epub',
                    stem=file_stem
                )
                logger.info(
                    LogModule.EXPORT,
                    f"[OUTPUT-GENERATOR] Task {task_id}: Updated workflow.document_translated.content "
                    f"with generated EPUB ({len(epub_content)} bytes), "
                    f"document_translated.content type: {type(workflow.document_translated.content).__name__}, "
                    f"document_translated.content length: {len(workflow.document_translated.content) if hasattr(workflow.document_translated, 'content') else 'N/A'}",
                )
            else:
                logger.warning(
                    LogModule.EXPORT,
                    f"[OUTPUT-GENERATOR] Task {task_id}: workflow.document_translated not found, "
                    f"cannot update content",
                )
            
            self.task_manager.add_log(task_id, "success", "MOBI/EPUB file generated using delayed DOM generation")
        except Exception as e:
            logger.error(
                LogModule.EXPORT,
                f"[OUTPUT-GENERATOR] Task {task_id}: Failed to generate MOBI/EPUB using delayed DOM generation: {e}",
                exc_info=True,
            )
            self.task_manager.add_log(task_id, "error", f"Failed to generate MOBI/EPUB: {str(e)}")
            # Don't raise - fall back to existing document_translated.content if available
    
    async def generate_html(
        self,
        task_id: str,
        workflow: Any,
        task_state: Dict[str, Any],
        output_dir: Path,
        file_stem: str
    ):
        """Generate HTML output file."""
        if not hasattr(workflow, 'save_as_html'):
            return
        
        self.task_manager.add_log(task_id, "info", "Generating HTML file using save_as_html...")
        
        # For markdown-based (PDF) workflow, rebuild with equation_format=latex so HTML gets $$...$$ for KaTeX
        workflow_type_name = getattr(workflow, '__class__', None).__name__ if hasattr(workflow, '__class__') else ""
        if "Markdown" in workflow_type_name and "Mobi" not in workflow_type_name:
            from utils.document_rebuild import rebuild_markdown_document_from_segments
            rebuilt = rebuild_markdown_document_from_segments(
                task_state,
                file_stem=file_stem,
                output_dir=output_dir,
                equation_format="latex",
                table_body_format="html",
            )
            if rebuilt is not None and hasattr(workflow, 'document_translated') and workflow.document_translated is not None:
                workflow.document_translated = rebuilt
                logger.info(LogModule.EXPORT, f"[OUTPUT-GENERATOR] Task {task_id}: Rebuilt markdown with equation_format=latex for HTML export")
        
        # For markdown-based workflows, replace image placeholders before saving HTML
        if hasattr(workflow, 'document_translated') and workflow.document_translated is not None:
            from ir.markdown_document import MarkdownDocument
            from utils.document_rebuild import _replace_placeholders_with_images
            if isinstance(workflow.document_translated, MarkdownDocument):
                # Get image_data_map from task_state
                image_data_map = (
                    task_state.get("translation_image_data_map")
                    or task_state.get("image_data_map")
                    or {}
                )
                if image_data_map:
                    # Replace placeholders with file paths (output_dir provided for saving images)
                    markdown_content = workflow.document_translated.content
                    if isinstance(markdown_content, bytes):
                        markdown_content = markdown_content.decode('utf-8')
                    elif not isinstance(markdown_content, str):
                        markdown_content = str(markdown_content)
                    
                    markdown_with_images, saved_paths = _replace_placeholders_with_images(
                        markdown_content, image_data_map, output_dir=output_dir  # Save images as files
                    )
                    
                    # Temporarily update document_translated content with replaced placeholders
                    workflow.document_translated = MarkdownDocument.from_bytes(
                        content=markdown_with_images.encode('utf-8'),
                        suffix=workflow.document_translated.suffix,
                        stem=workflow.document_translated.stem
                    )
                    if saved_paths:
                        logger.info(LogModule.EXPORT, f"[OUTPUT-GENERATOR] Task {task_id}: Replaced {len(image_data_map)} image placeholders, saved {len(saved_paths)} images to {output_dir / 'images'}")
        
        # Use local resources (cdn=False) to avoid CSP issues in iframe preview
        original_config = None
        if hasattr(workflow, 'config') and hasattr(workflow.config, 'html_exporter_config'):
            # Handle different workflow types
            workflow_type = getattr(workflow, '__class__', None).__name__ if hasattr(workflow, '__class__') else None
            is_mobi_workflow = 'Mobi' in str(type(workflow).__name__) if hasattr(workflow, '__class__') else False
            
            if is_mobi_workflow:
                # MOBI workflow uses Mobi2HTMLExporterConfig
                from exporter.mobi.mobi2html_exporter import Mobi2HTMLExporterConfig
                original_config = workflow.config.html_exporter_config
                # Get image_data_map from task_state for fallback image lookup
                image_data_map = (
                    task_state.get("mobi_image_data_map")
                    or task_state.get("image_data_map")
                    or {}
                )
                workflow.config.html_exporter_config = Mobi2HTMLExporterConfig(
                    cdn=False,
                    image_data_map=image_data_map
                )
                logger.info(
                    LogModule.EXPORT,
                    f"[OUTPUT-GENERATOR] Task {task_id}: Using local resources (cdn=False) for MOBI HTML save, "
                    f"with {len(image_data_map)} images from task_state for fallback lookup"
                )
            else:
                # Markdown-based workflow uses MD2HTMLExporterConfig
                from exporter.md.md2html_exporter import MD2HTMLExporterConfig
                from app.services.download.download_service import _get_image_layout_for_grouping
                original_config = workflow.config.html_exporter_config
                original_filename = task_state.get("original_filename", "")
                is_pdf_source = original_filename.lower().endswith('.pdf')
                _img_bidx, _path_to_bidx, _layout = _get_image_layout_for_grouping(task_state)
                workflow.config.html_exporter_config = MD2HTMLExporterConfig(
                    cdn=False,
                    preserve_line_breaks=is_pdf_source,
                    layout_block_bbox=task_state.get("layout_block_bbox"),
                    image_block_indices=_img_bidx,
                    layout_document=_layout if _img_bidx else None,
                )
                logger.info(LogModule.EXPORT, f"[OUTPUT-GENERATOR] Task {task_id}: Using local resources (cdn=False) for HTML save to avoid CSP issues")
        
        try:
            html_file = output_dir / f"{file_stem}_translated.html"
            # Pass filename with .html extension to ensure correct file is saved
            workflow.save_as_html(f"{file_stem}_translated.html", output_dir)
            
            if html_file.exists():
                task_state["downloadable_files"]["html"] = {
                    "path": str(html_file),
                    "filename": f"{file_stem}_translated.html"
                }
                self.task_manager.add_log(task_id, "success", f"HTML file generated: {html_file}")
            else:
                self.task_manager.add_log(task_id, "error", f"HTML file not found after generation: {html_file}")
        finally:
            # Restore original config
            if original_config is not None:
                workflow.config.html_exporter_config = original_config
    
    def _find_ebook_convert_cmd(self) -> Optional[str]:
        """Find calibre ebook-convert executable. Returns path or None."""
        return _calibre_cmd_path()

    def _generate_epub_via_pandoc_sync(
        self,
        task_id: str,
        task_state: Dict[str, Any],
        output_dir: Path,
        file_stem: str,
    ) -> Optional[Path]:
        """
        Generate EPUB from segments via Pandoc (MD -> EPUB). Blocking; call via asyncio.to_thread.
        Returns path to generated .epub or None on failure.
        """
        import subprocess
        from utils.format_convert_utils import _get_pandoc_path
        from utils.document_rebuild import rebuild_markdown_document_from_segments

        pandoc_path = _get_pandoc_path()
        if not pandoc_path:
            logger.warning(LogModule.EXPORT, "[OUTPUT-GENERATOR] Pandoc not found, cannot use pandoc EPUB path")
            return None

        rebuilt = rebuild_markdown_document_from_segments(
            task_state, file_stem=file_stem, output_dir=output_dir
        )
        if not rebuilt or not getattr(rebuilt, "content", None):
            logger.warning(LogModule.EXPORT, f"[OUTPUT-GENERATOR] Task {task_id}: No markdown content from segments for Pandoc EPUB")
            return None

        raw = rebuilt.content
        md_content = raw.decode("utf-8") if isinstance(raw, bytes) else (raw if isinstance(raw, str) else str(raw))
        # Replace image placeholders with saved image files so EPUB contains images
        image_data_map = (
            task_state.get("mobi_image_data_map")
            or task_state.get("translation_image_data_map")
            or task_state.get("image_data_map")
            or {}
        )
        if image_data_map:
            from utils.document_rebuild import _replace_placeholders_with_images
            md_content, saved_paths = _replace_placeholders_with_images(
                md_content, dict(image_data_map), output_dir=output_dir
            )
            if saved_paths:
                logger.info(LogModule.EXPORT, f"[OUTPUT-GENERATOR] Task {task_id}: Replaced {len(saved_paths)} image placeholders for Pandoc EPUB")
        md_file = output_dir / f"{file_stem}_translated.md"
        epub_file = output_dir / f"{file_stem}_translated.epub"
        try:
            md_file.write_text(md_content, encoding="utf-8")
        except Exception as e:
            logger.error(LogModule.EXPORT, f"[OUTPUT-GENERATOR] Task {task_id}: Failed to write MD for Pandoc: {e}", exc_info=True)
            return None

        ebook_meta = task_state.get("ebook_metadata") or {}
        title = (ebook_meta.get("title") or "").strip() or _ebook_title_from_stem(file_stem)
        author = (ebook_meta.get("author") or "").strip() or None
        cmd = str(pandoc_path)
        args = [str(md_file), "-o", str(epub_file), "--metadata", f"title={title}"]
        if author:
            args.append("--metadata")
            args.append(f"author={author}")
        for key, pandoc_key in (("language", "lang"), ("publisher", "publisher"), ("description", "description"), ("subject", "subject"), ("date", "date"), ("rights", "rights")):
            val = (ebook_meta.get(key) or "").strip()
            if val:
                args.append("--metadata")
                args.append(f"{pandoc_key}={val}")
        try:
            result = subprocess.run(
                [cmd] + args,
                capture_output=True,
                text=True,
                timeout=300,
                encoding="utf-8",
                errors="replace",
                cwd=str(output_dir),
            )
        except subprocess.TimeoutExpired:
            logger.warning(LogModule.EXPORT, f"[OUTPUT-GENERATOR] Task {task_id}: Pandoc EPUB conversion timed out")
            return None
        except Exception as e:
            logger.error(LogModule.EXPORT, f"[OUTPUT-GENERATOR] Task {task_id}: Pandoc EPUB failed: {e}", exc_info=True)
            return None

        if result.returncode != 0 or not epub_file.exists() or epub_file.stat().st_size == 0:
            logger.warning(
                LogModule.EXPORT,
                f"[OUTPUT-GENERATOR] Task {task_id}: Pandoc EPUB failed returncode={result.returncode} stderr={result.stderr!r}",
            )
            return None
        return epub_file
    
    def _generate_ebook_from_html(
        self,
        task_id: str,
        output_dir: Path,
        file_stem: str,
        target_ext: str,
        task_state: Dict[str, Any],
    ) -> Optional[Path]:
        """
        Generate EPUB or MOBI from the translated HTML file using calibre ebook-convert.
        Policy: EPUB/MOBI must NOT be generated from PDF; this fallback uses HTML only.
        Returns path to generated file or None.
        """
        html_file = output_dir / f"{file_stem}_translated.html"
        if not html_file.exists() or html_file.stat().st_size == 0:
            logger.debug(
                LogModule.EXPORT,
                f"[OUTPUT-GENERATOR] Task {task_id}: HTML file missing or empty, cannot generate {target_ext} from HTML",
            )
            return None
        cmd = self._find_ebook_convert_cmd()
        if not cmd:
            logger.debug(
                LogModule.EXPORT,
                f"[OUTPUT-GENERATOR] Task {task_id}: ebook-convert not found, cannot generate {target_ext} from HTML",
            )
            return None
        import subprocess
        out_file = output_dir / f"{file_stem}_translated.{target_ext}"
        ebook_meta = task_state.get("ebook_metadata") or {}
        title = (ebook_meta.get("title") or "").strip() or _ebook_title_from_stem(file_stem)
        author = (ebook_meta.get("author") or "").strip()
        ebook_args = [str(html_file), str(out_file), "--title", title]
        if author:
            ebook_args.extend(["--authors", author])
        # Preserve other metadata when calibre supports them (--publisher, --language, etc.)
        pub = (ebook_meta.get("publisher") or "").strip()
        if pub:
            ebook_args.extend(["--publisher", pub])
        lang = (ebook_meta.get("language") or "").strip()
        if lang:
            ebook_args.extend(["--language", lang])
        if target_ext.lower() == "epub":
            # Allow Calibre to split on page breaks and add default cover (with title/author)
            pass
        elif target_ext.lower() == "mobi":
            ebook_args.append("--dont-compress")  # Slightly faster, optional
        try:
            logger.info(
                LogModule.EXPORT,
                f"[OUTPUT-GENERATOR] Task {task_id}: Generating {target_ext.upper()} from HTML (not from PDF): {html_file} -> {out_file}",
            )
            self.task_manager.add_log(
                task_id, "info",
                f"Generating {target_ext.upper()} from translated HTML (calibre)..."
            )
            # subprocess.run is blocking; _generate_ebook_from_html is only called from async
            # code via asyncio.to_thread(), so the blocking happens in a worker thread.
            # encoding/errors avoid UnicodeDecodeError on Windows when Calibre outputs non-GBK.
            result = subprocess.run(
                [cmd] + ebook_args,
                capture_output=True,
                text=True,
                timeout=300,
                encoding="utf-8",
                errors="replace",
            )
            if result.returncode == 0 and out_file.exists() and out_file.stat().st_size > 0:
                logger.info(
                    LogModule.EXPORT,
                    f"[OUTPUT-GENERATOR] Task {task_id}: Generated {target_ext.upper()} from HTML: {out_file} ({out_file.stat().st_size} bytes)",
                )
                return out_file
            logger.warning(
                LogModule.EXPORT,
                f"[OUTPUT-GENERATOR] Task {task_id}: ebook-convert failed for HTML->{target_ext}: returncode={result.returncode}, stderr={result.stderr[:300] if result.stderr else 'none'}",
            )
        except Exception as e:
            logger.warning(
                LogModule.EXPORT,
                f"[OUTPUT-GENERATOR] Task {task_id}: Failed to generate {target_ext} from HTML: {e}",
                exc_info=False,
            )
        return None
    
    async def generate_docx(
        self,
        task_id: str,
        workflow: Any,
        payload: Any,
        task_state: Dict[str, Any],
        output_dir: Path,
        file_stem: str
    ):
        """Generate DOCX output file."""
        self.task_manager.add_log(task_id, "info", f"Checking DOCX export for workflow type: {getattr(payload, 'workflow_type', 'unknown')}")
        self.task_manager.add_log(task_id, "info", f"Workflow class: {type(workflow).__name__}")
        self.task_manager.add_log(task_id, "info", f"Has save_as_docx: {hasattr(workflow, 'save_as_docx')}")
        self.task_manager.add_log(task_id, "info", f"Has export_to_docx: {hasattr(workflow, 'export_to_docx')}")
        
        # Resolve target language and font for DOCX (used by MD2DOCX and HTML-to-DOCX)
        to_lang = None
        if payload:
            to_lang = (payload.get("to_lang") or payload.get("target_language")) if isinstance(payload, dict) else (getattr(payload, "to_lang", None) or getattr(payload, "target_language", None))
        if not to_lang and task_state:
            to_lang = task_state.get("to_lang") or task_state.get("target_language")
        try:
            from translator.ai_translator.docx_translator import get_font_for_language
            docx_font_name = get_font_for_language(to_lang) if to_lang else "Calibri"
        except Exception:
            docx_font_name = "Calibri"

        # Pandoc-first: only for markdown_based workflow (e.g. PDF); other workflows keep existing DOCX path
        workflow_type = getattr(payload, "workflow_type", None) if payload else None
        if not workflow_type and task_state:
            workflow_type = task_state.get("workflow_type")
        docx_file = output_dir / f"{file_stem}_translated.docx"
        if workflow_type == "markdown_based" and hasattr(workflow, "export_to_markdown"):
            md_content = None
            docx_font_lang = to_lang  # default: target language (translated content)
            # For PDF (layout) workflow: prefer rebuild with equation_format=image and table_body_format=image
            # so that DOCX contains formula and table images. export_to_markdown() yields text/html by default and no images.
            layout_doc = task_state.get("layout_document")
            original_filename = task_state.get("original_filename", "")
            is_pdf_with_layout = original_filename.lower().endswith(".pdf") and layout_doc is not None
            if is_pdf_with_layout:
                try:
                    from utils.document_rebuild import rebuild_markdown_document_from_segments
                    eq_fmt = task_state.get("equation_format") or (payload.get("equation_format") if isinstance(payload, dict) else getattr(payload, "equation_format", None)) or "image"
                    tbl_fmt = task_state.get("table_body_format") or (payload.get("table_body_format") if isinstance(payload, dict) else getattr(payload, "table_body_format", None)) or "image"
                    rebuilt_doc = rebuild_markdown_document_from_segments(
                        task_state,
                        file_stem=file_stem,
                        output_dir=output_dir,
                        equation_format=eq_fmt,
                        table_body_format=tbl_fmt,
                    )
                    if rebuilt_doc and hasattr(rebuilt_doc, "content"):
                        raw = rebuilt_doc.content
                        md_content = raw.decode("utf-8") if isinstance(raw, bytes) else (raw if isinstance(raw, str) else str(raw))
                        docx_font_lang = (
                            task_state.get("detected_language")
                            or (payload.get("from_lang") if isinstance(payload, dict) else getattr(payload, "from_lang", None))
                            or to_lang
                        )
                        logger.info(
                            LogModule.EXPORT,
                            f"[OUTPUT-GENERATOR] Task {task_id}: Rebuilt Markdown from segments for Pandoc DOCX "
                            f"(equation_format={eq_fmt}, table_body_format={tbl_fmt}) so images are included",
                        )
                        self.task_manager.add_log(task_id, "info", f"Rebuilt Markdown from segments for Pandoc DOCX (equation_format={eq_fmt}, table_body_format={tbl_fmt})")
                except Exception as rebuild_err:
                    logger.debug(LogModule.EXPORT, f"[OUTPUT-GENERATOR] Task {task_id}: rebuild from segments failed: {rebuild_err}")
            if md_content is None:
                try:
                    md_content = workflow.export_to_markdown()
                except Exception as e:
                    logger.info(LogModule.EXPORT, f"[OUTPUT-GENERATOR] Task {task_id}: workflow.export_to_markdown failed ({e}), trying rebuild from segments for Pandoc DOCX")
                    try:
                        from utils.document_rebuild import rebuild_markdown_document_from_segments
                        eq_fmt = task_state.get("equation_format") or (payload.get("equation_format") if isinstance(payload, dict) else getattr(payload, "equation_format", None)) or "text"
                        tbl_fmt = task_state.get("table_body_format") or (payload.get("table_body_format") if isinstance(payload, dict) else getattr(payload, "table_body_format", None)) or "html"
                        rebuilt_doc = rebuild_markdown_document_from_segments(
                            task_state,
                            file_stem=file_stem,
                            output_dir=output_dir,
                            equation_format=eq_fmt,
                            table_body_format=tbl_fmt,
                        )
                        if rebuilt_doc and hasattr(rebuilt_doc, "content"):
                            raw = rebuilt_doc.content
                            md_content = raw.decode("utf-8") if isinstance(raw, bytes) else (raw if isinstance(raw, str) else str(raw))
                            docx_font_lang = (
                                task_state.get("detected_language")
                                or (payload.get("from_lang") if isinstance(payload, dict) else getattr(payload, "from_lang", None))
                                or to_lang
                            )
                            self.task_manager.add_log(task_id, "info", f"Rebuilt Markdown from segments for Pandoc DOCX (equation_format={eq_fmt}, font by lang={docx_font_lang})")
                    except Exception as rebuild_err:
                        logger.debug(LogModule.EXPORT, f"[OUTPUT-GENERATOR] Task {task_id}: rebuild from segments failed: {rebuild_err}")
            if md_content:
                try:
                    from utils.format_convert_utils import convert_md_to_docx
                    if convert_md_to_docx(md_content, str(docx_file), output_dir=output_dir, to_lang=docx_font_lang):
                        if docx_file.exists():
                            if "downloadable_files" not in task_state:
                                task_state["downloadable_files"] = {}
                            task_state["downloadable_files"]["docx"] = {
                                "path": str(docx_file),
                                "filename": f"{file_stem}_translated.docx",
                            }
                            self.task_manager.add_log(task_id, "success", "DOCX file generated via Pandoc (formulas preserved).")
                            try:
                                from utils.docx_math_fragment_check import (
                                    apply_docx_math_fragment_issues_to_task_state,
                                )

                                frag_summary = apply_docx_math_fragment_issues_to_task_state(
                                    task_state,
                                    task_id=task_id,
                                    task_manager=self.task_manager,
                                )
                                logger.info(
                                    LogModule.EXPORT,
                                    f"[OUTPUT-GENERATOR] Task {task_id}: DOCX fragment math check "
                                    f"segments={frag_summary.checked_segments} issues={len(frag_summary.issues)}",
                                )
                            except Exception as frag_err:
                                logger.warning(
                                    LogModule.EXPORT,
                                    f"[OUTPUT-GENERATOR] Task {task_id}: DOCX fragment math check failed: {frag_err}",
                                    exc_info=False,
                                )
                            return
                        self.task_manager.add_log(task_id, "info", "Pandoc DOCX output missing, falling back to export_to_docx/save_as_docx.")
                except Exception as pandoc_err:
                    logger.info(LogModule.EXPORT, f"[OUTPUT-GENERATOR] Task {task_id}: Pandoc DOCX attempt failed, fallback: {pandoc_err}")
                    self.task_manager.add_log(task_id, "info", f"Pandoc DOCX skipped ({pandoc_err}), using export_to_docx/save_as_docx.")
            else:
                logger.info(LogModule.EXPORT, f"[OUTPUT-GENERATOR] Task {task_id}: No markdown content for Pandoc, using export_to_docx/save_as_docx.")

        # Prefer export_to_docx over save_as_docx to avoid encoding issues
        if hasattr(workflow, 'export_to_docx'):
            self.task_manager.add_log(task_id, "info", "Generating DOCX file using export_to_docx...")
            try:
                # For PDF files, use layout-based DOCX export
                original_filename = task_state.get("original_filename", "")
                is_pdf_file = original_filename.lower().endswith('.pdf')
                layout_doc = task_state.get("layout_document")
                docx_content = None
                
                if is_pdf_file and layout_doc is not None:
                    try:
                        from layout.base import LayoutDocument as _LD
                        if isinstance(layout_doc, _LD):
                            from exporter.md.md2docx_exporter import MD2DOCXExporterConfig
                            # For PDF workflow, respect table_body_format and equation_format
                            table_body_format = task_state.get("table_body_format") or "html"
                            if table_body_format not in ("html", "image"):
                                table_body_format = "html"
                            equation_format = task_state.get("equation_format") or "text"
                            if equation_format not in ("text", "latex", "image"):
                                equation_format = "text"
                            docx_config = MD2DOCXExporterConfig(
                                layout_document=layout_doc,
                                table_body_format=table_body_format,
                                equation_format=equation_format,
                                debug_output_dir=output_dir / "debug",
                            )
                            docx_content = workflow.export_to_docx(config=docx_config)
                            self.task_manager.add_log(
                                task_id,
                                "success",
                                f"Generated DOCX using layout-based export for PDF file "
                                f"(formulas supported, table_body_format={table_body_format})",
                            )
                    except Exception as e:
                        self.task_manager.add_log(task_id, "warning", f"Layout-based DOCX export failed: {str(e)}, falling back to default")
                
                # Fallback to default export if layout-based export failed or not applicable
                if docx_content is None:
                    docx_content = workflow.export_to_docx()
                
                docx_file = output_dir / f"{file_stem}_translated.docx"
                with open(docx_file, 'wb') as f:
                    f.write(docx_content)
                if docx_file.exists():
                    task_state["downloadable_files"]["docx"] = {
                        "path": str(docx_file),
                        "filename": f"{file_stem}_translated.docx"
                    }
                    self.task_manager.add_log(task_id, "success", f"DOCX file generated: {docx_file}")
                else:
                    self.task_manager.add_log(task_id, "error", f"DOCX file not found after generation: {docx_file}")
            except Exception as e:
                import traceback
                error_trace = traceback.format_exc()
                self.task_manager.add_log(task_id, "error", f"Error generating DOCX with export_to_docx: {str(e)}")
                self.task_manager.add_log(task_id, "error", f"Error traceback: {error_trace}")
        elif hasattr(workflow, 'save_as_docx'):
            self.task_manager.add_log(task_id, "info", "Generating DOCX file using save_as_docx (fallback)...")
            docx_file = output_dir / f"{file_stem}_translated.docx"
            try:
                # For PDF files, use layout-based DOCX export
                original_filename = task_state.get("original_filename", "")
                is_pdf_file = original_filename.lower().endswith('.pdf')
                layout_doc = task_state.get("layout_document")
                docx_config = None
                
                if is_pdf_file and layout_doc is not None:
                    try:
                        from layout.base import LayoutDocument as _LD
                        if isinstance(layout_doc, _LD):
                            from exporter.md.md2docx_exporter import MD2DOCXExporterConfig
                            table_body_format = task_state.get("table_body_format") or "html"
                            if table_body_format not in ("html", "image"):
                                table_body_format = "html"
                            docx_config = MD2DOCXExporterConfig(
                                layout_document=layout_doc,
                                table_body_format=table_body_format,
                                font_name=docx_font_name,
                                debug_output_dir=output_dir / "debug",
                            )
                            self.task_manager.add_log(
                                task_id,
                                "info",
                                f"Using layout-based DOCX export for PDF file "
                                f"(formulas supported, table_body_format={table_body_format})",
                            )
                    except Exception as e:
                        self.task_manager.add_log(task_id, "warning", f"Failed to create layout-based config: {str(e)}, using default")
                
                workflow.save_as_docx(f"{file_stem}_translated.docx", output_dir, config=docx_config)
                if docx_file.exists():
                    task_state["downloadable_files"]["docx"] = {
                        "path": str(docx_file),
                        "filename": f"{file_stem}_translated.docx"
                    }
                    self.task_manager.add_log(task_id, "success", f"DOCX file generated: {docx_file}")
                else:
                    self.task_manager.add_log(task_id, "error", f"DOCX file not found after generation: {docx_file}")
            except Exception as e:
                import traceback
                error_trace = traceback.format_exc()
                self.task_manager.add_log(task_id, "error", f"Error generating DOCX with save_as_docx: {str(e)}")
                self.task_manager.add_log(task_id, "error", f"Error traceback: {error_trace}")
        else:
            # Fallback: For TXT/HTML/MOBI/EPUB workflows, convert from HTML or MD directly (preserves format and images)
            workflow_type = getattr(payload, 'workflow_type', None)
            if workflow_type in ("txt", "html", "mobi", "epub"):
                workflow_name = "TXT" if workflow_type == "txt" else "MOBI/EPUB"
                self.task_manager.add_log(task_id, "info", f"[DOCX-EXPORT] {workflow_name} workflow: Converting to DOCX from HTML or MD (preserves format and images)...")
                try:
                    # Priority 1: Convert HTML directly to DOCX using Pandoc (best quality, preserves format and images)
                    if hasattr(workflow, 'export_to_html'):
                        self.task_manager.add_log(task_id, "info", "[DOCX-EXPORT] Workflow has export_to_html method, will use HTML-to-DOCX conversion")
                        # CRITICAL: For MOBI workflow, ensure html_exporter_config has image_data_map
                        # This is needed for workflow.export_to_html() to find images
                        if workflow_type == "mobi" and hasattr(workflow, 'config') and hasattr(workflow.config, 'html_exporter_config'):
                            from exporter.mobi.mobi2html_exporter import Mobi2HTMLExporterConfig
                            # Get image_data_map from task_state
                            image_data_map_for_html = (
                                task_state.get("image_data_map")
                                or task_state.get("translation_image_data_map")
                                or task_state.get("mobi_image_data_map")
                                or {}
                            )
                            workflow.config.html_exporter_config = Mobi2HTMLExporterConfig(
                                cdn=False,
                                image_data_map=image_data_map_for_html
                            )
                            self.task_manager.add_log(task_id, "info", f"Set image_data_map for MOBI HTML export: {len(image_data_map_for_html)} images")
                        # For TXT workflow, ensure html_exporter_config uses local resources (cdn=False) for DOCX conversion
                        elif workflow_type == "txt" and hasattr(workflow, 'config') and hasattr(workflow.config, 'html_exporter_config'):
                            from exporter.txt.txt2html_exporter import TXT2HTMLExporterConfig
                            workflow.config.html_exporter_config = TXT2HTMLExporterConfig(cdn=False)
                            self.task_manager.add_log(task_id, "info", "[DOCX-EXPORT] Set TXT HTML exporter config with cdn=False for DOCX conversion")
                        
                        html_content = workflow.export_to_html()
                        if html_content:
                            self.task_manager.add_log(task_id, "info", f"[DOCX-EXPORT] HTML content generated, length: {len(html_content)} chars")
                            # Convert HTML directly to DOCX using Pandoc (preserves format and images)
                            from utils.document_rebuild import convert_html_to_docx
                            docx_file = output_dir / f"{file_stem}_translated.docx"
                            try:
                                self.task_manager.add_log(task_id, "info", f"[DOCX-EXPORT] DOCX export font: to_lang={to_lang!r}, font_name={docx_font_name}")
                                logger.info(
                                    LogModule.EXPORT,
                                    f"[OUTPUT-GENERATOR] Task {task_id}: [DOCX-EXPORT] DOCX export font: to_lang={to_lang!r}, font_name={docx_font_name}"
                                )
                                self.task_manager.add_log(task_id, "info", f"[DOCX-EXPORT] Calling convert_html_to_docx with output_dir: {output_dir}")
                                # Pass output_dir and to_lang so font is applied by language
                                convert_html_to_docx(html_content, str(docx_file), output_dir=output_dir, to_lang=to_lang)
                                if docx_file.exists():
                                    task_state["downloadable_files"]["docx"] = {
                                        "path": str(docx_file),
                                        "filename": f"{file_stem}_translated.docx"
                                    }
                                    self.task_manager.add_log(task_id, "success", f"[DOCX-EXPORT] DOCX file generated from HTML via Pandoc: {docx_file}")
                                    return
                                else:
                                    self.task_manager.add_log(task_id, "error", f"[DOCX-EXPORT] DOCX file not found after Pandoc conversion: {docx_file}")
                            except Exception as pandoc_error:
                                import traceback
                                error_trace = traceback.format_exc()
                                self.task_manager.add_log(task_id, "warning", f"[DOCX-EXPORT] Pandoc HTML-to-DOCX conversion failed: {str(pandoc_error)}")
                                self.task_manager.add_log(task_id, "warning", f"[DOCX-EXPORT] Error traceback: {error_trace}")
                                # Continue to fallback Markdown conversion
                        else:
                            self.task_manager.add_log(task_id, "warning", "[DOCX-EXPORT] HTML content is empty, cannot convert to DOCX")
                    else:
                        self.task_manager.add_log(task_id, "warning", "[DOCX-EXPORT] Workflow does not have export_to_html method")
                    
                    # Priority 2: Fallback to Markdown conversion (if HTML-to-DOCX failed)
                    markdown_content = None
                    
                    # Try to rebuild from segments (preserves original format and images)
                    segments_data = task_state.get("translation_segments")
                    if segments_data and segments_data.get("segments"):
                        try:
                            from utils.document_rebuild import rebuild_markdown_document_from_segments
                            rebuilt_doc = rebuild_markdown_document_from_segments(
                                task_state,
                                file_stem=file_stem,
                                output_dir=output_dir
                            )
                            if rebuilt_doc and hasattr(rebuilt_doc, 'content'):
                                if isinstance(rebuilt_doc.content, bytes):
                                    markdown_content = rebuilt_doc.content.decode('utf-8')
                                else:
                                    markdown_content = rebuilt_doc.content
                                self.task_manager.add_log(task_id, "info", "Rebuilt Markdown from segments for DOCX conversion (fallback)")
                        except Exception as e:
                            self.task_manager.add_log(task_id, "warning", f"Could not rebuild Markdown from segments: {str(e)}")
                    
                    # Convert Markdown to DOCX (fallback)
                    if markdown_content:
                        from exporter.md.md2docx_exporter import MD2DOCXExporter, MD2DOCXExporterConfig
                        from ir.markdown_document import MarkdownDocument
                        
                        # Get image_data_map for DOCX export
                        # CRITICAL: rebuild_markdown_document_from_segments updates task_state["image_data_map"]
                        # with file paths (e.g., "./images/xxx.jpg"). We need to use the updated version.
                        # Priority: Use updated image_data_map from rebuild (if markdown was rebuilt),
                        # otherwise fall back to translation_image_data_map or image_data_map
                        was_rebuilt = markdown_content and segments_data and segments_data.get("segments")
                        if was_rebuilt:
                            # Markdown was rebuilt from segments, so use the updated image_data_map
                            # which includes file paths added by _replace_placeholders_with_images
                            image_data_map = task_state.get("image_data_map") or {}
                            self.task_manager.add_log(task_id, "info", f"DOCX export: Using rebuilt image_data_map with {len(image_data_map)} keys")
                            # Also merge with translation_image_data_map to ensure we have all original images
                            translation_image_data_map = task_state.get("translation_image_data_map") or {}
                            if translation_image_data_map:
                                # Merge: file paths from rebuild take precedence, but add missing originals
                                merged_count = 0
                                for key, value in translation_image_data_map.items():
                                    if key not in image_data_map:
                                        image_data_map[key] = value
                                        merged_count += 1
                                if merged_count > 0:
                                    self.task_manager.add_log(task_id, "info", f"DOCX export: Merged {merged_count} keys from translation_image_data_map")
                        else:
                            # Markdown was not rebuilt, use original image_data_map
                            image_data_map = (
                                task_state.get("translation_image_data_map")
                                or task_state.get("image_data_map")
                                or {}
                            )
                            self.task_manager.add_log(task_id, "info", f"DOCX export: Using original image_data_map with {len(image_data_map)} keys")
                        
                        # Log image_data_map keys for debugging
                        if image_data_map:
                            sample_keys = list(image_data_map.keys())[:10]
                            self.task_manager.add_log(task_id, "info", f"DOCX export: image_data_map has {len(image_data_map)} keys, sample: {sample_keys}")
                            # Check if markdown contains image references
                            import re
                            image_refs_in_md = re.findall(r'!\[([^\]]*)\]\(([^)]+)\)', markdown_content)
                            if image_refs_in_md:
                                self.task_manager.add_log(task_id, "info", f"DOCX export: Found {len(image_refs_in_md)} image references in markdown, sample: {image_refs_in_md[:3]}")
                                # Check if image references match image_data_map keys
                                for alt, ref in image_refs_in_md[:5]:
                                    if ref in image_data_map:
                                        self.task_manager.add_log(task_id, "info", f"DOCX export: Image reference '{ref}' found in image_data_map")
                                    else:
                                        # Try to find by filename
                                        ref_filename = ref.split('/')[-1].split('\\')[-1]
                                        found_by_filename = any(ref_filename in key for key in image_data_map.keys())
                                        if found_by_filename:
                                            matching_keys = [k for k in image_data_map.keys() if ref_filename in k]
                                            self.task_manager.add_log(task_id, "warning", f"DOCX export: Image reference '{ref}' NOT found directly, but found by filename in keys: {matching_keys[:3]}")
                                        else:
                                            self.task_manager.add_log(task_id, "warning", f"DOCX export: Image reference '{ref}' NOT found in image_data_map (filename: {ref_filename})")
                            else:
                                self.task_manager.add_log(task_id, "warning", "DOCX export: No image references found in markdown content")
                        else:
                            self.task_manager.add_log(task_id, "warning", "DOCX export: image_data_map is empty!")
                        
                        # ROOT CAUSE FIX: Rebuilt markdown can contain path refs (./images/xxx) from segment cache
                        # (saved from a previous export). image_data_map is keyed by layout filenames/placeholder IDs,
                        # so path-based keys are missing. Fill from output_dir for refs in markdown that are missing.
                        if markdown_content and image_data_map is not None:
                            import re as _re
                            import base64
                            import mimetypes
                            _img_refs = _re.findall(r'!\[([^\]]*)\]\(([^)]+)\)', markdown_content)
                            _filled = 0
                            for _alt, _ref in _img_refs:
                                if _ref in image_data_map or _ref.startswith("data:"):
                                    continue
                                # Ref looks like ./images/xxx.jpg or images/xxx.jpg
                                _norm = _ref.replace("\\", "/").lstrip("./")
                                _path = output_dir / _norm
                                if not _path.is_file():
                                    _fname = _norm.split("/")[-1]
                                    _path = output_dir / "images" / _fname
                                if _path.is_file():
                                    try:
                                        _raw = _path.read_bytes()
                                        _mime = mimetypes.guess_type(str(_path))[0] or "image/png"
                                        _data_uri = f"data:{_mime};base64,{base64.b64encode(_raw).decode('ascii')}"
                                        image_data_map[_ref] = {"data": _data_uri, "alt": _alt or _path.name}
                                        if _ref != _path.name and _path.name not in image_data_map:
                                            image_data_map[_path.name] = image_data_map[_ref]
                                        _filled += 1
                                    except Exception as _e:
                                        logger.debug(LogModule.EXPORT, f"[DOCX-IMAGE] Fallback read image failed: {_path}: {_e}")
                            if _filled:
                                logger.info(LogModule.EXPORT, f"[DOCX-IMAGE] Filled {_filled} image refs from output_dir for DOCX export")
                        
                        # If markdown was rebuilt from segments, image_data_map may have been updated
                        # with file paths. We need to ensure it's passed to DOCX exporter.
                        # Create MD2DOCXExporterConfig with image_data_map and font by target language
                        docx_config = MD2DOCXExporterConfig(
                            image_data_map=image_data_map,
                            font_name=docx_font_name,
                            debug_output_dir=output_dir / "debug",
                        )
                        exporter = MD2DOCXExporter(docx_config)
                        
                        # Create MarkdownDocument from content
                        md_doc = MarkdownDocument.from_bytes(
                            content=markdown_content.encode('utf-8'),
                            suffix='.md',
                            stem=file_stem
                        )
                        
                        # Export to DOCX
                        docx_doc = exporter.export(md_doc)
                        docx_content = docx_doc.content
                        
                        # Save DOCX file
                        docx_file = output_dir / f"{file_stem}_translated.docx"
                        with open(docx_file, 'wb') as f:
                            f.write(docx_content)
                        
                        if docx_file.exists():
                            task_state["downloadable_files"]["docx"] = {
                                "path": str(docx_file),
                                "filename": f"{file_stem}_translated.docx"
                            }
                            self.task_manager.add_log(task_id, "success", f"DOCX file generated from Markdown: {docx_file}")
                        else:
                            self.task_manager.add_log(task_id, "error", f"DOCX file not found after generation: {docx_file}")
                    else:
                        self.task_manager.add_log(task_id, "error", "Could not generate Markdown content for DOCX conversion")
                except Exception as e:
                    import traceback
                    error_trace = traceback.format_exc()
                    self.task_manager.add_log(task_id, "error", f"Error generating DOCX from Markdown: {str(e)}")
                    self.task_manager.add_log(task_id, "error", f"Error traceback: {error_trace}")
            else:
                self.task_manager.add_log(task_id, "warning", f"Workflow {workflow_type or 'unknown'} does not support DOCX export")
    
    async def generate_pptx(
        self,
        task_id: str,
        workflow: Any,
        task_state: Dict[str, Any],
        output_dir: Path,
        file_stem: str
    ):
        """Generate PPTX output file."""
        self.task_manager.add_log(task_id, "info", f"Checking PPTX export for workflow type: pptx")
        self.task_manager.add_log(task_id, "info", f"Workflow class: {type(workflow).__name__}")
        self.task_manager.add_log(task_id, "info", f"Has save_as_pptx: {hasattr(workflow, 'save_as_pptx')}")
        self.task_manager.add_log(task_id, "info", f"Has export_to_pptx: {hasattr(workflow, 'export_to_pptx')}")
        
        if hasattr(workflow, 'save_as_pptx'):
            self.task_manager.add_log(task_id, "info", "Generating PPTX file using save_as_pptx...")
            pptx_file = output_dir / f"{file_stem}_translated.pptx"
            try:
                workflow.save_as_pptx(f"{file_stem}_translated", output_dir)
                if pptx_file.exists():
                    task_state["downloadable_files"]["pptx"] = {
                        "path": str(pptx_file),
                        "filename": f"{file_stem}_translated.pptx"
                    }
                    self.task_manager.add_log(task_id, "success", f"PPTX file generated: {pptx_file}")
                else:
                    self.task_manager.add_log(task_id, "error", f"PPTX file not found after generation: {pptx_file}")
            except Exception as e:
                self.task_manager.add_log(task_id, "error", f"Error generating PPTX with save_as_pptx: {str(e)}")
        elif hasattr(workflow, 'export_to_pptx'):
            self.task_manager.add_log(task_id, "info", "Generating PPTX file using export_to_pptx...")
            try:
                pptx_content = workflow.export_to_pptx()
                pptx_file = output_dir / f"{file_stem}_translated.pptx"
                with open(pptx_file, 'wb') as f:
                    f.write(pptx_content)
                if pptx_file.exists():
                    task_state["downloadable_files"]["pptx"] = {
                        "path": str(pptx_file),
                        "filename": f"{file_stem}_translated.pptx"
                    }
                    self.task_manager.add_log(task_id, "success", f"PPTX file generated: {pptx_file}")
                else:
                    self.task_manager.add_log(task_id, "error", f"PPTX file not found after generation: {pptx_file}")
            except Exception as e:
                self.task_manager.add_log(task_id, "error", f"Error generating PPTX with export_to_pptx: {str(e)}")
        else:
            self.task_manager.add_log(task_id, "warning", f"Workflow pptx does not support PPTX export")
        
        # Clean up temporary PPTX file after export (if it was used)
        if hasattr(workflow, 'translator') and workflow.translator:
            if hasattr(workflow.translator, 'temp_pptx_path') and workflow.translator.temp_pptx_path:
                temp_path = workflow.translator.temp_pptx_path
                try:
                    if os.path.exists(temp_path):
                        os.remove(temp_path)
                        self.task_manager.add_log(task_id, "info", f"Cleaned up temporary PPTX file: {temp_path}")
                except Exception as e:
                    self.task_manager.add_log(task_id, "warning", f"Failed to clean up temporary PPTX file {temp_path}: {str(e)}")
    
    async def generate_xlsx(
        self,
        task_id: str,
        workflow: Any,
        task_state: Dict[str, Any],
        output_dir: Path,
        file_stem: str
    ):
        """Generate XLSX output file."""
        self.task_manager.add_log(task_id, "info", f"Checking XLSX export for workflow type: xlsx")
        self.task_manager.add_log(task_id, "info", f"Workflow class: {type(workflow).__name__}")
        self.task_manager.add_log(task_id, "info", f"Has save_as_xlsx: {hasattr(workflow, 'save_as_xlsx')}")
        self.task_manager.add_log(task_id, "info", f"Has export_to_xlsx: {hasattr(workflow, 'export_to_xlsx')}")
        
        if hasattr(workflow, 'save_as_xlsx'):
            self.task_manager.add_log(task_id, "info", "Generating XLSX file using save_as_xlsx...")
            xlsx_filename = f"{file_stem}_translated.xlsx"
            xlsx_file = output_dir / xlsx_filename
            try:
                workflow.save_as_xlsx(xlsx_filename, output_dir)
                # Check if file exists (may have different name from exporter)
                if xlsx_file.exists():
                    task_state["downloadable_files"]["xlsx"] = {
                        "path": str(xlsx_file),
                        "filename": xlsx_filename
                    }
                    self.task_manager.add_log(task_id, "success", f"XLSX file generated: {xlsx_file}")
                else:
                    # Try to find the file with any name in output_dir
                    xlsx_files = list(output_dir.glob("*.xlsx"))
                    if xlsx_files:
                        # Use the first XLSX file found
                        actual_file = xlsx_files[0]
                        task_state["downloadable_files"]["xlsx"] = {
                            "path": str(actual_file),
                            "filename": actual_file.name
                        }
                        self.task_manager.add_log(task_id, "success", f"XLSX file generated: {actual_file}")
                    else:
                        self.task_manager.add_log(task_id, "error", f"XLSX file not found after generation in {output_dir}")
            except Exception as e:
                self.task_manager.add_log(task_id, "error", f"Error generating XLSX with save_as_xlsx: {str(e)}", exc_info=True)
        elif hasattr(workflow, 'export_to_xlsx'):
            self.task_manager.add_log(task_id, "info", "Generating XLSX file using export_to_xlsx...")
            try:
                xlsx_content = workflow.export_to_xlsx()
                xlsx_file = output_dir / f"{file_stem}_translated.xlsx"
                with open(xlsx_file, 'wb') as f:
                    f.write(xlsx_content)
                if xlsx_file.exists():
                    task_state["downloadable_files"]["xlsx"] = {
                        "path": str(xlsx_file),
                        "filename": f"{file_stem}_translated.xlsx"
                    }
                    self.task_manager.add_log(task_id, "success", f"XLSX file generated: {xlsx_file}")
                else:
                    self.task_manager.add_log(task_id, "error", f"XLSX file not found after generation: {xlsx_file}")
            except Exception as e:
                self.task_manager.add_log(task_id, "error", f"Error generating XLSX with export_to_xlsx: {str(e)}", exc_info=True)
        else:
            self.task_manager.add_log(task_id, "warning", f"Workflow xlsx does not support XLSX export")
    
    async def generate_mobi(
        self,
        task_id: str,
        workflow: Any,
        task_state: Dict[str, Any],
        output_dir: Path,
        file_stem: str,
        mobi_engine: Optional[str] = None,
    ):
        """
        Generate MOBI output file.
        Policy: MOBI must NOT be generated from PDF. When mobi_engine=='pandoc', generate
        EPUB via Pandoc then convert to MOBI with Calibre; otherwise from workflow (EPUB)
        or translated HTML via Calibre.
        """
        if mobi_engine == "pandoc":
            epub_path = await asyncio.to_thread(
                self._generate_epub_via_pandoc_sync,
                task_id, task_state, output_dir, file_stem,
            )
            if epub_path:
                cmd = self._find_ebook_convert_cmd()
                if cmd:
                    mobi_path = output_dir / f"{file_stem}_translated.mobi"
                    result = await asyncio.to_thread(
                        _run_ebook_convert_sync,
                        cmd, str(epub_path), str(mobi_path), "--dont-compress",
                        timeout=300,
                    )
                    if result.returncode == 0 and mobi_path.exists() and mobi_path.stat().st_size > 0:
                        task_state.setdefault("downloadable_files", {})["mobi"] = {
                            "path": str(mobi_path),
                            "filename": mobi_path.name,
                        }
                        self.task_manager.add_log(task_id, "success", f"MOBI generated via Pandoc+Calibre: {mobi_path}")
                        logger.info(LogModule.EXPORT, f"[OUTPUT-GENERATOR] Task {task_id}: MOBI via Pandoc+Calibre: {mobi_path}")
                        return
                self.task_manager.add_log(task_id, "info", "Pandoc EPUB ok but Calibre MOBI failed, falling back to workflow/HTML")

        logger.info(LogModule.EXPORT, f"[OUTPUT-GENERATOR] Task {task_id}: Checking MOBI export for workflow type: mobi")
        logger.info(LogModule.EXPORT, f"[OUTPUT-GENERATOR] Task {task_id}: Workflow class: {type(workflow).__name__}")
        logger.info(LogModule.EXPORT, f"[OUTPUT-GENERATOR] Task {task_id}: Has save_as_mobi: {hasattr(workflow, 'save_as_mobi')}")
        logger.info(LogModule.EXPORT, f"[OUTPUT-GENERATOR] Task {task_id}: Has export_to_mobi: {hasattr(workflow, 'export_to_mobi')}")
        
        self.task_manager.add_log(task_id, "info", f"Checking MOBI export for workflow type: mobi")
        self.task_manager.add_log(task_id, "info", f"Workflow class: {type(workflow).__name__}")
        self.task_manager.add_log(task_id, "info", f"Has save_as_mobi: {hasattr(workflow, 'save_as_mobi')}")
        self.task_manager.add_log(task_id, "info", f"Has export_to_mobi: {hasattr(workflow, 'export_to_mobi')}")
        
        # CRITICAL: Use export_to_mobi() and convert EPUB to MOBI format
        # The workflow actually outputs EPUB format, which needs to be converted to MOBI
        if hasattr(workflow, 'export_to_mobi'):
            self.task_manager.add_log(task_id, "info", "Generating MOBI file using export_to_mobi...")
            try:
                # Check document_translated before export
                if hasattr(workflow, 'document_translated') and workflow.document_translated:
                    doc_content = workflow.document_translated.content
                    doc_content_type = type(doc_content).__name__
                    doc_content_len = len(doc_content) if hasattr(doc_content, '__len__') else 'N/A'
                    logger.info(
                        LogModule.EXPORT,
                        f"[OUTPUT-GENERATOR] Task {task_id}: Before export_to_mobi - "
                        f"document_translated.content type: {doc_content_type}, "
                        f"length: {doc_content_len}",
                    )
                
                epub_content = workflow.export_to_mobi()  # Actually returns EPUB format
                epub_content_type = type(epub_content).__name__
                epub_content_len = len(epub_content) if hasattr(epub_content, '__len__') else 'N/A'
                logger.info(
                    LogModule.EXPORT,
                    f"[OUTPUT-GENERATOR] Task {task_id}: export_to_mobi returned EPUB content - "
                    f"type: {epub_content_type}, length: {epub_content_len}",
                )
                
                if epub_content:
                    mobi_file = output_dir / f"{file_stem}_translated.mobi"
                    
                    # Try to convert EPUB to MOBI using calibre's ebook-convert
                    mobi_content = None
                    try:
                        import subprocess
                        import tempfile
                        import os
                        import shutil
                        
                        # Check if ebook-convert is available
                        ebook_convert_cmd = shutil.which('ebook-convert')
                        if not ebook_convert_cmd:
                            # Try common paths on Windows
                            if os.name == 'nt':
                                calibre_paths = [
                                    r'C:\Program Files\Calibre2\ebook-convert.exe',
                                    r'C:\Program Files (x86)\Calibre2\ebook-convert.exe',
                                ]
                                for path in calibre_paths:
                                    if os.path.exists(path):
                                        ebook_convert_cmd = path
                                        break
                        
                        if ebook_convert_cmd:
                            # Create temporary EPUB file
                            with tempfile.NamedTemporaryFile(delete=False, suffix='.epub') as tmp_epub:
                                if isinstance(epub_content, bytes):
                                    tmp_epub.write(epub_content)
                                else:
                                    tmp_epub.write(epub_content.encode('utf-8'))
                                tmp_epub_path = tmp_epub.name
                            
                            # Create temporary MOBI file path
                            with tempfile.NamedTemporaryFile(delete=False, suffix='.mobi') as tmp_mobi:
                                tmp_mobi_path = tmp_mobi.name
                            
                            try:
                                # Convert EPUB to MOBI using calibre (run in thread pool to avoid blocking event loop)
                                logger.info(
                                    LogModule.EXPORT,
                                    f"[OUTPUT-GENERATOR] Task {task_id}: Converting EPUB to MOBI using calibre: {ebook_convert_cmd}",
                                )
                                # --dont-compress speeds up MOBI conversion (slightly larger file)
                                result = await asyncio.to_thread(
                                    _run_ebook_convert_sync,
                                    ebook_convert_cmd,
                                    tmp_epub_path,
                                    tmp_mobi_path,
                                    "--dont-compress",
                                    timeout=300,
                                )
                                if result.returncode == 0 and os.path.exists(tmp_mobi_path):
                                    # Read converted MOBI file
                                    with open(tmp_mobi_path, 'rb') as f:
                                        mobi_content = f.read()
                                    logger.info(
                                        LogModule.EXPORT,
                                        f"[OUTPUT-GENERATOR] Task {task_id}: Successfully converted EPUB to MOBI (size: {len(mobi_content)} bytes)",
                                    )
                                else:
                                    logger.warning(
                                        LogModule.EXPORT,
                                        f"[OUTPUT-GENERATOR] Task {task_id}: ebook-convert failed: returncode={result.returncode}, "
                                        f"stderr={result.stderr[:200]}",
                                    )
                                    # Try HTML->MOBI when EPUB->MOBI conversion failed
                                    html_mobi_path = await asyncio.to_thread(
                                        self._generate_ebook_from_html,
                                        task_id, output_dir, file_stem, "mobi", task_state
                                    )
                                    if html_mobi_path:
                                        mobi_content = html_mobi_path.read_bytes()
                                        mobi_file = html_mobi_path
                            finally:
                                # Clean up temporary files
                                try:
                                    if os.path.exists(tmp_epub_path):
                                        os.unlink(tmp_epub_path)
                                    if os.path.exists(tmp_mobi_path):
                                        os.unlink(tmp_mobi_path)
                                except Exception as cleanup_error:
                                    logger.warning(
                                        LogModule.EXPORT,
                                        f"[OUTPUT-GENERATOR] Task {task_id}: Failed to cleanup temp files: {cleanup_error}",
                                    )
                        else:
                            # ebook-convert not found: try generating MOBI from HTML first (real MOBI, readable)
                            logger.info(
                                LogModule.EXPORT,
                                f"[OUTPUT-GENERATOR] Task {task_id}: ebook-convert not found for EPUB->MOBI, trying HTML->MOBI...",
                            )
                            html_mobi_path = await asyncio.to_thread(
                                self._generate_ebook_from_html,
                                task_id, output_dir, file_stem, "mobi", task_state
                            )
                            if html_mobi_path:
                                mobi_content = html_mobi_path.read_bytes()
                                mobi_file = html_mobi_path
                            # If HTML->MOBI 也失败，则不再“伪造”一个 EPUB 下载项；只提示用户需要安装 Calibre。
                            else:
                                self.task_manager.add_log(
                                    task_id,
                                    "warning",
                                    "MOBI requires Calibre (ebook-convert). Install Calibre to enable MOBI/EPUB conversion.",
                                )
                                logger.warning(
                                    LogModule.EXPORT,
                                    f"[OUTPUT-GENERATOR] Task {task_id}: No ebook-convert; EPUB download not offered. MOBI not generated.",
                                )
                                # Skip writing fake .mobi; mobi_content stays None, we will not register mobi
                                mobi_file = None
                    except Exception as convert_error:
                        logger.warning(
                            LogModule.EXPORT,
                            f"[OUTPUT-GENERATOR] Task {task_id}: Failed to convert EPUB to MOBI: {convert_error}, "
                            f"trying HTML->MOBI fallback",
                            exc_info=False,
                        )
                        html_mobi_path = await asyncio.to_thread(
                            self._generate_ebook_from_html,
                            task_id, output_dir, file_stem, "mobi", task_state
                        )
                        if html_mobi_path:
                            mobi_content = html_mobi_path.read_bytes()
                            mobi_file = html_mobi_path
                    
                    # Write MOBI file only when we have real MOBI content (never write EPUB bytes to .mobi - readers show blank)
                    if mobi_content:
                        out_path = output_dir / f"{file_stem}_translated.mobi"
                        with open(out_path, 'wb') as f:
                            f.write(mobi_content)
                        mobi_file = out_path
                    elif mobi_file is None:
                        pass  # Already handled (EPUB saved, or HTML fallback failed)
                    # Do NOT write EPUB bytes to .mobi - readers display blank; we already saved as .epub when no calibre
                    
                    if mobi_file and mobi_file.exists() and mobi_file.stat().st_size > 0:
                        file_size = mobi_file.stat().st_size
                        if mobi_content:
                            self.task_manager.add_log(task_id, "success", f"MOBI file generated: {mobi_file} (size: {file_size} bytes)")
                        else:
                            self.task_manager.add_log(task_id, "warning", f"MOBI file is EPUB content (install Calibre for real MOBI): {mobi_file}")
                        logger.info(LogModule.EXPORT, f"[OUTPUT-GENERATOR] Task {task_id}: MOBI file: {mobi_file} (size: {file_size} bytes)")
                        task_state.setdefault("downloadable_files", {})["mobi"] = {
                            "path": str(mobi_file),
                            "filename": mobi_file.name,
                        }
                    elif not task_state.get("downloadable_files", {}).get("epub") and epub_content:
                        file_size = 0
                        self.task_manager.add_log(task_id, "error", "MOBI file is empty or not generated. Install Calibre for MOBI, or use EPUB/HTML.")
                        logger.warning(LogModule.EXPORT, f"[OUTPUT-GENERATOR] Task {task_id}: MOBI not generated; EPUB offered instead.")
                else:
                    self.task_manager.add_log(task_id, "error", "export_to_mobi returned empty content")
                    logger.warning(LogModule.EXPORT, f"[OUTPUT-GENERATOR] Task {task_id}: export_to_mobi returned empty content", )
            except Exception as e:
                self.task_manager.add_log(task_id, "error", f"Error generating MOBI with export_to_mobi: {str(e)}")
                logger.error(LogModule.EXPORT, f"[OUTPUT-GENERATOR] Task {task_id}: Error generating MOBI with export_to_mobi: {e}", exc_info=True, )
        elif hasattr(workflow, 'save_as_mobi'):
            # Fallback to save_as_mobi if export_to_mobi is not available
            self.task_manager.add_log(task_id, "info", "Generating MOBI file using save_as_mobi (fallback)...")
            mobi_filename = f"{file_stem}_translated.mobi"
            mobi_file = output_dir / mobi_filename
            try:
                workflow.save_as_mobi(name=mobi_filename, output_dir=output_dir)
                # Check if file exists and has content
                if mobi_file.exists() and mobi_file.stat().st_size > 0:
                    task_state["downloadable_files"]["mobi"] = {
                        "path": str(mobi_file),
                        "filename": mobi_filename
                    }
                    file_size = mobi_file.stat().st_size
                    self.task_manager.add_log(task_id, "success", f"MOBI file generated: {mobi_file} (size: {file_size} bytes)")
                    logger.info(LogModule.EXPORT, f"[OUTPUT-GENERATOR] Task {task_id}: MOBI file generated: {mobi_file} (size: {file_size} bytes)")
                else:
                    # Try to find the file with any name in output_dir
                    mobi_files = list(output_dir.glob("*.mobi"))
                    if mobi_files:
                        actual_file = mobi_files[0]
                        if actual_file.stat().st_size > 0:
                            task_state["downloadable_files"]["mobi"] = {
                                "path": str(actual_file),
                                "filename": actual_file.name
                            }
                            file_size = actual_file.stat().st_size
                            self.task_manager.add_log(task_id, "success", f"MOBI file generated: {actual_file} (size: {file_size} bytes)")
                            logger.info(LogModule.EXPORT, f"[OUTPUT-GENERATOR] Task {task_id}: MOBI file generated: {actual_file} (size: {file_size} bytes)")
                        else:
                            self.task_manager.add_log(task_id, "error", f"MOBI file found but is empty: {actual_file}")
                            logger.warning(LogModule.EXPORT, f"[OUTPUT-GENERATOR] Task {task_id}: MOBI file found but is empty: {actual_file}", )
                    else:
                        self.task_manager.add_log(task_id, "error", f"MOBI file not found after generation in {output_dir}")
                        logger.warning(LogModule.EXPORT, f"[OUTPUT-GENERATOR] Task {task_id}: MOBI file not found after generation in {output_dir}", )
            except Exception as e:
                self.task_manager.add_log(task_id, "error", f"Error generating MOBI with save_as_mobi: {str(e)}")
                logger.error(LogModule.EXPORT, f"[OUTPUT-GENERATOR] Task {task_id}: Error generating MOBI with save_as_mobi: {e}", exc_info=True, )
        elif hasattr(workflow, 'export_to_mobi'):
            self.task_manager.add_log(task_id, "info", "Generating MOBI file using export_to_mobi...")
            try:
                mobi_content = workflow.export_to_mobi()
                if mobi_content:
                    mobi_file = output_dir / f"{file_stem}_translated.mobi"
                    with open(mobi_file, 'wb') as f:
                        if isinstance(mobi_content, bytes):
                            f.write(mobi_content)
                        else:
                            f.write(mobi_content.encode('utf-8'))
                    if mobi_file.exists():
                        task_state["downloadable_files"]["mobi"] = {
                            "path": str(mobi_file),
                            "filename": f"{file_stem}_translated.mobi"
                        }
                        self.task_manager.add_log(task_id, "success", f"MOBI file generated: {mobi_file}")
                        logger.info(LogModule.EXPORT,f"[OUTPUT-GENERATOR] Task {task_id}: MOBI file generated: {mobi_file}", )
                    else:
                        self.task_manager.add_log(task_id, "error", f"MOBI file not found after generation: {mobi_file}")
                        logger.warning(LogModule.EXPORT, f"[OUTPUT-GENERATOR] Task {task_id}: MOBI file not found after generation: {mobi_file}", )
                else:
                    self.task_manager.add_log(task_id, "error", "export_to_mobi returned empty content")
                    logger.warning(LogModule.EXPORT, f"[OUTPUT-GENERATOR] Task {task_id}: export_to_mobi returned empty content", )
            except Exception as e:
                self.task_manager.add_log(task_id, "error", f"Error generating MOBI with export_to_mobi: {str(e)}")
                logger.error(LogModule.EXPORT, f"[OUTPUT-GENERATOR] Task {task_id}: Error generating MOBI with export_to_mobi: {e}", exc_info=True, )
        else:
            self.task_manager.add_log(task_id, "warning", f"Workflow does not support native MOBI export")
            logger.warning(LogModule.EXPORT, f"[OUTPUT-GENERATOR] Task {task_id}: Workflow does not support native MOBI export")
        
        # Fallback: generate MOBI from translated HTML (never from PDF)
        if task_state.get("downloadable_files", {}).get("mobi") is None:
            html_file = output_dir / f"{file_stem}_translated.html"
            if (not html_file.exists() or html_file.stat().st_size == 0) and hasattr(workflow, "save_as_html"):
                self.task_manager.add_log(task_id, "info", "Generating HTML from segments for MOBI conversion...")
                await self.generate_html(task_id, workflow, task_state, output_dir, file_stem)
            out_path = await asyncio.to_thread(
                self._generate_ebook_from_html,
                task_id, output_dir, file_stem, "mobi", task_state
            )
            if out_path:
                task_state.setdefault("downloadable_files", {})["mobi"] = {
                    "path": str(out_path),
                    "filename": out_path.name,
                }
                self.task_manager.add_log(task_id, "success", f"MOBI generated from HTML: {out_path}")
    
    async def generate_epub(
        self,
        task_id: str,
        workflow: Any,
        task_state: Dict[str, Any],
        output_dir: Path,
        file_stem: str,
        epub_engine: Optional[str] = None,
    ):
        """
        Generate EPUB output file.
        Policy: EPUB must NOT be generated from PDF. It is generated from workflow document
        (EPUB content), from Pandoc (MD from segments -> EPUB) when epub_engine=='pandoc',
        or as fallback from the translated HTML file via Calibre.
        """
        if epub_engine == "pandoc":
            out_path = await asyncio.to_thread(
                self._generate_epub_via_pandoc_sync,
                task_id, task_state, output_dir, file_stem,
            )
            if out_path:
                task_state.setdefault("downloadable_files", {})["epub"] = {
                    "path": str(out_path),
                    "filename": out_path.name,
                }
                self.task_manager.add_log(task_id, "success", f"EPUB generated via Pandoc: {out_path}")
                logger.info(LogModule.EXPORT, f"[OUTPUT-GENERATOR] Task {task_id}: EPUB generated via Pandoc: {out_path}")
                return
            self.task_manager.add_log(task_id, "info", "Pandoc EPUB failed, falling back to Calibre/workflow")

        # MOBI workflow: EPUB was already generated in _generate_mobi_with_delayed_dom and stored in
        # workflow.document_translated.content. Write it to file and register for download.
        from workflow.mobi_workflow import MobiWorkflow
        if isinstance(workflow, MobiWorkflow) and getattr(workflow, "document_translated", None):
            doc = workflow.document_translated
            epub_bytes = getattr(doc, "content", None)
            if epub_bytes and len(epub_bytes) > 0:
                epub_file = output_dir / f"{file_stem}_translated.epub"
                with open(epub_file, "wb") as f:
                    f.write(epub_bytes if isinstance(epub_bytes, bytes) else epub_bytes.encode("utf-8"))
                task_state.setdefault("downloadable_files", {})["epub"] = {
                    "path": str(epub_file),
                    "filename": epub_file.name,
                }
                logger.info(
                    LogModule.EXPORT,
                    f"[OUTPUT-GENERATOR] Task {task_id}: Wrote MOBI-generated EPUB to {epub_file} ({len(epub_bytes)} bytes)",
                )
                self.task_manager.add_log(task_id, "success", f"EPUB file ready: {epub_file.name}")
                return

        logger.info(LogModule.EXPORT,f"[OUTPUT-GENERATOR] Task {task_id}: Checking EPUB export for workflow type: epub", )
        logger.info(LogModule.EXPORT,f"[OUTPUT-GENERATOR] Task {task_id}: Workflow class: {type(workflow).__name__}", )
        logger.info(LogModule.EXPORT,f"[OUTPUT-GENERATOR] Task {task_id}: Has save_as_epub: {hasattr(workflow, 'save_as_epub')}", )
        logger.info(LogModule.EXPORT,f"[OUTPUT-GENERATOR] Task {task_id}: Has export_to_epub: {hasattr(workflow, 'export_to_epub')}", )
        
        self.task_manager.add_log(task_id, "info", f"Checking EPUB export for workflow type: epub")
        self.task_manager.add_log(task_id, "info", f"Workflow class: {type(workflow).__name__}")
        self.task_manager.add_log(task_id, "info", f"Has save_as_epub: {hasattr(workflow, 'save_as_epub')}")
        self.task_manager.add_log(task_id, "info", f"Has export_to_epub: {hasattr(workflow, 'export_to_epub')}")
        
        # CRITICAL: Use export_to_epub() instead of save_as_epub() to ensure content is properly exported
        if hasattr(workflow, 'export_to_epub'):
            self.task_manager.add_log(task_id, "info", "Generating EPUB file using export_to_epub...")
            try:
                epub_content = workflow.export_to_epub()
                if epub_content:
                    epub_file = output_dir / f"{file_stem}_translated.epub"
                    with open(epub_file, 'wb') as f:
                        if isinstance(epub_content, bytes):
                            f.write(epub_content)
                        else:
                            f.write(epub_content.encode('utf-8'))
                    if epub_file.exists() and epub_file.stat().st_size > 0:
                        task_state["downloadable_files"]["epub"] = {
                            "path": str(epub_file),
                            "filename": f"{file_stem}_translated.epub"
                        }
                        file_size = epub_file.stat().st_size
                        self.task_manager.add_log(task_id, "success", f"EPUB file generated: {epub_file} (size: {file_size} bytes)")
                        logger.info(LogModule.EXPORT,f"[OUTPUT-GENERATOR] Task {task_id}: EPUB file generated: {epub_file} (size: {file_size} bytes)", )
                    else:
                        file_size = epub_file.stat().st_size if epub_file.exists() else 0
                        self.task_manager.add_log(task_id, "error", f"EPUB file is empty or not found: {epub_file} (size: {file_size} bytes)")
                        logger.warning(LogModule.EXPORT, f"[OUTPUT-GENERATOR] Task {task_id}: EPUB file is empty or not found: {epub_file} (size: {file_size} bytes)", )
                else:
                    self.task_manager.add_log(task_id, "error", "export_to_epub returned empty content")
                    logger.warning(LogModule.EXPORT, f"[OUTPUT-GENERATOR] Task {task_id}: export_to_epub returned empty content", )
            except Exception as e:
                self.task_manager.add_log(task_id, "error", f"Error generating EPUB with export_to_epub: {str(e)}")
                logger.error(LogModule.EXPORT, f"[OUTPUT-GENERATOR] Task {task_id}: Error generating EPUB with export_to_epub: {e}", exc_info=True, )
        elif hasattr(workflow, 'save_as_epub'):
            # Fallback to save_as_epub if export_to_epub is not available
            self.task_manager.add_log(task_id, "info", "Generating EPUB file using save_as_epub (fallback)...")
            epub_filename = f"{file_stem}_translated.epub"
            epub_file = output_dir / epub_filename
            try:
                workflow.save_as_epub(name=epub_filename, output_dir=output_dir)
                # Check if file exists and has content
                if epub_file.exists() and epub_file.stat().st_size > 0:
                    task_state["downloadable_files"]["epub"] = {
                        "path": str(epub_file),
                        "filename": epub_filename
                    }
                    file_size = epub_file.stat().st_size
                    self.task_manager.add_log(task_id, "success", f"EPUB file generated: {epub_file} (size: {file_size} bytes)")
                    logger.info(LogModule.EXPORT,f"[OUTPUT-GENERATOR] Task {task_id}: EPUB file generated: {epub_file} (size: {file_size} bytes)", )
                else:
                    # Try to find the file with any name in output_dir
                    epub_files = list(output_dir.glob("*.epub"))
                    if epub_files:
                        actual_file = epub_files[0]
                        if actual_file.stat().st_size > 0:
                            task_state["downloadable_files"]["epub"] = {
                                "path": str(actual_file),
                                "filename": actual_file.name
                            }
                            file_size = actual_file.stat().st_size
                            self.task_manager.add_log(task_id, "success", f"EPUB file generated: {actual_file} (size: {file_size} bytes)")
                            logger.info(LogModule.EXPORT,f"[OUTPUT-GENERATOR] Task {task_id}: EPUB file generated: {actual_file} (size: {file_size} bytes)", )
                        else:
                            self.task_manager.add_log(task_id, "error", f"EPUB file found but is empty: {actual_file}")
                            logger.warning(LogModule.EXPORT, f"[OUTPUT-GENERATOR] Task {task_id}: EPUB file found but is empty: {actual_file}", )
                    else:
                        self.task_manager.add_log(task_id, "error", f"EPUB file not found after generation in {output_dir}")
                        logger.warning(LogModule.EXPORT, f"[OUTPUT-GENERATOR] Task {task_id}: EPUB file not found after generation in {output_dir}", )
            except Exception as e:
                self.task_manager.add_log(task_id, "error", f"Error generating EPUB with save_as_epub: {str(e)}")
                logger.error(LogModule.EXPORT, f"[OUTPUT-GENERATOR] Task {task_id}: Error generating EPUB with save_as_epub: {e}", exc_info=True, )
        elif hasattr(workflow, 'export_to_epub'):
            self.task_manager.add_log(task_id, "info", "Generating EPUB file using export_to_epub...")
            try:
                epub_content = workflow.export_to_epub()
                if epub_content:
                    epub_file = output_dir / f"{file_stem}_translated.epub"
                    with open(epub_file, 'wb') as f:
                        if isinstance(epub_content, bytes):
                            f.write(epub_content)
                        else:
                            f.write(epub_content.encode('utf-8'))
                    if epub_file.exists():
                        task_state["downloadable_files"]["epub"] = {
                            "path": str(epub_file),
                            "filename": f"{file_stem}_translated.epub"
                        }
                        self.task_manager.add_log(task_id, "success", f"EPUB file generated: {epub_file}")
                        logger.info(LogModule.EXPORT,f"[OUTPUT-GENERATOR] Task {task_id}: EPUB file generated: {epub_file}", )
                    else:
                        self.task_manager.add_log(task_id, "error", f"EPUB file not found after generation: {epub_file}")
                        logger.warning(LogModule.EXPORT, f"[OUTPUT-GENERATOR] Task {task_id}: EPUB file not found after generation: {epub_file}", )
                else:
                    self.task_manager.add_log(task_id, "error", "export_to_epub returned empty content")
                    logger.warning(LogModule.EXPORT, f"[OUTPUT-GENERATOR] Task {task_id}: export_to_epub returned empty content", )
            except Exception as e:
                self.task_manager.add_log(task_id, "error", f"Error generating EPUB with export_to_epub: {str(e)}")
                logger.error(LogModule.EXPORT, f"[OUTPUT-GENERATOR] Task {task_id}: Error generating EPUB with export_to_epub: {e}", exc_info=True, )
        else:
            self.task_manager.add_log(task_id, "warning", f"Workflow does not support native EPUB export")
            logger.warning(LogModule.EXPORT, f"[OUTPUT-GENERATOR] Task {task_id}: Workflow does not support native EPUB export")
        
        # Fallback: generate EPUB from translated HTML (never from PDF)
        if task_state.get("downloadable_files", {}).get("epub") is None:
            html_file = output_dir / f"{file_stem}_translated.html"
            if (not html_file.exists() or html_file.stat().st_size == 0) and hasattr(workflow, "save_as_html"):
                self.task_manager.add_log(task_id, "info", "Generating HTML from segments for EPUB conversion...")
                await self.generate_html(task_id, workflow, task_state, output_dir, file_stem)
            out_path = await asyncio.to_thread(
                self._generate_ebook_from_html,
                task_id, output_dir, file_stem, "epub", task_state
            )
            if out_path:
                task_state.setdefault("downloadable_files", {})["epub"] = {
                    "path": str(out_path),
                    "filename": out_path.name,
                }
                self.task_manager.add_log(task_id, "success", f"EPUB generated from HTML: {out_path}")
    
    async def generate_markdown(
        self,
        task_id: str,
        workflow: Any,
        task_state: Dict[str, Any],
        output_dir: Path,
        file_stem: str
    ):
        """Generate Markdown output file."""
        if not hasattr(workflow, 'export_to_markdown'):
            return
        
        try:
            self.task_manager.add_log(task_id, "info", "Generating Markdown file...")
            markdown_content = None
            
            # For MOBI/EPUB workflows, prioritize HTML-to-Markdown conversion
            # (segments may contain HTML tags that need proper conversion)
            workflow_type = task_state.get("workflow_type") or task_state.get("payload", {}).get("workflow_type")
            orig_l = (task_state.get("original_filename") or "").lower()
            # XLSX/PPTX/HTML: translated HTML carries <table>; segment MD rebuild flattens cells / rows.
            prefer_html_table_md = workflow_type in ("xlsx", "pptx", "html") or orig_l.endswith(
                (".xlsx", ".xls", ".pptx", ".ppt", ".html", ".htm")
            )
            is_mobi_epub = workflow_type in ("mobi", "epub")
            
            if is_mobi_epub:
                # Priority 1: Use workflow export (HTML-to-Markdown conversion)
                try:
                    markdown_content = workflow.export_to_markdown()
                    self.task_manager.add_log(task_id, "info", "Markdown file generated from HTML (MOBI/EPUB workflow)")
                except Exception as e:
                    self.task_manager.add_log(task_id, "warning", f"Could not generate Markdown from HTML: {str(e)}, trying segments rebuild")
            else:
                # For other workflows, try to rebuild from segments first (preserves original format).
                # XLSX/PPTX: segment rebuild flattens table cells; use workflow HTML→MD path.
                segments_data = task_state.get("translation_segments")
                skip_segment_md_for_tables = prefer_html_table_md
                if skip_segment_md_for_tables:
                    self.task_manager.add_log(
                        task_id,
                        "info",
                        "Skipping Markdown rebuild from segments for XLSX/PPTX/HTML (use workflow HTML-table export).",
                    )
                if (
                    not skip_segment_md_for_tables
                    and segments_data
                    and segments_data.get("segments")
                ):
                    try:
                        from utils.document_rebuild import rebuild_markdown_document_from_segments
                        rebuilt_doc = rebuild_markdown_document_from_segments(
                            task_state,
                            file_stem=file_stem,
                            output_dir=output_dir
                        )
                        if rebuilt_doc and hasattr(rebuilt_doc, 'content'):
                            # Decode bytes to string
                            if isinstance(rebuilt_doc.content, bytes):
                                markdown_content = rebuilt_doc.content.decode('utf-8')
                            else:
                                markdown_content = rebuilt_doc.content
                            self.task_manager.add_log(task_id, "info", "Markdown file generated from segments (format preserved, images exported)")
                    except Exception as e:
                        self.task_manager.add_log(task_id, "warning", f"Could not rebuild Markdown from segments: {str(e)}, using workflow export")
            
            # Priority 2: Fallback to workflow export (if not already used)
            if markdown_content is None:
                markdown_content = workflow.export_to_markdown()
                self.task_manager.add_log(task_id, "info", "Markdown file generated from workflow export")

            # XLSX/PPTX: if in-memory export is tiny but translated HTML was written, use disk HTML
            html_saved = output_dir / f"{file_stem}_translated.html"
            if prefer_html_table_md and html_saved.is_file():
                try:
                    html_text = html_saved.read_text(encoding="utf-8-sig", errors="replace")
                    md_strip = (markdown_content or "").strip()
                    html_len = len(html_text)
                    if html_len > 500 and len(md_strip) < min(500, max(80, html_len // 20)):
                        from workflow.html_to_markdown_export import html_content_to_markdown

                        markdown_content = html_content_to_markdown(html_text)
                        logger.info(
                            LogModule.EXPORT,
                            f"[OUTPUT-GENERATOR] Task {task_id}: table-friendly MD from saved HTML "
                            f"(workflow MD chars={len(md_strip)}, html chars={html_len})",
                        )
                        self.task_manager.add_log(
                            task_id,
                            "info",
                            "Markdown built from saved translated HTML (workflow export was too short).",
                        )
                except Exception as ex:
                    logger.warning(
                        LogModule.EXPORT,
                        f"[OUTPUT-GENERATOR] Task {task_id}: MD from saved HTML failed: {ex}",
                        exc_info=True,
                    )
            
            if markdown_content:
                # Process images: convert data URI images to files if needed
                image_folder_name = "images"
                images_dir = output_dir / image_folder_name
                images_dir.mkdir(parents=True, exist_ok=True)
                
                # Pattern to match data URI images: ![alt](data:image/type;base64,data)
                data_uri_pattern = re.compile(r'!\[([^\]]*)\]\(data:image/([^;]+);base64,([^\)]+)\)')
                saved_count = 0
                
                def replace_data_uri_with_file(match: re.Match) -> str:
                    nonlocal saved_count
                    alt_text = match.group(1)
                    mime_type = match.group(2)
                    base64_data = match.group(3)
                    
                    try:
                        # Determine file extension
                        extension = mimetypes.guess_extension(f"image/{mime_type}") or ".png"
                        # Generate unique filename
                        image_id = hashlib.md5(base64_data.encode()).hexdigest()[:8]
                        image_filename = f"{image_id}{extension}"
                        image_path = images_dir / image_filename
                        
                        # Decode and save image
                        image_bytes = base64.b64decode(base64_data)
                        image_path.write_bytes(image_bytes)
                        saved_count += 1
                        
                        # Return markdown with relative file path
                        relative_path = f"./{image_folder_name}/{image_filename}"
                        return f"![{alt_text}]({relative_path})"
                    except Exception as e:
                        logger.warning(LogModule.EXPORT, f"Failed to save image: {e}, keeping data URI")
                        return match.group(0)
                
                # Replace data URI images with file references
                markdown_content = data_uri_pattern.sub(replace_data_uri_with_file, markdown_content)
                if saved_count > 0:
                    self.task_manager.add_log(task_id, "info", f"Exported {saved_count} images to {images_dir}")
                
                # Group consecutive images into side-by-side HTML layout (same row only when layout available)
                from app.services.download.download_service import _get_image_layout_for_grouping
                from utils.format_convert_utils import group_consecutive_images_for_markdown
                _img_bidx, _path_to_bidx, _layout = _get_image_layout_for_grouping(task_state)
                markdown_content = group_consecutive_images_for_markdown(
                    markdown_content, image_block_indices=_img_bidx, layout_document=_layout if _img_bidx else None,
                    layout_block_bbox=task_state.get("layout_block_bbox"),
                )
                
                markdown_file = output_dir / f"{file_stem}_translated.md"
                with open(markdown_file, 'w', encoding='utf-8') as f:
                    f.write(markdown_content)
                if markdown_file.exists():
                    task_state["downloadable_files"]["md"] = {
                        "path": str(markdown_file),
                        "filename": f"{file_stem}_translated.md"
                    }
                    self.task_manager.add_log(task_id, "success", f"Markdown file generated: {markdown_file}")
        except Exception as e:
            self.task_manager.add_log(task_id, "warning", f"Could not generate Markdown: {str(e)}")
    
    async def generate_txt(
        self,
        task_id: str,
        workflow: Any,
        task_state: Dict[str, Any],
        output_dir: Path,
        file_stem: str
    ):
        """Generate TXT output file."""
        if not hasattr(workflow, 'export_to_txt'):
            return
        
        try:
            self.task_manager.add_log(task_id, "info", "Generating TXT file...")
            txt_content = workflow.export_to_txt()
            txt_file = output_dir / f"{file_stem}_translated.txt"
            with open(txt_file, 'w', encoding='utf-8') as f:
                f.write(txt_content)
            if txt_file.exists():
                task_state["downloadable_files"]["txt"] = {
                    "path": str(txt_file),
                    "filename": f"{file_stem}_translated.txt"
                }
                self.task_manager.add_log(task_id, "success", f"TXT file generated: {txt_file}")
        except Exception as e:
            self.task_manager.add_log(task_id, "warning", f"Could not generate TXT: {str(e)}")
    
    async def generate_json(
        self,
        task_id: str,
        workflow: Any,
        task_state: Dict[str, Any],
        output_dir: Path,
        file_stem: str
    ):
        """Generate JSON output file."""
        if not hasattr(workflow, 'export_to_json'):
            return
        
        try:
            self.task_manager.add_log(task_id, "info", "Generating JSON file...")
            json_content = workflow.export_to_json()
            json_file = output_dir / f"{file_stem}_translated.json"
            with open(json_file, 'w', encoding='utf-8') as f:
                f.write(json_content)
            if json_file.exists():
                task_state["downloadable_files"]["json"] = {
                    "path": str(json_file),
                    "filename": f"{file_stem}_translated.json"
                }
                self.task_manager.add_log(task_id, "success", f"JSON file generated: {json_file}")
        except Exception as e:
            self.task_manager.add_log(task_id, "warning", f"Could not generate JSON: {str(e)}")

    async def generate_arb(
        self,
        task_id: str,
        workflow: Any,
        task_state: Dict[str, Any],
        output_dir: Path,
        file_stem: str,
    ):
        """Generate ARB output file (JSON-based, for ARB workflows)."""
        if not hasattr(workflow, "export_to_json"):
            return

        try:
            self.task_manager.add_log(task_id, "info", "Generating ARB file...")
            json_content = workflow.export_to_json()
            arb_file = output_dir / f"{file_stem}_translated.arb"
            with open(arb_file, "w", encoding="utf-8") as f:
                f.write(json_content)
            if arb_file.exists():
                task_state["downloadable_files"]["arb"] = {
                    "path": str(arb_file),
                    "filename": f"{file_stem}_translated.arb",
                }
                self.task_manager.add_log(
                    task_id, "success", f"ARB file generated: {arb_file}"
                )
        except Exception as e:
            self.task_manager.add_log(
                task_id, "warning", f"Could not generate ARB: {str(e)}"
            )
    
    async def generate_srt(
        self,
        task_id: str,
        workflow: Any,
        task_state: Dict[str, Any],
        output_dir: Path,
        file_stem: str
    ):
        """Generate SRT output file."""
        if not hasattr(workflow, 'export_to_srt'):
            return
        
        try:
            self.task_manager.add_log(task_id, "info", "Generating SRT file...")
            srt_content = workflow.export_to_srt()
            srt_file = output_dir / f"{file_stem}_translated.srt"
            with open(srt_file, 'w', encoding='utf-8') as f:
                f.write(srt_content)
            if srt_file.exists():
                task_state["downloadable_files"]["srt"] = {
                    "path": str(srt_file),
                    "filename": f"{file_stem}_translated.srt"
                }
                self.task_manager.add_log(task_id, "success", f"SRT file generated: {srt_file}")
        except Exception as e:
            self.task_manager.add_log(task_id, "warning", f"Could not generate SRT: {str(e)}")
    
    async def generate_ts(
        self,
        task_id: str,
        workflow: Any,
        task_state: Dict[str, Any],
        output_dir: Path,
        file_stem: str
    ):
        """Generate TS output file (for qt_ts workflow)."""
        if not hasattr(workflow, 'export_to_ts'):
            return
        
        try:
            self.task_manager.add_log(task_id, "info", "Generating TS file...")
            ts_content = workflow.export_to_ts()
            ts_file = output_dir / f"{file_stem}_translated.ts"
            with open(ts_file, 'w', encoding='utf-8') as f:
                f.write(ts_content)
            if ts_file.exists():
                task_state["downloadable_files"]["ts"] = {
                    "path": str(ts_file),
                    "filename": f"{file_stem}_translated.ts"
                }
                self.task_manager.add_log(task_id, "success", f"TS file generated: {ts_file}")
        except Exception as e:
            self.task_manager.add_log(task_id, "warning", f"Could not generate TS: {str(e)}")
    
    async def generate_pdf(
        self,
        task_id: str,
        workflow: Any,
        payload: Any,
        task_state: Dict[str, Any],
        output_dir: Path,
        file_stem: str
    ):
        """Generate PDF output file."""
        try:
            self.task_manager.add_log(task_id, "info", "Generating PDF file...")
            logger.info(LogModule.EXPORT,f"[OUTPUT-GENERATOR] Starting PDF generation for task {task_id}")
            
            # Update progress before PDF generation (which may take time)
            if task_state["progress"] < 95:
                task_state["progress"] = 95
                task_state["message"] = "Generating PDF file..."
            
            # For MOBI/EPUB workflows, convert from HTML directly (simple and preserves format/images)
            workflow_type = getattr(payload, 'workflow_type', None)
            logger.info(LogModule.EXPORT,f"[PDF-EXPORT] Checking workflow_type: {workflow_type}, payload type: {type(payload)}")
            self.task_manager.add_log(task_id, "info", f"[PDF-EXPORT] Workflow type: {workflow_type}")
            if workflow_type in ("mobi", "epub"):
                logger.info(LogModule.EXPORT,f"[PDF-EXPORT] MOBI/EPUB workflow detected, will use HTML-to-PDF conversion")
                self.task_manager.add_log(task_id, "info", f"[PDF-EXPORT] MOBI/EPUB workflow: Converting to PDF from HTML (preserves format and images)...")
                try:
                    logger.info(LogModule.EXPORT,f"[PDF-EXPORT] Checking if workflow has export_to_html method...")
                    has_export_to_html = hasattr(workflow, 'export_to_html')
                    logger.info(LogModule.EXPORT,f"[PDF-EXPORT] Workflow has export_to_html: {has_export_to_html}")
                    if has_export_to_html:
                        self.task_manager.add_log(task_id, "info", "[PDF-EXPORT] Workflow has export_to_html method, will use HTML-to-PDF conversion")
                        # CRITICAL: For MOBI workflow, ensure html_exporter_config has image_data_map
                        if hasattr(workflow, 'config') and hasattr(workflow.config, 'html_exporter_config'):
                            from exporter.mobi.mobi2html_exporter import Mobi2HTMLExporterConfig
                            # Get image_data_map from task_state
                            image_data_map_for_html = (
                                task_state.get("image_data_map")
                                or task_state.get("translation_image_data_map")
                                or task_state.get("mobi_image_data_map")
                                or {}
                            )
                            workflow.config.html_exporter_config = Mobi2HTMLExporterConfig(
                                cdn=False,
                                image_data_map=image_data_map_for_html
                            )
                            self.task_manager.add_log(task_id, "info", f"[PDF-EXPORT] Set image_data_map for MOBI HTML export: {len(image_data_map_for_html)} images")
                        
                        logger.info(LogModule.EXPORT,f"[PDF-EXPORT] Calling workflow.export_to_html()...")
                        html_content = workflow.export_to_html()
                        logger.info(LogModule.EXPORT,f"[PDF-EXPORT] workflow.export_to_html() completed, html_content length: {len(html_content) if html_content else 0}")
                        if html_content:
                            self.task_manager.add_log(task_id, "info", f"[PDF-EXPORT] HTML content generated, length: {len(html_content)} chars")
                            # Convert HTML to PDF via Pandoc (XeLaTeX) only.
                            from utils.format_convert_utils import convert_html_to_pdf
                            
                            pdf_file = output_dir / f"{file_stem}_translated.pdf"
                            try:
                                self.task_manager.add_log(task_id, "info", f"[PDF-EXPORT] Calling convert_html_to_pdf with output_dir: {output_dir}, pdf_file: {pdf_file}")
                                logger.info(LogModule.EXPORT,f"[PDF-EXPORT] Awaiting convert_html_to_pdf(html_length={len(html_content)}, output_path={pdf_file})")
                                await convert_html_to_pdf(
                                    html_content,
                                    str(pdf_file),
                                    output_dir=output_dir,
                                )
                                logger.info(LogModule.EXPORT,f"[PDF-EXPORT] Await convert_html_to_pdf completed, will check pdf_file existence")
                                self.task_manager.add_log(task_id, "info", f"[PDF-EXPORT] convert_html_to_pdf completed, checking if file exists: {pdf_file}")
                                
                                if pdf_file.exists():
                                    file_size = pdf_file.stat().st_size
                                    self.task_manager.add_log(task_id, "info", f"[PDF-EXPORT] PDF file exists, size: {file_size} bytes")
                                    if "downloadable_files" not in task_state:
                                        task_state["downloadable_files"] = {}
                                    task_state["downloadable_files"]["pdf"] = {
                                        "path": str(pdf_file),
                                        "filename": f"{file_stem}_translated.pdf"
                                    }
                                    self.task_manager.add_log(task_id, "success", f"[PDF-EXPORT] PDF file generated from HTML via Pandoc: {pdf_file}, added to downloadable_files")
                                    logger.info(LogModule.EXPORT,f"[OUTPUT-GENERATOR] PDF generation completed for task {task_id}, file: {pdf_file}, size: {file_size} bytes")
                                    return
                                else:
                                    self.task_manager.add_log(task_id, "error", f"[PDF-EXPORT] PDF file not found after Playwright conversion: {pdf_file}")
                                    raise FileNotFoundError(f"PDF file was not created at: {pdf_file}")
                            except Exception as pdf_error:
                                import traceback
                                error_trace = traceback.format_exc()
                                logger.error(LogModule.EXPORT, f"[PDF-EXPORT] Exception while running convert_html_to_pdf: {pdf_error}", exc_info=True)
                                self.task_manager.add_log(task_id, "error", f"[PDF-EXPORT] HTML-to-PDF conversion failed: {str(pdf_error)}")
                                self.task_manager.add_log(task_id, "error", f"[PDF-EXPORT] Error traceback: {error_trace}")
                                # For MOBI/EPUB, don't fallback to layout-based PDF (no layout available)
                                raise ValueError(f"HTML-to-PDF conversion failed for MOBI/EPUB workflow: {str(pdf_error)}")
                        else:
                            self.task_manager.add_log(task_id, "warning", "[PDF-EXPORT] HTML content is empty, cannot convert to PDF")
                            raise ValueError("HTML content is empty, cannot generate PDF for MOBI/EPUB workflow")
                    else:
                        logger.warning(LogModule.EXPORT, f"[PDF-EXPORT] Workflow does not have export_to_html method, workflow type: {type(workflow)}")
                        self.task_manager.add_log(task_id, "warning", "[PDF-EXPORT] Workflow does not have export_to_html method")
                        raise ValueError("Workflow does not have export_to_html method, cannot generate PDF for MOBI/EPUB workflow")
                except Exception as e:
                    # For MOBI/EPUB, don't fallback to layout-based PDF (no layout available)
                    logger.error(LogModule.EXPORT, f"[PDF-EXPORT] HTML-to-PDF conversion failed for MOBI/EPUB workflow: {e}", exc_info=True)
                    raise
            else:
                logger.info(
                    LogModule.EXPORT,
                    f"[PDF-EXPORT] Not a MOBI/EPUB workflow, workflow_type: {workflow_type}",
                )
            
            # For markdown_based workflows: prefer HTML->PDF so side-by-side images match HTML export; fallback to Pandoc MD->PDF
            if workflow_type == "markdown_based" and hasattr(workflow, "export_to_markdown"):
                to_lang = None
                if payload:
                    to_lang = (
                        (payload.get("to_lang") or payload.get("target_language"))
                        if isinstance(payload, dict)
                        else (getattr(payload, "to_lang", None) or getattr(payload, "target_language", None))
                    )
                if not to_lang and task_state:
                    to_lang = task_state.get("to_lang") or task_state.get("target_language")
                pdf_file = output_dir / f"{file_stem}_translated.pdf"
                from app.services.download.download_service import _get_image_layout_for_grouping
                _img_bidx, _path_to_bidx, _layout = _get_image_layout_for_grouping(task_state)
                try:
                    # Priority 1: HTML->PDF (same pipeline as HTML export so side-by-side images are preserved)
                    if hasattr(workflow, "export_to_html") and hasattr(workflow, "config") and hasattr(workflow.config, "html_exporter_config"):
                        from exporter.md.md2html_exporter import MD2HTMLExporterConfig
                        from utils.document_rebuild import rebuild_markdown_document_from_segments
                        from utils.document_rebuild import _replace_placeholders_with_images
                        from ir.markdown_document import MarkdownDocument
                        original_html_config = workflow.config.html_exporter_config
                        workflow.config.html_exporter_config = MD2HTMLExporterConfig(
                            cdn=False,
                            preserve_line_breaks=True,
                            layout_block_bbox=task_state.get("layout_block_bbox"),
                            image_block_indices=_img_bidx,
                            layout_document=_layout if _img_bidx else None,
                        )
                        try:
                            # PyMuPDF HTML->PDF path removed. Always use Pandoc (MD → XeLaTeX → PDF)
                            # for markdown_based workflow to keep one deterministic implementation.
                            pass
                        finally:
                            workflow.config.html_exporter_config = original_html_config
                    # Pandoc MD->PDF (single implementation)
                    from utils.format_convert_utils import convert_md_to_pdf
                    from utils.document_rebuild import rebuild_markdown_document_from_segments
                    md_content = None
                    try:
                        md_content = workflow.export_to_markdown()
                    except Exception:
                        pass
                    if task_state.get("translation_segments") and task_state.get("translation_segments", {}).get("segments"):
                        try:
                            rebuilt = rebuild_markdown_document_from_segments(
                                task_state,
                                file_stem=file_stem,
                                output_dir=output_dir,
                                equation_format="latex",
                                table_body_format="html",
                            )
                            if rebuilt and getattr(rebuilt, "content", None):
                                raw = rebuilt.content
                                md_content = raw.decode("utf-8") if isinstance(raw, bytes) else (raw if isinstance(raw, str) else str(raw))
                                self.task_manager.add_log(task_id, "info", "[PDF-EXPORT] Using rebuilt markdown with LaTeX equations for PDF")
                        except Exception as rebuild_err:
                            logger.debug(LogModule.EXPORT, f"[PDF-EXPORT] Rebuild for PDF failed: {rebuild_err}, using export_to_markdown")
                    if not md_content:
                        md_content = workflow.export_to_markdown()

                    # PRE-CHECK: validate LaTeX-containing segments before full export.
                    # This catches errors early so users don't wait for the entire document
                    # to compile only to fail on one bad segment.
                    segs = (task_state.get("translation_segments") or {}).get("segments") or []
                    if isinstance(segs, list) and segs:
                        try:
                            from utils.latex_repair_payload import has_latex_content
                            from utils.latex_formula_checker import check_segment_pdf_compat

                            latex_segs = [
                                seg for seg in segs
                                if isinstance(seg, dict)
                                and has_latex_content(
                                    seg.get("modified_text") or seg.get("target_text") or ""
                                )
                            ]
                            # Limit pre-check to avoid excessive pandoc calls on very large docs
                            _precheck_limit = 30
                            if len(latex_segs) > _precheck_limit:
                                logger.info(
                                    LogModule.EXPORT,
                                    f"[PDF-EXPORT] Pre-check: {len(latex_segs)} LaTeX segments found, "
                                    f"limiting pre-check to first {_precheck_limit}",
                                )
                                latex_segs = latex_segs[:_precheck_limit]

                            for seg in latex_segs:
                                seg_idx = seg.get("segment_index", -1)
                                text = seg.get("modified_text") or seg.get("target_text") or ""
                                pre_result = check_segment_pdf_compat(text, segment_index=seg_idx)
                                if not pre_result.passed:
                                    logger.warning(
                                        LogModule.EXPORT,
                                        f"[PDF-EXPORT] Pre-check FAILED for segment {seg_idx}; "
                                        f"skipping full PDF export to save time. "
                                        f"Issues: {len(pre_result.issues)}",
                                    )
                                    task_state["pdf_export_latex_issue"] = {
                                        "error_type": "pre_check_failed",
                                        "segment_index": seg_idx,
                                        "candidate_segment_indices": [seg_idx],
                                        "match_basis": "pre_check",
                                        "message": pre_result.message,
                                        "stderr_excerpt": (pre_result.stderr or "")[:2000],
                                    }
                                    self.task_manager.add_log(
                                        task_id,
                                        "warning",
                                        f"[PDF-EXPORT] Pre-check failed for segment {seg_idx}. "
                                        f"Please fix this segment before retrying PDF export.",
                                    )
                                    ok = False
                                    raise RuntimeError(
                                        f"PDF export pre-check failed for segment {seg_idx}. "
                                        f"Please fix the LaTeX error in this segment and retry."
                                    )
                            if latex_segs:
                                logger.info(
                                    LogModule.EXPORT,
                                    f"[PDF-EXPORT] Pre-check passed for {len(latex_segs)} LaTeX segment(s).",
                                )
                        except RuntimeError:
                            raise  # Re-raise our own pre-check failure
                        except Exception as pre_err:
                            # Pre-check itself failed (e.g. pandoc not found); log and continue
                            logger.debug(
                                LogModule.EXPORT,
                                f"[PDF-EXPORT] Pre-check encountered an error: {pre_err}; continuing with full export",
                            )

                    try:
                        ok = bool(md_content) and convert_md_to_pdf(
                            md_content,
                            str(pdf_file),
                            output_dir=output_dir,
                            to_lang=to_lang,
                            image_block_indices=_img_bidx,
                            path_to_block_index=_path_to_bidx,
                            layout_document=_layout if _path_to_bidx else None,
                            layout_block_bbox=task_state.get("layout_block_bbox"),
                        )
                    except Exception as e:
                        # Surface segment hint for LaTeX compilation errors (no auto-repair).
                        try:
                            from utils.format_convert_utils import PdfExportLatexError

                            if isinstance(e, PdfExportLatexError):
                                segs = (task_state.get("translation_segments") or {}).get("segments") or []
                                segment_index = None
                                candidates: list[int] = []
                                match_basis = "unknown"

                                def _best_effort_find_segment_index() -> None:
                                    nonlocal segment_index, match_basis
                                    if not isinstance(segs, list) or not segs:
                                        return

                                    import re as _re

                                    def _seg_text(seg: dict) -> str:
                                        """Return the best text to search against for a segment."""
                                        return (
                                            (seg or {}).get("modified_text")
                                            or (seg or {}).get("target_text", "")
                                            or ""
                                        )

                                    def _strip_line_numbers(snippet: str) -> list[str]:
                                        """Remove 'N: ' line-number prefixes and filter short lines."""
                                        out: list[str] = []
                                        for ln in (snippet or "").splitlines():
                                            clean = _re.sub(r"^\d+:\s*", "", ln).strip()
                                            if len(clean) >= 4:
                                                out.append(clean)
                                        return out

                                    # 1) MD snippet matches (highest priority)
                                    md_snippet = (e.md_snippet or "").strip()
                                    if md_snippet:
                                        lines = _strip_line_numbers(md_snippet)
                                        if lines:
                                            match_basis = "md_snippet"
                                            for seg in segs:
                                                t = _seg_text(seg)
                                                if not t:
                                                    continue
                                                for ln in lines[:10]:
                                                    if ln and ln in t:
                                                        segment_index = (seg or {}).get("segment_index")
                                                        return

                                    # 2) Tex snippet content matches (second priority)
                                    tex_snippet = (e.tex_snippet or "").strip()
                                    if tex_snippet:
                                        lines = _strip_line_numbers(tex_snippet)
                                        if lines:
                                            match_basis = "tex_snippet"
                                            for seg in segs:
                                                t = _seg_text(seg)
                                                if not t:
                                                    continue
                                                for ln in lines[:10]:
                                                    if ln and ln in t:
                                                        segment_index = (seg or {}).get("segment_index")
                                                        return

                                    # 3) Error token exact match (third priority)
                                    token = (getattr(e, "error_token", "") or "").strip()
                                    if token:
                                        match_basis = f"error_token:{token}"
                                        for seg in segs:
                                            t = _seg_text(seg)
                                            if t and token in t:
                                                segment_index = (seg or {}).get("segment_index")
                                                return

                                        # 3b) For environment tokens, extract env name and search broadly
                                        env_match = _re.search(r"\\(begin|end)\{([^}]+)\}", token)
                                        if env_match:
                                            env_name = env_match.group(2)
                                            env_begin = f"\\begin{{{env_name}}}"
                                            env_end = f"\\end{{{env_name}}}"
                                            match_basis = f"env_name:{env_name}"
                                            for seg in segs:
                                                t = _seg_text(seg)
                                                if t and (env_begin in t or env_end in t):
                                                    segment_index = (seg or {}).get("segment_index")
                                                    return

                                        # 3c) For general commands, try base command without braces/args
                                        cmd_match = _re.search(r"\\([a-zA-Z]+)", token)
                                        if cmd_match:
                                            cmd_base = "\\" + cmd_match.group(1)
                                            if cmd_base != token:
                                                match_basis = f"cmd_base:{cmd_base}"
                                                for seg in segs:
                                                    t = _seg_text(seg)
                                                    if t and cmd_base in t:
                                                        segment_index = (seg or {}).get("segment_index")
                                                        return

                                    # 4) Error-type heuristics: parse stderr for specific clues
                                    error_type = getattr(e, "error_type", "") or ""
                                    stderr = getattr(e, "stderr", "") or ""
                                    if error_type == "undefined_control_sequence":
                                        m = _re.search(
                                            r"Undefined control sequence[.\s]*\\(\w+)",
                                            stderr,
                                            _re.IGNORECASE,
                                        )
                                        if m:
                                            undefined_cmd = "\\" + m.group(1)
                                            match_basis = f"undefined_cmd:{undefined_cmd}"
                                            for seg in segs:
                                                t = _seg_text(seg)
                                                if t and undefined_cmd in t:
                                                    segment_index = (seg or {}).get("segment_index")
                                                    return

                                    # 5) Last resort: score segments by how many backslash commands
                                    # from stderr they contain. Only use if we find >= 2 matches.
                                    if stderr:
                                        cmds_in_stderr = set(
                                            _re.findall(r"\\([a-zA-Z]+)", stderr)
                                        )
                                        if cmds_in_stderr:
                                            best_seg = None
                                            best_score = 0
                                            for seg in segs:
                                                t = _seg_text(seg)
                                                if not t:
                                                    continue
                                                score = sum(
                                                    1 for cmd in cmds_in_stderr if f"\\{cmd}" in t
                                                )
                                                if score > best_score:
                                                    best_score = score
                                                    best_seg = seg
                                            if best_seg and best_score >= 2:
                                                segment_index = best_seg.get("segment_index")
                                                match_basis = f"stderr_cmd_score:{best_score}"

                                _best_effort_find_segment_index()

                                # FALLBACK: if best-effort could not locate the bad segment,
                                # run an automatic per-segment check on all LaTeX-containing
                                # segments and pick the first one that fails.
                                diagnosis_entries = []
                                if segment_index is None:
                                    try:
                                        from utils.latex_repair_payload import has_latex_content
                                        from utils.latex_formula_checker import check_segment_pdf_compat

                                        latex_segs = [
                                            seg for seg in segs
                                            if isinstance(seg, dict)
                                            and has_latex_content(
                                                seg.get("modified_text") or seg.get("target_text") or ""
                                            )
                                        ]

                                        # First, try to reuse cached pdf_compat_results (from batch-test-pdf-compat)
                                        cached_results = task_state.get("pdf_compat_results")
                                        has_cache = isinstance(cached_results, dict) and cached_results

                                        for seg in latex_segs:
                                            seg_idx = seg.get("segment_index", -1)
                                            text = seg.get("modified_text") or seg.get("target_text") or ""
                                            preview = (text or "").replace("\n", " ")[:120]

                                            # Prefer cached result to avoid redundant pandoc calls
                                            if has_cache:
                                                cached = cached_results.get(str(seg_idx)) or cached_results.get(seg_idx)
                                                if isinstance(cached, dict):
                                                    passed = cached.get("passed", False)
                                                    status = "PASS" if passed else "FAIL"
                                                    message = cached.get("message", "")
                                                else:
                                                    passed = True
                                                    status = "PASS"
                                                    message = ""
                                            else:
                                                pre = check_segment_pdf_compat(text, segment_index=seg_idx)
                                                passed = pre.passed
                                                status = "PASS" if passed else "FAIL"
                                                message = pre.message

                                            diagnosis_entries.append({
                                                "segment_index": seg_idx,
                                                "status": status,
                                                "preview": preview + ("..." if len(text) > 120 else ""),
                                                "message": message,
                                                "from_cache": has_cache,
                                            })

                                            if not passed and segment_index is None:
                                                segment_index = seg_idx
                                                match_basis = "auto_diagnose"

                                        # Build human-readable diagnosis log
                                        diag_lines = [
                                            f"Auto-diagnosis: {len(latex_segs)} LaTeX segment(s) checked "
                                            f"({'cached' if has_cache else 'live'}):"
                                        ]
                                        for entry in diagnosis_entries:
                                            diag_lines.append(
                                                f"  SEG {entry['segment_index']}: [{entry['status']}] {entry['preview']}"
                                            )
                                        if segment_index is not None:
                                            diag_lines.append(
                                                f"  >>> FIRST FAILING SEGMENT: {segment_index}"
                                            )
                                        else:
                                            diag_lines.append(
                                                "  >>> No failing segment found among checked ones."
                                            )

                                        self.task_manager.add_log(
                                            task_id,
                                            "warning",
                                            "\n".join(diag_lines),
                                        )
                                        logger.warning(
                                            LogModule.EXPORT,
                                            f"[PDF-EXPORT] Task {task_id}: Auto-diagnosis completed. "
                                            f"checked={len(latex_segs)}, first_fail={segment_index}, "
                                            f"cached={has_cache}",
                                        )
                                    except Exception as diag_err:
                                        logger.debug(
                                            LogModule.EXPORT,
                                            f"[PDF-EXPORT] Task {task_id}: Auto-diagnosis failed: {diag_err}",
                                        )

                                if isinstance(segment_index, int) and segment_index >= 0:
                                    candidates.append(segment_index)
                                    for d in (1, 2, 3):
                                        if segment_index - d >= 0:
                                            candidates.append(segment_index - d)

                                task_state["pdf_export_latex_issue"] = {
                                    "error_type": e.error_type,
                                    "line_no": e.line_no,
                                    "segment_index": segment_index,
                                    "candidate_segment_indices": candidates,
                                    "match_basis": match_basis,
                                    "error_token": getattr(e, "error_token", "") or "",
                                    "md_snippet": e.md_snippet,
                                    "tex_snippet": e.tex_snippet,
                                    "stderr_excerpt": (e.stderr or "")[:2000],
                                    "debug_tex_path": str(e.debug_tex_path) if e.debug_tex_path else None,
                                    "debug_md_path": str(e.debug_md_path) if e.debug_md_path else None,
                                    "diagnosis": diagnosis_entries,
                                }
                                self.task_manager.add_log(
                                    task_id,
                                    "warning",
                                    f"[PDF-EXPORT] LaTeX compilation failed. Suggested segment to fix: {segment_index}. "
                                    "Please use the segment 'Fix formula' action to repair and retry export.",
                                )
                                logger.warning(
                                    LogModule.EXPORT,
                                    f"[PDF-EXPORT] Task {task_id}: LaTeX compile failed; segment_index={segment_index}, "
                                    f"candidates={candidates}, basis={match_basis}, error_type={e.error_type}, line={e.line_no}",
                                )
                                ok = False
                            else:
                                raise
                        except Exception:
                            raise

                    if ok:
                        if pdf_file.exists():
                            if "downloadable_files" not in task_state:
                                task_state["downloadable_files"] = {}
                            task_state["downloadable_files"]["pdf"] = {
                                "path": str(pdf_file),
                                "filename": f"{file_stem}_translated.pdf",
                            }
                            self.task_manager.add_log(task_id, "success", "PDF file generated via Pandoc+XeLaTeX (formulas preserved).")
                            logger.info(LogModule.EXPORT, f"[OUTPUT-GENERATOR] PDF generation completed for task {task_id} (pandoc, markdown_based)")
                            return
                    self.task_manager.add_log(
                        task_id,
                        "warning",
                        "Pandoc PDF output missing or failed for markdown_based workflow; PDF will not be generated.",
                    )
                    logger.warning(
                        LogModule.EXPORT,
                        f"[OUTPUT-GENERATOR] Task {task_id}: Pandoc PDF output missing or failed (markdown_based); skipping PDF generation.",
                    )
                    return
                except Exception as e:
                    self.task_manager.add_log(
                        task_id,
                        "warning",
                        f"PDF generation failed for markdown_based workflow: {e}",
                    )
                    logger.warning(
                        LogModule.EXPORT,
                        f"[OUTPUT-GENERATOR] Task {task_id}: PDF generation failed for markdown_based workflow: {e}",
                        exc_info=True,
                    )
                    return
            
            # 其他非 markdown_based 工作流继续使用原有布局/HTML 的 PDF 生成逻辑
            from app.services.download.pdf_generator import PDFGenerator
            pdf_generator = PDFGenerator(self.task_manager)
            await pdf_generator.generate(
                workflow,
                output_dir,
                file_stem,
                task_state,
                task_id,
                table_body_format=None,
                equation_format=None,
            )
            
            logger.info(LogModule.EXPORT, f"[OUTPUT-GENERATOR] PDF generation completed for task {task_id}")
            self.task_manager.add_log(task_id, "success", "PDF file generated successfully")
        except Exception as e:
            err_str = str(e)
            if "Layout document not available" in err_str:
                logger.warning(LogModule.EXPORT, f"[OUTPUT-GENERATOR] Task {task_id}: PDF not generated (no layout, expected for non-PDF sources): {e}")
            else:
                logger.error(LogModule.EXPORT, f"[OUTPUT-GENERATOR] PDF generation failed for task {task_id}: {e}", exc_info=True)
            self.task_manager.add_log(task_id, "warning", f"Could not generate PDF: {err_str}")
            # Don't fail the entire task if PDF generation fails
            # The task can still be completed with other files

