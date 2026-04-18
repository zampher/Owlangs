# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

"""
Unit tests for base PDF renderer classes.

Run with: python layout/pdf_renderer/test_base.py
"""

import sys
from pathlib import Path

# Add backend to path
backend_path = Path(__file__).parent.parent.parent
sys.path.insert(0, str(backend_path))

from layout.pdf_renderer.config import PDFRendererConfig
from layout.pdf_renderer.base import BasePDFRenderer
from layout.base import LayoutDocument, LayoutPage, LayoutBlock


def test_pdf_renderer_config():
    """Test PDFRendererConfig initialization."""
    config = PDFRendererConfig(
        translated_text_by_block_index={1: "Translated text"},
        table_body_format="html",
        target_language="zh"
    )
    
    assert config.translated_text_by_block_index == {1: "Translated text"}
    assert config.table_body_format == "html"
    assert config.target_language == "zh"
    assert config.type_font_baselines == {}
    assert config.image_data_map == {}
    
    print("✓ test_pdf_renderer_config passed")


def test_base_pdf_renderer_abstract():
    """Test that BasePDFRenderer is abstract and cannot be instantiated."""
    try:
        config = PDFRendererConfig()
        # This should fail because BasePDFRenderer is abstract
        renderer = BasePDFRenderer(config)
        assert False, "BasePDFRenderer should not be instantiable"
    except TypeError:
        # Expected: cannot instantiate abstract class
        print("✓ test_base_pdf_renderer_abstract passed")


def test_base_pdf_renderer_subclass():
    """Test that a concrete subclass can be created."""
    class TestPDFRenderer(BasePDFRenderer):
        def render(self, layout_doc):
            return b"test pdf bytes"
    
    config = PDFRendererConfig()
    renderer = TestPDFRenderer(config)
    
    # Check that shared components are initialized
    assert renderer.layout_calc is not None
    assert renderer.font_calc is not None
    assert renderer.text_utils is not None
    assert renderer.font_utils is not None
    
    # Test render method
    layout_doc = LayoutDocument(engine="test", pages=[])
    pdf_bytes = renderer.render(layout_doc)
    assert pdf_bytes == b"test pdf bytes"
    
    print("✓ test_base_pdf_renderer_subclass passed")


def run_all_tests():
    """Run all tests."""
    print("Running base PDF renderer unit tests...\n")
    
    try:
        test_pdf_renderer_config()
        test_base_pdf_renderer_abstract()
        test_base_pdf_renderer_subclass()
        
        print("\n✅ All tests passed!")
        return True
    except AssertionError as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)

