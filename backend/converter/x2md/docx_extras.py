from __future__ import annotations

"""
DOCX utilities
 - extract_headers_footers(docx_bytes) -> list[(location, text)]
 - apply_headers_footers(docx_bytes, translations) -> bytes
 - extract_text_in_textboxes_and_sdts(docx_bytes) -> list[(location, text)]
 - apply_text_in_textboxes_and_sdts(docx_bytes, translations) -> bytes

Notes:
 - Keep field codes (PAGE, NUMPAGES, TOC) intact for headers/footers.
 - Textboxes are located in w:txbxContent (drawing) and sometimes legacy v:textbox; we best-effort handle both.
 - SDTs (Structured Document Tags / Content Controls) are w:sdt nodes.
"""

from io import BytesIO
from typing import List, Tuple, Dict

try:
    from docx import Document  # type: ignore
except Exception:  # optional dependency
    Document = None  # type: ignore


Location = Tuple[str, int]  # ("header"|"footer", section_index)


def _set_paragraph_text(paragraph, text: str):
    """Set text for a paragraph, clearing existing content."""
    # Clear existing runs
    for run in paragraph.runs:
        run.text = ""
    
    # Add new text as a single run
    if text:
        paragraph.add_run(text)


def extract_headers_footers(docx_bytes: bytes) -> List[Tuple[Location, str]]:
    if Document is None:
        return []
    doc = Document(BytesIO(docx_bytes))
    items: List[Tuple[Location, str]] = []
    for idx, section in enumerate(doc.sections):
        for name, part in (("header", section.header), ("footer", section.footer)):
            texts: List[str] = []
            for p in part.paragraphs:
                texts.append(p.text)
            for tbl in part.tables:
                for row in tbl.rows:
                    for cell in row.cells:
                        for p in cell.paragraphs:
                            texts.append(p.text)
            content = "\n".join(t for t in texts if t)
            if content.strip():
                items.append(((name, idx), content))
    return items


def apply_headers_footers(docx_bytes: bytes, translations: Dict[Location, str]) -> bytes:
    if Document is None:
        return docx_bytes
    doc = Document(BytesIO(docx_bytes))
    for idx, section in enumerate(doc.sections):
        for name, part in (("header", section.header), ("footer", section.footer)):
            key: Location = (name, idx)
            if key not in translations:
                continue
            new_text = translations[key]
            # Clear existing paragraphs (preserve tables layout by editing cell texts)
            # Paragraphs
            if part.paragraphs:
                # replace first paragraph text; remove extra paragraphs
                part.paragraphs[0].clear() if hasattr(part.paragraphs[0], 'clear') else None
                _set_paragraph_text(part.paragraphs[0], new_text)
                for p in part.paragraphs[1:]:
                    _set_paragraph_text(p, "")
            else:
                part.add_paragraph(new_text)
    bio = BytesIO()
    doc.save(bio)
    return bio.getvalue()


def has_toc_field(docx_bytes: bytes) -> bool:
    """Detect whether document contains a TOC field ({ TOC ... }).
    We simply scan for 'TOC' in field codes of the main document and headers/footers.
    """
    if Document is None:
        return False
    doc = Document(BytesIO(docx_bytes))
    # check body
    if _document_contains_toc(doc):
        return True
    # check sections' header/footer
    for section in doc.sections:
        for part in (section.header, section.footer):
            if _part_contains_toc(part):
                return True
    return False


def _document_contains_toc(doc) -> bool:
    from docx.oxml import OxmlElement  # type: ignore
    # paragraphs
    for p in doc.paragraphs:
        if _p_has_toc_field(p):
            return True
    # tables
    for tbl in doc.tables:
        for row in tbl.rows:
            for cell in row.cells:
                for p in cell.paragraphs:
                    if _p_has_toc_field(p):
                        return True
    return False


def _part_contains_toc(part) -> bool:
    for p in part.paragraphs:
        if _p_has_toc_field(p):
            return True
    for tbl in part.tables:
        for row in tbl.rows:
            for cell in row.cells:
                for p in cell.paragraphs:
                    if _p_has_toc_field(p):
                        return True
    return False


def _p_has_toc_field(paragraph) -> bool:
    try:
        p = paragraph._p  # lxml element
        fldChars = p.xpath('.//*[local-name()="fldChar"]')
        if not fldChars:
            # quick check for instruction text
            instrs = p.xpath('.//*[local-name()="instrText"]')
            for it in instrs:
                if 'TOC' in (it.text or ''):
                    return True
            return False
        instrs = p.xpath('.//*[local-name()="instrText"]')
        for it in instrs:
            if 'TOC' in (it.text or ''):
                return True
    except Exception:
        return False
    return False


def _set_paragraph_text(paragraph, text: str) -> None:
    # simple setter that avoids losing style: clear runs then add one run
    for run in list(getattr(paragraph, 'runs', [])):
        try:
            run.clear()  # type: ignore
        except Exception:
            try:
                run.text = ""
            except Exception:
                pass
    try:
        run = paragraph.add_run()
        run.text = text
    except Exception:
        try:
            paragraph.text = text
        except Exception:
            pass


def refresh_toc_fields(docx_bytes: bytes, method: str = "field_update") -> bytes:
    """
    Refresh TOC (Table of Contents) fields in the DOCX document.
    This function updates all TOC field codes to ensure they display current content.
    
    Args:
        docx_bytes: The DOCX document bytes
        method: The refresh method to use:
            - "field_update": Update field codes to force refresh
            - "field_clear": Clear and recreate TOC fields
            - "full_rebuild": Completely rebuild TOC structure
    """
    if Document is None:
        return docx_bytes
    
    try:
        doc = Document(BytesIO(docx_bytes))
        
        if method == "field_update":
            # Method 1: Update field codes to force refresh
            _refresh_toc_in_document(doc)
            _refresh_toc_in_headers_footers(doc)
            
        elif method == "field_clear":
            # Method 2: Clear and recreate TOC fields
            _clear_and_recreate_toc_fields(doc)
            
        elif method == "full_rebuild":
            # Method 3: Completely rebuild TOC structure
            _rebuild_toc_structure(doc)
            
        else:
            print(f"[DEBUG] Unknown TOC refresh method: {method}, using field_update")
            _refresh_toc_in_document(doc)
            _refresh_toc_in_headers_footers(doc)
        
        # Save the updated document
        bio = BytesIO()
        doc.save(bio)
        return bio.getvalue()
        
    except Exception as e:
        print(f"[DEBUG] Error refreshing TOC fields: {e}")
        return docx_bytes


def _refresh_toc_in_headers_footers(doc) -> None:
    """Refresh TOC fields in headers and footers."""
    for section in doc.sections:
        _refresh_toc_in_part(section.header)
        _refresh_toc_in_part(section.footer)


def _clear_and_recreate_toc_fields(doc) -> None:
    """Clear existing TOC fields and recreate them."""
    try:
        # Find and clear all TOC fields
        for para in doc.paragraphs:
            _clear_toc_field_in_paragraph(para)
        
        # Recreate TOC fields
        _recreate_toc_fields(doc)
        
    except Exception as e:
        print(f"[DEBUG] Error clearing and recreating TOC fields: {e}")


def _clear_toc_field_in_paragraph(paragraph) -> None:
    """Clear TOC field in a single paragraph."""
    try:
        p = paragraph._p  # lxml element
        
        # Find TOC field characters
        fldChars = p.xpath('.//*[local-name()="fldChar"]')
        if not fldChars:
            return
        
        # Find instruction text
        instrs = p.xpath('.//*[local-name()="instrText"]')
        for it in instrs:
            if 'TOC' in (it.text or ''):
                # Clear the field
                it.text = ""
                break
                
    except Exception as e:
        print(f"[DEBUG] Error clearing TOC field in paragraph: {e}")


def _recreate_toc_fields(doc) -> None:
    """Recreate TOC fields in the document."""
    try:
        # This is a simplified recreation - in practice, you might want to
        # preserve the original TOC field properties
        for para in doc.paragraphs:
            if _p_has_toc_field(para):
                # Recreate the TOC field
                _add_toc_field_to_paragraph(para)
                
    except Exception as e:
        print(f"[DEBUG] Error recreating TOC fields: {e}")


def _add_toc_field_to_paragraph(paragraph) -> None:
    """Add a TOC field to a paragraph."""
    try:
        # This is a simplified implementation
        # In practice, you would need to create the proper XML structure
        p = paragraph._p  # lxml element
        
        # Add TOC field instruction
        from docx.oxml import OxmlElement
        from docx.oxml.ns import qn
        
        # Create field instruction
        instr_text = OxmlElement('w:instrText')
        instr_text.text = 'TOC \\o "1-3" \\h \\z \\u'
        instr_text.set(qn('w:space'), 'preserve')
        
        # Add to paragraph
        p.append(instr_text)
        
    except Exception as e:
        print(f"[DEBUG] Error adding TOC field to paragraph: {e}")


def _rebuild_toc_structure(doc) -> None:
    """Completely rebuild the TOC structure."""
    try:
        # This is a more complex operation that would involve:
        # 1. Finding all heading paragraphs
        # 2. Creating a new TOC structure
        # 3. Replacing the old TOC with the new one
        
        # For now, we'll use the field update method
        print("[DEBUG] Full TOC rebuild not fully implemented, using field update")
        _refresh_toc_in_document(doc)
        _refresh_toc_in_headers_footers(doc)
        
    except Exception as e:
        print(f"[DEBUG] Error rebuilding TOC structure: {e}")


def force_toc_update(docx_bytes: bytes) -> bytes:
    """
    Force a complete TOC update using multiple methods.
    This function tries different approaches to ensure the TOC is updated.
    """
    if Document is None:
        return docx_bytes
    
    try:
        # Method 1: Field update
        print("[DEBUG] Attempting TOC update with field_update method")
        result = refresh_toc_fields(docx_bytes, "field_update")
        
        # Method 2: If that doesn't work, try field clear
        if result == docx_bytes:
            print("[DEBUG] Field update failed, trying field_clear method")
            result = refresh_toc_fields(docx_bytes, "field_clear")
        
        # Method 3: If that doesn't work, try full rebuild
        if result == docx_bytes:
            print("[DEBUG] Field clear failed, trying full_rebuild method")
            result = refresh_toc_fields(docx_bytes, "full_rebuild")
        
        return result
        
    except Exception as e:
        print(f"[DEBUG] Error in force_toc_update: {e}")
        return docx_bytes


def update_static_toc(docx_bytes: bytes) -> bytes:
    """
    Update static table of contents by regenerating it based on current headings.
    This function creates a new TOC based on the current document structure.
    """
    if Document is None:
        return docx_bytes
    
    try:
        doc = Document(BytesIO(docx_bytes))
        
        # Find all heading paragraphs
        headings = []
        for i, para in enumerate(doc.paragraphs):
            if hasattr(para, 'style') and para.style:
                style_name = para.style.name.lower()
                if 'heading' in style_name:
                    # Extract heading level
                    level = 1
                    if 'heading 1' in style_name:
                        level = 1
                    elif 'heading 2' in style_name:
                        level = 2
                    elif 'heading 3' in style_name:
                        level = 3
                    elif 'heading 4' in style_name:
                        level = 4
                    elif 'heading 5' in style_name:
                        level = 5
                    elif 'heading 6' in style_name:
                        level = 6
                    
                    headings.append({
                        'level': level,
                        'text': para.text.strip(),
                        'paragraph': para
                    })
        
        print(f"[DEBUG] Found {len(headings)} headings in document")
        
        # Generate new TOC content
        toc_content = _generate_toc_content(headings)
        
        # Find and replace existing TOC
        _replace_static_toc(doc, toc_content)
        
        # Save the updated document
        bio = BytesIO()
        doc.save(bio)
        return bio.getvalue()
        
    except Exception as e:
        print(f"[DEBUG] Error updating static TOC: {e}")
        return docx_bytes


def _generate_toc_content(headings: List[Dict]) -> str:
    """Generate TOC content from headings."""
    toc_lines = []
    
    for heading in headings:
        level = heading['level']
        text = heading['text']
        
        # Create indentation based on level
        indent = "  " * (level - 1)
        
        # Add bullet point or number
        if level == 1:
            bullet = "•"
        elif level == 2:
            bullet = "◦"
        else:
            bullet = "▪"
        
        toc_lines.append(f"{indent}{bullet} {text}")
    
    return "\n".join(toc_lines)


def _replace_static_toc(doc, new_toc_content: str) -> None:
    """Replace existing static TOC with new content."""
    try:
        # Find the first paragraph that looks like a TOC
        toc_paragraph = None
        for para in doc.paragraphs:
            text = para.text.strip()
            if any(keyword in text for keyword in ["目录", "Table of Contents", "Contents"]):
                toc_paragraph = para
                break
        
        if toc_paragraph:
            # Replace the content
            _set_paragraph_text(toc_paragraph, new_toc_content)
            print(f"[DEBUG] Replaced existing TOC with new content")
        else:
            # Create a new TOC paragraph at the beginning
            if doc.paragraphs:
                # Insert a new paragraph at the beginning
                from docx.oxml import OxmlElement
                from docx.oxml.ns import qn
                
                # Create a new paragraph element
                new_p = OxmlElement('w:p')
                new_r = OxmlElement('w:r')
                new_t = OxmlElement('w:t')
                new_t.text = new_toc_content
                new_r.append(new_t)
                new_p.append(new_r)
                
                # Insert at the beginning of the document
                body = doc._element.body
                body.insert(0, new_p)
                print(f"[DEBUG] Created new TOC paragraph at the beginning")
            else:
                print(f"[DEBUG] No paragraphs found in document")
            
    except Exception as e:
        print(f"[DEBUG] Error replacing static TOC: {e}")


def comprehensive_toc_update(docx_bytes: bytes) -> bytes:
    """
    Comprehensive TOC update that handles both field-based and static TOCs.
    This function tries multiple approaches to ensure the TOC is properly updated.
    """
    if Document is None:
        return docx_bytes
    
    try:
        # First, try to update field-based TOCs
        if has_toc_field(docx_bytes):
            print("[DEBUG] Document contains TOC fields, updating them...")
            result = force_toc_update(docx_bytes)
            if result != docx_bytes:
                return result
        
        # If no field-based TOCs or update failed, try static TOC update
        print("[DEBUG] No TOC fields found or update failed, trying static TOC update...")
        result = update_static_toc(docx_bytes)
        if result != docx_bytes:
            return result
        
        # If all else fails, return original
        print("[DEBUG] All TOC update methods failed, returning original document")
        return docx_bytes
        
    except Exception as e:
        print(f"[DEBUG] Error in comprehensive_toc_update: {e}")
        return docx_bytes


def _refresh_toc_in_document(doc) -> None:
    """Refresh TOC fields in document body."""
    # Refresh TOC in paragraphs
    for p in doc.paragraphs:
        _refresh_toc_in_paragraph(p)
    
    # Refresh TOC in tables
    for tbl in doc.tables:
        for row in tbl.rows:
            for cell in row.cells:
                for p in cell.paragraphs:
                    _refresh_toc_in_paragraph(p)


def _refresh_toc_in_part(part) -> None:
    """Refresh TOC fields in a document part (header/footer)."""
    # Refresh TOC in paragraphs
    for p in part.paragraphs:
        _refresh_toc_in_paragraph(p)
    
    # Refresh TOC in tables
    for tbl in part.tables:
        for row in tbl.rows:
            for cell in row.cells:
                for p in cell.paragraphs:
                    _refresh_toc_in_paragraph(p)


def _refresh_toc_in_paragraph(paragraph) -> None:
    """Refresh TOC field in a single paragraph."""
    try:
        p = paragraph._p  # lxml element
        
        # Find TOC field characters
        fldChars = p.xpath('.//*[local-name()="fldChar"]')
        if not fldChars:
            return
        
        # Find instruction text
        instrs = p.xpath('.//*[local-name()="instrText"]')
        for it in instrs:
            if 'TOC' in (it.text or ''):
                # This is a TOC field, we need to refresh it
                # The simplest way is to update the field code to force refresh
                original_text = it.text or ''
                if original_text.strip():
                    # Add a timestamp or modify the field to force refresh
                    # This will make Word refresh the TOC when the document is opened
                    it.text = original_text.strip() + ' \\* MERGEFORMAT'
                break
                
    except Exception as e:
        print(f"[DEBUG] Error refreshing TOC in paragraph: {e}")
        pass


# -------------------------------
# Textboxes and SDTs (content controls)
# -------------------------------

def extract_text_in_textboxes_and_sdts(docx_bytes: bytes) -> List[Tuple[Location, str]]:
    """
    Extract text from textboxes (w:txbxContent and legacy v:textbox) and SDTs (w:sdt).
    Returns a list of ((kind, index), text), where kind in {"textbox", "sdt"}.
    """
    if Document is None:
        return []
    from docx.oxml.ns import qn  # type: ignore
    doc = Document(BytesIO(docx_bytes))
    items: List[Tuple[Location, str]] = []

    # Helper function to extract text from a container
    def _extract_text_from_container(container, container_name: str, start_index: int) -> int:
        idx = start_index
        texts: List[str] = []
        # paragraphs
        for p in container.xpath('.//*[local-name()="p"]'):
            runs = p.xpath('.//*[local-name()="t"]')
            if runs:
                txt = ''.join([(t.text or '') for t in runs])
                if txt:
                    texts.append(txt)
        # tables
        for cell in container.xpath('.//*[local-name()="tc"]'):
            for p in cell.xpath('.//*[local-name()="p"]'):
                runs = p.xpath('.//*[local-name()="t"]')
                if runs:
                    txt = ''.join([(t.text or '') for t in runs])
                    if txt:
                        texts.append(txt)
        content = "\n".join(t for t in texts if t)
        if content.strip():
            items.append(((container_name, idx), content))
            idx += 1
        return idx

    # Extract all elements with unified indexing
    try:
        # 1) SDTs in body - only extract top-level SDTs to avoid duplication
        sdt_elems = doc._element.body.xpath('.//*[local-name()="sdt"]')
        sdt_index = 0
        for sdt in sdt_elems:
            # Check if this SDT is nested within another SDT
            parent_sdt = sdt.xpath('./ancestor::*[local-name()="sdt"]')
            if parent_sdt:
                print(f"[DEBUG] Skipping nested SDT: {sdt_index}")
                continue
            
            # Process all sdtContent elements within this SDT
            sdt_contents = sdt.xpath('.//*[local-name()="sdtContent"]')
            print(f"[DEBUG] Found {len(sdt_contents)} sdtContent elements in SDT {sdt_index}")
            
            for i, content in enumerate(sdt_contents):
                texts: List[str] = []
                # paragraphs within sdtContent
                for p in content.xpath('.//*[local-name()="p"]'):
                    runs = p.xpath('.//*[local-name()="t"]')
                    if runs:
                        txt = ''.join([(t.text or '') for t in runs])
                        if txt:
                            texts.append(txt)
                # tables within sdtContent
                for cell in content.xpath('.//*[local-name()="tc"]'):
                    for p in cell.xpath('.//*[local-name()="p"]'):
                        runs = p.xpath('.//*[local-name()="t"]')
                        if runs:
                            txt = ''.join([(t.text or '') for t in runs])
                            if txt:
                                texts.append(txt)
                content_text = "\n".join(t for t in texts if t)
                if content_text.strip():
                    items.append((('sdt_content', sdt_index, i), content_text))
                    print(f"[DEBUG] Found sdtContent {i}: {content_text[:50]}...")
            
            # Process child SDTs within this SDT
            child_sdts = sdt.xpath('.//*[local-name()="sdt"]')
            print(f"[DEBUG] Found {len(child_sdts)} child SDTs in SDT {sdt_index}")
            
            for i, child_sdt in enumerate(child_sdts):
                texts: List[str] = []
                # paragraphs within child SDT
                for p in child_sdt.xpath('.//*[local-name()="p"]'):
                    runs = p.xpath('.//*[local-name()="t"]')
                    if runs:
                        txt = ''.join([(t.text or '') for t in runs])
                        if txt:
                            texts.append(txt)
                # tables within child SDT
                for cell in child_sdt.xpath('.//*[local-name()="tc"]'):
                    for p in cell.xpath('.//*[local-name()="p"]'):
                        runs = p.xpath('.//*[local-name()="t"]')
                        if runs:
                            txt = ''.join([(t.text or '') for t in runs])
                            if txt:
                                texts.append(txt)
                child_text = "\n".join(t for t in texts if t)
                if child_text.strip():
                    items.append((('sdt_child', sdt_index, i), child_text))
                    print(f"[DEBUG] Found child SDT {i}: {child_text[:50]}...")
            
            # Process direct SDT content (if no sdtContent or child SDTs)
            if not sdt_contents and not child_sdts:
                texts: List[str] = []
                # paragraphs within sdt
                for p in sdt.xpath('.//*[local-name()="p"]'):
                    runs = p.xpath('.//*[local-name()="t"]')
                    if runs:
                        txt = ''.join([(t.text or '') for t in runs])
                        if txt:
                            texts.append(txt)
                # tables within sdt
                for cell in sdt.xpath('.//*[local-name()="tc"]'):
                    for p in cell.xpath('.//*[local-name()="p"]'):
                        runs = p.xpath('.//*[local-name()="t"]')
                        if runs:
                            txt = ''.join([(t.text or '') for t in runs])
                            if txt:
                                texts.append(txt)
                content = "\n".join(t for t in texts if t)
                if content.strip():
                    items.append((('sdt', sdt_index), content))
                    print(f"[DEBUG] Found SDT content: {content[:50]}...")
            
            sdt_index += 1
        
        # 2) Textboxes and drawing elements - search in entire document
        all_textbox_elements = []
        
        # Search for w:txbxContent nodes
        try:
            txbx_nodes = doc._element.xpath('.//*[local-name()="txbxContent"]')
            all_textbox_elements.extend(txbx_nodes)
        except Exception as e:
            print(f"[DEBUG] Error searching w:txbxContent: {e}")
        
        # Search for legacy v:textbox nodes
        try:
            pict_nodes = doc._element.xpath('.//*[local-name()="pict"]//*[local-name()="textbox"]')
            all_textbox_elements.extend(pict_nodes)
        except Exception as e:
            print(f"[DEBUG] Error searching v:textbox: {e}")
        
        # Search for drawing elements with text
        try:
            drawing_nodes = doc._element.xpath('.//*[local-name()="drawing"]')
            for drawing in drawing_nodes:
                text_elements = drawing.xpath('.//*[local-name()="t"]')
                if text_elements:
                    all_textbox_elements.append(drawing)
        except Exception as e:
            print(f"[DEBUG] Error searching w:drawing: {e}")
        
        print(f"[DEBUG] Found {len(all_textbox_elements)} total textbox/drawing elements in document")
        
        # Process all elements with consistent indexing
        tb_index = 0
        for element in all_textbox_elements:
            if element.tag.endswith('txbxContent') or element.tag.endswith('textbox'):
                # Handle textbox elements
                print(f"[DEBUG] Processing textbox element {tb_index}")
                tb_index = _extract_text_from_container(element, 'textbox', tb_index)
            elif element.tag.endswith('drawing'):
                # Handle drawing elements
                text_elements = element.xpath('.//*[local-name()="t"]')
                if text_elements:
                    texts = []
                    for t_elem in text_elements:
                        if t_elem.text:
                            texts.append(t_elem.text)
                    content = "\n".join(t for t in texts if t)
                    if content.strip():
                        print(f"[DEBUG] Found text in drawing: {content[:100]}...")
                        items.append((('textbox', tb_index), content))
                        tb_index += 1
    except Exception as e:
        print(f"[DEBUG] Error extracting elements: {e}")
        pass

    return items


def apply_text_in_textboxes_and_sdts(docx_bytes: bytes, translations: Dict[Location, str]) -> bytes:
    """
    Apply translations back into textboxes (w:txbxContent / legacy v:textbox) and SDTs.
    The matching order follows extract_text_in_textboxes_and_sdts iteration, keyed by (kind, index).
    """
    if Document is None:
        return docx_bytes
    doc = Document(BytesIO(docx_bytes))

    # Helper to set text for a node containing w:p descendants
    def _apply_to_container(container, kind: str, start_index: int) -> int:
        idx = start_index
        ns = doc._element.nsmap
        if kind == 'legacy':
            ns = dict(ns)
            if 'v' not in ns:
                ns['v'] = 'urn:schemas-microsoft-com:vml'
            p_xpath = './/*[local-name()="p"]'
            t_xpath = './/*[local-name()="t"]'
        else:
            p_xpath = './/*[local-name()="p"]'
            t_xpath = './/*[local-name()="t"]'

        for node in container:
            key = ('textbox', idx)
            if key in translations:
                new_text = translations[key]
                print(f"[DEBUG] Applying translation to container {idx}: {new_text[:50]}...")
                # replace first paragraph text; clear others
                paragraphs = node.xpath(p_xpath)
                if paragraphs:
                    print(f"[DEBUG] Found {len(paragraphs)} paragraphs in container {idx}")
                    # set first paragraph to new_text
                    from docx.text.paragraph import Paragraph  # type: ignore
                    try:
                        p0 = Paragraph(paragraphs[0], None)
                        _set_paragraph_text(p0, new_text)
                        print(f"[DEBUG] Successfully applied translation to paragraph in container {idx}")
                    except Exception as e:
                        print(f"[DEBUG] Failed to apply via Paragraph, using fallback: {e}")
                        # fallback: set w:t texts
                        ts = paragraphs[0].xpath(t_xpath)
                        if ts:
                            ts[0].text = new_text
                            print(f"[DEBUG] Applied translation via fallback to {len(ts)} text elements")
                    # clear remaining paragraphs
                    for p in paragraphs[1:]:
                        for t in p.xpath(t_xpath):
                            t.text = ''
                else:
                    print(f"[DEBUG] No paragraphs found in container {idx}")
            else:
                print(f"[DEBUG] No translation found for key {key}")
            idx += 1
        return idx

    # Apply all elements with unified indexing (same logic as extraction)
    try:
        # 1) Apply SDTs - only apply to top-level SDTs to avoid duplication
        sdt_elems = doc._element.body.xpath('.//*[local-name()="sdt"]')
        sdt_index = 0
        for sdt in sdt_elems:
            # Check if this SDT is nested within another SDT
            parent_sdt = sdt.xpath('./ancestor::*[local-name()="sdt"]')
            if parent_sdt:
                print(f"[DEBUG] Skipping nested SDT in apply: {sdt_index}")
                continue
            
            # Apply sdtContent translations
            sdt_contents = sdt.xpath('.//*[local-name()="sdtContent"]')
            for i, content in enumerate(sdt_contents):
                key = ('sdt_content', sdt_index, i)
                if key in translations:
                    new_text = translations[key]
                    print(f"[DEBUG] Applying sdtContent translation {sdt_index}.{i}: {new_text[:50]}...")
                    # Apply to sdtContent
                    paragraphs = content.xpath('.//*[local-name()="p"]')
                    if paragraphs:
                        from docx.text.paragraph import Paragraph  # type: ignore
                        try:
                            # 处理第一个段落：设置新文本
                            p0 = Paragraph(paragraphs[0], None)
                            _set_paragraph_text(p0, new_text)
                            print(f"[DEBUG] Successfully applied sdtContent translation {sdt_index}.{i}")
                            
                            # 处理其他段落：完全清空内容
                            for p in paragraphs[1:]:
                                try:
                                    p_para = Paragraph(p, None)
                                    _set_paragraph_text(p_para, "")
                                except Exception as e:
                                    print(f"[DEBUG] Failed to clear paragraph via Paragraph, using fallback: {e}")
                                    # 直接清空所有文本元素
                                    for t in p.xpath('.//*[local-name()="t"]'):
                                        t.text = ''
                        except Exception as e:
                            print(f"[DEBUG] Failed to apply sdtContent via Paragraph, using fallback: {e}")
                            # 直接操作XML元素
                            if paragraphs:
                                ts = paragraphs[0].xpath('.//*[local-name()="t"]')
                                if ts:
                                    ts[0].text = new_text
                                # 清空其他段落
                                for p in paragraphs[1:]:
                                    for t in p.xpath('.//*[local-name()="t"]'):
                                        t.text = ''
            
            # Apply child SDT translations
            child_sdts = sdt.xpath('.//*[local-name()="sdt"]')
            for i, child_sdt in enumerate(child_sdts):
                key = ('sdt_child', sdt_index, i)
                if key in translations:
                    new_text = translations[key]
                    print(f"[DEBUG] Applying child SDT translation {sdt_index}.{i}: {new_text[:50]}...")
                    # Apply to child SDT
                    paragraphs = child_sdt.xpath('.//*[local-name()="p"]')
                    if paragraphs:
                        from docx.text.paragraph import Paragraph  # type: ignore
                        try:
                            # 处理第一个段落：设置新文本
                            p0 = Paragraph(paragraphs[0], None)
                            _set_paragraph_text(p0, new_text)
                            print(f"[DEBUG] Successfully applied child SDT translation {sdt_index}.{i}")
                            
                            # 处理其他段落：完全清空内容
                            for p in paragraphs[1:]:
                                try:
                                    p_para = Paragraph(p, None)
                                    _set_paragraph_text(p_para, "")
                                except Exception as e:
                                    print(f"[DEBUG] Failed to clear child SDT paragraph via Paragraph, using fallback: {e}")
                                    # 直接清空所有文本元素
                                    for t in p.xpath('.//*[local-name()="t"]'):
                                        t.text = ''
                        except Exception as e:
                            print(f"[DEBUG] Failed to apply child SDT via Paragraph, using fallback: {e}")
                            # 直接操作XML元素
                            if paragraphs:
                                ts = paragraphs[0].xpath('.//*[local-name()="t"]')
                                if ts:
                                    ts[0].text = new_text
                                # 清空其他段落
                                for p in paragraphs[1:]:
                                    for t in p.xpath('.//*[local-name()="t"]'):
                                        t.text = ''
            
            # Apply direct SDT content (if no sdtContent or child SDTs)
            if not sdt_contents and not child_sdts:
                key = ('sdt', sdt_index)
                if key in translations:
                    new_text = translations[key]
                    print(f"[DEBUG] Applying SDT translation {sdt_index}: {new_text[:50]}...")
                    # set all paragraphs: first gets text, others cleared
                    paragraphs = sdt.xpath('.//*[local-name()="p"]')
                    if paragraphs:
                        from docx.text.paragraph import Paragraph  # type: ignore
                        try:
                            p0 = Paragraph(paragraphs[0], None)
                            _set_paragraph_text(p0, new_text)
                            print(f"[DEBUG] Successfully applied SDT translation {sdt_index}")
                        except Exception as e:
                            print(f"[DEBUG] Failed to apply SDT via Paragraph, using fallback: {e}")
                            ts = paragraphs[0].xpath('.//*[local-name()="t"]')
                            if ts:
                                ts[0].text = new_text
                        for p in paragraphs[1:]:
                            for t in p.xpath('.//*[local-name()="t"]'):
                                t.text = ''
            
            sdt_index += 1
        
        # 2) Apply textboxes and drawing elements
        all_textbox_elements = []
        
        # Search for w:txbxContent nodes
        try:
            txbx_nodes = doc._element.xpath('.//*[local-name()="txbxContent"]')
            all_textbox_elements.extend(txbx_nodes)
        except Exception as e:
            print(f"[DEBUG] Error searching w:txbxContent: {e}")
        
        # Search for legacy v:textbox nodes
        try:
            pict_nodes = doc._element.xpath('.//*[local-name()="pict"]//*[local-name()="textbox"]')
            all_textbox_elements.extend(pict_nodes)
        except Exception as e:
            print(f"[DEBUG] Error searching v:textbox: {e}")
        
        # Search for drawing elements with text
        try:
            drawing_nodes = doc._element.xpath('.//*[local-name()="drawing"]')
            for drawing in drawing_nodes:
                text_elements = drawing.xpath('.//*[local-name()="t"]')
                if text_elements:
                    all_textbox_elements.append(drawing)
        except Exception as e:
            print(f"[DEBUG] Error searching w:drawing: {e}")
        
        print(f"[DEBUG] Found {len(all_textbox_elements)} total textbox/drawing elements for applying translations")
        
        # Process all elements with consistent indexing
        tb_index = 0
        for element in all_textbox_elements:
            key = ('textbox', tb_index)
            if key in translations:
                new_text = translations[key]
                print(f"[DEBUG] Applying translation to element {tb_index}: {new_text[:50]}...")
                
                if element.tag.endswith('txbxContent') or element.tag.endswith('textbox'):
                    # Handle textbox elements
                    tb_index = _apply_to_container([element], kind='drawing', start_index=tb_index)
                elif element.tag.endswith('drawing'):
                    # Handle drawing elements
                    text_elements = element.xpath('.//*[local-name()="t"]')
                    if text_elements:
                        print(f"[DEBUG] Found {len(text_elements)} text elements in drawing {tb_index}")
                        # Replace first text element, clear others
                        text_elements[0].text = new_text
                        for t_elem in text_elements[1:]:
                            t_elem.text = ''
                        tb_index += 1
                    else:
                        print(f"[DEBUG] No text elements found in drawing {tb_index}")
                        tb_index += 1
                else:
                    tb_index += 1
            else:
                print(f"[DEBUG] No translation found for key {key}")
                tb_index += 1
    except Exception as e:
        print(f"[DEBUG] Error applying elements: {e}")
        pass

    bio = BytesIO()
    doc.save(bio)
    return bio.getvalue()

