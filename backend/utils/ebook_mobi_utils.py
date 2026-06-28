# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

"""Helpers to distinguish MOBI bytes from EPUB/ZIP mislabeled as MOBI.

Validation mirrors Calibre 9.x MOBI reader identity check:
  calibre/ebooks/mobi/reader/headers.py  MetadataHeader.identity()
  calibre/ebooks/mobi/reader/mobi6.py    MobiReader.__init__
  calibre/ebooks/mobi/debug/headers.py   PalmDB (type+creator at offset 60)
"""

# Palm DB header: 32-byte name + 28 bytes metadata => ident at offset 60
_MOBI_IDENT_OFFSET = 60
_MOBI_IDENT_LENGTH = 8
_VALID_MOBI_IDENTS = frozenset({b"BOOKMOBI", b"TEXTREAD"})


def is_epub_zip_bytes(data: bytes) -> bool:
    """Return True when bytes look like a ZIP/EPUB container (not MOBI)."""
    return bool(data) and len(data) >= 2 and data[:2] == b"PK"


def mobi_ident_at_offset(data: bytes) -> bytes:
    """Return the 8-byte MOBI type identifier Calibre reads at offset 60."""
    if not data or len(data) < _MOBI_IDENT_OFFSET + _MOBI_IDENT_LENGTH:
        return b""
    return data[_MOBI_IDENT_OFFSET : _MOBI_IDENT_OFFSET + _MOBI_IDENT_LENGTH].upper()


def is_valid_mobi_bytes(data: bytes) -> bool:
    """Return True when bytes look like a Palm/MOBI file Calibre can open."""
    if not data or len(data) < _MOBI_IDENT_OFFSET + _MOBI_IDENT_LENGTH:
        return False
    if is_epub_zip_bytes(data):
        return False
    if data.startswith(b"TPZ"):
        return False
    if data.startswith(b"\xeaDRMION\xee"):
        return False
    return mobi_ident_at_offset(data) in _VALID_MOBI_IDENTS
