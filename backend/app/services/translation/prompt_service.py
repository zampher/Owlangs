# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

"""
Prompt Service

Handles prompt synthesis and smart glossary matching.
"""

from typing import Any, Dict

from logger import unified_logger as logger
from logger.logger import LogModule


from utils.language_utils import get_language_name_from_code


class PromptService:
    """Service for prompt synthesis and glossary matching."""
    
    def synthesize_prompt(self, payload: Any) -> str:
        """
        Synthesize final prompt from payload controls.
        
        Args:
            payload: Task payload (dict or object)
            
        Returns:
            Synthesized prompt string
        """
        try:
            # Support both dict and object access
            if isinstance(payload, dict):
                mode = payload.get('prompt_mode', 'off') or 'off'
                style = (payload.get('prompt_style') or '').lower()
                note = payload.get('custom_note') or ''
                to_lang_code = payload.get('to_lang', 'en')
            else:
                mode = getattr(payload, 'prompt_mode', 'off') or 'off'
                style = (getattr(payload, 'prompt_style', None) or '').lower()
                note = getattr(payload, 'custom_note', None) or ''
                to_lang_code = getattr(payload, 'to_lang', 'en')
            
            # Convert language code to full language name for better AI recognition
            to_lang_name = get_language_name_from_code(to_lang_code)
            
            # System skeleton — avoid "chat assistant" phrasing that triggers conversational replies on small models
            parts = [
                "Additional translation rules (follow together with system SEG format rules):",
                "- Translate faithfully; do not omit, merge, invent, or skip any segment.",
                "- Preserve structure, numbering, spacing, inline code, formulas, and punctuation.",
                f"- Output language: {to_lang_name}.",
                "- When a glossary is provided, strictly apply term replacements.",
            ]
            
            # Language-pair light constraints (placeholder)
            # Use original code for language-specific checks
            lower_code = to_lang_code.lower()
            if lower_code.startswith('en'):
                parts.append("- Use concise, natural English; keep units and symbols unchanged.")
            if lower_code.startswith('zh'):
                # Generic Chinese guidance
                parts.append("- 使用地道、自然的中文表达，专有名词保持一致。")
                # Additional constraint for Traditional Chinese targets
                if any(s in lower_code for s in ('zh-tw', 'zh_hant', 'zh-hant', 'zh-hk')):
                    parts.append("- 请使用繁体中文书写译文，避免使用简体字。")
            
            # Style
            if mode in ('simple', 'advanced'):
                if style:
                    parts.append(f"- Translation style: {style}.")
                if note:
                    parts.append(f"- Additional note: {note}.")
            
            synthesized = "\n".join(parts)
            
            logger.debug(LogModule.TRANS, f"  - prompt_mode: {mode}")
            logger.debug(LogModule.TRANS, f"  - prompt_style: {style}")
            logger.debug(LogModule.TRANS, f"  - custom_note: {note}")
            logger.debug(LogModule.TRANS, f"  - Final synthesized prompt:\n{synthesized}")
            
            return synthesized
        except Exception as e:
            logger.warning(LogModule.TRANS, f"Failed to synthesize prompt: {e}", exc_info=True)
            # Return default prompt
            return "You are a professional translation assistant."
    
    def apply_smart_glossary_matching(
        self,
        translator_args: Dict[str, Any],
        payload: Any
    ) -> Dict[str, Any]:
        """
        Apply smart glossary matching to translator args.
        
        Args:
            translator_args: Translator arguments dictionary
            payload: Task payload
            
        Returns:
            Updated translator arguments dictionary
        """
        try:
            # Get smart_glossary_matching flag from task_state or payload
            # This is set in _start_translation_task based on request or config
            task_id = translator_args.get('task_id')
            task_state = None
            if task_id:
                from backend.app.services.task import task_manager
                task_state = task_manager.get_task(task_id)
                if task_state:
                    smart_glossary = task_state.get("smart_glossary_matching")
                    if smart_glossary is not None:
                        logger.debug(LogModule.TRANS, f"[GLOSSARY] Task {task_id}: Using smart_glossary_matching={smart_glossary} from task_state")
                    else:
                        # Fallback to payload
                        if isinstance(payload, dict):
                            smart_glossary = payload.get('smart_glossary_matching', False)
                        else:
                            smart_glossary = getattr(payload, 'smart_glossary_matching', False)
                        logger.debug(LogModule.TRANS, f"[GLOSSARY] Task {task_id}: Using smart_glossary_matching={smart_glossary} from payload")
                else:
                    smart_glossary = False
            else:
                smart_glossary = False
            
            # Get glossary from payload or task_state
            glossary = {}
            
            # Priority 1: Check task_state["applied_glossary"] (set by applyGlossaryToTask API)
            if task_id and task_state:
                applied_glossary = task_state.get("applied_glossary")
                logger.debug(LogModule.TRANS, f"[GLOSSARY] Task {task_id}: Checking applied_glossary in task_state: {applied_glossary is not None}")
                if applied_glossary and isinstance(applied_glossary, dict):
                    glossary_dict = applied_glossary.get("glossary_dict", {})
                    logger.debug(LogModule.TRANS, f"[GLOSSARY] Task {task_id}: Found glossary_dict in applied_glossary: {glossary_dict is not None}, size: {len(glossary_dict) if glossary_dict else 0}")
                    if glossary_dict:
                        glossary = glossary_dict.copy()
                        logger.info(LogModule.TRANS, f"[GLOSSARY] Task {task_id}: Loaded {len(glossary)} entries from task_state['applied_glossary']")
                        sample = dict(list(glossary.items())[:3])
                        logger.debug(LogModule.TRANS, f"[GLOSSARY] Task {task_id}: Sample entries: {sample}")
                    else:
                        logger.debug(LogModule.TRANS, f"[GLOSSARY] Task {task_id}: glossary_dict is empty or None")
                else:
                    logger.debug(LogModule.TRANS, f"[GLOSSARY] Task {task_id}: applied_glossary is not a dict or is None")
            else:
                if not task_id:
                    logger.debug(LogModule.TRANS, f"[GLOSSARY] No task_id provided, cannot check task_state")
                elif not task_state:
                    logger.debug(LogModule.TRANS, f"[GLOSSARY] Task {task_id} not found in task_state")
            
            # Priority 2: Check payload.glossary_dict or payload.glossary (if not already loaded from task_state)
            if not glossary:
                if isinstance(payload, dict):
                    # Try glossary_dict first (matches Pydantic model field name), then fallback to glossary
                    glossary = payload.get('glossary_dict') or payload.get('glossary', {})
                    logger.debug(LogModule.TRANS, f"[GLOSSARY] Task {task_id}: Checking payload.glossary_dict/glossary (dict), found: {glossary is not None}, type: {type(glossary)}, size: {len(glossary) if isinstance(glossary, dict) else 'N/A'}")
                    if glossary:
                        sample = dict(list(glossary.items())[:3]) if isinstance(glossary, dict) else {}
                        logger.debug(LogModule.TRANS, f"[GLOSSARY] Task {task_id}: Payload glossary sample: {sample}")
                else:
                    # Try glossary_dict first (matches Pydantic model field name), then fallback to glossary
                    glossary = getattr(payload, 'glossary_dict', None) or getattr(payload, 'glossary', {}) or {}
                    logger.debug(LogModule.TRANS, f"[GLOSSARY] Task {task_id}: Checking payload.glossary_dict/glossary (object), found: {glossary is not None}, type: {type(glossary)}, size: {len(glossary) if isinstance(glossary, dict) else 'N/A'}")
            
            if not glossary:
                logger.debug(LogModule.TRANS, f"[GLOSSARY] No glossary provided for task {task_id}")
                return translator_args
            
            # Apply smart matching if enabled
            if smart_glossary:
                try:
                    from utils.glossary_utils import apply_smart_glossary_matching as apply_smart
                    glossary = apply_smart(glossary, task_id=task_id)
                    logger.debug(LogModule.TRANS, f"[GLOSSARY] Applied smart glossary matching for task {task_id}")
                except ImportError:
                    logger.warning(LogModule.TRANS, f"[GLOSSARY] Smart glossary matching not available, using original glossary")
                except Exception as e:
                    logger.warning(LogModule.TRANS, f"[GLOSSARY] Failed to apply smart glossary matching: {e}", exc_info=True)
            
            translator_args['glossary_dict'] = glossary
            
            final_glossary = translator_args.get('glossary_dict')
            if final_glossary:
                logger.debug(LogModule.TRANS, f"Final glossary dict to be passed to translator for task {task_id}: {len(final_glossary)} entries")
            else:
                logger.debug(LogModule.TRANS, f"No glossary dict for task {task_id}")
            
            return translator_args
        except Exception as e:
            logger.warning(LogModule.TRANS, f"Failed to apply smart glossary matching: {e}", exc_info=True)
            return translator_args


# Global singleton instance
prompt_service = PromptService()

