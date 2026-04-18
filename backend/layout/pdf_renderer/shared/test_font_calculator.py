# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

"""
Unit tests for FontSizeCalculator.

Run with: python -m pytest layout/pdf_renderer/shared/test_font_calculator.py
Or: python layout/pdf_renderer/shared/test_font_calculator.py
"""

import sys
from pathlib import Path

# Add backend to path
backend_path = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(backend_path))

from layout.pdf_renderer.shared.font_calculator import FontSizeCalculator


def test_estimate_initial_font_size():
    """Test initial font size estimation."""
    calc = FontSizeCalculator()
    
    # Test single line block
    font_size = calc.estimate_initial_font_size(
        block_height=12.0,
        text="Single line text",
        block_width=100.0
    )
    assert 7.0 <= font_size <= 24.0, f"Font size {font_size} should be in range [7, 24]"
    assert font_size >= 11.0, f"Single line should have font size >= 11pt, got {font_size}"
    
    # Test multi-line block
    font_size = calc.estimate_initial_font_size(
        block_height=36.0,
        text="Line 1\nLine 2\nLine 3",
        block_width=100.0
    )
    assert 7.0 <= font_size <= 24.0, f"Font size {font_size} should be in range [7, 24]"
    # For 3 lines with height 36pt, font size should be around (36/3)*0.92 = 11.04pt
    # But if text wrapping is estimated differently, it could be higher
    # So we just check it's reasonable (between 7 and 20pt for this case)
    assert 7.0 <= font_size <= 20.0, f"Multi-line font size should be reasonable, got {font_size}"
    
    # Test with block_raw (layout lines)
    block_raw = {"lines": [{"spans": [{"content": "Line 1"}]}, {"spans": [{"content": "Line 2"}]}]}
    font_size = calc.estimate_initial_font_size(
        block_height=24.0,
        text="Line 1\nLine 2",
        block_width=100.0,
        block_raw=block_raw
    )
    assert 7.0 <= font_size <= 24.0, f"Font size {font_size} should be in range [7, 24]"
    
    # Test edge case: zero height
    font_size = calc.estimate_initial_font_size(block_height=0.0)
    assert font_size == 12.0, f"Zero height should return default 12pt, got {font_size}"
    
    print("✓ test_estimate_initial_font_size passed")


def test_quantize_font_size():
    """Test font size quantization."""
    calc = FontSizeCalculator()
    
    # Test normal values
    assert calc.quantize_font_size(7.4) == 7.0, "7.4 should quantize to 7"
    assert calc.quantize_font_size(7.6) == 8.0, "7.6 should quantize to 8"
    assert calc.quantize_font_size(12.3) == 12.0, "12.3 should quantize to 12"
    assert calc.quantize_font_size(12.7) == 13.0, "12.7 should quantize to 13"
    
    # Test clamping
    assert calc.quantize_font_size(3.0) == 5.0, "3.0 should clamp to 5.0"
    assert calc.quantize_font_size(30.0) == 24.0, "30.0 should clamp to 24.0"
    
    # Test edge cases
    assert calc.quantize_font_size(5.0) == 5.0, "5.0 should stay 5.0"
    assert calc.quantize_font_size(24.0) == 24.0, "24.0 should stay 24.0"
    
    print("✓ test_quantize_font_size passed")


def test_estimate_line_count_from_font_size():
    """Test line count estimation."""
    calc = FontSizeCalculator()
    
    # Test with explicit newlines
    line_count = calc.estimate_line_count_from_font_size(
        text="Line 1\nLine 2\nLine 3",
        font_size=12.0,
        block_width=100.0
    )
    assert line_count == 3, f"Should detect 3 explicit lines, got {line_count}"
    
    # Test with block_raw (layout lines)
    block_raw = {"lines": [{"spans": [{"content": "Line 1"}]}, {"spans": [{"content": "Line 2"}]}]}
    line_count = calc.estimate_line_count_from_font_size(
        text="Line 1 Line 2",
        font_size=12.0,
        block_width=100.0,
        block_raw=block_raw
    )
    assert line_count == 2, f"Should use layout lines (2), got {line_count}"
    
    # Test empty text
    line_count = calc.estimate_line_count_from_font_size(
        text="",
        font_size=12.0,
        block_width=100.0
    )
    assert line_count == 1, f"Empty text should return 1 line, got {line_count}"
    
    print("✓ test_estimate_line_count_from_font_size passed")


def test_calculate_block_height_from_font_size():
    """Test block height calculation from font size."""
    calc = FontSizeCalculator()
    
    # Test single line
    height = calc.calculate_block_height_from_font_size(font_size=12.0, line_count=1)
    assert height == 12.0 * 1.1, f"Single line height should be font_size * 1.1, got {height}"
    
    # Test multiple lines
    height = calc.calculate_block_height_from_font_size(font_size=12.0, line_count=3)
    expected = 12.0 * 0.75 + (3 - 1) * 12.0 * 1.2 + 12.0 * 0.25
    assert abs(height - expected) < 0.1, f"Multi-line height should be ~{expected}, got {height}"
    
    # Test zero lines
    height = calc.calculate_block_height_from_font_size(font_size=12.0, line_count=0)
    assert height == 12.0, f"Zero lines should return font_size, got {height}"
    
    print("✓ test_calculate_block_height_from_font_size passed")


def test_get_font_size_from_type_baseline():
    """Test getting font size from type baseline."""
    baselines = {"text": 12.0, "title": 14.0, "ref_text": 10.0}
    calc = FontSizeCalculator(type_font_baselines=baselines)
    
    assert calc.get_font_size_from_type_baseline("text") == 12.0
    assert calc.get_font_size_from_type_baseline("title") == 14.0
    assert calc.get_font_size_from_type_baseline("ref_text") == 10.0
    assert calc.get_font_size_from_type_baseline("unknown") is None
    
    print("✓ test_get_font_size_from_type_baseline passed")


def run_all_tests():
    """Run all tests."""
    print("Running FontSizeCalculator unit tests...\n")
    
    try:
        test_estimate_initial_font_size()
        test_quantize_font_size()
        test_estimate_line_count_from_font_size()
        test_calculate_block_height_from_font_size()
        test_get_font_size_from_type_baseline()
        
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

