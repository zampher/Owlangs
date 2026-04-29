# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

"""
Workflow Executor

Handles workflow execution (convert, translate) and output generation.
"""

import os
import pathlib
import inspect
from typing import Any, Dict, Optional, Callable

from logger import unified_logger as logger
from logger.logger import LogModule
from backend.app.services.task import TaskManager


class WorkflowExecutor:
    """Service for executing workflows and generating outputs."""
    
    def __init__(self, task_manager: TaskManager):
        """
        Initialize workflow executor.
        
        Args:
            task_manager: Task manager instance
        """
        self.task_manager = task_manager
    
    async def execute_convert(
        self,
        task_id: str,
        workflow: Any,
        payload: Any,
        task_state: Dict[str, Any]
    ):
        """
        Execute format conversion (convert without translation).
        
        Args:
            task_id: Task identifier
            workflow: Workflow instance
            payload: Task payload
            task_state: Task state dictionary
        """
        workflow_type = getattr(payload, 'workflow_type', None)
        logger.info(LogModule.WORKFLOW, f"[WORKFLOW-EXECUTOR] Starting format conversion: task_id={task_id}, workflow_type={workflow_type}")
        
        # Restore MinerU attachment if needed (for PDF files)
        is_pdf_file = task_state.get("original_filename", "").lower().endswith('.pdf')
        if is_pdf_file:
            self._restore_mineru_attachment(workflow, task_state, task_id)
        
        # Check if workflow supports convert_without_translation_async (only markdown_based workflows have this)
        from workflow.md_based_workflow import MarkdownBasedWorkflow
        is_markdown_based = isinstance(workflow, MarkdownBasedWorkflow)
        
        if is_markdown_based:
            # For images: notify user that OCR is running to extract text for later translation
            original_name = (task_state.get("original_filename") or "").lower()
            if original_name.endswith((".jpg", ".jpeg", ".png")):
                self.task_manager.add_log(
                    task_id, "info",
                    "Image detected. Running MinerU OCR to extract text; you can translate after extraction.",
                )
            # For markdown_based workflows (PDF/image), call convert_without_translation_async
            try:
                await workflow.convert_without_translation_async()
                logger.info(LogModule.WORKFLOW, f"[WORKFLOW-EXECUTOR] Format conversion completed: task_id={task_id}")
                self.task_manager.add_log(task_id, "info", "Converted document to Markdown (format conversion without translation)")
            except RuntimeError as convert_error:
                # RuntimeError from md_based_workflow.py indicates layout_document loading failure
                # This is a fatal error for PDF files
                error_msg = str(convert_error)
                logger.error(LogModule.WORKFLOW, f"[WORKFLOW-EXECUTOR] Format conversion failed: task_id={task_id}, workflow_type={workflow_type}, error={error_msg}")
                self.task_manager.add_log(task_id, "error", f"PDF format conversion failed: {error_msg}")
                task_state["error"] = error_msg
                task_state["error_flag"] = True
                from fastapi import HTTPException
                raise HTTPException(status_code=500, detail=error_msg)
            except Exception as convert_error:
                logger.error(LogModule.WORKFLOW, f"[WORKFLOW-EXECUTOR] Format conversion failed: task_id={task_id}, workflow_type={workflow_type}, error={convert_error}", exc_info=True)
                raise
        else:
            # For other workflows (DOCX, PPTX, HTML, etc.), format conversion doesn't require conversion
            # The file is already in the target format. We just need to ensure skip_translate=True
            # and the workflow is ready for export. The file has already been read into workflow.document_original
            logger.info(LogModule.WORKFLOW, f"[WORKFLOW-EXECUTOR] Format conversion for {workflow_type} workflow: file already in target format, no conversion needed")
            self.task_manager.add_log(task_id, "info", f"Format conversion for {workflow_type} workflow: file ready for export")
            
            # Ensure document_translated is set to document_original for format conversion
            # This allows export methods to work correctly
            if hasattr(workflow, 'document_original') and workflow.document_original:
                if not hasattr(workflow, 'document_translated') or workflow.document_translated is None:
                    workflow.document_translated = workflow.document_original
                    logger.debug(LogModule.CONVERT, f"[WORKFLOW-EXECUTOR] Set document_translated to document_original for {workflow_type} format conversion")
            
            # CRITICAL: For MOBI workflows, extract images during format conversion
            # This is needed for HTML export to display images correctly
            if workflow_type == "mobi":
                self._extract_mobi_images_for_format_conversion(task_id, workflow, task_state)
        
        # Sync workflow attachments after conversion
        self._sync_workflow_attachments(task_id, workflow, task_state, reason="convert_only")
    
    async def execute_translate(
        self,
        task_id: str,
        workflow: Any,
        payload: Any,
        original_filename: str,
        temp_dir: str,
        task_state: Dict[str, Any]
    ):
        """
        Execute translation.
        
        Args:
            task_id: Task identifier
            workflow: Workflow instance
            payload: Task payload
            original_filename: Original filename
            temp_dir: Temporary directory path
            task_state: Task state dictionary
        """
        workflow_type = getattr(payload, 'workflow_type', None)
        logger.info(LogModule.WORKFLOW, f"[WORKFLOW-EXECUTOR] Starting translation: task_id={task_id}, workflow_type={workflow_type}")
        
        # Restore MinerU attachment if needed (for PDF files)
        is_pdf_file = original_filename.lower().endswith('.pdf')
        if is_pdf_file:
            self._restore_mineru_attachment(workflow, task_state, task_id)
        
        # Create progress callback for translation - map translation progress to 10%-90%
        last_logged_progress = {'completed': -1, 'mapped_percent': -1}
        
        def translation_progress_callback(completed: int, total: int, percent: int):
            # CRITICAL: Log every call to confirm callback is being invoked
            logger.info(LogModule.TRANS, f"[WORKFLOW-EXECUTOR] translation_progress_callback CALLED: task_id={task_id}, completed={completed}, total={total}, percent={percent}")
            
            # CRITICAL: If translation is 100% complete, update progress to 100%
            # Note: We do NOT set status=completed here, as _after_translate still needs to run
            # to check translation success/failure and perform necessary post-processing
            if completed == total and percent >= 100:
                old_progress = task_state.get("progress", 0)
                task_state["progress"] = 100
                task_state["message"] = "Translation completed, performing post-processing..."
                flow_id = task_state.get("flow_id", "N/A")
                logger.info(
                    LogModule.TRANS,
                    f"[WORKFLOW-EXECUTOR] Translation 100% complete: task_id={task_id}, flow_id={flow_id}, {completed}/{total} chunks, "
                    f"updating progress to 100% (status remains 'processing' until _after_translate completes)"
                )
                last_logged_progress['completed'] = completed
                last_logged_progress['mapped_percent'] = 100
                return
            
            # Map translation progress (0%-100%) to overall progress (10%-90%)
            mapped_percent = 10 + int(percent * 0.8)  # Map 0-100 to 10-90
            # CRITICAL: Update task_state immediately to ensure progress is visible to API calls
            old_progress = task_state.get("progress", 0)
            # Ensure progress never decreases (monotonically increasing).
            # Previous phases (Extract, Detect Language) may have already set a higher value.
            if mapped_percent < old_progress:
                task_state["message"] = f"Translating... {completed}/{total} chunks ({mapped_percent}%)"
                logger.debug(LogModule.TRANS, f"[WORKFLOW-EXECUTOR] Translation progress mapped to {mapped_percent}% but current progress is {old_progress}%, keeping current progress to avoid frontend confusion")
            else:
                task_state["progress"] = mapped_percent
                task_state["message"] = f"Translating... {completed}/{total} chunks ({mapped_percent}%)"
            
            # Log INFO when progress actually changes (changed from DEBUG to INFO for visibility)
            if (completed != last_logged_progress['completed'] or 
                mapped_percent != last_logged_progress['mapped_percent']):
                # Get flow_id from task_state if available (for debugging)
                flow_id = task_state.get("flow_id", "N/A")
                effective_progress = task_state.get('progress', mapped_percent)
                logger.info(LogModule.TRANS, f"[WORKFLOW-EXECUTOR] Translation progress: task_id={task_id}, flow_id={flow_id}, {completed}/{total} chunks ({mapped_percent}%), old_progress={old_progress}, effective_progress={effective_progress}")
                last_logged_progress['completed'] = completed
                last_logged_progress['mapped_percent'] = mapped_percent
        
        # Set status to "processing" when starting to send requests to AI platform
        task_state["status"] = "processing"
        task_state["message"] = "Sending translation requests to AI platform..."
        # NOTE: Do NOT force reset progress to 10 here. Previous phases (Extract/Detect Language)
        # may have already set a higher progress value. The translation_progress_callback
        # will ensure progress only moves forward (monotonically increasing).
        logger.info(LogModule.WORKFLOW, f"[WORKFLOW-EXECUTOR] Set status to 'processing' for task {task_id} (starting AI platform requests), current_progress={task_state.get('progress', 0)}")
        
        # Execute the translation with optional progress callback
        if hasattr(workflow, 'translate_async'):
            sig = inspect.signature(workflow.translate_async)
            logger.info(LogModule.WORKFLOW, f"[WORKFLOW-EXECUTOR] translate_async signature: task_id={task_id}, sig={sig}, params={list(sig.parameters.keys())}")
            kwargs = {}
            if 'progress_callback' in sig.parameters:
                kwargs['progress_callback'] = translation_progress_callback
                logger.info(LogModule.WORKFLOW, f"[WORKFLOW-EXECUTOR] Passing progress_callback to translate_async: task_id={task_id}, callback={translation_progress_callback}")
            else:
                logger.warning(LogModule.WORKFLOW, f"[WORKFLOW-EXECUTOR] translate_async does not accept progress_callback parameter: task_id={task_id}, sig={sig.parameters.keys()}, workflow_type={workflow_type}, workflow_class={type(workflow).__name__}")
            if 'task_id' in sig.parameters:
                kwargs['task_id'] = task_id
            if 'task_state' in sig.parameters:
                kwargs['task_state'] = task_state
            if 'original_filename' in sig.parameters:
                kwargs['original_filename'] = original_filename
            if 'workflow_type' in sig.parameters:
                kwargs['workflow_type'] = workflow_type
            if 'temp_dir' in sig.parameters:
                kwargs['temp_dir'] = temp_dir  # Pass temp_dir for PPTX workflow
            
            try:
                await workflow.translate_async(**kwargs)
                logger.info(LogModule.WORKFLOW, f"[WORKFLOW-EXECUTOR] Translation completed: task_id={task_id}")
            except Exception as translate_error:
                logger.error(LogModule.WORKFLOW, f"[WORKFLOW-EXECUTOR] Translation failed: task_id={task_id}, workflow_type={workflow_type}, error={translate_error}", exc_info=True)
                raise
        else:
            # Synchronous translate fallback
            # Set status to "processing" when starting to send requests to AI platform
            task_state["status"] = "processing"
            task_state["message"] = "Sending translation requests to AI platform..."
            logger.info(LogModule.WORKFLOW, f"[WORKFLOW-EXECUTOR] Set status to 'processing' for task {task_id} (starting AI platform requests, sync mode)")
            
            if hasattr(workflow, 'translate'):
                workflow.translate()
            else:
                logger.warning(LogModule.WORKFLOW, f"[WORKFLOW-EXECUTOR] Workflow {workflow_type} has no translate method")
        
        # CRITICAL: Log that execute_translate is about to sync attachments and update progress
        logger.info(LogModule.WORKFLOW, f"[WORKFLOW-EXECUTOR] Task {task_id}: Translation phase completed, syncing attachments and updating progress")
        
        # Sync workflow attachments after translation
        logger.info(LogModule.WORKFLOW, f"[WORKFLOW-EXECUTOR] Task {task_id}: Syncing workflow attachments after translation")
        self._sync_workflow_attachments(task_id, workflow, task_state, reason="post_translate")
        logger.info(LogModule.WORKFLOW, f"[WORKFLOW-EXECUTOR] Task {task_id}: Workflow attachments synced")
        
        # Update progress
        logger.info(LogModule.WORKFLOW, f"[WORKFLOW-EXECUTOR] Task {task_id}: Updating progress to 100% and setting message")
        self.task_manager.add_log(task_id, "info", "Translation completed, generating outputs...")
        if task_state["progress"] < 100:
            task_state["progress"] = 100
        task_state["message"] = "Generating output files..."
        logger.info(LogModule.WORKFLOW, f"[WORKFLOW-EXECUTOR] Task {task_id}: execute_translate completed successfully, returning to process_translation_task")
    
    def _restore_mineru_attachment(
        self,
        workflow: Any,
        task_state: Dict[str, Any],
        task_id: str
    ):
        """
        Restore MinerU attachment to workflow if available in task_state.
        
        This is needed for PDF files when using cached conversion results.
        """
        # First, check if layout_source_zip exists in task_state (from previous conversion)
        layout_source_zip = task_state.get("layout_source_zip")
        if layout_source_zip and not workflow.attachment.attachment_dict.get("mineru"):
            try:
                from ir.document import Document
                mineru_doc = Document.from_bytes(content=layout_source_zip, suffix=".zip", stem="mineru")
                workflow.attachment.add_document("mineru", mineru_doc)
                workflow._layout_source_zip = layout_source_zip
                logger.info(LogModule.WORKFLOW, f"[WORKFLOW-EXECUTOR] Restored MinerU ZIP from layout_source_zip to workflow for task {task_id} (cached conversion)")
            except Exception as restore_error:
                logger.debug(LogModule.EXTRACT, f"[WORKFLOW-EXECUTOR] Failed to restore MinerU ZIP from layout_source_zip: {restore_error}")
        
        # Also check existing attachments
        existing_attachments = task_state.get("attachments", {})
        if "mineru" in existing_attachments and not workflow.attachment.attachment_dict.get("mineru"):
            mineru_attachment = existing_attachments["mineru"]
            try:
                if hasattr(mineru_attachment, "content") and mineru_attachment.content:
                    from ir.document import Document
                    mineru_doc = Document.from_bytes(content=mineru_attachment.content, suffix=".zip", stem="mineru")
                    workflow.attachment.add_document("mineru", mineru_doc)
                    workflow._layout_source_zip = mineru_attachment.content
                    logger.info(LogModule.WORKFLOW, f"[WORKFLOW-EXECUTOR] Restored MinerU attachment to workflow from task_state for task {task_id}")
                elif hasattr(mineru_attachment, "document") and hasattr(mineru_attachment.document, "content"):
                    workflow.attachment.add_document("mineru", mineru_attachment.document)
                    workflow._layout_source_zip = mineru_attachment.document.content
                    logger.info(LogModule.WORKFLOW, f"[WORKFLOW-EXECUTOR] Restored MinerU document to workflow from task_state for task {task_id}")
            except Exception as restore_error:
                logger.debug(LogModule.EXTRACT, f"[WORKFLOW-EXECUTOR] Failed to restore MinerU attachment from task_state: {restore_error}")
    
    def _sync_workflow_attachments(
        self,
        task_id: str,
        workflow: Any,
        task_state: Dict[str, Any],
        reason: str
    ):
        """
        Sync workflow attachments to task_state.
        
        Persist workflow attachments (e.g., MinerU ZIP) into task_state.
        """
        try:
            if workflow is None or not hasattr(workflow, "attachment"):
                return
            attachment_manager = getattr(workflow, "attachment", None)
            if not attachment_manager:
                return
            attachment_dict = getattr(attachment_manager, "attachment_dict", {})
            if not attachment_dict:
                return
            
            # Store attachment documents in task_state for downstream usage (e.g., layout images)
            task_state["attachments"] = dict(attachment_dict)
            mineru_doc = attachment_dict.get("mineru")
            if mineru_doc and hasattr(mineru_doc, "content") and mineru_doc.content:
                task_state["layout_source_zip"] = mineru_doc.content
                logger.debug(LogModule.EXTRACT, f"[WORKFLOW-EXECUTOR] Stored MinerU ZIP bytes for task {task_id} (reason={reason})")
                
                # Extract MinerU ZIP to task's temp directory for easy access
                temp_dir = task_state.get("temp_dir")
                if temp_dir and os.path.isdir(temp_dir):
                    try:
                        import zipfile
                        import io
                        mineru_zip_path = os.path.join(temp_dir, "mineru_layout.zip")
                        mineru_extract_dir = os.path.join(temp_dir, "mineru_extracted")
                        
                        # Save ZIP file to temp directory
                        with open(mineru_zip_path, 'wb') as f:
                            f.write(mineru_doc.content)
                        logger.debug(LogModule.EXTRACT, f"[WORKFLOW-EXECUTOR] Saved MinerU ZIP to {mineru_zip_path}")
                        
                        # Extract ZIP contents to mineru_extracted subdirectory
                        os.makedirs(mineru_extract_dir, exist_ok=True)
                        with zipfile.ZipFile(io.BytesIO(mineru_doc.content), 'r') as zip_ref:
                            zip_ref.extractall(mineru_extract_dir)
                        logger.debug(LogModule.EXTRACT, f"[WORKFLOW-EXECUTOR] Extracted MinerU ZIP to {mineru_extract_dir}")
                        
                        # Store paths in task_state for reference
                        task_state["mineru_zip_path"] = mineru_zip_path
                        task_state["mineru_extract_dir"] = mineru_extract_dir
                    except Exception as extract_error:
                        logger.warning(LogModule.WORKFLOW, f"[WORKFLOW-EXECUTOR] Failed to extract MinerU ZIP to temp directory: {extract_error}")
        except Exception as attachment_error:
            logger.debug(LogModule.EXTRACT, f"[WORKFLOW-EXECUTOR] Failed to sync workflow attachments ({reason}): {attachment_error}")
    
    def _extract_title_from_html(self, html_content: bytes) -> Optional[str]:
        """
        Extract title from HTML content.
        Tries to find title in <title> tag or first <h1> tag.
        Returns None if no title is found.
        """
        try:
            from bs4 import BeautifulSoup
            html_str = html_content.decode('utf-8', errors='ignore')
            soup = BeautifulSoup(html_str, 'html.parser')
            
            # Try to get title from <title> tag
            title_tag = soup.find('title')
            if title_tag and title_tag.string:
                title_text = title_tag.string.strip()
                if title_text and title_text.lower() not in ('untitled', 'mobi content'):
                    return title_text
            
            # Try to get title from first <h1> tag
            h1_tag = soup.find('h1')
            if h1_tag:
                h1_text = h1_tag.get_text(strip=True)
                if h1_text and h1_text.lower() not in ('untitled', 'mobi content'):
                    return h1_text
            
            # Try to get title from first heading (h1-h6)
            for tag_name in ['h1', 'h2', 'h3', 'h4', 'h5', 'h6']:
                heading = soup.find(tag_name)
                if heading:
                    heading_text = heading.get_text(strip=True)
                    if heading_text and heading_text.lower() not in ('untitled', 'mobi content'):
                        return heading_text
            
            return None
        except Exception as e:
            logger.debug(LogModule.TRANS, f"[WORKFLOW_EXECUTOR] Failed to extract title from HTML: {e}")
            return None

    def _extract_author_from_html(self, html_content: bytes) -> Optional[str]:
        """
        Extract author from HTML content.
        Tries <meta name="author" content="...">, then Dublin Core <meta name="DC.creator" content="...">.
        Returns None if no author is found.
        """
        try:
            from bs4 import BeautifulSoup
            html_str = html_content.decode("utf-8", errors="ignore")
            soup = BeautifulSoup(html_str, "html.parser")
            meta = soup.find("meta", attrs={"name": "author"})
            if meta and meta.get("content"):
                return meta["content"].strip() or None
            meta = soup.find("meta", attrs={"name": "DC.creator"})
            if meta and meta.get("content"):
                return meta["content"].strip() or None
            meta = soup.find("meta", attrs={"property": "author"})
            if meta and meta.get("content"):
                return meta["content"].strip() or None
            return None
        except Exception as e:
            logger.debug(LogModule.TRANS, f"[WORKFLOW_EXECUTOR] Failed to extract author from HTML: {e}")
            return None

    def _extract_mobi_images_for_format_conversion(
        self,
        task_id: str,
        workflow: Any,
        task_state: Dict[str, Any]
    ):
        """
        Extract images from MOBI file during format conversion.
        This is needed for HTML export to display images correctly.
        
        Args:
            task_id: Task identifier
            workflow: Workflow instance (MobiWorkflow)
            task_state: Task state dictionary
        """
        try:
            import ebooklib
            from ebooklib import epub
            import base64
            import mimetypes
            from io import BytesIO
            
            # Get document content from workflow
            if not hasattr(workflow, 'document_original') or not workflow.document_original:
                logger.warning(LogModule.WORKFLOW, f"[WORKFLOW-EXECUTOR] Task {task_id}: No document_original in workflow for image extraction")
                return
            
            document = workflow.document_original
            content_bytes = document.content if hasattr(document, 'content') else None
            
            if not content_bytes:
                logger.warning(LogModule.WORKFLOW, f"[WORKFLOW-EXECUTOR] Task {task_id}: No content in document_original for image extraction")
                return
            
            # Read MOBI/EPUB file
            book = None
            try:
                # Try using mobi library first
                import mobi
                import tempfile
                import os
                import shutil
                temp_file = None
                bookpath = None
                
                try:
                    # Create temporary file for mobi library
                    with tempfile.NamedTemporaryFile(delete=False, suffix='.mobi') as tmp:
                        tmp.write(content_bytes)
                        temp_file = tmp.name
                    
                    # Extract MOBI file
                    bookpath, epubpath = mobi.extract(temp_file)
                    
                    # CRITICAL: Initialize variables before use
                    epub_file_path = None
                    html_file_path = None
                    
                    # Check what was extracted
                    # bookpath is the directory where files were extracted
                    # epubpath might point to an HTML file, EPUB file, or other format
                    if epubpath and os.path.exists(epubpath):
                        # Check if it's an EPUB file (ZIP archive)
                        if epubpath.lower().endswith('.epub'):
                            try:
                                import zipfile
                                # Verify it's a valid ZIP/EPUB
                                with zipfile.ZipFile(epubpath, 'r') as zf:
                                    epub_file_path = epubpath
                            except (zipfile.BadZipFile, Exception) as zip_error:
                                # Not a valid EPUB, might be HTML or other format
                                # Log for debugging but continue to check for HTML
                                logger.debug(
                                    LogModule.WORKFLOW,
                                    f"[WORKFLOW-EXECUTOR] Task {task_id}: epubpath points to invalid EPUB: {epubpath}, error: {zip_error}"
                                )
                        
                        # Check if it's an HTML file (check extension first, then content)
                        if epubpath.lower().endswith('.html') or epubpath.lower().endswith('.htm'):
                            html_file_path = epubpath
                        elif not epub_file_path:
                            # If not EPUB and extension doesn't indicate HTML, check file content
                            # Some MOBI files extract to files without .html extension
                            try:
                                with open(epubpath, 'rb') as f:
                                    content_start = f.read(1024).decode('utf-8', errors='ignore').lower()
                                    if '<html' in content_start or '<!doctype html' in content_start:
                                        html_file_path = epubpath
                                        logger.debug(
                                            LogModule.WORKFLOW,
                                            f"[WORKFLOW-EXECUTOR] Task {task_id}: Detected HTML file by content: {epubpath}"
                                        )
                            except Exception:
                                pass
                    
                    # If no EPUB found, look for EPUB files in the extracted directory
                    if not epub_file_path and bookpath and os.path.isdir(bookpath):
                        for root, dirs, files in os.walk(bookpath):
                            for file in files:
                                if file.lower().endswith('.epub'):
                                    try:
                                        import zipfile
                                        epub_candidate = os.path.join(root, file)
                                        # Verify it's a valid EPUB
                                        with zipfile.ZipFile(epub_candidate, 'r') as zf:
                                            epub_file_path = epub_candidate
                                            break
                                    except:
                                        continue
                            if epub_file_path:
                                break
                    
                    # If no EPUB found, look for HTML files in the extracted directory
                    if not epub_file_path and not html_file_path and bookpath and os.path.isdir(bookpath):
                        for root, dirs, files in os.walk(bookpath):
                            for file in files:
                                if file.lower().endswith('.html') or file.lower().endswith('.htm'):
                                    html_file_path = os.path.join(root, file)
                                    break
                            if html_file_path:
                                break
                    
                    # Read the content
                    # CRITICAL: Read file content BEFORE cleanup to avoid "Bad Zip file" errors
                    if epub_file_path:
                        # Read EPUB file - read content immediately before cleanup
                        try:
                            book = epub.read_epub(epub_file_path)
                        except Exception as epub_read_error:
                            # If reading fails, try to read file content first, then parse
                            # This ensures file is not deleted before reading
                            raise ValueError(
                                f"Failed to read EPUB file from MOBI extraction. "
                                f"EPUB path: {epub_file_path}, Error: {epub_read_error}"
                            )
                    elif html_file_path:
                        # Read HTML file directly - mobi library extracted HTML content
                        # Read content immediately before cleanup
                        with open(html_file_path, 'rb') as f:
                            html_content = f.read()
                        
                        # Try to extract title from HTML content
                        title_text = self._extract_title_from_html(html_content)
                        # No fallback - if no title found, use empty string or None
                        # Some MOBI documents don't have titles, which is acceptable
                        
                        # Create a new EPUB book from HTML content
                        book = epub.EpubBook()
                        # Add a chapter with the HTML content
                        chapter = epub.EpubHtml(
                            title='Content',
                            file_name='content.xhtml',
                            lang='en'
                        )
                        from utils.epub_fix import sanitize_html_for_epub
                        chapter.content = sanitize_html_for_epub(html_content.decode("utf-8", errors="replace") if isinstance(html_content, bytes) else html_content)
                        if isinstance(chapter.content, str):
                            chapter.content = chapter.content.encode("utf-8")
                        book.add_item(chapter)
                        # Add chapter to spine. Do not add 'nav' unless we add an actual nav item to the book,
                        # otherwise Apple Books (and other strict readers) will reject the EPUB.
                        book.spine = [chapter]
                        # Set metadata (dc:title required by EPUB; post-process adds nav)
                        book.set_identifier('mobi-html-conversion')
                        book.set_title(title_text if title_text else "Untitled")
                        author_from_html = self._extract_author_from_html(html_content)
                        if author_from_html:
                            book.add_metadata("DC", "creator", author_from_html)
                        else:
                            # Fallback: try reading original MOBI with ebooklib to get metadata
                            try:
                                book_meta = epub.read_epub(BytesIO(content_bytes))
                                creator_val = book_meta.get_metadata("DC", "creator")
                                author_fallback = (creator_val[0][0] if creator_val and creator_val[0] else None) or None
                                if isinstance(author_fallback, str) and author_fallback.strip():
                                    book.add_metadata("DC", "creator", author_fallback.strip())
                            except Exception:
                                pass
                        book.set_language('en')
                        
                        # CRITICAL: When extracting from HTML, images are in the bookpath directory
                        # We need to scan the directory and add images to the book object
                        if bookpath and os.path.isdir(bookpath):
                            # Common image extensions
                            image_extensions = ['.png', '.jpg', '.jpeg', '.gif', '.svg', '.webp', '.bmp']
                            for root, dirs, files in os.walk(bookpath):
                                for file in files:
                                    file_lower = file.lower()
                                    if any(file_lower.endswith(ext) for ext in image_extensions):
                                        try:
                                            img_path = os.path.join(root, file)
                                            with open(img_path, 'rb') as img_file:
                                                img_data = img_file.read()
                                            
                                            # Determine MIME type
                                            mime_type, _ = mimetypes.guess_type(file)
                                            if not mime_type:
                                                if img_data.startswith(b'\x89PNG'):
                                                    mime_type = 'image/png'
                                                elif img_data.startswith(b'\xff\xd8'):
                                                    mime_type = 'image/jpeg'
                                                elif img_data.startswith(b'GIF'):
                                                    mime_type = 'image/gif'
                                                elif img_data.startswith(b'<svg') or img_data.startswith(b'<?xml'):
                                                    mime_type = 'image/svg+xml'
                                                else:
                                                    mime_type = 'image/png'
                                            
                                            # Create relative path for image item name
                                            # Use relative path from bookpath to preserve directory structure
                                            rel_path = os.path.relpath(img_path, bookpath)
                                            # Normalize path separators for EPUB (use forward slashes)
                                            rel_path = rel_path.replace('\\', '/')
                                            
                                            # Create EpubItem for image
                                            img_item = epub.EpubItem(
                                                uid=rel_path,
                                                file_name=rel_path,
                                                media_type=mime_type,
                                                content=img_data
                                            )
                                            book.add_item(img_item)
                                            logger.debug(
                                                LogModule.WORKFLOW,
                                                f"[WORKFLOW-EXECUTOR] Task {task_id}: Added image from directory: {rel_path}, "
                                                f"size={len(img_data)} bytes, mime={mime_type}"
                                            )
                                        except Exception as img_file_error:
                                            logger.warning(
                                                LogModule.WORKFLOW,
                                                f"[WORKFLOW-EXECUTOR] Task {task_id}: Failed to add image {file} from directory: {img_file_error}",
                                                exc_info=True
                                            )
                                            continue
                    else:
                        # No valid file found
                        raise ValueError(
                            f"MOBI extraction did not produce a readable EPUB or HTML file. "
                            f"Extracted path: {epubpath}, Book path: {bookpath}"
                        )

                    # Clean up temporary file
                    if temp_file and os.path.exists(temp_file):
                        try:
                            os.unlink(temp_file)
                        except:
                            pass
                    # Clean up extracted directory
                    if bookpath and os.path.isdir(bookpath):
                        try:
                            import time
                            time.sleep(0.5)
                            shutil.rmtree(bookpath)
                        except:
                            pass
                except Exception as mobi_error:
                    # mobi library failed, try ebooklib as fallback
                    try:
                        book = epub.read_epub(BytesIO(content_bytes))
                    except Exception as epub_error:
                        logger.warning(
                            LogModule.WORKFLOW,
                            f"[WORKFLOW-EXECUTOR] Task {task_id}: Failed to read MOBI/EPUB for image extraction. "
                            f"mobi error: {mobi_error}, ebooklib error: {epub_error}",
                            exc_info=True
                        )
                        return
            except ImportError:
                # mobi library not available, try ebooklib directly
                try:
                    book = epub.read_epub(BytesIO(content_bytes))
                except Exception as e:
                    logger.warning(
                        LogModule.WORKFLOW,
                        f"[WORKFLOW-EXECUTOR] Task {task_id}: Failed to read MOBI/EPUB for image extraction: {e}",
                        exc_info=True
                    )
                    return
            
            if not book:
                logger.warning(LogModule.WORKFLOW, f"[WORKFLOW-EXECUTOR] Task {task_id}: Failed to read book object for image extraction")
                return

            # Extract full ebook metadata (title, author, language, identifier, etc.) for export
            try:
                from utils.ebook_metadata import extract_from_ebooklib_book
                meta = extract_from_ebooklib_book(book)
                if any(meta.get(k) for k in meta):
                    task_state["ebook_metadata"] = meta
                    logger.info(
                        LogModule.WORKFLOW,
                        "[WORKFLOW-EXECUTOR] Task %s: Saved ebook_metadata from format conversion (title, author, language, ...)" % task_id,
                    )
            except Exception as meta_err:
                logger.debug(
                    LogModule.WORKFLOW,
                    f"[WORKFLOW-EXECUTOR] Task {task_id}: Could not extract ebook metadata during format conversion: {meta_err}"
                )

            # Extract images
            image_data_map = {}
            for item in book.get_items():
                if item.get_type() == ebooklib.ITEM_IMAGE:
                    try:
                        img_data = item.get_content()
                        if img_data:
                            item_name = item.get_name() or ''
                            # Get MIME type
                            mime_type, _ = mimetypes.guess_type(item_name)
                            if not mime_type:
                                # Fallback: detect from content
                                if img_data.startswith(b'\x89PNG'):
                                    mime_type = 'image/png'
                                elif img_data.startswith(b'\xff\xd8'):
                                    mime_type = 'image/jpeg'
                                elif img_data.startswith(b'GIF'):
                                    mime_type = 'image/gif'
                                elif img_data.startswith(b'<svg') or img_data.startswith(b'<?xml'):
                                    mime_type = 'image/svg+xml'
                                else:
                                    mime_type = 'image/png'  # Default fallback
                            
                            # Convert to base64 data URI
                            img_base64 = base64.b64encode(img_data).decode('utf-8')
                            data_uri = f"data:{mime_type};base64,{img_base64}"
                            
                            # Store image data
                            image_key = item_name if item_name else item.get_id()
                            image_data_map[image_key] = {
                                "data": data_uri,
                                "mime": mime_type,
                                "size": len(img_data)
                            }
                    except Exception as img_error:
                        logger.warning(
                            LogModule.WORKFLOW,
                            f"[WORKFLOW-EXECUTOR] Task {task_id}: Failed to extract image {item.get_name()}: {img_error}",
                            exc_info=True
                        )
                        continue
            
            # CRITICAL: Extract HTML templates for image segment detection in preview
            # This is needed for frontend to display images in Extract preview and Exclusion statistics
            html_templates = {}  # item_id -> original_html_content
            try:
                for item in book.get_items():
                    if item.get_type() == ebooklib.ITEM_DOCUMENT:
                        item_id = item.get_id()
                        content = item.get_content()
                        if content:
                            # Decode content to string
                            if isinstance(content, bytes):
                                html_content = content.decode('utf-8', errors='ignore')
                            else:
                                html_content = str(content)
                            html_templates[item_id] = html_content
                
                # Save HTML templates to task_state
                if html_templates:
                    task_state['mobi_html_templates'] = html_templates
                    logger.info(
                        LogModule.CONVERT,
                        f"[WORKFLOW-EXECUTOR] Task {task_id}: Extracted {len(html_templates)} HTML templates during format conversion"
                    )
            except Exception as html_template_error:
                logger.warning(
                    LogModule.WORKFLOW,
                    f"[WORKFLOW-EXECUTOR] Task {task_id}: Failed to extract HTML templates during format conversion: {html_template_error}",
                    exc_info=True
                )
            
            # Save images to task_state
            if image_data_map:
                task_state['mobi_image_data_map'] = image_data_map
                task_state['image_data_map'] = image_data_map
                image_keys = list(image_data_map.keys())[:5]
                logger.info(
                    LogModule.WORKFLOW,
                    f"[WORKFLOW-EXECUTOR] Task {task_id}: Extracted {len(image_data_map)} images during format conversion. "
                    f"Sample image keys: {image_keys}"
                )
            else:
                logger.info(LogModule.WORKFLOW, f"[WORKFLOW-EXECUTOR] Task {task_id}: No images found in MOBI file during format conversion")
        except Exception as e:
            logger.warning(
                LogModule.WORKFLOW,
                f"[WORKFLOW-EXECUTOR] Task {task_id}: Failed to extract images during format conversion: {e}",
                exc_info=True
            )