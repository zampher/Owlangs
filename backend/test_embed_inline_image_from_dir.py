#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

"""
Test script to verify the embed_inline_image_from_dir function.
"""

import io
import os
import sys
import tempfile
import zipfile
from pathlib import Path
import base64

# Add the backend directory to Python path
sys.path.append(str(Path(__file__).parent))

from utils.markdown_utils import embed_inline_image_from_dir, embed_inline_image_from_zip

def create_test_files():
    """Create test files for testing."""
    # Create a temporary directory
    temp_dir = tempfile.mkdtemp()
    
    # Create an images directory
    images_dir = os.path.join(temp_dir, "images")
    os.makedirs(images_dir, exist_ok=True)
    
    # Create a test image file
    image_path = os.path.join(images_dir, "test_image.png")
    # Create a simple red square image
    red_square = b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\xf3\xffa\x00\x00\x00\tpHYs\x00\x00\x0b\x13\x00\x00\x0b\x13\x01\x00\x9a\x9c\x18\x00\x00\x00\x07tIME\x07\xe8\x0c\x16\x0b\x1e0\xf2\x97\x90n\x00\x00\x00\rIDAT\x08\xd7c\x90\x00\x00\x00\x02\x00\x01\xe2!\xfa\xd0\x00\x00\x00\x00IEND\xaeB`\x82'
    with open(image_path, 'wb') as f:
        f.write(red_square)
    
    # Create a test Markdown file
    md_content = """# Test Document

This is a test document with an image:

![Test Image](images/test_image.png)

"""
    md_path = os.path.join(temp_dir, "full.md")
    with open(md_path, 'w', encoding='utf-8') as f:
        f.write(md_content)
    
    # Create a ZIP file for comparison
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, 'w') as zip_file:
        zip_file.writestr("full.md", md_content)
        zip_file.writestr("images/test_image.png", red_square)
    zip_buffer.seek(0)
    
    return temp_dir, zip_buffer.getvalue()

def test_embed_inline_image_from_dir():
    """Test the embed_inline_image_from_dir function."""
    print("=== Testing embed_inline_image_from_dir ===")
    
    try:
        # Create test files
        temp_dir, zip_bytes = create_test_files()
        print(f"Created test files in: {temp_dir}")
        
        # Test the new function
        print("\n1. Testing embed_inline_image_from_dir:")
        md_content_from_dir = embed_inline_image_from_dir(temp_dir, "full.md")
        print(f"   Successfully processed Markdown from directory")
        print(f"   Result: {md_content_from_dir[:100]}...")
        
        # Test the original function for comparison
        print("\n2. Testing embed_inline_image_from_zip (for comparison):")
        md_content_from_zip = embed_inline_image_from_zip(zip_bytes, "full.md")
        print(f"   Successfully processed Markdown from ZIP")
        print(f"   Result: {md_content_from_zip[:100]}...")
        
        # Verify both functions produce the same result
        print("\n3. Comparing results:")
        if md_content_from_dir == md_content_from_zip:
            print("   ✅ SUCCESS: Both functions produce identical results!")
        else:
            print("   ❌ FAILURE: Results are different!")
            print(f"   From dir: {repr(md_content_from_dir)}")
            print(f"   From zip: {repr(md_content_from_zip)}")
        
        # Clean up
        import shutil
        shutil.rmtree(temp_dir)
        print(f"\nCleaned up test directory: {temp_dir}")
        
        return md_content_from_dir == md_content_from_zip
        
    except Exception as e:
        print(f"\n❌ Error during testing: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_embed_inline_image_from_dir()
    sys.exit(0 if success else 1)