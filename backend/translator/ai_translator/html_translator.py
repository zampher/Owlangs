# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0
import asyncio
import re
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

    async def translate_async(self, document: Document, task_id: str = None, task_state: dict = None, progress_callback=None) -> Self:
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
        
        # CRITICAL: Read excluded segments from task_state and filter them out before translation
        # This ensures user-selected exclusions from the Extract phase are respected
        excluded_indices = set()
        if task_state:
            segments_metadata = task_state.get("segments_metadata", {})
            excluded_segment_indices = segments_metadata.get("excluded_segment_indices", [])
            if excluded_segment_indices:
                excluded_indices = set(int(x) for x in excluded_segment_indices if x is not None)
                self.logger.info(
                    LogModule.TRANS,
                    f"[HTML_TRANSLATOR] Task {task_id}: Found {len(excluded_indices)} excluded segments, "
                    f"will skip translation for them."
                )
        
        # Build included indices and texts (skip excluded segments)
        included_indices = []
        included_texts = []
        for idx, text in enumerate(original_texts):
            if idx in excluded_indices:
                continue
            included_indices.append(idx)
            included_texts.append(text)
        
        # If all segments are excluded, skip LLM translation entirely
        if not included_texts:
            self.logger.info(
                LogModule.TRANS,
                f"[HTML_TRANSLATOR] Task {task_id}: All {len(original_texts)} segments are excluded, "
                f"skipping LLM translation."
            )
            translated_texts = original_texts.copy()
        else:
            # Translate segments using SegmentsTranslateAgent
            if self.glossary_agent:
                self.glossary_dict_gen = await self.glossary_agent.send_segments_async(
                    included_texts, self.chunk_size, progress_callback=progress_callback, segment_indices=included_indices
                )
                if self.translate_agent:
                    self.translate_agent.update_glossary_dict(self.glossary_dict_gen)
            
            if self.translate_agent:
                # Set task_state for API debug output
                if task_state and self.translate_agent:
                    self.translate_agent.task_state = task_state
                translated_included_texts = await self.translate_agent.send_segments_async(
                    included_texts, self.chunk_size, progress_callback=progress_callback, segment_indices=included_indices
                )
            else:
                translated_included_texts = included_texts.copy()
            
            # Rebuild full translated_texts: insert translated text for included segments,
            # keep original text for excluded segments
            translated_texts = original_texts.copy()
            for i, idx in enumerate(included_indices):
                if i < len(translated_included_texts):
                    translated_texts[idx] = translated_included_texts[i]
            
            self.logger.info(
                LogModule.TRANS,
                f"[HTML_TRANSLATOR] Task {task_id}: Translated {len(included_indices)}/{len(original_texts)} segments, "
                f"{len(excluded_indices)} segments kept original (excluded)."
            )
        
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
        
        # Write translated segments back to HTML.
        # CRITICAL: Handle both single-segment and multi-segment tags.
        # HtmlExtractor with deep_split=True may split a single tag's text into
        # multiple segments. Matching tag.string (full text) against individual
        # segments fails for these cases, so we use _apply_html_translations which
        # falls back to consecutive-segment concatenation matching.
        document.content = await asyncio.to_thread(
            _apply_html_translations,
            html_content, original_texts, translated_texts,
            NON_TRANSLATABLE_TAGS, SAFE_TAGS,
        )
        return self
    
    def _after_translate_with_extractor(self, html_content: str, original_texts: List[str], translated_texts: List[str]) -> bytes:
        """
        Write translated segments back to HTML using extractor-based approach.
        Delegates to module-level _apply_html_translations for shared logic.
        """
        return _apply_html_translations(
            html_content, original_texts, translated_texts,
            NON_TRANSLATABLE_TAGS, SAFE_TAGS,
        )


def _apply_html_translations(
    html_content: str,
    original_texts: List[str],
    translated_texts: List[str],
    non_translatable_tags: Set[str],
    safe_tags: Set[str],
) -> bytes:
    """Apply translations to an HTML string using text-node-based matching.

    The HtmlExtractor may combine text from multiple adjacent inline tags into
    one segment (e.g. two <span>s inside a <div>). This approach matches at the
    text-node character level rather than by tag.string, correctly handling:
    1. One tag -> one segment (direct match)
    2. One tag -> multiple segments (deep split)
    3. Multiple tags -> one segment (tag-group combining, the common case)

    Returns the translated HTML as bytes (encoded utf-8).
    """
    from bs4 import BeautifulSoup, NavigableString, Comment as BSComment

    soup = BeautifulSoup(html_content, 'lxml')

    # Remove non-translatable tags
    for tag in soup.find_all(non_translatable_tags):
        tag.decompose()

    # Phase 1: Collect all text nodes within safe tags and build flat text
    text_nodes: list = []
    node_texts: list[str] = []
    for text_node in soup.find_all(string=True):
        if isinstance(text_node, BSComment):
            continue
        parent = text_node.parent
        if parent and hasattr(parent, 'name') and parent.name in safe_tags:
            t = str(text_node)
            text_nodes.append(text_node)
            node_texts.append(t)

    # Track consumed segment indices to handle duplicate original texts
    consumed_indices: Set[int] = set()

    for seg_idx, (orig, trans) in enumerate(zip(original_texts, translated_texts)):
        if seg_idx in consumed_indices:
            continue
        if not orig or not orig.strip():
            consumed_indices.add(seg_idx)
            continue

        # (Re)build flat text from current node state and cumulative positions
        flat_text = "".join(node_texts)

        # Find this segment in the flat text
        pos = flat_text.find(orig)
        if pos == -1:
            continue

        end = pos + len(orig)

        # Build cumulative node positions for this iteration
        node_positions: List[tuple[int, int]] = []
        cum = 0
        for nt in node_texts:
            node_positions.append((cum, cum + len(nt)))
            cum += len(nt)

        # Find which text node(s) this segment spans
        start_ni: Optional[int] = None
        end_ni: Optional[int] = None
        for ni, (n_start, n_end) in enumerate(node_positions):
            if start_ni is None and n_start <= pos < n_end:
                start_ni = ni
            if n_start < end <= n_end:
                end_ni = ni
                break

        if start_ni is None or end_ni is None:
            continue

        consumed_indices.add(seg_idx)

        if start_ni == end_ni:
            # Single node — replace within this node
            node = text_nodes[start_ni]
            n_start, n_end = node_positions[start_ni]
            offset = pos - n_start
            old = node_texts[start_ni]
            new_text = old[:offset] + trans + old[offset + len(orig):]
            new_node = NavigableString(new_text)
            node.replace_with(new_node)
            text_nodes[start_ni] = new_node  # Update reference for subsequent iterations
            node_texts[start_ni] = new_text
        else:
            # Multiple nodes — segment content spans inline tag boundaries.
            # Put the translated text in the first affected node, clear the rest.
            n_start, _ = node_positions[start_ni]
            offset = pos - n_start
            first_head = node_texts[start_ni][:offset]

            _, n_end = node_positions[end_ni]
            end_off = end - node_positions[end_ni][0]
            last_tail = node_texts[end_ni][end_off:]

            combined = first_head + trans + last_tail

            new_first = NavigableString(combined)
            text_nodes[start_ni].replace_with(new_first)
            text_nodes[start_ni] = new_first
            node_texts[start_ni] = combined

            for ni in range(start_ni + 1, end_ni + 1):
                new_empty = NavigableString("")
                text_nodes[ni].replace_with(new_empty)
                text_nodes[ni] = new_empty
                node_texts[ni] = ""

    # Strip CSS hiding that would require JavaScript to unhide.
    # WeChat and other platforms set visibility:hidden/opacity:0 on content
    # and rely on JS to remove them — scripts are already decomposed.
    _VIS_HIDDEN_RE = re.compile(r'visibility\s*:\s*hidden\s*;?\s*', re.IGNORECASE)
    _OPACITY_ZERO_RE = re.compile(r'opacity\s*:\s*0\s*;?\s*', re.IGNORECASE)
    for elem in soup.find_all(style=True):
        style = elem.get('style', '')
        new_style = _VIS_HIDDEN_RE.sub('', style)
        new_style = _OPACITY_ZERO_RE.sub('', new_style)
        if new_style != style:
            new_style = new_style.strip().strip(';').strip()
            if new_style:
                elem['style'] = new_style
            else:
                del elem['style']

    return soup.encode('utf-8')