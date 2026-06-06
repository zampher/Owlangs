# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

import asyncio
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from typing import Self, List, Dict, Any, Tuple, Optional

from agents.segments_agent import SegmentsTranslateAgentConfig, SegmentsTranslateAgent
from ir.document import Document
from translator.ai_translator.base import AiTranslatorConfig, AiTranslator
from logger.logger import LogModule


@dataclass
class QtTsTranslatorConfig(AiTranslatorConfig):
    """
    Configuration for Qt .ts file translator.
    
    Attributes:
        skip_existing_translations: Skip messages that already have translations
        translate_unfinished: Translate messages marked as unfinished (type='unfinished')
        translate_vanished: Translate messages marked as vanished (type='vanished')
        translate_obsolete: Translate messages marked as obsolete (type='obsolete')
        preserve_xml_format: Preserve original XML formatting (indentation, line breaks)
    """
    skip_existing_translations: bool = True
    translate_unfinished: bool = True
    translate_vanished: bool = True
    translate_obsolete: bool = True
    preserve_xml_format: bool = True


class QtTsTranslator(AiTranslator):
    """
    Translator for Qt .ts translation source files.
    
    This translator:
    1. Parses the .ts XML file
    2. Extracts all <source> text that needs translation
    3. Translates the text
    4. Writes translations back to corresponding <translation> tags
    5. Updates type attributes (removes 'unfinished', marks as complete)
    """

    def __init__(self, config: QtTsTranslatorConfig):
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
                max_tokens=getattr(config, 'max_tokens', None)  # Get max_tokens from platform config
            )
            self.translate_agent = SegmentsTranslateAgent(agent_config)
        
        self.skip_existing = config.skip_existing_translations
        self.translate_unfinished = config.translate_unfinished
        self.translate_vanished = config.translate_vanished
        self.translate_obsolete = config.translate_obsolete
        self.preserve_format = config.preserve_xml_format

    def _pre_translate(self, document: Document) -> Tuple[ET.Element, List[Dict], List[str]]:
        """
        Parse Qt .ts XML file and extract all <source> text that needs translation.
        
        Returns:
            Tuple of (root_element, translation_items, original_texts)
        """
        # Parse XML
        root = ET.fromstring(document.content)
        
        translation_items: List[Dict[str, Any]] = []
        original_texts: List[str] = []
        
        # Traverse all context/message elements
        for context in root.findall('.//context'):
            for message in context.findall('message'):
                source = message.find('source')
                if source is None or not source.text:
                    continue
                
                source_text = source.text.strip()
                if not source_text:
                    continue
                
                # Check translation status
                translation = message.find('translation')
                translation_type = translation.get('type') if translation is not None else None
                has_translation = (
                    translation is not None and 
                    translation.text and 
                    translation.text.strip() and
                    translation_type not in ('unfinished', 'vanished', 'obsolete')
                )
                
                # Decide whether to skip this message
                should_skip = False
                
                if self.skip_existing and has_translation:
                    should_skip = True
                elif translation_type == 'unfinished' and not self.translate_unfinished:
                    should_skip = True
                elif translation_type == 'vanished' and not self.translate_vanished:
                    should_skip = True
                elif translation_type == 'obsolete' and not self.translate_obsolete:
                    should_skip = True
                
                if should_skip:
                    continue
                
                # Create or get translation element
                if translation is None:
                    translation = ET.SubElement(message, 'translation')
                
                translation_items.append({
                    'type': 'translation',
                    'message': message,
                    'translation_element': translation,
                    'source_text': source_text,
                    'translation_type': translation_type,
                })
                original_texts.append(source_text)
        
        return root, translation_items, original_texts

    def _format_xml(self, elem: ET.Element, level: int = 0) -> None:
        """
        Format XML element with proper indentation.
        This modifies the element in-place.
        """
        indent = "\n" + "  " * level
        if len(elem):
            if not elem.text or not elem.text.strip():
                elem.text = indent + "  "
            if not elem.tail or not elem.tail.strip():
                elem.tail = indent
            for child in elem:
                self._format_xml(child, level + 1)
                if not child.tail or not child.tail.strip():
                    child.tail = indent
        else:
            if level and (not elem.tail or not elem.tail.strip()):
                elem.tail = indent

    def _after_translate(
        self, 
        root: ET.Element, 
        translation_items: List[Dict], 
        translated_texts: List[str]
    ) -> bytes:
        """
        Write translated text back to corresponding <translation> tags.
        
        Args:
            root: Root XML element
            translation_items: List of translation item metadata
            translated_texts: List of translated texts
            
        Returns:
            Updated XML content as bytes
        """
        if len(translation_items) != len(translated_texts):
            self.logger.error(LogModule.TRANS, f"Number of translation items ({len(translation_items)}) "
            f"does not match number of translated texts ({len(translated_texts)}), "
            "skipping write operation to prevent file corruption.")
            # Return original content on error
            return ET.tostring(root, encoding='utf-8', xml_declaration=True)
        
        # Write translations back
        for i, item in enumerate(translation_items):
            if i >= len(translated_texts):
                break
            
            translation_elem = item['translation_element']
            translated_text = translated_texts[i]
            
            # Write translated text
            translation_elem.text = translated_text
            
            # Update type attribute
            translation_type = item.get('translation_type')
            if translation_type == 'unfinished':
                # Remove 'unfinished' type to mark as complete
                translation_elem.attrib.pop('type', None)
            elif translation_type in ('vanished', 'obsolete'):
                # Keep these types as they indicate special status
                pass
            # If no type was set and we have translation, ensure no 'unfinished' type
            elif 'type' in translation_elem.attrib and translation_elem.attrib['type'] == 'unfinished':
                translation_elem.attrib.pop('type', None)
        
        # Format XML if requested
        if self.preserve_format:
            self._format_xml(root)
        
        # Convert to bytes
        # Note: ET.tostring doesn't preserve DOCTYPE, but that's usually fine
        xml_bytes = ET.tostring(root, encoding='utf-8', xml_declaration=True)
        
        # Try to preserve DOCTYPE if it existed in original
        # This is a simple approach - for more complex cases, consider using lxml
        original_content = self._original_content if hasattr(self, '_original_content') else b''
        if b'<!DOCTYPE' in original_content:
            # Extract DOCTYPE line
            lines = original_content.decode('utf-8', errors='ignore').split('\n')
            doctype_line = None
            for line in lines:
                if '<!DOCTYPE' in line:
                    doctype_line = line.strip()
                    break
            
            if doctype_line:
                # Insert DOCTYPE after XML declaration
                xml_str = xml_bytes.decode('utf-8')
                if '<?xml' in xml_str:
                    parts = xml_str.split('?>', 1)
                    if len(parts) == 2:
                        xml_str = parts[0] + '?>\n' + doctype_line + '\n' + parts[1]
                        xml_bytes = xml_str.encode('utf-8')
        
        return xml_bytes

    def translate(self, document: Document) -> Self:
        """
        Synchronously translate Qt .ts file.
        """
        # Store original content for DOCTYPE preservation
        self._original_content = document.content
        
        root, translation_items, original_texts = self._pre_translate(document)
        
        if not translation_items:
            self.logger.info(LogModule.TRANS, "No translatable content found in Qt .ts file.")
            # Return original document if nothing to translate
            return self
        
        # Generate glossary if needed
        if self.glossary_agent:
            self.glossary_dict_gen = self.glossary_agent.send_segments(original_texts, self.chunk_size)
            if self.translate_agent:
                self.translate_agent.update_glossary_dict(self.glossary_dict_gen)
        
        # Translate
        if self.translate_agent:
            translated_texts = self.translate_agent.send_segments(original_texts, self.chunk_size)
        else:
            translated_texts = original_texts
        
        if len(original_texts) != len(translated_texts):
            raise ValueError(
                f"Number of items returned by translation service ({len(translated_texts)}) "
                f"does not match number sent ({len(original_texts)})."
            )
        
        # Write translations back
        document.content = self._after_translate(root, translation_items, translated_texts)
        
        return self

    async def translate_async(self, document: Document, progress_callback=None) -> Self:
        """
        Asynchronously translate Qt .ts file.
        """
        # Store original content for DOCTYPE preservation
        self._original_content = document.content
        
        # Run _pre_translate in thread pool since it's CPU-bound XML parsing
        root, translation_items, original_texts = await asyncio.to_thread(self._pre_translate, document)
        
        if not translation_items:
            self.logger.info(LogModule.TRANS, "No translatable content found in Qt .ts file.")
            return self
        
        # Generate glossary if needed
        if self.glossary_agent:
            self.glossary_dict_gen = await self.glossary_agent.send_segments_async(original_texts, self.chunk_size, progress_callback=progress_callback)
            if self.translate_agent:
                self.translate_agent.update_glossary_dict(self.glossary_dict_gen)
        
        # Translate
        if self.translate_agent:
            # Set task_state on agent for API debug output
            task_id = getattr(self, '_task_id', None)
            if task_id:
                try:
                    from backend.app.services.task import task_manager
                    task_state = task_manager.get_task(task_id) if task_id else None
                    if task_state and self.translate_agent:
                        self.translate_agent.task_state = task_state
                        self.translate_agent.task_id = task_id
                except Exception as e:
                    self.logger.debug(LogModule.TRANS, f"[QT_TS_TRANSLATOR] Failed to set task_state on agent: {e}")
            
            translated_texts = await self.translate_agent.send_segments_async(original_texts, self.chunk_size, progress_callback=progress_callback)
            
            # Save API logs to temp directory
            if task_id:
                try:
                    from backend.app.services.task import task_manager
                    from utils.chunk_translation_helper import save_api_logs_to_temp_dir
                    task_state = task_manager.get_task(task_id) if task_id else None
                    if task_state:
                        save_api_logs_to_temp_dir(
                            task_state=task_state,
                            task_id=task_id,
                            subfolder="translation",
                            llm_api_input=task_state.get('llm_api_input'),
                            llm_api_output=task_state.get('llm_api_output'),
                            llm_api_system_prompt=task_state.get('llm_api_system_prompt'),
                        )
                except Exception as log_e:
                    self.logger.warning(LogModule.TRANS, f"[QT_TS_TRANSLATOR] Failed to save API logs: {log_e}", exc_info=True)
        else:
            translated_texts = original_texts
        
        if len(original_texts) != len(translated_texts):
            raise ValueError(
                f"Number of items returned by translation service ({len(translated_texts)}) "
                f"does not match number sent ({len(original_texts)})."
            )
        
        # Write translations back
        document.content = await asyncio.to_thread(
            self._after_translate, root, translation_items, translated_texts
        )
        
        return self

