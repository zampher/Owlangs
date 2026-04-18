# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0
import asyncio
from dataclasses import dataclass
from typing import Self, Literal, Set, Dict, List, Tuple

from bs4 import BeautifulSoup, NavigableString, Comment

from agents.segments_agent import SegmentsTranslateAgentConfig, SegmentsTranslateAgent
from ir.document import Document
from translator.ai_translator.base import AiTranslatorConfig, AiTranslator
from logger.logger import LogModule

# --- Rule Definitions ---

# 1. Non-translatable tags (blacklist)
# These tags and their content should not be translated under any circumstances, as they usually contain code, styles, or metadata.
# During preprocessing, these tags and all their child elements will be directly removed from the document to ensure they are not accidentally modified.
NON_TRANSLATABLE_TAGS: Set[str] = {
    'script',  # JavaScript code
    'style',  # CSS styles
    'pre',  # Preformatted text, usually for code blocks
    'code',  # Inline code
    'kbd',  # Keyboard input
    'samp',  # Sample output
    'var',  # Variables
    'noscript',  # Content when script is not enabled
    'meta',  # Metadata
    'link',  # External resource links
    'head',  # Document head, usually doesn't contain visible translatable content
}

# 2. Translatable tags (whitelist)
# Define a set of HTML tags considered "safe", where direct text content is suitable for translation.
# This whitelist strategy combined with the blacklist above provides double protection.
SAFE_TAGS: Set[str] = {
    'p', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
    'li', 'blockquote', 'q', 'caption',
    'span', 'a', 'strong', 'em', 'b', 'i', 'u',
    'td', 'th',
    'button', 'label', 'legend', 'option',
    'figcaption', 'summary', 'details',
    'div',  # div is quite general, but our logic only extracts its top-level text nodes, which is relatively safe
}

# 3. Translatable attributes (whitelist)
# Define a set of "safe" attributes whose values are usually readable text for users.
# Format: { 'tag_name': ['attr1', 'attr2'], ... }
SAFE_ATTRIBUTES: Dict[str, List[str]] = {
    'img': ['alt', 'title'],
    'a': ['title'],
    'input': ['placeholder', 'title'],
    'textarea': ['placeholder', 'title'],
    'abbr': ['title'],
    'area': ['alt'],
    # For all tags, title attribute is usually translatable
    '*': ['title']
}


@dataclass
class HtmlTranslatorConfig(AiTranslatorConfig):
    """
    Configuration class for HTML translator.

    Attributes:
        insert_mode (Literal["replace", "append", "prepend"]):
            Specify how to insert translated text.
            - "replace": Replace original text with translation.
            - "append": Append translation after original text.
            - "prepend": Prepend translation before original text.
        separator (str): String used to separate original and translated text in "append" or "prepend" mode.
    """
    insert_mode: Literal["replace", "append", "prepend"] = "replace"
    separator: str = " "  # Using space as default separator in HTML may be more appropriate


class HtmlTranslator(AiTranslator):
    """
    A translator for translating HTML file content.
    It adopts a blacklist and whitelist combined strategy to maximize page style and functionality preservation:
    1. Blacklist: First, completely remove script, style, code and other clearly non-translatable tags and their content.
    2. Whitelist: Then, in the remaining HTML, only extract and translate text content in specified safe tags and attributes.
    3. Comment protection: Explicitly skip HTML comments to ensure they are not translated.
    This method effectively avoids breaking page structure, scripts, styles and comments.
    """

    def __init__(self, config: HtmlTranslatorConfig):
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
                logger=self.logger,
                glossary_dict=config.glossary_dict,
                retry=config.retry,
                max_tokens=getattr(config, 'max_tokens', None),  # Get max_tokens from platform config
                use_seg_tags=True,  # Use SEG-tag format for HTML segments
            )
            self.translate_agent = SegmentsTranslateAgent(agent_config)
        self.insert_mode = config.insert_mode
        self.separator = config.separator

    def _pre_translate(self, document: Document) -> Tuple[BeautifulSoup, List[Dict], List[str]]:
        """
        Parse HTML document and extract all text nodes and attributes that need translation according to rules.
        Steps:
        1. Use blacklist to remove all non-translatable tags, fundamentally preventing them from being processed.
        2. Traverse remaining HTML elements, extract translatable text and attribute values according to whitelist, while skipping comments.
        """
        soup = BeautifulSoup(document.content, 'lxml')

        # Step 1: Remove all non-translatable tags and their content
        for tag in soup.find_all(NON_TRANSLATABLE_TAGS):
            tag.decompose()

        translatable_items = []
        original_texts = []

        # Step 2: Traverse all remaining tags, extract translatable content
        # Use find_all(string=True) to recursively find all text nodes, then filter by parent tag
        # This ensures nested tags (e.g., span inside p) are also extracted
        processed_text_nodes = set()  # Track processed text nodes to avoid duplicates
        
        for text_node in soup.find_all(string=True):
            # Skip comments
            if isinstance(text_node, Comment):
                continue
            
            # Skip empty or whitespace-only text
            if not text_node.strip():
                continue
            
            # Skip if already processed (avoid duplicates)
            if text_node in processed_text_nodes:
                continue
            
            # Get parent tag
            parent = text_node.parent
            if parent is None:
                continue
            
            # Check if parent has a name attribute (should always be true for tags, but safety check)
            if not hasattr(parent, 'name') or parent.name is None:
                continue
            
            # Only process text nodes whose parent is a safe tag
            if parent.name in SAFE_TAGS:
                # Check if parent or any ancestor is in NON_TRANSLATABLE_TAGS (should not happen after Step 1, but double-check)
                ancestor = parent
                skip = False
                while ancestor and hasattr(ancestor, 'name') and ancestor.name and ancestor.name != '[document]':
                    if ancestor.name in NON_TRANSLATABLE_TAGS:
                        skip = True
                        break
                    ancestor = ancestor.parent
                
                if not skip:
                    text = str(text_node)
                    translatable_items.append({'type': 'node', 'object': text_node})
                    original_texts.append(text)
                    processed_text_nodes.add(text_node)
        
        # --- 2b. Translate safe attributes within safe tags ---
        # Process attributes separately after processing all text nodes
        for tag in soup.find_all(True):
            if not hasattr(tag, 'name') or tag.name is None:
                continue
            attributes_to_check = SAFE_ATTRIBUTES.get(tag.name, []) + SAFE_ATTRIBUTES.get('*', [])
            for attr in set(attributes_to_check):  # Use set to deduplicate
                if tag.has_attr(attr) and tag[attr].strip():
                    value = tag[attr]
                    translatable_items.append({'type': 'attribute', 'tag': tag, 'attribute': attr})
                    original_texts.append(value)

        return soup, translatable_items, original_texts

    def _after_translate(self, soup: BeautifulSoup, translatable_items: list,
                         translated_texts: list[str], original_texts: list[str]) -> bytes:
        """
        Write translated text back to corresponding nodes or attributes in BeautifulSoup object and return final HTML byte stream.
        """
        if len(translatable_items) != len(translated_texts):
            self.logger.error(LogModule.TRANS, "Number of text segments before and after translation don't match (%d vs %d), skipping write operation to prevent file corruption.",
                              len(translatable_items), len(translated_texts))
            return soup.encode('utf-8')

        for i, item in enumerate(translatable_items):
            translated_text = translated_texts[i]
            original_text = original_texts[i]

            new_content = ""
            if self.insert_mode == "replace":
                if item['type'] == 'node':
                    # For text nodes, preserve leading and trailing whitespace from original text, which is crucial for maintaining inline element spacing.
                    leading_space = original_text[:len(original_text) - len(original_text.lstrip())]
                    trailing_space = original_text[len(original_text.rstrip()):]
                    new_content = leading_space + translated_text + trailing_space
                else:  # Attribute
                    new_content = translated_text

            elif self.insert_mode == "append":
                new_content = original_text + self.separator + translated_text
            elif self.insert_mode == "prepend":
                new_content = translated_text + self.separator + original_text
            else:
                self.logger.error(LogModule.TRANS, f"Invalid HtmlTranslatorConfig parameter: insert_mode='{self.insert_mode}'")
                new_content = original_text  # Restore original text on error

            # Write content back based on type
            if item['type'] == 'node':
                node = item['object']
                # Check if node is still in parse tree to prevent issues during processing
                if node.parent:
                    node.replace_with(NavigableString(new_content))
            elif item['type'] == 'attribute':
                tag = item['tag']
                attr = item['attribute']
                tag[attr] = new_content

        # Encode modified BeautifulSoup object to utf-8 byte stream
        return soup.encode('utf-8')

    def translate(self, document: Document) -> Self:
        """
        Synchronously translate HTML document.
        """
        soup, translatable_items, original_texts = self._pre_translate(document)
        if not translatable_items:
            self.logger.info(LogModule.TRANS, "\nNo translatable content found in HTML file that meets safety rules.")
            # Even without translation content, return cleaned document content (removed non-translatable tags)
            document.content = soup.encode('utf-8')
            return self

        if self.glossary_agent:
            self.glossary_dict_gen = self.glossary_agent.send_segments(original_texts, self.chunk_size)
            if self.translate_agent:
                self.translate_agent.update_glossary_dict(self.glossary_dict_gen)
        if self.translate_agent:
            translated_texts = self.translate_agent.send_segments(original_texts, self.chunk_size)
        else:
            translated_texts = original_texts
        document.content = self._after_translate(soup, translatable_items, translated_texts, original_texts)
        return self

    async def translate_async(self, document: Document, task_id: str = None, task_state: dict = None) -> Self:
        """
        Asynchronously translate HTML document.
        
        CRITICAL: For consistency with Extract stage, use HtmlExtractor to extract segments
        instead of text node extraction. This ensures translation segments match Extract preview.
        """
        # CRITICAL: Use HtmlExtractor to extract segments (same as Extract stage)
        # This ensures translation segments match the Extract preview
        from extractor.html_extractor import HtmlExtractor
        
        html_content = document.content.decode('utf-8')
        deep_split_enabled = bool(task_state.get("deep_split") if task_state else True)
        
        # Extract segments using HtmlExtractor (same as Extract stage)
        extract_result = HtmlExtractor(html_content, chunk_size=self.chunk_size, deep_split=deep_split_enabled).extract()
        original_texts = extract_result.segments
        
        if not original_texts:
            self.logger.info(LogModule.TRANS, "\nNo translatable content found in HTML file.")
            return self
        
        # Store extract result for later use in _after_translate
        self._extract_result = extract_result
        self._html_content = html_content
        
        # Translate segments using SegmentsTranslateAgent
        if self.glossary_agent:
            self.glossary_dict_gen = await self.glossary_agent.send_segments_async(original_texts, self.chunk_size)
            if self.translate_agent:
                self.translate_agent.update_glossary_dict(self.glossary_dict_gen)
        
        if self.translate_agent:
            # Set task_state for API debug output
            if task_state and self.translate_agent:
                self.translate_agent.task_state = task_state
            translated_texts = await self.translate_agent.send_segments_async(original_texts, self.chunk_size)
        else:
            translated_texts = original_texts
        
        # Store original_texts and translated_texts for later use in _record_html_segments
        self.original_texts = original_texts
        self.translated_texts = translated_texts
        
        # Save API logs to temp directory
        if task_id and task_state:
            try:
                from utils.chunk_translation_helper import save_api_logs_to_temp_dir
                save_api_logs_to_temp_dir(
                    task_state=task_state,
                    task_id=task_id,
                    subfolder="translation",
                    llm_api_input=task_state.get('llm_api_input'),
                    llm_api_output=task_state.get('llm_api_output'),
                    llm_api_system_prompt=task_state.get('llm_api_system_prompt'),
                )
            except Exception as log_e:
                self.logger.warning(LogModule.TRANS, f"[HTML_TRANSLATOR] Failed to save API logs: {log_e}", exc_info=True)
        
        # Write translated segments back to HTML
        document.content = await asyncio.to_thread(
            self._after_translate_with_extractor, html_content, original_texts, translated_texts
        )
        return self
    
    def _after_translate_with_extractor(self, html_content: str, original_texts: List[str], translated_texts: List[str]) -> bytes:
        """
        Write translated segments back to HTML using extractor-based approach.
        This replaces each extracted block with its translated version.
        """
        from bs4 import BeautifulSoup
        
        soup = BeautifulSoup(html_content, 'lxml')
        
        # Remove non-translatable tags
        for tag in soup.find_all(NON_TRANSLATABLE_TAGS):
            tag.decompose()
        
        # Create a mapping from original text to translated text
        translation_map = dict(zip(original_texts, translated_texts))
        
        # Find and replace text in safe tags
        for tag in soup.find_all(SAFE_TAGS):
            if tag.string:
                original_text = tag.string.strip()
                if original_text in translation_map:
                    translated_text = translation_map[original_text]
                    tag.string = translated_text
        
        return soup.encode('utf-8')