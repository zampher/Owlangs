# SPDX-FileCopyrightText: 2025 Owlangs
# SPDX-License-Identifier: MPL-2.0

"""
Donor trial: 15-day grace for new installs without activation.

- effective_activated = activated OR within trial period
- Trial state is used to show status and features (e.g. Pro / Web trial) but does not
  directly block translation task creation; callers decide how to interpret it.

- Trial anchor: earliest trial start date is stored in two places: (1) system data dir
  (survives typical uninstall), (2) a more hidden dir (generic-looking path, no app name).
  Effective date = min(secrets, anchor1, anchor2). Writing updates both anchors.
"""

import hashlib
import json
import os
import platform
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

TRIAL_DAYS = 15

_ANCHOR_SALT = b"owlangs-trial-anchor-v1"
_ANCHOR_SECONDARY_DIR_SALT = b"owlangs-trial-2nd-dir-v1"


def _get_trial_anchor_path_primary() -> Optional[Path]:
    """Primary: machine-specific file under system data dir (e.g. C:\\ProgramData\\Owlangs)."""
    try:
        from utils.path_utils import get_system_data_dir
        from utils.machine_id import get_machine_id
        data_dir = Path(get_system_data_dir())
        data_dir.mkdir(parents=True, exist_ok=True)
        mid = get_machine_id()
        name = ".ol_" + hashlib.sha256(_ANCHOR_SALT + mid.encode("utf-8")).hexdigest()[:16]
        return data_dir / name
    except Exception:
        return None


def _get_trial_anchor_path_secondary() -> Optional[Path]:
    """Secondary: under a generic-looking cache dir (no app name in path) for extra concealment."""
    try:
        from utils.machine_id import get_machine_id
        system = platform.system().lower()
        if system == "windows":
            base = os.environ.get("LOCALAPPDATA") or os.environ.get("TEMP") or "."
        elif system == "darwin":
            base = os.path.join(os.path.expanduser("~"), "Library", "Caches")
        else:
            base = os.environ.get("XDG_CACHE_HOME") or os.path.join(os.path.expanduser("~"), ".cache")
        parent_name = hashlib.sha256(_ANCHOR_SECONDARY_DIR_SALT).hexdigest()[:12]
        sub_name = hashlib.sha256(_ANCHOR_SALT + get_machine_id().encode("utf-8")).hexdigest()[:12]
        anchor_dir = Path(base) / parent_name
        anchor_dir.mkdir(parents=True, exist_ok=True)
        return anchor_dir / sub_name
    except Exception:
        return None


def _get_trial_anchor_paths() -> List[Path]:
    """Return both anchor paths (primary first)."""
    out: List[Path] = []
    for getter in (_get_trial_anchor_path_primary, _get_trial_anchor_path_secondary):
        p = getter()
        if p is not None:
            out.append(p)
    return out


def _read_one_anchor(path: Path) -> Optional[str]:
    """Read one anchor file; return ISO date or None."""
    if not path.is_file():
        return None
    try:
        raw = path.read_text(encoding="utf-8")
        data = json.loads(raw) if raw.strip() else {}
        s = (data.get("e") or "").strip()[:10]
        if s and len(s) == 10:
            datetime.strptime(s, "%Y-%m-%d")
            return s
    except Exception:
        pass
    return None


def read_trial_anchor() -> Optional[str]:
    """Read earliest trial start from all anchor files; return min date or None."""
    dates: List[str] = []
    for path in _get_trial_anchor_paths():
        d = _read_one_anchor(path)
        if d:
            dates.append(d)
    return min(dates) if dates else None


def write_trial_anchor(date_str: str) -> None:
    """Persist earliest trial start to both anchor paths (only update if date_str is earlier)."""
    try:
        s = (date_str or "").strip()[:10]
        if not s or len(s) != 10:
            return
        datetime.strptime(s, "%Y-%m-%d")
    except (ValueError, TypeError):
        return
    current = read_trial_anchor()
    to_write = min(s, current) if current else s
    payload = json.dumps({"e": to_write}, ensure_ascii=False)
    for path in _get_trial_anchor_paths():
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(payload, encoding="utf-8")
            try:
                os.chmod(path, 0o600)
            except Exception:
                pass
        except Exception:
            pass


def get_effective_trial_start(secrets_trial_start: Optional[str]) -> str:
    """
    Return effective trial start date for this machine (earliest of secrets and anchor).
    Persists current secrets value to anchor so anchor keeps the earliest date across reinstalls.
    Call this when returning trial_start_date to callers and when normalizing missing trial.
    """
    today = date.today().isoformat()
    anchor = read_trial_anchor()
    if secrets_trial_start:
        s = secrets_trial_start.strip()[:10]
        if s and len(s) == 10:
            try:
                datetime.strptime(s, "%Y-%m-%d")
                effective = min(s, anchor) if anchor else s
                write_trial_anchor(secrets_trial_start)
                return effective
            except ValueError:
                pass
        return anchor or today
    effective = anchor or today
    write_trial_anchor(effective)
    return effective


def get_trial_ends_at(trial_start_date_str: Optional[str]) -> Optional[str]:
    """
    Return trial end date as ISO date string (YYYY-MM-DD), or None if no trial.
    """
    if not trial_start_date_str or not isinstance(trial_start_date_str, str):
        return None
    s = trial_start_date_str.strip()
    if not s:
        return None
    try:
        start = datetime.strptime(s[:10], "%Y-%m-%d").date()
        end = start + timedelta(days=TRIAL_DAYS)
        return end.isoformat()
    except (ValueError, TypeError):
        return None


def is_trial_expired(trial_ends_at_str: Optional[str], today: Optional[date] = None) -> bool:
    """True if trial end date is in the past."""
    if not trial_ends_at_str:
        return True  # no trial
    d = today or date.today()
    try:
        end = datetime.strptime(trial_ends_at_str.strip()[:10], "%Y-%m-%d").date()
        return d >= end
    except (ValueError, TypeError):
        return True


def is_effective_activated(
    activated: bool,
    trial_start_date_str: Optional[str],
    today: Optional[date] = None,
) -> Tuple[bool, Optional[str], bool]:
    """
    Compute effective Pro state (activated or within trial).

    Returns:
        (effective_activated, trial_ends_at_iso, trial_expired)
    """
    if activated:
        return True, None, False
    trial_ends_at = get_trial_ends_at(trial_start_date_str)
    if not trial_ends_at:
        return False, None, True
    expired = is_trial_expired(trial_ends_at, today)
    if expired:
        return False, trial_ends_at, True
    return True, trial_ends_at, False


def can_create_translation_task(
    donor_activation: Dict[str, Any],
    edition: str,
) -> Tuple[bool, Optional[str]]:
    """
    Whether the deployment may create new translation tasks (legacy helper).

    Current design does not hard-block translation tasks even when trial expired.
    This helper always returns (True, None) and is kept for potential future use.

    Args:
        donor_activation: from secrets_manager.get_donor_activation() (activated, trial_start_date).
        edition: "PRO" or "PRO-WEB".

    Returns:
        (allowed, error_message). error_message set only when allowed is False for Web.
    """
    # No hard block for now; desktop standard edition must always remain usable.
    return True, None
