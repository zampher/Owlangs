"""
Debug script to analyze why layout mapping fails.

This script simulates the mapping process to identify issues.
"""

import json
import re
from pathlib import Path
from typing import List, Dict

# Sample data from the actual files
MARKDOWN_SAMPLE = """![](images/f66a2451f964b380d670840060dea6ff9e1ebd69e3e297959ac1e35a6edc5d1d.jpg)

OPEN ACCESS

![](images/09c3e31a05c1cac665aa3ae3fded9e7b8ee751282c5b116c6794c7cab74468b4.jpg)

Check for updates

# Risks of deep vein thrombosis, pulmonary embolism, and bleeding after Covid-19: nationwide self-controlled cases series and matched cohort study

Ioannis Katsoularis, $^{1}$  Osvaldo Fonseca-Rodriguez, $^{2}$  Paddy Farrington, $^{3}$  Hanna Jerndal, $^{2}$  Erling Häggström Lundevaller, $^{4}$  Malin Sund, $^{5,6}$  Krister Lindmark, $^{1}$  Anne-Marie Fors Connolly $^{2}$

For numbered affiliations see end of the article"""

CONTENT_LIST_SAMPLE = [
    {"type": "image", "img_path": "images/f66a2451f964b380d670840060dea6ff9e1ebd69e3e297959ac1e35a6edc5d1d.jpg", "bbox": [53, 88, 109, 105], "page_idx": 0},
    {"type": "text", "text": "OPEN ACCESS", "bbox": [112, 93, 216, 105], "page_idx": 0},
    {"type": "image", "img_path": "images/09c3e31a05c1cac665aa3ae3fded9e7b8ee751282c5b116c6794c7cab74468b4.jpg", "bbox": [57, 119, 85, 139], "page_idx": 0},
    {"type": "text", "text": "Check for updates", "bbox": [90, 124, 206, 134], "page_idx": 0},
    {"type": "text", "text": "Risks of deep vein thrombosis, pulmonary embolism, and bleeding after Covid-19: nationwide self-controlled cases series and matched cohort study", "text_level": 1, "bbox": [231, 88, 858, 163], "page_idx": 0},
    {"type": "text", "text": "Ioannis Katsoularis, $^{1}$  Osvaldo Fonseca-Rodriguez, $^{2}$  Paddy Farrington, $^{3}$  Hanna Jerndal, $^{2}$  Erling Häggström Lundevaller, $^{4}$  Malin Sund, $^{5,6}$  Krister Lindmark, $^{1}$  Anne-Marie Fors Connolly $^{2}$", "bbox": [231, 171, 905, 206], "page_idx": 0},
    {"type": "text", "text": "For numbered affiliations see end of the article", "bbox": [52, 224, 205, 245], "page_idx": 0},
]


def _normalize_text_for_matching(text: str) -> str:
    """Same as in translation_segments.py"""
    if not text:
        return ""
    
    # Remove markdown image references
    text = re.sub(r'!\[.*?\]\([^)]+\)', '', text)
    
    # Remove markdown headers
    text = re.sub(r'^#+\s*', '', text, flags=re.MULTILINE)
    
    # Remove markdown bold/italic
    text = re.sub(r'\*\*([^*]+)\*\*', r'\1', text)
    text = re.sub(r'\*([^*]+)\*', r'\1', text)
    
    # Remove markdown links
    text = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', text)
    
    # Normalize LaTeX
    text = re.sub(r'\$([^$]+)\$', r'\1', text)
    text = re.sub(r'\\\(([^)]+)\\\)', r'\1', text)
    
    # Normalize whitespace
    text = re.sub(r'\s+', ' ', text)
    
    return text.strip()


def analyze_mapping():
    """Analyze why mapping fails"""
    
    print("=" * 80)
    print("LAYOUT MAPPING DIAGNOSTIC ANALYSIS")
    print("=" * 80)
    
    # 1. Analyze markdown chunks (simulated)
    print("\n1. MARKDOWN CHUNKS (simulated split):")
    print("-" * 80)
    markdown_lines = MARKDOWN_SAMPLE.split('\n')
    for i, line in enumerate(markdown_lines[:10]):
        print(f"  Chunk {i}: {repr(line[:80])}")
        normalized = _normalize_text_for_matching(line)
        print(f"    Normalized: {repr(normalized[:80])}")
        if normalized:
            print(f"    [OK] Has content after normalization")
        else:
            print(f"    [EMPTY] Empty after normalization")
    
    # 2. Analyze layout blocks
    print("\n2. LAYOUT BLOCKS (from content_list.json):")
    print("-" * 80)
    text_blocks = []
    for i, item in enumerate(CONTENT_LIST_SAMPLE):
        if item.get("type") == "text":
            text = item.get("text", "")
            text_blocks.append((i, text))
            normalized = _normalize_text_for_matching(text)
            print(f"  Block {i}: {repr(text[:80])}")
            print(f"    Normalized: {repr(normalized[:80])}")
            if normalized:
                print(f"    [OK] Has content after normalization")
            else:
                print(f"    [EMPTY] Empty after normalization")
    
    # 3. Build full_text (simulated)
    print("\n3. BUILDING FULL_TEXT FOR MATCHING:")
    print("-" * 80)
    normalized_full_text_parts = []
    for i, item in enumerate(CONTENT_LIST_SAMPLE):
        if item.get("type") == "text":
            text = item.get("text", "")
            normalized = _normalize_text_for_matching(text)
            if normalized:
                normalized_full_text_parts.append(normalized)
    
    normalized_full_text = ' '.join(normalized_full_text_parts)
    print(f"  Normalized full_text length: {len(normalized_full_text)} chars")
    print(f"  First 200 chars: {repr(normalized_full_text[:200])}")
    
    # 4. Try to match markdown chunks
    print("\n4. ATTEMPTING TO MATCH MARKDOWN CHUNKS:")
    print("-" * 80)
    matched_count = 0
    for i, line in enumerate(markdown_lines[:10]):
        normalized_chunk = _normalize_text_for_matching(line)
        if not normalized_chunk:
            print(f"  Chunk {i}: SKIPPED (empty after normalization)")
            continue
        
        found_pos = normalized_full_text.find(normalized_chunk)
        if found_pos >= 0:
            print(f"  Chunk {i}: [MATCHED] at position {found_pos}")
            print(f"    Chunk: {repr(normalized_chunk[:60])}")
            matched_count += 1
        else:
            print(f"  Chunk {i}: [NOT FOUND]")
            print(f"    Chunk: {repr(normalized_chunk[:60])}")
            # Try to find partial matches
            words = normalized_chunk.split()
            if words:
                first_word = words[0]
                if first_word in normalized_full_text:
                    print(f"    Note: First word '{first_word}' exists in full_text")
                else:
                    print(f"    Note: First word '{first_word}' NOT in full_text")
    
    print(f"\n  Summary: {matched_count}/{len(markdown_lines[:10])} chunks matched")
    
    # 5. Potential issues
    print("\n5. POTENTIAL ISSUES:")
    print("-" * 80)
    
    # Check if chunks might be too large (spanning multiple blocks)
    print("  a) Chunk size vs block size:")
    for i, line in enumerate(markdown_lines[:5]):
        if line.strip() and not line.startswith('!'):
            normalized = _normalize_text_for_matching(line)
            if normalized:
                print(f"    Chunk {i} length: {len(normalized)} chars")
                # Find matching blocks
                for j, item in enumerate(CONTENT_LIST_SAMPLE):
                    if item.get("type") == "text":
                        block_text = item.get("text", "")
                        normalized_block = _normalize_text_for_matching(block_text)
                        if normalized_block and normalized_block in normalized:
                            print(f"      → Contains block {j} text")
                        elif normalized and normalized_block in normalized:
                            print(f"      → Block {j} text is substring of chunk")
    
    # Check LaTeX differences
    print("\n  b) LaTeX format differences:")
    markdown_latex = "$^{1}$"
    layout_latex = "$^{1}$"  # Same in content_list
    print(f"    Markdown LaTeX: {repr(markdown_latex)}")
    print(f"    Layout LaTeX: {repr(layout_latex)}")
    print(f"    Markdown normalized: {repr(_normalize_text_for_matching(markdown_latex))}")
    print(f"    Layout normalized: {repr(_normalize_text_for_matching(layout_latex))}")
    
    # Check if chunks contain multiple blocks
    print("\n  c) Multi-block chunks:")
    # Simulate a larger chunk that might span multiple blocks
    large_chunk = "\n".join(markdown_lines[3:6])
    normalized_large = _normalize_text_for_matching(large_chunk)
    print(f"    Large chunk (lines 3-6): {len(normalized_large)} chars")
    print(f"    First 100 chars: {repr(normalized_large[:100])}")
    found = normalized_full_text.find(normalized_large)
    if found >= 0:
        print(f"    [FOUND] in full_text at position {found}")
    else:
        print(f"    [NOT FOUND] in full_text")
        # Try to find parts
        parts = normalized_large.split()
        if parts:
            print(f"    Trying to find first 3 words: {' '.join(parts[:3])}")
            partial = ' '.join(parts[:3])
            found_partial = normalized_full_text.find(partial)
            if found_partial >= 0:
                print(f"      [FOUND] at position {found_partial}")
            else:
                print(f"      [NOT FOUND]")
    
    print("\n" + "=" * 80)
    print("ANALYSIS COMPLETE")
    print("=" * 80)


if __name__ == "__main__":
    analyze_mapping()

