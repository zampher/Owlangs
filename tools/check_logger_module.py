#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

"""
Check that all logger calls use (module, message) with a LogModule.

Scans Python files under a given root (default: backend), parses AST,
finds calls to logger.debug/info/warning/error/trace/success (and
unified_logger, self.logger, config.logger, etc.), and reports calls
where the first argument is not clearly a LogModule (e.g. a string),
so they can be fixed to use logger.METHOD(LogModule.XXX, "message").

Usage:
  python tools/check_logger_module.py [--root backend] [--strict]
  From repo root: python -m tools.check_logger_module
  From backend:   python ../tools/check_logger_module.py --root .
"""

import ast
import argparse
import sys
from pathlib import Path
from typing import List, Tuple

# Logger method names we care about (unified_logger / UnifiedLogger API)
LOG_METHODS = frozenset({"debug", "info", "warning", "error", "trace", "success", "log", "critical"})

# Attribute names that indicate a logger (e.g. logger, unified_logger, self.logger)
LOGGER_ATTR_NAMES = frozenset({"logger", "unified_logger", "log"})


def _is_logger_receiver(node: ast.AST) -> bool:
    """True if this node is a logger-like receiver (logger, unified_logger, self.logger, config.logger)."""
    if isinstance(node, ast.Name):
        return node.id in LOGGER_ATTR_NAMES
    if isinstance(node, ast.Attribute):
        # self.logger, config.logger, etc.
        return node.attr in LOGGER_ATTR_NAMES
    return False


def _first_arg_is_log_module(args: list) -> Tuple[bool, str]:
    """
    Check if the first positional argument is a LogModule (e.g. LogModule.SYSTEM).
    Returns (is_ok, reason).
    """
    if not args:
        return False, "no arguments"
    first = args[0]
    # LogModule.SOMETHING -> ast.Attribute(value=Name(LogModule), attr=SOMETHING)
    if isinstance(first, ast.Attribute):
        if isinstance(first.value, ast.Name) and first.value.id == "LogModule":
            return True, "LogModule.%s" % first.attr
        # Could be e.g. self.some_module_attr; we treat as uncertain
        return False, "first arg is attribute but not LogModule.XXX"
    if isinstance(first, ast.Name):
        # Variable as first arg: could be a LogModule value; we cannot know without execution
        return False, "first arg is variable '%s' (ensure it is LogModule)" % first.id
    if isinstance(first, ast.Constant):
        if isinstance(first.value, str):
            return False, "first arg is string literal (missing module)"
        return False, "first arg is constant (expected LogModule)"
    if isinstance(first, ast.JoinedStr):
        return False, "first arg is f-string (missing module)"
    if isinstance(first, ast.Call):
        return False, "first arg is function call (missing module)"
    if isinstance(first, ast.BinOp):
        return False, "first arg is expression (missing module)"
    # Subscript, Lambda, etc.
    return False, "first arg is %s (expected LogModule)" % type(first).__name__


def _get_call_name(node: ast.Attribute) -> str:
    """Return full call name like 'logger.debug' or 'self.logger.info' for reporting."""
    if isinstance(node.value, ast.Name):
        return node.value.id + "." + node.attr
    if isinstance(node.value, ast.Attribute):
        return _get_call_name(node.value) + "." + node.attr
    return "?." + node.attr


# In logger/logger.py, I18nLogger and UnifiedLogger call the underlying logging.Logger
# with .log(level, message), which is the standard API. Exclude those line numbers.
LOGGER_PY_EXCLUDED_LINES = frozenset({440, 443, 643})


def check_file(path: Path, root: Path) -> List[Tuple[int, str, str]]:
    """
    Parse a Python file and find logger calls that lack a clear LogModule first arg.
    Returns list of (line_no, call_name, reason).
    """
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except Exception as e:
        return [(-1, "", "read error: %s" % e)]
    try:
        tree = ast.parse(text)
    except SyntaxError as e:
        return [(-1, "", "syntax error: %s" % e)]

    issues = []
    # Exclude internal uses of raw Logger.log(level, msg) in logger/logger.py
    try:
        rel = path.relative_to(root)
        is_logger_py = rel.parts == ("logger", "logger.py")
    except ValueError:
        is_logger_py = False

    class Visitor(ast.NodeVisitor):
        def visit_Call(self, node: ast.Call):
            if isinstance(node.func, ast.Attribute):
                if node.func.attr not in LOG_METHODS:
                    self.generic_visit(node)
                    return
                if not _is_logger_receiver(node.func.value):
                    self.generic_visit(node)
                    return
                if is_logger_py and node.lineno in LOGGER_PY_EXCLUDED_LINES:
                    self.generic_visit(node)
                    return
                call_name = _get_call_name(node.func)
                ok, reason = _first_arg_is_log_module(node.args)
                if not ok:
                    issues.append((node.lineno, call_name, reason))
            self.generic_visit(node)

    Visitor().visit(tree)
    return issues


def main():
    parser = argparse.ArgumentParser(
        description="Check that logger calls use (LogModule, message)."
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parent.parent / "backend",
        help="Root directory to scan for .py files (default: backend)",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Treat variable-as-first-arg as pass (default: report as uncertain)",
    )
    parser.add_argument(
        "--exclude",
        type=str,
        default="__pycache__,.venv,venv,.git",
        help="Comma-separated dirs to exclude (default: __pycache__,.venv,venv,.git)",
    )
    args = parser.parse_args()
    root = args.root.resolve()
    exclude = set(d.strip() for d in args.exclude.split(",") if d.strip())

    if not root.is_dir():
        print("Error: root is not a directory: %s" % root, file=sys.stderr)
        sys.exit(2)

    py_files = []
    for p in root.rglob("*.py"):
        if any(part in p.parts for part in exclude):
            continue
        py_files.append(p)

    total_issues = 0
    files_with_issues = 0
    for path in sorted(py_files):
        rel = path.relative_to(root) if root != path else path.name
        issues = check_file(path, root)
        if not issues:
            continue
        files_with_issues += 1
        total_issues += len(issues)
        print("%s" % rel)
        for line_no, call_name, reason in issues:
            if line_no > 0:
                print("  L%d  %s  -> %s" % (line_no, call_name, reason))
            else:
                print("  %s" % reason)
        print()

    if total_issues:
        print("Total: %d potential issue(s) in %d file(s)." % (total_issues, files_with_issues))
        print("Fix by using e.g. logger.debug(LogModule.SYSTEM, 'message') instead of logger.debug('message').")
        sys.exit(1)
    print("All checked logger calls appear to pass a module (LogModule.XXX) as first argument.")
    sys.exit(0)


if __name__ == "__main__":
    main()
