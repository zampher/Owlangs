# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

"""Tests for identifier pattern detection."""

from __future__ import annotations

from exclusion.detection.identifier_detector import is_identifier_pattern


def test_single_letter_vowels_and_consonants_are_identifiers():
    for letter in ("A", "B", "C", "E", "I", "a", "e"):
        assert is_identifier_pattern(letter), f"expected identifier: {letter}"


def test_multi_letter_vowel_words_are_not_identifiers():
    assert not is_identifier_pattern("HELLO")
    assert not is_identifier_pattern("WORLD")


def test_all_consonant_acronyms_remain_identifiers():
    assert is_identifier_pattern("HTTP")
    assert is_identifier_pattern("XYZ")
    assert is_identifier_pattern("BCG")
