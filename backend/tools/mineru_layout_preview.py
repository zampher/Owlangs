"""
MinerU layout preview generator.

Usage (from repo root, in venv):

  python -m backend.tools.mineru_layout_preview --dir "temp/510c33b3-50f9-4f56-86a3-48ce5a36fbd2"

It will:
  - Read `<uuid>_content_list.json` in the given directory
  - Group all blocks by `page_idx`
  - Normalize `bbox` coordinates per page
  - Generate a simple HTML file with absolutely positioned blocks so you can
    visually inspect how MinerU sees the page layout (text & image regions).

This is a standalone inspection tool and does NOT affect the main workflow.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Tuple


@dataclass
class Block:
  page_idx: int
  bbox: Tuple[float, float, float, float]
  type: str
  text: str | None
  img_path: str | None


def _load_content_list(base_dir: Path) -> List[Block]:
  files = sorted(base_dir.glob("*_content_list.json"))
  if not files:
    raise SystemExit(f"No *_content_list.json found under {base_dir}")
  path = files[0]
  data = json.loads(path.read_text(encoding="utf-8"))
  if not isinstance(data, list):
    raise SystemExit(f"{path.name} is not a list")

  blocks: List[Block] = []
  for item in data:
    if not isinstance(item, dict):
      continue
    page_idx = int(item.get("page_idx", 0))
    bbox = item.get("bbox") or item.get("box") or item.get("rect")
    if not (isinstance(bbox, list) and len(bbox) == 4):
      continue
    x0, y0, x1, y1 = bbox
    try:
      x0 = float(x0)
      y0 = float(y0)
      x1 = float(x1)
      y1 = float(y1)
    except (TypeError, ValueError):
      continue

    btype = str(item.get("type", "unknown"))
    text = item.get("text")
    if isinstance(text, list):
      text = " ".join(str(t) for t in text)
    if text is not None:
      text = str(text)
    img_path = item.get("img_path")
    if img_path is not None:
      img_path = str(img_path)

    blocks.append(
      Block(
        page_idx=page_idx,
        bbox=(x0, y0, x1, y1),
        type=btype,
        text=text,
        img_path=img_path,
      )
    )
  return blocks


def _normalize_pages(blocks: List[Block]) -> Dict[int, Dict[str, Any]]:
  """
  For each page, compute min/max of x/y and normalize bbox to [0,1] range.
  Returns:
    {page_idx: {"blocks": [{"nx0","ny0","nw","nh","type","text","img_path"}], "size": (w,h)}}
  """
  pages: Dict[int, List[Block]] = {}
  for b in blocks:
    pages.setdefault(b.page_idx, []).append(b)

  result: Dict[int, Dict[str, Any]] = {}
  for page_idx, pblocks in pages.items():
    xs: List[float] = []
    ys: List[float] = []
    for b in pblocks:
      x0, y0, x1, y1 = b.bbox
      xs.extend([x0, x1])
      ys.extend([y0, y1])
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)
    width = max_x - min_x or 1.0
    height = max_y - min_y or 1.0

    norm_blocks: List[Dict[str, Any]] = []
    for b in pblocks:
      x0, y0, x1, y1 = b.bbox
      nx0 = (x0 - min_x) / width
      ny0 = (y0 - min_y) / height
      nw = (x1 - x0) / width
      nh = (y1 - y0) / height
      norm_blocks.append(
        {
          "nx0": nx0,
          "ny0": ny0,
          "nw": nw,
          "nh": nh,
          "type": b.type,
          "text": b.text,
          "img_path": b.img_path,
        }
      )
    result[page_idx] = {
      "blocks": norm_blocks,
      "size": (width, height),
    }
  return result


def _escape_html(s: str | None) -> str:
  if s is None:
    return ""
  return (
    s.replace("&", "&amp;")
    .replace("<", "&lt;")
    .replace(">", "&gt;")
    .replace('"', "&quot;")
  )


def _shorten(s: str, max_len: int = 160) -> str:
  s = s.replace("\n", " ")
  if len(s) <= max_len:
    return s
  return s[: max_len - 3] + "..."


def generate_html(pages: Dict[int, Dict[str, Any]], output_path: Path) -> None:
  page_indices = sorted(pages.keys())
  html_parts: List[str] = []

  html_parts.append(
    """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>MinerU Layout Preview</title>
  <style>
    body {
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
      background: #f0f0f3;
      margin: 0;
      padding: 16px;
    }
    .page-container {
      display: flex;
      flex-wrap: wrap;
      gap: 16px;
    }
    .page {
      position: relative;
      width: 480px;
      height: 680px;
      background: #fff;
      box-shadow: 0 2px 6px rgba(0,0,0,0.15);
      border-radius: 4px;
      overflow: hidden;
    }
    .page-header {
      font-size: 13px;
      font-weight: 600;
      padding: 4px 8px;
      background: #f5f5f8;
      border-bottom: 1px solid #ddd;
    }
    .page-content {
      position: relative;
      width: 100%;
      height: calc(100% - 24px);
      background: #fff;
    }
    .block {
      position: absolute;
      border: 1px solid rgba(0,0,0,0.15);
      box-sizing: border-box;
      overflow: hidden;
      padding: 2px;
      font-size: 10px;
      line-height: 1.3;
      border-radius: 2px;
      background-color: rgba(255,255,255,0.85);
    }
    .block.text { border-color: #4caf50; }
    .block.title { border-color: #2196f3; }
    .block.header { border-color: #9c27b0; }
    .block.image { border-color: #ff9800; background-color: rgba(255,249,230,0.9); }
    .block .label {
      font-weight: 600;
      font-size: 9px;
      color: #555;
      margin-bottom: 2px;
    }
    .block .content {
      font-size: 10px;
      color: #222;
    }
  </style>
</head>
<body>
  <h2>MinerU Layout Preview</h2>
  <p>Blocks are drawn per page using normalized <code>bbox</code> (page_idx, type, text/img_path).</p>
  <div class="page-container">
"""
  )

  for page_idx in page_indices:
    page = pages[page_idx]
    blocks = page["blocks"]
    html_parts.append(
      f'    <div class="page"><div class="page-header">Page {page_idx}</div><div class="page-content">'
    )
    for b in blocks:
      nx0 = max(0.0, min(1.0, float(b["nx0"])))
      ny0 = max(0.0, min(1.0, float(b["ny0"])))
      nw = max(0.0, min(1.0, float(b["nw"])))
      nh = max(0.0, min(1.0, float(b["nh"])))
      left = nx0 * 100.0
      top = ny0 * 100.0
      width = nw * 100.0
      height = nh * 100.0

      btype = str(b["type"])
      cls_type = btype if btype in {"text", "title", "header", "image"} else "text"
      text = b.get("text")
      img_path = b.get("img_path")

      label_bits: List[str] = [btype]
      if img_path:
        label_bits.append("img")
      label = " / ".join(label_bits)

      if text:
        content = _shorten(text)
      elif img_path:
        content = f"[IMAGE] {img_path}"
      else:
        content = ""

      html_parts.append(
        f'      <div class="block {cls_type}" '
        f'style="left:{left:.2f}%;top:{top:.2f}%;width:{width:.2f}%;height:{height:.2f}%;">'
        f'<div class="label">{_escape_html(label)}</div>'
        f'<div class="content">{_escape_html(content)}</div>'
        f'</div>'
      )

    html_parts.append("      </div></div>")

  html_parts.append(
    """  </div>
</body>
</html>
"""
  )

  output_path.write_text("\n".join(html_parts), encoding="utf-8")


def main() -> None:
  parser = argparse.ArgumentParser(
    description="Generate an HTML visual preview from MinerU *_content_list.json."
  )
  parser.add_argument(
    "--dir",
    type=str,
    required=True,
    help="Path to extracted MinerU ZIP directory (containing *_content_list.json).",
  )
  parser.add_argument(
    "--output",
    type=str,
    default="mineru_layout_preview.html",
    help="Output HTML file name (created inside the given directory).",
  )
  args = parser.parse_args()

  base_dir = Path(args.dir)
  blocks = _load_content_list(base_dir)
  if not blocks:
    raise SystemExit(f"No blocks loaded from content_list.json under {base_dir}")

  pages = _normalize_pages(blocks)
  output_path = base_dir / args.output
  generate_html(pages, output_path)
  print(f"Layout preview HTML generated at: {output_path}")


if __name__ == "__main__":
  main()


