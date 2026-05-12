# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

"""HTML -> Markdown table preservation (XLSX / html2text path)."""

from workflow.html_to_markdown_export import html_content_to_markdown
from workflow.html_table_to_markdown import html_table_to_markdown_fragment
from bs4 import BeautifulSoup


def test_simple_table_becomes_pipe_markdown():
    html = """<html><body><table>
<tr><th>A</th><th>B</th></tr>
<tr><td>1</td><td>2</td></tr>
</table></body></html>"""
    md = html_content_to_markdown(html)
    assert "| A |" in md and "| B |" in md
    assert "| 1 |" in md and "| 2 |" in md
    assert "<table" not in md.lower()


def test_rowspan_table_embeds_html():
    html = """<table><tr><td rowspan="2">X</td><td>a</td></tr><tr><td>b</td></tr></table>"""
    soup = BeautifulSoup(html, "html.parser")
    frag = html_table_to_markdown_fragment(soup.find("table"))
    assert "rowspan" in frag.lower()
    assert "<table" in frag.lower()


def test_placeholder_has_no_angle_brackets_in_serialized_html():
    """Regression: '<' in placeholder becomes &lt; in str(soup) and breaks html2text restore."""
    from workflow.html_table_to_markdown import (
        extract_tables_and_insert_placeholders,
        md_table_placeholder_token,
    )

    soup = BeautifulSoup(
        "<body><table><tr><td>x</td></tr></table></body>",
        "html.parser",
    )
    extract_tables_and_insert_placeholders(soup)
    serialized = str(soup)
    assert md_table_placeholder_token(0) in serialized
    assert "&lt;&lt;&lt;OWLANGS_MD_TABLE" not in serialized


def test_placeholder_round_trip_with_html2text_skipped():
    from workflow.html_table_to_markdown import (
        extract_tables_and_insert_placeholders,
        restore_table_placeholders,
    )

    soup = BeautifulSoup(
        "<body><p>Hi</p><table><tr><td>z</td></tr></table></body>",
        "html.parser",
    )
    frags = extract_tables_and_insert_placeholders(soup)
    assert len(frags) == 1
    assert "| z |" in frags[0]
    from workflow.html_table_to_markdown import md_table_placeholder_token

    fake_md = f"Hi\n\n{md_table_placeholder_token(0)}\n"
    out = restore_table_placeholders(fake_md, frags)
    assert "| z |" in out
    assert md_table_placeholder_token(0) not in out
