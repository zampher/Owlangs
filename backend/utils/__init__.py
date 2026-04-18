"""
Utility package initialization for Owlangs backend.

Many modules in the codebase import helpers using absolute paths such as
`from utils.markdown_splitter import ...`. When the project is packaged or
executed as a module (e.g. `python -m backend.app`), the real module path is
`backend.utils.*`. To keep legacy imports working in every environment, alias
this package to the top-level name ``utils``.
"""

import sys as _sys

if __name__ != "utils":
    _sys.modules.setdefault("utils", _sys.modules[__name__])

__all__ = []

