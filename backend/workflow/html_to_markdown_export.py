# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

"""Shared HTML → Markdown conversion for workflows that expose export_to_html()."""

from __future__ import annotations

import re


def html_content_to_markdown(html_content: str) -> str:
    """Convert translated HTML (full document or fragment) to Markdown."""
    from bs4 import BeautifulSoup

    from workflow.html_table_to_markdown import (
        extract_tables_and_insert_placeholders,
        restore_table_placeholders,
    )

    soup = BeautifulSoup(html_content, "html.parser")

    for tag in soup(["style", "script", "meta", "link"]):
        tag.decompose()

    for title in soup.find_all("title"):
        if title.string and ("Untitled" in title.string or not title.string.strip()):
            title.decompose()

    table_fragments = extract_tables_and_insert_placeholders(soup)

    try:
        import html2text

        cleaned_html = str(soup)
        h = html2text.HTML2Text()
        h.ignore_links = False
        h.ignore_images = False
        h.body_width = 0
        h.unicode_snob = True
        h.escape_snob = True
        h.single_line_break = False
        h.mark_code = False
        markdown = h.handle(cleaned_html)
    except ImportError:
        markdown = _soup_to_markdown(soup)

    markdown = restore_table_placeholders(markdown, table_fragments)

    return _clean_markdown(markdown)


def _soup_to_markdown(soup) -> str:
    from workflow.html_table_to_markdown import html_table_to_markdown_fragment

    lines: list[str] = []

    def process_element(elem, indent: int = 0) -> None:
        if elem.name is None:
            text = str(elem.string) if elem.string else ""
            if text.strip():
                lines.append(text.strip())
        elif elem.name in ("h1", "h2", "h3", "h4", "h5", "h6"):
            level = int(elem.name[1])
            text = elem.get_text(strip=True)
            if text:
                lines.append("#" * level + " " + text)
                lines.append("")
        elif elem.name == "p":
            text = elem.get_text(separator=" ", strip=True)
            if text:
                lines.append(text)
                lines.append("")
        elif elem.name == "table":
            frag = html_table_to_markdown_fragment(elem)
            if frag.strip():
                lines.append(frag.strip())
                lines.append("")
        elif elem.name in ("div", "section", "article"):
            has_content = False
            for child in elem.children:
                if hasattr(child, "name") and child.name:
                    process_element(child, indent)
                    has_content = True
                elif isinstance(child, str) and child.strip():
                    lines.append(child.strip())
                    has_content = True
            if has_content:
                lines.append("")
        elif elem.name == "br":
            lines.append("")
        elif elem.name == "img":
            alt = elem.get("alt", "")
            src = elem.get("src", "")
            if src:
                lines.append(f"![{alt}]({src})")
        elif elem.name == "a":
            text = elem.get_text(strip=True)
            href = elem.get("href", "")
            if text and href:
                lines.append(f"[{text}]({href})")
            elif text:
                lines.append(text)
        elif elem.name in ("strong", "b"):
            text = elem.get_text(strip=True)
            if text:
                lines.append(f"**{text}**")
        elif elem.name in ("em", "i"):
            text = elem.get_text(strip=True)
            if text:
                lines.append(f"*{text}*")
        elif elem.name in ("ul", "ol"):
            items = elem.find_all("li", recursive=False)
            for i, item in enumerate(items):
                text = item.get_text(separator=" ", strip=True)
                if text:
                    prefix = "- " if elem.name == "ul" else f"{i + 1}. "
                    lines.append(prefix + text)
            lines.append("")
        elif elem.name == "li":
            text = elem.get_text(separator=" ", strip=True)
            if text:
                lines.append(text)
        else:
            text = elem.get_text(separator=" ", strip=True)
            if text:
                lines.append(text)

    body = soup.find("body") or soup
    for child in body.children:
        if hasattr(child, "name"):
            process_element(child)
        elif isinstance(child, str) and child.strip():
            lines.append(child.strip())

    return "\n".join(lines)


def _clean_markdown(markdown: str) -> str:
    lines = markdown.split("\n")
    cleaned_lines: list[str] = []
    skip_blank = False
    in_css_block = False

    for line in lines:
        stripped = line.strip()

        if stripped.startswith("body {") or stripped.startswith("h1 {") or stripped.startswith(
            ".epub-content"
        ):
            in_css_block = True
            continue
        if in_css_block:
            if stripped.endswith("}") or (
                stripped == ""
                and len(cleaned_lines) > 0
                and cleaned_lines[-1].strip().endswith("}")
            ):
                in_css_block = False
            continue

        if stripped == "Untitled" or (stripped.startswith("Untitled") and len(stripped) < 20):
            continue

        if re.match(r"^\s*[a-z-]+:\s*[^;]+;\s*$", stripped):
            continue

        if stripped == "":
            if not skip_blank:
                cleaned_lines.append("")
                skip_blank = True
        else:
            cleaned_lines.append(line.rstrip())
            skip_blank = False

    while cleaned_lines and cleaned_lines[0].strip() == "":
        cleaned_lines.pop(0)
    while cleaned_lines and cleaned_lines[-1].strip() == "":
        cleaned_lines.pop()

    return "\n".join(cleaned_lines)
