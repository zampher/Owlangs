# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

"""Resolve configurable download filename suffixes from user profile and config."""

from __future__ import annotations

from typing import Any, Dict, Optional


def resolve_default_output_suffix(task_state: dict) -> str:
    is_conv = bool(task_state.get("is_format_conversion") or task_state.get("convert_only"))
    return "_converted" if is_conv else "_translated"


def read_user_output_suffix(task_state: dict) -> Optional[str]:
    """Read suffix from the task owner's user profile; empty string is valid."""
    owner = (task_state.get("owner_username") or "local").strip() or "local"
    is_conv = bool(task_state.get("is_format_conversion") or task_state.get("convert_only"))
    attr = "converter_output_suffix" if is_conv else "translator_output_suffix"
    try:
        from auth.user_profile import get_user_profile_manager

        profile = get_user_profile_manager().get_user_profile(owner)
        if hasattr(profile, attr):
            value = getattr(profile, attr)
            if value is not None:
                return str(value)
    except Exception:
        pass
    return None


def get_output_suffix(task_state: Optional[Dict[str, Any]] = None, default: str | None = None) -> str:
    """Resolve the output filename suffix for downloads.

    Priority matches GET /auth/app-config:
    1. Task owner's user profile (supports empty suffix)
    2. Global app_config.json
    3. Task snapshot in *task_state*
    4. Built-in default (_translated / _converted)
    """
    ctx = task_state or {}
    if default is None:
        default = resolve_default_output_suffix(ctx)

    user_suffix = read_user_output_suffix(ctx)
    if user_suffix is not None:
        return user_suffix

    try:
        from config import get_app_config

        cfg = get_app_config()
        is_conv = default == "_converted"
        cfg_suffix = cfg.converter_output_suffix if is_conv else cfg.translator_output_suffix
        if cfg_suffix is not None:
            return cfg_suffix
    except Exception:
        pass

    snapshot = ctx.get("output_suffix")
    if snapshot is not None:
        return snapshot
    return default
