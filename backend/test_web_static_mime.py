# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

"""MIME types for Flutter Web / pdf.js static assets."""

from __future__ import annotations

import mimetypes

from utils.web_static_mime import ensure_web_static_mime_types


def test_mjs_served_as_javascript_mime() -> None:
    # Simulate Windows default before fix.
    mimetypes.add_type("text/plain", ".mjs")
    assert mimetypes.guess_type("pdf.min.mjs")[0] == "text/plain"

    ensure_web_static_mime_types()
    mime, _ = mimetypes.guess_type("pdf.min.mjs")
    assert mime in ("text/javascript", "application/javascript")
