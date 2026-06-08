"""Standalone MCP client helper for Owlangs.

Provides a shared wrapper around the raw MCP session so individual example
scripts don't need to repeat connection logic or JSON parsing.

Requirements:
    pip install mcp httpx

Usage (from another script in this directory):
    from mcp_client import connect, OwlangsMCPClient

    async with connect("http://127.0.0.1:8100/mcp") as client:
        result = await client.call("owlangs_list_platforms")
"""

import base64
import json
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, AsyncIterator, Optional

from mcp.client.session import ClientSession
from mcp.client.streamable_http import streamable_http_client


# ── Client wrapper ─────────────────────────────────────────────────────────────


class OwlangsMCPClient:
    """Thin wrapper over an initialized MCP session.

    Each ``call()`` invokes an ``owlangs_*`` tool and returns the
    parsed JSON result.
    """

    def __init__(self, session: ClientSession) -> None:
        self._session = session

    async def call(self, tool: str, **kwargs: Any) -> Any:
        result = await self._session.call_tool(tool, kwargs)
        for content in result.content:
            if hasattr(content, "text") and content.text:
                try:
                    return json.loads(content.text)
                except json.JSONDecodeError:
                    return content.text
        return result.content

    # ── Convenience wrappers ───────────────────────────────────────────────

    async def translate(self, file_path: str, to_lang: str,
                        **kwargs: Any) -> dict:
        encoded = base64.b64encode(Path(file_path).read_bytes()).decode()
        return await self.call(
            "owlangs_translate",
            file_content=encoded,
            file_name=Path(file_path).name,
            to_lang=to_lang,
            **kwargs,
        )

    async def translate_bytes(self, data: bytes, file_name: str,
                              to_lang: str, **kwargs: Any) -> dict:
        encoded = base64.b64encode(data).decode()
        return await self.call(
            "owlangs_translate",
            file_content=encoded,
            file_name=file_name,
            to_lang=to_lang,
            **kwargs,
        )

    async def status(self, task_id: str) -> dict:
        return await self.call("owlangs_translate_status", task_id=task_id)

    async def download(self, task_id: str,
                       file_type: str = "target") -> dict:
        return await self.call(
            "owlangs_translate_download",
            task_id=task_id,
            file_type=file_type,
        )

    async def convert(self, file_path: str, **kwargs: Any) -> dict:
        encoded = base64.b64encode(Path(file_path).read_bytes()).decode()
        return await self.call(
            "owlangs_convert_document",
            file_content=encoded,
            file_name=Path(file_path).name,
            **kwargs,
        )

    async def batch_zip(self, zip_path: str, to_lang: str,
                        **kwargs: Any) -> dict:
        encoded = base64.b64encode(Path(zip_path).read_bytes()).decode()
        return await self.call(
            "owlangs_translate_batch_zip",
            zip_content=encoded,
            zip_file_name=Path(zip_path).name,
            to_lang=to_lang,
            **kwargs,
        )

    async def batch_download(self, task_ids: list[str],
                             file_type: str = "target") -> dict:
        return await self.call(
            "owlangs_translate_batch_download",
            task_ids=task_ids,
            file_type=file_type,
        )


# ── Connection helper ─────────────────────────────────────────────────────────


@asynccontextmanager
async def connect(server_url: str) -> AsyncIterator[OwlangsMCPClient]:
    """Connect to an Owlangs MCP HTTP server and yield a ready client.

    Usage::

        async with connect("http://127.0.0.1:8100/mcp") as client:
            platforms = await client.call("owlangs_list_platforms")
    """
    async with streamable_http_client(server_url) as streams:
        async with ClientSession(streams[0], streams[1]) as session:
            await session.initialize()
            yield OwlangsMCPClient(session)


# ── Polling helper ────────────────────────────────────────────────────────────


async def poll_until_done(client: OwlangsMCPClient, task_id: str,
                          interval: float = 10.0,
                          timeout: float = 3600.0) -> dict:
    """Poll a task until it completes, fails, or times out.

    Returns the final status dict.
    """
    import asyncio

    deadline = asyncio.get_event_loop().time() + timeout
    while True:
        st = await client.status(task_id)
        s = st.get("status")
        if s == "completed":
            return st
        if s in ("failed", "cancelled"):
            return st
        if asyncio.get_event_loop().time() >= deadline:
            return {"status": "timeout", "task_id": task_id}
        await asyncio.sleep(interval)
