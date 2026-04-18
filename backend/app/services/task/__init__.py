# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

"""
Task management services.

This package provides task state management, logging, and cleanup functionality.
"""

from .task_manager import TaskManager, task_manager

__all__ = ["TaskManager", "task_manager"]

