# Owlangs MCP Client Examples

Connect to the Owlangs MCP server from third-party applications.

## Requirements

```bash
pip install mcp httpx
```

## Quick Start

### 1. Start the MCP server (do this first)

```bash
python -m backend.mcp_server --http --host 0.0.0.0 --port 8100
```

### 2. Run an example (in another terminal)

```bash
python examples/mcp_client/example_translate_single.py my_document.pdf "Chinese"
```

---

## Example Scripts

| Script | Purpose |
|--------|---------|
| [example_translate_single.py](example_translate_single.py) | Translate a single file, poll, download multiple formats |
| [example_convert_single.py](example_convert_single.py) | Convert document format without translation |
| [example_translate_zip.py](example_translate_zip.py) | Batch translate all supported files in a ZIP |
| [example_download_batch.py](example_download_batch.py) | Download results from multiple task IDs into one ZIP |
| [mcp_client_example.py](mcp_client_example.py) | All-in-one demo showing all workflows |
| [mcp_client.py](mcp_client.py) | Shared client helper (imported by all examples) |

### `example_translate_single.py`

Translate a single file and download results in multiple formats (docx, md, html, target).

```bash
python examples/mcp_client/example_translate_single.py my_doc.pdf "Chinese"
python examples/mcp_client/example_translate_single.py report.docx "Japanese" --host 192.168.1.100
python examples/mcp_client/example_translate_single.py notes.md "Korean" --port 8100
```

### `example_convert_single.py`

Convert a document format without going through the translation pipeline.

```bash
python examples/mcp_client/example_convert_single.py my_doc.pdf
python examples/mcp_client/example_convert_single.py invoice.xlsx --host 192.168.1.100
```

### `example_translate_zip.py`

Upload a ZIP of documents, translate all supported files, poll all tasks, and download batch results.

```bash
python examples/mcp_client/example_translate_zip.py documents.zip "Chinese"
python examples/mcp_client/example_translate_zip.py batch.zip "Japanese" --host 192.168.1.100
```

### `example_download_batch.py`

Download results from known task IDs into a single ZIP file.

```bash
python examples/mcp_client/example_download_batch.py abc123 def456
python examples/mcp_client/example_download_batch.py abc123 def456 --file-type html
python examples/mcp_client/example_download_batch.py abc123 --file-type md_zip --output results.zip
```

### `mcp_client_example.py`

Comprehensive demo that runs through all workflows in sequence.

```bash
python examples/mcp_client/mcp_client_example.py
python examples/mcp_client/mcp_client_example.py --host 192.168.1.100 --port 8100
```

---

## Shared Client Module

All examples import from [mcp_client.py](mcp_client.py), which provides:

- **`OwlangsMCPClient`** — wrapper around the raw MCP session with convenience methods
- **`connect(server_url)`** — async context manager that handles connection and initialization
- **`poll_until_done(client, task_id)`** — polls a task until completed/failed/timeout

```python
from mcp_client import connect, poll_until_done

async with connect("http://127.0.0.1:8100/mcp") as client:
    result = await client.translate("doc.pdf", "Chinese")
    task_id = result["task_id"]
    status = await poll_until_done(client, task_id)
    dl = await client.download(task_id, "docx")
```

---

## Typical Workflow

### Single file translation

```
1. owlangs_list_platforms          → pick a platform_id
2. owlangs_translate               → get task_id
     file_content (base64) + file_name
     to_lang (e.g. "Chinese", "Japanese")
3. owlangs_translate_status(task_id)  → poll until "completed"
4. owlangs_translate_download(task_id, file_type="docx")  → base64 content
```

### ZIP batch translation

```
1. owlangs_translate_batch_zip     → get task_id list
     zip_content (base64 of ZIP file) + zip_file_name
     to_lang
2. owlangs_translate_status(task_id)  → poll each until "completed"
3. owlangs_translate_batch_download(task_ids=[...], file_type="target")
     → base64 of a result ZIP
```

---

## Claude Desktop Integration

Claude Desktop does **not** support HTTP URLs directly in `claude_desktop_config.json`. It only supports stdio subprocess. For a remote MCP server (the common case for third-party users), you need a **stdio-to-HTTP bridge**.

### Option A: Using `mcp-remote` (recommended for remote servers)

```bash
npx mcp-remote http://<server-ip>:8100/mcp
```

Add to `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "owlangs": {
      "command": "npx",
      "args": [
        "mcp-remote",
        "http://192.168.1.100:8100/mcp"
      ]
    }
  }
}
```

Replace `192.168.1.100` with your server's actual IP or hostname.

### Option B: Using `@plingcast/mcp-proxy`

```json
{
  "mcpServers": {
    "owlangs": {
      "command": "npx",
      "args": ["-y", "@plingcast/mcp-proxy"],
      "env": {
        "MCP_URL": "http://192.168.1.100:8100/mcp"
      }
    }
  }
}
```

### Option C: Direct stdio (local only — requires backend code on the same machine)

```json
{
  "mcpServers": {
    "owlangs": {
      "command": "python",
      "args": ["-m", "backend.mcp_server"],
      "cwd": "/path/to/owlangs/project",
      "env": {
        "OWLANGS_ROOT": "/path/to/owlangs/project"
      }
    }
  }
}
```

> **Claude Code** supports HTTP MCP servers natively without a bridge:
> ```bash
> claude mcp add owlangs --transport http http://192.168.1.100:8100/mcp
> ```
```

---

## File Upload

Provide a file as **base64-encoded content** (remote clients should use this):

```bash
# POSIX
base64 -w0 my_document.pdf

# PowerShell
[Convert]::ToBase64String([IO.File]::ReadAllBytes("my_document.pdf"))
```

---

## Supported Formats

**Input:** `.pdf` `.docx` `.doc` `.pptx` `.ppt` `.xlsx` `.xls` `.csv` `.txt` `.md` `.html` `.htm` `.json` `.srt` `.epub` `.mobi` `.azw` `.ts` `.png` `.jpg` `.jpeg`

**Download:** `target` `docx` `md` `html` `pdf` `txt` `md_zip`

---

## Notes

- The MCP server is **unauthenticated** — secure access via firewall / VPN.
- API keys are configured server-side; each call can optionally override `base_url`, `api_key`, `model_id`.
- Translation tasks run **asynchronously** — always poll until `status == "completed"`.
