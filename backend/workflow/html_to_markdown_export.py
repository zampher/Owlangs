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

    # Preprocess lazy-loaded images: copy data-src to src so html2text
    # (and _soup_to_markdown) can see the actual image URLs.
    for img in soup.find_all("img"):
        src = img.get("src", "").strip()
        data_src = img.get("data-src", "").strip()
        if not src and data_src:
            img["src"] = data_src

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


def _extract_inline_md(elem) -> str:
    """Recursively extract inline Markdown from an element, preserving <img> tags."""
    from bs4 import NavigableString, Tag

    parts: list[str] = []
    for child in elem.children:
        if isinstance(child, NavigableString):
            parts.append(str(child))
        elif isinstance(child, Tag):
            if child.name == "img":
                alt = child.get("alt", "")
                # Prefer data-src (lazy-load) over src for WeChat/modern HTML
                src = child.get("data-src") or child.get("src", "")
                if src:
                    parts.append(f"![{alt}]({src})")
            elif child.name == "a":
                href = child.get("href", "")
                inner = _extract_inline_md(child).strip()
                if href and inner:
                    parts.append(f"[{inner}]({href})")
                elif inner:
                    parts.append(inner)
            elif child.name in ("strong", "b"):
                inner = _extract_inline_md(child).strip()
                if inner:
                    parts.append(f"**{inner}**")
            elif child.name in ("em", "i"):
                inner = _extract_inline_md(child).strip()
                if inner:
                    parts.append(f"*{inner}*")
            elif child.name == "br":
                parts.append(" ")
            elif child.name in ("span", "code"):
                parts.append(_extract_inline_md(child))
            else:
                # Recursively process unknown tags to preserve inline images
                # (e.g., <figure>, <main>, <header>, <picture>)
                parts.append(_extract_inline_md(child))
    return "".join(parts)


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
            text = _extract_inline_md(elem).strip()
            if text:
                lines.append("#" * level + " " + text)
                lines.append("")
        elif elem.name == "p":
            text = _extract_inline_md(elem).strip()
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
            # Prefer data-src (lazy-load) over src for WeChat/modern HTML
            src = elem.get("data-src") or elem.get("src", "")
            if src:
                lines.append(f"![{alt}]({src})")
        elif elem.name == "a":
            text = _extract_inline_md(elem).strip()
            href = elem.get("href", "")
            if text and href:
                lines.append(f"[{text}]({href})")
            elif text:
                lines.append(text)
        elif elem.name in ("strong", "b"):
            text = _extract_inline_md(elem).strip()
            if text:
                lines.append(f"**{text}**")
        elif elem.name in ("em", "i"):
            text = _extract_inline_md(elem).strip()
            if text:
                lines.append(f"*{text}*")
        elif elem.name in ("ul", "ol"):
            items = elem.find_all("li", recursive=False)
            for i, item in enumerate(items):
                text = _extract_inline_md(item).strip()
                if text:
                    prefix = "- " if elem.name == "ul" else f"{i + 1}. "
                    lines.append(prefix + text)
            lines.append("")
        elif elem.name == "li":
            text = _extract_inline_md(elem).strip()
            if text:
                lines.append(text)
        else:
            text = _extract_inline_md(elem).strip()
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
