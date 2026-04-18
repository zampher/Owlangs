# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

"""
Encoding utilities.

Provides robust text encoding detection and decoding functions.
"""

from logger import unified_logger as logger
from logger.logger import LogModule


def decode_with_detection(data: bytes) -> str:
    """
    Robust bytes->str decoding with detection and fallbacks.
    
    Attempts to decode bytes using multiple encoding strategies:
    1. UTF-8
    2. UTF-8 with BOM (UTF-8-SIG)
    3. charset_normalizer (if available)
    4. Common encodings (GB18030, GBK, CP936, Big5, Shift-JIS, etc.)
    5. UTF-8 with error replacement (final fallback)
    
    Args:
        data: Bytes to decode
        
    Returns:
        Decoded string
    """
    if not data:
        return ""
    
    try:
        text = data.decode("utf-8")
        logger.info(LogModule.SYSTEM, f"[ENCODE] decoded as utf-8, len={len(text)}")
        return text
    except UnicodeDecodeError:
        pass
    
    try:
        text = data.decode("utf-8-sig")
        logger.info(LogModule.SYSTEM, f"[ENCODE] decoded as utf-8-sig (BOM), len={len(text)}")
        return text
    except UnicodeDecodeError:
        pass
    
    try:
        import charset_normalizer  # type: ignore
        result = charset_normalizer.from_bytes(data).best()
        if result is not None:
            enc = getattr(result, "encoding", "unknown")
            text = str(result)
            logger.info(LogModule.SYSTEM, f"[ENCODE] charset_normalizer best encoding={enc}, len={len(text)}")
            return text
    except Exception:
        pass
    
    for enc in ("gb18030", "gbk", "cp936", "big5", "shift_jis", "euc-jp", "euc-kr", "iso-8859-1"):
        try:
            text = data.decode(enc)
            logger.info(LogModule.SYSTEM, f"[ENCODE] decoded with fallback encoding={enc}, len={len(text)}")
            return text
        except UnicodeDecodeError:
            continue
    
    text = data.decode("utf-8", errors="replace")
    logger.warning(LogModule.SYSTEM, f"[ENCODE] fallback utf-8(replace), len={len(text)}")
    return text

