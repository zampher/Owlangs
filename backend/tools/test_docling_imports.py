"""Quick test script to check Docling API structure."""
import sys

print("Testing Docling imports...")

# Test 1: Check docling module
try:
    import docling
    print(f"✓ docling module imported")
    print(f"  Attributes: {[a for a in dir(docling) if not a.startswith('_')]}")
except ImportError as e:
    print(f"✗ Failed to import docling: {e}")
    sys.exit(1)

# Test 2: Check document_converter module
try:
    import docling.document_converter as dc
    print(f"✓ docling.document_converter module imported")
    print(f"  Attributes: {[a for a in dir(dc) if not a.startswith('_')]}")
    DocumentConverter = getattr(dc, "DocumentConverter", None)
    if DocumentConverter:
        print(f"  ✓ Found DocumentConverter: {DocumentConverter}")
    else:
        print(f"  ✗ DocumentConverter not found")
except ImportError as e:
    print(f"✗ Failed to import docling.document_converter: {e}")

# Test 3: Check datamodel module
try:
    import docling.datamodel as dm
    print(f"✓ docling.datamodel module imported")
    print(f"  Attributes: {[a for a in dir(dm) if not a.startswith('_')][:20]}")
    Document = getattr(dm, "Document", None)
    if Document:
        print(f"  ✓ Found Document: {Document}")
    else:
        print(f"  ✗ Document not found")
except ImportError as e:
    print(f"✗ Failed to import docling.datamodel: {e}")

# Test 4: Check docling_core
try:
    import docling_core
    print(f"✓ docling_core module imported")
    print(f"  Attributes: {[a for a in dir(docling_core) if not a.startswith('_')][:20]}")
except ImportError as e:
    print(f"✗ Failed to import docling_core: {e}")

# Test 5: Try to create DocumentConverter instance
try:
    import docling.document_converter as dc
    DocumentConverter = getattr(dc, "DocumentConverter", None)
    if DocumentConverter:
        converter = DocumentConverter()
        print(f"✓ Successfully created DocumentConverter instance: {converter}")
    else:
        print(f"✗ Cannot create DocumentConverter - class not found")
except Exception as e:
    print(f"✗ Failed to create DocumentConverter: {e}")

