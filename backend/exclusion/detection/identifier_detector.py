# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

"""
Identifier detection utilities for exclusion detection.

This module provides functions to detect identifier patterns in text,
which can be used for exclusion detection.
"""

import re
from typing import Optional

# Vowels (English) - only all-consonant letter sequences are treated as identifier
_LATIN_VOWELS = set("aeiouAEIOU")


def _is_all_consonants(s: str) -> bool:
    """True if s has at least one letter and every letter is a consonant (no vowel)."""
    letters = [c for c in s if c.isalpha()]
    if not letters:
        return False
    return not any(c in _LATIN_VOWELS for c in letters)


def _is_pure_number(text: str) -> bool:
    """Check if text is pure numbers (with optional separators like spaces, commas, periods, hyphens)."""
    if not text or not text.strip():
        return False
    
    text_stripped = text.strip()
    text_clean = text_stripped.replace(" ", "").replace(",", "").replace(".", "").replace("-", "")
    return text_clean and text_clean.isdigit()


def _is_url(text: str) -> bool:
    """Check if text contains a URL (http://, https://, www., ftp://, etc.)."""
    if not text or not text.strip():
        return False
    
    text_stripped = text.strip()
    
    # Pattern 1: URLs with protocol
    protocol_url_patterns = [
        r'https?://[^\s]+',
        r'ftp://[^\s]+',
        r'file://[^\s]+',
        r'mailto:[^\s]+',
    ]
    for pattern in protocol_url_patterns:
        # CRITICAL: Only search once, reuse match result
        match = re.search(pattern, text_stripped, re.IGNORECASE)
        if match:
            url_part = match.group(0)
            if '.' in url_part and re.search(r'\.[a-zA-Z]{2,}', url_part):
                # Only treat as URL-identifier when the surrounding text does not
                # contain real sentence content (letters/CJK). This prevents long
                # paragraphs that merely contain a URL from being classified as a
                # pure IDENTIFIER segment.
                prefix = text_stripped[: match.start()].strip()
                suffix = text_stripped[match.end() :].strip()

                def _has_real_text(s: str) -> bool:
                    for ch in s:
                        if ch.isalpha():
                            return True
                        # Basic CJK range
                        if "\u4e00" <= ch <= "\u9fff":
                            return True
                    return False

                if not _has_real_text(prefix) and not _has_real_text(suffix):
                    return True
    
    # Pattern 2: www. URLs
    www_pattern = r'\bwww\.[a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?(\.[a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?)*\.[a-zA-Z]{2,}'
    www_match = re.search(www_pattern, text_stripped, re.IGNORECASE)
    if www_match:
        prefix = text_stripped[: www_match.start()].strip()
        suffix = text_stripped[www_match.end() :].strip()

        def _has_real_text(s: str) -> bool:
            for ch in s:
                if ch.isalpha():
                    return True
                if "\u4e00" <= ch <= "\u9fff":
                    return True
            return False

        if not _has_real_text(prefix) and not _has_real_text(suffix):
            return True
    
    # Pattern 3: Domain without protocol
    if '.' in text_stripped and ' ' not in text_stripped:
        domain_pattern = r'^[a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?(\.[a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?)*\.[a-zA-Z]{2,}$'
        if re.match(domain_pattern, text_stripped):
            return True
    
    return False


def _is_email(text: str) -> bool:
    """Check if text is an email address."""
    if not text or not text.strip():
        return False
    
    # Normalize surrounding punctuation that often appears with emails in text,
    # e.g. "alec@openai.com," or "(alec@openai.com)".
    text_stripped = text.strip()
    # Strip common leading wrappers
    text_stripped = text_stripped.lstrip('<([{“"\'')
    # Strip common trailing punctuation/wrappers
    text_stripped = text_stripped.rstrip('>)]}”"\',.;:!?，。；？！')
    
    email_pattern = (
        r'^[a-zA-Z0-9]'
        r'([a-zA-Z0-9._+-]*[a-zA-Z0-9])?'
        r'@[a-zA-Z0-9]'
        r'([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?'
        r'(\.[a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?)*'
        r'\.[a-zA-Z]{2,}$'
    )
    return bool(re.match(email_pattern, text_stripped, re.IGNORECASE))


def _is_serial_number(text: str) -> bool:
    """Check if text is a serial number/identifier pattern."""
    if not text or not text.strip():
        return False
    
    text_stripped = text.strip()
    # CRITICAL: Early return for length check before expensive non-ASCII check
    if len(text_stripped) > 30:
        return False
    
    # CRITICAL: Optimize non-ASCII check - only check if text might contain non-ASCII
    # Most ASCII characters are < 128, so we can use a faster check
    has_non_ascii = not text_stripped.isascii()
    
    if has_non_ascii:
        return False
    
    # CRITICAL: Serial numbers generally don't contain spaces
    # If original text contains spaces, it's likely not a serial number (e.g., "Vol. 32" is a volume label, not a serial number)
    if " " in text_stripped:
        return False
    
    text_no_sep = text_stripped.replace("-", "").replace("_", "").replace(".", "")
    
    if text_no_sep and text_no_sep.isalnum():
        if re.match(r'^[A-Za-z]+\d{2,}$', text_no_sep):
            return True
        
        if re.match(r'^\d{2,}[A-Za-z]+$', text_no_sep):
            return True
        
        # Pure letters (upper or lower): treat as identifier only when all consonants
        if len(text_no_sep) <= 10 and (text_no_sep.isupper() or text_no_sep.islower()):
            if text_no_sep.isalpha() and len(text_no_sep) <= 8:
                if _is_all_consonants(text_no_sep):
                    return True
    
    return False


def _is_camel_case_identifier(text: str) -> bool:
    """Check if text is a camelCase or PascalCase word."""
    if not text or not text.strip():
        return False
    
    text_stripped = text.strip()
    # CRITICAL: Early return for length and space checks before expensive non-ASCII check
    if len(text_stripped) > 30 or ' ' in text_stripped:
        return False
    
    # CRITICAL: Optimize non-ASCII check - only check if text might contain non-ASCII
    has_non_ascii = not text_stripped.isascii()
    
    if has_non_ascii:
        return False
    
    camel_case_pattern = r'^[A-Z][a-z]+([A-Z][a-z]*)*[A-Za-z0-9]*$'
    if re.match(camel_case_pattern, text_stripped):
        if any(c.islower() for c in text_stripped) and any(c.isupper() for c in text_stripped):
            uppercase_count = sum(1 for c in text_stripped if c.isupper())
            # CRITICAL: PascalCase/camelCase identifiers should have at least 2 uppercase letters
            # Single uppercase letter at start (like "Rimas") is usually a normal word, not an identifier
            if uppercase_count >= 2:
                return True
            # Only accept single uppercase if it's very short (<=3 chars) and contains digits
            # This catches things like "A1", "B2" but not normal words like "Rimas"
            if uppercase_count == 1 and len(text_stripped) <= 3 and any(c.isdigit() for c in text_stripped):
                return True
    
    return False


def _is_uppercase_identifier(text: str) -> bool:
    """
    Check if text is an uppercase identifier.
    Only all-consonant letter sequences (e.g. HTTP, XYZ, ABC) are treated as identifier.
    Normal uppercase words that contain vowels (e.g. HELLO, WORLD) are NOT identifiers.
    """
    if not text or not text.strip():
        return False

    text_stripped = text.strip()
    has_non_ascii = not text_stripped.isascii()
    if has_non_ascii:
        return False

    if not text_stripped.isupper() or not any(c.isalpha() for c in text_stripped):
        return False

    # Uppercase with digits or separators (e.g. ABC123, HTTP/1.1): identifier only if letter part is all consonants
    if any(c.isdigit() for c in text_stripped) or any(
        not c.isalnum() and not c.isspace() for c in text_stripped
    ):
        letter_part = "".join(c for c in text_stripped if c.isalpha())
        if not _is_all_consonants(letter_part):
            return False
        if len(text_stripped) <= 30:
            return True
        if re.match(r"^[A-Z0-9]+([\-_\.\/][A-Z0-9]+)+$", text_stripped):
            return True
        return False

    # Pure uppercase letters (no digits, no special): identifier only when all consonants
    if text_stripped.isalpha():
        return _is_all_consonants(text_stripped)

    return False


def _is_punctuation_only(text: str) -> bool:
    """
    Check if text contains only punctuation or special characters (no alphanumeric).
    
    CRITICAL: Exclude translatable punctuation marks (period, comma, semicolon, colon, 
    exclamation, question mark, and Chinese equivalents) as these need translation 
    between Chinese and English and should not be marked as Identifier.
    """
    if not text or not text.strip():
        return False
    
    text_stripped = text.strip()
    
    # If text contains only translatable punctuation, it should NOT be marked as Identifier
    # These punctuation marks differ between Chinese and English and need translation:
    # Chinese: 、（顿号），（逗号）。（句号）：（冒号）；（分号）！（感叹号）？（问号）
    # English: ,（comma）.（period）:（colon）;（semicolon）!（exclamation）?（question）
    translatable_punctuation = {
        # Chinese punctuation
        '、', '，', '。', '：', '；', '！', '？',
        # English punctuation
        ',', '.', ':', ';', '!', '?',
    }
    
    # If text contains only translatable punctuation, return False (not an identifier)
    if all(c in translatable_punctuation for c in text_stripped):
        return False
    
    # Otherwise, check if text contains only non-alphanumeric characters
    return not any(c.isalnum() for c in text_stripped)


def _is_digits_and_special_chars_only(text: str) -> bool:
    """Check if text contains only digits and special characters (no letters)."""
    if not text or not text.strip():
        return False
    
    text_stripped = text.strip()
    text_no_digits = ''.join(c for c in text_stripped if not c.isdigit())
    
    if text_no_digits and not any(c.isalpha() for c in text_no_digits):
        if any(c.isdigit() for c in text_stripped):
            return True
    
    return False


def is_identifier_pattern(text: str, exclude_language_match: bool = True) -> bool:
    """
    Check if text matches identifier patterns (URL, email, serial number, pure numbers, etc.).
    
    Args:
        text: Text to check
        exclude_language_match: If True, exclude language match detection (default: True)
    
    Returns:
        True if text matches identifier patterns, False otherwise
    """
    if not text or not text.strip():
        return False
    
    # Normalize common leading/trailing wrappers and sentence punctuation so that
    # "OpenAI." / "(OpenAI)" / "OpenAI," are treated the same as "OpenAI".
    text_stripped = text.strip()
    text_stripped = text_stripped.lstrip('<([{“"\'')
    text_stripped = text_stripped.rstrip('>)]}”"\',;:，。；:!?？！')
    
    if _is_pure_number(text_stripped):
        return True
    
    if _is_url(text_stripped):
        return True
    
    if _is_email(text_stripped):
        return True
    
    if _is_serial_number(text_stripped):
        return True
    
    if _is_punctuation_only(text_stripped):
        return True
    
    if _is_digits_and_special_chars_only(text_stripped):
        return True
    
    if _is_camel_case_identifier(text_stripped):
        return True
    
    if _is_uppercase_identifier(text_stripped):
        return True
    
    return False
