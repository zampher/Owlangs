#!/usr/bin/env python3
"""
macos_launch_signal.py

This script sends the application launch complete signal to macOS.
It should be called once the application has fully started.
"""

import sys
import os
import subprocess

# Import logger
from logger import unified_logger as logger
from logger.logger import LogModule

def send_launch_complete_signal():
    """
    Send the macOS application launch complete signal.
    This tells macOS that the application has finished launching.
    """
    # Only run on macOS
    if sys.platform != 'darwin':
        return
    
    try:
        logger.info(LogModule.SYSTEM, "Sending macOS launch complete signal using simple method...")
        
        # Simple approach: Just activate of app without requiring special permissions
        # This avoids asking users for System Events or Finder permissions
        commands = [
            # Simple activation - no special permissions needed
            'tell application "Owlangs" to activate'
        ]
        
        for cmd in commands:
            try:
                result = subprocess.run(['osascript', '-e', cmd], capture_output=True, text=True, timeout=1)
                if result.returncode != 0:
                    logger.warning(LogModule.SYSTEM, f"AppleScript command failed: {cmd}\nError: {result.stderr}")
                else:
                    logger.info(LogModule.SYSTEM, f"AppleScript command executed: {cmd}")
            except Exception as e:
                # Don't log timeout as error - it's expected behavior
                if "timed out" not in str(e):
                    logger.warning(LogModule.SYSTEM, f"AppleScript command failed: {cmd}\nError: {e}")
        
        logger.info(LogModule.SYSTEM, "Launch signal sent successfully")
        
    except Exception as e:
        # Log the error but don't let it crash the application
        logger.warning(LogModule.SYSTEM, f"Error sending macOS launch signal: {e}")
    
    # Final confirmation log
    logger.info(LogModule.SYSTEM, "macOS launch complete signal sending process finished")

# Only run if executed directly
if __name__ == "__main__":
    send_launch_complete_signal()
