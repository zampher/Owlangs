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
import time
import socket
from pathlib import Path
from typing import Optional, Dict, Any


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
            'ui.json.template',
            'secrets.json.template',
            'local.json.template',
            'logging.yaml',
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


class SingleFileLauncher:
    """Launcher for single-file executable mode."""
    
    def __init__(self):
        self.config_manager = ConfigManager()
        self.server_process: Optional[subprocess.Popen] = None
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
    
    def start_server(self) -> bool:
        """Start the backend server."""
        # Initialize configs
        config_dir = self.config_manager.init_user_configs()
        
        # Set environment variables
        os.environ['OWLANGS_CONFIG_PATH'] = str(config_dir)
        os.environ['OWLANGS_PORT'] = str(self.port)
        os.environ['OWLANGS_LOGS_PATH'] = str(self.config_manager.get_logs_dir())
        
        # Find server executable or module
        if hasattr(sys, '_MEIPASS'):
            # PyInstaller mode: run the extracted backend
            # The backend is already extracted to _MEIPASS
            python_exe = sys.executable
            cmd = [
                python_exe,
                '-m', 'backend.cli',
                '-i',  # Interactive mode
                '--port', str(self.port)
            ]
        else:
            # Development mode
            backend_dir = Path(__file__).parent
            cmd = [
                sys.executable,
                str(backend_dir / 'cli.py'),
                '-i',
                '--port', str(self.port)
            ]
        
        print(f"[Launcher] Starting server...", flush=True)
        print(f"[Launcher] Config: {config_dir}", flush=True)
        
        # Start server process
        try:
            self.server_process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                universal_newlines=True
            )
            return True
        except Exception as e:
            print(f"[Launcher] Failed to start server: {e}", flush=True)
            return False
    
    def open_browser(self) -> None:
        """Open browser to access the application."""
        url = f'http://localhost:{self.port}'
        print(f"[Launcher] Opening browser: {url}", flush=True)
        webbrowser.open(url)
    
    def run_interactive(self) -> int:
        """Run in interactive mode (with console output).
        
        Returns:
            Exit code.
        """
        print("=" * 60, flush=True)
        print("Owlangs - Translation and Collaboration Tool", flush=True)
        print("=" * 60, flush=True)
        print()
        
        # Check if first run
        if not self.config_manager.check_secrets_configured():
            print("[First Run] Please configure API keys for translation services.", flush=True)
            print("[First Run] Opening secrets.json for editing...", flush=True)
            
            self.config_manager.init_user_configs()
            self.config_manager.open_config_editor('secrets')
            
            input("\nPress Enter after configuring API keys...")
            
            # Check again
            if not self.config_manager.check_secrets_configured():
                print("[Warning] No API keys configured. Some features may not work.", flush=True)
                response = input("Continue anyway? (y/n): ")
                if response.lower() != 'y':
                    return 1
        
        # Check port
        if not self.check_port_available(self.port):
            print(f"[Error] Port {self.port} is already in use.", flush=True)
            print(f"[Error] Another instance of Owlangs may be running.", flush=True)
            response = input("Open browser to existing instance? (y/n): ")
            if response.lower() == 'y':
                self.open_browser()
                return 0
            return 1
        
        # Start server
        if not self.start_server():
            return 1
        
        # Wait for server
        if not self.wait_for_server():
            print("[Error] Server failed to start within timeout.", flush=True)
            self.stop_server()
            return 1
        
        # Open browser
        self.open_browser()
        
        print()
        print("-" * 60, flush=True)
        print("Server is running. Press Ctrl+C to stop.", flush=True)
        print("-" * 60, flush=True)
        print()
        
        # Stream server output
        try:
            if self.server_process and self.server_process.stdout:
                for line in iter(self.server_process.stdout.readline, ''):
                    print(line, end='', flush=True)
        except KeyboardInterrupt:
            print("\n[Launcher] Stopping server...", flush=True)
        finally:
            self.stop_server()
        
        return 0
    
    def run_silent(self) -> int:
        """Run in silent mode (no console output, for background service).
        
        Returns:
            Exit code.
        """
        # Initialize configs
        self.config_manager.init_user_configs()
        
        # Set environment
        os.environ['OWLANGS_CONFIG_PATH'] = str(self.config_manager.get_user_config_dir())
        os.environ['OWLANGS_PORT'] = str(self.port)
        
        # Start server silently
        if not self.start_server():
            return 1
        
        # Wait and open browser
        if self.wait_for_server():
            self.open_browser()
        
        # Wait for server to finish
        if self.server_process:
            try:
                self.server_process.wait()
            except KeyboardInterrupt:
                self.stop_server()
        
        return 0
    
    def stop_server(self) -> None:
        """Stop the server."""
        if self.server_process:
            try:
                self.server_process.terminate()
                self.server_process.wait(timeout=5)
            except:
                self.server_process.kill()
            finally:
                self.server_process = None


def main():
    """Main entry point for single-file launcher."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Owlangs Single-File Launcher')
    parser.add_argument('--silent', action='store_true', 
                        help='Run in silent mode (no console output)')
    parser.add_argument('--port', type=int, default=8800,
                        help='Port to run server on (default: 8800)')
    parser.add_argument('--init-config', action='store_true',
                        help='Initialize configuration files and exit')
    parser.add_argument('--edit-config', metavar='NAME', default=None,
                        help='Open configuration file in editor (e.g., secrets)')
    
    args = parser.parse_args()
    
    launcher = SingleFileLauncher()
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
        return launcher.run_silent()
    else:
        return launcher.run_interactive()


if __name__ == '__main__':
    sys.exit(main())
