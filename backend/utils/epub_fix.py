# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

"""
EPUB compliance fixes for Apple Books / EPUBCheck.

- Sanitize HTML: remove deprecated elements/attributes, fix image paths, strip mbp:pagebreak.
- Post-process OPF: ensure dc:title, remove toc="ncx", add minimal EPUB 3 nav document.
"""

import io
import re
import zipfile
from typing import Optional

# Use BeautifulSoup for HTML sanitization (already used in mobi_translator)
try:
    from bs4 import BeautifulSoup
except ImportError:
    BeautifulSoup = None  # type: ignore

_OWLANGS_LAYOUT_STYLE_ID = "owlangs-epub-readable-layout"


def _inject_readable_layout_css_into_head(soup) -> None:
    """
    Legacy MOBI/KF8 HTML often ships body/html rules like max-width + centered column.
    When those XHTML files are written into EPUB unchanged, readers show an overly narrow column.

    Append a small override so translated EPUB chapters use the viewer width sensibly.
    """
    if soup is None or soup.find("style", id=_OWLANGS_LAYOUT_STYLE_ID):
        return
    head = soup.find("head")
    if not head:
        return
    style = soup.new_tag("style", attrs={"type": "text/css", "id": _OWLANGS_LAYOUT_STYLE_ID})
    style.string = """
/* Owlangs: relax html/body constraints from legacy MOBI/KF8 CSS */
html, body {
  max-width: 100% !important;
  width: 100% !important;
  box-sizing: border-box !important;
  margin-left: auto !important;
  margin-right: auto !important;
}
"""
    head.append(style)


def sanitize_html_for_epub(html: str) -> str:
    """
    Make HTML from MOBI extraction valid XHTML for EPUB 3 / Apple Books.

    - Fix image paths: "一mages" -> "Images" (encoding corruption).
    - Replace deprecated <font> with <span>; move align/width/height/bgcolor to style where invalid.
    - Remove mbp:pagebreak and other unknown-namespace elements.
    """
    if not html or not html.strip():
        return html
    if BeautifulSoup is None:
        return _sanitize_html_fallback(html)

    soup = BeautifulSoup(html, "html.parser")

    # Fix img src path encoding (e.g. 一mages -> Images)
    for img in soup.find_all("img"):
        src = img.get("src")
        if src and "一" in src:
            img["src"] = src.replace("一mages", "Images").replace("一", "I")
        # EPUB 3: width/height/align are allowed on img; strip if they cause issues or move to style
        # EPUBCheck said height/width/align "not allowed here" on some element - may be on td/div
        pass

    # Replace deprecated <font> with <span>
    for font in soup.find_all("font"):
        span = soup.new_tag("span")
        if font.get("color"):
            span["style"] = (span.get("style") or "") + f"color:{font['color']};"
        if font.get("size"):
            span["style"] = (span.get("style") or "") + f"font-size:{font['size']};"
        span.attrs = {k: v for k, v in font.attrs.items() if k not in ("color", "size")}
        span.extend(list(font.children))
        font.replace_with(span)

    # On elements that don't allow align/width/height/bgcolor/valign, move to style
    for tag in soup.find_all(True):
        style_parts = []
        if tag.get("align"):
            style_parts.append(f"text-align:{tag['align']}")
            del tag["align"]
        if tag.get("valign"):
            style_parts.append(f"vertical-align:{tag['valign']}")
            del tag["valign"]
        if tag.get("width") and tag.name not in ("img", "svg"):
            style_parts.append(f"width:{tag['width']}")
            del tag["width"]
        if tag.get("height") and tag.name not in ("img", "svg"):
            style_parts.append(f"height:{tag['height']}")
            del tag["height"]
        if tag.get("bgcolor"):
            style_parts.append(f"background-color:{tag['bgcolor']}")
            del tag["bgcolor"]
        # "value" allowed only on input, button, option, li, param in HTML5; strip elsewhere for EPUB
        if tag.get("value") and tag.name not in ("input", "button", "option", "li", "param"):
            del tag["value"]
        if style_parts:
            existing = tag.get("style") or ""
            tag["style"] = (existing + ";" if existing else "") + ";".join(style_parts)

    # Remove mbp:pagebreak and any element with unknown prefix (e.g. mbp:pagebreak)
    for tag in list(soup.find_all(True)):
        if tag.name and ":" in tag.name and tag.name.split(":")[0].lower() == "mbp":
            tag.decompose()

    _inject_readable_layout_css_into_head(soup)

    return str(soup)


def _sanitize_html_fallback(html: str) -> str:
    """Fallback without BeautifulSoup: fix image path, valign, remove mbp:pagebreak."""
    html = re.sub(r'src="([^"]*一mages[^"]*)"', lambda m: f'src="{m.group(1).replace("一mages", "Images").replace("一", "I")}"', html)
    html = re.sub(r'\bvalign="([^"]*)"', r'style="vertical-align:\1"', html, flags=re.IGNORECASE)
    html = re.sub(r"<mbp:pagebreak[^>]*/?>", "", html, flags=re.IGNORECASE)
    return html


def fix_epub_for_epubcheck(epub_bytes: bytes) -> bytes:
    """
    Post-process EPUB bytes so it passes EPUBCheck / Apple Books.

    - Ensure dc:title in metadata (add "Untitled" if missing).
    - Remove spine toc="ncx" so we don't reference missing NCX.
    - Add minimal EPUB 3 nav document and reference it in manifest/spine.
    """
    if not epub_bytes or len(epub_bytes) < 100:
        return epub_bytes

    buf = io.BytesIO(epub_bytes)
    try:
        zf = zipfile.ZipFile(buf, "r")
        names = zf.namelist()
        zf.close()
    except Exception:
        return epub_bytes

    # Find OPF path
    opf_path = None
    opf_dir = "EPUB"
    for n in names:
        if n.endswith(".opf"):
            opf_path = n
            opf_dir = n.rsplit("/", 1)[0] if "/" in n else ""
            break
    if not opf_path:
        return epub_bytes

    buf.seek(0)
    zf = zipfile.ZipFile(buf, "r")
    opf_bytes = zf.read(opf_path)
    zf.close()

    opf = opf_bytes.decode("utf-8", errors="replace")

    # 1) Ensure dc:title (required by EPUB; EPUBCheck RSC-005)
    if "<dc:title>" not in opf and "<dc:title " not in opf:
        opf = opf.replace("</metadata>", "    <dc:title>Untitled</dc:title>\n  </metadata>", 1)

    # 2) Remove toc="ncx" from spine
    opf = re.sub(r'<spine\s+toc="ncx"\s*', "<spine ", opf, count=1)
    opf = re.sub(r"<spine\s+toc='ncx'\s*", "<spine ", opf, count=1)

    # 3) Add nav document if not present (EPUB 3 requires one item with properties="nav")
    nav_href = None
    nav_file_path = None
    if 'properties="nav"' not in opf:
        nav_id = "nav"
        # Href is relative to OPF location (e.g. EPUB/content.opf -> same dir = nav.xhtml)
        nav_href = "nav.xhtml"
        nav_file_path = f"{opf_dir}/{nav_href}" if opf_dir else nav_href
        # Add manifest item
        opf = opf.replace(
            "</manifest>",
            f'    <item href="{nav_href}" id="{nav_id}" media-type="application/xhtml+xml" properties="nav"/>\n  </manifest>',
            1,
        )
        # Insert itemref for nav at start of spine (after <spine...>)
        opf = re.sub(r"(<spine[^>]*>)\s*", r'\1\n    <itemref idref="nav"/>\n    ', opf, count=1)

    out = io.BytesIO()
    zf_in = zipfile.ZipFile(io.BytesIO(epub_bytes), "r")
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zout:
        # Mimetype first, uncompressed (EPUB spec)
        if "mimetype" in names:
            mt = zipfile.ZipInfo("mimetype", (1980, 1, 1, 0, 0, 0))
            mt.compress_type = zipfile.ZIP_STORED
            zout.writestr(mt, b"application/epub+zip")
        for n in names:
            if n == "mimetype":
                continue
            data = zf_in.read(n)
            if n == opf_path:
                data = opf.encode("utf-8")
            # Sanitize content documents (font/mbp:pagebreak/deprecated attrs, 一mages -> Images)
            if n.endswith(".xhtml") or n.endswith(".html"):
                try:
                    text = data.decode("utf-8", errors="replace")
                    text = sanitize_html_for_epub(text)
                    data = text.encode("utf-8")
                except Exception:
                    pass
            zout.writestr(n, data)
        if nav_href:
            nav_body = _minimal_nav_xhtml()
            zout.writestr(nav_file_path, nav_body.encode("utf-8"))
    zf_in.close()

    return out.getvalue()


def _minimal_nav_xhtml() -> str:
    return """<?xml version="1.0" encoding="utf-8"?>
<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops">
<head><title>Navigation</title></head>
<body>
<nav epub:type="toc"><h2>Contents</h2><ol><li><a href="content.xhtml">Content</a></li></ol></nav>
</body>
</html>
"""
