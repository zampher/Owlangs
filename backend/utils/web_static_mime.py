# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

"""Register MIME types required for Flutter Web / pdf.js static assets."""

from __future__ import annotations

import mimetypes


def ensure_web_static_mime_types() -> None:
    """Ensure ``.mjs`` (and related) map to JS MIME types browsers accept for modules.

    On Windows, the system MIME database often maps ``.mjs`` to ``text/plain``.
    Starlette ``StaticFiles`` uses ``mimetypes.guess_type``, so module scripts
    (pdf.js) fail with: Expected a JavaScript-or-Wasm module script but the
    server responded with a MIME type of \"text/plain\".
    """
    # Prefer text/javascript (HTML living standard); browsers also accept application/javascript.
    mimetypes.add_type("text/javascript", ".mjs")
    mimetypes.add_type("text/javascript", ".js")
    mimetypes.add_type("application/wasm", ".wasm")
    # pdf.js cmaps / font binaries are fine as octet-stream; leave defaults.
