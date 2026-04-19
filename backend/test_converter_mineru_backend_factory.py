# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0
"""Unit tests for MinerU backend selection and local sync task id token."""

import os
import sys

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
if CURRENT_DIR not in sys.path:
    sys.path.insert(0, CURRENT_DIR)


def test_cloud_host_always_cloud_backend():
    from converter.x2md.converter_mineru import (
        BackendFactory,
        ConverterMineruConfig,
        MinerUCloudBackend,
        MinerULocalBackend,
    )

    # mineru.net must use cloud even if api_endpoints contains local-style keys (mis-merge guard).
    cfg = ConverterMineruConfig(
        mineru_token="test-token",
        base_url="https://mineru.net/api/v4",
        api_endpoints={
            "upload_sync": "/file_parse",
            "upload_async": "/tasks",
            "api_version": "local-v3.1",
        },
    )
    backend = BackendFactory.create_backend(cfg)
    assert isinstance(backend, MinerUCloudBackend)


def test_non_mineru_host_uses_local_backend():
    from converter.x2md.converter_mineru import (
        BackendFactory,
        ConverterMineruConfig,
        MinerULocalBackend,
    )

    cfg = ConverterMineruConfig(
        mineru_token="",
        base_url="http://127.0.0.1:8920",
        api_endpoints={
            "upload_sync": "/file_parse",
            "result": "/tasks/{task_id}/result",
        },
    )
    backend = BackendFactory.create_backend(cfg)
    assert isinstance(backend, MinerULocalBackend)


def test_local_sync_task_id_constant():
    from converter.x2md.converter_mineru import _LOCAL_MINERU_SYNC_TASK_ID

    assert _LOCAL_MINERU_SYNC_TASK_ID == "__LOCAL_MINERU_SYNC__"


def test_local_backend_roundtrip_pending_zip():
    from converter.x2md.converter_mineru import (
        MinerULocalBackend,
        _LOCAL_MINERU_SYNC_TASK_ID,
    )
    import zipfile
    import io

    backend = MinerULocalBackend(
        base_url="http://localhost:8920",
        mineru_token="",
    )
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("full.md", "# hello")
    zip_bytes = buf.getvalue()

    backend._pending_sync_zip_bytes = zip_bytes
    md, out_zip = backend.get_result(_LOCAL_MINERU_SYNC_TASK_ID)
    assert backend._pending_sync_zip_bytes is None
    assert out_zip == zip_bytes
    assert "hello" in md


if __name__ == "__main__":
    test_cloud_host_always_cloud_backend()
    test_non_mineru_host_uses_local_backend()
    test_local_sync_task_id_constant()
    test_local_backend_roundtrip_pending_zip()
    print("converter_mineru tests OK")
