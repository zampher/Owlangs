#!/usr/bin/env python3
"""
Generate macOS .icns from Icon Composer exported PNG files.

This script uses the PNG files exported from Icon Composer to create a macOS .icns file.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path


def create_iconset_from_icon_composer_png(png_path: Path, iconset_dir: Path) -> None:
    """Create a iconset from an Icon Composer exported PNG."""
    # Use the 1024x1024 PNG as the high-resolution source
    if not png_path.exists():
        raise FileNotFoundError(f"PNG file not found: {png_path}")
    
    # Create iconset directory if it doesn't exist
    iconset_dir.mkdir(parents=True, exist_ok=True)
    print(f"[iconset] Created iconset directory: {iconset_dir}")
    
    # Copy the PNG to the iconset directory as 512x512@2x
    macos_icon_name = "icon_512x512@2x.png"
    macos_icon_path = iconset_dir / macos_icon_name
    
    print(f"[iconset] Using Icon Composer PNG: {png_path}")
    print(f"[iconset] Copying to: {macos_icon_path}")
    
    shutil.copy2(png_path, macos_icon_path)
    print(f"[iconset] Copied file size: {macos_icon_path.stat().st_size} bytes")
    
    # Ensure corners are transparent
    try:
        from PIL import Image
        img = Image.open(macos_icon_path).convert('RGBA')
        width, height = img.size
        
        # Set corners to transparent
        corners = [(0, 0), (width-1, 0), (0, height-1), (width-1, height-1)]
        pixels = img.load()
        
        for x, y in corners:
            r, g, b, a = pixels[x, y]
            # Set to fully transparent
            pixels[x, y] = (r, g, b, 0)
        
        # Save the modified image
        img.save(macos_icon_path, format='PNG')
        print(f"[iconset] Set corners to transparent")
        print(f"[iconset] Modified file size: {macos_icon_path.stat().st_size} bytes")
    except ImportError:
        print(f"[iconset] PIL not available, skipping corner transparency fix")
    except Exception as e:
        print(f"[iconset] Error fixing corner transparency: {e}")
    
    # Create Contents.json with all required sizes
    # This ensures proper transparency handling
    contents = {
        "info": {"version": 1, "author": "xcode"},
        "images": [
            {
                "idiom": "mac",
                "size": "16x16",
                "scale": "1x"
            },
            {
                "idiom": "mac",
                "size": "16x16",
                "scale": "2x"
            },
            {
                "idiom": "mac",
                "size": "32x32",
                "scale": "1x"
            },
            {
                "idiom": "mac",
                "size": "32x32",
                "scale": "2x"
            },
            {
                "idiom": "mac",
                "size": "64x64",
                "scale": "1x"
            },
            {
                "idiom": "mac",
                "size": "64x64",
                "scale": "2x"
            },
            {
                "idiom": "mac",
                "size": "128x128",
                "scale": "1x"
            },
            {
                "idiom": "mac",
                "size": "128x128",
                "scale": "2x"
            },
            {
                "idiom": "mac",
                "size": "256x256",
                "scale": "1x"
            },
            {
                "idiom": "mac",
                "size": "256x256",
                "scale": "2x"
            },
            {
                "idiom": "mac",
                "size": "512x512",
                "filename": macos_icon_name,
                "scale": "2x"
            },
            {
                "idiom": "mac",
                "size": "1024x1024",
                "scale": "1x"
            }
        ],
    }
    
    contents_path = iconset_dir / "Contents.json"
    contents_path.write_text(json.dumps(contents, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[iconset] wrote Contents.json: {contents_path}")
    print(f"[iconset] Contents.json size: {contents_path.stat().st_size} bytes")
    
    # List files in iconset directory for debugging
    print("[iconset] Files in iconset directory:")
    for file in iconset_dir.iterdir():
        if file.is_file():
            size = file.stat().st_size
            print(f"[iconset]   - {file.name} ({size} bytes)")


def iconset_to_icns(iconset_dir: Path, icns_path: Path) -> None:
    """Convert iconset to .icns using iconutil."""
    iconutil = shutil.which("iconutil")
    if not iconutil:
        raise RuntimeError("iconutil not found on this machine.")

    print(f"[iconutil] Using iconutil: {iconutil}")
    print(f"[iconutil] Input iconset: {iconset_dir}")
    print(f"[iconutil] Output icns: {icns_path}")

    if icns_path.exists():
        print(f"[iconutil] Removing existing ICNS: {icns_path}")
        icns_path.unlink()

    print("[iconutil] Running iconutil command...")
    result = subprocess.run(
        ["iconutil", "-c", "icns", str(iconset_dir), "-o", str(icns_path)],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    
    if result.returncode != 0:
        print(f"[iconutil] Error output: {result.stdout}")
        raise RuntimeError(f"iconutil failed: {result.stdout}")
    else:
        print(f"[iconutil] Command successful")
        if icns_path.exists():
            size = icns_path.stat().st_size
            print(f"[iconutil] Generated ICNS size: {size} bytes")
        else:
            raise RuntimeError("iconutil completed but no ICNS file was created")


def main() -> None:
    """Main function."""
    import argparse

    print("========================================")
    print(" macOS ICNS Generator from Icon Composer ")
    print("========================================")

    # Determine default paths
    script_dir = Path(__file__).parent
    project_root = script_dir.parent.parent
    
    default_png_path = project_root / "frontend" / "macos" / "Owlangs icon composer-macOS-Default-1024x1024@1x.png"
    default_icns_path = project_root / "build" / "generated" / "Owlangs.icns"

    parser = argparse.ArgumentParser(description="Create macOS icns from Icon Composer exported PNG files.")
    parser.add_argument("png_path", type=Path, nargs='?', default=default_png_path, help="Path to Icon Composer exported PNG file")
    parser.add_argument("out_icns_path", type=Path, nargs='?', default=default_icns_path, help="Path to output .icns file")
    parser.add_argument(
        "--iconset-dir",
        type=Path,
        default=None,
        help="Optional iconset directory path (default: sibling of out_icns_path).",
    )
    args = parser.parse_args()

    print(f"\n[main] Input PNG: {args.png_path}")
    print(f"[main] Output ICNS: {args.out_icns_path}")

    if not args.png_path.is_file():
        raise FileNotFoundError(f"Missing PNG file: {args.png_path}")
    else:
        print(f"[main] Input PNG exists: {args.png_path.stat().st_size} bytes")

    # Create output directory if it doesn't exist
    output_dir = args.out_icns_path.parent
    print(f"[main] Output directory: {output_dir}")
    output_dir.mkdir(parents=True, exist_ok=True)
    print(f"[main] Created output directory")

    iconset_dir = args.iconset_dir
    if iconset_dir is None:
        iconset_dir = args.out_icns_path.with_suffix(".iconset")
    print(f"[main] Iconset directory: {iconset_dir}")

    if iconset_dir.exists():
        print(f"[main] Removing existing iconset directory")
        shutil.rmtree(iconset_dir)
    print(f"[main] Creating iconset directory")
    iconset_dir.mkdir(parents=True, exist_ok=True)

    # Create iconset from Icon Composer PNG
    print("\n[main] Step 1: Creating iconset from PNG...")
    create_iconset_from_icon_composer_png(args.png_path, iconset_dir)

    # Convert iconset to icns
    print("\n[main] Step 2: Converting iconset to ICNS...")
    iconset_to_icns(iconset_dir, args.out_icns_path)
    
    # Final verification
    if args.out_icns_path.exists():
        size = args.out_icns_path.stat().st_size
        print(f"\n[main] ✅ ICNS generation completed successfully!")
        print(f"[main] Generated ICNS: {args.out_icns_path}")
        print(f"[main] ICNS size: {size} bytes")
    else:
        print(f"\n[main] ❌ ICNS generation failed - no output file created")
    
    print("\n========================================")
    print("                Finished                ")
    print("========================================")


if __name__ == "__main__":
    main()