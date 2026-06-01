#!/usr/bin/env python3
import argparse
import subprocess
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


def _is_generated_file(file_path: Path) -> bool:
    """Check if a file matches generated-file patterns."""
    filename = file_path.name
    return any(filename.endswith(pattern) for pattern in GENERATED_FILE_PATTERNS)


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


# Extensions grouped by comment style
# Single-line: //  Multi-line: /* */
C_STYLE_EXTS = {".dart", ".cs", ".csx", ".js", ".ts"}
# Single-line: #  (no multi-line)
HASH_STYLE_EXTS = {".py", ".sh", ".yaml", ".yml", ".ps1", ".psm1", ".psd1", ".bat", ".cmd"}
# Multi-line only: /* */
CSS_STYLE_EXTS = {".css"}
# Multi-line: <!-- -->
HTML_STYLE_EXTS = {".html"}
# No comments (every non-empty line is code)
NO_COMMENT_EXTS = {".json"}


def _count_lines_c_style(lines: list[str]) -> int:
    """Count code lines for C-style comments: // single-line, /* */ multi-line."""
    code = 0
    in_multiline = False
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        line_content = stripped
        while "/*" in line_content:
            start_idx = line_content.index("/*")
            if "*/" in line_content[start_idx + 2:]:
                end_idx = line_content.index("*/", start_idx + 2) + 2
                line_content = line_content[:start_idx] + line_content[end_idx:]
            else:
                line_content = line_content[:start_idx]
                in_multiline = True
                break
        if in_multiline:
            if "*/" in stripped:
                end_idx = stripped.index("*/") + 2
                remaining = stripped[end_idx:].strip()
                in_multiline = False
                if remaining and not remaining.startswith("//"):
                    code += 1
            continue
        if line_content.strip() and not line_content.strip().startswith("//"):
            code += 1
    return code


def _count_lines_css_style(lines: list[str]) -> int:
    """Count code lines for CSS-style: /* */ multi-line comments only."""
    code = 0
    in_multiline = False
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        line_content = stripped
        while "/*" in line_content:
            start_idx = line_content.index("/*")
            if "*/" in line_content[start_idx + 2:]:
                end_idx = line_content.index("*/", start_idx + 2) + 2
                line_content = line_content[:start_idx] + line_content[end_idx:]
            else:
                line_content = line_content[:start_idx]
                in_multiline = True
                break
        if in_multiline:
            if "*/" in stripped:
                end_idx = stripped.index("*/") + 2
                remaining = stripped[end_idx:].strip()
                in_multiline = False
                if remaining:
                    code += 1
            continue
        if line_content.strip():
            code += 1
    return code


def _count_lines_html_style(lines: list[str]) -> int:
    """Count code lines for HTML-style: <!-- --> multi-line comments."""
    code = 0
    in_multiline = False
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        line_content = stripped
        while "<!--" in line_content:
            start_idx = line_content.index("<!--")
            if "-->" in line_content[start_idx + 4:]:
                end_idx = line_content.index("-->", start_idx + 4) + 3
                line_content = line_content[:start_idx] + line_content[end_idx:]
            else:
                line_content = line_content[:start_idx]
                in_multiline = True
                break
        if in_multiline:
            if "-->" in stripped:
                end_idx = stripped.index("-->") + 3
                remaining = stripped[end_idx:].strip()
                in_multiline = False
                if remaining:
                    code += 1
            continue
        if line_content.strip():
            code += 1
    return code


def _count_lines_hash_style(lines: list[str]) -> int:
    """Count code lines for hash-style: # single-line comments."""
    return sum(
        1 for line in lines
        if line.strip() and not line.lstrip().startswith("#")
    )


def count_lines_in_file(file_path: Path) -> tuple[int, int]:
    """Count total lines and non-comment code lines in a single text file."""
    try:
        text = file_path.read_text(encoding="utf-8", errors="ignore")
    except Exception as e:
        print(f"Error reading {file_path}: {e}")
        return 0, 0

    lines = text.splitlines()
    total = len(lines)

    # Handle trailing newline: don't count an empty last line
    if text.endswith("\n") and lines and lines[-1] == "":
        lines = lines[:-1]
        total = len(lines)

    ext = file_path.suffix.lower()

    if ext in C_STYLE_EXTS:
        code = _count_lines_c_style(lines)
    elif ext in HASH_STYLE_EXTS:
        code = _count_lines_hash_style(lines)
    elif ext in CSS_STYLE_EXTS:
        code = _count_lines_css_style(lines)
    elif ext in HTML_STYLE_EXTS:
        code = _count_lines_html_style(lines)
    elif ext in NO_COMMENT_EXTS:
        code = sum(1 for line in lines if line.strip())
    else:
        # Default: treat as hash-style (# comments)
        code = _count_lines_hash_style(lines)

    return total, code


def _get_git_files(root_dir: Path) -> list[str] | None:
    """Return list of relative file paths from git ls-files, or None if not a git repo."""
    try:
        result = subprocess.run(
            ["git", "-C", str(root_dir), "ls-files", "--cached", "--others", "--exclude-standard"],
            capture_output=True, text=True, check=True,
        )
        files = [p.strip() for p in result.stdout.splitlines() if p.strip()]
        return files
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None


def count_lines_in_directory(
    root_dir: Path, extensions: list[str], verbose: bool = False
) -> dict[str, dict[str, int]]:
    """Count lines for given extensions under root_dir, respecting .gitignore."""
    stats: dict[str, dict[str, int]] = {
        ext: {"files": 0, "total": 0, "code": 0} for ext in extensions
    }
    excluded_count = {ext: 0 for ext in extensions}

    ext_set = {f".{e}" for e in extensions}

    git_files = _get_git_files(root_dir)
    if git_files is not None:
        # Use git ls-files (respects .gitignore)
        for rel in git_files:
            file_path = root_dir / rel
            if not file_path.is_file():
                continue
            ext = file_path.suffix.lower()
            if ext not in ext_set:
                continue
            # Also skip generated files
            if _is_generated_file(file_path):
                excluded_count[ext.lstrip(".")] += 1
                if verbose:
                    print(f"[EXCLUDED] {file_path.relative_to(root_dir)}")
                continue
            ext_key = ext.lstrip(".")
            total, code = count_lines_in_file(file_path)
            s = stats[ext_key]
            s["files"] += 1
            s["total"] += total
            s["code"] += code
            if verbose:
                print(f"[COUNTED] {file_path.relative_to(root_dir)}: {total} total, {code} code")
    else:
        # Fallback: manual rglob with exclusion list (not a git repo)
        print("[WARN] Not a git repository; .gitignore will not be respected.")
        for ext in extensions:
            pattern = f"*.{ext}"
            for file_path in root_dir.rglob(pattern):
                if not file_path.is_file():
                    continue
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
        description="Count lines of code in the repository."
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
        "--javascript", "--js", action="store_true", dest="javascript", help="Count only JavaScript files"
    )
    parser.add_argument(
        "--typescript", "--ts", action="store_true", dest="typescript", help="Count only TypeScript files"
    )
    parser.add_argument(
        "--powershell", "--ps", action="store_true", dest="powershell", help="Count only PowerShell files"
    )
    parser.add_argument(
        "--css", action="store_true", help="Count only CSS files"
    )
    parser.add_argument(
        "--html", action="store_true", help="Count only HTML files"
    )
    parser.add_argument(
        "--json", action="store_true", help="Count only JSON files"
    )
    parser.add_argument(
        "--shell", "--sh", action="store_true", dest="shell", help="Count only Shell script files"
    )
    parser.add_argument(
        "--yaml", action="store_true", help="Count only YAML files"
    )
    parser.add_argument(
        "--batch", action="store_true", dest="batch", help="Count only Batch script files"
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true", help="Show detailed output (files being counted/excluded)"
    )
    args = parser.parse_args()

    # Map CLI flags to extensions
    flag_to_ext: dict[str, list[str]] = {
        "python": ["py"],
        "dart": ["dart"],
        "csharp": ["cs"],
        "javascript": ["js"],
        "typescript": ["ts"],
        "powershell": ["ps1", "psm1", "psd1"],
        "css": ["css"],
        "html": ["html"],
        "json": ["json"],
        "shell": ["sh"],
        "yaml": ["yaml", "yml"],
        "batch": ["bat", "cmd"],
    }

    extensions: list[str] = []
    for flag, exts in flag_to_ext.items():
        if getattr(args, flag):
            extensions.extend(exts)

    if not extensions:
        # Default: count all supported languages
        extensions = [
            "py", "dart", "cs",
            "js", "ts",
            "ps1", "psm1", "psd1",
            "css", "html", "json",
            "sh", "yaml", "yml",
            "bat", "cmd",
        ]

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
        "js": "JavaScript",
        "ts": "TypeScript",
        "ps1": "PowerShell",
        "psm1": "PowerShell",
        "psd1": "PowerShell",
        "css": "CSS",
        "html": "HTML",
        "json": "JSON",
        "sh": "Shell",
        "yaml": "YAML",
        "yml": "YAML",
        "bat": "Batch",
        "cmd": "Batch",
    }

    # Aggregate stats by language display name (extensions > same lang merge)
    aggregated: dict[str, dict[str, int]] = {}
    lang_order: list[str] = []  # preserve first-seen order
    for ext in extensions:
        info = stats.get(ext, {"files": 0, "total": 0, "code": 0})
        if info["files"] == 0:
            continue
        lang_name = lang_display_names.get(ext, ext.upper())
        if lang_name not in aggregated:
            aggregated[lang_name] = {"files": 0, "total": 0, "code": 0}
            lang_order.append(lang_name)
        aggregated[lang_name]["files"] += info["files"]
        aggregated[lang_name]["total"] += info["total"]
        aggregated[lang_name]["code"] += info["code"]

    for lang_name in lang_order:
        info = aggregated[lang_name]
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

