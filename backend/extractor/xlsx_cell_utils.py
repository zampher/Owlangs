# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0
"""Shared XLSX cell typing and date/number round-trip helpers."""

from __future__ import annotations

import re
from datetime import datetime, time as dt_time
from typing import Any, Dict, Optional, Tuple

# Excel serial range for calendar dates roughly 1982-2050 (day-level integers).
_EXCEL_DATE_SERIAL_MIN = 30_000
_EXCEL_DATE_SERIAL_MAX = 55_000

_ISO_DATE_PATTERNS = (
    ("%Y-%m-%d %H:%M:%S", "datetime"),
    ("%Y-%m-%d", "date"),
    ("%H:%M:%S", "time"),
)

_DEFAULT_DATE_NUMBER_FORMAT = "yyyy-mm-dd"
_DEFAULT_DATETIME_NUMBER_FORMAT = "yyyy-mm-dd hh:mm:ss"
_DEFAULT_TIME_NUMBER_FORMAT = "hh:mm:ss"


def _is_time_only_format(number_format: str) -> bool:
    nf = number_format.lower()
    _cjk_date = {"年", "月", "日", "년", "월", "일"}
    _has_cjk_date = any(t in nf for t in _cjk_date)
    date_tokens = ("y", "d", "年", "月", "日", "년", "월", "일", "г", "д", "t", "j")
    time_tokens = (
        "h", "s", "am/pm", "a/p", "时", "分", "秒", "時", "시", "분", "초",
        "ч", "с", "мин", "сек", "std", "sek",
    )
    has_date = any(t in nf for t in date_tokens) or _has_cjk_date
    has_time = any(t in nf for t in time_tokens)
    return has_time and not has_date


def nf_has_date_token(number_format: str) -> bool:
    nf_lower = number_format.lower()
    if any(t in nf_lower for t in ("y", "年", "년", "г", "j")):
        return True
    if any(t in number_format for t in ("ddd", "dddd", "aaa", "aaaa", "曜日", "星期")):
        return True
    if re.search(r"(?<![a-z])d(?=[^a-z]|\d|$)", nf_lower):
        return True
    return False


def is_general_like_number_format(number_format: str) -> bool:
    nf = (number_format or "").strip().lower()
    return nf in ("general", "@", "", "0", "0.00")


def classify_excel_numeric_cell(
    value: Any,
    number_format: str,
    *,
    is_date_flag: bool = False,
) -> Optional[str]:
    """Return cell_value_kind for numeric cells: date, datetime, time, percentage, or None."""
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return None

    nf = str(number_format or "")
    if "%" in nf:
        return "percentage"

    if is_date_flag or nf_has_date_token(nf):
        if isinstance(value, float) and 0.0 < value < 1.0:
            return "time"
        if _is_time_only_format(nf):
            return "time"
        if isinstance(value, float) and not float(value).is_integer():
            hour_frac = value - int(value)
            if hour_frac > 0:
                return "datetime"
        return "date"

    # Custom time-only formats (e.g. "h:mm:ss") that lack a built-in date
    # flag — openpyxl read_only mode does not set is_date for these.
    if _is_time_only_format(nf):
        return "time"

    if is_general_like_number_format(nf):
        serial = float(value)
        if _EXCEL_DATE_SERIAL_MIN <= serial <= _EXCEL_DATE_SERIAL_MAX:
            if serial == int(serial):
                return "date"
            hour_frac = serial - int(serial)
            if 0.0 < hour_frac < 1.0:
                return "datetime"

    return None


def excel_serial_to_iso_text(value: float, number_format: str = "") -> str:
    from openpyxl.utils.datetime import from_excel

    dt = from_excel(value)
    if isinstance(value, float) and 0.0 < value < 1.0:
        return dt.strftime("%H:%M:%S")
    if _is_time_only_format(number_format):
        return dt.strftime("%H:%M:%S")
    if dt.hour != 0 or dt.minute != 0 or dt.second != 0:
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    return dt.strftime("%Y-%m-%d")


def try_iso_to_excel_serial(text: str) -> Optional[float]:
    if not isinstance(text, str) or not text.strip():
        return None

    text = text.strip()
    for fmt, kind in _ISO_DATE_PATTERNS:
        try:
            dt = datetime.strptime(text, fmt)
            from openpyxl.utils.datetime import to_excel

            serial = to_excel(dt)
            if kind == "time":
                # datetime.strptime for %H:%M:%S fills in 1900-01-01 as the
                # date, which produces serial ≈ 1 + fractional.  Keep only
                # the fractional part for pure time values.
                serial = serial - int(serial)
            elif kind == "date" and dt.hour == 0 and dt.minute == 0 and dt.second == 0:
                serial = float(int(serial))
            return float(serial)
        except ValueError:
            continue
    return None


def resolve_date_number_format(number_format: str, cell_value_kind: str) -> str:
    nf = str(number_format or "").strip()
    if nf and not is_general_like_number_format(nf):
        return nf
    if cell_value_kind == "time":
        return _DEFAULT_TIME_NUMBER_FORMAT
    if cell_value_kind == "datetime":
        return _DEFAULT_DATETIME_NUMBER_FORMAT
    return _DEFAULT_DATE_NUMBER_FORMAT


def format_xlsx_cell_for_extraction(cell) -> Tuple[Optional[str], Dict[str, Any]]:
    """Convert an openpyxl cell to extractable text plus round-trip metadata."""
    val = cell.value
    if val is None:
        return None, {}

    nf = str(getattr(cell, "number_format", "") or "")
    dt = str(getattr(cell, "data_type", "") or "")
    meta: Dict[str, Any] = {
        "number_format": nf,
        "data_type": dt,
    }

    if isinstance(val, datetime):
        meta["cell_value_kind"] = (
            "date"
            if val.hour == 0 and val.minute == 0 and val.second == 0
            else "datetime"
        )
        meta["excel_serial"] = try_iso_to_excel_serial(
            val.strftime("%Y-%m-%d %H:%M:%S")
            if meta["cell_value_kind"] == "datetime"
            else val.strftime("%Y-%m-%d")
        )
        if meta["cell_value_kind"] == "datetime":
            return val.strftime("%Y-%m-%d %H:%M:%S"), meta
        return val.strftime("%Y-%m-%d"), meta

    if isinstance(val, dt_time):
        # Native time objects (openpyxl stores pure times as datetime.time)
        serial = (val.hour * 3600 + val.minute * 60 + val.second) / 86400.0
        meta["cell_value_kind"] = "time"
        meta["excel_serial"] = serial
        return val.strftime("%H:%M:%S"), meta

    if isinstance(val, (int, float)) and not isinstance(val, bool):
        kind = classify_excel_numeric_cell(
            val,
            nf,
            is_date_flag=getattr(cell, "is_date", False),
        )
        if kind == "percentage":
            return f"{float(val) * 100}%", {**meta, "cell_value_kind": "percentage"}
        if kind in ("date", "datetime", "time"):
            serial = float(val)
            meta["cell_value_kind"] = kind
            meta["excel_serial"] = serial
            return excel_serial_to_iso_text(serial, nf), meta
        return str(val), meta

    text = str(val)
    return (text if text.strip() else None), meta


def apply_xlsx_translated_cell_value(
    cell,
    translated_text: str,
    cell_info: Dict[str, Any],
) -> None:
    """Write translated text back to a cell, restoring typed values when possible."""
    original_nf = str(cell_info.get("number_format") or "")
    kind = cell_info.get("cell_value_kind")
    stored_serial = cell_info.get("excel_serial")

    if kind in ("date", "datetime", "time"):
        serial = try_iso_to_excel_serial(translated_text)
        if serial is None and stored_serial is not None:
            try:
                parsed = float(str(translated_text).strip())
            except (TypeError, ValueError):
                parsed = None
            if parsed is not None and abs(parsed - float(stored_serial)) < 0.0001:
                serial = float(stored_serial)
        if serial is not None:
            cell.value = serial
            cell.number_format = resolve_date_number_format(original_nf, kind)
            return

    if kind == "percentage":
        text = str(translated_text).strip()
        if text.endswith("%"):
            try:
                cell.value = float(text[:-1].strip()) / 100.0
                cell.number_format = original_nf or "0%"
                return
            except (TypeError, ValueError):
                pass

    cell.value = translated_text
    if original_nf:
        cell.number_format = original_nf
