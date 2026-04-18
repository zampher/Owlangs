#!/usr/bin/env python3
"""
Regenerate all platform icons from the frontend PNG source.

This script:
1. Uses assets/owlangs_owl_solid_frontend.png as the canonical source
2. Copies PNG to macOS icon directory
3. Generates all platform icons from the PNG

Usage:
    python tools/regenerate_all_icons.py
"""

import os
import sys
import shutil
from pathlib import Path

# Try to import PIL Image
try:
    from PIL import Image
except ImportError:
    Image = None

# Default fill ratio for PNG icons (same as generate_ico.py default)
DEFAULT_FILL_RATIO = 1.0  # Use 1.0 to preserve original rounded corners without adding margins


def composite_centered_on_square(
    img, canvas_size: int, fill_ratio: float
) -> object:
    """Place artwork on a transparent square canvas with margin so small icons keep shape readable.
    
    Preserves alpha channel for rounded corner transparency.
    """
    if fill_ratio <= 0 or fill_ratio > 1.0:
        raise ValueError("fill_ratio must be in (0, 1]")
    inner = max(1, int(round(canvas_size * fill_ratio)))
    
    # Ensure image is in RGBA mode to preserve transparency
    if img.mode != "RGBA":
        img = img.convert("RGBA")
    
    # Resize to target inner size with transparency preserved
    scaled = img.resize((inner, inner), Image.Resampling.LANCZOS)
    
    # Create transparent background (RGBA with alpha=0)
    out = Image.new("RGBA", (canvas_size, canvas_size), (255, 255, 255, 0))
    off = (canvas_size - inner) // 2
    out.paste(scaled, (off, off), scaled)  # Use scaled as mask for alpha
    return out

# Get project root and frontend directory
PROJECT_ROOT = Path(__file__).parent.parent.parent
FRONTEND_DIR = Path(__file__).parent.parent
ASSETS_DIR = PROJECT_ROOT / "assets"
MACOS_ICON_DIR = FRONTEND_DIR / "macos" / "Runner" / "Assets.xcassets" / "AppIcon.appiconset"

# Source files (use frontend-specific PNG as the canonical source)
PNG_SOURCE = ASSETS_DIR / "owlangs_owl_solid_frontend.png"
SVG_SOURCE = ASSETS_DIR / "owlangs_owl_solid_frontend.svg"
MACOS_TARGET = MACOS_ICON_DIR / "app_icon_1024.png"


def main():
    import argparse
    
    # Parse command line arguments
    parser = argparse.ArgumentParser(description="Regenerate all platform icons from updated PNG.")
    parser.add_argument(
        "--fill-ratio",
        type=float,
        default=DEFAULT_FILL_RATIO,
        help=f"Scale factor inside each square (0-1); default {DEFAULT_FILL_RATIO} preserves original rounded corners. Use <1.0 to add margins for small icons.",
    )
    parser.add_argument(
        "--use-psd-template",
        action="store_true",
        help="Use Apple's PSD template for macOS icons instead of simple rounded corners",
    )
    args = parser.parse_args()
    
    # Set UTF-8 encoding for Windows console
    if sys.platform == 'win32':
        import io
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
    
    print("Regenerating all platform icons from updated PNG source...")
    print(f"Fill ratio: {args.fill_ratio}")
    print()

    # Step 1: Check PNG source
    if not PNG_SOURCE.exists():
        print(f"ERROR: PNG source not found: {PNG_SOURCE}")
        print("   Please ensure the PNG file exists.")
        return 1

    print(f"OK: PNG source found: {PNG_SOURCE}")

    if Image is not None:
        try:
            img = Image.open(PNG_SOURCE)
            if img.size[0] < 1024 or img.size[1] < 1024:
                print(f"WARNING: PNG is smaller than 1024x1024: {img.size[0]}x{img.size[1]}")
                print("   Some platform icons may be lower quality.")
            else:
                print(f"OK: PNG size is {img.size[0]}x{img.size[1]}")
        except Exception as e:
            print(f"ERROR: Could not verify PNG: {e}")
            return 1

        # Apply fill ratio to the source PNG if needed
        if args.fill_ratio < 0.95:
            try:
                source_img = Image.open(PNG_SOURCE)
                if source_img.mode != 'RGBA':
                    source_img = source_img.convert('RGBA')
                processed_img = composite_centered_on_square(source_img, 1024, args.fill_ratio)
                processed_img.save(PNG_SOURCE, "PNG", optimize=True)
                print(f"OK: Applied fill ratio {args.fill_ratio} to 1024x1024 PNG (added transparent margin)")
            except Exception as e:
                print(f"WARNING: Failed to apply fill ratio to PNG: {e}")
        else:
            print(f"OK: Using original PNG as-is (preserves original rounded corners)")
    else:
        print("WARNING: Pillow not installed, skipping PNG verification and fill ratio application")
    
    # Step 3: Generate macOS icons
    print()
    print("Generating macOS icons...")
    
    # Ensure macOS icon directory exists
    MACOS_ICON_DIR.mkdir(parents=True, exist_ok=True)
    
    # Check if Apple-style PNG exists (manually created with proper rounded corners)
    APPLE_STYLE_PNG = FRONTEND_DIR / "macos" / "Owlangs-iOS-Default-1024@1x.png"
    
    # Generate all macOS icon sizes from the source PNG
    try:
        if Image is None:
            print("WARNING: Pillow not installed, skipping macOS icon size generation")
        else:
            # Use Apple-style PNG if available
            if APPLE_STYLE_PNG.exists():
                print(f"Using Apple-style PNG: {APPLE_STYLE_PNG}")
                source_img = Image.open(APPLE_STYLE_PNG)
                if source_img.mode != 'RGBA':
                    source_img = source_img.convert('RGBA')
                
                # macOS icon sizes needed
                macos_sizes = {
                    "app_icon_16.png": 16,
                    "app_icon_32.png": 32,
                    "app_icon_64.png": 64,
                    "app_icon_128.png": 128,
                    "app_icon_256.png": 256,
                    "app_icon_512.png": 512,
                    "app_icon_1024.png": 1024,
                }
                
                for filename, size in macos_sizes.items():
                    output_path = MACOS_ICON_DIR / filename
                    # Direct resize - Apple-style PNG already has proper rounded corners
                    resized = source_img.resize((size, size), Image.Resampling.LANCZOS)
                    if resized.mode != 'RGB':
                        resized = resized.convert('RGB')
                    resized.save(output_path, "PNG", optimize=True)
                    print(f"OK: Generated {filename} ({size}x{size}) from Apple-style PNG")
            
            # Check if we should use PSD template
            elif args.use_psd_template:
                psd_template = FRONTEND_DIR / "macos" / "App Icon Template.psd"
                if psd_template.exists():
                    print("Using Apple's PSD template for macOS icons...")
                    # Import and use the PSD-based generator
                    sys.path.insert(0, str(PROJECT_ROOT / "tools"))
                    try:
                        from generate_macos_icons_from_psd import generate_macos_icons
                        generate_macos_icons(PNG_SOURCE, psd_template, MACOS_ICON_DIR, args.fill_ratio)
                    except ImportError as e:
                        print(f"WARNING: PSD generator not available: {e}")
                        print("   Falling back to simple rounded corners...")
                        args.use_psd_template = False
                    except Exception as e:
                        print(f"WARNING: PSD generation failed: {e}")
                        print("   Falling back to simple rounded corners...")
                        args.use_psd_template = False
                else:
                    print(f"WARNING: PSD template not found: {psd_template}")
                    print("   Falling back to simple rounded corners...")
                    args.use_psd_template = False
            
            # If not using PSD template or Apple-style PNG, use simple rounded corners
            if not args.use_psd_template and not APPLE_STYLE_PNG.exists():
                # Copy PNG to macOS directory (1024x1024)
                try:
                    shutil.copy2(PNG_SOURCE, MACOS_TARGET)
                    print(f"OK: Copied to: {MACOS_TARGET}")
                except Exception as e:
                    print(f"ERROR: Failed to copy PNG: {e}")
                    return 1
                
                # Generate other sizes (skip 1024x1024 as it's already copied)
                source_img = Image.open(PNG_SOURCE)
                if source_img.mode != 'RGBA':
                    source_img = source_img.convert('RGBA')
                
                # macOS icon sizes needed
                macos_sizes = {
                    "app_icon_16.png": 16,
                    "app_icon_32.png": 32,
                    "app_icon_64.png": 64,
                    "app_icon_128.png": 128,
                    "app_icon_256.png": 256,
                    "app_icon_512.png": 512,
                    "app_icon_1024.png": 1024,
                }
                
                for filename, size in macos_sizes.items():
                    if filename == "app_icon_1024.png":
                        continue  # Already copied
                    output_path = MACOS_ICON_DIR / filename
                    
                    # Direct resize to preserve rounded corners perfectly
                    # Only use composite if fill_ratio is significantly less than 1.0
                    if args.fill_ratio < 0.95:
                        # Use composite with fill ratio for better small icon readability
                        # This adds transparent margin around the icon
                        resized = composite_centered_on_square(source_img, size, args.fill_ratio)
                        print(f"OK: Generated {filename} ({size}x{size}) with fill ratio {args.fill_ratio} (with margin)")
                    else:
                        # Direct resize preserves original rounded corners perfectly
                        resized = source_img.resize((size, size), Image.Resampling.LANCZOS)
                        # Keep RGBA mode to preserve transparency
                        if resized.mode != 'RGBA':
                            resized = resized.convert('RGBA')
                        print(f"OK: Generated {filename} ({size}x{size}) - direct resize (preserves rounded corners)")
                    resized.save(output_path, "PNG", optimize=True)
    except Exception as e:
        print(f"WARNING: Failed to generate macOS icon sizes: {e}")
        print("   Continuing with just the 1024x1024 copy...")
    
    # Step 4: Run copy_icons_from_macos.py to generate all platform icons
    print()
    print("Running copy_icons_from_macos.py to generate all platform icons...")
    print()
    
    # Import and run the copy script
    sys.path.insert(0, str(FRONTEND_DIR / "tools"))
    try:
        if Image is None:
            print("WARNING: Pillow not installed, skipping cross-platform icon generation")
        else:
            from copy_icons_from_macos import main as copy_main
            copy_main()
    except Exception as e:
        print(f"ERROR: Failed to generate icons: {e}")
        import traceback
        traceback.print_exc()
        print("   Continuing with other steps...")
    
    # Step 5: Update all favicon.png files
    print()
    print("Updating all favicon.png files...")
    
    # Source favicon PNG - always regenerate from the latest PNG source
    SOURCE_FAVICON_PNG = None
    LOGO_48_PNG = None
    
    # Generate favicon.png from the main PNG source (64x64 so it is not too small in tabs/apps)
    if PNG_SOURCE.exists():
        try:
            if Image is None:
                print("WARNING: Pillow not installed, skipping favicon generation")
            else:
                source_img = Image.open(PNG_SOURCE)
                if source_img.mode != 'RGBA':
                    source_img = source_img.convert('RGBA')
                
                # Create 64x64 favicon (larger than 32x32 so it does not look tiny on high-DPI)
                FAVICON_SIZE = 64
                if args.fill_ratio < 0.95:
                    favicon_img = composite_centered_on_square(source_img, FAVICON_SIZE, args.fill_ratio)
                else:
                    favicon_img = source_img.resize((FAVICON_SIZE, FAVICON_SIZE), Image.Resampling.LANCZOS)
                    if favicon_img.mode != 'RGBA':
                        favicon_img = favicon_img.convert('RGBA')
                SOURCE_FAVICON_PNG = FRONTEND_DIR / "images" / "favicon.png"
                SOURCE_FAVICON_PNG.parent.mkdir(parents=True, exist_ok=True)
                favicon_img.save(SOURCE_FAVICON_PNG, "PNG", optimize=True)
                print(f"Generated favicon.png ({FAVICON_SIZE}x{FAVICON_SIZE}) from source PNG: {PNG_SOURCE.relative_to(PROJECT_ROOT)}")
                
                # Create a 48x48 logo for homepage/app bar (legacy size)
                if args.fill_ratio < 0.95:
                    favicon_48 = composite_centered_on_square(source_img, 48, args.fill_ratio)
                else:
                    favicon_48 = source_img.resize((48, 48), Image.Resampling.LANCZOS)
                    if favicon_48.mode != 'RGBA':
                        favicon_48 = favicon_48.convert('RGBA')
                LOGO_48_PNG = FRONTEND_DIR / "images" / "logo_48.png"
                LOGO_48_PNG.parent.mkdir(parents=True, exist_ok=True)
                favicon_48.save(LOGO_48_PNG, "PNG", optimize=True)
                print(
                    f"Generated logo_48.png (48x48) from source PNG: "
                    f"{PNG_SOURCE.relative_to(PROJECT_ROOT)}"
                )

                # Create a 64x64 logo for larger placements (e.g. workspace top-left)
                if args.fill_ratio < 0.95:
                    logo_64 = composite_centered_on_square(source_img, 64, args.fill_ratio)
                else:
                    logo_64 = source_img.resize((64, 64), Image.Resampling.LANCZOS)
                    if logo_64.mode != 'RGBA':
                        logo_64 = logo_64.convert('RGBA')
                LOGO_64_PNG = FRONTEND_DIR / "images" / "logo_64.png"
                LOGO_64_PNG.parent.mkdir(parents=True, exist_ok=True)
                logo_64.save(LOGO_64_PNG, "PNG", optimize=True)
                print(
                    f"Generated logo_64.png (64x64) from source PNG: "
                    f"{PNG_SOURCE.relative_to(PROJECT_ROOT)}"
                )

                # Create a 96x96 logo for high‑resolution placements
                if args.fill_ratio < 0.95:
                    logo_96 = composite_centered_on_square(source_img, 96, args.fill_ratio)
                else:
                    logo_96 = source_img.resize((96, 96), Image.Resampling.LANCZOS)
                    if logo_96.mode != 'RGBA':
                        logo_96 = logo_96.convert('RGBA')
                LOGO_96_PNG = FRONTEND_DIR / "images" / "logo_96.png"
                LOGO_96_PNG.parent.mkdir(parents=True, exist_ok=True)
                logo_96.save(LOGO_96_PNG, "PNG", optimize=True)
                print(
                    f"Generated logo_96.png (96x96) from source PNG: "
                    f"{PNG_SOURCE.relative_to(PROJECT_ROOT)}"
                )
        except Exception as e:
            print(f"WARNING: Failed to generate favicon.png from source: {e}")
    
    # Step 5.5: Copy logo_48.png to web and windows directories
    if LOGO_48_PNG and LOGO_48_PNG.exists():
        print()
        print("Copying logo_48.png to web and windows directories...")
        
        LOGO_48_LOCATIONS = [
            # Frontend web
            FRONTEND_DIR / "web" / "logo_48.png",
            # Windows runner resources
            FRONTEND_DIR / "windows" / "runner" / "resources" / "logo_48.png",
        ]
        
        updated_count = 0
        for logo_path in LOGO_48_LOCATIONS:
            try:
                # Ensure parent directory exists
                logo_path.parent.mkdir(parents=True, exist_ok=True)
                
                # Copy logo
                shutil.copy2(LOGO_48_PNG, logo_path)
                print(f"OK: Updated {logo_path.relative_to(PROJECT_ROOT)}")
                updated_count += 1
            except Exception as e:
                print(f"WARNING: Failed to update {logo_path.relative_to(PROJECT_ROOT)}: {e}")
        
        print(f"Updated {updated_count}/{len(LOGO_48_LOCATIONS)} logo_48.png files")
    
    if SOURCE_FAVICON_PNG and SOURCE_FAVICON_PNG.exists():
        # List of all favicon.png locations to update
        FAVICON_PNG_LOCATIONS = [
            # Frontend web
            FRONTEND_DIR / "web" / "favicon.png",
            # Frontend images (source location)
            FRONTEND_DIR / "images" / "favicon.png",
            # Backend static
            PROJECT_ROOT / "backend" / "static" / "favicon.png",
            PROJECT_ROOT / "backend" / "static" / "flutter-web" / "favicon.png",
            # Root directory
            PROJECT_ROOT / "favicon.png",
        ]
        
        updated_count = 0
        for favicon_path in FAVICON_PNG_LOCATIONS:
            try:
                # Ensure parent directory exists
                favicon_path.parent.mkdir(parents=True, exist_ok=True)
                
                # Copy favicon
                shutil.copy2(SOURCE_FAVICON_PNG, favicon_path)
                print(f"OK: Updated {favicon_path.relative_to(PROJECT_ROOT)}")
                updated_count += 1
            except Exception as e:
                print(f"WARNING: Failed to update {favicon_path.relative_to(PROJECT_ROOT)}: {e}")
        
        print(f"Updated {updated_count}/{len(FAVICON_PNG_LOCATIONS)} favicon.png files")
    else:
        print(f"WARNING: Source favicon.png not found or could not be generated")
        print("   Skipping favicon.png updates.")
    
    # Step 6: Generate favicon.ico from frontend PNG, then update all favicon.ico files
    print()
    print("Step 6: Generating and updating favicon.ico files...")

    # Generate ICO from frontend PNG (web + Windows app icon) via project script
    SOURCE_FAVICON = FRONTEND_DIR / "web" / "favicon.ico"
    if PNG_SOURCE.exists():
        try:
            import subprocess
            result = subprocess.run(
                [sys.executable, str(PROJECT_ROOT / "tools" / "generate_ico.py"), "--frontend", "--fill-ratio", str(args.fill_ratio)],
                cwd=str(PROJECT_ROOT),
                capture_output=True,
                text=True,
                timeout=60,
            )
            if result.returncode == 0:
                print(f"OK: Generated favicon.ico and app_icon.ico from {PNG_SOURCE.name}")
            else:
                print(f"WARNING: generate_ico.py --frontend failed: {result.stderr or result.stdout or 'unknown'}")
        except Exception as e:
            print(f"WARNING: Could not run generate_ico.py: {e}")
    else:
        print(f"WARNING: PNG source not found: {PNG_SOURCE}")
        print("   Skipping favicon.ico generation.")

    if not SOURCE_FAVICON.exists():
        print(f"WARNING: Source favicon not found: {SOURCE_FAVICON}")
        print("   Run: python tools/generate_ico.py --frontend")
        print("   Skipping favicon copy to other locations.")
    else:
        # List of all favicon.ico locations to update
        FAVICON_LOCATIONS = [
            # Frontend assets
            FRONTEND_DIR / "assets" / "images" / "favicon.ico",
            FRONTEND_DIR / "assets" / "icons" / "favicon.ico",
            # Frontend images and icons (current structure)
            FRONTEND_DIR / "images" / "favicon.ico",
            FRONTEND_DIR / "icons" / "favicon.ico",
            # Backend static
            PROJECT_ROOT / "backend" / "static" / "favicon.ico",
            PROJECT_ROOT / "backend" / "static" / "flutter-web" / "favicon.ico",
            # Backend static flutter-web assets (nested paths)
            PROJECT_ROOT / "backend" / "static" / "flutter-web" / "assets" / "assets" / "images" / "favicon.ico",
            PROJECT_ROOT / "backend" / "static" / "flutter-web" / "assets" / "assets" / "icons" / "favicon.ico",
            # Root directory
            PROJECT_ROOT / "favicon.ico",
            # Legacy frontend
            PROJECT_ROOT / "legacy-frontend" / "static" / "favicon.ico",
            # Flutter frontend (if exists)
            FRONTEND_DIR / "flutter-frontend" / "assets" / "images" / "favicon.ico",
        ]
        
        updated_count = 0
        for favicon_path in FAVICON_LOCATIONS:
            try:
                # Ensure parent directory exists
                favicon_path.parent.mkdir(parents=True, exist_ok=True)
                
                # Copy favicon
                shutil.copy2(SOURCE_FAVICON, favicon_path)
                print(f"OK: Updated {favicon_path.relative_to(PROJECT_ROOT)}")
                updated_count += 1
            except Exception as e:
                print(f"WARNING: Failed to update {favicon_path.relative_to(PROJECT_ROOT)}: {e}")
        
        print(f"Updated {updated_count}/{len(FAVICON_LOCATIONS)} favicon.ico files")
    
    # Step 7: Generate macOS .icns file
    print()
    print("Step 7: Generating macOS .icns file...")
    
    ICNS_OUTPUT = PROJECT_ROOT / "assets" / "Owlangs.icns"
    if sys.platform == 'darwin':  # Only on macOS
        try:
            import subprocess
            
            # Use Icon Composer exported PNG as source for ICNS (best quality)
            ICON_COMPOSER_PNG = FRONTEND_DIR / "macos" / "Owlangs icon composer-macOS-Default-1024x1024@1x.png"
            
            if ICON_COMPOSER_PNG.exists():
                print(f"Using Icon Composer PNG as source: {ICON_COMPOSER_PNG}")
                
                # Build command to generate ICNS from Icon Composer PNG
                cmd = [
                    sys.executable, 
                    str(PROJECT_ROOT / "tools" / "build" / "macos_create_icns_from_icon_composer.py"),
                    str(ICON_COMPOSER_PNG),
                    str(ICNS_OUTPUT)
                ]
                
                result = subprocess.run(
                    cmd,
                    cwd=str(PROJECT_ROOT),
                    capture_output=True,
                    text=True,
                    timeout=60,
                )
                if result.returncode == 0:
                    print(f"OK: Generated macOS .icns file: {ICNS_OUTPUT}")
                    print("   Using high-quality Icon Composer PNG")
                else:
                    print(f"WARNING: Failed to generate .icns: {result.stderr or result.stdout or 'unknown'}")
            else:
                print(f"WARNING: Icon Composer PNG not found: {ICON_COMPOSER_PNG}")
        except Exception as e:
            print(f"WARNING: Could not generate .icns: {e}")
    else:
        print("   Skipping .icns generation (only available on macOS)")
    
    print()
    print("SUCCESS: All icons regenerated successfully!")
    print()
    print("Summary:")
    print(f"   - PNG source: {PNG_SOURCE}")
    if SVG_SOURCE.exists():
        print(f"   - SVG source (fallback): {SVG_SOURCE}")
    print(f"   - macOS icon: {MACOS_TARGET}")
    print("   - All platform icons have been updated")
    print("   - All favicon.png files have been updated")
    print("   - All favicon.ico files have been updated")
    if sys.platform == 'darwin':
        print(f"   - macOS .icns: {ICNS_OUTPUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
