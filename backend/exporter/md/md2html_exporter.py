# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0
import html as html_module
import logging
import re  # <--- Step 1: Import re module
from dataclasses import dataclass
from typing import Any, Dict, List, Optional
import jinja2
import markdown
from logger import unified_logger as logger
from logger.logger import LogModule
from exporter.md.base import MDExporter, MDExporterConfig
from ir.document import Document
from ir.markdown_document import MarkdownDocument
from utils.resource_utils import resource_path


def _preserve_line_breaks_skip_tables(html_content: str) -> str:
    """
    Convert literal newlines to <br /> for line-break preservation, but do not touch
    newlines inside <table>...</table> blocks (inserting <br /> there breaks table layout).
    """
    _br_placeholder = "\u200bBR\u200b"
    _table_placeholder_prefix = "\u200bTABLE"
    _table_placeholder_suffix = "\u200b"

    # Extract <table>...</table> blocks (handle nested tables by counting tags)
    tables: list[str] = []
    i = 0
    content_lower = html_content.lower()
    while True:
        start = content_lower.find("<table", i)
        if start == -1:
            break
        depth = 1
        pos = content_lower.find(">", start)
        if pos == -1:
            i = start + 1
            continue
        pos += 1
        while pos <= len(html_content) and depth > 0:
            next_table = content_lower.find("<table", pos)
            next_close = content_lower.find("</table>", pos)
            if next_close == -1:
                break
            if next_table != -1 and next_table < next_close:
                depth += 1
                pos = next_table + 6
            else:
                depth -= 1
                if depth == 0:
                    end = next_close + len("</table>")
                    tables.append(html_content[start:end])
                    placeholder = _table_placeholder_prefix + str(len(tables) - 1) + _table_placeholder_suffix
                    html_content = html_content[:start] + placeholder + html_content[end:]
                    content_lower = html_content.lower()
                    i = start + len(placeholder)
                    break
                pos = next_close + 8
        else:
            i = start + 1

    # Replace newlines with <br /> (avoid doubling existing <br />\n)
    html_content = html_content.replace("<br />\n", _br_placeholder)
    html_content = html_content.replace("\n", "<br />\n")
    html_content = html_content.replace(_br_placeholder, "<br />\n")

    # Restore table blocks
    for idx, table_html in enumerate(tables):
        html_content = html_content.replace(_table_placeholder_prefix + str(idx) + _table_placeholder_suffix, table_html)

    # Remove <br /> between block-level elements so side-by-side image paragraphs don't get extra line breaks
    # e.g. </p><br />\n<p> -> </p>\n<p>
    _block_close_open = re.compile(
        r'(</(?:p|div|h[1-6]|ul|ol|section|header|footer)\s*>)\s*(<br\s*/?>\s*\n?)+\s*(<(?:p|div|h[1-6]|ul|ol|section|header|footer)(?:\s[^>]*)?>)',
        re.IGNORECASE,
    )
    html_content = _block_close_open.sub(r'\1\n\3', html_content)
    # Remove <br /> between two <img> in the same block (e.g. <p><img/><br /><img/></p> from "![](a)\n![](b)")
    _br_between_imgs = re.compile(r'(<img\s[^>]*/>)\s*(<br\s*/?>\s*)+\s*(<img\s)', re.IGNORECASE)
    html_content = _br_between_imgs.sub(r'\1 \3', html_content)
    return html_content


# Separator row: cell content is only spaces, colons, dashes (e.g. ---, :---:, ---:)
_TABLE_SEP_RE = re.compile(r'^[\s:\-]+$')


def _parse_table_cells(row: str) -> list[str]:
    """Split a markdown table row by | and return non-empty stripped cells (skip leading/trailing empty from pipes)."""
    parts = [p.strip() for p in row.split('|')]
    if len(parts) >= 2 and parts[0] == '' and parts[-1] == '':
        return [p for p in parts[1:-1]]
    return [p for p in parts if p]


def _is_separator_row(cells: list[str]) -> bool:
    """True if every cell looks like a table separator (only dashes and optional colons)."""
    if not cells:
        return False
    return all(_TABLE_SEP_RE.match(c) and ('-' in c or ':' in c) for c in cells)


def _preprocess_multiline_tables(md_content: str) -> str:
    """
    Find markdown table blocks where rows may span multiple lines (cell content contains newlines).
    Convert each such block to HTML <table> so the standard markdown table extension does not need
    to parse them (it requires one line per row). Preserves newlines inside cells as <br>.
    """
    lines = md_content.split('\n')
    i = 0
    while i < len(lines):
        line = lines[i]
        if '|' not in line:
            i += 1
            continue
        start = i
        end = start
        while end < len(lines) and lines[end].strip() != '' and '|' in lines[end]:
            end += 1
        if end <= start:
            i += 1
            continue
        block = lines[start:end]

        # Merge into logical rows (a row ends when we see a line ending with |)
        logical_rows: list[str] = []
        pos = 0
        while pos < len(block):
            row_lines = [block[pos]]
            pos += 1
            while pos < len(block) and not row_lines[-1].rstrip().endswith('|'):
                row_lines.append(block[pos])
                pos += 1
            logical_rows.append('\n'.join(row_lines))

        if len(logical_rows) < 2:
            i = end
            continue

        # Parse cells for each row
        parsed = [_parse_table_cells(r) for r in logical_rows]
        if not all(parsed):
            i = end
            continue
        # Normalize column count (use max and pad)
        ncols = max(len(cells) for cells in parsed)
        for cells in parsed:
            while len(cells) < ncols:
                cells.append('')

        # Check if second row is separator
        has_sep = len(parsed) >= 2 and _is_separator_row(parsed[1])
        if has_sep:
            header_cells = parsed[0]
            body_rows = parsed[2:]
        else:
            header_cells = None
            body_rows = parsed

        def cell_html(text: str) -> str:
            escaped = html_module.escape(text)
            return escaped.replace('\n', '<br>\n')

        frags: list[str] = ['<table>\n']
        if header_cells is not None:
            frags.append('<thead>\n<tr>\n')
            for c in header_cells:
                frags.append(f'<th>{cell_html(c)}</th>\n')
            frags.append('</tr>\n</thead>\n')
        frags.append('<tbody>\n')
        for row in body_rows:
            frags.append('<tr>\n')
            for c in row:
                frags.append(f'<td>{cell_html(c)}</td>\n')
            frags.append('</tr>\n')
        frags.append('</tbody>\n</table>\n')
        table_html = ''.join(frags)

        lines = lines[:start] + [table_html] + lines[end:]
        i = start + 1

    return '\n'.join(lines)


@dataclass
class MD2HTMLExporterConfig(MDExporterConfig):
    cdn: bool = True
    # When True, bare \n inside paragraphs are converted to <br> tags.
    # Enable for PDF-derived content where every line break is intentional.
    preserve_line_breaks: bool = False
    # Optional layout for side-by-side image grouping (same row only). When set, same-row consecutive images are wrapped in one HTML div before MD->HTML so HTML/PDF match DOCX/MD.
    layout_block_bbox: Optional[Dict[int, Any]] = None
    image_block_indices: Optional[List[int]] = None
    layout_document: Optional[Any] = None


class MD2HTMLExporter(MDExporter):
    def __init__(self, config: MD2HTMLExporterConfig = None):
        config = config or MD2HTMLExporterConfig()
        super().__init__(config=config)
        self.cdn = config.cdn
        self.preserve_line_breaks = config.preserve_line_breaks
        self.logger = logger

    def export(self, document: MarkdownDocument) -> Document:
        cdn = self.cdn
        if self.logger:
            self.logger.debug(LogModule.EXPORT, f"[MD2HTML] Exporting with cdn={cdn}")
        # language=html
        # When cdn=False, try to inline pico.css, fallback to CDN if not found
        cdn_pico = r'<link rel="stylesheet" href="https://s4.zstatic.net/ajax/libs/picocss/2.1.1/pico.min.css" integrity="sha512-+4kjFgVD0n6H3xt19Ox84B56MoS7srFn60tgdWFuO4hemtjhySKyW4LnftYZn46k3THUEiTTsbVjrHai+0MOFw==" crossorigin="anonymous" referrerpolicy="no-referrer" />'
        if not cdn:
            try:
                pico_css_path = resource_path("static/pico.css")
                if pico_css_path.exists():
                    pico_css_content = pico_css_path.read_text(encoding="utf-8")
                    pico = f'<style>{pico_css_content}</style>'
                else:
                    # Fallback to CDN if local file not found
                    self.logger.warning(LogModule.EXPORT, "Pico CSS not found locally, using CDN fallback")
                    pico = cdn_pico
            except Exception as e:
                self.logger.warning(LogModule.EXPORT, f"Failed to load Pico CSS locally: {e}, using CDN fallback")
                pico = cdn_pico
        else:
            pico = cdn_pico
        html_template = resource_path("template/markdown.html").read_text(encoding="utf-8")
        # When cdn=False, try to inline resources for blob URL compatibility
        # If local files not found, fallback to CDN (CSP now allows s4.zstatic.net)
        # When cdn=True, use CDN links
        cdn_katex_css = r"""<link rel="stylesheet" href="https://s4.zstatic.net/ajax/libs/KaTeX/0.16.9/katex.min.css" integrity="sha512-fHwaWebuwA7NSF5Qg/af4UeDx9XqUpYpOGgubo3yWu+b2IQR4UeQwbb42Ti7gVAjNtVoI/I9TEoYeu9omwcC6g==" crossorigin="anonymous" referrerpolicy="no-referrer" />"""
        cdn_katex_js = r"""<script src="https://s4.zstatic.net/ajax/libs/KaTeX/0.16.9/katex.min.js" integrity="sha512-LQNxIMR5rXv7o+b1l8+N1EZMfhG7iFZ9HhnbJkTp4zjNr5Wvst75AqUeFDxeRUa7l5vEDyUiAip//r+EFLLCyA==" crossorigin="anonymous" referrerpolicy="no-referrer"></script>"""
        
        if not cdn:
            # Try to inline KaTeX CSS and JS for blob URL compatibility
            try:
                katex_css_path = resource_path("static/katex/katex.css")
                if katex_css_path.exists():
                    katex_css_content = katex_css_path.read_text(encoding="utf-8")
                    katex_css = f'<style>{katex_css_content}</style>'
                    if self.logger:
                        self.logger.debug(LogModule.EXPORT, f"[MD2HTML] Inlined KaTeX CSS (cdn=False), size: {len(katex_css_content)} bytes")
                else:
                    # Fallback to CDN if local file not found
                    if self.logger:
                        self.logger.warning(LogModule.EXPORT, f"[MD2HTML] KaTeX CSS not found locally at {katex_css_path}, using CDN fallback")
                    katex_css = cdn_katex_css
            except Exception as e:
                if self.logger:
                    self.logger.warning(LogModule.EXPORT, f"[MD2HTML] Failed to load KaTeX CSS locally: {e}, using CDN fallback")
                katex_css = cdn_katex_css
            
            try:
                katex_js_path = resource_path("static/katex/katex.js")
                if katex_js_path.exists():
                    katex_js_content = katex_js_path.read_text(encoding="utf-8")
                    katex_js = f'<script>{katex_js_content}</script>'
                    if self.logger:
                        self.logger.debug(LogModule.EXPORT, f"[MD2HTML] Inlined KaTeX JS (cdn=False), size: {len(katex_js_content)} bytes")
                else:
                    # Fallback to CDN if local file not found
                    if self.logger:
                        self.logger.warning(LogModule.EXPORT, f"[MD2HTML] KaTeX JS not found locally at {katex_js_path}, using CDN fallback")
                    katex_js = cdn_katex_js
            except Exception as e:
                if self.logger:
                    self.logger.warning(LogModule.EXPORT, f"[MD2HTML] Failed to load KaTeX JS locally: {e}, using CDN fallback")
                katex_js = cdn_katex_js
        else:
            katex_css = cdn_katex_css
            katex_js = cdn_katex_js
        # When cdn=False, try to inline auto-render script, fallback to CDN if not found
        cdn_auto_render = r"""<script src="https://s4.zstatic.net/ajax/libs/KaTeX/0.16.9/contrib/auto-render.min.js" integrity="sha512-iWiuBS5nt6r60fCz26Nd0Zqe0nbk1ZTIQbl3Kv7kYsX+yKMUFHzjaH2+AnM6vp2Xs+gNmaBAVWJjSmuPw76Efg==" crossorigin="anonymous" referrerpolicy="no-referrer"></script>"""
        if not cdn:
            try:
                auto_render_path = resource_path("static/autoRender.js")
                if auto_render_path.exists():
                    auto_render_content = auto_render_path.read_text(encoding="utf-8")
                    auto_render = f'<script>{auto_render_content}</script>'
                else:
                    # Fallback to CDN if local file not found
                    self.logger.warning(LogModule.EXPORT, "Auto-render JS not found locally, using CDN fallback")
                    auto_render = cdn_auto_render
            except Exception as e:
                self.logger.warning(LogModule.EXPORT, f"Failed to load auto-render JS locally: {e}, using CDN fallback")
                auto_render = cdn_auto_render
        else:
            auto_render = cdn_auto_render

        # Arithmatex outputs \[...\] and \(...\); also support raw $$ and $ so LaTeX from
        # layout rebuild (e.g. PDF workflow) renders when markdown has $$\n...\n$$.
        # language=javascript
        render_math_in_element = r"""
        <script>
            document.addEventListener("DOMContentLoaded", function () {
                renderMathInElement(document.body, {
                    delimiters: [
                        {left: '$$', right: '$$', display: true},
                        {left: '\\[', right: '\\]', display: true},
                        {left: '$', right: '$', display: false},
                        {left: '\\(', right: '\\)', display: false}
                    ],
                    throwOnError: false,
                    errorColor: '#F5CF27',
                    macros: {
                        "\\f": "#1f(#2)"
                    },
                    trust: true,
                    strict: false
                })
            });
        </script>"""

        mermaid_file = resource_path("static/mermaid.js")
        if mermaid_file.exists():
            mermaid = f'<script>{mermaid_file.read_text(encoding="utf-8")}</script>'
        else:
            mermaid = '<!-- Mermaid script missing -->'
            self.logger.warning(LogModule.EXPORT, "static/mermaid.js not found; skipping Mermaid diagrams")

        # Extension configuration remains unchanged, we still use arithmatex
        extensions = [
            'markdown.extensions.tables',
            'pymdownx.arithmatex',
            'pymdownx.superfences'
        ]
        # For PDF-derived content, preserve bare \n as <br> so that
        # intra-segment line breaks survive the markdown→HTML conversion.
        if self.preserve_line_breaks:
            extensions.append('markdown.extensions.nl2br')
            if self.logger:
                self.logger.debug(LogModule.EXPORT, "[MD2HTML] nl2br extension enabled (preserve_line_breaks=True)")

        extension_configs = {
            'pymdownx.arithmatex': {
                'generic': True,
                'block_tag': 'div',
                'inline_tag': 'span',
                'block_syntax': ['dollar', 'square'],
                'inline_syntax': ['dollar', 'round'],
                'tex_inline_wrap': ['\\(', '\\)'],
                'tex_block_wrap': ['\\[', '\\]'],
                'smart_dollar': True
            },
            'pymdownx.superfences': {
                'custom_fences': [
                    {
                        'name': 'mermaid',
                        'class': 'mermaid',
                        'format': lambda source, language, css_class, options, md,
                                         **kwargs: f'<pre class="{css_class}">{source}</pre>'
                    }
                ]
            }
        }

        # Decode content with robust error handling
        if isinstance(document.content, str):
            content = document.content
        elif isinstance(document.content, bytes):
            try:
                # Try UTF-8 first (standard)
                content = document.content.decode('utf-8')
            except UnicodeDecodeError:
                # If UTF-8 fails, try common encodings or use error replacement
                # Common encodings: utf-8, gbk, gb2312, latin-1, cp1252
                encodings_to_try = ['utf-8', 'gbk', 'gb2312', 'latin-1', 'cp1252']
                content = None
                for encoding in encodings_to_try:
                    try:
                        content = document.content.decode(encoding)
                        break
                    except (UnicodeDecodeError, LookupError):
                        continue
                # If all encodings fail, use UTF-8 with error replacement
                if content is None:
                    content = document.content.decode('utf-8', errors='replace')
        else:
            raise ValueError(f"Unexpected content type: {type(document.content)}")

        # Group same-row consecutive images into one HTML div so HTML/PDF show side-by-side like DOCX/MD (generic handling)
        if getattr(self.config, "image_block_indices", None) and (
            getattr(self.config, "layout_block_bbox", None) or getattr(self.config, "layout_document", None)
        ):
            from utils.format_convert_utils import group_consecutive_images_for_markdown
            content = group_consecutive_images_for_markdown(
                content,
                image_block_indices=self.config.image_block_indices,
                layout_block_bbox=getattr(self.config, "layout_block_bbox", None),
                layout_document=getattr(self.config, "layout_document", None),
            )

        # Convert markdown tables with multi-line cells to HTML so they render correctly
        # (Python-Markdown tables extension requires one logical row per line).
        content = _preprocess_multiline_tables(content)

        html_content = markdown.markdown(
            content,
            extensions=extensions,
            extension_configs=extension_configs
        )
        
        # Safety net: convert any remaining markdown image syntax that the parser
        # failed to process (e.g. images trapped inside unclosed HTML blocks,
        # indented images treated as code blocks, etc.).
        # This replaces literal  ![alt](url)  text with  <img src="url" alt="alt">
        # so images are always rendered even if the markdown parser missed them.
        import re
        _MD_IMAGE_LEFTOVER = re.compile(
            r'!\[([^\]]*)\]\((data:image/[^)]+)\)'
        )
        leftover_count = len(_MD_IMAGE_LEFTOVER.findall(html_content))
        if leftover_count > 0:
            if self.logger:
                self.logger.warning(
                    LogModule.EXPORT,
                    f"[MD2HTML] Found {leftover_count} unconverted markdown image(s) "
                    f"with data-URI src in HTML output — converting to <img> tags "
                    f"(likely caused by unclosed HTML block in markdown input)",
                )
            def _md_img_to_html(m: re.Match) -> str:
                alt = m.group(1) or "Image"
                src = m.group(2)
                return f'<img src="{src}" alt="{alt}">'
            html_content = _MD_IMAGE_LEFTOVER.sub(_md_img_to_html, html_content)
        
        # Post-process HTML to ensure images have proper styling to prevent stretching
        # Preserve display: inline-block for side-by-side images (from group_consecutive_images_for_markdown) so HTML/PDF match DOCX/MD
        def add_image_styles(match):
            img_tag = match.group(0)
            alt_match = re.search(r'alt=["\']([^"\']*)["\']', img_tag)
            alt_text = alt_match.group(1) if alt_match else ""
            # Keep inline-block for side-by-side div so we do not force a line break
            has_inline_block = "inline-block" in img_tag
            is_formula_or_table = "equation" in alt_text.lower() or "table" in alt_text.lower()
            max_width = "70%" if is_formula_or_table else "90%"
            display_val = "inline-block" if has_inline_block else "block"
            if 'style=' in img_tag:
                img_tag = re.sub(
                    r'style=["\']([^"\']*)["\']',
                    lambda m: f'style="{m.group(1)}; max-width: {max_width}; height: auto; object-fit: contain; display: {display_val}; margin: 1em auto;"',
                    img_tag
                )
            else:
                style_attr = f' style="max-width: {max_width}; height: auto; object-fit: contain; display: {display_val}; margin: 1em auto;"'
                img_tag = img_tag.rstrip('>') + style_attr + '>'
            return img_tag
        
        # Process all img tags in the HTML content
        html_content = re.sub(r'<img[^>]*>', add_image_styles, html_content)

        # Remove <br /> and newlines inside .arithmatex blocks so KaTeX sees clean \[...\] or \(...\)
        # (preserve_line_breaks / nl2br can insert <br /> inside math, which breaks KaTeX rendering)
        _ARITHMATEX_DIV = re.compile(
            r'<div\s+class="arithmatex">(.*?)</div>',
            re.DOTALL | re.IGNORECASE
        )
        def _clean_arithmatex(m: re.Match) -> str:
            inner = m.group(1)
            inner = inner.replace("<br />", " ").replace("<br>", " ").replace("\n", " ")
            inner = re.sub(r"\s+", " ", inner).strip()
            return f'<div class="arithmatex">{inner}</div>'
        html_content = _ARITHMATEX_DIV.sub(_clean_arithmatex, html_content)

        # When preserving line breaks (PDF), convert any remaining literal newlines to <br />
        # so that content that reached the parser without "  \n" (e.g. due to empty separators
        # in rebuild) still shows line breaks in the browser.
        # Do NOT replace newlines inside <table>...</table> or inserting <br /> breaks table layout.
        if self.preserve_line_breaks and "\n" in html_content:
            html_content = _preserve_line_breaks_skip_tables(html_content)

        render = jinja2.Template(html_template).render(
            title=document.stem,
            pico=pico,
            katexCss=katex_css,
            katexJs=katex_js,
            autoRender=auto_render,
            markdown=html_content,
            renderMathInElement=render_math_in_element,
            mermaid=mermaid,
        )
        return Document.from_bytes(content=render.encode("utf-8"), suffix=".html", stem=document.stem)

if __name__ == '__main__':
    from pathlib import Path

    # d = Document.from_path(r"C:\Users\jxgm\Desktop\mcp_folder\study_notes\internet_auth_mechanism\internet_auth_mechanism.md")
    # d = Document.from_path(r"C:\Users\jxgm\Desktop\matrixcalc_translated.md")
    d = Document.from_path(r"C:\Users\jxgm\Desktop\full_translated.md")
    exporter = MD2HTMLExporter()
    d1 = exporter.export(d)
    path = Path(r"C:\Users\jxgm\Desktop\a.html")
    path.write_bytes(d1.content)