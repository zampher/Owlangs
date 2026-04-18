import os
import sys

import pytest


# Ensure backend package imports work when running this test directly.
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
if CURRENT_DIR not in sys.path:
    sys.path.insert(0, CURRENT_DIR)


from layout.base import LayoutBlock, LayoutDocument, LayoutPage  # noqa: E402
from layout.markdown_builder import LayoutMarkdownBuilder  # noqa: E402


def _build_simple_table_document() -> LayoutDocument:
    """Build a minimal LayoutDocument containing a single HTML table block."""
    table_html = """
    <table>
      <tr>
        <th>Task</th>
        <th>Datasets</th>
      </tr>
      <tr>
        <td>Natural language inference</td>
        <td>SNLI [5], MultiNLI [66], Question NLI [64], RTE [4], SciTail [25]</td>
      </tr>
      <tr>
        <td>Question Answering</td>
        <td>RACE [30], Story Cloze [40]</td>
      </tr>
    </table>
    """.strip()

    # Mimic MinerU/Docling-like nested table structure expected by markdown_builder.
    raw_block = {
        "blocks": [
            {
                "type": "table_body",
                "lines": [
                    {
                        "spans": [
                            {
                                "type": "table",
                                "html": table_html,
                                "image_path": None,
                            }
                        ]
                    }
                ],
            }
        ]
    }

    table_block = LayoutBlock(
        page_index=0,
        bbox=(0.0, 0.0, 100.0, 100.0),
        type="table",
        index=0,
        text=None,
        image_path=None,
        raw=raw_block,
    )

    page = LayoutPage(page_index=0, blocks=[table_block])
    return LayoutDocument(pages=[page], engine="unit-test")


@pytest.mark.unit
def test_table_body_kept_as_single_segment():
    """
    Ensure that HTML table bodies are kept as a single segment in layout markdown.

    This guarantees that PDF tables appear as one segment in Translate instead of
    being split into multiple row-level segments.
    """
    layout_doc = _build_simple_table_document()
    builder = LayoutMarkdownBuilder(
        max_chunk_chars=2000,
        include_images=True,
        deep_split=True,
        table_body_format="html",
    )

    result = builder.build(layout_doc)

    # There should be exactly one text chunk for the table body.
    text_chunks = [c for c in result.chunks if c.chunk_type == "text"]
    assert (
        len(text_chunks) == 1
    ), "Table body should be kept as a single text segment for HTML format"

    table_chunk = text_chunks[0]
    # The markdown text should contain multiple lines (header + rows) within one segment.
    assert "| Task | Datasets |" in table_chunk.text
    assert "Natural language inference" in table_chunk.text
    assert "Question Answering" in table_chunk.text

