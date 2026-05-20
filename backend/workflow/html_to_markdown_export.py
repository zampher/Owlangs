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


def rebuild_html_with_translations(
    html_content: str,
    original_texts: list[str],
    translated_texts: list[str],
) -> str:
    """
    Rebuild translated HTML by replacing text nodes in safe tags.
    Mirrors HtmlTranslator._after_translate_with_extractor without needing
    a translator instance, so download-service rebuilds can reuse it.
    """
    from bs4 import BeautifulSoup

    if len(original_texts) != len(translated_texts):
        raise ValueError(
            f"original_texts ({len(original_texts)}) and translated_texts "
            f"({len(translated_texts)}) length mismatch"
        )

    soup = BeautifulSoup(html_content, "lxml")

    # Same sets as HtmlTranslator
    non_translatable_tags = {
        "script",
        "style",
        "pre",
        "code",
        "kbd",
        "samp",
        "var",
        "noscript",
        "meta",
        "link",
        "head",
    }
    safe_tags = {
        "p",
        "h1",
        "h2",
        "h3",
        "h4",
        "h5",
        "h6",
        "li",
        "blockquote",
        "q",
        "caption",
        "span",
        "a",
        "strong",
        "em",
        "b",
        "i",
        "u",
        "td",
        "th",
        "button",
        "label",
        "legend",
        "option",
        "figcaption",
        "summary",
        "details",
        "div",
    }

    for tag in soup.find_all(non_translatable_tags):
        tag.decompose()

    # Apply translations to soup, handling both single-segment and multi-segment tags.
    # The HtmlExtractor with deep_split=True may split a single tag's text content
    # into multiple segments (e.g. by paragraph or sentence boundaries). When the
    # rebuild matches by tag.string (full tag content), individual segments won't
    # match. We handle this by trying consecutive-segment concatenation as a fallback.
    _apply_html_translations(soup, original_texts, translated_texts, safe_tags)

    # Fix lazy-loaded images
    for img in soup.find_all("img"):
        src = img.get("src", "").strip()
        data_src = img.get("data-src", "").strip()
        if not src and data_src:
            img["src"] = data_src

    # Strip CSS hiding that would require JavaScript to unhide.
    # WeChat and other platforms set visibility:hidden/opacity:0 on content
    # and rely on JS to remove them — scripts are already decomposed.
    _VIS_HIDDEN_RE = re.compile(r'visibility\s*:\s*hidden\s*;?\s*', re.IGNORECASE)
    _OPACITY_ZERO_RE = re.compile(r'opacity\s*:\s*0\s*;?\s*', re.IGNORECASE)
    for elem in soup.find_all(style=True):
        style = elem.get('style', '')
        new_style = _VIS_HIDDEN_RE.sub('', style)
        new_style = _OPACITY_ZERO_RE.sub('', new_style)
        if new_style != style:
            new_style = new_style.strip().strip(';').strip()
            if new_style:
                elem['style'] = new_style
            else:
                del elem['style']

    return str(soup)


def _apply_html_translations(
    soup,
    original_texts: list[str],
    translated_texts: list[str],
    safe_tags: set[str],
) -> None:
    """Apply translations to a BeautifulSoup tree using text-node-based matching.

    The HtmlExtractor may combine text from multiple adjacent inline tags into
    one segment (e.g. two <span>s inside a <div>). This approach matches at the
    text-node character level rather than by tag.string, correctly handling:
    1. One tag -> one segment (direct match)
    2. One tag -> multiple segments (deep split)
    3. Multiple tags -> one segment (tag-group combining, the common case)
    """
    from bs4 import Comment as BSComment, NavigableString

    # Phase 1: Collect all text nodes within safe tags
    text_nodes: list = []
    node_texts: list[str] = []
    for text_node in soup.find_all(string=True):
        if isinstance(text_node, BSComment):
            continue
        parent = text_node.parent
        if parent and hasattr(parent, 'name') and parent.name in safe_tags:
            t = str(text_node)
            text_nodes.append(text_node)
            node_texts.append(t)

    # Track consumed segment indices to handle duplicate original texts
    consumed_indices: set[int] = set()

    for seg_idx, (orig, trans) in enumerate(zip(original_texts, translated_texts)):
        if seg_idx in consumed_indices:
            continue
        if not orig or not orig.strip():
            consumed_indices.add(seg_idx)
            continue

        # (Re)build flat text from current node state
        flat_text = "".join(node_texts)

        # Find this segment in the flat text
        pos = flat_text.find(orig)
        if pos == -1:
            continue

        end = pos + len(orig)

        # Build cumulative node positions for this iteration
        node_positions: list[tuple[int, int]] = []
        cum = 0
        for nt in node_texts:
            node_positions.append((cum, cum + len(nt)))
            cum += len(nt)

        # Find which text node(s) this segment spans
        start_ni: int | None = None
        end_ni: int | None = None
        for ni, (n_start, n_end) in enumerate(node_positions):
            if start_ni is None and n_start <= pos < n_end:
                start_ni = ni
            if n_start < end <= n_end:
                end_ni = ni
                break

        if start_ni is None or end_ni is None:
            continue

        consumed_indices.add(seg_idx)

        if start_ni == end_ni:
            # Single node — replace within this node
            node = text_nodes[start_ni]
            n_start, n_end = node_positions[start_ni]
            offset = pos - n_start
            old = node_texts[start_ni]
            new_text = old[:offset] + trans + old[offset + len(orig):]
            new_node = NavigableString(new_text)
            node.replace_with(new_node)
            text_nodes[start_ni] = new_node  # Update reference for subsequent iterations
            node_texts[start_ni] = new_text
        else:
            # Multiple nodes — segment content spans inline tag boundaries.
            # Put the translated text in the first affected node, clear the rest.
            n_start, _ = node_positions[start_ni]
            offset = pos - n_start
            first_head = node_texts[start_ni][:offset]

            _, n_end = node_positions[end_ni]
            end_off = end - node_positions[end_ni][0]
            last_tail = node_texts[end_ni][end_off:]

            combined = first_head + trans + last_tail

            new_first = NavigableString(combined)
            text_nodes[start_ni].replace_with(new_first)
            text_nodes[start_ni] = new_first
            node_texts[start_ni] = combined

            for ni in range(start_ni + 1, end_ni + 1):
                new_empty = NavigableString("")
                text_nodes[ni].replace_with(new_empty)
                text_nodes[ni] = new_empty
                node_texts[ni] = ""
