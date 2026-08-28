# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

"""
Configuration manager for single-file executable mode.
Handles initialization, migration, and persistence of user configurations.
"""

import os
import sys
import json
import shutil
import webbrowser
import subprocess
import threading
import time
import socket
from pathlib import Path
from typing import Optional, Dict, Any

from backend import __version__


class ConfigManager:
    """Manages application configuration for single-file executable mode."""
    
    def __init__(self):
        self._user_config_dir: Optional[Path] = None
        self._builtin_config_dir: Optional[Path] = None
        
    @staticmethod
    def get_builtin_path(relative_path: str) -> Path:
        """Get path to built-in resources (works in both dev and PyInstaller modes)."""
        if hasattr(sys, '_MEIPASS'):
            # PyInstaller single-file mode
            return Path(sys._MEIPASS) / relative_path
        else:
            # Development mode
            backend_dir = Path(__file__).parent
            return backend_dir.parent / relative_path
    
    @staticmethod
    def get_user_config_dir() -> Path:
        """Get user configuration directory (persistent storage).
        
        Uses C:\\ProgramData\\Owlangs for Windows to ensure all users can access.
        Falls back to user's home directory.
        """
        # Try ProgramData directory first (all users can access)
        program_data = os.environ.get('PROGRAMDATA')
        if program_data:
            config_dir = Path(program_data) / 'Owlangs' / 'configs'
        else:
            # Fallback to user's home directory
            config_dir = Path.home() / '.owlangs' / 'configs'
        
        config_dir.mkdir(parents=True, exist_ok=True)
        return config_dir
    
    @staticmethod
    def get_logs_dir() -> Path:
        """Get logs directory."""
        program_data = os.environ.get('PROGRAMDATA')
        if program_data:
            logs_dir = Path(program_data) / 'Owlangs' / 'logs'
        else:
            logs_dir = Path.home() / '.owlangs' / 'logs'
        logs_dir.mkdir(parents=True, exist_ok=True)
        return logs_dir

    @staticmethod
    def get_task_cache_dir(task_id: str) -> Path:
        """Persistent per-task cache outside OS TEMP (survives Temp cleanup).

        Used to keep a durable copy of the original PDF for Typst overlay export
        when ``%TEMP%/owlangs_*`` is deleted mid-session by Windows/antivirus.
        """
        safe_id = "".join(
            c for c in str(task_id or "") if c.isalnum() or c in "-_"
        )[:64] or "unknown"
        program_data = os.environ.get("PROGRAMDATA")
        if program_data:
            base = Path(program_data) / "Owlangs" / "task_cache"
        else:
            base = Path.home() / ".owlangs" / "task_cache"
        cache_dir = base / safe_id
        cache_dir.mkdir(parents=True, exist_ok=True)
        return cache_dir
    
    @staticmethod
    def get_models_dir() -> Path:
        """Get models directory for spaCy models."""
        program_data = os.environ.get('PROGRAMDATA')
        if program_data:
            models_dir = Path(program_data) / 'Owlangs' / 'models' / 'spacy'
        else:
            models_dir = Path.home() / '.owlangs' / 'models' / 'spacy'
        models_dir.mkdir(parents=True, exist_ok=True)
        return models_dir
    
    def init_user_configs(self, force_reset: bool = False) -> Path:
        """Initialize user configuration directory from built-in templates.
        
        Args:
            force_reset: If True, overwrite existing user configs with templates.
            
        Returns:
            Path to user configuration directory.
        """
        builtin_dir = self.get_builtin_path('configs')
        user_dir = self.get_user_config_dir()
        
        # Config files to initialize
        config_files = [
            'system.json',
            'system.json.template',
            'platforms.json.template',
            'secrets.json.template',
            'local.json.template',
            'logging.yaml',
            'translation_config.json.template',
            'static.json.template',
            'app_config.json.template',
            'local_users.json.template',
            'launcher_config.json.template',
        ]
        
        initialized_files = []
        
        for config_file in config_files:
            builtin_file = builtin_dir / config_file
            user_file = user_dir / config_file
            
            # Remove .template suffix for runtime files
            if user_file.name.endswith('.template'):
                runtime_name = user_file.stem
                user_file = user_dir / runtime_name
            
            # Copy if: doesn't exist, or force_reset, or it's a template
            if force_reset or not user_file.exists():
                # Try multiple sources
                sources_to_try = [
                    builtin_dir / config_file,
                    builtin_dir / config_file.replace('.template', ''),
                    Path(__file__).parent.parent / 'configs' / config_file,
                ]
                
                for source in sources_to_try:
                    if source.exists():
                        shutil.copy2(source, user_file)
                        initialized_files.append(user_file.name)
                        break
        
        # Create secrets.json from template if it doesn't exist
        secrets_file = user_dir / 'secrets.json'
        if not secrets_file.exists():
            template_file = builtin_dir / 'secrets.json.template'
            if template_file.exists():
                shutil.copy2(template_file, secrets_file)
                initialized_files.append('secrets.json')
        
        if initialized_files:
            print(f"[Config] Initialized: {', '.join(initialized_files)}")
        
        self._user_config_dir = user_dir
        return user_dir
    
    def load_config(self, config_name: str) -> Dict[str, Any]:
        """Load configuration with fallback: user config > builtin defaults.
        
        Args:
            config_name: Name of config file (e.g., 'system', 'platforms')
            
        Returns:
            Merged configuration dictionary.
        """
        # Start with builtin defaults
        builtin_path = self.get_builtin_path(f'configs/{config_name}.json.template')
        if not builtin_path.exists():
            builtin_path = self.get_builtin_path(f'configs/{config_name}.json')
        
        config = {}
        if builtin_path.exists():
            with open(builtin_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
        
        # Merge user config (overrides builtin)
        user_path = self.get_user_config_dir() / f'{config_name}.json'
        if user_path.exists():
            with open(user_path, 'r', encoding='utf-8') as f:
                user_config = json.load(f)
                config.update(user_config)
        
        return config
    
    def save_config(self, config_name: str, config: Dict[str, Any]) -> None:
        """Save configuration to user directory.
        
        Args:
            config_name: Name of config file (without extension)
            config: Configuration dictionary to save
        """
        user_path = self.get_user_config_dir() / f'{config_name}.json'
        with open(user_path, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
    
    def check_secrets_configured(self) -> bool:
        """Check if API keys are configured in secrets.json.
        
        Returns:
            True if at least one API key is set.
        """
        secrets_file = self.get_user_config_dir() / 'secrets.json'
        if not secrets_file.exists():
            return False
        
        try:
            with open(secrets_file, 'r', encoding='utf-8') as f:
                secrets = json.load(f)
            
            # Check for any API key
            api_keys = [
                secrets.get('openai_api_key'),
                secrets.get('anthropic_api_key'),
                secrets.get('azure_api_key'),
                secrets.get('gemini_api_key'),
            ]
            return any(key and key.strip() for key in api_keys)
        except Exception:
            return False
    
    def open_config_editor(self, config_name: str = 'secrets') -> None:
        """Open configuration file in default editor.
        
        Args:
            config_name: Name of config file to edit (without extension)
        """
        config_file = self.get_user_config_dir() / f'{config_name}.json'
        
        # Ensure file exists
        if not config_file.exists():
            self.init_user_configs()
        
        # Open with default application
        if sys.platform == 'win32':
            os.startfile(config_file)
        else:
            # For non-Windows, try xdg-open or open
            import platform
            if platform.system() == 'Darwin':
                subprocess.run(['open', str(config_file)])
            else:
                subprocess.run(['xdg-open', str(config_file)])


def _setup_frozen_env(skip_app=False):
    """Set up frozen environment for PyInstaller single-file mode.

    Args:
        skip_app: If True, skip importing backend.app (used in CLI mode
                  to avoid the heavy FastAPI startup cost).
    """
    if not hasattr(sys, 'frozen'):
        return

    # Set up utils alias: code imports "from utils.xxx", bundled as backend.utils
    import backend.utils
    sys.modules['utils'] = backend.utils

    # Pre-register key submodules so lazy imports in frozen build resolve
    _submodules = [
        'backend.utils.resource_utils',
        'backend.utils.redis_manager',
        'backend.utils.utils',
        'backend.utils.language_utils',
        'backend.utils.path_utils',
        'backend.utils.font_utils',
        'backend.utils.json_utils',
        'backend.utils.translation_segments',
        'backend.utils.markdown_splitter',
        'backend.utils.markdown_utils',
        'backend.utils.http_content_disposition',
        'backend.utils.output_suffix',
        'backend.utils.batch_download_zip',
        'backend.utils.equation_tag_merge',
        'backend.utils.pdf_export_failure_locator',
        'backend.utils.format_convert_utils',
    ]
    for mod_name in _submodules:
        try:
            __import__(mod_name)
            short = mod_name.replace('backend.utils.', 'utils.', 1)
            if mod_name in sys.modules:
                sys.modules.setdefault(short, sys.modules[mod_name])
        except Exception:
            pass

    if skip_app:
        return

    # Pre-import backend.app so sys.modules["app"] is set for uvicorn's import_from_string
    try:
        import backend.app  # noqa: F401
    except Exception:
        pass


class PortableLauncher:
    """Launcher for portable executable mode."""
    
    def __init__(self):
        self.config_manager = ConfigManager()
        self.server_process: Optional[subprocess.Popen] = None
        self.server_thread: Optional[threading.Thread] = None
        self._server_ready = threading.Event()
        self.port = 8800
        
    def check_port_available(self, port: int) -> bool:
        """Check if port is available."""
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(('0.0.0.0', port))
                return True
            except OSError:
                return False
    
    def wait_for_server(self, timeout: int = 60) -> bool:
        """Wait for server to be ready."""
        print(f"[Launcher] Waiting for server on port {self.port}...", flush=True)
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    s.settimeout(1)
                    result = s.connect_ex(('127.0.0.1', self.port))
                    if result == 0:
                        # Port is open, but wait for health check
                        import urllib.request
                        try:
                            urllib.request.urlopen(
                                f'http://127.0.0.1:{self.port}/api/health',
                                timeout=2
                            )
                            print(f"[Launcher] Server is ready!", flush=True)
                            return True
                        except:
                            pass
            except Exception:
                pass
            time.sleep(0.5)
        
        return False
    
    def _setup_frozen_env(self):
        """Delegate to module-level frozen environment setup."""
        _setup_frozen_env(skip_app=False)

    def start_server(self) -> bool:
        """Start the backend server in-process using uvicorn in a daemon thread."""
        # Initialize configs
        config_dir = self.config_manager.init_user_configs()
        # OWLANGS_CONFIG_PATH should point to the Owlangs data root, NOT the configs subdir
        # because get_configs_dir() in path_utils.py appends /configs/ automatically
        os.environ['OWLANGS_CONFIG_PATH'] = str(config_dir.parent)
        os.environ['OWLANGS_PORT'] = str(self.port)
        os.environ['OWLANGS_LOGS_PATH'] = str(self.config_manager.get_logs_dir())

        # Set up frozen environment
        self._setup_frozen_env()

        print(f"[Launcher] Starting server...", flush=True)
        print(f"[Launcher] Config: {config_dir}", flush=True)

        # Start uvicorn in a daemon thread (in-process)
        def _run_uvicorn():
            import uvicorn
            try:
                uvicorn.run(
                    "app.factory:app",
                    host="0.0.0.0",
                    port=self.port,
                    log_level="info",
                )
            except Exception as e:
                print(f"[Launcher] Server error: {e}", flush=True)
            finally:
                self._server_ready.set()  # Unblock wait_for_server on failure

        self.server_thread = threading.Thread(target=_run_uvicorn, daemon=True)
        self.server_thread.start()
        return True
    
    def open_browser(self) -> None:
        """Open browser to access the application."""
        url = f'http://localhost:{self.port}'
        print(f"[Launcher] Opening browser: {url}", flush=True)
        webbrowser.open(url)
    
    def run_interactive(self, no_browser: bool = False) -> int:
        """Run in interactive mode (with console output).

        Args:
            no_browser: If True, skip opening the browser.

        Returns:
            Exit code.
        """
        print("=" * 60, flush=True)
        print("Owlangs - Translation and Collaboration Tool", flush=True)
        print("=" * 60, flush=True)
        print()

        # Initialize configs from templates silently
        self.config_manager.init_user_configs()

        # Check port
        if not self.check_port_available(self.port):
            print(f"[Error] Port {self.port} is already in use.", flush=True)
            print(f"[Error] Another instance of Owlangs may be running.", flush=True)
            response = input("Open browser to existing instance? (y/n): ")
            if response.lower() == 'y':
                self.open_browser()
                return 0
            return 1

        # Start server (in-process uvicorn in daemon thread)
        if not self.start_server():
            return 1

        # Wait for server
        if not self.wait_for_server():
            print("[Error] Server failed to start within timeout.", flush=True)
            self.stop_server()
            return 1

        # Open browser (unless --no-browser)
        if not no_browser:
            self.open_browser()

        print()
        print("-" * 60, flush=True)
        print("Server is running. Press Ctrl+C to stop.", flush=True)
        print("-" * 60, flush=True)
        print()

        # Keep main thread alive
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\n[Launcher] Stopping server...", flush=True)
        finally:
            self.stop_server()

        return 0

    def run_silent(self, no_browser: bool = False) -> int:
        """Run in silent mode (no console output, for background service).

        Args:
            no_browser: If True, skip opening the browser.

        Returns:
            Exit code.
        """
        # Initialize configs
        self.config_manager.init_user_configs()

        # Set environment (point to parent dir, not configs subdir)
        os.environ['OWLANGS_CONFIG_PATH'] = str(self.config_manager.get_user_config_dir().parent)
        os.environ['OWLANGS_PORT'] = str(self.port)

        # Start server in-process
        if not self.start_server():
            return 1

        # Wait and open browser (unless --no-browser)
        if self.wait_for_server() and not no_browser:
            self.open_browser()

        # Wait for server to finish (daemon thread keeps running)
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            self.stop_server()

        return 0
    
    def stop_server(self) -> None:
        """Stop the server."""
        # In-process uvicorn runs in a daemon thread; it will be terminated
        # automatically when the main thread exits.
        if self.server_process:
            try:
                self.server_process.terminate()
                self.server_process.wait(timeout=5)
            except:
                self.server_process.kill()
            finally:
                self.server_process = None
        self.server_thread = None


def main():
    """Main entry point for single-file launcher.

    Supports both CLI mode (translate/convert/batch/etc.) and launcher mode
    (start server + open browser). Double-clicking with no arguments runs
    launcher mode; passing a CLI subcommand runs CLI mode.
    """
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
        # Skip Redis startup in CLI mode to improve cold-start speed
        # Must be set BEFORE _setup_frozen_env() imports backend.app
        os.environ["REDIS_ENABLED"] = "false"
        _setup_frozen_env(skip_app=True)
        # Initialize user configs so CLI can find secrets.json and other configs
        config_mgr = ConfigManager()
        config_dir = config_mgr.init_user_configs()
        os.environ['OWLANGS_CONFIG_PATH'] = str(config_dir.parent)
        from backend.owlangs_cli import main as cli_main
        sys.exit(cli_main())

    # ── Launcher mode ──
    import argparse

    parser = argparse.ArgumentParser(description='Owlangs Single-File Launcher')
    parser.add_argument('-i', '--interactive', action='store_true',
                        help='Start in interactive mode (launcher default)')
    parser.add_argument('--version', action='version',
                        version=f'%(prog)s {__version__}',
                        help='Show version information and exit')
    parser.add_argument('--silent', action='store_true',
                        help='Run in silent mode (no console output)')
    parser.add_argument('--port', type=int, default=8800,
                        help='Port to run server on (default: 8800)')
    parser.add_argument('--init-config', action='store_true',
                        help='Initialize configuration files and exit')
    parser.add_argument('--edit-config', metavar='NAME', default=None,
                        help='Open configuration file in editor (e.g., secrets)')
    parser.add_argument('--no-browser', action='store_true',
                        help='Do not open the web browser on startup')

    args = parser.parse_args()
    
    launcher = PortableLauncher()
    launcher.port = args.port
    
    # Handle special commands
    if args.init_config:
        config_dir = launcher.config_manager.init_user_configs(force_reset=True)
        print(f"Configuration initialized: {config_dir}")
        return 0
    
    if args.edit_config:
        launcher.config_manager.open_config_editor(args.edit_config)
        return 0
    
    # Run launcher
    if args.silent:
        return launcher.run_silent(no_browser=args.no_browser)
    else:
        return launcher.run_interactive(no_browser=args.no_browser)


if __name__ == '__main__':
    sys.exit(main())
