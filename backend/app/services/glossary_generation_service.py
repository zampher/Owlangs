# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

"""
Glossary generation service for Owlangs.

This service handles standalone glossary generation from documents,
reusing translation parameters for consistency.
"""

import base64
import tempfile
import csv
from io import StringIO
from typing import Dict, List, Optional
from pathlib import Path

from logger import unified_logger as logger
from logger.logger import LogModule

from agents.glossary_agent import GlossaryAgent, GlossaryAgentConfig
from app.models.service import GenerateGlossaryRequest, GenerateGlossaryResponse
from backend.app.services.task import task_manager


class GlossaryGenerationService:
    """Service for generating glossaries from documents."""
    
    def __init__(self):
        self.logger = logger
    
    async def generate_glossary(self, request: GenerateGlossaryRequest, username: str) -> GenerateGlossaryResponse:
        """
        Generate glossary from document using translation parameters.
        
        If task_id is provided, will reuse chunks from Extract phase instead of extracting segments.
        This avoids redundant chunk generation and ensures consistency with Extract phase.
        
        Args:
            request: Glossary generation request
            username: Username for personal glossary saving
            
        Returns:
            GenerateGlossaryResponse with generated glossary
        """
        try:
            # Try to get chunks from Extract phase if task_id is provided
            chunks_text = None
            if request.task_id:
                task_state = task_manager.get_task(request.task_id)
                if task_state:
                    # Try to get chunks from layout_prepared_chunks (PDF workflow)
                    # CRITICAL: Use only non-excluded chunks to match frontend display (8 chunks)
                    # layout_prepared_chunks contains ALL chunks (including excluded), but we only want non-excluded ones
                    layout_chunks = task_state.get("layout_prepared_chunks")
                    if layout_chunks and isinstance(layout_chunks, list):
                        # Extract text from chunks (skip excluded chunks and chunks with only placeholders)
                        chunks_text = []
                        for chunk in layout_chunks:
                            if isinstance(chunk, dict):
                                chunk_text = chunk.get("text", "")
                                is_excluded = chunk.get("is_excluded", False)
                                is_image = chunk.get("is_image", False)
                                # Skip excluded and image chunks (to match frontend display)
                                if chunk_text.strip() and not is_excluded and not is_image:
                                    # Filter out chunks that only contain image placeholders
                                    # Remove placeholders and check if there's actual text left
                                    import re
                                    text_without_placeholders = re.sub(r'<ph-[^>]+>', '', chunk_text).strip()
                                    if text_without_placeholders:
                                        chunks_text.append(chunk_text)
                                    else:
                                        self.logger.debug(LogModule.GLOSSARY, f"Skipping chunk with only placeholders: {chunk_text[:100]}...")
                        
                        if chunks_text:
                            self.logger.info(LogModule.GLOSSARY,f"Using {len(chunks_text)} non-excluded chunks from Extract phase (task_id={request.task_id}, total layout_prepared_chunks={len(layout_chunks)})")
                    
                    # Fallback: try to get chunks from source_chunks_cache (other workflows)
                    if not chunks_text:
                        source_chunks_cache = task_state.get("source_chunks_cache", {})
                        cached_segments = source_chunks_cache.get("segments", [])
                        if cached_segments:
                            # Build chunks from cached segments using chunk_to_segment_map
                            chunk_to_segment_map = task_state.get("chunk_to_segment_map")
                            if chunk_to_segment_map and isinstance(chunk_to_segment_map, list):
                                chunks_text = []
                                for chunk_segment_indices in chunk_to_segment_map:
                                    if isinstance(chunk_segment_indices, list):
                                        # Merge segments in this chunk
                                        chunk_parts = []
                                        for seg_idx in chunk_segment_indices:
                                            if seg_idx < len(cached_segments):
                                                seg_text = cached_segments[seg_idx]
                                                if isinstance(seg_text, dict):
                                                    seg_text = seg_text.get("text", "")
                                                if seg_text and seg_text.strip():
                                                    chunk_parts.append(seg_text.strip())
                                        if chunk_parts:
                                            chunks_text.append("\n\n".join(chunk_parts))
                                
                                if chunks_text:
                                    self.logger.info(LogModule.GLOSSARY,f"Built {len(chunks_text)} chunks from cached segments using chunk_to_segment_map (task_id={request.task_id})")
            
            # If no chunks from Extract phase, extract segments from file
            if not chunks_text:
                # Decode file content
                file_content = base64.b64decode(request.file_content)
                
                # Determine workflow type based on file extension
                file_ext = Path(request.file_name).suffix.lower()
                workflow_type = self._get_workflow_type(file_ext)
                
                # Extract text from document
                text_segments = await self._extract_text_segments(
                    file_content, 
                    request.file_name, 
                    workflow_type
                )
                
                if not text_segments:
                    return GenerateGlossaryResponse(
                        success=False,
                        message="No text content found in document"
                    )
                
                # Convert segments to chunks_text for glossary agent
                # GlossaryAgent expects chunks (merged segments), not individual segments
                # We'll pass segments and let GlossaryAgent handle chunking
                chunks_text = text_segments  # GlossaryAgent will merge them internally
            
            # Create glossary agent config using translation parameters
            glossary_config = GlossaryAgentConfig(
                to_lang=request.to_lang,
                base_url=request.base_url,
                api_key=request.api_key,
                model_id=request.model_id,
                api_type=request.api_type or "openai",  # Pass API protocol type (openai/anthropic/ollama)
                temperature=request.temperature,
                thinking=request.thinking,
                concurrent=request.concurrent,
                connect_timeout=getattr(request, 'connect_timeout', 15),
                timeout=request.timeout,
                retry=request.retry,
                custom_prompt=request.custom_prompt,  # Pass user-defined custom prompt
                detection_mode=request.detection_mode,  # Pass detection mode: "uncertain" or "deep"
                logger=self.logger
            )
            
            # Generate glossary
            # If chunks_text came from Extract phase, they are already chunks (merged segments)
            # If chunks_text came from file extraction, they are segments (will be merged by GlossaryAgent)
            glossary_agent = GlossaryAgent(glossary_config)
            
            # Pass task_state to glossary_agent for debug file saving
            if request.task_id:
                task_state = task_manager.get_task(request.task_id)
                if task_state:
                    glossary_agent.task_state = task_state
            
            # Check if chunks came from Extract phase (indicated by task_id being provided)
            if request.task_id and chunks_text:
                # Chunks from Extract phase are already merged, use send_chunks_async to avoid re-merging
                self.logger.info(LogModule.GLOSSARY,f"Using pre-merged chunks from Extract phase: {len(chunks_text)} chunks, target_lang={request.to_lang}")
                glossary_dict = await glossary_agent.send_chunks_async(chunks_text, task_id=request.task_id)
            else:
                # Segments from file extraction, use send_segments_async to merge them
                self.logger.info(LogModule.GLOSSARY,f"Using segments from file extraction: {len(chunks_text)} segments, chunk_size={request.chunk_size}, target_lang={request.to_lang}")
                glossary_dict = await glossary_agent.send_segments_async(
                    chunks_text, 
                    request.chunk_size,
                    task_id=request.task_id
                )
            
            if not glossary_dict:
                self.logger.warning(LogModule.GLOSSARY, "No glossary terms generated from document")
                return GenerateGlossaryResponse(
                    success=False,
                    message="No glossary terms generated"
                )
            
            # Log generated glossary details
            self.logger.info(LogModule.GLOSSARY,f"Glossary generation completed: {len(glossary_dict)} terms extracted")
            if len(glossary_dict) > 0:
                # Log first 10 terms as sample
                sample_terms = list(glossary_dict.items())[:10]
                self.logger.info(LogModule.GLOSSARY, "Sample glossary terms (first 10):")
                for idx, (src, dst) in enumerate(sample_terms, 1):
                    self.logger.info(LogModule.GLOSSARY,f"  [{idx}] {src} -> {dst}")
                if len(glossary_dict) > 10:
                    self.logger.info(LogModule.GLOSSARY,f"  ... and {len(glossary_dict) - 10} more terms")
                
                # Log all terms if not too many (limit to 50 to avoid log spam)
                if len(glossary_dict) <= 50:
                    self.logger.info(LogModule.GLOSSARY, "Complete glossary terms:")
                    for idx, (src, dst) in enumerate(glossary_dict.items(), 1):
                        self.logger.info(LogModule.GLOSSARY,f"  [{idx}] {src} -> {dst}")
                else:
                    self.logger.info(LogModule.GLOSSARY,f"Complete glossary has {len(glossary_dict)} terms (too many to log all, showing first 10 above)")
            
            # Save to personal glossary if requested
            if request.save_to_personal:
                await self._save_to_personal_glossary(glossary_dict, username, request.to_lang)
            
            # Generate download URL if needed
            download_url = None
            if request.output_format == "csv":
                download_url = await self._generate_csv_download(glossary_dict, request.file_name, request.to_lang, request.task_id)
            
            # Final summary log
            self.logger.info(LogModule.GLOSSARY,f"Glossary generation summary: {len(glossary_dict)} terms, target_lang={request.to_lang}, save_to_personal={request.save_to_personal}")
            
            return GenerateGlossaryResponse(
                success=True,
                message=f"Glossary generated successfully with {len(glossary_dict)} terms",
                glossary=glossary_dict,
                item_count=len(glossary_dict),
                download_url=download_url
            )
            
        except Exception as e:
            self.logger.error(LogModule.GLOSSARY, f"Glossary generation failed: {e}")
            return GenerateGlossaryResponse(
                success=False,
                message=f"Glossary generation failed: {str(e)}"
            )
    
    def _get_workflow_type(self, file_ext: str) -> str:
        """Determine workflow type based on file extension."""
        ext_to_workflow = {
            '.pdf': 'markdown_based',
            '.docx': 'docx',
            '.doc': 'docx',
            '.txt': 'txt',
            '.md': 'markdown_based',
            '.html': 'html',
            '.xlsx': 'xlsx',
            '.xls': 'xlsx',
            '.srt': 'srt',
            '.epub': 'epub',
            '.mobi': 'mobi',
            '.azw': 'mobi',  # Kindle format
            '.json': 'json',
            '.ts': 'qt_ts',  # Qt translation source file
        }
        return ext_to_workflow.get(file_ext, 'markdown_based')
    
    async def _extract_text_segments(self, file_content: bytes, file_name: str, workflow_type: str) -> List[str]:
        """Extract text segments from document for glossary generation using extractors."""
        try:
            file_ext = Path(file_name).suffix.lower()
            
            # Use existing extractors for text extraction
            if file_ext == '.txt':
                # Direct text file reading
                text_content = file_content.decode('utf-8', errors='ignore')
                text_segments = [
                    line.strip() 
                    for line in text_content.split('\n') 
                    if line.strip() and len(line.strip()) > 10  # Filter out very short lines
                ]
                return text_segments
            
            elif file_ext == '.md':
                # Markdown file reading
                text_content = file_content.decode('utf-8', errors='ignore')
                from extractor.markdown_extractor import MarkdownExtractor
                extractor = MarkdownExtractor(text_content, chunk_size=3000)
                result = extractor.extract()
                # Filter out very short segments
                return [seg for seg in result.segments if seg.strip() and len(seg.strip()) > 10]
            
            elif file_ext in ['.docx', '.doc']:
                # Use DocxExtractor
                try:
                    from extractor.docx_extractor import DocxExtractor
                    extractor = DocxExtractor(file_content, chunk_size=3000)
                    result = extractor.extract()
                    # Filter out very short segments
                    return [seg for seg in result.segments if seg.strip() and len(seg.strip()) > 10]
                except Exception as e:
                    self.logger.error(LogModule.GLOSSARY, f"Error extracting text from .docx file: {e}")
                    return []
            
            elif file_ext in ['.xlsx', '.xls']:
                # Use XlsxExtractor
                try:
                    from extractor.xlsx_extractor import XlsxExtractor
                    extractor = XlsxExtractor(file_content, chunk_size=3000)
                    result = extractor.extract()
                    # Filter out very short segments and empty cells
                    return [seg for seg in result.segments if seg.strip() and len(seg.strip()) > 3]  # XLSX cells can be shorter
                except Exception as e:
                    self.logger.error(LogModule.GLOSSARY, f"Error extracting text from .xlsx file: {e}")
                    return []
            
            elif file_ext == '.html' or file_ext == '.htm':
                # Use HtmlExtractor
                try:
                    from extractor.html_extractor import HtmlExtractor
                    extractor = HtmlExtractor(file_content, chunk_size=3000)
                    result = extractor.extract()
                    # Filter out very short segments
                    return [seg for seg in result.segments if seg.strip() and len(seg.strip()) > 10]
                except Exception as e:
                    self.logger.error(LogModule.GLOSSARY, f"Error extracting text from .html file: {e}")
                    return []
            
            elif file_ext == '.srt':
                # Use SrtExtractor
                try:
                    from extractor.srt_extractor import SrtExtractor
                    extractor = SrtExtractor(file_content, chunk_size=3000)
                    result = extractor.extract()
                    # Filter out very short segments
                    return [seg for seg in result.segments if seg.strip() and len(seg.strip()) > 10]
                except Exception as e:
                    self.logger.error(LogModule.GLOSSARY, f"Error extracting text from .srt file: {e}")
                    return []
            
            elif file_ext == '.json':
                # Use JsonExtractor
                try:
                    from extractor.json_extractor import JsonExtractor
                    extractor = JsonExtractor(file_content, chunk_size=3000)
                    result = extractor.extract()
                    # Filter out very short segments
                    return [seg for seg in result.segments if seg.strip() and len(seg.strip()) > 10]
                except Exception as e:
                    self.logger.error(LogModule.GLOSSARY, f"Error extracting text from .json file: {e}")
                    return []
            
            elif file_ext == '.ts':
                # Use QtTsExtractor
                try:
                    from extractor.qt_ts_extractor import QtTsExtractor
                    extractor = QtTsExtractor(file_content, chunk_size=3000)
                    result = extractor.extract()
                    # Filter out very short segments
                    return [seg for seg in result.segments if seg.strip() and len(seg.strip()) > 10]
                except Exception as e:
                    self.logger.error(LogModule.GLOSSARY, f"Error extracting text from .ts file: {e}")
                    return []
            
            elif file_ext == '.pdf':
                # For PDF, use PyPDF2 for text extraction.
                try:
                    import PyPDF2
                    from io import BytesIO
                    pdf_reader = PyPDF2.PdfReader(BytesIO(file_content))
                    text_segments = []
                    for page in pdf_reader.pages:
                        page_text = page.extract_text()
                        if page_text and page_text.strip():
                            # Split by paragraphs (double newlines) and filter
                            paragraphs = [p.strip() for p in page_text.split('\n\n') if p.strip() and len(p.strip()) > 10]
                            text_segments.extend(paragraphs)
                    if text_segments:
                        self.logger.info(LogModule.GLOSSARY,f"Extracted {len(text_segments)} text segments from PDF using PyPDF2")
                        return text_segments
                except ImportError:
                    self.logger.warning(LogModule.GLOSSARY, "PyPDF2 not available for PDF text extraction")
                except Exception as e:
                    self.logger.warning(LogModule.GLOSSARY, f"PyPDF2 extraction failed: {e}")
                
                # If extraction fails, suggest format conversion
                self.logger.warning(LogModule.GLOSSARY, f"PDF text extraction failed. For better results, please use format conversion first (Convert button), or configure MinerU/Docling for advanced PDF parsing.")
                return []
            
            else:
                # For other formats, log warning and return empty
                self.logger.warning(LogModule.GLOSSARY, f"Text extraction not implemented for {file_ext} files")
                return []
                
        except Exception as e:
            self.logger.error(LogModule.GLOSSARY, f"Text extraction failed: {e}", exc_info=True)
            return []
    
    async def _save_to_personal_glossary(self, glossary_dict: Dict[str, str], username: str, target_lang: str):
        """Save generated glossary to user's personal glossary with target language."""
        try:
            from glossary.manager import get_glossary_manager
            manager = get_glossary_manager()
            
            # Convert to format with target_lang: {src: {dst, category, target_lang}}
            glossary_with_lang = {
                src: {
                    'dst': dst,
                    'category': '',
                    'target_lang': target_lang,
                }
                for src, dst in glossary_dict.items()
            }
            
            # Get existing personal glossary
            existing_glossary = manager.get_user_personal_glossary(username)
            if existing_glossary:
                # Merge with existing glossary
                existing_dict = manager.get_glossary_content_with_languages(existing_glossary.id) or {}
                # Convert simple dict to format with languages if needed
                if existing_dict and isinstance(list(existing_dict.values())[0], str):
                    existing_dict = {
                        src: {'dst': dst, 'category': '', 'target_lang': ''}
                        for src, dst in existing_dict.items()
                    }
                # Merge new entries
                merged_dict = {**existing_dict, **glossary_with_lang}
                personal_id = f"personal_{username}"
                manager.save_glossary_with_languages(personal_id, merged_dict, username)
            else:
                # Create new personal glossary with languages
                personal_id = f"personal_{username}"
                manager.save_glossary_with_languages(personal_id, glossary_with_lang, username)
                
            self.logger.info(LogModule.GLOSSARY,f"Saved {len(glossary_dict)} terms to personal glossary for user {username} with target_lang={target_lang}")
            
        except Exception as e:
            self.logger.error(LogModule.GLOSSARY, f"Failed to save to personal glossary: {e}")
            # Don't raise exception, just log the error
    
    async def _generate_csv_download(self, glossary_dict: Dict[str, str], original_filename: str, target_lang: str, task_id: str = None) -> str:
        """Generate CSV download URL for glossary with target language."""
        try:
            # Use task_state temp_dir if available, otherwise use system temp directory
            csv_path = None
            if task_id:
                task_state = task_manager.get_task(task_id)
                if task_state:
                    temp_dir = task_state.get("temp_dir")
                    if temp_dir and os.path.isdir(temp_dir):
                        glossary_dir = os.path.join(temp_dir, "glossary")
                        os.makedirs(glossary_dir, exist_ok=True)
                        csv_path = os.path.join(glossary_dir, f"glossary_{Path(original_filename).stem}.csv")
            
            # Fallback: use system temp directory
            if csv_path:
                temp_file = open(csv_path, 'w', encoding='utf-8-sig')
            else:
                temp_file = tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False, encoding='utf-8-sig')
            
            writer = csv.writer(temp_file)
            writer.writerow(['src', 'dst', 'category', 'target_lang'])
            
            for src, dst in glossary_dict.items():
                writer.writerow([src, dst, '', target_lang])
            
            temp_file.close()
            
            # Generate download URL (simplified - in real implementation, you'd use a proper file service)
            filename = f"glossary_{Path(original_filename).stem}.csv"
            return f"/downloads/glossary/{filename}"
            
        except Exception as e:
            self.logger.error(LogModule.GLOSSARY, f"Failed to generate CSV download: {e}")
            return None


# Service instance
glossary_generation_service = GlossaryGenerationService()

