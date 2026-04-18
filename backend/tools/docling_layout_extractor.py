"""
Docling-based layout extraction tool.

Usage (from repo root, in venv):

    python -m backend.tools.docling_layout_extractor --pdf "test-doc/mineru_sample/c9097029-cced-46f0-b8e9-413728ea1f81_origin.pdf"

It will:
  - Open the given PDF with Docling
  - For each page, read page size (if available) and block bounding boxes with text
  - Dump a simple JSON layout structure similar to:

    {
      "engine": "docling",
      "pages": [
        {
          "page_index": 0,
          "width": 595.0,
          "height": 842.0,
          "blocks": [
            {"type": "text", "bbox": [x0, y0, x1, y1], "text": "..."}
          ]
        },
        ...
      ]
    }

This is a standalone inspection tool and does NOT affect the main workflow.

Note:
  Docling API evolves quickly; this script assumes a basic `Document` API
  (from the high-level examples). If your installed Docling version differs,
  you might need to adjust the imports or attribute names slightly.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Tuple


# Try multiple import strategies for different Docling versions
DocumentConverter = None
DlDocument = None
_import_errors = []
_docling_import_strategy = "unknown"

try:
    # Strategy 1: Docling v2.x - document_converter is a module, not a class
    # Check if document_converter module exists and find DocumentConverter class inside it
    import docling.document_converter as dc_module
    DocumentConverter = getattr(dc_module, "DocumentConverter", None)
    if DocumentConverter is None:
        raise ImportError("DocumentConverter not found in docling.document_converter module")
    
    # Try to find Document class in various places
    DlDocument = None
    try:
        from docling.datamodel import Document as DlDocument  # type: ignore[import]
    except ImportError:
        try:
            import docling.datamodel as dm
            DlDocument = getattr(dm, "Document", None)
        except ImportError:
            pass
    
    if DlDocument is None:
        # Document might not be needed for basic conversion, but log a warning
        print("Warning: Document class not found, but continuing...")
        DlDocument = type(None)  # Use NoneType as placeholder
    
    _docling_import_strategy = "docling.document_converter module + docling.datamodel"
except (ImportError, AttributeError) as e1:
    _import_errors.append(f"Strategy 1 (docling.document_converter module): {e1}")
    try:
        # Strategy 2: Try direct imports from docling
        import docling
        DocumentConverter = getattr(docling.document_converter, "DocumentConverter", None) if hasattr(docling, "document_converter") else None
        DlDocument = getattr(docling.datamodel, "Document", None) if hasattr(docling, "datamodel") else None
        
        if DocumentConverter is None or DlDocument is None:
            raise ImportError("DocumentConverter or Document not found")
        _docling_import_strategy = "docling (module attributes)"
    except (ImportError, AttributeError) as e2:
        _import_errors.append(f"Strategy 2 (docling module attributes): {e2}")
        # Print helpful debug info
        try:
            import docling
            print("Debug: docling module found. Available attributes:")
            attrs = [a for a in dir(docling) if not a.startswith("_")]
            print(f"  {', '.join(attrs[:20])}")  # Show first 20
            if hasattr(docling, "__version__"):
                print(f"  Version: {docling.__version__}")
            # Check document_converter module
            if hasattr(docling, "document_converter"):
                print(f"  document_converter module attributes: {[a for a in dir(docling.document_converter) if not a.startswith('_')][:20]}")
            # Check datamodel module
            if hasattr(docling, "datamodel"):
                print(f"  datamodel module attributes: {[a for a in dir(docling.datamodel) if not a.startswith('_')][:20]}")
        except ImportError:
            pass
        raise SystemExit(
            f"Failed to import Docling components after trying {len(_import_errors)} strategies:\n"
            + "\n".join(f"  {i+1}. {err}" for i, err in enumerate(_import_errors))
            + f"\n\nPlease check your Docling installation:\n"
            f"  pip show docling\n"
            f"  pip show docling-core\n"
            f"\nIf needed, reinstall:\n"
            f"  pip install -U docling docling-core"
        ) from e2


@dataclass
class DoclingBlock:
    page_index: int
    bbox: Tuple[float, float, float, float] | None
    type: str
    text: str | None


def _extract_layout_with_docling(pdf_path: Path) -> Dict[str, Any]:
    """Extract a simple layout representation from a PDF using Docling."""
    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")

    # Use DocumentConverter to parse the PDF into a Docling Document
    try:
        converter = DocumentConverter()
        # convert() returns a document object (type may vary by Docling version)
        dl_doc = converter.convert(str(pdf_path))  # type: ignore[call-arg]
    except Exception as e:
        raise RuntimeError(
            f"Failed to convert PDF with Docling: {e}. "
            "Make sure Docling is properly installed and the PDF file is valid."
        ) from e

    pages: List[Dict[str, Any]] = []

    # The exact API depends on Docling version; the following assumes:
    #   dl_doc.pages -> iterable of page objects
    #   page.width / page.height or page.bbox to get size
    #   page.blocks or page.elements -> iterable of block-like objects with bbox/text/type
    
    # Try to get pages attribute
    doc_pages = getattr(dl_doc, "pages", None)
    if doc_pages is None:
        # Some versions might use different attribute names
        doc_pages = getattr(dl_doc, "page", None)
        if doc_pages is None:
            # Try to iterate directly if it's iterable
            try:
                doc_pages = list(dl_doc) if hasattr(dl_doc, "__iter__") else []
            except (TypeError, AttributeError):
                doc_pages = []
    
    if not doc_pages:
        print("Warning: No pages found in Docling document. Document structure:")
        print(f"  Document type: {type(dl_doc)}")
        print(f"  Document attributes: {dir(dl_doc)}")
        return {
            "engine": "docling",
            "source": str(pdf_path),
            "page_count": 0,
            "pages": [],
            "error": "No pages found in document",
        }
    
    for page_index, page in enumerate(doc_pages):
        # Fallbacks for size: try width/height first, then bbox
        page_width = None
        page_height = None

        if hasattr(page, "width") and hasattr(page, "height"):
            try:
                page_width = float(page.width)
                page_height = float(page.height)
            except (TypeError, ValueError):
                page_width = None
                page_height = None

        if (page_width is None or page_height is None) and hasattr(page, "bbox"):
            # bbox may be (x0, y0, x1, y1)
            bbox = getattr(page, "bbox")
            if isinstance(bbox, (list, tuple)) and len(bbox) == 4:
                try:
                    x0, y0, x1, y1 = map(float, bbox)
                    page_width = x1 - x0
                    page_height = y1 - y0
                except (TypeError, ValueError):
                    pass

        blocks: List[DoclingBlock] = []

        page_blocks = getattr(page, "blocks", None)
        if page_blocks is None:
            # Some Docling versions might use different names; try `elements`
            page_blocks = getattr(page, "elements", None)
            if page_blocks is None:
                # Try other common attribute names
                page_blocks = getattr(page, "content", None)
                if page_blocks is None:
                    page_blocks = []
        
        # Ensure page_blocks is iterable
        if page_blocks is None:
            page_blocks = []
        elif not hasattr(page_blocks, "__iter__"):
            page_blocks = [page_blocks]

        for block in page_blocks:
            # Try to get bbox
            bbox = getattr(block, "bbox", None)
            bbox_tuple: Tuple[float, float, float, float] | None = None
            if isinstance(bbox, (list, tuple)) and len(bbox) == 4:
                try:
                    x0, y0, x1, y1 = map(float, bbox)
                    bbox_tuple = (x0, y0, x1, y1)
                except (TypeError, ValueError):
                    bbox_tuple = None

            # Try to get text
            text = getattr(block, "text", None)
            if text is not None:
                text = str(text)

            # Try to get type; fall back to class name
            btype = getattr(block, "type", None)
            if btype is None:
                btype = block.__class__.__name__
            else:
                btype = str(btype)

            blocks.append(
                DoclingBlock(
                    page_index=page_index,
                    bbox=bbox_tuple,
                    type=btype,
                    text=text,
                )
            )

        page_entry: Dict[str, Any] = {
            "page_index": page_index,
            "width": page_width,
            "height": page_height,
            "blocks": [],
        }

        for b in blocks:
            entry: Dict[str, Any] = {
                "type": b.type,
            }
            if b.bbox is not None:
                entry["bbox"] = list(b.bbox)
            if b.text is not None:
                entry["text"] = b.text
            page_entry["blocks"].append(entry)

        pages.append(page_entry)

    return {
        "engine": "docling",
        "source": str(pdf_path),
        "page_count": len(pages),
        "pages": pages,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Extract a simple layout JSON from PDF using Docling."
    )
    parser.add_argument(
        "--pdf",
        type=str,
        required=True,
        help="Path to source PDF file.",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Optional output JSON path. If not set, will print to stdout and also create <stem>_docling_layout.json next to the PDF.",
    )
    parser.add_argument(
        "--debug-imports",
        action="store_true",
        help="Debug mode: show Docling import information and exit.",
    )
    args = parser.parse_args()
    
    # Debug mode: show import info
    if args.debug_imports:
        print("Docling Import Debug Information:")
        print(f"  Import strategy used: {_docling_import_strategy}")
        print(f"  DocumentConverter: {DocumentConverter}")
        print(f"  DlDocument: {DlDocument}")
        try:
            import docling
            print(f"  docling module: {docling}")
            print(f"  docling attributes: {[a for a in dir(docling) if not a.startswith('_')][:20]}")
            if hasattr(docling, "__version__"):
                print(f"  docling version: {docling.__version__}")
        except ImportError as e:
            print(f"  docling module not importable: {e}")
        try:
            import docling_core
            print(f"  docling_core module: {docling_core}")
            print(f"  docling_core attributes: {[a for a in dir(docling_core) if not a.startswith('_')][:20]}")
        except ImportError as e:
            print(f"  docling_core module not importable: {e}")
        return

    pdf_path = Path(args.pdf)
    try:
        layout = _extract_layout_with_docling(pdf_path)
    except Exception as e:
        print(f"Error extracting layout: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)

    # Decide output path
    output_path: Path | None = None
    if args.output:
        output_path = Path(args.output)
    else:
        output_path = pdf_path.with_name(pdf_path.stem + "_docling_layout.json")

    # Write JSON to file
    if output_path is not None:
        output_path.write_text(
            json.dumps(layout, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(f"Docling layout JSON written to: {output_path}")

    # Also print a short summary to stdout
    print(json.dumps(layout, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()


