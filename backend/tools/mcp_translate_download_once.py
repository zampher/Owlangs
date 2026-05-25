"""One-off: translate a file and save docx/md (same logic as MCP tools).

LLM platform config (base_url, api_key, model_id) is auto-resolved from the
backend's default platform configuration — no need to pass them explicitly.
"""
import asyncio
import base64
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from backend.mcp_server.service_layer import (  # noqa: E402
    setup_path,
    translate_file,
    get_task_status,
    download_result,
)


async def main() -> int:
    setup_path()
    pdf = Path(r"D:/workspace/localrepo/CollabTrans/test/samples/6_PDFsam_尿素吸附.pdf")
    out_dir = pdf.parent / "6_PDFsam_尿素吸附_translated"
    out_dir.mkdir(exist_ok=True)

    start = await translate_file(
        file_content=None,
        file_path=str(pdf),
        file_name=pdf.name,
        to_lang="Chinese",
        # convert_engine / base_url / api_key / model_id are optional —
        # automatically resolved from the backend's default platform config
        # from the backend's default platform (configured in platforms.json).
    )
    print("START", json.dumps(start, ensure_ascii=False))
    if not start.get("task_started"):
        return 1

    task_id = start["task_id"]
    for i in range(360):
        await asyncio.sleep(10)
        status = await get_task_status(task_id)
        st = status.get("status")
        msg = (status.get("message") or "")[:120]
        print(f"POLL {i}: {st} {status.get('progress')}% {msg}")
        if st == "completed":
            break
        if st in ("failed", "cancelled"):
            print("FAIL", status.get("error") or status.get("message"))
            return 2
    else:
        print("TIMEOUT")
        return 3

    for file_type in ("docx", "md"):
        result = await download_result(task_id, file_type)
        if not result.get("success"):
            print("DOWNLOAD_FAIL", file_type, result.get("message"))
            return 4
        name = result.get("file_name") or f"{pdf.stem}.{file_type}"
        path = out_dir / name
        path.write_bytes(base64.b64decode(result["file_content"]))
        print("SAVED", path, path.stat().st_size)

    print("TASK_ID", task_id)
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
