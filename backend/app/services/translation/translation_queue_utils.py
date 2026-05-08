# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

"""Pure helpers for translation task queue (no side effects, minimal imports)."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple


def queue_position_for_task(all_tasks: Dict[str, Dict[str, Any]], task_id: str) -> Optional[int]:
    """1-based position among tasks with status ``queued``, ordered by ``queued_at`` then ``task_id``."""
    ts = all_tasks.get(task_id)
    if not ts or ts.get("status") != "queued":
        return None
    queued: List[Tuple[str, float]] = []
    for tid, st in all_tasks.items():
        if st.get("status") == "queued":
            qa = float(st.get("queued_at") or st.get("task_start_time") or 0.0)
            queued.append((tid, qa))
    queued.sort(key=lambda x: (x[1], x[0]))
    for i, (tid, _) in enumerate(queued):
        if tid == task_id:
            return i + 1
    return None
