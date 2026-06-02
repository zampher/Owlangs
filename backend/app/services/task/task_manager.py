# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

"""
Task Manager Service

Manages task state, logs, and cleanup operations.
"""

import asyncio
import os
import shutil
import time
from typing import Dict, Any, Optional, List
from pathlib import Path

from logger import unified_logger as logger
from logger.logger import LogModule

# Task cleanup configuration
TASK_CLEANUP_INTERVAL = 3600  # 1 hour in seconds
TASK_MAX_AGE = 86400  # 24 hours in seconds


class TaskManager:
    """Manages task state, logs, and cleanup operations."""
    
    def __init__(self):
        """Initialize task manager with empty state."""
        self._tasks: Dict[str, Dict[str, Any]] = {}
        self._log_queues: Dict[str, asyncio.Queue] = {}
        self._log_histories: Dict[str, list] = {}
        self._last_logged_status: Dict[str, Dict[str, Any]] = {}
    
    def create_task(self, task_id: str) -> Dict[str, Any]:
        """
        Create a new task with default state.
        
        Args:
            task_id: Unique task identifier
            
        Returns:
            Created task state dictionary
        """
        task_state = {
            "is_processing": False,
            "status_message": "Idle",
            "error_flag": False,
            "download_ready": False,
            "workflow_instance": None,  # Only used during processing
            "original_filename_stem": None,
            "original_relative_path": None,
            "task_start_time": 0,
            "task_end_time": 0,
            "current_task_ref": None,
            "original_filename": None,
            "temp_dir": None,  # Directory for storing temporary files
            "downloadable_files": {},  # Store paths and names of downloadable files
            "attachment_files": {},  # Store paths and identifiers of attachment files
            # Additional fields for new service
            "status": "pending",
            "progress": 0,
            "message": "Task created, waiting to start...",
            "downloads": {},
            "attachments": {},
            "error": None,
            "created_at": None,
            "started_at": None,
            "completed_at": None,
        }
        
        self._tasks[task_id] = task_state
        self._log_queues[task_id] = asyncio.Queue()
        self._log_histories[task_id] = []
        
        return task_state
    
    def get_task(self, task_id: str) -> Optional[Dict[str, Any]]:
        """
        Get task state by task ID.
        
        Args:
            task_id: Unique task identifier
            
        Returns:
            Task state dictionary or None if not found
        """
        return self._tasks.get(task_id)
    
    def update_task(self, task_id: str, updates: Dict[str, Any]):
        """
        Update task state with new values.
        
        Args:
            task_id: Unique task identifier
            updates: Dictionary of updates to apply
        """
        if task_id in self._tasks:
            self._tasks[task_id].update(updates)
        else:
            logger.warning(LogModule.SYSTEM, f"[TASK-MANAGER] Attempted to update non-existent task: {task_id}")
    
    def delete_task(self, task_id: str):
        """
        Delete a task and clean up its resources.
        
        Args:
            task_id: Unique task identifier
        """
        self.cleanup_task_resources(task_id)
    
    def cleanup_task_resources(self, task_id: str):
        """
        Clean up resources for a specific task.
        
        Args:
            task_id: Unique task identifier
        """
        # Clean up status cache
        if task_id in self._last_logged_status:
            del self._last_logged_status[task_id]
        
        task_state = self._tasks.get(task_id)
        if task_state:
            # Clean up temporary directory
            temp_dir = task_state.get("temp_dir")
            if temp_dir and os.path.isdir(temp_dir):
                try:
                    shutil.rmtree(temp_dir)
                    logger.debug(LogModule.SYSTEM, f"[TASK-MANAGER] Cleaned up temp directory for task {task_id}")
                except Exception as e:
                    logger.warning(LogModule.SYSTEM, f"[TASK-MANAGER] Error cleaning temp directory for task {task_id}: {e}")
        
        # Remove from all data structures
        self._tasks.pop(task_id, None)
        self._log_queues.pop(task_id, None)
        self._log_histories.pop(task_id, None)
    
    def add_log(self, task_id: str, level: str, message: str):
        """
        Add a log entry to task history.
        
        Args:
            task_id: Unique task identifier
            level: Log level (info, warning, error, etc.)
            message: Log message
        """
        timestamp = time.time()
        
        log_entry = {
            "timestamp": timestamp,
            "level": level,
            "message": message
        }
        
        if task_id in self._log_histories:
            self._log_histories[task_id].append(log_entry)
        
        # Also add to queue for real-time access
        if task_id in self._log_queues:
            try:
                self._log_queues[task_id].put_nowait(log_entry)
            except asyncio.QueueFull:
                pass  # Queue is full, skip this log entry
    
    def get_logs(self, task_id: str) -> List[Dict[str, Any]]:
        """
        Get all logs for a task.
        
        Args:
            task_id: Unique task identifier
            
        Returns:
            List of log entries
        """
        return self._log_histories.get(task_id, [])
    
    def get_log_queue(self, task_id: str) -> Optional[asyncio.Queue]:
        """
        Get log queue for a task.
        
        Args:
            task_id: Unique task identifier
            
        Returns:
            Log queue or None if not found
        """
        return self._log_queues.get(task_id)
    
    def cleanup_expired_tasks(self):
        """Clean up expired tasks from memory."""
        current_time = time.time()
        expired_tasks = []
        
        for task_id, task_state in self._tasks.items():
            created_at = task_state.get("created_at", 0)
            if created_at and current_time - created_at > TASK_MAX_AGE:
                expired_tasks.append(task_id)
        
        for task_id in expired_tasks:
            logger.info(LogModule.SYSTEM, f"[TASK-MANAGER] Cleaning up expired task: {task_id}")
            self.cleanup_task_resources(task_id)
    
    def get_all_task_ids(self) -> List[str]:
        """
        Get list of all task IDs.
        
        Returns:
            List of task IDs
        """
        return list(self._tasks.keys())
    
    def get_all_tasks(self) -> Dict[str, Dict[str, Any]]:
        """
        Get all tasks as a dictionary.
        
        Returns:
            Dictionary mapping task_id to task_state
        """
        return self._tasks.copy()  # Return a copy to prevent external modification
    
    def get_last_logged_status(self, task_id: str) -> Optional[Dict[str, Any]]:
        """
        Get last logged status for a task.
        
        Args:
            task_id: Unique task identifier
            
        Returns:
            Last logged status dictionary or None if not found
        """
        return self._last_logged_status.get(task_id)
    
    def update_last_logged_status(self, task_id: str, status: Dict[str, Any]):
        """
        Update last logged status for a task.
        
        Args:
            task_id: Unique task identifier
            status: Status dictionary to store
        """
        self._last_logged_status[task_id] = status


# Global singleton instance
task_manager = TaskManager()

