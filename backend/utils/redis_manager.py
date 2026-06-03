# SPDX-FileCopyrightText: 2026 Zamphersss
# SPDX-License-Identifier: MPL-2.0

import os
import sys
import subprocess
import shutil
import time
import signal
import atexit
import threading
from pathlib import Path
from typing import Optional
import redis

# Import unified logger
from logger import unified_logger, LogModule


class LocalRedisManager:
    """Local Redis manager - automatically start and manage Redis service"""

    def __init__(self):
        self.redis_process: Optional[subprocess.Popen] = None
        self.redis_client: Optional[redis.Redis] = None
        self.redis_port = 6379
        self.redis_host = "127.0.0.1"
        self._original_sigterm_handler = None
        self._original_sigint_handler = None
        self._redis_started = False  # Track if Redis was started by this instance

        # Register cleanup function on exit
        atexit.register(self.cleanup)

        # Save original signal handlers and set our handler
        # Our handler will cleanup Redis and then call the original handler
        # Note: signal.signal only works in main thread, so we wrap it in try/except
        try:
            if hasattr(signal, 'SIGTERM'):
                self._original_sigterm_handler = signal.signal(signal.SIGTERM, self._signal_handler)
            if hasattr(signal, 'SIGINT'):
                self._original_sigint_handler = signal.signal(signal.SIGINT, self._signal_handler)
        except ValueError:
            # signal.signal raises ValueError when called from non-main thread
            # This is expected when running in a thread (e.g., uvicorn reload mode)
            unified_logger.info(LogModule.SYSTEM, "Redis signal handlers not registered (not in main thread)")
            self._original_sigterm_handler = None
            self._original_sigint_handler = None
    
    def _signal_handler(self, signum, frame):
        """Signal handler - cleanup Redis and forward signal to original handler"""
        unified_logger.info(LogModule.SYSTEM, f"Received signal {signum}, shutting down Redis service...")
        try:
            # Only cleanup if not already cleaned up
            if self.redis_process and self.redis_process.poll() is None:
                self.cleanup()
        except Exception as e:
            unified_logger.warning(LogModule.SYSTEM, f"Error during cleanup: {e}")

        # Restore and call original signal handler to allow uvicorn to handle shutdown
        # This ensures the signal is properly propagated to uvicorn
        try:
            # Check which signal was received and call appropriate original handler
            if hasattr(signal, 'SIGTERM') and signum == signal.SIGTERM:
                if self._original_sigterm_handler is not None:
                    if callable(self._original_sigterm_handler):
                        self._original_sigterm_handler(signum, frame)
                        return
                    elif self._original_sigterm_handler == signal.SIG_DFL:
                        # Default handler - raise KeyboardInterrupt
                        raise KeyboardInterrupt()
                    elif self._original_sigterm_handler == signal.SIG_IGN:
                        # Ignore signal - do nothing
                        return

            if hasattr(signal, 'SIGINT') and signum == signal.SIGINT:
                if self._original_sigint_handler is not None:
                    if callable(self._original_sigint_handler):
                        self._original_sigint_handler(signum, frame)
                        return
                    elif self._original_sigint_handler == signal.SIG_DFL:
                        # Default handler - raise KeyboardInterrupt
                        raise KeyboardInterrupt()
                    elif self._original_sigint_handler == signal.SIG_IGN:
                        # Ignore signal - do nothing
                        return

            # No original handler or handler is not callable, raise KeyboardInterrupt
            # This will trigger uvicorn's shutdown mechanism
            raise KeyboardInterrupt()

        except KeyboardInterrupt:
            # Re-raise to allow uvicorn to catch it
            raise
        except Exception as e:
            # If original handler fails, raise KeyboardInterrupt as fallback
            unified_logger.warning(LogModule.SYSTEM, f"Error in original signal handler: {e}")
            raise KeyboardInterrupt()
    
    def _get_redis_path(self) -> Optional[Path]:
        """Get Redis executable file path"""
        if sys.platform == "win32":
            # Windows - Check multiple possible locations

            # 0. Check EXE-side directory (single-file portable mode: 3rdParty alongside EXE)
            #    This is the highest priority for portable/single-file deployments.
            try:
                exe_side = Path(sys.executable).parent / "3rdParty" / "windows" / "Redis-x64-3.0.504"
                exe_side_server = exe_side / "redis-server.exe"
                if exe_side_server.exists():
                    unified_logger.info(LogModule.SYSTEM, f"Found Redis alongside executable: {exe_side_server}")
                    return exe_side_server
            except Exception:
                pass

            # 1. Check PyInstaller environment (packaged executable)
            # In PyInstaller, sys.executable points to the EXE, and we can find Redis relative to it
            if hasattr(sys, '_MEIPASS'):
                # Running from PyInstaller - try to find Redis relative to executable
                exe_path = Path(sys.executable)
                # Onedir: EXE and 3rdParty are in the same folder
                redis_dir = exe_path.parent / "3rdParty" / "windows" / "Redis-x64-3.0.504"
                redis_server = redis_dir / "redis-server.exe"
                if redis_server.exists():
                    unified_logger.info(LogModule.SYSTEM, f"Found Redis in onedir directory: {redis_server}")
                    return redis_server
                # Onedir / onefile fallback: _MEIPASS contains bundled 3rdParty
                meipass_redis = Path(sys._MEIPASS) / "3rdParty" / "windows" / "Redis-x64-3.0.504" / "redis-server.exe"
                if meipass_redis.exists():
                    unified_logger.info(LogModule.SYSTEM, f"Found Redis in PyInstaller bundle directory: {meipass_redis}")
                    return meipass_redis
                # Legacy: EXE is in a subdir (e.g. bin/), Redis is in parent
                install_base = exe_path.parent.parent
                redis_dir = install_base / "3rdParty" / "windows" / "Redis-x64-3.0.504"
                redis_server = redis_dir / "redis-server.exe"
                if redis_server.exists():
                    unified_logger.info(LogModule.SYSTEM, f"Found Redis in installation directory: {redis_server}")
                    return redis_server

            # 2. Check installation directory (production)
            # Search common install locations; install dir first so user can override,
            # then ProgramData for the new installer layout.
            for install_dir in [
                Path("C:/Program Files/Owlangs"),
                Path("C:/Program Files (x86)/Owlangs"),
                Path(os.environ.get("PROGRAMDATA", "")) / "Owlangs",
                Path(os.environ.get("LOCALAPPDATA", "")) / "Owlangs",
            ]:
                if not install_dir.exists():
                    continue
                redis_dir = install_dir / "3rdParty" / "windows" / "Redis-x64-3.0.504"
                redis_server = redis_dir / "redis-server.exe"
                if redis_server.exists():
                    unified_logger.info(LogModule.SYSTEM, f"Found Redis in installation directory: {redis_server}")
                    return redis_server
            
            # 3. Check development directory
            dev_redis_dir = Path(__file__).parent.parent.parent / "3rdParty" / "windows" / "Redis-x64-3.0.504"
            dev_redis_server = dev_redis_dir / "redis-server.exe"
            if dev_redis_server.exists():
                unified_logger.info(LogModule.SYSTEM, f"Found Redis in development directory: {dev_redis_server}")
                return dev_redis_server

            # 4. Check current working directory
            cwd_redis_dir = Path.cwd() / "3rdParty" / "windows" / "Redis-x64-3.0.504"
            cwd_redis_server = cwd_redis_dir / "redis-server.exe"
            if cwd_redis_server.exists():
                unified_logger.info(LogModule.SYSTEM, f"Found Redis in current directory: {cwd_redis_server}")
                return cwd_redis_server
        elif sys.platform == "darwin":
            # macOS: Homebrew (Intel / Apple Silicon) then PATH
            for path in ("/usr/local/bin/redis-server", "/opt/homebrew/bin/redis-server"):
                p = Path(path)
                if p.exists():
                    return p
            path_in_env = shutil.which("redis-server")
            if path_in_env:
                return Path(path_in_env)
        elif sys.platform.startswith("linux"):
            # Linux: common path then PATH
            redis_server = Path("/usr/bin/redis-server")
            if redis_server.exists():
                return redis_server
            path_in_env = shutil.which("redis-server")
            if path_in_env:
                return Path(path_in_env)

        return None
    
    def _is_redis_running(self) -> bool:
        """Check if Redis is already running.

        Uses a thread-level timeout so that a stalled TCP connect (e.g. Windows
        firewall silently dropping SYN to 6379) does not block startup for 20+ seconds.
        """
        result = [False]

        def _try():
            try:
                client = redis.Redis(
                    host=self.redis_host,
                    port=self.redis_port,
                    socket_connect_timeout=1.0,
                )
                client.ping()
                result[0] = True
            except Exception:
                pass

        t = threading.Thread(target=_try, daemon=True)
        t.start()
        t.join(timeout=2.0)  # Hard timeout: never block startup longer than 2 seconds
        return result[0]
    
    def start_redis(self) -> bool:
        """Start Redis service"""
        # Check if Redis is disabled via environment variable
        redis_enabled = os.getenv("REDIS_ENABLED", "true").lower()
        if redis_enabled in ["false", "0", "no", "off"]:
            unified_logger.warning(LogModule.SYSTEM, "Redis is disabled via REDIS_ENABLED environment variable")
            return False

        # Check if Redis is disabled via configuration file
        try:
            from backend.config.local_config import load_config
            config = load_config()
            if hasattr(config, 'redis') and hasattr(config.redis, 'enabled') and not config.redis.enabled:
                unified_logger.warning(LogModule.SYSTEM, "Redis is disabled via configuration file")
                return False
        except Exception:
            # If config loading fails, continue with default behavior
            pass

        # If Redis is already running, return success directly
        if self._is_redis_running():
            unified_logger.info(LogModule.SYSTEM, "Redis service is already running")
            self._redis_started = True
            return True

        # Quick check: if we already tried to start and failed, don't retry immediately
        if hasattr(self, '_start_failed_time'):
            elapsed = time.time() - self._start_failed_time
            if elapsed < 5:  # Don't retry within 5 seconds
                unified_logger.info(LogModule.SYSTEM, f"Redis start was attempted recently ({elapsed:.1f}s ago), skipping")
                return False

        # Get Redis executable file path
        redis_server_path = self._get_redis_path()
        if not redis_server_path:
            unified_logger.error(LogModule.SYSTEM, "Redis executable file not found")
            self._start_failed_time = time.time()
            return False

        start_time = time.time()
        try:
            unified_logger.info(LogModule.SYSTEM, f"Starting local Redis service: {redis_server_path}")

            # Start Redis service with low priority to avoid blocking
            if sys.platform == "win32":
                # Windows: start with configuration file
                config_file = redis_server_path.parent / "redis.windows.conf"
                if config_file.exists():
                    # Use DETACHED_PROCESS to avoid blocking
                    self.redis_process = subprocess.Popen(
                        [str(redis_server_path), str(config_file)],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        creationflags=subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS
                    )
                else:
                    self.redis_process = subprocess.Popen(
                        [str(redis_server_path)],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        creationflags=subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS
                    )
            else:
                # Linux/macOS
                self.redis_process = subprocess.Popen(
                    [str(redis_server_path)],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )

            # Wait for Redis to start with optimized timeout
            max_wait = 5  # Reduced from 10 to 5 seconds for faster feedback
            check_interval = 0.1  # Check every 100ms for faster detection

            while time.time() - start_time < max_wait:
                if self._is_redis_running():
                    elapsed = time.time() - start_time
                    unified_logger.info(LogModule.SYSTEM, f"Redis service started successfully (took {elapsed:.2f}s)")
                    self._redis_started = True
                    return True
                time.sleep(check_interval)

            elapsed = time.time() - start_time
            unified_logger.error(LogModule.SYSTEM, f"Redis service startup timeout after {elapsed:.2f}s")
            self._start_failed_time = time.time()
            return False

        except Exception as e:
            unified_logger.error(LogModule.SYSTEM, f"Failed to start Redis service: {e}")
            self._start_failed_time = time.time()
            return False
    
    def get_redis_client(self) -> Optional[redis.Redis]:
        """Get Redis client"""
        # Return cached client if already connected
        if self.redis_client:
            try:
                self.redis_client.ping()
                return self.redis_client
            except Exception:
                # Connection lost, reset and retry
                self.redis_client = None

        # Check if Redis is disabled via environment variable
        redis_enabled = os.getenv("REDIS_ENABLED", "true").lower()
        if redis_enabled in ["false", "0", "no", "off"]:
            unified_logger.warning(LogModule.SYSTEM, "Redis is disabled via REDIS_ENABLED environment variable")
            return None

        # Check if Redis is disabled via configuration file
        try:
            from backend.config.local_config import load_config
            config = load_config()
            if hasattr(config, 'redis') and hasattr(config.redis, 'enabled') and not config.redis.enabled:
                unified_logger.warning(LogModule.SYSTEM, "Redis is disabled via configuration file")
                return None
        except Exception:
            # If config loading fails, continue with default behavior
            pass

        # Try to connect to existing Redis or start new one
        if not self._is_redis_running():
            if not self.start_redis():
                return None

        try:
            self.redis_client = redis.Redis(
                host=self.redis_host,
                port=self.redis_port,
                decode_responses=True,
                socket_connect_timeout=5,
                socket_timeout=5
            )
            # Test connection
            self.redis_client.ping()
        except Exception as e:
            unified_logger.error(LogModule.SYSTEM, f"Failed to connect to Redis: {e}")
            self.redis_client = None
            return None

        return self.redis_client

    def cleanup(self):
        """Clean up resources - only stop Redis if we started it"""
        # Only cleanup if we actually started Redis
        if not self._redis_started:
            return

        if self.redis_process and self.redis_process.poll() is None:
            unified_logger.info(LogModule.SYSTEM, "Shutting down Redis service...")
            try:
                if sys.platform == "win32":
                    # Windows: send termination signal
                    self.redis_process.terminate()
                else:
                    # Linux/macOS: send SIGTERM signal
                    self.redis_process.terminate()

                # Wait for process to end
                try:
                    self.redis_process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    # Force kill process
                    self.redis_process.kill()
                    self.redis_process.wait()

                unified_logger.info(LogModule.SYSTEM, "Redis service has been shut down")
            except Exception as e:
                unified_logger.warning(LogModule.SYSTEM, f"Error occurred while shutting down Redis service: {e}")
        elif self.redis_process is not None:
            unified_logger.info(LogModule.SYSTEM, "Redis service already shut down")

        self.redis_process = None
        self.redis_client = None


# Global Redis manager instance
_redis_manager: Optional[LocalRedisManager] = None


def get_redis_manager() -> LocalRedisManager:
    """Get global Redis manager instance"""
    global _redis_manager
    if _redis_manager is None:
        _redis_manager = LocalRedisManager()
    return _redis_manager


def get_redis_client() -> Optional[redis.Redis]:
    """Get Redis client (automatically start Redis service)"""
    manager = get_redis_manager()
    return manager.get_redis_client()
