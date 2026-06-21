# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

"""
Exclusion detection function for translation segments.
"""

from typing import Optional, Tuple

from layout.block_types import IMAGE_CAPTION, CAPTION, TABLE_BODY, TABLE_CAPTION, TABLE_FOOTNOTE, CHART_BODY
from logger import unified_logger as logger
from logger.logger import LogModule
from exclusion.core.exclusion_reason import ExclusionReason


def detect_exclusion_reason(
    text: str,
    block_type: Optional[str] = None,
    target_lang: Optional[str] = None,
    is_image: bool = False,
    is_table: bool = False,
    strict_table_priority: bool = False
) -> Optional[Tuple[ExclusionReason, dict]]:
    """
    Detect exclusion reason for a segment.
    
    Priority order depends on strict_table_priority:
    
    If strict_table_priority=True (PDF format):
    1. Image
    2. Formula
    3. Table (from block_type or is_table flag) - STRICT: Table takes priority over Identifier
    4. Identifier (URL, email, serial number, pure numbers, etc.)
    5. Reference (from block_type)
    6. Structural (from block_type)
    7. Language match (if target_lang provided)
    
    If strict_table_priority=False (other formats like DOCX, PPTX, etc.):
    1. Image
    2. Formula
    3. Identifier (URL, email, serial number, pure numbers, etc.) - Identifier takes priority over Table
       - This ensures table cells containing identifiers (e.g., "01", "02") are marked as IDENTIFIER, not TABLE
    4. Table (from block_type or is_table flag)
    5. Reference (from block_type)
    6. Structural (from block_type)
    7. Language match (if target_lang provided)
    
    Args:
        text: Segment text to check
        block_type: Optional block type from layout (e.g., "ref_text", "page_header", "table")
        target_lang: Optional target language code (e.g., 'zh', 'en')
        is_image: Whether segment is already identified as image
        is_table: Whether segment is already identified as table (for markdown/HTML workflows)
        strict_table_priority: If True, Table takes priority over Identifier (for PDF format)
    
    Returns:
        Tuple of (ExclusionReason, metadata_dict) if should be excluded, None otherwise.
        metadata_dict contains additional information (e.g., detected_lang for LANGUAGE_MATCH).
    """
    if not text or not text.strip():
        return None
    
    # Lazy import to avoid circular dependency
    from utils.translation_segments import (
        _is_image_segment,
        _is_formula_segment,
        _is_table_segment,
        _normalize_language_code_for_comparison
    )
    
    text_stripped = text.strip()
    
    # Priority 1: Image
    # CRITICAL: Do NOT exclude image_caption blocks as images
    # Image captions contain actual text content and should be translated, not excluded
    if block_type not in (IMAGE_CAPTION, CAPTION):
        if is_image or _is_image_segment(text_stripped):
            return (ExclusionReason.IMAGE, {})
    
    # Priority 2: Formula
    if _is_formula_segment(text_stripped):
        return (ExclusionReason.FORMULA, {})
    
    # Priority 3/4: Table vs Identifier (order depends on strict_table_priority)
    # For PDF: Table takes priority (strict_table_priority=True) - Table is strictly based on layout
    # For other formats: Identifier takes priority (strict_table_priority=False) - Identifier in table cells should be marked as IDENTIFIER
    
    # Check Table first if strict_table_priority is True (PDF format)
    # For PDF, if layout says it's a table, it's a table (no identifier override)
    if strict_table_priority:
        # Priority 3: Table Body (from block_type or is_table flag) - STRICT for PDF
        if block_type == TABLE_BODY or (is_table and block_type != TABLE_CAPTION and block_type != TABLE_FOOTNOTE) or _is_table_segment(text_stripped):
            return (ExclusionReason.TABLE, {"block_type": TABLE_BODY})
        # Priority 4: Chart Body (from block_type) - STRICT for PDF, optional exclusion
        if block_type == CHART_BODY:
            return (ExclusionReason.CHART, {"block_type": CHART_BODY})
    
    # Priority 3 (non-PDF) or Priority 5 (PDF): Identifier (URL, email, serial number, pure numbers, etc.)
    # For non-PDF formats: Identifier takes priority over Table
    # For PDF format: Identifier is checked after Table (only if not already identified as table)
    from exclusion.detection.identifier_detector import (
        is_identifier_pattern,
        _is_pure_number,
        _is_url,
        _is_email,
        _is_serial_number
    )
    
    # Check for obvious identifiers first (pure numbers, URLs, emails, serial numbers)
    is_pure_number = _is_pure_number(text_stripped)
    is_url = _is_url(text_stripped)
    is_email = _is_email(text_stripped)
    is_serial_number = _is_serial_number(text_stripped)
    
    if is_pure_number or is_url or is_email or is_serial_number:
        # For non-PDF: Obvious identifiers take priority over table
        # For PDF: Only check identifier if not already identified as table (strict_table_priority already handled table)
        if not strict_table_priority:
            logger.debug(
                LogModule.EXCLUSION,
                f"Detected IDENTIFIER exclusion reason for obvious identifier: "
                f"text='{text_stripped[:50]}{'...' if len(text_stripped) > 50 else ''}', "
                f"is_pure_number={is_pure_number}, is_url={is_url}, is_email={is_email}, is_serial_number={is_serial_number}"
            )
            return (ExclusionReason.IDENTIFIER, {})
        # For PDF: If already identified as table above, skip identifier check (strict table priority)
        # If not table, check identifier
        elif not (block_type == "table_body" or (is_table and block_type != "table_caption" and block_type != "table_footnote") or _is_table_segment(text_stripped)):
            logger.debug(
                LogModule.EXCLUSION,
                f"Detected IDENTIFIER exclusion reason for obvious identifier (PDF, non-table): "
                f"text='{text_stripped[:50]}{'...' if len(text_stripped) > 50 else ''}', "
                f"is_pure_number={is_pure_number}, is_url={is_url}, is_email={is_email}, is_serial_number={is_serial_number}"
            )
            return (ExclusionReason.IDENTIFIER, {})
    
    # Check for other identifier patterns (camelCase, uppercase, punctuation, etc.)
    if is_identifier_pattern(text_stripped, exclude_language_match=True):
        # Determine which identifier type matched for better logging
        identifier_type = "unknown"
        from exclusion.detection.identifier_detector import (
            _is_punctuation_only,
            _is_digits_and_special_chars_only,
            _is_camel_case_identifier,
            _is_uppercase_identifier
        )
        if _is_punctuation_only(text_stripped):
            identifier_type = "punctuation_only"
        elif _is_digits_and_special_chars_only(text_stripped):
            identifier_type = "digits_and_special_chars"
        elif _is_camel_case_identifier(text_stripped):
            identifier_type = "camel_case"
        elif _is_uppercase_identifier(text_stripped):
            identifier_type = "uppercase_identifier"
        
        # For non-PDF: These take priority over table
        # For PDF: Only if not already identified as table
        if not strict_table_priority:
            # Non-PDF: Identifier takes priority
            if target_lang:
                from exclusion.detection.language_match_detector import is_language_match
                match_result = is_language_match(text_stripped, target_lang)
                if match_result:
                    detected_lang, normalized_detected, normalized_target = match_result
                    logger.debug(
                        LogModule.EXCLUSION,
                        f"Identifier-like text also matches target language, but returning IDENTIFIER (priority): "
                        f"text='{text_stripped[:50]}...', "
                        f"detected_lang={detected_lang} (normalized={normalized_detected}), "
                        f"target_lang={target_lang} (normalized={normalized_target}), "
                        f"returning IDENTIFIER instead of LANGUAGE_MATCH for consistency"
                    )
                    return (ExclusionReason.IDENTIFIER, {
                        "detected_lang": detected_lang,
                        "target_lang": target_lang,
                        "also_language_match": True
                    })
            
            logger.debug(
                LogModule.EXCLUSION,
                f"Detected IDENTIFIER exclusion reason for text: '{text_stripped[:50]}{'...' if len(text_stripped) > 50 else ''}' "
                f"(type: {identifier_type})"
            )
            return (ExclusionReason.IDENTIFIER, {})
        else:
            # PDF: Only if not already identified as table (strict table priority)
            if not (block_type == TABLE_BODY or (is_table and block_type != TABLE_CAPTION and block_type != TABLE_FOOTNOTE) or _is_table_segment(text_stripped)):
                if target_lang:
                    from exclusion.detection.language_match_detector import is_language_match
                    match_result = is_language_match(text_stripped, target_lang)
                    if match_result:
                        detected_lang, normalized_detected, normalized_target = match_result
                        logger.debug(
                            LogModule.EXCLUSION,
                            f"Identifier-like text also matches target language, but returning IDENTIFIER (priority): "
                            f"text='{text_stripped[:50]}...', "
                            f"detected_lang={detected_lang} (normalized={normalized_detected}), "
                            f"target_lang={target_lang} (normalized={normalized_target}), "
                            f"returning IDENTIFIER instead of LANGUAGE_MATCH for consistency"
                        )
                        return (ExclusionReason.IDENTIFIER, {
                            "detected_lang": detected_lang,
                            "target_lang": target_lang,
                            "also_language_match": True
                        })
                
                logger.debug(
                    LogModule.EXCLUSION,
                    f"Detected IDENTIFIER exclusion reason for text (PDF, non-table): '{text_stripped[:50]}{'...' if len(text_stripped) > 50 else ''}' "
                    f"(type: {identifier_type})"
                )
                return (ExclusionReason.IDENTIFIER, {})
    
    # Priority 4 (non-PDF): Table Body (from block_type or is_table flag)
    # For non-PDF: Only check table if not already identified as identifier
    # For PDF: Already checked above (strict_table_priority=True), skip here
    if not strict_table_priority:
        if block_type == TABLE_BODY or (is_table and block_type != TABLE_CAPTION and block_type != TABLE_FOOTNOTE) or _is_table_segment(text_stripped):
            return (ExclusionReason.TABLE, {"block_type": TABLE_BODY})

    # Priority 5: Chart Body (from block_type) - optional exclusion, default not excluded
    if block_type == CHART_BODY:
        return (ExclusionReason.CHART, {"block_type": CHART_BODY})
    
    # Priority 6: Reference (from block_type)
    if block_type == "ref_text":
        return (ExclusionReason.REFERENCE, {"block_type": block_type})
    
    # Priority 6: Structural (from block_type)
    if block_type in ["header", "footer", "page_header", "page_footer", "footnote"]:
        return (ExclusionReason.STRUCTURAL, {"block_type": block_type})
    
    # Priority 7: Language match (if target_lang provided)
    if target_lang:
        from exclusion.detection.language_match_detector import is_language_match
        match_result = is_language_match(text_stripped, target_lang)
        if match_result:
            detected_lang, normalized_detected, normalized_target = match_result
            # NOTE: Removed verbose debug log for each language match detection to reduce log noise
            return (ExclusionReason.LANGUAGE_MATCH, {
                "detected_lang": detected_lang,
                "target_lang": target_lang
            })
        else:
            logger.trace(
                LogModule.EXCLUSION,
                f"Language mismatch: text='{text_stripped[:50]}{'...' if len(text_stripped) > 50 else ''}', "
                f"target_lang={target_lang}, match=False -> NOT excluded"
            )
    
    return None  # Should not be excluded
