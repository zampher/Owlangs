#!/usr/bin/env python3
"""
Set DMG volume icon using Python and Cocoa APIs.
This script properly sets the custom icon attribute for DMG volumes.
"""

import sys
import subprocess
import os
from pathlib import Path

def set_volume_icon(volume_path: str, icon_path: str) -> bool:
    """Set custom icon for a volume."""
    try:
        # Copy icon file to volume root
        volume_icon_path = os.path.join(volume_path, ".VolumeIcon.icns")
        subprocess.run(["cp", icon_path, volume_icon_path], check=True)
        
        # Set the custom icon attribute using SetFile
        result = subprocess.run(
            ["SetFile", "-a", "C", volume_path],
            capture_output=True,
            text=True
        )
        
        if result.returncode != 0:
            print(f"SetFile failed: {result.stderr}")
            return False
        
        print(f"Successfully set volume icon for {volume_path}")
        return True
    except Exception as e:
        print(f"Error setting volume icon: {e}")
        return False

def main():
    if len(sys.argv) != 3:
        print("Usage: python set_dmg_icon.py <volume_path> <icon_path>")
        sys.exit(1)
    
    volume_path = sys.argv[1]
    icon_path = sys.argv[2]
    
    if not os.path.exists(volume_path):
        print(f"Volume path does not exist: {volume_path}")
        sys.exit(1)
    
    if not os.path.exists(icon_path):
        print(f"Icon path does not exist: {icon_path}")
        sys.exit(1)
    
    success = set_volume_icon(volume_path, icon_path)
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()