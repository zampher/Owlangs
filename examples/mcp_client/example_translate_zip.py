"""Example: translate all supported files in a ZIP archive in batch.

Usage:
    python examples/mcp_client/example_translate_zip.py <zip_path> [to_lang] [--host HOST] [--port PORT]

Examples:
    python examples/mcp_client/example_translate_zip.py documents.zip "Chinese"
    python examples/mcp_client/example_translate_zip.py batch.zip "Japanese" --host 192.168.1.100
"""

import argparse
import asyncio
import base64
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from mcp_client import connect, poll_until_done


async def main() -> int:
    parser = argparse.ArgumentParser(description="Batch translate files in a ZIP")
    parser.add_argument("zip", help="Path to the ZIP file")
    parser.add_argument("to_lang", nargs="?", default="Chinese",
                        help="Target language (default: Chinese)")
    parser.add_argument("--host", default="127.0.0.1", help="MCP server host")
    parser.add_argument("--port", type=int, default=8100, help="MCP server port")
    args = parser.parse_args()

    zip_path = Path(args.zip)
    if not zip_path.exists():
        print(f"ZIP not found: {zip_path}")
        return 1

    url = f"http://{args.host}:{args.port}/mcp"

    async with connect(url) as client:
        # ── 1. Submit batch translation ──
        print(f"Submitting ZIP: {zip_path.name} -> {args.to_lang}")
        result = await client.batch_zip(str(zip_path), args.to_lang)
        print("Submit:", json.dumps(result, ensure_ascii=False, indent=2))

        if not result.get("success"):
            print("FAILED:", result.get("message"))
            return 1

        tasks = result.get("tasks", [])
        if not tasks:
            print("No supported files found in the ZIP")
            return 1

        print(f"\nSubmitted {len(tasks)} tasks:")
        for t in tasks:
            print(f"  {t['task_id']}  {t['file_name']}")

        # ── 2. Poll all tasks concurrently ──
        async def poll_one(t: dict) -> dict:
            st = await poll_until_done(client, t["task_id"])
            return {"task_id": t["task_id"], "file_name": t["file_name"],
                    "status": st.get("status")}

        print("\nPolling all tasks...")
        results = await asyncio.gather(*[poll_one(t) for t in tasks])

        completed = [r for r in results if r["status"] == "completed"]
        failed = [r for r in results if r["status"] != "completed"]
        print(f"\nCompleted: {len(completed)}  |  Failed: {len(failed)}")
        for r in results:
            print(f"  {r['task_id']}: {r['status']}  ({r['file_name']})")

        if not completed:
            print("No tasks completed successfully")
            return 1

        # ── 3. Batch download ──
        task_ids = [r["task_id"] for r in completed]
        print(f"\nDownloading {len(task_ids)} results as ZIP...")
        dl = await client.batch_download(task_ids, file_type="target")
        if dl.get("success"):
            out_dir = zip_path.parent / f"{zip_path.stem}_results"
            out_dir.mkdir(exist_ok=True)
            out_path = out_dir / "batch_results.zip"
            out_path.write_bytes(base64.b64decode(dl["file_content"]))
            print(f"SAVED {out_path}  ({out_path.stat().st_size} bytes)")
        else:
            print("Batch download failed:", dl.get("message"))

        print(f"\nTask IDs: {json.dumps(task_ids)}")

    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
