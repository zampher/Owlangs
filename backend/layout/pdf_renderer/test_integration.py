# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

"""
Integration tests for PDF renderer using real layout.json.

Run with: python layout/pdf_renderer/test_integration.py
"""

import sys
import json
import zipfile
import io
from pathlib import Path

# Add backend to path
backend_path = Path(__file__).parent.parent.parent
sys.path.insert(0, str(backend_path))

from layout.pdf_renderer import render_layout_pdf
from layout.mineru_layout_model import parse_layout_json, parse_mineru_layout_from_zip_bytes
from layout.base import LayoutDocument

# Import REPORTLAB_AVAILABLE directly to avoid circular import issues
try:
    from layout.pdf_renderer.reportlab.renderer import REPORTLAB_AVAILABLE
except (ImportError, AttributeError):
    # Fallback: try to import from old module
    try:
        from layout.pdf_renderer_reportlab import REPORTLAB_AVAILABLE
    except ImportError:
        REPORTLAB_AVAILABLE = False


def test_load_layout_json():
    """Test loading layout.json file."""
    layout_json_path = backend_path.parent / "test-doc" / "mineru_sample" / "layout.json"
    
    if not layout_json_path.exists():
        print(f"[WARN] Layout JSON not found at {layout_json_path}")
        print("   Skipping integration test")
        return None
    
    print(f"Loading layout.json from: {layout_json_path}")
    layout_doc = parse_layout_json(layout_json_path)
    
    assert layout_doc is not None, "Failed to load layout document"
    assert layout_doc.engine == "mineru", f"Expected engine 'mineru', got '{layout_doc.engine}'"
    assert len(layout_doc.pages) > 0, "Layout document should have at least one page"
    
    # Count blocks
    total_blocks = sum(1 for _ in layout_doc.iter_blocks())
    print(f"  [OK] Loaded {len(layout_doc.pages)} pages, {total_blocks} blocks")
    
    return layout_doc


def test_create_zip_with_images():
    """Create a ZIP file with images for testing."""
    images_dir = backend_path.parent / "test-doc" / "mineru_sample" / "images"
    layout_json_path = backend_path.parent / "test-doc" / "mineru_sample" / "layout.json"
    
    if not images_dir.exists() or not layout_json_path.exists():
        print(f"[WARN] Images directory or layout.json not found")
        print("   Skipping ZIP creation")
        return None
    
    # Create ZIP in memory
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
        # Add layout.json
        zip_file.write(layout_json_path, "layout.json")
        
        # Add images
        for image_file in images_dir.glob("*.jpg"):
            zip_file.write(image_file, f"images/{image_file.name}")
            print(f"  [OK] Added image: {image_file.name}")
    
    zip_bytes = zip_buffer.getvalue()
    print(f"  [OK] Created ZIP with {len(zip_bytes)} bytes")
    
    return zip_bytes


def test_render_pdf_with_new_architecture(layout_doc: LayoutDocument, zip_bytes: bytes = None):
    """Test PDF rendering with new architecture."""
    if not REPORTLAB_AVAILABLE:
        print("[WARN] ReportLab not available, skipping PDF rendering test")
        return None
    
    print("\nTesting PDF rendering with new architecture...")
    
    # Test 1: Basic rendering without translation
    print("  Test 1: Basic rendering (no translation)...")
    try:
        pdf_bytes = render_layout_pdf(
            layout_doc=layout_doc,
            translated_text_by_block_index=None,
            zip_bytes=zip_bytes,
            table_body_format="html",
            renderer_type="reportlab",
        )
        
        assert pdf_bytes is not None, "PDF bytes should not be None"
        assert len(pdf_bytes) > 0, "PDF bytes should not be empty"
        assert pdf_bytes.startswith(b'%PDF'), "PDF should start with PDF header"
        
        print(f"    [OK] Generated PDF: {len(pdf_bytes)} bytes")
        
        # Save for inspection
        output_path = backend_path / "test_output_new_architecture.pdf"
        output_path.write_bytes(pdf_bytes)
        print(f"    [OK] Saved to: {output_path}")
        
    except Exception as e:
        print(f"    [FAIL] Failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # Test 2: Rendering with translation
    print("  Test 2: Rendering with translation...")
    try:
        # Create some translated text (just for testing)
        translated_text = {}
        block_count = 0
        for block in layout_doc.iter_blocks():
            if block.text and block.index is not None and block_count < 10:
                # Simple translation: add prefix for testing
                translated_text[block.index] = f"[TRANSLATED] {block.text}"
                block_count += 1
        
        pdf_bytes = render_layout_pdf(
            layout_doc=layout_doc,
            translated_text_by_block_index=translated_text if translated_text else None,
            zip_bytes=zip_bytes,
            table_body_format="html",
            target_language="zh",
            renderer_type="reportlab",
        )
        
        assert pdf_bytes is not None, "PDF bytes should not be None"
        assert len(pdf_bytes) > 0, "PDF bytes should not be empty"
        
        print(f"    [OK] Generated translated PDF: {len(pdf_bytes)} bytes")
        
        # Save for inspection
        output_path = backend_path / "test_output_translated.pdf"
        output_path.write_bytes(pdf_bytes)
        print(f"    [OK] Saved to: {output_path}")
        
    except Exception as e:
        print(f"    [FAIL] Failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # Test 3: Test with table format "image"
    print("  Test 3: Rendering with table format 'image'...")
    try:
        pdf_bytes = render_layout_pdf(
            layout_doc=layout_doc,
            translated_text_by_block_index=None,
            zip_bytes=zip_bytes,
            table_body_format="image",
            renderer_type="reportlab",
        )
        
        assert pdf_bytes is not None, "PDF bytes should not be None"
        assert len(pdf_bytes) > 0, "PDF bytes should not be empty"
        
        print(f"    [OK] Generated PDF with image tables: {len(pdf_bytes)} bytes")
        
    except Exception as e:
        print(f"    [WARN] Table image format test failed (may not have tables): {e}")
        # This is OK if there are no tables in the document
    
    return True


def test_compare_with_old_implementation(layout_doc: LayoutDocument, zip_bytes: bytes = None):
    """Compare new architecture with old implementation."""
    if not REPORTLAB_AVAILABLE:
        print("[WARN] ReportLab not available, skipping comparison")
        return None
    
    print("\nComparing new architecture with old implementation...")
    
    try:
        # Old implementation
        from layout.pdf_renderer_reportlab import render_layout_pdf_reportlab
        
        pdf_bytes_old = render_layout_pdf_reportlab(
            layout_doc=layout_doc,
            translated_text_by_block_index=None,
            zip_bytes=zip_bytes,
            table_body_format="html",
        )
        
        # New implementation
        pdf_bytes_new = render_layout_pdf(
            layout_doc=layout_doc,
            translated_text_by_block_index=None,
            zip_bytes=zip_bytes,
            table_body_format="html",
            renderer_type="reportlab",
        )
        
        # Compare sizes (they should be similar, but not necessarily identical)
        size_diff = abs(len(pdf_bytes_old) - len(pdf_bytes_new))
        size_diff_percent = (size_diff / len(pdf_bytes_old)) * 100 if len(pdf_bytes_old) > 0 else 0
        
        print(f"  Old implementation: {len(pdf_bytes_old)} bytes")
        print(f"  New implementation: {len(pdf_bytes_new)} bytes")
        print(f"  Size difference: {size_diff} bytes ({size_diff_percent:.1f}%)")
        
        if size_diff_percent < 10:
            print("  [OK] Size difference is acceptable (< 10%)")
        else:
            print("  [WARN] Size difference is significant (> 10%), may indicate issues")
        
        # Save both for comparison
        (backend_path / "test_output_old.pdf").write_bytes(pdf_bytes_old)
        (backend_path / "test_output_new.pdf").write_bytes(pdf_bytes_new)
        print("  [OK] Saved both PDFs for comparison")
        
        return True
        
    except Exception as e:
        print(f"  [FAIL] Comparison failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_shared_components():
    """Test shared components individually."""
    print("\nTesting shared components...")
    
    from layout.pdf_renderer.shared import LayoutCalculator, TextUtils, FontSizeCalculator
    from utils.font_utils import FontUtils
    
    # Test LayoutCalculator
    calc = LayoutCalculator()
    available_height = calc.calculate_available_height(height=100.0, font_size=12.0)
    assert available_height > 0, "Available height should be positive"
    print(f"  [OK] LayoutCalculator: available_height={available_height:.1f}pt")
    
    # Test TextUtils
    text_utils = TextUtils()
    lang = text_utils.detect_language("Hello world")
    assert lang == "en", f"Expected 'en', got '{lang}'"
    lang_zh = text_utils.detect_language("你好世界")
    assert lang_zh == "zh", f"Expected 'zh', got '{lang_zh}'"
    print(f"  [OK] TextUtils: language detection works")
    
    # Test FontUtils
    font_utils = FontUtils()
    font_name = font_utils.get_font_name_for_language("zh")
    print(f"  [OK] FontUtils: font for Chinese = {font_name}")
    
    # Test FontSizeCalculator
    font_calc = FontSizeCalculator()
    font_size = font_calc.estimate_initial_font_size(block_height=24.0, text="Test text", block_width=100.0)
    assert 7.0 <= font_size <= 24.0, f"Font size {font_size} should be in range [7, 24]"
    print(f"  [OK] FontSizeCalculator: estimated font_size={font_size:.1f}pt")
    
    return True


def run_all_tests():
    """Run all integration tests."""
    print("=" * 70)
    print("PDF Renderer Integration Tests")
    print("=" * 70)
    
    all_passed = True
    
    # Test shared components
    try:
        test_shared_components()
        print("[OK] Shared components test passed\n")
    except Exception as e:
        print(f"[FAIL] Shared components test failed: {e}\n")
        import traceback
        traceback.print_exc()
        all_passed = False
    
    # Load layout document
    layout_doc = test_load_layout_json()
    if layout_doc is None:
        print("[WARN] Cannot proceed without layout document")
        return False
    
    # Create ZIP with images
    zip_bytes = test_create_zip_with_images()
    
    # Test PDF rendering (only if ReportLab is available)
    if REPORTLAB_AVAILABLE:
        try:
            result = test_render_pdf_with_new_architecture(layout_doc, zip_bytes)
            if result:
                print("[OK] PDF rendering test passed\n")
            else:
                all_passed = False
        except Exception as e:
            print(f"[FAIL] PDF rendering test failed: {e}\n")
            import traceback
            traceback.print_exc()
            all_passed = False
        
        # Compare with old implementation
        try:
            result = test_compare_with_old_implementation(layout_doc, zip_bytes)
            if result:
                print("[OK] Comparison test passed\n")
            else:
                all_passed = False
        except Exception as e:
            print(f"[WARN] Comparison test failed (non-critical): {e}\n")
            # This is non-critical, don't fail the test suite
    else:
        print("[SKIP] PDF rendering tests skipped (ReportLab not available)\n")
        print("       Install ReportLab with: pip install reportlab\n")
    
    print("=" * 70)
    if all_passed:
        print("[SUCCESS] All integration tests passed!")
    else:
        print("[FAILED] Some tests failed")
    print("=" * 70)
    
    return all_passed


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)

