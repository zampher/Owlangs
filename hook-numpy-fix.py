# -*- coding: utf-8 -*-
"""
PyInstaller runtime hook to fix numpy compatibility issues.
This hook runs before any other imports and injects a safe stub for
`numpy._core.overrides.add_docstring` to avoid the docstring TypeError during
NumPy import in frozen apps.
"""
import sys
import os
import types

# Set environment variables early (harmless if not used)
os.environ['NUMPY_EXPERIMENTAL_DTYPE_API'] = '1'
os.environ['NUMPY_DISABLE_CPU_FEATURES'] = '1'

# Completely disable problematic modules
sys.modules['numpy.core._add_newdocs'] = types.ModuleType('numpy.core._add_newdocs')
sys.modules['numpy._core._add_newdocs'] = types.ModuleType('numpy._core._add_newdocs')

def _install_overrides_stub():
    """Install a stub module for numpy._core.overrides with a safe add_docstring.

    We avoid importing numpy here. Instead, we pre-populate sys.modules with a
    stub so that when numpy imports `numpy._core.overrides`, it will receive our
    safe implementation and won't crash while defining C-extension symbols that
    use the decorator.
    """
    try:
        # If already present, do nothing
        if 'numpy._core.overrides' in sys.modules:
            return

        overrides_stub = types.ModuleType('numpy._core.overrides')

        def safe_add_docstring(func, docstring):
            # Ensure docstring is a string; behave as a no-op if needed
            if not isinstance(docstring, str):
                docstring = '' if docstring is None else str(docstring)
            try:
                # Some numpy builds replace this later; we keep behavior minimal
                func.__doc__ = docstring
            except Exception:
                pass
            return func

        # Expose the symbol expected by numpy
        overrides_stub.add_docstring = safe_add_docstring  # type: ignore[attr-defined]

        # Provide minimal no-op implementations for other expected helpers
        def array_function_from_dispatcher(*args, **kwargs):  # noqa: D401
            """Return a pass-through decorator used during import in frozen builds."""
            def decorator(func):
                return func
            return decorator

        def set_module(module):  # noqa: D401
            """Return a decorator that sets __module__ and passes through the function."""
            def decorator(func):
                try:
                    func.__module__ = module
                except Exception:
                    pass
                return func
            return decorator

        def set_array_function_like_doc(*args, **kwargs):  # noqa: D401
            """No-op doc helper; returns a passthrough decorator."""
            def decorator(func):
                return func
            return decorator

        def get_array_function_like_doc(*args, **kwargs):  # noqa: D401
            """No-op getter expected by some NumPy versions; returns passthrough decorator."""
            def decorator(func):
                return func
            return decorator

        def finalize_array_function_like(*args, **kwargs):  # noqa: D401
            """No-op finalize helper expected by newer NumPy versions."""
            def decorator(func):
                return func
            return decorator

        def array_function_like_doc(*args, **kwargs):  # noqa: D401
            """No-op doc helper expected by pandas; returns a passthrough decorator."""
            if len(args) == 0:
                # Called as decorator
                def decorator(func):
                    return func
                return decorator
            else:
                # Called with arguments, return a string
                return ""

        overrides_stub.array_function_from_dispatcher = array_function_from_dispatcher  # type: ignore[attr-defined]
        # Some numpy code imports array_function_dispatch (older alias)
        def array_function_dispatch(*args, **kwargs):  # noqa: D401
            """Alias used by some numpy modules; return passthrough decorator."""
            def decorator(func):
                return func
            return decorator

        overrides_stub.array_function_dispatch = array_function_dispatch  # type: ignore[attr-defined]
        overrides_stub.set_module = set_module  # type: ignore[attr-defined]
        overrides_stub.set_array_function_like_doc = set_array_function_like_doc  # type: ignore[attr-defined]
        overrides_stub.get_array_function_like_doc = get_array_function_like_doc  # type: ignore[attr-defined]
        overrides_stub.finalize_array_function_like = finalize_array_function_like  # type: ignore[attr-defined]
        overrides_stub.array_function_like_doc = array_function_like_doc  # type: ignore[attr-defined]

        # Register stub only for the submodule key. Do NOT register 'numpy' itself
        sys.modules['numpy._core.overrides'] = overrides_stub
        print('[INFO] Installed numpy._core.overrides stub (safe add_docstring)')
    except Exception as e:
        print(f'[WARN] Failed to install overrides stub: {e}')


if hasattr(sys, 'frozen'):
    # Install for both legacy and current module paths
    _install_overrides_stub()
    try:
        # Duplicate the stub for numpy.core.overrides if only the legacy key exists
        if 'numpy._core.overrides' in sys.modules and 'numpy.core.overrides' not in sys.modules:
            sys.modules['numpy.core.overrides'] = sys.modules['numpy._core.overrides']
        # Or vice versa
        if 'numpy.core.overrides' in sys.modules and 'numpy._core.overrides' not in sys.modules:
            sys.modules['numpy._core.overrides'] = sys.modules['numpy.core.overrides']
        print('[INFO] Ensured overrides stub for both numpy.core.overrides and numpy._core.overrides')
    except Exception as _e:
        print(f'[WARN] Failed to mirror overrides stub: {_e}')
