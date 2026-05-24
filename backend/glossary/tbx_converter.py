# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

"""
TBX ↔ CSV-dict converter for Owlangs glossary system.

TBX (TermBase eXchange) is the ISO standard XML format for terminology exchange.
This module converts between TBX files and the internal CSV-dict format
({src: {dst, category, target_lang}}) without modifying the internal data model.
"""

from pathlib import Path
from typing import Dict, List, Optional
from collections import defaultdict

try:
    import xml.etree.ElementTree as ET
except ImportError:
    ET = None


# Language code normalization map (ISO 639-1 → BCP 47 with region)
_LANG_CODE_MAP = {
    'en': 'en-US',
    'zh': 'zh-CN',
    'ja': 'ja-JP',
    'ko': 'ko-KR',
    'fr': 'fr-FR',
    'de': 'de-DE',
    'es': 'es-ES',
    'ru': 'ru-RU',
    'ar': 'ar-SA',
    'pt': 'pt-BR',
    'it': 'it-IT',
    'nl': 'nl-NL',
    'sv': 'sv-SE',
    'da': 'da-DK',
    'fi': 'fi-FI',
    'nb': 'nb-NO',
    'pl': 'pl-PL',
    'tr': 'tr-TR',
    'th': 'th-TH',
    'vi': 'vi-VN',
}


def _lang_code_to_tbx(code: str) -> str:
    """Normalize a language code to TBX-compatible BCP 47 format.

    - 'en' → 'en-US'
    - 'zh' → 'zh-CN'
    - Already region-qualified codes (e.g. 'en-US', 'zh-CN') are returned as-is.
    """
    if not code:
        return 'en-US'
    # If it already looks like a BCP 47 tag (contains '-'), return as-is
    if '-' in code:
        return code
    return _LANG_CODE_MAP.get(code, code)


def _lang_code_from_tbx(code: str) -> str:
    """Reverse: convert a TBX xml:lang back to a short ISO code for CSV storage.

    - 'en-US' → 'en'
    - 'zh-CN' → 'zh'
    - Other codes → first part before '-'
    """
    if not code:
        return 'en'
    return code.split('-')[0]


def _find_elements(root: ET.Element, tag_suffix: str) -> List[ET.Element]:
    """Find elements by tag suffix, trying multiple namespace strategies."""
    results = root.findall(f'.//{tag_suffix}')
    if not results:
        results = root.findall(f'.//{tag_suffix}')
    if not results:
        # Try case-insensitive partial match
        for elem in root.iter():
            if tag_suffix.lower() in elem.tag.lower():
                results.append(elem)
    return results


def _get_element_text(elem: ET.Element, child_tag: str) -> Optional[str]:
    """Get text from a child element, trying direct find and iter find."""
    child = elem.find(child_tag)
    if child is None:
        child = elem.find(f'.//{child_tag}')
    if child is not None and child.text:
        return child.text.strip()
    return None


def detect_languages(tbx_path: Path) -> List[str]:
    """Scan a TBX file and return all distinct language codes found.

    Returns short ISO codes (e.g. ['en', 'zh', 'ja']).
    """
    if ET is None:
        raise ImportError("xml.etree.ElementTree is required to parse TBX files")

    tree = ET.parse(tbx_path)
    root = tree.getroot()

    languages: set = set()
    for elem in root.iter():
        lang = (elem.get('xml:lang')
                or elem.get('lang')
                or elem.get('{http://www.w3.org/XML/1998/namespace}lang'))
        if lang:
            languages.add(_lang_code_from_tbx(lang))

    return sorted(languages)


def tbx_to_entries(
    tbx_path: Path,
    source_lang: str = 'en',
) -> Dict[str, Dict[str, str]]:
    """Parse a TBX file into the internal CSV-dict format.

    Args:
        tbx_path: Path to the .tbx file.
        source_lang: The language (short ISO code) to treat as the source.
                      Entries in this language become the 'src' key.

    Returns:
        Dict mapping source term → {dst, category, target_lang}.
        If a TBX entry contains multiple non-source languages, multiple
        entries are created (one per target language).
    """
    if ET is None:
        raise ImportError("xml.etree.ElementTree is required to parse TBX files")

    tree = ET.parse(tbx_path)
    root = tree.getroot()

    source_lang_tbx = _lang_code_to_tbx(source_lang)
    result: Dict[str, Dict[str, str]] = {}

    # Find all termEntry elements
    term_entries = _find_elements(root, 'termEntry')
    if not term_entries:
        return result

    for entry in term_entries:
        # Collect all langSets
        lang_sets = _find_elements(entry, 'langSet')
        if not lang_sets:
            lang_sets = _find_elements(entry, 'langGrp')

        # Separate source and target langSets
        source_terms: List[str] = []
        target_groups: List[tuple] = []  # (dst, target_lang_code)

        for lang_set in lang_sets:
            lang = (lang_set.get('xml:lang')
                    or lang_set.get('lang')
                    or lang_set.get('{http://www.w3.org/XML/1998/namespace}lang', ''))
            lang_short = _lang_code_from_tbx(lang) if lang else ''

            # Extract all terms from this langSet
            tig_elements = _find_elements(lang_set, 'tig')
            term_grp_elements = _find_elements(lang_set, 'termGrp')

            # Deduplicate: list(tigs) + list(termGrps) may overlap via _find_elements aggregation
            seen_term_texts: set = set()
            for tg in tig_elements + term_grp_elements:
                term_text = _get_element_text(tg, 'term')
                if term_text and term_text not in seen_term_texts:
                    seen_term_texts.add(term_text)

                    # Also extract termNote/descrip for metadata (minimal — just category mapping)
                    category = ''
                    for child in tg.iter():
                        tag_lower = child.tag.lower()
                        if 'note' in tag_lower and child.text:
                            note_type = child.get('type', '')
                            # Map 'subjectField' or 'domain' to category
                            if note_type in ('subjectField', 'domain'):
                                category = child.text.strip()

                    if lang_short == source_lang:
                        source_terms.append(term_text)
                    else:
                        target_lang = lang_short if lang_short else 'unknown'
                        target_groups.append((term_text, target_lang, category))

        # Create entries: for each source term × each (dst, target_lang) pair
        if not source_terms or not target_groups:
            continue

        for src in source_terms:
            for dst, tlang, cat in target_groups:
                entry_key = src
                # If same src + target_lang already exists, disambiguate
                if entry_key in result and result[entry_key].get('target_lang') == tlang:
                    disambiguator = 1
                    while f"{entry_key}___{disambiguator}" in result:
                        disambiguator += 1
                    entry_key = f"{entry_key}___{disambiguator}"
                result[entry_key] = {
                    'dst': dst,
                    'category': cat,
                    'target_lang': tlang,
                }

    return result


def entries_to_tbx(
    glossary_dict: Dict[str, Dict[str, str]],
    output_path: Path,
    source_lang: str = 'en',
) -> str:
    """Convert internal CSV-dict format to a TBX-Basic XML file.

    Args:
        glossary_dict: Dict mapping source term → {dst, category, target_lang}.
        output_path: Where to write the .tbx file.
        source_lang: The language (short ISO code) of the 'src' field.

    Returns:
        The string path to the written file, or empty string on failure.
    """
    if ET is None:
        raise ImportError("xml.etree.ElementTree is required to write TBX files")

    if not glossary_dict:
        return ''

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Group entries by (source_term, target_lang) for multi-term merging
    # structure: {src_term: {target_lang: [dst, category]}}
    entry_groups: Dict[str, Dict[str, tuple]] = {}
    for src, entry in glossary_dict.items():
        dst = entry.get('dst', '')
        target_lang = entry.get('target_lang', '')
        category = entry.get('category', '')
        if dst:
            if src not in entry_groups:
                entry_groups[src] = {}
            # Keep first dst per target_lang (prefer existing)
            if target_lang not in entry_groups[src]:
                entry_groups[src][target_lang] = (dst, category)

    source_lang_tbx = _lang_code_to_tbx(source_lang)

    try:
        # Build XML
        root = ET.Element('martif', {
            'type': 'TBX-Basic',
            'xml:lang': source_lang,
        })

        # Header
        martif_header = ET.SubElement(root, 'martifHeader')
        file_desc = ET.SubElement(martif_header, 'fileDesc')
        title_stmt = ET.SubElement(file_desc, 'titleStmt')
        title = ET.SubElement(title_stmt, 'title')
        title.text = 'Terminology Database'
        source_desc = ET.SubElement(file_desc, 'sourceDesc')
        p = ET.SubElement(source_desc, 'p')
        p.text = 'Exported from Owlangs Glossary'

        encoding_desc = ET.SubElement(martif_header, 'encodingDesc')
        p_encoding = ET.SubElement(encoding_desc, 'p', {'type': 'DCSName'})
        p_encoding.text = 'TBXBasicXCSV02.xcs'

        # Body
        text = ET.SubElement(root, 'text')
        body = ET.SubElement(text, 'body')

        for idx, (src_term, lang_map) in enumerate(entry_groups.items(), start=1):
            term_entry = ET.SubElement(body, 'termEntry', {'id': f'TE-{idx:03d}'})

            # Source language langSet
            src_lang_set = ET.SubElement(term_entry, 'langSet', {'xml:lang': source_lang_tbx})
            src_ntig = ET.SubElement(src_lang_set, 'ntig')
            src_term_grp = ET.SubElement(src_ntig, 'termGrp')
            ET.SubElement(src_term_grp, 'term').text = src_term

            # Target language langSets
            for target_lang, (dst, category) in lang_map.items():
                if not dst:
                    continue
                target_lang_tbx = _lang_code_to_tbx(target_lang) if target_lang else 'unknown'
                tgt_lang_set = ET.SubElement(term_entry, 'langSet', {'xml:lang': target_lang_tbx})
                tgt_ntig = ET.SubElement(tgt_lang_set, 'ntig')
                tgt_term_grp = ET.SubElement(tgt_ntig, 'termGrp')
                ET.SubElement(tgt_term_grp, 'term').text = dst

                # Category → descrip type="subjectField"
                if category:
                    ET.SubElement(tgt_term_grp, 'descrip', {'type': 'subjectField'}).text = category

        # Write with DOCTYPE
        tree = ET.ElementTree(root)
        with open(str(output_path), 'wb') as f:
            f.write(b'<?xml version="1.0" encoding="UTF-8"?>\n')
            f.write(b'<!DOCTYPE martif SYSTEM "TBXBasiccoreStructV02.dtd">\n')
            tree.write(f, encoding='utf-8', method='xml', xml_declaration=False)

        if output_path.exists():
            return str(output_path)
        return ''

    except Exception:
        return ''


def tbx_bytes_to_entries(
    content: bytes,
    source_lang: str = 'en',
) -> Dict[str, Dict[str, str]]:
    """Parse TBX content from bytes into internal CSV-dict format.

    Same as tbx_to_entries but reads from bytes instead of a file path.
    Useful for API uploads where the file is in memory.
    """
    if ET is None:
        raise ImportError("xml.etree.ElementTree is required to parse TBX files")

    import tempfile
    with tempfile.NamedTemporaryFile(suffix='.tbx', delete=False) as tmp:
        tmp.write(content)
        tmp_path = tmp.name

    try:
        return tbx_to_entries(Path(tmp_path), source_lang)
    finally:
        Path(tmp_path).unlink(missing_ok=True)


def entries_to_tbx_bytes(
    glossary_dict: Dict[str, Dict[str, str]],
    source_lang: str = 'en',
) -> bytes:
    """Convert internal CSV-dict format to TBX bytes (in-memory).

    Same as entries_to_tbx but returns bytes instead of writing to file.
    """
    import tempfile
    with tempfile.NamedTemporaryFile(suffix='.tbx', delete=False) as tmp:
        tmp_path = tmp.name

    try:
        result_path = entries_to_tbx(glossary_dict, Path(tmp_path), source_lang)
        if result_path:
            return Path(result_path).read_bytes()
        return b''
    finally:
        Path(tmp_path).unlink(missing_ok=True)
