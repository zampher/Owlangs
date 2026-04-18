#!/usr/bin/env python3
import argparse
from pathlib import Path


# Common directories to exclude (build artifacts, caches, dependencies, etc.)
EXCLUDED_DIRS = {
    # Python
    "__pycache__",
    ".venv",
    "venv",
    "env",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    # Build outputs
    "build",
    "dist",
    "wheels",
    "*.egg-info",
    # Node.js / Flutter
    "node_modules",
    ".dart_tool",
    ".flutter-plugins",
    ".flutter-plugins-dependencies",
    ".pub-cache",
    ".pub",
    ".metadata",
    "coverage",
    # Launcher build artifacts
    "bin",
    "obj",
    # IDE
    ".idea",
    ".vscode",
    ".vs",
    # Git
    ".git",
    # Third-party models/data (large, not source code)
    "spacy_models",
    # Temporary/test outputs
    "tests/resource",
    "backend/output",
    "logs",
    "temp",
    "metadata",
    # Flutter build outputs
    "flutter/ephemeral",
    "flutter/build",
    "frontend/build",
    "frontend/.dart_tool",
    "frontend/.flutter-plugins",
    "frontend/.flutter-plugins-dependencies",
    "frontend/.pub-cache",
    "frontend/.pub",
    "frontend/.metadata",
    "frontend/coverage",
}


# Generated file patterns (files that should be excluded)
GENERATED_FILE_PATTERNS = [
    ".g.dart",  # Flutter code generation
    ".freezed.dart",  # Freezed code generation
    ".mocks.dart",  # Mockito generated files
]


def should_exclude_path(file_path: Path, root_dir: Path) -> bool:
    """Check if a file path should be excluded from counting."""
    try:
        rel_path = file_path.relative_to(root_dir)
        
        # Check for generated files (by filename pattern)
        filename = file_path.name
        if any(filename.endswith(pattern) for pattern in GENERATED_FILE_PATTERNS):
            return True
        
        # Check if any part of the path matches excluded directory names
        for part in rel_path.parts:
            if part in EXCLUDED_DIRS:
                return True
            # Also check if part starts with excluded patterns (e.g., *.egg-info)
            if any(part.startswith(excluded.rstrip("*")) for excluded in EXCLUDED_DIRS if "*" in excluded):
                return True
    except ValueError:
        # Path is not relative to root_dir, skip it
        return True
    return False


def count_lines_in_file(file_path: Path) -> tuple[int, int]:
    """Count total lines and non-comment code lines in a single text file."""
    try:
        text = file_path.read_text(encoding="utf-8", errors="ignore")
    except Exception as e:
        print(f"Error reading {file_path}: {e}")
        return 0, 0

    lines = text.splitlines()
    total = len(lines)
    
    # Determine comment style based on file extension
    ext = file_path.suffix.lower()
    if ext == ".py":
        # Python: # for single-line comments
        code = sum(
            1
            for line in lines
            if line.strip() and not line.lstrip().startswith("#")
        )
    elif ext in (".cs", ".csx"):
        # C#: // for single-line, /* */ for multi-line
        code = 0
        in_multiline_comment = False
        for line in lines:
            stripped = line.strip()
            if not stripped:
                continue
            
            # Process multi-line comments
            line_content = stripped
            # Remove multi-line comments from the line
            while "/*" in line_content:
                start_idx = line_content.index("/*")
                # Check if comment ends on same line
                if "*/" in line_content[start_idx + 2:]:
                    end_idx = line_content.index("*/", start_idx + 2) + 2
                    # Remove the comment, keep content before and after
                    line_content = line_content[:start_idx] + line_content[end_idx:]
                else:
                    # Comment starts but doesn't end on this line
                    line_content = line_content[:start_idx]
                    in_multiline_comment = True
                    break
            
            # If we're in a multi-line comment, check if it ends on this line
            if in_multiline_comment:
                if "*/" in stripped:
                    # Comment ends on this line, extract content after */
                    end_idx = stripped.index("*/") + 2
                    remaining = stripped[end_idx:].strip()
                    in_multiline_comment = False
                    # Check if there's code after the comment
                    if remaining and not remaining.startswith("//"):
                        code += 1
                # Otherwise, this line is entirely within comment, skip it
                continue
            
            # Check for single-line comment
            if line_content.strip() and not line_content.strip().startswith("//"):
                code += 1
    elif ext == ".dart":
        # Dart: // for single-line, /* */ for multi-line
        code = 0
        in_multiline_comment = False
        for line in lines:
            stripped = line.strip()
            if not stripped:
                continue
            
            # Process multi-line comments
            line_content = stripped
            # Remove multi-line comments from the line
            while "/*" in line_content:
                start_idx = line_content.index("/*")
                # Check if comment ends on same line
                if "*/" in line_content[start_idx + 2:]:
                    end_idx = line_content.index("*/", start_idx + 2) + 2
                    # Remove the comment, keep content before and after
                    line_content = line_content[:start_idx] + line_content[end_idx:]
                else:
                    # Comment starts but doesn't end on this line
                    line_content = line_content[:start_idx]
                    in_multiline_comment = True
                    break
            
            # If we're in a multi-line comment, check if it ends on this line
            if in_multiline_comment:
                if "*/" in stripped:
                    # Comment ends on this line, extract content after */
                    end_idx = stripped.index("*/") + 2
                    remaining = stripped[end_idx:].strip()
                    in_multiline_comment = False
                    # Check if there's code after the comment
                    if remaining and not remaining.startswith("//"):
                        code += 1
                # Otherwise, this line is entirely within comment, skip it
                continue
            
            # Check for single-line comment
            if line_content.strip() and not line_content.strip().startswith("//"):
                code += 1
    else:
        # Default: treat as Python-style (# comments)
        code = sum(
            1
            for line in lines
            if line.strip() and not line.lstrip().startswith("#")
        )
    
    return total, code


def count_lines_in_directory(
    root_dir: Path, extensions: list[str], verbose: bool = False
) -> dict[str, dict[str, int]]:
    """Recursively count lines for given extensions under root_dir, excluding build/cache dirs."""
    stats: dict[str, dict[str, int]] = {
        ext: {"files": 0, "total": 0, "code": 0} for ext in extensions
    }
    
    excluded_count = {ext: 0 for ext in extensions}

    for ext in extensions:
        pattern = f"*.{ext}"
        for file_path in root_dir.rglob(pattern):
            if not file_path.is_file():
                continue
            # Skip excluded directories
            if should_exclude_path(file_path, root_dir):
                excluded_count[ext] += 1
                if verbose:
                    print(f"[EXCLUDED] {file_path.relative_to(root_dir)}")
                continue
            total, code = count_lines_in_file(file_path)
            s = stats[ext]
            s["files"] += 1
            s["total"] += total
            s["code"] += code
            if verbose:
                print(f"[COUNTED] {file_path.relative_to(root_dir)}: {total} total, {code} code")

    if verbose:
        print(f"\nExcluded files: {excluded_count}")

    return stats


def main() -> None:
    script_dir = Path(__file__).resolve().parent
    # Default to repository root (parent of tools/) so you can run from tools/
    default_root = script_dir.parent

    parser = argparse.ArgumentParser(
        description="Count lines of Python, Dart, and C# code in the repository."
    )
    parser.add_argument(
        "--path",
        default=str(default_root),
        help="Root directory to search (default: repo root, parent of tools/)",
    )
    parser.add_argument(
        "--python", action="store_true", help="Count only Python files"
    )
    parser.add_argument(
        "--dart", action="store_true", help="Count only Dart files"
    )
    parser.add_argument(
        "--csharp", "--cs", action="store_true", dest="csharp", help="Count only C# files"
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true", help="Show detailed output (files being counted/excluded)"
    )
    args = parser.parse_args()

    extensions: list[str] = []
    if args.python:
        extensions.append("py")
    if args.dart:
        extensions.append("dart")
    if args.csharp:
        extensions.append("cs")
    if not extensions:
        # Default: count all supported languages
        extensions = ["py", "dart", "cs"]

    root_dir = Path(args.path).resolve()
    stats = count_lines_in_directory(root_dir, extensions, verbose=args.verbose)

    print(f"\n{'Code Line Statistics':^60}")
    print(f"{'=' * 60}")
    print(f"{'Language':<15} {'Files':<10} {'Total Lines':<15} {'Code Lines':<15}")
    print(f"{'-' * 60}")

    total_files = 0
    total_lines = 0
    total_code = 0

    # Map extension to display name
    lang_display_names = {
        "py": "Python",
        "dart": "Dart",
        "cs": "C#",
    }
    
    for ext in extensions:
        info = stats.get(ext, {"files": 0, "total": 0, "code": 0})
        if info["files"] > 0:
            lang_name = lang_display_names.get(ext, ext.upper())
            print(
                f"{lang_name:<15} {info['files']:<10} "
                f"{info['total']:<15} {info['code']:<15}"
            )
            total_files += info["files"]
            total_lines += info["total"]
            total_code += info["code"]

    print(f"{'=' * 60}")
    print(f"{'Total':<15} {total_files:<10} {total_lines:<15} {total_code:<15}")
    print(f"{'=' * 60}\n")


if __name__ == "__main__":
    main()

