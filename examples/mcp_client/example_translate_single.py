"""Example: translate a single file and download the result.

Usage:
    python examples/mcp_client/example_translate_single.py <file_path> [to_lang] [--host HOST] [--port PORT]

Examples:
    python examples/mcp_client/example_translate_single.py my_doc.pdf "Chinese"
    python examples/mcp_client/example_translate_single.py report.docx "Japanese" --host 192.168.1.100
"""

import argparse
import asyncio
import base64
import json
import sys
from pathlib import Path

# Add parent to sys.path so we can import mcp_client.py
sys.path.insert(0, str(Path(__file__).resolve().parent))
from mcp_client import connect, poll_until_done


async def main() -> int:
    parser = argparse.ArgumentParser(description="Translate a single file")
    parser.add_argument("file", help="Path to the file to translate")
    parser.add_argument("to_lang", nargs="?", default="Chinese",
                        help="Target language (default: Chinese)")
    parser.add_argument("--host", default="127.0.0.1", help="MCP server host")
    parser.add_argument("--port", type=int, default=8100, help="MCP server port")
    args = parser.parse_args()

    file_path = Path(args.file)
    if not file_path.exists():
        print(f"File not found: {file_path}")
        return 1

    url = f"http://{args.host}:{args.port}/mcp"

    async with connect(url) as client:
        # ── 1. Submit translation ──
        print(f"Submitting: {file_path.name} -> {args.to_lang}")
        result = await client.translate(str(file_path), args.to_lang)
        print("Submit:", json.dumps(result, ensure_ascii=False, indent=2))

        if not result.get("task_started"):
            print("FAILED to start task")
            return 1

        task_id = result["task_id"]
        print(f"\nTask ID: {task_id}")

        # ── 2. Poll until done ──
        print("Polling...")
        status = await poll_until_done(client, task_id)

        if status.get("status") != "completed":
            print(f"Task failed: {status.get('status')}")
            if status.get("error"):
                print(f"Error: {status['error']}")
            return 2

        print(f"Completed ({status.get('progress')}%)")

        # ── 3. Download results ──
        out_dir = file_path.parent / f"{file_path.stem}_translated"
        out_dir.mkdir(exist_ok=True)

        for file_type in ("docx", "md", "html", "target"):
            dl = await client.download(task_id, file_type)
            if not dl.get("success"):
                print(f"  SKIP {file_type}: {dl.get('message')}")
                continue
            raw = base64.b64decode(dl["file_content"])
            name = dl.get("file_name", f"{file_path.stem}.{file_type}")
            dst = out_dir / name
            dst.write_bytes(raw)
            print(f"  SAVED {dst}  ({dst.stat().st_size} bytes)")

        print(f"\nDone. Files saved to: {out_dir}/")

    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
