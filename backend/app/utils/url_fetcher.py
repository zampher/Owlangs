# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

"""URL fetching utilities for downloading web pages and extracting content."""

import hashlib
from typing import Optional
from urllib.request import urlopen, Request
from urllib.error import URLError, HTTPError

from logger import unified_logger as logger
from logger.logger import LogModule
from backend.app.utils.encoding_utils import decode_with_detection


def _insert_images_at_positions(extracted: str, html_str: str, base_url: str = "") -> str:
    """
    Insert images from raw HTML into extracted content at their approximate
    original positions, instead of appending them all at the end.

    We match each <img> to the nearest preceding text block in the raw HTML,
    then find the same text block in the extracted content and insert the
    image right after it.
    """
    try:
        from bs4 import BeautifulSoup
        from urllib.parse import urljoin
    except ImportError:
        return extracted

    raw_soup = BeautifulSoup(html_str, 'lxml')
    extracted_soup = BeautifulSoup(extracted, 'lxml')

    block_tags = ('p', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'div', 'section', 'article')
    extracted_blocks = [
        tag for tag in extracted_soup.find_all(block_tags)
        if tag.get_text(strip=True)
    ]

    imgs_to_insert = []
    for img in raw_soup.find_all('img'):
        src = img.get('src', '') or img.get('data-src', '')
        if not src or src.startswith(('data:', 'javascript:', 'blob:')):
            continue
        if base_url and not src.startswith(('http://', 'https://')):
            src = urljoin(base_url, src)

        prev_text = ''
        for prev in img.find_all_previous(block_tags):
            text = prev.get_text(strip=True)
            if text:
                prev_text = text
                break

        imgs_to_insert.append({'src': src, 'prev_text': prev_text})

    if not imgs_to_insert:
        return extracted

    inserted = 0
    for img_info in imgs_to_insert:
        prev_text = img_info['prev_text']
        best_idx = -1
        best_score = -1

        for idx, block in enumerate(extracted_blocks):
            block_text = block.get_text(strip=True)
            if not block_text:
                continue
            if prev_text == block_text:
                best_idx = idx
                best_score = float('inf')
                break
            # Partial match using common prefix length
            score = 0
            for a, b in zip(prev_text, block_text):
                if a == b:
                    score += 1
                else:
                    break
            if score > best_score:
                best_score = score
                best_idx = idx

        if best_idx >= 0:
            new_p = extracted_soup.new_tag('p')
            img_tag = extracted_soup.new_tag('img', src=img_info['src'])
            new_p.append(img_tag)
            target = extracted_blocks[best_idx]
            target.insert_after(new_p)
            inserted += 1

    logger.info(
        LogModule.WORKFLOW,
        f"[URL-FETCH] Inserted {inserted}/{len(imgs_to_insert)} image(s) at approximate positions",
    )
    return str(extracted_soup)


def _preprocess_lazy_load_images(html_str: str, base_url: str = "") -> str:
    """
    Convert lazy-loaded images (data-src) to regular <img src> tags.

    WeChat articles and many other sites use data-src for lazy loading.
    Trafilatura only recognizes src, so we preprocess the HTML to ensure
    images appear in their original positions within the extracted content.
    """
    try:
        from bs4 import BeautifulSoup
        from urllib.parse import urljoin
    except ImportError:
        return html_str

    soup = BeautifulSoup(html_str, 'lxml')
    modified = False
    for img in soup.find_all('img'):
        data_src = img.get('data-src', '')
        src = img.get('src', '')
        # Use data-src if it looks like a real image URL and src is missing,
        # empty, or a placeholder / tiny tracking pixel.
        if data_src and (
            not src
            or src.startswith('data:')
            or 'placeholder' in src.lower()
            or '1x1' in src.lower()
            or 'blank' in src.lower()
            or 'spacer' in src.lower()
        ):
            actual_src = data_src.strip()
            if base_url and not actual_src.startswith(('http://', 'https://', 'data:')):
                actual_src = urljoin(base_url, actual_src)
            img['src'] = actual_src
            modified = True
            # Remove data-src so downstream doesn't double-process
            if 'data-src' in img.attrs:
                del img['data-src']
    if modified:
        logger.info(
            LogModule.WORKFLOW,
            "[URL-FETCH] Preprocessed lazy-loaded images (data-src -> src)",
        )
    return str(soup)


def _extract_images_from_html(html_str: str, base_url: str = "") -> list[str]:
    """Extract image URLs from raw HTML, preferring data-src over src (WeChat lazy-load)."""
    try:
        from bs4 import BeautifulSoup
        from urllib.parse import urljoin
    except ImportError:
        return []

    soup = BeautifulSoup(html_str, 'lxml')
    image_urls: list[str] = []
    for img in soup.find_all('img'):
        src = img.get('data-src', '') or img.get('src', '')
        if src and not src.startswith(('data:', 'javascript:', 'blob:')):
            if base_url and not src.startswith(('http://', 'https://')):
                src = urljoin(base_url, src)
            if src and src not in image_urls:
                image_urls.append(src)
    return image_urls


def fetch_url_content(url: str, timeout: int = 30) -> bytes:
    """
    Download raw HTML content from a URL.

    Args:
        url: The URL to fetch.
        timeout: Request timeout in seconds.

    Returns:
        Raw bytes of the response body.

    Raises:
        ValueError: If URL is empty or invalid.
        HTTPError: If server returns an error status.
        URLError: If connection fails.
    """
    if not url or not url.strip():
        raise ValueError("URL is empty")

    url = url.strip()
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept": (
            "text/html,application/xhtml+xml,application/xml;q=0.9,"
            "image/avif,image/webp,image/apng,*/*;q=0.8"
        ),
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Accept-Encoding": "identity",
        "Connection": "keep-alive",
    }

    # WeChat articles require Referer
    if "mp.weixin.qq.com" in url or "weixin" in url:
        headers["Referer"] = "https://mp.weixin.qq.com/"

    req = Request(url, headers=headers)

    try:
        with urlopen(req, timeout=timeout) as resp:
            data = resp.read()
            logger.info(
                LogModule.WORKFLOW,
                f"[URL-FETCH] Fetched {url}: {len(data)} bytes, status={resp.status}",
            )
            return data
    except HTTPError as e:
        logger.error(
            LogModule.WORKFLOW,
            f"[URL-FETCH] HTTP error fetching {url}: {e.code} {e.reason}",
        )
        raise
    except URLError as e:
        logger.error(
            LogModule.WORKFLOW,
            f"[URL-FETCH] URL error fetching {url}: {e.reason}",
        )
        raise


def _simplify_html_element(tag):
    """
    Simplify a BeautifulSoup tag for clean export:
    - Remove class/id attributes (avoid external-CSS dependency)
    - Remove inline styles that hide content
    - Unwrap decorative containers (<section> -> <div>)
    - Keep only safe/semantic tags
    """
    # Tags we want to keep as-is
    keep_tags = {
        'p', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
        'img', 'a', 'br', 'hr',
        'strong', 'em', 'b', 'i', 'u', 'span',
        'blockquote', 'pre', 'code',
        'table', 'thead', 'tbody', 'tr', 'td', 'th',
        'ul', 'ol', 'li',
        'div',
    }

    # Tags to completely remove (but keep children)
    unwrap_tags = {
        'section', 'article', 'main', 'header', 'footer',
        'aside', 'figure', 'figcaption', 'picture', 'source',
    }

    # Tags to remove entirely (including children)
    remove_tags = {
        'script', 'style', 'noscript', 'iframe', 'svg',
        'canvas', 'video', 'audio', 'form', 'input',
        'button', 'select', 'textarea', 'nav',
    }

    # Use reversed(find_all) so we process deepest children first.
    # This avoids iterator invalidation when we decompose/unwrap tags.
    for child in reversed(list(tag.find_all(True))):
        if child is None:
            continue
        if not hasattr(child, 'name') or child.name is None:
            continue
        if not hasattr(child, 'get') or not callable(getattr(child, 'get', None)):
            continue
        if not hasattr(child, 'attrs') or child.attrs is None:
            continue

        name = child.name.lower()

        if name in remove_tags:
            child.decompose()
            continue

        if name in unwrap_tags:
            child.unwrap()
            continue

        if name not in keep_tags:
            # Unknown tag: try to unwrap it
            try:
                child.unwrap()
            except Exception:
                child.decompose()
            continue

        # Clean attributes
        decomposed = False
        attrs_to_remove = []
        for attr in list(child.attrs.keys()):
            attr_lower = attr.lower()
            if attr_lower in ('class', 'id', 'data-src', 'data-url', 'data-type',
                              'data-id', 'role', 'aria-hidden', 'tabindex'):
                attrs_to_remove.append(attr)
            elif attr_lower == 'style':
                style = child.get('style', '')
                style_lower = style.replace(' ', '').lower()
                # Remove elements that are explicitly hidden
                if any(h in style_lower for h in (
                    'display:none',
                    'visibility:hidden',
                    'opacity:0',
                    'font-size:0',
                    'height:0',
                    'width:0',
                    'color:transparent',
                )):
                    child.decompose()
                    decomposed = True
                    break
                # Otherwise remove the style attribute to avoid CSS dependency
                attrs_to_remove.append(attr)
            elif attr_lower == 'src' and name == 'img':
                # Keep img src, but verify it's not a data-URI placeholder
                src = child.get('src', '')
                if src.startswith('data:image/gif;base64'):
                    # This is likely a 1x1 placeholder – try data-src fallback
                    data_src = child.get('data-src', '')
                    if data_src:
                        child['src'] = data_src
                    else:
                        child.decompose()
                        decomposed = True
                        break

        if not decomposed:
            for attr in attrs_to_remove:
                if attr in child.attrs:
                    del child.attrs[attr]


def _extract_by_common_selectors(html_str: str, url: str = "") -> Optional[str]:
    """
    Try to extract main content by well-known site-specific selectors.
    This preserves original image placement better than trafilatura for
    sites with predictable DOM structures (e.g. WeChat, Zhihu, Jianshu).

    Returns the cleaned HTML string if a match is found, else None.
    """
    try:
        from bs4 import BeautifulSoup, Comment
        from urllib.parse import urljoin
    except ImportError:
        return None

    soup = BeautifulSoup(html_str, 'lxml')

    # Site-specific selectors, ordered by priority
    selectors = [
        # WeChat
        '#js_content',
        '#img-content',
        # Zhihu
        '.RichContent-inner',
        '.Post-RichTextContainer',
        # Jianshu
        'article',
        '.show-content-free',
        # Generic
        '[itemprop="articleBody"]',
        '.article-content',
        '.post-content',
        '.entry-content',
        '.content',
    ]

    content_elem = None
    for sel in selectors:
        content_elem = soup.select_one(sel)
        if content_elem:
            logger.info(
                LogModule.WORKFLOW,
                f"[URL-FETCH] Matched content selector: {sel}",
            )
            break

    if not content_elem:
        return None

    # --- Extract title (outside the content container) ---
    title_text = ''
    title_selectors = [
        # WeChat
        '.rich_media_title',
        '#activity_name',
        'h2.rich_media_title',
        # Generic
        'h1',
        '.article-title',
        '.post-title',
        '.entry-title',
        '.title',
    ]
    for tsel in title_selectors:
        title_tag = soup.select_one(tsel)
        if title_tag:
            txt = title_tag.get_text(strip=True)
            if txt:
                title_text = txt
                logger.info(
                    LogModule.WORKFLOW,
                    f"[URL-FETCH] Matched title selector: {tsel}",
                )
                break

    # Preprocess lazy-loaded images within the matched content
    for img in content_elem.find_all('img'):
        data_src = img.get('data-src', '')
        src = img.get('src', '')
        if data_src and (
            not src
            or src.startswith('data:')
            or 'placeholder' in src.lower()
            or '1x1' in src.lower()
            or 'blank' in src.lower()
            or 'spacer' in src.lower()
        ):
            actual_src = data_src.strip()
            if url and not actual_src.startswith(('http://', 'https://', 'data:')):
                actual_src = urljoin(url, actual_src)
            img['src'] = actual_src
            if 'data-src' in img.attrs:
                del img['data-src']

    # Convert relative image URLs to absolute
    for img in content_elem.find_all('img'):
        src = img.get('src', '')
        if src and url and not src.startswith(('http://', 'https://', 'data:')):
            img['src'] = urljoin(url, src)

    # Simplify HTML: remove classes, styles, unwrap decorative containers
    _simplify_html_element(content_elem)

    # Remove HTML comments
    for comment in content_elem.find_all(string=lambda t: isinstance(t, Comment)):
        comment.extract()

    # Paragraphize: wrap loose inline/text children inside divs with <p>
    # so they get proper block-level line breaks after section/article unwrap.
    # Images are also wrapped so they sit in their own paragraph with spacing.
    for div in content_elem.find_all('div'):
        if div is content_elem:
            continue
        if div.parent and div.parent.name in ('p', 'pre', 'td', 'th', 'li'):
            continue
        for child in list(div.children):
            if child.name is None:
                text = str(child).strip()
                if text:
                    new_p = content_elem.new_tag('p')
                    new_p.string = text
                    child.replace_with(new_p)
            elif child.name not in ('p', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
                                    'div', 'ul', 'ol', 'table', 'pre', 'blockquote',
                                    'hr', 'br'):
                new_p = content_elem.new_tag('p')
                child.wrap(new_p)

    # Remove empty block-level tags (but keep <img> and <br>)
    for tag in content_elem.find_all():
        if tag.name in ('img', 'br', 'hr'):
            continue
        if not tag.get_text(strip=True) and not tag.find_all('img'):
            tag.decompose()

    # Strip root element attributes so no hidden styles/classes leak through
    content_elem.attrs = {}

    # Assemble title + body
    parts = []
    if title_text:
        parts.append(f'<h1>{title_text}</h1>')
    parts.append(str(content_elem))
    return '\n'.join(parts)


def _sanitize_full_html(html_str: str, url: str = "") -> str:
    """
    Sanitize raw HTML for safe offline reading.

    Removes external resource references (<script>, <link stylesheet>, etc.)
    that cause CORS/404 errors when the file is opened via file:// protocol.
    Also fixes lazy-loaded images and converts relative URLs to absolute.
    """
    try:
        from bs4 import BeautifulSoup, Comment
        from urllib.parse import urljoin
    except ImportError:
        return html_str

    soup = BeautifulSoup(html_str, 'lxml')

    # 1. Remove tags that cause external requests or are useless offline
    remove_tags = {
        'script', 'noscript', 'iframe', 'svg', 'canvas',
        'video', 'audio', 'form', 'input', 'button',
        'select', 'textarea', 'nav', 'embed', 'object',
    }
    for tag_name in remove_tags:
        for tag in soup.find_all(tag_name):
            tag.decompose()

    # 2. Remove <style> tags (inline styles often depend on external CSS vars)
    for tag in soup.find_all('style'):
        tag.decompose()

    # 3. Remove <link> tags (stylesheets, preloads, etc.)
    for tag in soup.find_all('link'):
        tag.decompose()

    # 4. Remove <meta> tags that cause issues (CSP, referrer, etc.)
    for tag in soup.find_all('meta'):
        http_equiv = tag.get('http-equiv', '').lower()
        if http_equiv in ('content-security-policy', 'content-security-policy-report-only'):
            tag.decompose()

    # 5. Remove HTML comments
    for comment in soup.find_all(string=lambda t: isinstance(t, Comment)):
        comment.extract()

    # 6. Fix lazy-loaded images and convert relative URLs
    for img in soup.find_all('img'):
        data_src = img.get('data-src', '')
        src = img.get('src', '')
        if data_src and (
            not src
            or src.startswith('data:')
            or 'placeholder' in src.lower()
            or '1x1' in src.lower()
            or 'blank' in src.lower()
            or 'spacer' in src.lower()
        ):
            actual_src = data_src.strip()
            if url and not actual_src.startswith(('http://', 'https://', 'data:')):
                actual_src = urljoin(url, actual_src)
            img['src'] = actual_src
            if 'data-src' in img.attrs:
                del img.attrs['data-src']
        # Convert relative src to absolute
        src = img.get('src', '')
        if src and url and not src.startswith(('http://', 'https://', 'data:')):
            img['src'] = urljoin(url, src)
        # Clean image attributes
        for attr in list(img.attrs.keys()):
            if attr.lower() not in ('src', 'alt', 'title', 'width', 'height'):
                del img.attrs[attr]

    # 7. Remove event-handler attributes and data-* / class / id / style / role
    event_prefixes = ('on', 'aria-', 'data-')
    for tag in soup.find_all(True):
        if tag.attrs is None:
            continue
        attrs_to_remove = []
        for attr in list(tag.attrs.keys()):
            attr_lower = attr.lower()
            if attr_lower.startswith(event_prefixes):
                attrs_to_remove.append(attr)
            elif attr_lower in ('class', 'id', 'role', 'tabindex', 'style'):
                attrs_to_remove.append(attr)
        for attr in attrs_to_remove:
            del tag.attrs[attr]

    # 8. Remove empty head if nothing useful remains
    head = soup.head
    if head and not head.find_all(True):
        head.decompose()

    return str(soup)


def extract_main_content(html_bytes: bytes, url: str = "") -> str:
    """
    Extract main article content from raw HTML.

    Strategy:
    1. Try site-specific selectors first (preserves original image placement).
    2. Fall back to trafilatura for generic pages.
    3. Final fallback to raw HTML.

    Args:
        html_bytes: Raw HTML bytes.
        url: Original URL (helps resolve relative links).

    Returns:
        Clean HTML string containing only the main content (title + body + images).
    """
    html_str = decode_with_detection(html_bytes)

    # Strategy 1: site-specific extraction (best for WeChat, Zhihu, etc.)
    extracted = _extract_by_common_selectors(html_str, url)
    if extracted:
        img_count = extracted.count('<img')
        logger.info(
            LogModule.WORKFLOW,
            f"[URL-FETCH] Site-specific extraction: {len(extracted)} chars, {img_count} image(s)",
        )
        return extracted

    # Strategy 2: trafilatura for generic pages
    try:
        import trafilatura
    except ImportError:
        logger.error(LogModule.WORKFLOW, "[URL-FETCH] trafilatura not installed, falling back to raw HTML")
        return html_str

    # Preprocess lazy-loaded images so trafilatura can see them
    html_str = _preprocess_lazy_load_images(html_str, url)

    extracted = trafilatura.extract(
        html_str,
        url=url or None,
        output_format="html",
        include_images=True,
        include_comments=False,
        include_tables=True,
        include_links=True,
        favor_precision=False,
        favor_recall=True,
    )

    if extracted and extracted.strip():
        try:
            from bs4 import BeautifulSoup
            from urllib.parse import urljoin

            soup = BeautifulSoup(extracted, 'lxml')
            img_count = 0
            for graphic in soup.find_all('graphic'):
                graphic.name = 'img'
                src = (
                    graphic.get('src', '')
                    or graphic.get('url', '')
                    or graphic.get('data-src', '')
                )
                if src and url and not src.startswith(('http://', 'https://', 'data:')):
                    src = urljoin(url, src)
                if src:
                    graphic['src'] = src
                    img_count += 1
            extracted = str(soup)
            logger.info(
                LogModule.WORKFLOW,
                f"[URL-FETCH] Converted {img_count} <graphic> tag(s) to <img>",
            )

            if img_count == 0:
                extracted = _insert_images_at_positions(extracted, html_str, url)
        except Exception as e:
            logger.warning(
                LogModule.WORKFLOW,
                f"[URL-FETCH] Failed to convert <graphic> to <img>: {e}",
            )
        logger.info(
            LogModule.WORKFLOW,
            f"[URL-FETCH] Extracted main content: {len(extracted)} chars",
        )
        return extracted

    logger.warning(
        LogModule.WORKFLOW,
        "[URL-FETCH] trafilatura returned empty content, falling back to raw HTML",
    )
    return html_str
