# SPDX-License-Identifier: MIT
"""One-off diagnostic for MOBI segment replacement misses."""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

from bs4 import BeautifulSoup

from backend.translator.ai_translator.mobi_translator import MobiTranslator
from backend.utils.epub_html_segments import (
    _match_block_elements,
    _parser_blocks,
    extract_paragraph_segments_from_html,
)


async def main() -> None:
    task_dir = Path(r"C:\Users\Zampher\AppData\Local\Temp\owlangs_77eadf1f_5pit8hqw")
    mobi = next(task_dir.glob("*.mobi"))
    print("mobi:", mobi)

    translator = MobiTranslator()
    book = translator._load_book(str(mobi))
    templates = translator._extract_html_templates(book)
    html = next(iter(templates.values()))
    print("html len:", len(html))

    cache_path = task_dir / "debug" / "translation_segments.json"
    cache_segments = [s["source_text"] for s in json.loads(cache_path.read_text(encoding="utf-8"))]
    print("cache segments:", len(cache_segments))

    per_item = extract_paragraph_segments_from_html(html, chunk_size=8000, deep_split=True)
    print("per-item extraction:", len(per_item))

    blocks = [b for b in _parser_blocks(html) if b and b.strip()]
    print("parser blocks (non-empty):", len(blocks))

    soup = BeautifulSoup(html, "html.parser")
    matched = _match_block_elements(html, soup)
    print("matched DOM pairs:", sum(1 for m in matched if m is not None))

    print("\n--- last 10 cache segments ---")
    for i, text in enumerate(cache_segments[-10:], start=len(cache_segments) - 10):
        print(i, repr(text[:80]))

    print("\n--- last 10 per-item segments ---")
    for i, text in enumerate(per_item[-10:], start=len(per_item) - 10):
        print(i, repr(text[:80]))

    if len(per_item) > len(cache_segments):
        print("\nextra per-item beyond cache count:")
        for t in per_item[len(cache_segments) :]:
            print(" ", repr(t[:120]))

    print("\n--- last 10 parser blocks ---")
    for i, block in enumerate(blocks[-10:], start=len(blocks) - 10):
        print(i, repr(block[:80]))

    for needle in ["Rima LXXVI", "Sobre", "LXXV", "LXXIV", "Rima LXXV"]:
        idx = html.rfind(needle)
        if idx >= 0:
            print(f"rfind {needle!r}:", idx, "context:", repr(html[max(0, idx - 40) : idx + 60]))
        else:
            print(f"rfind {needle!r}: NOT FOUND")


if __name__ == "__main__":
    asyncio.run(main())
