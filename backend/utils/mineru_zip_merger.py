# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

"""
MinerU ZIP merging utilities.

Merges multiple MinerU result ZIPs (from split PDF parts) into a single ZIP
that is compatible with ``load_layout_from_engine_zip``.
"""

import json
import os
import zipfile
import io
from typing import List, Tuple

from layout.base import LayoutDocument


def merge_mineru_zips(
    zip_parts: List[Tuple[bytes, LayoutDocument]],
    merged_layout_doc: LayoutDocument,
    merged_markdown: str,
) -> bytes:
    """
    Merge multiple MinerU ZIP results into a single ZIP.

    The output ZIP contains:
      - ``full.md``: the merged markdown content
      - ``layout.json``: a MinerU-compatible layout file generated from *merged_layout_doc*
      - all image files from the input ZIPs (renamed on collision)

    Args:
        zip_parts: List of (zip_bytes, layout_doc) for each split part.
        merged_layout_doc: The merged LayoutDocument.
        merged_markdown: The merged markdown string.

    Returns:
        The merged ZIP file as bytes.
    """
    output = io.BytesIO()
    with zipfile.ZipFile(output, 'w', zipfile.ZIP_DEFLATED) as zf_out:
        # 1. Merged markdown
        zf_out.writestr("full.md", merged_markdown.encode('utf-8'))

        # 2. Images — copy from each part, rename on conflict
        # TODO: When an image is renamed, the corresponding image_path references
        # inside layout.json / block.raw are NOT updated yet. Collision probability
        # is assumed low for MVP.
        seen_names: set = set()
        for part_idx, (zip_bytes, _) in enumerate(zip_parts):
            with zipfile.ZipFile(io.BytesIO(zip_bytes), 'r') as zf_in:
                for name in zf_in.namelist():
                    # Skip non-image files (markdown, json, etc.)
                    if name.endswith(('.md', '.json')):
                        continue

                    data = zf_in.read(name)
                    if name in seen_names:
                        base = os.path.basename(name)
                        dir_name = os.path.dirname(name)
                        stem, ext = os.path.splitext(base)
                        new_name = (
                            f"{dir_name}/{stem}_part{part_idx}{ext}"
                            if dir_name
                            else f"{stem}_part{part_idx}{ext}"
                        )
                        seen_names.add(new_name)
                        zf_out.writestr(new_name, data)
                    else:
                        seen_names.add(name)
                        zf_out.writestr(name, data)

        # 3. Generate merged layout.json
        layout_json = _generate_layout_json(merged_layout_doc)
        zf_out.writestr(
            "layout.json",
            json.dumps(layout_json, ensure_ascii=False, indent=2).encode('utf-8'),
        )

    return output.getvalue()


def _generate_layout_json(layout_doc: LayoutDocument) -> dict:
    """Generate a MinerU-compatible layout.json from a LayoutDocument."""
    pdf_info = []
    for page in layout_doc.pages:
        page_data: dict = {
            "page_idx": page.page_index,
            "page_size": [page.width, page.height] if page.width and page.height else [],
            "para_blocks": [],
            "discarded_blocks": [],
        }
        for block in page.blocks:
            if block.raw:
                block_data = dict(block.raw)
                block_data["page_idx"] = block.page_index
            else:
                block_data = {
                    "page_idx": block.page_index,
                    "type": block.type,
                    "bbox": list(block.bbox),
                    "text": block.text or "",
                }
            if block.is_structural():
                page_data["discarded_blocks"].append(block_data)
            else:
                page_data["para_blocks"].append(block_data)
        pdf_info.append(page_data)

    return {
        "pdf_info": pdf_info,
        "_backend": layout_doc.metadata.get("_backend", "mineru"),
        "_version_name": layout_doc.metadata.get("_version_name", "merged"),
    }
