#!/usr/bin/env python3
"""
直接运行应用的脚本
"""

import sys
import os
from pathlib import Path

# 添加当前目录到Python路径
current_dir = Path(__file__).parent
sys.path.insert(0, str(current_dir))
sys.path.insert(0, str(current_dir.parent))  # Add project root to Python path

# 设置环境变量
os.environ['PYTHONPATH'] = str(current_dir)


def _check_port(port: int) -> bool:
    """Check if a port is already in use"""
    import socket
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.bind(("0.0.0.0", port))
            return False  # Port is available
        except OSError:
            return True  # Port is in use


def _show_port_occupied_dialog() -> bool:
    """Show dialog to user when port is occupied
    Returns True if user wants to continue (e.g., after terminating process)
    """
    import sys
    import subprocess
    
    message = "Port 8800 is already in use, possibly by a previous Owlangs process.\n\nTo resolve: Open Terminal and run 'lsof -i :8800' to find the process, then 'kill -9 <PID>' to terminate it.\n\nContinue startup anyway?"
    
    if sys.platform == 'darwin':  # macOS
        try:
            script = f'''display dialog "{message}" buttons {{"Cancel", "Continue"}} default button "Continue" with title "Port In Use"'''
            result = subprocess.run(
                ['osascript', '-e', script],
                capture_output=True,
                text=True
            )
            return 'Continue' in result.stdout
        except Exception:
            # Fallback to console
            return input("Port 8800 is in use. Continue anyway? (y/n): ").lower() == 'y'
    elif sys.platform == 'win32':  # Windows
        try:
            import ctypes
            result = ctypes.windll.user32.MessageBoxW(
                0,
                message,
                "Port In Use",
                0x40 | 0x1  # MB_YESNO | MB_ICONQUESTION
            )
            return result == 6  # IDYES
        except Exception:
            return input("Port 8800 is in use. Continue anyway? (y/n): ").lower() == 'y'
    else:  # Linux
        try:
            result = subprocess.run(
                ['zenity', '--question', '--title=Port In Use', '--text=' + message],
                capture_output=True
            )
            return result.returncode == 0
        except Exception:
            try:
                result = subprocess.run(
                    ['kdialog', '--yesno', message, '--title', 'Port In Use'],
                    capture_output=True
                )
                return result.returncode == 0
            except Exception:
                return input("Port 8800 is in use. Continue anyway? (y/n): ").lower() == 'y'


def _run_server() -> None:
    """Start uvicorn server. Only called when this file is run as main process (not in multiprocessing child)."""
    import multiprocessing
    if multiprocessing.current_process().name != "MainProcess":
        # On macOS (spawn), multiprocessing re-executes __main__ in the child; do not start server again
        return
    try:
        import uvicorn
        from app.factory import app  # Use the pre-created app instance instead of calling create_app() again
        from logger.logger import get_uvicorn_log_config

        # Check if port 8800 is already in use
        if _check_port(8800):
            print("⚠️  端口 8800 已被占用")
            if not _show_port_occupied_dialog():
                print("🛑 用户取消启动")
                sys.exit(0)
            print("🔄 继续启动...")

        print("🚀 Starting Owlangs backend server...")
        print("📍 Backend will be available at: http://localhost:8800")
        print("📚 API documentation at: http://localhost:8800/docs")
        print("🛑 Press Ctrl+C to stop the server")
        print("-" * 50)

        try:
            uvicorn.run(
                app,
                host="0.0.0.0",
                port=8800,
                reload=False,
                log_level="info",
                log_config=get_uvicorn_log_config()
            )
        except KeyboardInterrupt:
            print("\n🛑 Server shutdown requested by user (Ctrl+C)")
            sys.exit(0)
    except ImportError as e:
        print(f"❌ Import error: {e}")
        print("💡 Make sure you're in the backend directory and all dependencies are installed")
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    _run_server()


