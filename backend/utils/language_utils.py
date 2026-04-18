# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

"""
Language utility functions for converting between language codes and full names.
"""


def get_language_name_from_code(lang_code: str) -> str:
    """
    Convert language code to full English language name for better AI recognition.
    
    This function is used in AI prompts to convert shorthand language codes (e.g., "zh")
    to full language names (e.g., "Chinese") for better model understanding.
    
    Args:
        lang_code: Language code (e.g., 'zh', 'en', 'ja', 'zh-CN', 'en-US')
        
    Returns:
        Full English language name (e.g., 'Chinese', 'English', 'Japanese')
        Falls back to the original code if not found in the mapping.
    
    Examples:
        >>> get_language_name_from_code('zh')
        'Chinese'
        >>> get_language_name_from_code('zh-CN')
        'Chinese'
        >>> get_language_name_from_code('en')
        'English'
        >>> get_language_name_from_code('unknown')
        'unknown'
    """
    if not lang_code:
        return lang_code

    # Normalize and handle special variants first (e.g. Traditional Chinese)
    lower = lang_code.lower().strip()
    # Treat common Traditional Chinese variants explicitly so prompts can
    # distinguish them from Simplified Chinese.
    if lower in {'zh-tw', 'zh_hant', 'zh-hant', 'zh-hk', 'zh-hant-hk', 'zh-hant-mo'}:
        return "Chinese (Traditional)"

    # Map language codes to full names
    # This is the reverse mapping of full_name_map in translation_segments.py
    code_to_name_map = {
        'zh': 'Chinese',
        'en': 'English',
        'ja': 'Japanese',
        'ko': 'Korean',
        'fr': 'French',
        'de': 'German',
        'es': 'Spanish',
        'ru': 'Russian',
        'it': 'Italian',
        'pt': 'Portuguese',
        'ar': 'Arabic',
        'bn': 'Bengali',
        'ca': 'Catalan',
        'cs': 'Czech',
        'hr': 'Croatian',
        'da': 'Danish',
        'nl': 'Dutch',
        'fil': 'Filipino',
        'fi': 'Finnish',
        'el': 'Greek',
        'he': 'Hebrew',
        'hi': 'Hindi',
        'km': 'Khmer',
        'lt': 'Lithuanian',
        'mk': 'Macedonian',
        'ms': 'Malay',
        'nb': 'Norwegian',
        'pl': 'Polish',
        'ro': 'Romanian',
        'sl': 'Slovenian',
        'sv': 'Swedish',
        'th': 'Thai',
        'tr': 'Turkish',
        'uk': 'Ukrainian',
        'ur': 'Urdu',
        'vi': 'Vietnamese',
    }
    
    # Normalize language code (handle variations like 'zh-CN', 'en-US')
    # Extract base code by splitting on '-' and taking the first part
    normalized_code = lower.split('-')[0]

    # Return full name if found, otherwise return original code
    return code_to_name_map.get(normalized_code, lang_code)
