"""Standalone all-in-one demo: list platforms, translate, convert, batch ZIP.

Connects to the Owlangs MCP server via Streamable HTTP and runs through
various workflows to demonstrate the full API.

Requirements:
    pip install mcp httpx

Usage:
    python examples/mcp_client/mcp_client_example.py
    python examples/mcp_client/mcp_client_example.py --host 192.168.1.100 --port 8100
"""

import argparse
import asyncio
import base64
import json
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from mcp_client import connect, poll_until_done


async def demo_list_platforms(client) -> None:
    """List available translation platforms."""
    print("\n── Available platforms ──")
    platforms = await client.call("owlangs_list_platforms")
    print(json.dumps(platforms, ensure_ascii=False, indent=2))


async def demo_translate_single(client, file_path: str, to_lang: str):
    """Single file translation workflow."""
    print(f"\n{'='*60}")
    print(f"1. SINGLE FILE TRANSLATION: {file_path} -> {to_lang}")
    print(f"{'='*60}")

    result = await client.translate(file_path, to_lang)
    print("Submit:", json.dumps(result, ensure_ascii=False, indent=2))
    if not result.get("task_started"):
        return None

    task_id = result["task_id"]
    print(f"\nTask ID: {task_id}")

    print("Polling...")
    status = await poll_until_done(client, task_id)
    if status.get("status") != "completed":
        print(f"FAILED: {status.get('status')}")
        return None
    print(f"Completed ({status.get('progress')}%)")

    out_dir = Path(file_path).parent / f"{Path(file_path).stem}_translated"
    out_dir.mkdir(exist_ok=True)
    for ft in ("docx", "md", "html", "target"):
        dl = await client.download(task_id, ft)
        if dl.get("success"):
            dst = out_dir / (dl.get("file_name", f"{Path(file_path).stem}.{ft}"))
            dst.write_bytes(base64.b64decode(dl["file_content"]))
            print(f"  {ft} -> {dst}  ({dst.stat().st_size} bytes)")
        else:
            print(f"  {ft}: SKIP ({dl.get('message')})")

    print(f"\nTask ID: {task_id}")
    return task_id


async def demo_convert_single(client, file_path: str):
    """Single file format conversion."""
    print(f"\n{'='*60}")
    print(f"2. CONVERT: {file_path}")
    print(f"{'='*60}")

    result = await client.convert(file_path)
    print("Submit:", json.dumps(result, ensure_ascii=False, indent=2))
    if not result.get("success"):
        return None

    task_id = result["task_id"]
    print(f"\nTask ID: {task_id}")
    print("Polling...")
    status = await poll_until_done(client, task_id)
    if status.get("status") != "completed":
        print(f"FAILED: {status.get('status')}")
        return None

    print(f"Completed ({status.get('progress')}%)")
    dl = await client.download(task_id, "docx")
    if dl.get("success"):
        dst = Path(dl.get("file_name", f"{Path(file_path).stem}.docx"))
        dst.write_bytes(base64.b64decode(dl["file_content"]))
        print(f"  docx -> {dst}  ({dst.stat().st_size} bytes)")

    return task_id


async def demo_batch_zip(client, zip_path: str, to_lang: str):
    """ZIP batch translation workflow."""
    print(f"\n{'='*60}")
    print(f"3. ZIP BATCH: {zip_path} -> {to_lang}")
    print(f"{'='*60}")

    result = await client.batch_zip(zip_path, to_lang)
    print("Submit:", json.dumps(result, ensure_ascii=False, indent=2))
    if not result.get("success"):
        return []

    tasks = result.get("tasks", [])
    if not tasks:
        return []

    print(f"\nSubmitted {len(tasks)} tasks")

    async def poll_one(t: dict) -> dict:
        st = await poll_until_done(client, t["task_id"])
        return {"task_id": t["task_id"], "file_name": t["file_name"],
                "status": st.get("status")}

    print("Polling all tasks...")
    results = await asyncio.gather(*[poll_one(t) for t in tasks])
    completed = [r for r in results if r["status"] == "completed"]
    print(f"Completed: {len(completed)} / {len(tasks)}")

    if completed:
        task_ids = [r["task_id"] for r in completed]
        dl = await client.batch_download(task_ids, file_type="target")
        if dl.get("success"):
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            dst = Path(f"batch_results_{ts}.zip")
            dst.write_bytes(base64.b64decode(dl["file_content"]))
            print(f"Batch ZIP -> {dst}  ({dst.stat().st_size} bytes)")

    return [r["task_id"] for r in completed]


async def main():
    parser = argparse.ArgumentParser(description="Owlangs MCP all-in-one demo")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8100)
    args = parser.parse_args()

    url = f"http://{args.host}:{args.port}/mcp"
    print(f"Connecting to {url}")

    async with connect(url) as client:
        await demo_list_platforms(client)

        # Single file translate
        sample = Path("test/test_mcp_translate.md")
        if sample.exists():
            await demo_translate_single(client, str(sample), "Chinese")
        else:
            print(f"\nSkip translate: {sample} not found")

        # Convert
        pdf = Path("test/6_PDFsam_尿素吸附.pdf")
        if pdf.exists():
            await demo_convert_single(client, str(pdf))
        else:
            print(f"\nSkip convert: {pdf} not found")

        # ZIP batch
        zip_path = Path("test/test2.zip")
        if zip_path.exists():
            await demo_batch_zip(client, str(zip_path), "Chinese")
        else:
            print(f"\nSkip batch zip: {zip_path} not found")

    print(f"\n{'='*60}")
    print("Done.")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
