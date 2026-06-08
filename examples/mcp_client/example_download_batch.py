"""Example: download results from multiple task IDs into a single ZIP.

Usage:
    python examples/mcp_client/example_download_batch.py <task_id_1> [task_id_2 ...] [--file-type TYPE] [--host HOST] [--port PORT]

Examples:
    python examples/mcp_client/example_download_batch.py abc123 def456
    python examples/mcp_client/example_download_batch.py abc123 def456 --file-type html
    python examples/mcp_client/example_download_batch.py abc123 --file-type md_zip

Available file types: target, docx, md, html, pdf, txt, md_zip
"""

import argparse
import asyncio
import base64
import json
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from mcp_client import connect


async def main() -> int:
    parser = argparse.ArgumentParser(description="Batch download task results")
    parser.add_argument("task_ids", nargs="+", help="Task IDs to download")
    parser.add_argument("--file-type", default="target",
                        help="Output format (default: target)")
    parser.add_argument("--host", default="127.0.0.1", help="MCP server host")
    parser.add_argument("--port", type=int, default=8100, help="MCP server port")
    parser.add_argument("--output", "-o", default=None,
                        help="Output ZIP path (default: auto-generated)")
    args = parser.parse_args()

    url = f"http://{args.host}:{args.port}/mcp"

    print(f"Downloading {len(args.task_ids)} tasks as '{args.file_type}'...")
    for tid in args.task_ids:
        print(f"  - {tid}")

    async with connect(url) as client:
        result = await client.batch_download(args.task_ids, args.file_type)

    if not result.get("success"):
        print("FAILED:", result.get("message"))
        return 1

    raw = base64.b64decode(result["file_content"])

    # Determine output path
    if args.output:
        out_path = Path(args.output)
    else:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        out_path = Path(f"batch_download_{args.file_type}_{timestamp}.zip")
    out_path.write_bytes(raw)
    print(f"\nSAVED {out_path}  ({out_path.stat().st_size} bytes)")

    # Print manifest
    manifest = result.get("manifest", {})
    if manifest:
        print(f"\nManifest ({len(manifest)} tasks):")
        for tid, info in manifest.items():
            status = info.get("status", "?")
            detail = info.get("file") or info.get("reason", "")
            print(f"  {tid}: {status}  {detail}")

    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
