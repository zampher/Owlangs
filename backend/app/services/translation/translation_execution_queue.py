# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

"""
In-process FIFO queue for translation tasks (queued execution mode).

Workers consume task_ids and delegate to TranslationService.process_queued_task.
Concurrency is controlled by OWLANGS_TRANSLATION_QUEUE_WORKERS (default 1).
"""

from __future__ import annotations

import asyncio
import os
from typing import List, Optional

from logger import unified_logger as logger
from logger.logger import LogModule

_ENV_WORKERS = "OWLANGS_TRANSLATION_QUEUE_WORKERS"

_queue: Optional[asyncio.Queue[str]] = None
_worker_tasks: List[asyncio.Task] = []
_started: bool = False
_stop_requested: bool = False


async def _worker_loop(worker_id: int) -> None:
    global _stop_requested
    logger.info(LogModule.SYSTEM, f"[TRANSLATION-QUEUE] Worker {worker_id} started")
    assert _queue is not None
    while not _stop_requested:
        try:
            task_id = await asyncio.wait_for(_queue.get(), timeout=0.5)
        except asyncio.TimeoutError:
            continue
        except asyncio.CancelledError:
            break
        try:
            # Late import avoids circular dependency at module load.
            from backend.app.routes.service.app_routes_translation import translation_service

            await translation_service.process_queued_task(task_id)
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error(
                LogModule.SYSTEM,
                f"[TRANSLATION-QUEUE] Worker {worker_id} error processing task_id={task_id}: {e}",
                exc_info=True,
            )
        finally:
            try:
                _queue.task_done()
            except ValueError:
                pass
    logger.info(LogModule.SYSTEM, f"[TRANSLATION-QUEUE] Worker {worker_id} stopped")


async def start_translation_execution_queue() -> None:
    """Start queue workers (idempotent)."""
    global _queue, _worker_tasks, _started, _stop_requested
    if _started:
        return
    _stop_requested = False
    _queue = asyncio.Queue()
    n_raw = os.environ.get(_ENV_WORKERS, "1").strip()
    try:
        n = max(1, int(n_raw))
    except ValueError:
        logger.warning(
            LogModule.SYSTEM,
            f"[TRANSLATION-QUEUE] Invalid {_ENV_WORKERS}={n_raw!r}, using 1",
        )
        n = 1
    for i in range(n):
        t = asyncio.create_task(_worker_loop(i), name=f"owlangs-translation-queue-{i}")
        _worker_tasks.append(t)
    _started = True
    logger.info(LogModule.SYSTEM, f"[TRANSLATION-QUEUE] Started {n} worker(s) ({_ENV_WORKERS}={n_raw!r})")


async def stop_translation_execution_queue() -> None:
    """Stop workers (best-effort)."""
    global _started, _stop_requested, _worker_tasks, _queue
    _stop_requested = True
    for t in _worker_tasks:
        if not t.done():
            t.cancel()
            try:
                await t
            except asyncio.CancelledError:
                pass
            except Exception:
                pass
    _worker_tasks.clear()
    _started = False
    _queue = None
    logger.info(LogModule.SYSTEM, "[TRANSLATION-QUEUE] Stopped workers")


async def enqueue_translation_task(task_id: str) -> None:
    """Append a task to the queue (call after task_state is ready and status is ``queued``)."""
    global _queue
    if _queue is None:
        await start_translation_execution_queue()
    assert _queue is not None
    await _queue.put(task_id)
    logger.info(LogModule.SYSTEM, f"[TRANSLATION-QUEUE] Enqueued task_id={task_id}")


async def drain_pending_execution_queue_task_ids() -> List[str]:
    """
    Remove task IDs waiting in the asyncio FIFO without executing them.

    Used by admin purge so queued work is not started after clearing memory/stash.
    """
    global _queue
    drained: List[str] = []
    if _queue is None:
        return drained
    while True:
        try:
            tid = _queue.get_nowait()
        except asyncio.QueueEmpty:
            break
        drained.append(tid)
        try:
            _queue.task_done()
        except ValueError:
            pass
    if drained:
        logger.info(
            LogModule.SYSTEM,
            f"[TRANSLATION-QUEUE] Drained {len(drained)} pending queue slot(s): {drained[:12]}...",
        )
    return drained
