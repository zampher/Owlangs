#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

"""
Helper script to add module parameter to logger.debug and logger.trace calls.
This is a one-time migration script.
"""

import re
import sys
from pathlib import Path

def add_module_to_logs(file_path: Path, module: str = "TRANS"):
    """Add module parameter to debug/trace calls in a file."""
    content = file_path.read_text(encoding='utf-8')
    original_content = content
    
    # Pattern to match logger.debug(...) or logger.trace(...) calls
    # This handles both single-line and multi-line calls
    pattern = r'logger\.(debug|trace)\s*\(\s*([^)]+)\)'
    
    def replace_match(match):
        log_level = match.group(1)
        args = match.group(2)
        
        # Check if module parameter already exists
        if 'module=' in args or 'module:' in args:
            return match.group(0)  # Already has module, skip
        
        # Check if it's a multi-line call (contains newlines)
        if '\n' in args:
            # Multi-line: add module parameter before closing parenthesis
            # Find the last line and add module parameter
            lines = args.split('\n')
            last_line = lines[-1].rstrip()
            # Remove trailing comma if exists
            if last_line.endswith(','):
                last_line = last_line[:-1].rstrip()
            # Add module parameter
            lines[-1] = f"{last_line},\n            module=LogModule.{module}"
            new_args = '\n'.join(lines)
            return f"logger.{log_level}(\n            {new_args}\n        )"
        else:
            # Single-line: add module parameter at the end
            args_stripped = args.rstrip()
            if args_stripped.endswith(','):
                args_stripped = args_stripped[:-1].rstrip()
            return f"logger.{log_level}({args_stripped}, module=LogModule.{module})"
    
    # Replace all matches
    content = re.sub(pattern, replace_match, content, flags=re.MULTILINE | re.DOTALL)
    
    if content != original_content:
        file_path.write_text(content, encoding='utf-8')
        return True
    return False

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python _add_module_to_logs.py <file_path> [module]")
        sys.exit(1)
    
    file_path = Path(sys.argv[1])
    module = sys.argv[2] if len(sys.argv) > 2 else "TRANS"
    
    if not file_path.exists():
        print(f"File not found: {file_path}")
        sys.exit(1)
    
    if add_module_to_logs(file_path, module):
        print(f"Updated {file_path} with module={module}")
    else:
        print(f"No changes needed in {file_path}")
