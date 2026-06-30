#!/usr/bin/env python3
"""Owlangs CLI — Command-line interface for translation & document conversion.

Usage:
    owlangs translate <file> --to <lang> [options]
    owlangs convert <file> [options]
    owlangs batch <zip> --to <lang> [options]
    owlangs status <task_id>
    owlangs download <task_id> --type <fmt> --output <path>
    owlangs cancel <task_id>
    owlangs platform list
    owlangs formats
    owlangs glossary list
    owlangs glossary search <query>

Examples:
    owlangs translate report.pdf --to Japanese
    owlangs convert invoice.xlsx --output ./invoice.docx
    owlangs batch docs.zip --to Chinese --output ./translated/
    owlangs status <task_id>
    owlangs download <task_id> --type docx --output result.docx
    owlangs platform list --json
"""

# SPDX-FileCopyrightText: 2025 QinHan
# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

import argparse
import asyncio
import base64
import json
import os
import sys
import textwrap
from pathlib import Path
from typing import Any, Dict, List, Optional

# Ensure UTF-8 output on Windows
os.environ.setdefault("PYTHONIOENCODING", "utf-8")
os.environ.setdefault("LC_ALL", "en_US.UTF-8")
os.environ.setdefault("LANG", "en_US.UTF-8")

# Add backend to path (same pattern as backend/cli.py)
backend_dir = Path(__file__).resolve().parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

# Lazy import service_layer to avoid heavy import at startup
_service_layer = None


def _get_service_layer():
    global _service_layer
    if _service_layer is None:
        from backend.mcp_server import service_layer as sl
        _service_layer = sl
    return _service_layer


# ── Exit codes ───────────────────────────────────────────────────────────────
EXIT_SUCCESS = 0
EXIT_ARG_ERROR = 1
EXIT_TASK_FAILED = 2
EXIT_TIMEOUT = 3
EXIT_INTERNAL_ERROR = 4


# ── Config helpers ───────────────────────────────────────────────────────────

def _get_config_path() -> Path:
    if sys.platform == "win32":
        config_dir = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local")) / "Owlangs"
    elif sys.platform == "darwin":
        config_dir = Path.home() / "Library" / "Application Support" / "Owlangs"
    else:
        config_dir = Path.home() / ".config" / "Owlangs"
    config_dir.mkdir(parents=True, exist_ok=True)
    return config_dir / "config.toml"


def _load_config() -> Dict[str, Any]:
    """Load user config from ~/.config/Owlangs/config.toml if present."""
    config_path = _get_config_path()
    if not config_path.exists():
        return {}
    try:
        import tomllib
        with config_path.open("rb") as f:
            return tomllib.load(f)
    except ImportError:
        try:
            import tomli as tomllib  # type: ignore
            with config_path.open("rb") as f:
                return tomllib.load(f)
        except ImportError:
            return {}
    except Exception:
        return {}


# Global config cache (loaded once)
_USER_CONFIG: Optional[Dict[str, Any]] = None


def _get_user_config() -> Dict[str, Any]:
    global _USER_CONFIG
    if _USER_CONFIG is None:
        _USER_CONFIG = _load_config()
    return _USER_CONFIG


def _config_value(key: str, fallback: Any = None) -> Any:
    """Get a value from user config with dot-notation key, e.g. 'translate.default_lang'."""
    cfg = _get_user_config()
    parts = key.split(".")
    for part in parts:
        if isinstance(cfg, dict) and part in cfg:
            cfg = cfg[part]
        else:
            return fallback
    return cfg


def _output_suffix_for_cli(args_suffix: Optional[str], *, convert: bool) -> str:
    """Resolve local output-dir suffix: CLI flag > config.toml > app_config.json > default."""
    if args_suffix is not None:
        return args_suffix
    cfg_key = "converter_output_suffix" if convert else "translator_output_suffix"
    default = "_converted" if convert else "_translated"
    cfg = _get_user_config()
    if isinstance(cfg, dict) and cfg_key in cfg:
        return str(cfg[cfg_key])
    try:
        from config import get_app_config

        app_cfg = get_app_config()
        value = getattr(app_cfg, cfg_key, None)
        if value is not None:
            return str(value)
    except Exception:
        pass
    return default


def _resolve_translate_options(args: argparse.Namespace) -> Dict[str, Any]:
    """Merge CLI flags with config.toml defaults (CLI wins when explicitly set)."""
    glossary = list(args.glossary) if args.glossary else None
    if not glossary:
        cfg_glossaries = _config_value("glossary.default_glossaries")
        if isinstance(cfg_glossaries, list) and cfg_glossaries:
            glossary = cfg_glossaries

    formats = args.formats
    if formats is None:
        cfg_formats = _config_value("translate.default_formats")
        formats = cfg_formats if isinstance(cfg_formats, list) and cfg_formats else [
            "target", "docx", "md", "html",
        ]

    return {
        "glossary": glossary,
        "formats": formats,
        "temperature": (
            args.temperature
            if args.temperature is not None
            else _config_value("translate.advanced.temperature", 0.3)
        ),
        "chunk_size": (
            args.chunk_size
            if args.chunk_size is not None
            else _config_value("translate.advanced.chunk_size", 0)
        ),
        "concurrent": (
            args.concurrent
            if args.concurrent is not None
            else _config_value("translate.advanced.concurrent", 3)
        ),
        "prompt_mode": args.prompt_mode or _config_value("translate.advanced.prompt_mode"),
        "prompt_style": args.prompt_style or _config_value("translate.advanced.prompt_style"),
    }


# ── Output helpers ───────────────────────────────────────────────────────────

def _out(data: Any, json_mode: bool):
    if json_mode:
        print(json.dumps(data, ensure_ascii=False, indent=None))
    else:
        print(data)


def _err(msg: str):
    print(msg, file=sys.stderr)


def _json_err(message: str, json_mode: bool, code: int = EXIT_INTERNAL_ERROR):
    if json_mode:
        _out({"success": False, "error": message}, True)
    else:
        _err(f"Error: {message}")
    return code


# ── File helpers ─────────────────────────────────────────────────────────────

def _require_file(path: str) -> Optional[Path]:
    p = Path(path)
    if not p.exists():
        return None
    return p.resolve()


def _safe_filename(name: str, file_type: str) -> str:
    """Ensure filename has correct extension for the file type."""
    p = Path(name)
    # Map file_type to expected extension
    ext_map = {
        "target": ".txt",
        "docx": ".docx",
        "md": ".md",
        "html": ".html",
        "pdf": ".pdf",
        "txt": ".txt",
        "md_zip": ".zip",
    }
    expected_ext = ext_map.get(file_type, f".{file_type}")
    if p.suffix.lower() != expected_ext.lower():
        return f"{p.stem}{expected_ext}"
    return name


# ── Progress helpers ─────────────────────────────────────────────────────────

def _print_progress(status: str, progress: int, msg: str, first: bool = False):
    """Print an in-place progress line (if terminal supports it)."""
    line = f"  {status:12s} {progress:3d}%  {msg[:60]}"
    if sys.stdout.isatty():
        end = "\r" if not first else "\n"
        print(f"\r{line:<80}", end="", flush=True)
    else:
        print(line)


def _clear_progress():
    if sys.stdout.isatty():
        print("\r" + " " * 80 + "\r", end="")


# ── Polling helper ───────────────────────────────────────────────────────────

async def _poll_task(
    task_id: str,
    service_layer: Any,
    json_mode: bool,
    verbose: bool,
    max_retries: int = 360,
    interval: int = 10,
) -> Dict[str, Any]:
    for i in range(max_retries):
        status = await service_layer.get_task_status(task_id)
        st = status.get("status")
        progress = status.get("progress", 0)
        msg = (status.get("message") or "")[:100]

        if verbose and not json_mode:
            print(f"  [{i:3d}] {st:12s} {progress:3d}%  {msg}")
        elif not json_mode and i == 0:
            _print_progress(st, progress, msg, first=True)
        elif not json_mode and sys.stdout.isatty():
            _print_progress(st, progress, msg)

        if st == "completed":
            if not json_mode and sys.stdout.isatty():
                _clear_progress()
            return status
        if st in ("failed", "cancelled"):
            if not json_mode and sys.stdout.isatty():
                _clear_progress()
            return status

        if i < max_retries - 1:
            await asyncio.sleep(interval)

    if not json_mode and sys.stdout.isatty():
        _clear_progress()
    return {"status": "timeout", "task_id": task_id}


# ── Command handlers ─────────────────────────────────────────────────────────

async def cmd_translate(args: argparse.Namespace) -> int:
    sl = _get_service_layer()
    opts = _resolve_translate_options(args)

    # Resolve language: CLI arg > config > "Chinese"
    to_lang = args.to or _config_value("translate.default_lang", "Chinese")
    platform_id = args.platform or _config_value("translate.default_platform", "")

    # Handle stdin (-) or regular file
    if args.file == "-":
        file_name = args.file_name or "stdin.txt"
        source_stem = Path(file_name).stem
        if args.json:
            pass
        else:
            print(f"Translating: <stdin> -> {to_lang}")
        file_content = base64.b64encode(sys.stdin.buffer.read()).decode("utf-8")
        file_path = None
    else:
        file_path = _require_file(args.file)
        if file_path is None:
            return _json_err(f"File not found: {args.file}", args.json, EXIT_ARG_ERROR)
        file_name = file_path.name
        source_stem = file_path.stem
        file_content = None
        if args.json:
            pass
        else:
            print(f"Translating: {file_path.name} -> {to_lang}")

    if platform_id and not args.json:
        print(f"  Platform: {platform_id}")

    # Build platform config from selected platform
    base_url, api_key, model_id = "", "", ""
    if platform_id:
        plat = sl.get_platform_detail(platform_id)
        if plat:
            base_url = plat.get("url", "")
            api_key = plat.get("api_key", "")
            model_id = plat.get("model", "")

    result = await sl.translate_file(
        file_content=file_content,
        file_path=str(file_path) if file_path else None,
        file_name=file_name,
        to_lang=to_lang,
        base_url=base_url,
        api_key=api_key,
        model_id=model_id,
        glossary_ids=opts["glossary"],
        temperature=opts["temperature"],
        chunk_size=opts["chunk_size"],
        concurrent=opts["concurrent"],
        prompt_mode=opts["prompt_mode"] or None,
        prompt_style=opts["prompt_style"] or None,
        skip_translate=False,
    )

    if not result.get("task_started"):
        return _json_err(result.get("message", "Failed to start task"), args.json, EXIT_ARG_ERROR)

    task_id = result["task_id"]
    if args.json:
        _out({"success": True, "task_id": task_id, "status": "submitted"}, True)
    else:
        print(f"  Task ID: {task_id}")
        print("  Polling...")

    if args.no_wait:
        return EXIT_SUCCESS

    final = await _poll_task(task_id, sl, args.json, args.verbose)
    st = final.get("status")

    if st == "completed":
        if not args.json:
            print(f"  Completed ({final.get('progress', 100)}%)")
    elif st == "timeout":
        return _json_err("Polling timeout (60 minutes)", args.json, EXIT_TIMEOUT)
    else:
        return _json_err(
            final.get("error") or final.get("message") or f"Task {st}",
            args.json,
            EXIT_TASK_FAILED,
        )

    # Download results
    suffix = _output_suffix_for_cli(args.output_suffix, convert=False)
    out_dir = _resolve_output_dir(args.output, file_path, suffix, source_stem=source_stem)
    out_dir.mkdir(parents=True, exist_ok=True)

    downloaded = []
    for file_type in opts["formats"]:
        dl = await sl.download_result(task_id, file_type)
        if not dl.get("success"):
            if args.verbose and not args.json:
                print(f"  SKIP {file_type}: {dl.get('message')}")
            continue
        raw = base64.b64decode(dl["file_content"])
        name = _safe_filename(dl.get("file_name") or f"{source_stem}.{file_type}", file_type)
        dst = out_dir / name
        dst.write_bytes(raw)
        downloaded.append(str(dst))
        if not args.json:
            print(f"  SAVED {dst}  ({len(raw)} bytes)")

    if args.json:
        _out(
            {
                "success": True,
                "task_id": task_id,
                "status": "completed",
                "output_dir": str(out_dir),
                "files": downloaded,
            },
            True,
        )
    else:
        print(f"\nDone. Files saved to: {out_dir}/")

    return EXIT_SUCCESS


async def cmd_convert(args: argparse.Namespace) -> int:
    sl = _get_service_layer()
    file_path = _require_file(args.file)
    if file_path is None:
        return _json_err(f"File not found: {args.file}", args.json, EXIT_ARG_ERROR)

    if not args.json:
        print(f"Converting: {file_path.name}")

    result = await sl.convert_document(
        file_content=None,
        file_path=str(file_path),
        file_name=file_path.name,
        convert_engine=args.engine or None,
    )

    if not result.get("success"):
        return _json_err(result.get("message", "Failed to start conversion"), args.json, EXIT_ARG_ERROR)

    task_id = result["task_id"]
    if not args.json:
        print(f"  Task ID: {task_id}")
        print("  Polling...")

    if args.no_wait:
        if args.json:
            _out({"success": True, "task_id": task_id, "status": "submitted"}, True)
        return EXIT_SUCCESS

    final = await _poll_task(task_id, sl, args.json, args.verbose)
    st = final.get("status")

    if st == "completed":
        if not args.json:
            print(f"  Completed ({final.get('progress', 100)}%)")
    elif st == "timeout":
        return _json_err("Polling timeout", args.json, EXIT_TIMEOUT)
    else:
        return _json_err(
            final.get("error") or final.get("message") or f"Task {st}",
            args.json,
            EXIT_TASK_FAILED,
        )

    suffix = _output_suffix_for_cli(args.output_suffix, convert=True)
    out_dir = _resolve_output_dir(args.output, file_path, suffix)
    out_dir.mkdir(parents=True, exist_ok=True)

    downloaded = []
    for file_type in ("docx", "md", "target"):
        dl = await sl.download_result(task_id, file_type)
        if not dl.get("success"):
            if args.verbose and not args.json:
                print(f"  SKIP {file_type}: {dl.get('message')}")
            continue
        raw = base64.b64decode(dl["file_content"])
        # Ensure unique filename per format to avoid overwrites
        name = _safe_filename(dl.get("file_name") or f"{file_path.stem}.{file_type}", file_type)
        dst = out_dir / name
        dst.write_bytes(raw)
        downloaded.append(str(dst))
        if not args.json:
            print(f"  SAVED {dst}  ({len(raw)} bytes)")

    if args.json:
        _out(
            {
                "success": True,
                "task_id": task_id,
                "status": "completed",
                "output_dir": str(out_dir),
                "files": downloaded,
            },
            True,
        )
    else:
        print(f"\nDone. Files saved to: {out_dir}/")

    return EXIT_SUCCESS


async def cmd_batch(args: argparse.Namespace) -> int:
    sl = _get_service_layer()
    zip_path = _require_file(args.zip)
    if zip_path is None:
        return _json_err(f"ZIP not found: {args.zip}", args.json, EXIT_ARG_ERROR)

    to_lang = args.to or _config_value("translate.default_lang", "Chinese")

    if not args.json:
        print(f"Batch translating ZIP: {zip_path.name} -> {to_lang}")

    zip_content = base64.b64encode(zip_path.read_bytes()).decode("utf-8")
    result = await sl.translate_batch_zip(
        zip_content=zip_content,
        zip_file_name=zip_path.name,
        to_lang=to_lang,
    )

    if not result.get("success"):
        return _json_err(result.get("message", "Batch submission failed"), args.json, EXIT_ARG_ERROR)

    tasks = result.get("tasks", [])
    if not tasks:
        return _json_err("No supported files found in ZIP", args.json, EXIT_ARG_ERROR)

    if not args.json:
        print(f"  Submitted {len(tasks)} tasks:")
        for t in tasks:
            print(f"    {t['task_id']}  {t['file_name']}")

    if args.no_wait:
        if args.json:
            _out(
                {
                    "success": True,
                    "total": result.get("total", 0),
                    "submitted": result.get("submitted", 0),
                    "failed": result.get("failed", 0),
                    "tasks": tasks,
                },
                True,
            )
        return EXIT_SUCCESS

    async def poll_one(task_id: str) -> Dict[str, Any]:
        st = await _poll_task(task_id, sl, args.json, args.verbose)
        return {"task_id": task_id, "status": st.get("status")}

    if not args.json:
        print("\n  Polling all tasks...")

    poll_results = await asyncio.gather(*[poll_one(t["task_id"]) for t in tasks])

    completed = [r for r in poll_results if r["status"] == "completed"]
    failed = [r for r in poll_results if r["status"] != "completed"]

    if not args.json:
        print(f"\n  Completed: {len(completed)}  |  Failed: {len(failed)}")
        for r in poll_results:
            icon = "✓" if r["status"] == "completed" else "✗"
            print(f"    {icon} {r['task_id']}: {r['status']}")

    if not completed:
        return _json_err("No tasks completed successfully", args.json, EXIT_TASK_FAILED)

    task_ids = [r["task_id"] for r in completed]
    dl = await sl.download_batch_results(task_ids, file_type="target")

    out_dir = _resolve_output_dir(args.output, zip_path, "_results")
    out_path = out_dir / "batch_results.zip"
    if dl.get("success"):
        out_dir.mkdir(parents=True, exist_ok=True)
        raw = base64.b64decode(dl["file_content"])
        out_path.write_bytes(raw)
        if not args.json:
            print(f"\n  SAVED {out_path}  ({len(raw)} bytes)")
    else:
        return _json_err(dl.get("message", "Batch download failed"), args.json, EXIT_TASK_FAILED)

    partial = len(failed) > 0
    if args.json:
        _out(
            {
                "success": not partial,
                "partial": partial,
                "completed": len(completed),
                "failed": len(failed),
                "output_dir": str(out_dir),
                "zip": str(out_path),
                "task_ids": task_ids,
            },
            True,
        )

    return EXIT_TASK_FAILED if partial else EXIT_SUCCESS


async def cmd_status(args: argparse.Namespace) -> int:
    sl = _get_service_layer()
    status = await sl.get_task_status(args.task_id)
    _out(status, args.json)
    st = status.get("status")
    if st in ("failed", "cancelled"):
        return EXIT_TASK_FAILED
    return EXIT_SUCCESS


async def cmd_download(args: argparse.Namespace) -> int:
    sl = _get_service_layer()
    dl = await sl.download_result(args.task_id, args.type)
    if not dl.get("success"):
        return _json_err(dl.get("message", "Download failed"), args.json, EXIT_ARG_ERROR)

    raw = base64.b64decode(dl["file_content"])
    out_path = Path(args.output)

    # If output is a directory, auto-generate filename from server response
    if out_path.is_dir() or args.output.endswith(("/", "\\")):
        out_path.mkdir(parents=True, exist_ok=True)
        name = _safe_filename(dl.get("file_name") or f"{args.task_id}.{args.type}", args.type)
        out_path = out_path / name
    else:
        out_path.parent.mkdir(parents=True, exist_ok=True)

    out_path.write_bytes(raw)

    if args.json:
        _out(
            {
                "success": True,
                "file": str(out_path),
                "size": len(raw),
                "type": args.type,
            },
            True,
        )
    else:
        print(f"SAVED {out_path}  ({len(raw)} bytes)")

    return EXIT_SUCCESS


async def cmd_cancel(args: argparse.Namespace) -> int:
    sl = _get_service_layer()
    result = await sl.cancel_task(args.task_id)
    _out(result, args.json)
    return EXIT_SUCCESS if result.get("success") else EXIT_ARG_ERROR


def cmd_platform_list(args: argparse.Namespace) -> int:
    sl = _get_service_layer()
    platforms = sl.list_platforms()
    if args.json:
        _out({"success": True, "platforms": platforms}, True)
    else:
        print(f"Available platforms ({len(platforms)}):")
        for p in platforms:
            default_mark = " (default)" if p.get("is_default") else ""
            print(f"  {p['id']}: {p['name']}{default_mark}")
            print(f"    model: {p.get('model', 'N/A')}, protocol: {p.get('api_protocol', 'N/A')}")
    return EXIT_SUCCESS


def cmd_formats(args: argparse.Namespace) -> int:
    sl = _get_service_layer()
    formats = sl.list_supported_formats()
    if args.json:
        _out({"success": True, "formats": formats}, True)
    else:
        print(f"Supported formats ({len(formats)}):")
        for f in formats:
            ext = f['extension'].lstrip(".")
            print(f"  .{ext:8s}  {f['workflow_type']:12s}  {f.get('description', '')}")
    return EXIT_SUCCESS


def cmd_glossary_list(args: argparse.Namespace) -> int:
    sl = _get_service_layer()
    glossaries = sl.list_glossaries(scope=args.scope)
    if args.json:
        _out({"success": True, "glossaries": glossaries}, True)
    else:
        print(f"Glossaries ({len(glossaries)}):")
        for g in glossaries:
            print(f"  {g['id']}: {g['name']} ({g.get('item_count', 0)} terms)")
    return EXIT_SUCCESS


def cmd_glossary_search(args: argparse.Namespace) -> int:
    sl = _get_service_layer()
    results = sl.search_glossary(query=args.query, glossary_id=args.glossary, limit=args.limit)
    if args.json:
        _out({"success": True, "results": results}, True)
    else:
        print(f"Search results ({len(results)}):")
        for r in results:
            print(f"  {r['src']} -> {r['dst']}  [{r.get('category', 'N/A')}]")
    return EXIT_SUCCESS


def cmd_config_init(args: argparse.Namespace) -> int:
    config_path = _get_config_path()
    if config_path.exists() and not args.force:
        if args.json:
            _out({"success": False, "error": f"Config already exists: {config_path}. Use --force to overwrite."}, True)
        else:
            _err(f"Config already exists: {config_path}")
            _err("Use --force to overwrite.")
        return EXIT_ARG_ERROR

    default_config = '''# Owlangs CLI configuration file
# Location: {path}

[translate]
default_lang = "Chinese"
# default_platform = "deepseek"
# default_formats = ["target", "docx", "md"]

[translate.advanced]
# temperature = 0.3
# chunk_size = 8000
# concurrent = 3
# prompt_mode = "standard"
# prompt_style = "detailed"

[glossary]
# default_glossaries = ["medical", "legal"]
'''.format(path=config_path)

    config_path.write_text(default_config, encoding="utf-8")
    if args.json:
        _out({"success": True, "path": str(config_path)}, True)
    else:
        print(f"Config created: {config_path}")
    return EXIT_SUCCESS


def cmd_config_show(args: argparse.Namespace) -> int:
    config_path = _get_config_path()
    exists = config_path.exists()
    if args.json:
        _out({"path": str(config_path), "exists": exists}, True)
    else:
        print(f"Config path: {config_path}")
        print(f"Exists: {exists}")
    return EXIT_SUCCESS


# ── Utility helpers ──────────────────────────────────────────────────────────

def _resolve_output_dir(
    output: Optional[str],
    source: Optional[Path],
    suffix: str,
    *,
    source_stem: Optional[str] = None,
) -> Path:
    if output:
        return Path(output)
    if source is not None:
        return source.parent / f"{source.stem}{suffix}"
    stem = source_stem or "stdin"
    return Path.cwd() / f"{stem}{suffix}"


# ── Argument parser ──────────────────────────────────────────────────────────

def build_parser() -> argparse.ArgumentParser:
    from backend import __version__

    common_parser = argparse.ArgumentParser(add_help=False)
    common_parser.add_argument("--json", action="store_true", help="Output JSON (machine-readable)")
    common_parser.add_argument("-v", "--verbose", action="store_true", help="Verbose output")

    parser = argparse.ArgumentParser(
        prog="owlangs",
        description="Owlangs CLI — Translate and convert documents from the command line.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        parents=[common_parser],
        epilog=textwrap.dedent("""\
            Examples:
              owlangs translate report.pdf --to Japanese
              owlangs convert invoice.xlsx --output ./invoice.docx
              owlangs batch docs.zip --to Chinese
              owlangs status <task_id>
              owlangs download <task_id> --type docx --output result.docx
              owlangs --json platform list
              cat doc.md | owlangs translate - --to Chinese
        """),
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # ── translate ──
    p_translate = subparsers.add_parser("translate", help="Translate a single file", parents=[common_parser])
    p_translate.add_argument("file", help="Path to the file to translate (use '-' for stdin)")
    p_translate.add_argument("--file-name", help="Filename when reading from stdin (default: stdin.txt)")
    p_translate.add_argument("--to", help="Target language (e.g. Chinese, Japanese). Default from config.")
    p_translate.add_argument("--output", "-o", help="Output directory (default: <file>_translated/)")
    p_translate.add_argument(
        "--output-suffix",
        default=None,
        help="Filename suffix for output directory (default from config: _translated)",
    )
    p_translate.add_argument(
        "--formats",
        nargs="+",
        default=None,
        help="Download formats (default: from config or target docx md html)",
    )
    p_translate.add_argument("--no-wait", action="store_true", help="Submit and exit without polling")
    # Advanced options
    p_translate.add_argument("--platform", help="Platform ID to use for translation")
    p_translate.add_argument("--glossary", nargs="+", help="Glossary ID(s) to apply")
    p_translate.add_argument(
        "--temperature",
        type=float,
        default=None,
        help="LLM temperature (default: from config or 0.3)",
    )
    p_translate.add_argument(
        "--chunk-size",
        type=int,
        default=None,
        help="Chunk size in tokens (default: from config or 0 = auto)",
    )
    p_translate.add_argument(
        "--concurrent",
        type=int,
        default=None,
        help="Concurrent chunks (default: from config or 3)",
    )
    p_translate.add_argument("--prompt-mode", help="Prompt mode (e.g. standard, academic)")
    p_translate.add_argument("--prompt-style", help="Prompt style (e.g. concise, detailed)")
    p_translate.set_defaults(func=cmd_translate)

    # ── convert ──
    p_convert = subparsers.add_parser("convert", help="Convert file format without translation", parents=[common_parser])
    p_convert.add_argument("file", help="Path to the file to convert")
    p_convert.add_argument("--output", "-o", help="Output directory (default: <file>_converted/)")
    p_convert.add_argument(
        "--output-suffix",
        default=None,
        help="Filename suffix for output directory (default from config: _converted)",
    )
    p_convert.add_argument("--engine", help="Conversion engine")
    p_convert.add_argument("--no-wait", action="store_true", help="Submit and exit without polling")
    p_convert.set_defaults(func=cmd_convert)

    # ── batch ──
    p_batch = subparsers.add_parser("batch", help="Batch translate files in a ZIP", parents=[common_parser])
    p_batch.add_argument("zip", help="Path to the ZIP file")
    p_batch.add_argument("--to", help="Target language. Default from config.")
    p_batch.add_argument("--output", "-o", help="Output directory (default: <zip>_results/)")
    p_batch.add_argument("--no-wait", action="store_true", help="Submit and exit without polling")
    p_batch.set_defaults(func=cmd_batch)

    # ── status ──
    p_status = subparsers.add_parser("status", help="Check task status", parents=[common_parser])
    p_status.add_argument("task_id", help="Task ID")
    p_status.set_defaults(func=cmd_status)

    # ── download ──
    p_download = subparsers.add_parser("download", help="Download task result", parents=[common_parser])
    p_download.add_argument("task_id", help="Task ID")
    p_download.add_argument("--type", required=True, help="File type (target, docx, md, html, pdf, txt)")
    p_download.add_argument("--output", "-o", required=True, help="Output file or directory path")
    p_download.set_defaults(func=cmd_download)

    # ── cancel ──
    p_cancel = subparsers.add_parser("cancel", help="Cancel a running task", parents=[common_parser])
    p_cancel.add_argument("task_id", help="Task ID")
    p_cancel.set_defaults(func=cmd_cancel)

    # ── platform ──
    p_platform = subparsers.add_parser("platform", help="Platform management", parents=[common_parser])
    platform_sub = p_platform.add_subparsers(dest="platform_cmd")
    p_plat_list = platform_sub.add_parser("list", help="List available platforms", parents=[common_parser])
    p_plat_list.set_defaults(func=cmd_platform_list)

    # ── formats ──
    p_formats = subparsers.add_parser("formats", help="List supported file formats", parents=[common_parser])
    p_formats.set_defaults(func=cmd_formats)

    # ── glossary ──
    p_glossary = subparsers.add_parser("glossary", help="Glossary management", parents=[common_parser])
    glossary_sub = p_glossary.add_subparsers(dest="glossary_cmd")
    p_gloss_list = glossary_sub.add_parser("list", help="List glossaries", parents=[common_parser])
    p_gloss_list.add_argument("--scope", default="all", help="Scope: all or global")
    p_gloss_list.set_defaults(func=cmd_glossary_list)
    p_gloss_search = glossary_sub.add_parser("search", help="Search glossary terms", parents=[common_parser])
    p_gloss_search.add_argument("query", help="Search query")
    p_gloss_search.add_argument("--glossary", help="Glossary ID to search in")
    p_gloss_search.add_argument("--limit", type=int, default=20, help="Max results")
    p_gloss_search.set_defaults(func=cmd_glossary_search)

    # ── config ──
    p_config = subparsers.add_parser("config", help="Configuration management", parents=[common_parser])
    config_sub = p_config.add_subparsers(dest="config_cmd")
    p_config_init = config_sub.add_parser("init", help="Create default config file", parents=[common_parser])
    p_config_init.add_argument("--force", action="store_true", help="Overwrite existing config")
    p_config_init.set_defaults(func=cmd_config_init)
    p_config_show = config_sub.add_parser("show", help="Show current config file path", parents=[common_parser])
    p_config_show.set_defaults(func=cmd_config_show)

    return parser


# ── Main entry point ─────────────────────────────────────────────────────────

def _merge_global_cli_flags(args: argparse.Namespace) -> argparse.Namespace:
    """Subparsers ignore global flags placed before the subcommand name.
    Scan sys.argv to detect these flags only before the subcommand,
    avoiding false matches in filenames or flag values."""
    argv = sys.argv[1:]  # skip program name
    # Find the first non-flag argument (the subcommand)
    try:
        sub_idx = next(i for i, a in enumerate(argv) if not a.startswith("-"))
    except StopIteration:
        return args  # no subcommand found

    prefix = argv[:sub_idx]
    if "--json" in prefix:
        args.json = True
    if "-v" in prefix or "--verbose" in prefix:
        args.verbose = True
    return args


def main() -> int:
    parser = build_parser()
    args = _merge_global_cli_flags(parser.parse_args())

    if not args.command:
        parser.print_help()
        return EXIT_ARG_ERROR

    func = getattr(args, "func", None)
    if func is None:
        parser.print_help()
        return EXIT_ARG_ERROR

    try:
        if asyncio.iscoroutinefunction(func):
            return asyncio.run(func(args))
        else:
            return func(args)
    except KeyboardInterrupt:
        if not args.json:
            _err("\nInterrupted by user")
        return EXIT_ARG_ERROR
    except Exception as e:
        if args.verbose:
            import traceback
            _err(traceback.format_exc())
        return _json_err(str(e), getattr(args, "json", False), EXIT_INTERNAL_ERROR)


if __name__ == "__main__":
    raise SystemExit(main())
