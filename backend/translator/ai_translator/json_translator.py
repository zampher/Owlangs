# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0
import json
from dataclasses import dataclass
from typing import Self, Any, Tuple, List, Optional

from jsonpath_ng.ext import parse

from logger.logger import LogModule
from agents.segments_agent import SegmentsTranslateAgentConfig, SegmentsTranslateAgent
from ir.document import Document
from translator.ai_translator.base import AiTranslatorConfig, AiTranslator


@dataclass
class JsonTranslatorConfig(AiTranslatorConfig):
    json_paths: list[str]
    # When True, send one segment per API request to avoid one bad segment (e.g. @@locale) breaking a chunk
    segment_per_request: bool = False


class JsonTranslator(AiTranslator):
    def __init__(self, config: JsonTranslatorConfig):
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
                segment_per_request=getattr(config, 'segment_per_request', False),
            )
            self.translate_agent = SegmentsTranslateAgent(agent_config)
        self.json_paths = config.json_paths

    def _get_key_or_index_from_path(self, path) -> Any:
        """Extract key or index from jsonpath_ng Path object."""
        if hasattr(path, 'fields') and path.fields:
            return path.fields[0]
        if hasattr(path, 'index'):
            return path.index
        return None

    def _rebuild_update_targets_from_paths(self, content: dict, paths: List[str]) -> List[Tuple[Any, Any]]:
        """
        Rebuild update_targets from JSON paths (from segment_info).
        Each path string (e.g., '$.a.b', '$.arr[0].x') is converted to (container, key_or_index).
        
        Args:
            content: Parsed JSON object
            paths: List of JSON path strings from segment_info
            
        Returns:
            List of (container, key_or_index) tuples
        """
        update_targets = []
        for path_str in paths:
            try:
                # Parse path string to jsonpath_ng expression
                jsonpath_expr = parse(path_str)
                matches = jsonpath_expr.find(content)
                if matches:
                    # Use first match (should be unique for leaf paths)
                    match = matches[0]
                    parent = match.context.value if match.context else None
                    key_or_index = self._get_key_or_index_from_path(match.path)
                    if parent is not None and key_or_index is not None:
                        update_targets.append((parent, key_or_index))
            except Exception as e:
                self.logger.warning(LogModule.TRANS, f"[JSON_TRANSLATOR] Failed to parse path '{path_str}': {e}")
        return update_targets

    def _find_path_for_text(self, content: dict, text: str, json_paths: List[str]) -> Optional[str]:
        """
        Find the JSON path for a given text value by searching through the JSON structure.
        This is used to complement missing path information in segment_info.
        
        Args:
            content: Parsed JSON object
            text: Text value to find
            json_paths: Optional json_paths to limit search scope
            
        Returns:
            JSON path string (e.g., '$.a.b') or None if not found
        """
        def _search_recursive(node: Any, base_path: str = '$', visited: set = None) -> Optional[str]:
            if visited is None:
                visited = set()
            node_id = id(node)
            if node_id in visited:
                return None
            visited.add(node_id)
            
            if isinstance(node, str):
                if node == text:
                    return base_path
            elif isinstance(node, dict):
                for k, v in node.items():
                    path = f"{base_path}.{k}"
                    result = _search_recursive(v, path, visited)
                    if result:
                        return result
            elif isinstance(node, list):
                for i, item in enumerate(node):
                    path = f"{base_path}[{i}]"
                    result = _search_recursive(item, path, visited)
                    if result:
                        return result
            return None
        
        # If json_paths is provided, search only within those paths
        if json_paths:
            for path_str in json_paths:
                try:
                    jsonpath_expr = parse(path_str)
                    matches = jsonpath_expr.find(content)
                    for match in matches:
                        result = _search_recursive(match.value, path_str, set())
                        if result:
                            return result
                except Exception:
                    continue
        else:
            # Search entire JSON structure
            return _search_recursive(content)
        
        return None

    def _collect_strings_for_translation(self, content: dict) -> Tuple[List[str], List[Tuple[Any, Any]]]:
        """
        Find matches based on jsonpath and recursively collect all strings for translation.
        To prevent duplicates, track the exact position of each string.

        Returns:
            - original_texts: A list containing all strings to be translated.
            - update_targets: A list of targets containing update information, each element is (container, key_or_index).
        """
        original_texts = []
        update_targets = []
        # Use (id(container), key_or_index) to uniquely identify a position and prevent duplicate additions
        seen_targets = set()

        # Helper recursive function for traversing JSON objects
        def _traverse(node: Any, container: Any, key_or_index: Any):
            # If current node is a string and its position has not been recorded
            target_id = (id(container), key_or_index)
            if isinstance(node, str):
                if target_id not in seen_targets:
                    original_texts.append(node)
                    update_targets.append((container, key_or_index))
                    seen_targets.add(target_id)
            # If it's a dictionary, traverse all its child nodes
            elif isinstance(node, dict):
                for k, v in node.items():
                    _traverse(v, node, k)
            # If it's a list, traverse all its child nodes
            elif isinstance(node, list):
                for i, item in enumerate(node):
                    _traverse(item, node, i)

        # 1. Find all top-level matches
        all_matches = []
        if self.json_paths:
            # If json_paths is provided, use jsonpath to find matches
            for path_str in self.json_paths:
                jsonpath_expr = parse(path_str)
                all_matches.extend(jsonpath_expr.find(content))

            # 2. Traverse matches and start recursive collection
            for match in all_matches:
                parent = match.context.value if match.context else None
                key_or_index = self._get_key_or_index_from_path(match.path)

                # Start traversal directly on the matched value
                _traverse(match.value, parent, key_or_index)
        else:
            # If json_paths is empty, traverse the entire JSON structure (default behavior)
            # This matches JsonExtractor's behavior when paths is empty
            _traverse(content, None, None)

        return original_texts, update_targets

    def _apply_translations(self, update_targets: List[Tuple[Any, Any]], translated_texts: List[str]):
        """
        Update original JSON content with translated text.
        """
        if len(update_targets) != len(translated_texts):
            raise ValueError("The number of translation targets does not match the number of translated texts.")

        for target, text in zip(update_targets, translated_texts):
            container, key_or_index = target
            # Ensure container and key/index are valid, then perform update
            if container is not None and key_or_index is not None:
                container[key_or_index] = text

    def translate(self, document: Document) -> Self:
        """
        Main method: extract, translate and update specified content in JSON document.

        Process:
        1. Try to use cached segments from Extract phase for consistency.
        2. If cached segments available, rebuild update_targets from segment_info.paths.
        3. Otherwise, extract strings and positions using _collect_strings_for_translation.
        4. Batch send extracted strings for translation.
        5. Update JSON object with translated text based on their original positions.
        6. Write updated content back to document.
        """
        content = json.loads(document.content.decode())

        # --- Step 1: Try to use cached segments from Extract phase for consistency ---
        task_id = getattr(self, '_task_id', None)
        task_state = None
        cached_segments = None
        segment_info = None
        if task_id:
            try:
                from backend.app.services.task import task_manager
                from logger.logger import LogModule
                task_state = task_manager.get_task(task_id) if task_id else None
                if task_state:
                    cache_info = task_state.get("source_chunks_cache", {})
                    cached_segments = cache_info.get("segments", [])
                    segments_metadata = task_state.get("segments_metadata", {})
                    segment_info = segments_metadata.get("segment_info", [])
                    if cached_segments:
                        self.logger.info(
                            LogModule.TRANS,
                            f"[JSON_TRANSLATOR] Found {len(cached_segments)} cached segments from Extract phase. "
                            f"Will use cached segments to ensure consistency with chunk mapping.",
                        )
            except Exception as e:
                self.logger.debug(LogModule.TRANS, f"[JSON_TRANSLATOR] Failed to get cached segments: {e}")

        # --- Step 2: CRITICAL - Must use cached segments from Extract phase, no fallback ---
        if not cached_segments or len(cached_segments) == 0:
            raise ValueError(
                f"[JSON_TRANSLATOR] CRITICAL: Cached segments from Extract phase are not available. "
                f"This should not happen. Extract phase must be completed before Translate phase."
            )
        
        # CRITICAL: Always use cached segments from Extract phase to ensure consistency
        original_texts = [str(s) for s in cached_segments]
        self.logger.info(
            LogModule.TRANS,
            f"[JSON_TRANSLATOR] Using {len(original_texts)} cached segments from Extract phase "
            f"(no re-extraction) to ensure consistency with chunk mapping",
        )

        # Rebuild update_targets from segment_info.paths
        update_targets: list[tuple[Any, Any]] = []
        # For ARB files: skip metadata keys starting with "@" (e.g. "@@locale", "@settingsGeneralTitle")
        arb_meta_indices: set[int] = set()
        if not segment_info or len(segment_info) != len(cached_segments):
            # CRITICAL: segment_info is missing or count mismatch, we must complement it
            self.logger.warning(LogModule.TRANS, f"[JSON_TRANSLATOR] segment_info missing or count mismatch "
                f"(segments={len(cached_segments)}, segment_info={len(segment_info) if segment_info else 0}). "
                f"Will complement missing paths by searching JSON structure.")
            # Complement missing segment_info by finding paths for each segment
            for idx, seg_text in enumerate(original_texts):
                if segment_info and idx < len(segment_info) and isinstance(segment_info[idx], dict) and 'paths' in segment_info[idx]:
                    paths = segment_info[idx]['paths']
                    if paths and len(paths) > 0:
                        path_str = paths[0]
                    else:
                        # Path is empty, find it
                        path_str = self._find_path_for_text(content, seg_text, self.json_paths)
                        if not path_str:
                            raise ValueError(
                                f"[JSON_TRANSLATOR] CRITICAL: Cannot find path for segment {idx}: '{seg_text[:50]}...'. "
                                f"This segment cannot be updated in the JSON structure."
                            )
                else:
                    # segment_info is missing for this segment, find path
                    path_str = self._find_path_for_text(content, seg_text, self.json_paths)
                    if not path_str:
                        raise ValueError(
                            f"[JSON_TRANSLATOR] CRITICAL: Cannot find path for segment {idx}: '{seg_text[:50]}...'. "
                            f"This segment cannot be updated in the JSON structure."
                        )

                # ARB metadata keys (starting with "@") should not be translated.
                # Their JSONPath-style representation from Extract is like "$.@@locale" or "$.@settingsGeneralTitle...".
                if isinstance(path_str, str) and path_str.startswith('$.@'):
                    self.logger.info(
                        LogModule.TRANS,
                        f"[JSON_TRANSLATOR] Skipping ARB metadata segment {idx} with path '{path_str}'",
                    )
                    # Use a no-op update target to keep indices aligned; _apply_translations will ignore it.
                    update_targets.append((None, None))
                    arb_meta_indices.add(idx)
                    continue

                # Rebuild update_target from found path
                targets = self._rebuild_update_targets_from_paths(content, [path_str])
                if targets:
                    update_targets.extend(targets)
                else:
                    # If we cannot rebuild update_target for this segment, log and skip it
                    self.logger.warning(
                        LogModule.TRANS,
                        f"[JSON_TRANSLATOR] CRITICAL: Failed to rebuild update_target from path '{path_str}' "
                        f"for segment {idx}. This segment will be kept as original and skipped from translation.",
                    )
                    update_targets.append((None, None))
        else:
            # segment_info is available and count matches
            for idx, seg_info in enumerate(segment_info):
                if not isinstance(seg_info, dict) or 'paths' not in seg_info:
                    # segment_info is missing 'paths' key, find it
                    seg_text = original_texts[idx] if idx < len(original_texts) else ""
                    path_str = self._find_path_for_text(content, seg_text, self.json_paths)
                    if not path_str:
                        raise ValueError(
                            f"[JSON_TRANSLATOR] CRITICAL: segment_info[{idx}] missing 'paths' and cannot find path "
                            f"for segment: '{seg_text[:50]}...'. This segment cannot be updated."
                        )
                    targets = self._rebuild_update_targets_from_paths(content, [path_str])
                    if targets:
                        update_targets.extend(targets)
                    else:
                        self.logger.warning(
                            LogModule.TRANS,
                            f"[JSON_TRANSLATOR] CRITICAL: Failed to rebuild update_target from found path '{path_str}' "
                            f"for segment {idx}. This segment will be kept as original and skipped from translation.",
                        )
                        update_targets.append((None, None))
                else:
                    paths = seg_info['paths']
                    if not paths or len(paths) == 0:
                        # Path is empty, find it
                        seg_text = original_texts[idx] if idx < len(original_texts) else ""
                        path_str = self._find_path_for_text(content, seg_text, self.json_paths)
                        if not path_str:
                            raise ValueError(
                                f"[JSON_TRANSLATOR] CRITICAL: segment_info[{idx}].paths is empty and cannot find path "
                                f"for segment: '{seg_text[:50]}...'. This segment cannot be updated."
                            )
                        targets = self._rebuild_update_targets_from_paths(content, [path_str])
                        if targets:
                            update_targets.extend(targets)
                        else:
                            self.logger.warning(
                                LogModule.TRANS,
                                f"[JSON_TRANSLATOR] CRITICAL: Failed to rebuild update_target from found path '{path_str}' "
                                f"for segment {idx}. This segment will be kept as original and skipped from translation.",
                            )
                            update_targets.append((None, None))
                    else:
                        # Use first path (each segment typically has one path)
                        path_str = paths[0]
                        # ARB metadata keys (starting with "@") should not be translated.
                        if isinstance(path_str, str) and path_str.startswith('$.@'):
                            self.logger.info(
                                LogModule.TRANS,
                                f"[JSON_TRANSLATOR] Skipping ARB metadata segment {idx} with path '{path_str}'",
                            )
                            update_targets.append((None, None))
                            arb_meta_indices.add(idx)
                        else:
                            targets = self._rebuild_update_targets_from_paths(content, [path_str])
                            if targets:
                                update_targets.extend(targets)
                            else:
                                self.logger.warning(
                                    LogModule.TRANS,
                                    f"[JSON_TRANSLATOR] CRITICAL: Failed to rebuild update_target from path '{path_str}' "
                                    f"for segment {idx}. This segment will be kept as original and skipped from translation.",
                                )
                                update_targets.append((None, None))
        
        # Verify update_targets count matches original_texts
        if len(update_targets) != len(original_texts):
            # Instead of failing the whole task, log and pad with no-op targets
            self.logger.warning(
                LogModule.TRANS,
                f"[JSON_TRANSLATOR] CRITICAL: update_targets count mismatch "
                f"(segments={len(original_texts)}, targets={len(update_targets)}). "
                f"Padding with no-op targets to keep JSON structure unchanged.",
            )
            while len(update_targets) < len(original_texts):
                update_targets.append((None, None))

        if not original_texts:
            return self

        # CRITICAL: Filter excluded segments before translation
        # Get excluded segments using ExclusionManager (single source of truth)
        excluded_set: set[int] = set()
        if task_id and task_state:
            try:
                from exclusion.core import ExclusionManager
                from logger.logger import LogModule
                excluded_segments_with_reasons = ExclusionManager.get_excluded_segments(task_state)
                excluded_set = set(excluded_segments_with_reasons.keys())
                if excluded_set:
                    self.logger.info(LogModule.TRANS, f"[JSON_TRANSLATOR] Task {task_id}: Retrieved {len(excluded_set)} excluded_segments from ExclusionManager. "
                        f"Excluded indices: {sorted(excluded_set)[:20]}{'...' if len(excluded_set) > 20 else ''}")
                else:
                    self.logger.debug(LogModule.TRANS, f"[JSON_TRANSLATOR] Task {task_id}: No excluded_segments found from ExclusionManager")
            except Exception as e:
                self.logger.warning(LogModule.TRANS, f"[JSON_TRANSLATOR] Failed to get excluded segments: {e}")

        # Always exclude ARB metadata segments (no translation / no update)
        if arb_meta_indices:
            self.logger.info(
                LogModule.TRANS,
                f"[JSON_TRANSLATOR] Excluding {len(arb_meta_indices)} ARB metadata segments from translation: "
                f"indices={sorted(arb_meta_indices)}",
            )
            excluded_set.update(arb_meta_indices)

        # Filter out excluded segments
        translate_indices = [i for i in range(len(original_texts)) if i not in excluded_set]
        texts_for_translation = [original_texts[i] for i in translate_indices]
        update_targets_for_translation = [update_targets[i] for i in translate_indices]

        if excluded_set:
            self.logger.info(LogModule.TRANS, f"[JSON_TRANSLATOR] Skipping translation for {len(excluded_set)} excluded segments: {sorted(excluded_set)[:20]}{'...' if len(excluded_set) > 20 else ''}")

        if not texts_for_translation:
            # All segments are excluded, keep original text
            self.logger.info(LogModule.TRANS, f"[JSON_TRANSLATOR] All segments are excluded, keeping original JSON unchanged")
            return self

        if self.glossary_agent:
            self.glossary_dict_gen = self.glossary_agent.send_segments(texts_for_translation, self.chunk_size)
            if self.translate_agent:
                self.translate_agent.update_glossary_dict(self.glossary_dict_gen)

        # Step 2: Batch translate extracted text (only non-excluded segments)
        if self.translate_agent:
            translated_segments = self.translate_agent.send_segments(texts_for_translation, self.chunk_size)
        else:
            translated_segments = texts_for_translation

        if len(texts_for_translation) != len(translated_segments):
            raise ValueError("The number of items returned by translation service does not match the number sent.")

        # Step 3: Map translated segments back to original positions
        # Create a mapping: segment_index -> translated_text
        translated_texts = list(original_texts)  # Initialize with original texts
        for idx, segment_idx in enumerate(translate_indices):
            if idx < len(translated_segments):
                translated_texts[segment_idx] = translated_segments[idx]

        # Step 4: Write translation results back to original JSON object
        # For excluded segments, original_texts[segment_idx] will be used (no change)
        self._apply_translations(update_targets, translated_texts)

        # Preserve JSON layout (newlines) when available so export matches original format
        json_layout = None
        if task_state:
            json_layout = (task_state.get("segments_metadata") or {}).get("json_layout")
        if json_layout and isinstance(content, dict):
            try:
                from utils.json_layout import dump_json_preserving_layout
                json_str = dump_json_preserving_layout(content, json_layout)
                document.content = json_str.encode('utf-8')
            except Exception as e:
                self.logger.warning(
                    LogModule.TRANS,
                    f"[JSON_TRANSLATOR] json_layout dump failed, using default: {e}",
                )
                document.content = json.dumps(content, ensure_ascii=False, indent=2).encode('utf-8')
        else:
            document.content = json.dumps(content, ensure_ascii=False, indent=2).encode('utf-8')

        # CRITICAL: Record translation segments if task_id is provided
        # This ensures segments are recorded using the actual segments used in translation (not re-extracted)
        # Similar to DOCX workflow, where translator records segments directly
        if task_id and len(original_texts) == len(translated_texts):
            try:
                self.logger.info(
                    LogModule.TRANS,
                    f"[JSON_TRANSLATOR] About to record_translation_segments for task {task_id}, segments={len(original_texts)}",
                )
                from utils.translation_segments import record_translation_segments
                from backend.app.services.task import task_manager
                from logger.logger import LogModule
                task_state_for_recording = task_manager.get_task(task_id)
                
                if task_state_for_recording:
                    # Get platform key from task_state (set during task initialization)
                    platform_key = task_state_for_recording.get("platform_key")
                    self.logger.info(LogModule.TRANS, f"Recording {len(original_texts)} translation segments for task {task_id}")
                    
                    # Get excluded segments for recording.
                    # IMPORTANT: ARB metadata indices (arb_meta_indices) are excluded from translation,
                    # but they are not true "exclusions" from the user's perspective and do not carry ExclusionReason.
                    # To avoid data inconsistency in record_translation_segments, we do NOT include them here.
                    excluded_set_for_recording = (
                        excluded_set - arb_meta_indices if excluded_set else set()
                    )
                    excluded_segments_for_recording = (
                        sorted(excluded_set_for_recording)
                        if excluded_set_for_recording
                        else None
                    )
                    if excluded_segments_for_recording:
                        self.logger.info(LogModule.TRANS, f"[JSON_TRANSLATOR] Using {len(excluded_segments_for_recording)} excluded_segments for recording: {excluded_segments_for_recording[:10]}...")
                    
                    # CRITICAL: For JSON workflow, original_texts and translated_texts are segments (not chunks)
                    # We need to pass chunk_to_segment_map=None to let record_translation_segments correctly identify them as segments
                    record_translation_segments(
                        task_id=task_id,
                        source_chunks=original_texts,
                        target_chunks=translated_texts,
                        original_filename=getattr(self, "_original_filename", None),
                        workflow_type=getattr(self, "_workflow_type", None),
                        source_lang=None,
                        target_lang=self.config.to_lang
                        if hasattr(self.config, "to_lang")
                        else None,
                        platform_key=platform_key,
                        task_state=task_state_for_recording,
                        excluded_segments=excluded_segments_for_recording,
                        chunk_to_segment_map=None,  # CRITICAL: Pass None to indicate these are segments, not chunks
                        arb_metadata_indices=list(arb_meta_indices)
                        if arb_meta_indices
                        else None,
                    )
                    self.logger.info(LogModule.TRANS, f"Successfully recorded translation segments for task {task_id}")
                else:
                    self.logger.warning(LogModule.TRANS, f"Task state not found for task {task_id}, cannot record segments")
            except Exception as e:
                # Log error but don't fail translation (frontend can still get source preview)
                self.logger.error(
                    LogModule.TRANS,
                    f"[JSON_TRANSLATOR] Failed to record translation segments for task {task_id}: {e}",
                    exc_info=True,
                )
        else:
            if not task_id:
                self.logger.debug(LogModule.TRANS, "No task_id provided, skipping segment recording")
            elif len(original_texts) != len(translated_texts):
                self.logger.warning(LogModule.TRANS, f"Source segments ({len(original_texts)}) and target segments ({len(translated_texts)}) "
                    f"count mismatch, skipping segment recording")
        
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
                self.logger.warning(LogModule.TRANS, f"[JSON_TRANSLATOR] Failed to save API logs: {log_e}", exc_info=True)

        return self

    async def translate_async(self, document: Document) -> Self:
        content = json.loads(document.content.decode())

        # --- Step 1: Try to use cached segments from Extract phase for consistency ---
        task_id = getattr(self, '_task_id', None)
        task_state = None
        cached_segments = None
        segment_info = None
        if task_id:
            try:
                from backend.app.services.task import task_manager
                from logger.logger import LogModule
                task_state = task_manager.get_task(task_id) if task_id else None
                if task_state:
                    cache_info = task_state.get("source_chunks_cache", {})
                    cached_segments = cache_info.get("segments", [])
                    segments_metadata = task_state.get("segments_metadata", {})
                    segment_info = segments_metadata.get("segment_info", [])
                    if cached_segments:
                        self.logger.info(
                            LogModule.TRANS,
                            f"[JSON_TRANSLATOR] Found {len(cached_segments)} cached segments from Extract phase. "
                            f"Will use cached segments to ensure consistency with chunk mapping.",
                        )
            except Exception as e:
                self.logger.debug(LogModule.TRANS, f"[JSON_TRANSLATOR] Failed to get cached segments: {e}")

        # --- Step 2: CRITICAL - Must use cached segments from Extract phase, no fallback ---
        if not cached_segments or len(cached_segments) == 0:
            raise ValueError(
                f"[JSON_TRANSLATOR] CRITICAL: Cached segments from Extract phase are not available. "
                f"This should not happen. Extract phase must be completed before Translate phase."
            )
        
        # CRITICAL: Always use cached segments from Extract phase to ensure consistency
        original_texts = [str(s) for s in cached_segments]
        self.logger.info(
            LogModule.TRANS,
            f"[JSON_TRANSLATOR] Using {len(original_texts)} cached segments from Extract phase "
            f"(no re-extraction) to ensure consistency with chunk mapping",
        )

        # Rebuild update_targets from segment_info.paths
        update_targets: list[tuple[Any, Any]] = []
        # For ARB files: skip metadata keys starting with "@" (e.g. "@@locale", "@settingsGeneralTitle")
        arb_meta_indices: set[int] = set()

        if not segment_info or len(segment_info) != len(cached_segments):
            # CRITICAL: segment_info is missing or count mismatch, we must complement it
            self.logger.warning(
                LogModule.TRANS,
                f"[JSON_TRANSLATOR] segment_info missing or count mismatch "
                f"(segments={len(cached_segments)}, segment_info={len(segment_info) if segment_info else 0}). "
                f"Will complement missing paths by searching JSON structure.",
            )
            # Complement missing segment_info by finding paths for each segment
            for idx, seg_text in enumerate(original_texts):
                if (
                    segment_info
                    and idx < len(segment_info)
                    and isinstance(segment_info[idx], dict)
                    and "paths" in segment_info[idx]
                ):
                    paths = segment_info[idx]["paths"]
                    if paths and len(paths) > 0:
                        path_str = paths[0]
                    else:
                        # Path is empty, find it
                        path_str = self._find_path_for_text(
                            content, seg_text, self.json_paths
                        )
                        if not path_str:
                            raise ValueError(
                                f"[JSON_TRANSLATOR] CRITICAL: Cannot find path for segment {idx}: '{seg_text[:50]}...'. "
                                f"This segment cannot be updated in the JSON structure."
                            )
                else:
                    # segment_info is missing for this segment, find path
                    path_str = self._find_path_for_text(
                        content, seg_text, self.json_paths
                    )
                    if not path_str:
                        raise ValueError(
                            f"[JSON_TRANSLATOR] CRITICAL: Cannot find path for segment {idx}: '{seg_text[:50]}...'. "
                            f"This segment cannot be updated in the JSON structure."
                        )

                # ARB metadata keys (starting with "@") should not be translated.
                # Their JSONPath-style representation from Extract is like "$.@@locale" or "$.@settingsGeneralTitle...".
                if isinstance(path_str, str) and path_str.startswith("$.@"):
                    self.logger.info(
                        LogModule.TRANS,
                        f"[JSON_TRANSLATOR] Skipping ARB metadata segment {idx} with path '{path_str}'",
                    )
                    # Use a no-op update target to keep indices aligned; _apply_translations will ignore it.
                    update_targets.append((None, None))
                    arb_meta_indices.add(idx)
                    continue

                # Rebuild update_target from found path
                targets = self._rebuild_update_targets_from_paths(
                    content, [path_str]
                )
                if targets:
                    update_targets.extend(targets)
                else:
                    # If we cannot rebuild update_target for this segment, log and skip it
                    self.logger.warning(
                        LogModule.TRANS,
                        f"[JSON_TRANSLATOR] CRITICAL: Failed to rebuild update_target from path '{path_str}' "
                        f"for segment {idx}. This segment will be kept as original and skipped from translation.",
                    )
                    update_targets.append((None, None))
        else:
            # segment_info is available and count matches
            for idx, seg_info in enumerate(segment_info):
                if not isinstance(seg_info, dict) or "paths" not in seg_info:
                    # segment_info is missing 'paths' key, find it
                    seg_text = original_texts[idx] if idx < len(original_texts) else ""
                    path_str = self._find_path_for_text(
                        content, seg_text, self.json_paths
                    )
                    if not path_str:
                        raise ValueError(
                            f"[JSON_TRANSLATOR] CRITICAL: segment_info[{idx}] missing 'paths' and cannot find path "
                            f"for segment: '{seg_text[:50]}...'. This segment cannot be updated."
                        )
                    targets = self._rebuild_update_targets_from_paths(
                        content, [path_str]
                    )
                    if targets:
                        update_targets.extend(targets)
                    else:
                        self.logger.warning(
                            LogModule.TRANS,
                            f"[JSON_TRANSLATOR] CRITICAL: Failed to rebuild update_target from found path '{path_str}' "
                            f"for segment {idx}. This segment will be kept as original and skipped from translation.",
                        )
                        update_targets.append((None, None))
                else:
                    paths = seg_info["paths"]
                    if not paths or len(paths) == 0:
                        # Path is empty, find it
                        seg_text = original_texts[idx] if idx < len(original_texts) else ""
                        path_str = self._find_path_for_text(
                            content, seg_text, self.json_paths
                        )
                        if not path_str:
                            raise ValueError(
                                f"[JSON_TRANSLATOR] CRITICAL: segment_info[{idx}].paths is empty and cannot find path "
                                f"for segment: '{seg_text[:50]}...'. This segment cannot be updated."
                            )
                        targets = self._rebuild_update_targets_from_paths(
                            content, [path_str]
                        )
                        if targets:
                            update_targets.extend(targets)
                        else:
                            self.logger.warning(
                                LogModule.TRANS,
                                f"[JSON_TRANSLATOR] CRITICAL: Failed to rebuild update_target from found path '{path_str}' "
                                f"for segment {idx}. This segment will be kept as original and skipped from translation.",
                            )
                            update_targets.append((None, None))
                    else:
                        # Use first path (each segment typically has one path)
                        path_str = paths[0]
                        # ARB metadata keys (starting with "@") should not be translated.
                        if isinstance(path_str, str) and path_str.startswith("$.@"):
                            self.logger.info(
                                LogModule.TRANS,
                                f"[JSON_TRANSLATOR] Skipping ARB metadata segment {idx} with path '{path_str}'",
                            )
                            update_targets.append((None, None))
                            arb_meta_indices.add(idx)
                        else:
                            targets = self._rebuild_update_targets_from_paths(
                                content, [path_str]
                            )
                            if targets:
                                update_targets.extend(targets)
                            else:
                                self.logger.warning(
                                    LogModule.TRANS,
                                    f"[JSON_TRANSLATOR] CRITICAL: Failed to rebuild update_target from path '{path_str}' "
                                    f"for segment {idx}. This segment will be kept as original and skipped from translation.",
                                )
                                update_targets.append((None, None))

        # Verify update_targets count matches original_texts
        if len(update_targets) != len(original_texts):
            # Instead of failing the whole task, log and pad with no-op targets
            self.logger.warning(
                LogModule.TRANS,
                f"[JSON_TRANSLATOR] CRITICAL: update_targets count mismatch "
                f"(segments={len(original_texts)}, targets={len(update_targets)}). "
                f"Padding with no-op targets to keep JSON structure unchanged.",
            )
            while len(update_targets) < len(original_texts):
                update_targets.append((None, None))

        if not original_texts:
            return self

        # CRITICAL: Filter excluded segments before translation
        # Get excluded segments using ExclusionManager (single source of truth)
        # task_state is already retrieved above, reuse it here
        excluded_set = set()
        if task_id and task_state:
            try:
                from exclusion.core import ExclusionManager
                from logger.logger import LogModule
                excluded_segments_with_reasons = ExclusionManager.get_excluded_segments(task_state)
                excluded_set = set(excluded_segments_with_reasons.keys())
                if excluded_set:
                    self.logger.info(LogModule.TRANS, f"[JSON_TRANSLATOR] Task {task_id}: Retrieved {len(excluded_set)} excluded_segments from ExclusionManager. "
                        f"Excluded indices: {sorted(excluded_set)[:20]}{'...' if len(excluded_set) > 20 else ''}")
                else:
                    self.logger.debug(LogModule.TRANS, f"[JSON_TRANSLATOR] Task {task_id}: No excluded_segments found from ExclusionManager")
            except Exception as e:
                self.logger.warning(LogModule.TRANS, f"[JSON_TRANSLATOR] Failed to get excluded segments: {e}")

        # Always exclude ARB metadata segments (no translation / no update)
        if arb_meta_indices:
            self.logger.info(
                LogModule.TRANS,
                f"[JSON_TRANSLATOR] Excluding {len(arb_meta_indices)} ARB metadata segments from translation: "
                f"indices={sorted(arb_meta_indices)}",
            )
            excluded_set.update(arb_meta_indices)

        # Filter out excluded segments
        translate_indices = [
            i for i in range(len(original_texts)) if i not in excluded_set
        ]
        texts_for_translation = [original_texts[i] for i in translate_indices]
        update_targets_for_translation = [update_targets[i] for i in translate_indices]

        if excluded_set:
            self.logger.info(LogModule.TRANS, f"[JSON_TRANSLATOR] Skipping translation for {len(excluded_set)} excluded segments: {sorted(excluded_set)[:20]}{'...' if len(excluded_set) > 20 else ''}")

        if not texts_for_translation:
            # All segments are excluded, keep original text
            self.logger.info(LogModule.TRANS, f"[JSON_TRANSLATOR] All segments are excluded, keeping original JSON unchanged")
            return self

        if self.glossary_agent:
            self.glossary_dict_gen = await self.glossary_agent.send_segments_async(texts_for_translation, self.chunk_size)
            if self.translate_agent:
                self.translate_agent.update_glossary_dict(self.glossary_dict_gen)

        # Step 2: Batch translate extracted text (only non-excluded segments)
        # Pass progress_callback so status shows "Translating... X/Y" instead of stuck "Detect Language: 100%"
        progress_callback = getattr(self, "_progress_callback", None)
        if self.translate_agent:
            self.logger.info(
                LogModule.TRANS,
                f"[JSON_TRANSLATOR] Calling send_segments_async: {len(texts_for_translation)} segments, "
                f"progress_callback={progress_callback is not None}",
            )
            try:
                translated_segments = await self.translate_agent.send_segments_async(
                    texts_for_translation, self.chunk_size, progress_callback=progress_callback
                )
                self.logger.info(
                    LogModule.TRANS,
                    f"[JSON_TRANSLATOR] send_segments_async returned: {len(translated_segments)} segments",
                )
            except Exception as send_err:
                self.logger.error(
                    LogModule.TRANS,
                    f"[JSON_TRANSLATOR] send_segments_async failed: {send_err}",
                    exc_info=True,
                )
                raise
        else:
            translated_segments = texts_for_translation

        if len(texts_for_translation) != len(translated_segments):
            raise ValueError("The number of items returned by translation service does not match the number sent.")

        # Step 3: Map translated segments back to original positions
        # Create a mapping: segment_index -> translated_text
        translated_texts = list(original_texts)  # Initialize with original texts
        for idx, segment_idx in enumerate(translate_indices):
            if idx < len(translated_segments):
                translated_texts[segment_idx] = translated_segments[idx]

        # Step 4: Write translation results back to original JSON object
        # For excluded segments, original_texts[segment_idx] will be used (no change)
        self._apply_translations(update_targets, translated_texts)

        # Preserve JSON layout (newlines) when available so export matches original format
        json_layout = None
        if task_state:
            json_layout = (task_state.get("segments_metadata") or {}).get("json_layout")
        if json_layout and isinstance(content, dict):
            try:
                from utils.json_layout import dump_json_preserving_layout
                json_str = dump_json_preserving_layout(content, json_layout)
                document.content = json_str.encode('utf-8')
            except Exception as e:
                self.logger.warning(
                    LogModule.TRANS,
                    f"[JSON_TRANSLATOR] json_layout dump failed, using default: {e}",
                )
                document.content = json.dumps(content, ensure_ascii=False, indent=2).encode('utf-8')
        else:
            document.content = json.dumps(content, ensure_ascii=False, indent=2).encode('utf-8')

        # CRITICAL: Record translation segments if task_id is provided
        # This ensures segments are recorded using the actual segments used in translation (not re-extracted)
        # Similar to DOCX workflow, where translator records segments directly
        if task_id and len(original_texts) == len(translated_texts):
            try:
                self.logger.info(
                    LogModule.TRANS,
                    f"[JSON_TRANSLATOR] About to record_translation_segments for task {task_id}, segments={len(original_texts)}",
                )
                from utils.translation_segments import record_translation_segments
                from backend.app.services.task import task_manager
                from logger.logger import LogModule
                task_state_for_recording = task_manager.get_task(task_id)
                
                if task_state_for_recording:
                    # Get platform key from task_state (set during task initialization)
                    platform_key = task_state_for_recording.get("platform_key")
                    self.logger.info(LogModule.TRANS, f"Recording {len(original_texts)} translation segments for task {task_id}")
                    
                    # Get excluded segments for recording.
                    # IMPORTANT: ARB metadata indices (arb_meta_indices) are excluded from translation,
                    # but they are not true "exclusions" from the user's perspective and do not carry ExclusionReason.
                    # To avoid data inconsistency in record_translation_segments, we do NOT include them here.
                    excluded_set_for_recording = (
                        excluded_set - arb_meta_indices if excluded_set else set()
                    )
                    excluded_segments_for_recording = (
                        sorted(excluded_set_for_recording)
                        if excluded_set_for_recording
                        else None
                    )
                    if excluded_segments_for_recording:
                        self.logger.info(LogModule.TRANS, f"[JSON_TRANSLATOR] Using {len(excluded_segments_for_recording)} excluded_segments for recording: {excluded_segments_for_recording[:10]}...")
                    
                    # CRITICAL: For JSON workflow, original_texts and translated_texts are segments (not chunks)
                    # We need to pass chunk_to_segment_map=None to let record_translation_segments correctly identify them as segments
                    record_translation_segments(
                        task_id=task_id,
                        source_chunks=original_texts,
                        target_chunks=translated_texts,
                        original_filename=getattr(self, "_original_filename", None),
                        workflow_type=getattr(self, "_workflow_type", None),
                        source_lang=None,
                        target_lang=self.config.to_lang
                        if hasattr(self.config, "to_lang")
                        else None,
                        platform_key=platform_key,
                        task_state=task_state_for_recording,
                        excluded_segments=excluded_segments_for_recording,
                        chunk_to_segment_map=None,  # CRITICAL: Pass None to indicate these are segments, not chunks
                        arb_metadata_indices=list(arb_meta_indices)
                        if arb_meta_indices
                        else None,
                    )
                    self.logger.info(LogModule.TRANS, f"Successfully recorded translation segments for task {task_id}")
                else:
                    self.logger.warning(LogModule.TRANS, f"Task state not found for task {task_id}, cannot record segments")
            except Exception as e:
                # Log error but don't fail translation (frontend can still get source preview)
                self.logger.error(
                    LogModule.TRANS,
                    f"[JSON_TRANSLATOR] Failed to record translation segments for task {task_id}: {e}",
                    exc_info=True,
                )
        else:
            if not task_id:
                self.logger.debug(LogModule.TRANS, "No task_id provided, skipping segment recording")
            elif len(original_texts) != len(translated_texts):
                self.logger.warning(LogModule.TRANS, f"Source segments ({len(original_texts)}) and target segments ({len(translated_texts)}) "
                    f"count mismatch, skipping segment recording")
        
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
                self.logger.warning(LogModule.TRANS, f"[JSON_TRANSLATOR] Failed to save API logs: {log_e}", exc_info=True)
        
        return self
