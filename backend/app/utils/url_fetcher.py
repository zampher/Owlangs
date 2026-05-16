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


def extract_main_content(html_bytes: bytes, url: str = "") -> str:
    """
    Extract main article content from raw HTML using trafilatura.

    Args:
        html_bytes: Raw HTML bytes.
        url: Original URL (helps trafilatura resolve relative links).

    Returns:
        Clean HTML string containing only the main content (title + body + images).
    """
    try:
        import trafilatura
    except ImportError:
        logger.error(LogModule.WORKFLOW, "[URL-FETCH] trafilatura not installed, falling back to raw HTML")
        return decode_with_detection(html_bytes)

    html_str = decode_with_detection(html_bytes)

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
        # Trafilatura converts <img> to <graphic> when include_images=True.
        # Convert <graphic> back to <img> so downstream processing
        # (HtmlExtractor, browsers, Pandoc DOCX export) handles images.
        # Also convert relative image URLs to absolute URLs so exported
        # documents can display images without the original site context.
        try:
            from bs4 import BeautifulSoup
            from urllib.parse import urljoin

            soup = BeautifulSoup(extracted, 'lxml')
            for graphic in soup.find_all('graphic'):
                graphic.name = 'img'
                # Resolve relative image URLs
                src = graphic.get('src', '')
                if src and url and not src.startswith(('http://', 'https://', 'data:')):
                    graphic['src'] = urljoin(url, src)
            extracted = str(soup)
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
