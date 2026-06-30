# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

"""Tests for configurable output suffix filename construction in downloads."""


def _build_batch_entry_name(base_name: str, suffix: str, ext: str) -> str:
    """Mirror the non-md-zip entry naming in service_batch_download_route."""
    return f"{base_name}{suffix}.{ext}"


def test_default_suffix_in_entry_name():
    assert _build_batch_entry_name("document", "_translated", "md") == "document_translated.md"


def test_conversion_suffix_in_entry_name():
    assert _build_batch_entry_name("document", "_converted", "docx") == "document_converted.docx"


def test_empty_suffix_removes_separator():
    """When the user clears the suffix, filenames must not contain a trailing underscore."""
    assert _build_batch_entry_name("document", "", "md") == "document.md"


def test_custom_suffix_in_entry_name():
    assert _build_batch_entry_name("document", "_v2", "md") == "document_v2.md"


def test_get_output_suffix_prefers_empty_user_profile_over_app_config(monkeypatch):
    from utils import output_suffix

    monkeypatch.setattr(output_suffix, "read_user_output_suffix", lambda ctx: "")

    class _Cfg:
        translator_output_suffix = "_translated"
        converter_output_suffix = "_converted"

    monkeypatch.setattr("config.get_app_config", lambda: _Cfg())

    assert output_suffix.get_output_suffix({"owner_username": "local"}) == ""


def test_add_md_zip_download_flattens_inner_zip():
    import io
    import zipfile

    from utils.batch_download_zip import add_md_zip_download_to_batch_archive

    inner_buf = io.BytesIO()
    with zipfile.ZipFile(inner_buf, "w") as inner_zf:
        inner_zf.writestr("doc_translated.md", b"# Title")
        inner_zf.writestr("images/a.png", b"PNG")

    outer_buf = io.BytesIO()
    with zipfile.ZipFile(outer_buf, "w") as outer_zf:
        entry = add_md_zip_download_to_batch_archive(
            outer_zf,
            inner_buf.getvalue(),
            "folder/doc_translated",
            "doc",
            "_translated",
            lambda name: name,
        )
    assert entry == "folder/doc_translated/"

    with zipfile.ZipFile(io.BytesIO(outer_buf.getvalue()), "r") as outer_zf:
        names = outer_zf.namelist()
    assert "folder/doc_translated/doc_translated.md" in names
    assert "folder/doc_translated/images/a.png" in names


def test_add_md_zip_download_remaps_legacy_md_suffix_to_current():
    import io
    import zipfile

    from utils.batch_download_zip import add_md_zip_download_to_batch_archive

    inner_buf = io.BytesIO()
    with zipfile.ZipFile(inner_buf, "w") as inner_zf:
        inner_zf.writestr("doc_translated.md", b"# Title")
        inner_zf.writestr("images/a.png", b"PNG")

    outer_buf = io.BytesIO()
    with zipfile.ZipFile(outer_buf, "w") as outer_zf:
        add_md_zip_download_to_batch_archive(
            outer_zf,
            inner_buf.getvalue(),
            "folder/doc",
            "doc",
            "",
            lambda name: name,
        )

    with zipfile.ZipFile(io.BytesIO(outer_buf.getvalue()), "r") as outer_zf:
        names = outer_zf.namelist()
    assert "folder/doc/doc.md" in names
    assert "folder/doc/images/a.png" in names
    assert not any("_translated" in n for n in names)


def test_strip_legacy_output_suffix():
    from utils.batch_download_zip import strip_legacy_output_suffix

    assert strip_legacy_output_suffix("book_translated") == "book"
    assert strip_legacy_output_suffix("book") == "book"


def test_make_batch_folder_name_truncates_long_stems():
    from utils.batch_download_zip import make_batch_folder_name, make_batch_md_filename

    long_name = "IET Smart Grid - 2025 - Li - A Multiple Market Trading Mechanism for Virtual Power Plants Participating in Electricity源文件"
    folder = make_batch_folder_name(long_name, "cbb81c7e", "")
    md_name = make_batch_md_filename(long_name, "")
    assert len(folder.encode("utf-8")) <= 80
    assert folder.endswith("_cbb81c7e")
    assert md_name == f"{long_name}.md"


def test_short_folder_keeps_full_md_filename():
    import io
    import zipfile

    from utils.batch_download_zip import (
        add_md_zip_download_to_batch_archive,
        make_batch_folder_name,
        make_batch_md_filename,
    )

    long_name = "IET Smart Grid - 2025 - Li - A Multiple Market Trading Mechanism for Virtual Power Plants Participating in Electricity源文件"
    folder = make_batch_folder_name(long_name, "cbb81c7e", "")
    md_name = make_batch_md_filename(long_name, "")

    inner_buf = io.BytesIO()
    with zipfile.ZipFile(inner_buf, "w") as inner_zf:
        inner_zf.writestr("inner.md", b"# Title")
        inner_zf.writestr("images/a.png", b"PNG")

    outer_buf = io.BytesIO()
    with zipfile.ZipFile(outer_buf, "w") as outer_zf:
        add_md_zip_download_to_batch_archive(
            outer_zf,
            inner_buf.getvalue(),
            f"batch/{folder}",
            long_name,
            "",
            lambda name: name,
        )

    with zipfile.ZipFile(io.BytesIO(outer_buf.getvalue()), "r") as outer_zf:
        names = outer_zf.namelist()
    assert f"batch/{folder}/{md_name}" in names
    assert folder != long_name


def test_add_md_zip_writes_directory_stubs():
    import io
    import zipfile

    from utils.batch_download_zip import add_md_zip_download_to_batch_archive

    inner_buf = io.BytesIO()
    with zipfile.ZipFile(inner_buf, "w") as inner_zf:
        inner_zf.writestr("doc.md", b"# Title")
        inner_zf.writestr("images/a.png", b"PNG")

    outer_buf = io.BytesIO()
    with zipfile.ZipFile(outer_buf, "w") as outer_zf:
        add_md_zip_download_to_batch_archive(
            outer_zf,
            inner_buf.getvalue(),
            "folder/doc",
            "doc",
            "",
            lambda name: name,
        )

    with zipfile.ZipFile(io.BytesIO(outer_buf.getvalue()), "r") as outer_zf:
        names = outer_zf.namelist()
    assert "folder/" in names
    assert "folder/doc/" in names
    assert "folder/doc/doc.md" in names


def test_add_md_zip_download_accepts_plain_markdown_bytes():
    import io
    import zipfile

    from utils.batch_download_zip import add_md_zip_download_to_batch_archive

    outer_buf = io.BytesIO()
    with zipfile.ZipFile(outer_buf, "w") as outer_zf:
        add_md_zip_download_to_batch_archive(
            outer_zf,
            b"# Hello\n\nParagraph",
            "folder/doc",
            "doc",
            "",
            lambda name: name,
        )

    with zipfile.ZipFile(io.BytesIO(outer_buf.getvalue()), "r") as outer_zf:
        assert outer_zf.read("folder/doc/doc.md") == b"# Hello\n\nParagraph"
