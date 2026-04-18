#!/usr/bin/env python3
"""
Generate macOS .icns from Icon Composer exported PNG files.
This is a convenience wrapper for easy one-command execution.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

def main() -> None:
    # Determine paths
    script_dir = Path(__file__).parent
    project_root = script_dir.parent.parent
    
    icon_composer_dir = project_root / "frontend" / "macos" / "Owlangs icon composer Exports"
    png_file = icon_composer_dir / "Owlangs icon composer-iOS-Default-1024x1024@1x.png"
    output_dir = project_root / "build" / "generated"
    output_icns = output_dir / "Owlangs.icns"
    
    # Check if PNG file exists
    if not png_file.exists():
        print(f"ERROR: Icon Composer PNG not found: {png_file}")
        print(f"Please ensure the file exists at the expected location.")
        sys.exit(1)
    
    # Create output directory
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Import the ICNS generation module
    sys.path.insert(0, str(script_dir))
    from macos_create_icns_from_icon_composer import main as create_icns_main
    
    # Override sys.argv to pass arguments to the main function
    sys.argv = [
        "macos_create_icns_from_icon_composer.py",
        str(png_file),
        str(output_icns)
    ]
    
    # Run the ICNS generation
    try:
        create_icns_main()
        print(f"\n✓ Successfully generated: {output_icns}")
        print(f"  Size: {output_icns.stat().st_size} bytes")
        return 0
    except Exception as e:
        print(f"\n✗ ERROR: Failed to generate ICNS: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())