#!/usr/bin/env python3
"""
Copy and convert macOS icons to other platforms (Web, Windows, Android, iOS, Linux).

This script uses the macOS AppIcon.appiconset icons as the source and generates
icons for all other platforms with appropriate sizes.

Usage:
    python tools/copy_icons_from_macos.py
"""

import os
import sys
from pathlib import Path
from PIL import Image

# Get the frontend directory
FRONTEND_DIR = Path(__file__).parent.parent
MACOS_ICON_DIR = FRONTEND_DIR / "macos" / "Runner" / "Assets.xcassets" / "AppIcon.appiconset"

# Source icon (use the largest available)
SOURCE_ICON = MACOS_ICON_DIR / "app_icon_1024.png"
if not SOURCE_ICON.exists():
    # Fallback to 512 if 1024 doesn't exist
    SOURCE_ICON = MACOS_ICON_DIR / "app_icon_512.png"
if not SOURCE_ICON.exists():
    # Fallback to 256
    SOURCE_ICON = MACOS_ICON_DIR / "app_icon_256.png"

# Platform icon mappings: (target_path, size)
WEB_ICONS = [
    (FRONTEND_DIR / "web" / "icons" / "Icon-192.png", 192),
    (FRONTEND_DIR / "web" / "icons" / "Icon-512.png", 512),
    (FRONTEND_DIR / "web" / "icons" / "Icon-maskable-192.png", 192),
    (FRONTEND_DIR / "web" / "icons" / "Icon-maskable-512.png", 512),
]

ANDROID_ICONS = [
    (FRONTEND_DIR / "android" / "app" / "src" / "main" / "res" / "mipmap-mdpi" / "ic_launcher.png", 48),
    (FRONTEND_DIR / "android" / "app" / "src" / "main" / "res" / "mipmap-hdpi" / "ic_launcher.png", 72),
    (FRONTEND_DIR / "android" / "app" / "src" / "main" / "res" / "mipmap-xhdpi" / "ic_launcher.png", 96),
    (FRONTEND_DIR / "android" / "app" / "src" / "main" / "res" / "mipmap-xxhdpi" / "ic_launcher.png", 144),
    (FRONTEND_DIR / "android" / "app" / "src" / "main" / "res" / "mipmap-xxxhdpi" / "ic_launcher.png", 192),
]

IOS_ICONS = [
    (FRONTEND_DIR / "ios" / "Runner" / "Assets.xcassets" / "AppIcon.appiconset" / "Icon-App-20x20@1x.png", 20),
    (FRONTEND_DIR / "ios" / "Runner" / "Assets.xcassets" / "AppIcon.appiconset" / "Icon-App-20x20@2x.png", 40),
    (FRONTEND_DIR / "ios" / "Runner" / "Assets.xcassets" / "AppIcon.appiconset" / "Icon-App-20x20@3x.png", 60),
    (FRONTEND_DIR / "ios" / "Runner" / "Assets.xcassets" / "AppIcon.appiconset" / "Icon-App-29x29@1x.png", 29),
    (FRONTEND_DIR / "ios" / "Runner" / "Assets.xcassets" / "AppIcon.appiconset" / "Icon-App-29x29@2x.png", 58),
    (FRONTEND_DIR / "ios" / "Runner" / "Assets.xcassets" / "AppIcon.appiconset" / "Icon-App-29x29@3x.png", 87),
    (FRONTEND_DIR / "ios" / "Runner" / "Assets.xcassets" / "AppIcon.appiconset" / "Icon-App-40x40@1x.png", 40),
    (FRONTEND_DIR / "ios" / "Runner" / "Assets.xcassets" / "AppIcon.appiconset" / "Icon-App-40x40@2x.png", 80),
    (FRONTEND_DIR / "ios" / "Runner" / "Assets.xcassets" / "AppIcon.appiconset" / "Icon-App-40x40@3x.png", 120),
    (FRONTEND_DIR / "ios" / "Runner" / "Assets.xcassets" / "AppIcon.appiconset" / "Icon-App-60x60@2x.png", 120),
    (FRONTEND_DIR / "ios" / "Runner" / "Assets.xcassets" / "AppIcon.appiconset" / "Icon-App-60x60@3x.png", 180),
    (FRONTEND_DIR / "ios" / "Runner" / "Assets.xcassets" / "AppIcon.appiconset" / "Icon-App-76x76@1x.png", 76),
    (FRONTEND_DIR / "ios" / "Runner" / "Assets.xcassets" / "AppIcon.appiconset" / "Icon-App-76x76@2x.png", 152),
    (FRONTEND_DIR / "ios" / "Runner" / "Assets.xcassets" / "AppIcon.appiconset" / "Icon-App-83.5x83.5@2x.png", 167),
    (FRONTEND_DIR / "ios" / "Runner" / "Assets.xcassets" / "AppIcon.appiconset" / "Icon-App-1024x1024@1x.png", 1024),
]

LINUX_ICONS = [
    (FRONTEND_DIR / "linux" / "owlangs.png", 512),
]

# Windows ICO - we'll use the 256px icon as the base
WINDOWS_ICO_SOURCE = MACOS_ICON_DIR / "app_icon_256.png"
WINDOWS_ICO_TARGET = FRONTEND_DIR / "windows" / "runner" / "resources" / "app_icon.ico"


def resize_icon(source_img, output_path, size):
    """Resize icon to specified size, preserving alpha channel for rounded corners."""
    try:
        # Ensure source is RGBA to preserve transparency
        if source_img.mode != 'RGBA':
            img = source_img.convert('RGBA')
        else:
            img = source_img
        
        # Resize with high-quality resampling
        resized = img.resize((size, size), Image.Resampling.LANCZOS)
        
        # Ensure output directory exists
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        # Save as PNG with transparency
        resized.save(output_path, "PNG", optimize=True)
        print(f"✓ Generated: {output_path} ({size}x{size})")
        return True
    except Exception as e:
        print(f"✗ Error generating {output_path}: {e}")
        return False


def create_ico_from_png(png_path, ico_path):
    """Create ICO file from PNG (Windows icon), preserving transparency for rounded corners."""
    try:
        img = Image.open(png_path)
        
        # Ensure image is in RGBA mode to preserve transparency
        if img.mode != 'RGBA':
            img = img.convert('RGBA')
        
        # ICO files can contain multiple sizes for better compatibility
        # Generate multiple standard sizes from the source
        os.makedirs(os.path.dirname(ico_path), exist_ok=True)
        
        # Create multiple sizes for better Windows compatibility
        sizes = [(16, 16), (32, 32), (48, 48), (128, 128), (256, 256)]
        # Only include sizes that are <= source size
        valid_sizes = [(w, h) for w, h in sizes if w <= img.width and h <= img.height]
        if not valid_sizes:
            valid_sizes = [(img.width, img.height)]
        
        # Save as ICO with all sizes (Pillow supports ICO format with transparency)
        img.save(ico_path, "ICO", sizes=valid_sizes)
        print(f"✓ Generated: {ico_path} (from {png_path}, sizes: {valid_sizes})")
        return True
    except Exception as e:
        print(f"✗ Error creating ICO {ico_path}: {e}")
        return False


def main():
    print("🔄 Copying icons from macOS to other platforms...\n")
    
    # Check if source icon exists
    if not SOURCE_ICON.exists():
        print(f"❌ Error: Source icon not found: {SOURCE_ICON}")
        print("Available macOS icons:")
        for icon_file in MACOS_ICON_DIR.glob("app_icon_*.png"):
            print(f"  - {icon_file.name}")
        sys.exit(1)
    
    print(f"📦 Source icon: {SOURCE_ICON.name}")
    
    # Load source image
    try:
        source_img = Image.open(SOURCE_ICON)
        if source_img.mode != 'RGBA':
            source_img = source_img.convert('RGBA')
        print(f"   Size: {source_img.size[0]}x{source_img.size[1]}\n")
    except Exception as e:
        print(f"❌ Error loading source image: {e}")
        sys.exit(1)
    
    success_count = 0
    total_count = 0
    
    # Generate Web icons
    print("🌐 Generating Web icons...")
    for target_path, size in WEB_ICONS:
        total_count += 1
        if resize_icon(source_img, target_path, size):
            success_count += 1
    
    # Generate Android icons
    print("\n🤖 Generating Android icons...")
    for target_path, size in ANDROID_ICONS:
        total_count += 1
        if resize_icon(source_img, target_path, size):
            success_count += 1
    
    # Generate iOS icons
    print("\n🍎 Generating iOS icons...")
    for target_path, size in IOS_ICONS:
        total_count += 1
        if resize_icon(source_img, target_path, size):
            success_count += 1
    
    # Generate Linux icons
    print("\n🐧 Generating Linux icons...")
    for target_path, size in LINUX_ICONS:
        total_count += 1
        if resize_icon(source_img, target_path, size):
            success_count += 1
    
    # Generate Windows ICO
    print("\n🪟 Generating Windows icon...")
    if WINDOWS_ICO_SOURCE.exists():
        total_count += 1
        if create_ico_from_png(WINDOWS_ICO_SOURCE, WINDOWS_ICO_TARGET):
            success_count += 1
    else:
        # Fallback: create ICO from source image
        print(f"   Warning: {WINDOWS_ICO_SOURCE.name} not found, using source image")
        total_count += 1
        if create_ico_from_png(SOURCE_ICON, WINDOWS_ICO_TARGET):
            success_count += 1
    
    # Copy favicon for Web
    print("\n📄 Copying Web favicon...")
    web_favicon = FRONTEND_DIR / "web" / "favicon.ico"
    if WINDOWS_ICO_SOURCE.exists():
        total_count += 1
        if create_ico_from_png(WINDOWS_ICO_SOURCE, web_favicon):
            success_count += 1
    else:
        total_count += 1
        if create_ico_from_png(SOURCE_ICON, web_favicon):
            success_count += 1
    
    print(f"\n✅ Successfully generated {success_count}/{total_count} icons")
    print("\n📝 Note:")
    print("   - Web icons: Ready to use")
    print("   - Android icons: Ready to use")
    print("   - iOS icons: Ready to use")
    print("   - Linux icons: Ready to use")
    print("   - Windows icon: Ready to use")


if __name__ == "__main__":
    main()

