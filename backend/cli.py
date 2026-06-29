# SPDX-FileCopyrightText: 2025 QinHan
# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

import argparse
import sys # Used to check command line argument count
import os
from pathlib import Path

# Set UTF-8 encoding for East Asian language environments
os.environ.setdefault('PYTHONIOENCODING', 'utf-8')
os.environ.setdefault('LC_ALL', 'en_US.UTF-8')
os.environ.setdefault('LANG', 'en_US.UTF-8')

# Add backend directory to Python path (must be before importing logger)
backend_dir = Path(__file__).resolve().parent
sys.path.insert(0, str(backend_dir))

# When frozen (PyInstaller), bundle has "backend" at _MEIPASS. Code uses "from utils.xxx".
# Ensure backend is on path and alias utils -> backend.utils; pre-register submodules used at
# import time so "utils.redis_manager" and "utils.utils" resolve in frozen exe.
if getattr(sys, "frozen", False):
    _mei = getattr(sys, "_MEIPASS", None)
    if _mei and _mei not in sys.path:
        sys.path.insert(0, _mei)
    _base = backend_dir.parent
    if _base and str(_base) not in sys.path:
        sys.path.insert(0, str(_base))
    import backend.utils as _backend_utils
    sys.modules["utils"] = _backend_utils
    # Pre-register submodules so "from utils.xxx" works in bundle (avoid ModuleNotFoundError)
    _utils_submodules = (
        "redis_manager",
        "utils",
        "language_utils",
        "path_utils",
        "resource_utils",
        "font_utils",
        "pagination",
        "document_rebuild",
        "translation_segments",
        "markdown_splitter",
        "markdown_utils",
        "json_utils",
        "chunk_translation_helper",
        "translation_validator",
        "chunk_size_converter",
        "token_estimator",
        "docx_utils",
        "table_utils",
        "image_placeholder_utils",
        "format_convert_utils",
        "math_md_normalize",
        "docx_md_normalize",
        "docx_algorithm_latex_wrap",
        "markdown_chunk_merger",
        "language_detection_utils",
        # LaTeX integrity check routes (used by app.routes.service.app_routes_formula_check)
        "latex_formula_checker",
        "latex_repair_llm",
        "latex_repair_payload",
        "latex_formula_batch_repair",
        "docx_math_fragment_check",
        "docx_math_fragment_llm_repair",
        "llm_client",
        "extract_segments_debug",
        # PDF split/merge: dynamic imports in converter_mineru.py
        "pdf_splitter",
        "layout_merger",
        "mineru_zip_merger",
        "epub_html_segments",
        "ebook_mobi_utils",
        "ebook_image_utils",
        "ebook_metadata",
    )
    import importlib
    for _sub in _utils_submodules:
        try:
            _mod = importlib.import_module(f"backend.utils.{_sub}")
        except ModuleNotFoundError:
            _mod = getattr(_backend_utils, _sub, None)
        if _mod is not None:
            sys.modules[f"utils.{_sub}"] = _mod

# Import logger after path setup
from logger.logger import unified_logger, LogModule


def _get_lock_file_path() -> Path:
    """Get the path to the singleton lock file"""
    if sys.platform == 'darwin':  # macOS
        lock_dir = Path.home() / "Library" / "Application Support" / "Owlangs"
    elif sys.platform == 'win32':  # Windows
        lock_dir = Path(os.environ.get('LOCALAPPDATA', Path.home() / 'AppData' / 'Local')) / "Owlangs"
    else:  # Linux
        lock_dir = Path.home() / ".config" / "Owlangs"
    
    lock_dir.mkdir(parents=True, exist_ok=True)
    return lock_dir / "owlangs.lock"


# Global lock file handle (kept open for the lifetime of the process)
_lock_file_handle = None


def _is_process_running(pid: int) -> bool:
    """Check if a process with the given PID is still running"""
    try:
        os.kill(pid, 0)  # Signal 0 is used to check if process exists
        return True
    except (OSError, ProcessLookupError):
        return False


def _acquire_singleton_lock() -> bool:
    """
    Acquire singleton lock using file locking.
    Returns True if lock acquired (first instance), False if another instance is running.
    """
    global _lock_file_handle
    import fcntl  # Unix-only; Windows uses different mechanism
    
    lock_file = _get_lock_file_path()
    print(f"[SINGLETON] Lock file: {lock_file}", flush=True)
    
    # Check if there's a stale lock file from a crashed process
    if lock_file.exists():
        try:
            old_pid = int(lock_file.read_text().strip())
            if not _is_process_running(old_pid):
                print(f"[SINGLETON] Removing stale lock file from crashed process (PID: {old_pid})", flush=True)
                lock_file.unlink()
            else:
                print(f"[SINGLETON] Process with PID {old_pid} is still running", flush=True)
        except (ValueError, OSError) as e:
            print(f"[SINGLETON] Could not read old lock file: {e}", flush=True)
    
    try:
        _lock_file_handle = open(lock_file, 'w')
        # Try to acquire exclusive lock without blocking
        fcntl.flock(_lock_file_handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        # Write PID to lock file for debugging
        _lock_file_handle.write(str(os.getpid()))
        _lock_file_handle.flush()
        print(f"[SINGLETON] Lock acquired (PID: {os.getpid()})", flush=True)
        return True
    except (IOError, OSError) as e:
        # Lock is held by another process
        print(f"[SINGLETON] Lock already held by another instance: {e}", flush=True)
        if _lock_file_handle:
            _lock_file_handle.close()
            _lock_file_handle = None
        return False


def _release_singleton_lock():
    """Release the singleton lock on exit"""
    global _lock_file_handle
    if _lock_file_handle:
        import fcntl
        try:
            fcntl.flock(_lock_file_handle.fileno(), fcntl.LOCK_UN)
            _lock_file_handle.close()
            print("[SINGLETON] Lock released", flush=True)
        except Exception as e:
            print(f"[SINGLETON] Error releasing lock: {e}", flush=True)
        finally:
            _lock_file_handle = None


def _check_port(port: int) -> bool:
    """Check if a port is already in use"""
    import socket
    print(f"[PORT-CHECK] Checking if port {port} is in use...", flush=True)
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.bind(("0.0.0.0", port))
            print(f"[PORT-CHECK] Port {port} is available", flush=True)
            return False  # Port is available
        except OSError as e:
            print(f"[PORT-CHECK] Port {port} is in use: {e}", flush=True)
            return True  # Port is in use


def _find_process_using_port(port: int) -> list:
    """Find processes using the specified port
    Returns list of dicts with 'pid', 'name', 'cmdline' info
    """
    import subprocess
    import re
    
    processes = []
    current_pid = str(os.getpid())  # Get current process PID
    print(f"[PORT-CHECK] Current process PID: {current_pid}", flush=True)
    
    try:
        if sys.platform == 'darwin':  # macOS
            # Use lsof to find processes using the port
            result = subprocess.run(
                ['lsof', '-i', f':{port}', '-P', '-n'],
                capture_output=True,
                text=True
            )
            if result.returncode == 0:
                lines = result.stdout.strip().split('\n')
                print(f"[PORT-CHECK] lsof found {len(lines)-1} processes using port {port}", flush=True)
                # Skip header line
                for line in lines[1:]:
                    parts = line.split()
                    if len(parts) >= 2:
                        name = parts[0]
                        pid = parts[1].strip()  # Ensure no whitespace
                        print(f"[PORT-CHECK] Checking PID {pid} (name: {name}) against current {current_pid}", flush=True)
                        # Skip current process (this is the process checking the port)
                        if pid == current_pid:
                            print(f"[PORT-CHECK] Skipping current process PID {pid}", flush=True)
                            continue
                        # Get command line
                        cmd_result = subprocess.run(
                            ['ps', '-p', pid, '-o', 'comm='],
                            capture_output=True,
                            text=True
                        )
                        cmdline = cmd_result.stdout.strip() if cmd_result.returncode == 0 else name
                        processes.append({
                            'pid': pid,
                            'name': name,
                            'cmdline': cmdline
                        })
        elif sys.platform == 'win32':  # Windows
            result = subprocess.run(
                ['netstat', '-ano', '|', 'findstr', f':{port}'],
                capture_output=True,
                text=True,
                shell=True
            )
            if result.returncode == 0:
                lines = result.stdout.strip().split('\n')
                for line in lines:
                    parts = line.split()
                    if len(parts) >= 5:
                        pid = parts[4]
                        # Skip current process
                        if pid == current_pid:
                            print(f"[PORT-CHECK] Skipping current process PID {pid}", flush=True)
                            continue
                        # Get process name
                        task_result = subprocess.run(
                            ['tasklist', '/FI', f'PID eq {pid}', '/FO', 'CSV', '/NH'],
                            capture_output=True,
                            text=True
                        )
                        if task_result.returncode == 0:
                            csv_parts = task_result.stdout.strip().strip('"').split('","')
                            name = csv_parts[0] if csv_parts else 'Unknown'
                        else:
                            name = 'Unknown'
                        processes.append({
                            'pid': pid,
                            'name': name,
                            'cmdline': name
                        })
        else:  # Linux
            result = subprocess.run(
                ['ss', '-tlnp'],
                capture_output=True,
                text=True
            )
            if result.returncode == 0:
                for line in result.stdout.split('\n'):
                    if f':{port}' in line:
                        # Parse ss output to extract pid
                        match = re.search(r'pid=(\d+)', line)
                        if match:
                            pid = match.group(1)
                            # Skip current process
                            if pid == current_pid:
                                print(f"[PORT-CHECK] Skipping current process PID {pid}", flush=True)
                                continue
                            # Get process info
                            cmd_result = subprocess.run(
                                ['cat', f'/proc/{pid}/comm'],
                                capture_output=True,
                                text=True
                            )
                            name = cmd_result.stdout.strip() if cmd_result.returncode == 0 else 'Unknown'
                            cmdline_result = subprocess.run(
                                ['cat', f'/proc/{pid}/cmdline'],
                                capture_output=True,
                                text=True
                            )
                            cmdline = cmdline_result.stdout.strip().replace('\x00', ' ') if cmdline_result.returncode == 0 else name
                            processes.append({
                                'pid': pid,
                                'name': name,
                                'cmdline': cmdline
                            })
    except Exception as e:
        print(f"[PORT-CHECK] Error finding process: {e}", flush=True)
    
    # Remove duplicates (same PID)
    seen_pids = set()
    unique_processes = []
    for proc in processes:
        if proc['pid'] not in seen_pids:
            seen_pids.add(proc['pid'])
            unique_processes.append(proc)
    
    return unique_processes


def _kill_process(pid: str) -> bool:
    """Kill a process by PID
    Returns True if successful
    """
    import subprocess
    import signal
    import time
    
    try:
        pid_int = int(pid)
        
        if sys.platform == 'win32':
            # Windows: use taskkill
            result = subprocess.run(
                ['taskkill', '/F', '/PID', str(pid)],
                capture_output=True,
                text=True
            )
            success = result.returncode == 0
        else:
            # Unix (macOS/Linux): use kill
            try:
                os.kill(pid_int, signal.SIGTERM)
                # Wait a bit for graceful shutdown
                time.sleep(1)
                # Check if still running
                try:
                    os.kill(pid_int, 0)  # Check if process exists
                    # Still running, force kill
                    os.kill(pid_int, signal.SIGKILL)
                    time.sleep(0.5)
                except OSError:
                    pass  # Process already terminated
                success = True
            except ProcessLookupError:
                success = True  # Process already gone
            except Exception as e:
                print(f"[PORT-CHECK] Error killing process: {e}", flush=True)
                success = False
        
        if success:
            print(f"[PORT-CHECK] Successfully terminated process {pid}", flush=True)
        else:
            print(f"[PORT-CHECK] Failed to terminate process {pid}", flush=True)
        
        return success
    except Exception as e:
        print(f"[PORT-CHECK] Error in kill_process: {e}", flush=True)
        return False


def _show_port_occupied_dialog(port: int) -> tuple:
    """Show dialog to user when port is occupied
    Returns (action, should_continue) where action is 'kill', 'continue', or 'cancel'
    """
    import subprocess
    import time
    
    print(f"[PORT-CHECK] Showing port occupied dialog for port {port}", flush=True)
    
    # Find processes using the port
    processes = _find_process_using_port(port)
    
    if processes:
        proc_info = "\n".join([f"• PID {p['pid']}: {p['name']}" for p in processes[:3]])  # Show max 3
        if len(processes) > 3:
            proc_info += f"\n... and {len(processes) - 3} more"
    else:
        proc_info = "(Could not identify the process)"
    
    message = f"Another Owlangs instance is already running and using port {port}.\n\nExisting process:\n{proc_info}\n\nWould you like to:\n• Terminate the existing process and start a new instance\n• Continue and connect to the existing instance\n• Cancel startup"
    
    if sys.platform == 'darwin':  # macOS
        print("[PORT-CHECK] Showing macOS dialog...", flush=True)
        try:
            # Try to show dialog with 3 buttons
            script = f'''display dialog "{message}" buttons {{"Cancel", "Use Existing", "Restart"}} default button "Restart" with title "Owlangs Already Running"'''
            result = subprocess.run(
                ['osascript', '-e', script],
                capture_output=True,
                text=True
            )
            print(f"[PORT-CHECK] Dialog result: {result.stdout}", flush=True)
            
            if 'Restart' in result.stdout:
                # Kill all found processes (the existing/old ones)
                killed_any = False
                for proc in processes:
                    if _kill_process(proc['pid']):
                        killed_any = True
                # Wait a moment for port to be released
                if killed_any:
                    time.sleep(2)
                    # Verify port is now free
                    if not _check_port(port):
                        return ('kill', True)
                    else:
                        # Port still in use, maybe a different process
                        return _show_port_occupied_dialog(port)  # Recurse
                return ('kill', False)
            elif 'Use Existing' in result.stdout:
                return ('continue', True)
            else:
                return ('cancel', False)
        except Exception as e:
            print(f"[PORT-CHECK] Dialog failed: {e}", flush=True)
            # Fallback to console
            return _console_port_dialog(port, processes)
    elif sys.platform == 'win32':  # Windows
        print("[PORT-CHECK] Showing Windows dialog...", flush=True)
        try:
            import ctypes
            # Windows MessageBox doesn't support 3 buttons easily, use console fallback
            return _console_port_dialog(port, processes)
        except Exception as e:
            print(f"[PORT-CHECK] Dialog failed: {e}", flush=True)
            return _console_port_dialog(port, processes)
    else:  # Linux
        print("[PORT-CHECK] Showing Linux dialog...", flush=True)
        try:
            # Try zenity with multiple buttons
            result = subprocess.run(
                ['zenity', '--question', '--title', 'Owlangs Already Running', 
                 '--text=' + message,
                 '--ok-label=Restart (Kill Old)', '--cancel-label=Use Existing'],
                capture_output=True
            )
            if result.returncode == 0:
                # User clicked Restart (Kill Old)
                killed_any = False
                for proc in processes:
                    if _kill_process(proc['pid']):
                        killed_any = True
                if killed_any:
                    time.sleep(2)
                    if not _check_port(port):
                        return ('kill', True)
                    else:
                        return _show_port_occupied_dialog(port)
                return ('kill', False)
            else:
                # User clicked Use Existing or Cancel
                return ('continue', True)
        except Exception:
            return _console_port_dialog(port, processes)


def _console_port_dialog(port: int, processes: list) -> tuple:
    """Console-based dialog for port conflict resolution"""
    import time
    
    print(f"\n{'='*60}", flush=True)
    print(f"  OWLANGS IS ALREADY RUNNING", flush=True)
    print(f"{'='*60}", flush=True)
    print(f"\n  Another Owlangs instance is using port {port}.", flush=True)
    
    if processes:
        print("\n  Existing process:", flush=True)
        for proc in processes:
            print(f"    PID {proc['pid']}: {proc['name']}", flush=True)
    else:
        print("\n  (Could not identify the existing process)", flush=True)
    
    print("\n  Options:", flush=True)
    print("    [1] Restart - Terminate old instance and start new", flush=True)
    print("    [2] Use Existing - Connect to running instance", flush=True)
    print("    [3] Cancel - Exit without starting", flush=True)
    print(f"{'='*60}", flush=True)
    
    while True:
        try:
            choice = input("\n  Your choice (1-3): ").strip()
            
            if choice == '1':
                killed_any = False
                for proc in processes:
                    if _kill_process(proc['pid']):
                        killed_any = True
                if killed_any:
                    print("  Waiting for old instance to terminate...", flush=True)
                    time.sleep(2)
                    if not _check_port(port):
                        print("  ✓ Old instance terminated, starting new...", flush=True)
                        return ('kill', True)
                    else:
                        print("  ! Port still in use, checking again...", flush=True)
                        return _console_port_dialog(port, _find_process_using_port(port))
                return ('kill', False)
            
            elif choice == '2':
                print("  Using existing instance...", flush=True)
                return ('continue', True)
            
            elif choice == '3':
                print("  Startup cancelled.", flush=True)
                return ('cancel', False)
            
            else:
                print("  Invalid choice, please enter 1, 2, or 3.", flush=True)
        
        except KeyboardInterrupt:
            print("\n  Startup cancelled.", flush=True)
            return ('cancel', False)
        except EOFError:
            # Non-interactive mode, default to continue
            print("  Non-interactive mode, continuing anyway...", flush=True)
            return ('continue', True)


def main():
    """Main entry point for the CLI"""
    # ── CLI mode: delegate to owlangs_cli for translate/convert/batch etc. ──
    CLI_COMMANDS = {
        "translate", "convert", "batch", "status", "download",
        "cancel", "platform", "formats", "glossary", "config",
    }
    # Skip global flags (e.g. --json, -v) placed before the subcommand
    _cli_idx = 1
    while _cli_idx < len(sys.argv) and sys.argv[_cli_idx].startswith("-"):
        _cli_idx += 1
    if _cli_idx < len(sys.argv) and sys.argv[_cli_idx] in CLI_COMMANDS:
        from backend.owlangs_cli import main as cli_main
        sys.exit(cli_main())

    # Create parser with description that includes version info
    parser = argparse.ArgumentParser(
        description="Owlangs CLI - Command line interface for Owlangs backend"
    )
    
    # Add arguments
    parser.add_argument(
        '-i', '--interactive',
        action='store_true',
        help='Start the graphical interface (GUI mode)'
    )
    parser.add_argument(
        '-p', '--port',
        type=int,
        default=8800,
        help='Port to run the server on (default: 8800)'
    )
    parser.add_argument(
        '-v', '--version',
        action='store_true',
        help='Show version information'
    )
    parser.add_argument(
        '--mcp-port',
        type=int,
        default=8100,
        help='Port for the MCP HTTP server (default: 8100)'
    )
    parser.add_argument(
        '--no-mcp',
        action='store_true',
        help='Disable MCP server startup (start FastAPI only)'
    )

    # Strip multiprocessing-fork args before parse_args (PyInstaller + uvicorn reload spawns child with these)
    # Child process would otherwise fail with "unrecognized arguments: --multiprocessing-fork parent_pid=... pipe_handle=..."
    _argv = []
    i = 0
    while i < len(sys.argv):
        if sys.argv[i] == "--multiprocessing-fork":
            i += 1
            while i < len(sys.argv) and (
                sys.argv[i].startswith("parent_pid=") or sys.argv[i].startswith("pipe_handle=")
            ):
                i += 1
            continue
        _argv.append(sys.argv[i])
        i += 1
    sys.argv = _argv

    # Check if no arguments are provided (except the script name itself)
    if len(sys.argv) == 1:
        unified_logger.info(LogModule.SYSTEM, "Welcome to Owlangs!")
        unified_logger.info(LogModule.SYSTEM, "Please use '-i' or '--interactive' option to start the graphical interface.")
        unified_logger.info(LogModule.SYSTEM, "Examples: backend -i | backend --interactive")
        sys.exit(0)

    args = parser.parse_args()

    # Call core logic
    if args.interactive: # Note: this is args.interactive, corresponding to "--interactive"
        # 直接使用uvicorn启动，避免复杂的模块导入
        import uvicorn
        import subprocess
        
        port = args.port or 8800
        
        # Step 1: Try to acquire singleton lock (file-based)
        # This is the primary mechanism to prevent multiple instances
        print(f"[SINGLETON] Checking if another instance is running...", flush=True)
        
        # Unix systems (macOS/Linux): use file locking
        if sys.platform != 'win32':
            try:
                has_lock = _acquire_singleton_lock()
                if not has_lock:
                    # Another instance is running, open browser and exit
                    print("[SINGLETON] Another instance is already running, opening browser...", flush=True)
                    import webbrowser
                    url = f"http://localhost:{port}"
                    webbrowser.open(url)
                    print(f"[SINGLETON] Browser opened: {url}", flush=True)
                    print("[SINGLETON] Exiting (singleton mode)", flush=True)
                    sys.exit(0)
                # Lock acquired, register cleanup on exit
                import atexit
                atexit.register(_release_singleton_lock)
                print("[SINGLETON] Singleton lock acquired, this is the first instance", flush=True)
            except ImportError:
                # fcntl not available, fall back to port check
                print("[SINGLETON] File locking not available, falling back to port check", flush=True)
                has_lock = None  # Indicate fallback
        else:
            has_lock = None  # Windows: fall back to port check
        
        # Step 2: Fallback to port check (if file lock not available or on Windows)
        if has_lock is None:
            print(f"[PORT-CHECK] Starting port check for port {port}", flush=True)
            try:
                is_port_in_use = _check_port(port)
                print(f"[PORT-CHECK] Port check result: port_in_use={is_port_in_use}", flush=True)
                
                if is_port_in_use:
                    print(f"[PORT-CHECK] 端口 {port} 已被占用", flush=True)
                    
                    # macOS: When launched from Dock, directly open browser without dialog
                    if sys.platform == 'darwin':
                        print("[PORT-CHECK] macOS detected, opening browser to existing instance...", flush=True)
                        import webbrowser
                        url = f"http://localhost:{port}"
                        webbrowser.open(url)
                        print(f"[PORT-CHECK] 浏览器已打开: {url}", flush=True)
                        sys.exit(0)
                    
                    # Windows/Linux: Show dialog for choice
                    action, should_continue = _show_port_occupied_dialog(port)
                    if not should_continue:
                        print("[PORT-CHECK] 用户取消启动", flush=True)
                        sys.exit(0)
                    if action == 'kill':
                        print("[PORT-CHECK] 已终止占用进程，继续启动...", flush=True)
                    else:  # action == 'continue' (Use Existing)
                        print("[PORT-CHECK] 使用已存在的实例，打开浏览器...", flush=True)
                        import webbrowser
                        url = f"http://localhost:{port}"
                        webbrowser.open(url)
                        print(f"[PORT-CHECK] 浏览器已打开: {url}", flush=True)
                        sys.exit(0)
            except Exception as e:
                print(f"[PORT-CHECK] Error during port check: {e}", flush=True)
                import traceback
                print(f"[PORT-CHECK] Traceback: {traceback.format_exc()}", flush=True)
            
            print("[PORT-CHECK] Port check completed, starting server...", flush=True)
        else:
            print("[SINGLETON] Skip port check (file lock acquired)", flush=True)
        unified_logger.info(LogModule.SYSTEM, "Starting Owlangs backend server on port {port}", port=port)
        unified_logger.info(LogModule.SYSTEM, "Owlangs will be available at: http://localhost:{port}", port=port)
        unified_logger.info(LogModule.SYSTEM, "Press Ctrl+C to stop the server")
        unified_logger.info(LogModule.SYSTEM, "-" * 50)
        
        # 配置日志格式，确保所有日志都包含时间戳
        from logger.logger import get_uvicorn_log_config
        
        # Use uvicorn to start server.
        # Disable reload when frozen (PyInstaller): reload spawns child process with --multiprocessing-fork
        # args that our CLI does not accept, so the worker never starts and health check always fails.
        # In debug mode (debugpy attached), also disable reload to avoid interference.
        is_debugging = hasattr(sys, "gettrace") and sys.gettrace() is not None
        is_frozen = getattr(sys, "frozen", False)
        enable_reload = not is_debugging and not is_frozen

        # In frozen build, pre-import backend.app so sys.modules["app"] is set for uvicorn's import_from_string("app.factory:app")
        if is_frozen:
            import backend.app  # noqa: F401

        try:
            # Start server in a separate thread
            import threading

            # Note: reload mode uses signal.signal() which only works in main thread.
            # Since we're starting server in a thread, we must disable reload.
            if enable_reload:
                unified_logger.info(LogModule.SYSTEM, "Reload mode disabled: cannot use reload when running server in a thread")
            reload = False  # Always disable reload when using thread mode

            def start_server():
                uvicorn.run(
                    "app.factory:app",
                    host="0.0.0.0",
                    port=port,
                    reload=reload,
                    log_level="info",
                    log_config=get_uvicorn_log_config()
                )
            
            # Start server thread
            server_thread = threading.Thread(target=start_server, daemon=True)
            server_thread.start()

            # ── MCP Server (background thread) ──────────────────────────────────────
            mcp_port = args.mcp_port or 8100
            if not args.no_mcp:
                def start_mcp_server():
                    try:
                        from backend.mcp_server.server import mcp
                        import uvicorn
                        app = mcp.streamable_http_app()
                        uvicorn.run(app, host="127.0.0.1", port=mcp_port, log_level="info")
                    except ImportError as e:
                        unified_logger.warning(LogModule.SYSTEM, "MCP server not available (install 'mcp' package): {err}", err=e)
                    except Exception as e:
                        unified_logger.warning(LogModule.SYSTEM, "MCP server failed to start (port {port}?): {err}", port=mcp_port, err=e)

                mcp_thread = threading.Thread(target=start_mcp_server, daemon=True)
                mcp_thread.start()
                unified_logger.info(LogModule.SYSTEM, "MCP server starting on 127.0.0.1:{port}", port=mcp_port)
            else:
                unified_logger.info(LogModule.SYSTEM, "MCP server disabled by --no-mcp flag")
            # ─────────────────────────────────────────────────────────────────────────

            # Wait for server to actually start (poll port instead of fixed sleep)
            import time
            import socket

            def wait_for_server(port: int, timeout: float = 30.0, interval: float = 0.5) -> bool:
                """Wait for server to be ready by trying to connect to the port"""
                start_time = time.time()
                while time.time() - start_time < timeout:
                    try:
                        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                            s.settimeout(1)
                            s.connect(("127.0.0.1", port))
                            return True
                    except (socket.error, ConnectionRefusedError):
                        time.sleep(interval)
                return False

            unified_logger.info(LogModule.SYSTEM, "Waiting for server to be ready...")
            if wait_for_server(port, timeout=60.0):
                elapsed = time.time() - server_thread.start_time if hasattr(server_thread, 'start_time') else 0
                unified_logger.info(LogModule.SYSTEM, "Server is ready, opening browser...")
            else:
                unified_logger.warning(LogModule.SYSTEM, "Server may not be fully ready yet, opening browser anyway...")

            # Open browser
            import webbrowser
            url = f"http://localhost:{port}"
            unified_logger.info(LogModule.SYSTEM, "Opening browser at: {url}", url=url)
            webbrowser.open(url)
            
            # Keep main thread alive
            while server_thread.is_alive():
                time.sleep(1)
        except KeyboardInterrupt:
            unified_logger.info(LogModule.SYSTEM, "Server shutdown requested by user (Ctrl+C)")
            sys.exit(0)
    elif args.version:
        from __init__ import  __version__
        print(__version__)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
