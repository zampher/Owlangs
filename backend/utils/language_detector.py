# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

"""
Shared language detection module (independent of anonymization).
Provides langdetect-based language detection for translation, exclusion, and other workflows.
"""

import re
from typing import Dict

import langdetect
from langdetect import detect, detect_langs, DetectorFactory


class LanguageDetector:
    """
    Language detection utility using langdetect.
    Used by translation workflow, exclusion detection, and language_detection_utils.
    """

    # Language code normalization mapping (langdetect codes -> normalized codes)
    LANGUAGE_MAPPING: Dict[str, str] = {
        'zh-cn': 'zh',
        'zh-tw': 'zh',
        'zh': 'zh',
        'ca': 'ca',
        'hr': 'hr',
        'da': 'da',
        'nl': 'nl',
        'en': 'en',
        'fi': 'fi',
        'fr': 'fr',
        'de': 'de',
        'el': 'el',
        'it': 'it',
        'ja': 'ja',
        'ko': 'ko',
        'lt': 'lt',
        'mk': 'mk',
        'xx': 'xx',
        'nb': 'nb',
        'no': 'nb',
        'pl': 'pl',
        'pt': 'pt',
        'ro': 'ro',
        'ru': 'ru',
        'sl': 'sl',
        'es': 'es',
        'sv': 'sv',
        'uk': 'uk',
        'ar': 'ar',
        'vi': 'vi',
        'bn': 'bn',
        'cs': 'cs',
        'fil': 'fil',
        'he': 'he',
        'hi': 'hi',
        'km': 'km',
        'ms': 'ms',
        'th': 'th',
        'tr': 'tr',
    }

    def __init__(self) -> None:
        """Initialize language detector with consistent seed for reproducible results."""
        DetectorFactory.seed = 0

    def _has_chinese_characters(self, text: str) -> bool:
        """Check if text contains Chinese characters (CJK Unified Ideographs)."""
        chinese_pattern = re.compile(r'[\u4e00-\u9fff\u3400-\u4dbf\uf900-\ufaff]')
        return bool(chinese_pattern.search(text))

    def _count_chinese_characters(self, text: str) -> int:
        """Count the number of Chinese characters in text."""
        chinese_pattern = re.compile(r'[\u4e00-\u9fff\u3400-\u4dbf\uf900-\ufaff]')
        return len(chinese_pattern.findall(text))

    def detect_language(self, text: str) -> str:
        """
        Detect the language of the input text.

        For mixed-language text (especially Chinese-English), uses a more sophisticated
        approach with detect_langs() when Chinese characters are present.

        Args:
            text: Input text to analyze

        Returns:
            Normalized language code (e.g., 'zh', 'en', 'es')
        """
        if not text or not text.strip():
            return 'en'

        try:
            has_chinese = self._has_chinese_characters(text)
            chinese_char_count = self._count_chinese_characters(text)
            total_chars = len(text)
            chinese_char_ratio = chinese_char_count / total_chars if total_chars > 0 else 0

            if has_chinese:
                try:
                    lang_probs = detect_langs(text)
                    zh_prob = 0.0
                    for lang_prob in lang_probs:
                        if lang_prob.lang in ('zh', 'zh-cn', 'zh-tw'):
                            zh_prob = lang_prob.prob
                            break

                    if zh_prob > 0.1 or chinese_char_ratio > 0.05:
                        top_lang = lang_probs[0].lang
                        return self.LANGUAGE_MAPPING.get(top_lang, 'en')
                except Exception:
                    pass

            detected_lang = detect(text)
            return self.LANGUAGE_MAPPING.get(detected_lang, 'en')

        except Exception:
            return 'en'
