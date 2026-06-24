#!/usr/bin/env python3
"""
Owlangs macOS Menu Bar Application
Provides menu bar controls and log window for managing the backend service.
"""

import os
import sys
import subprocess
import threading
import time
import traceback
import queue
from pathlib import Path

# Ensure log directory exists
LOG_DIR = Path.home() / "Library" / "Logs" / "Owlangs"
LOG_DIR.mkdir(parents=True, exist_ok=True)
LOG_FILE = LOG_DIR / "menubar.log"

# Queue for log messages from backend
log_queue = queue.Queue()


def log_message(msg):
    """Write log message to file."""
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    try:
        with open(LOG_FILE, "a") as f:
            f.write(f"[{timestamp}] {msg}\n")
    except:
        pass


# Log startup
log_message("=" * 50)
log_message("Owlangs starting...")
log_message(f"Python: {sys.executable}")
log_message(f"Frozen: {getattr(sys, 'frozen', False)}")
log_message(f"CWD: {os.getcwd()}")

# Import Cocoa frameworks
try:
    import objc
    from Foundation import NSObject, NSUserNotification, NSUserNotificationCenter, NSThread
    from Foundation import NSMakeRect, NSMakeRange, NSLog
    from AppKit import (
        NSApplication, NSStatusBar, NSStatusItem, NSMenu, NSMenuItem,
        NSImage, NSVariableStatusItemLength, NSApplicationActivationPolicyRegular,
        NSWindow, NSWindowStyleMaskTitled, NSWindowStyleMaskClosable,
        NSWindowStyleMaskMiniaturizable, NSBackingStoreBuffered,
        NSTextView, NSScrollView, NSMakeSize, NSTextField, NSFont,
        NSColor, NSBezelStyleRounded, NSButton, NSWindowStyleMaskResizable,
        NSView, NSLayoutConstraint, NSLayoutAttributeWidth, NSLayoutAttributeHeight,
        NSLayoutAttributeTop, NSLayoutAttributeLeading, NSLayoutAttributeBottom,
        NSLayoutAttributeTrailing, NSLayoutRelationEqual, NSLayoutFormatAlignAllLeading,
        NSAlert
    )
    from PyObjCTools import AppHelper
    log_message("Cocoa frameworks imported successfully")
except Exception as e:
    log_message(f"ERROR importing Cocoa: {e}")
    log_message(traceback.format_exc())
    sys.exit(1)

# Configuration
PORT = 8800
LOCK_FILE = Path.home() / "Library" / "Application Support" / "Owlangs" / "owlangs.lock"
PREFERENCES_FILE = Path.home() / "Library" / "Application Support" / "Owlangs" / "preferences.json"


def get_app_version():
    """Get app version from backend/__init__.py (single source of truth)."""
    try:
        # Try to import backend module directly
        if getattr(sys, 'frozen', False):
            # In bundled app, try to read version from bundled backend
            bundle_dir = Path(sys._MEIPASS)
            backend_init = bundle_dir / "backend" / "__init__.py"
        else:
            # In development, read from project root
            backend_init = Path(__file__).resolve().parent.parent.parent / "backend" / "__init__.py"
        
        if backend_init.exists():
            content = backend_init.read_text()
            import re
            match = re.search(r'__version__\s*=\s*["\']([^"\']+)["\']', content)
            if match:
                return match.group(1)
    except Exception as e:
        log_message(f"Warning: Could not read version: {e}")
    
    return "1.2.0.0"  # Fallback version


APP_VERSION = get_app_version()


class LogWindowController(NSObject):
    """Controller for the log window."""
    
    def init(self):
        self = objc.super(LogWindowController, self).init()
        if self is None:
            return None
        self.window = None
        self.text_view = None
        self.scroll_view = None
        self.log_buffer = []
        self.max_lines = 1000
        self.buffer_lock = threading.Lock()
        return self
    
    def showWindow(self):
        """Show the log window. Create if needed."""
        if self.window is not None:
            self.window.makeKeyAndOrderFront_(None)
            self.window.orderFrontRegardless()
            return
        
        self.createWindow()
    
    def createWindow(self):
        """Create the log window."""
        # Create window
        frame = NSMakeRect(100, 100, 900, 600)
        style_mask = (
            NSWindowStyleMaskTitled | 
            NSWindowStyleMaskClosable | 
            NSWindowStyleMaskMiniaturizable |
            NSWindowStyleMaskResizable
        )
        
        self.window = NSWindow.alloc().initWithContentRect_styleMask_backing_defer_(
            frame, style_mask, NSBackingStoreBuffered, False
        )
        self.window.setTitle_("Owlangs Logs")
        self.window.setDelegate_(self)
        self.window.setReleasedWhenClosed_(False)
        
        # Create scroll view
        self.scroll_view = NSScrollView.alloc().initWithFrame_(
            self.window.contentView().bounds()
        )
        self.scroll_view.setAutoresizingMask_(18)  # Width and height sizers
        self.scroll_view.setHasVerticalScroller_(True)
        self.scroll_view.setHasHorizontalScroller_(True)
        self.scroll_view.setAutohidesScrollers_(False)
        
        # Create text view with proper frame
        content_size = self.scroll_view.contentSize()
        self.text_view = NSTextView.alloc().initWithFrame_(
            NSMakeRect(0, 0, content_size.width, content_size.height)
        )
        self.text_view.setAutoresizingMask_(18)
        self.text_view.setEditable_(False)
        self.text_view.setSelectable_(True)
        self.text_view.setFont_(NSFont.fontWithName_size_("Menlo", 12))
        self.text_view.setBackgroundColor_(NSColor.blackColor())
        self.text_view.setTextColor_(NSColor.greenColor())
        self.text_view.setInsertionPointColor_(NSColor.greenColor())
        
        self.scroll_view.setDocumentView_(self.text_view)
        self.window.contentView().addSubview_(self.scroll_view)
        
        # Add initial message
        self.addLogText_("Owlangs Server Logs\n")
        self.addLogText_("=" * 60 + "\n")
        self.addLogText_("Waiting for server to start...\n\n")
        
        # Show window
        self.window.makeKeyAndOrderFront_(None)
        self.window.orderFrontRegardless()
        
        # Start queue checker
        self.performSelectorInBackground_withObject_("checkLogQueue", None)
        
        # Add a test message to verify logging works
        log_queue.put("[Log system initialized]\n")
        
        log_message("Log window created")
    
    def addLogText_(self, text):
        """Add text to the text view directly (PyObjC method with underscore for argument)."""
        if self.text_view is None:
            return
        
        # Get the text storage and append
        storage = self.text_view.textStorage()
        end_range = NSMakeRange(storage.length(), 0)
        
        # Insert at end
        self.text_view.replaceCharactersInRange_withString_(end_range, text)
        
        # Scroll to bottom
        self.text_view.scrollRangeToVisible_(NSMakeRange(storage.length(), 0))
    
    def appendLog_(self, text):
        """Append text to the log view (called from background thread)."""
        with self.buffer_lock:
            self.log_buffer.append(text)
            if len(self.log_buffer) > self.max_lines:
                self.log_buffer = self.log_buffer[-self.max_lines:]
        
        # Schedule update on main thread
        self.performSelectorOnMainThread_withObject_waitUntilDone_(
            "flushLogBuffer", None, False
        )
    
    def flushLogBuffer(self):
        """Flush buffered logs to text view (always called on main thread)."""
        if self.text_view is None:
            return
        
        with self.buffer_lock:
            buffer_copy = self.log_buffer[:]
            self.log_buffer = []
        
        if buffer_copy:
            text = "".join(buffer_copy)
            self.addLogText_(text)
    
    def checkLogQueue(self):
        """Background thread to check log queue."""
        log_message("Log queue checker started")
        while True:
            try:
                # Check if window still exists
                if self.window is None:
                    break
                
                # Get message from queue
                msg = log_queue.get(timeout=0.5)
                
                # Add to buffer and flush
                self.appendLog_(msg)
                
            except queue.Empty:
                continue
            except Exception as e:
                log_message(f"Error in checkLogQueue: {e}")
                time.sleep(0.5)
        
        log_message("Log queue checker stopped")
    
    def windowWillClose_(self, notification):
        """Called when window is closed. Hide the window."""
        if self.window:
            self.window.orderOut_(None)
        log_message("Log window hidden")


class InstallWindowController(NSObject):
    """Window showing real-time dependency installation progress with cancel support."""
    
    def init(self):
        self = objc.super(InstallWindowController, self).init()
        if self is None:
            return None
        self.window = None
        self.text_view = None
        self.status_label = None
        self.cancel_button = None
        self.scroll_view = None
        self.process = None
        self.cancelled = False
        self.on_complete = None
        return self
    
    def showWindow(self):
        if self.window is not None:
            self.window.makeKeyAndOrderFront_(None)
            self.window.orderFrontRegardless()
            return
        self._createWindow()
    
    def _createWindow(self):
        frame = NSMakeRect(100, 100, 720, 480)
        style = (
            NSWindowStyleMaskTitled |
            NSWindowStyleMaskClosable |
            NSWindowStyleMaskMiniaturizable
        )
        self.window = NSWindow.alloc().initWithContentRect_styleMask_backing_defer_(
            frame, style, NSBackingStoreBuffered, False
        )
        self.window.setTitle_("Installing Dependencies")
        self.window.setDelegate_(self)
        self.window.setReleasedWhenClosed_(False)
        
        # Status label
        self.status_label = NSTextField.alloc().initWithFrame_(NSMakeRect(20, 430, 680, 24))
        self.status_label.setStringValue_("Preparing installation...")
        self.status_label.setBezeled_(False)
        self.status_label.setDrawsBackground_(False)
        self.status_label.setEditable_(False)
        self.status_label.setSelectable_(False)
        self.status_label.setFont_(NSFont.boldSystemFontOfSize_(13))
        self.window.contentView().addSubview_(self.status_label)
        
        # Scroll view for logs
        self.scroll_view = NSScrollView.alloc().initWithFrame_(NSMakeRect(20, 60, 680, 360))
        self.scroll_view.setHasVerticalScroller_(True)
        self.scroll_view.setHasHorizontalScroller_(True)
        self.scroll_view.setAutohidesScrollers_(False)
        
        content_size = self.scroll_view.contentSize()
        self.text_view = NSTextView.alloc().initWithFrame_(
            NSMakeRect(0, 0, content_size.width, content_size.height)
        )
        self.text_view.setEditable_(False)
        self.text_view.setSelectable_(True)
        self.text_view.setFont_(NSFont.fontWithName_size_("Menlo", 11))
        self.text_view.setBackgroundColor_(NSColor.blackColor())
        self.text_view.setTextColor_(NSColor.greenColor())
        self.text_view.setInsertionPointColor_(NSColor.greenColor())
        self.scroll_view.setDocumentView_(self.text_view)
        self.window.contentView().addSubview_(self.scroll_view)
        
        # Cancel button
        self.cancel_button = NSButton.alloc().initWithFrame_(NSMakeRect(20, 16, 100, 28))
        self.cancel_button.setTitle_("Cancel")
        self.cancel_button.setBezelStyle_(NSBezelStyleRounded)
        self.cancel_button.setTarget_(self)
        self.cancel_button.setAction_("cancelInstall:")
        self.window.contentView().addSubview_(self.cancel_button)
        
        self.window.makeKeyAndOrderFront_(None)
        self.window.orderFrontRegardless()
        
        # Set initial text directly (avoids threading issues during init)
        init_text = (
            "Owlangs Dependency Installer\n"
            "=" * 50 + "\n"
            "Real-time installation progress will appear below.\n"
            "Click Cancel at any time to abort.\n\n"
        )
        self.text_view.setString_(init_text)
    
    def appendText_(self, text):
        """Append text to the log view (thread-safe, schedules on main thread)."""
        self.performSelectorOnMainThread_withObject_waitUntilDone_(
            "appendTextOnMainThread:", text, False
        )
    
    def appendTextOnMainThread_(self, text):
        """Actually append text (always runs on main thread)."""
        if self.text_view is None:
            return
        self.text_view.textStorage().mutableString().appendString_(text)
        storage_len = self.text_view.textStorage().length()
        self.text_view.scrollRangeToVisible_(NSMakeRange(storage_len, 0))
    
    def setStatus_(self, status):
        if self.status_label is not None:
            self.status_label.setStringValue_(status)
    
    def cancelInstall_(self, sender):
        if self.cancelled:
            return
        self.cancelled = True
        self.appendText_("\n[INFO] Cancelling installation...\n")
        if self.process and self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=2)
        self.setStatus_("Installation cancelled")
        self.cancel_button.setEnabled_(False)
        log_message("User cancelled dependency installation")
    
    def windowWillClose_(self, notification):
        if self.window:
            self.window.orderOut_(None)
        if self.process and self.process.poll() is None:
            self.cancelInstall_(None)
    
    @objc.python_method
    def runInstall(self, script_path, completion_callback):
        self.on_complete = completion_callback
        self.cancelled = False
        if self.cancel_button is not None:
            self.cancel_button.setEnabled_(True)
        
        def _install_thread():
            try:
                output_buffer = []
                
                # First attempt without admin
                self.performSelectorOnMainThread_withObject_waitUntilDone_(
                    "setStatus:", "Installing... (without admin privileges)", False
                )
                self.appendText_("[INFO] Starting installation (no admin)...\n\n")
                
                self.process = subprocess.Popen(
                    ["/bin/bash", "-l", str(script_path), "install"],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1
                )
                
                for line in self.process.stdout:
                    if self.cancelled:
                        break
                    output_buffer.append(line)
                    self.appendText_(line)
                
                self.process.stdout.close()
                rc = self.process.wait()
                
                if self.cancelled:
                    self.appendText_("\n[CANCELLED] Installation was cancelled by user.\n")
                    if self.on_complete:
                        self.on_complete(False, "cancelled")
                    return
                
                if rc == 0:
                    self.appendText_("\n[SUCCESS] All dependencies installed successfully!\n")
                    self.performSelectorOnMainThread_withObject_waitUntilDone_(
                        "setStatus:", "Installation complete ✓", False
                    )
                    if self.on_complete:
                        self.on_complete(True, None)
                    return
                
                # Analyze failure
                all_output = "".join(output_buffer).lower()
                is_tty_issue = (
                    "sudo: a terminal is required" in all_output or
                    "password" in all_output or
                    "non-interactive" in all_output
                )
                is_homebrew_root = "running homebrew as root" in all_output
                
                if is_tty_issue:
                    self.appendText_(
                        "\n[INFO] Homebrew cask requires a password but GUI has no TTY.\n"
                        "[INFO] Opening Terminal.app to continue installation...\n"
                    )
                    self.performSelectorOnMainThread_withObject_waitUntilDone_(
                        "setStatus:", "Installing in Terminal... please enter your password", False
                    )
                    
                    # Open Terminal.app to run the install script
                    import tempfile
                    escaped_path = str(script_path).replace('\\', '\\\\').replace('"', '\\"')
                    cmd_path = Path(tempfile.gettempdir()) / "owlangs_install.command"
                    cmd_content = (
                        f'#!/bin/bash\n'
                        f'cd "{script_path.parent}"\n'
                        f'/bin/bash -l "{escaped_path}" install\n'
                        f'rm -f "{cmd_path}"\n'
                    )
                    try:
                        cmd_path.write_text(cmd_content)
                        cmd_path.chmod(0o755)
                        subprocess.Popen(["open", str(cmd_path)])
                        self.appendText_("[INFO] Terminal opened. Please enter your password when prompted.\n")
                        self.appendText_("[INFO] This window will auto-detect when installation completes.\n")
                    except Exception as e:
                        self.appendText_(f"[ERROR] Could not open Terminal: {e}\n")
                        self.appendText_(
                            "[INFO] Please open Terminal and run:\n"
                            f"  /bin/bash -l {script_path} install\n"
                        )
                        if self.on_complete:
                            self.on_complete(False, "tty_required")
                        return
                    
                    # Poll for completion by checking if xelatex becomes available
                    self.appendText_("[INFO] Polling for XeLaTeX installation (this may take several minutes)...\n")
                    for _ in range(600):  # up to 10 minutes
                        if self.cancelled:
                            break
                        time.sleep(1)
                        # Check if all deps are now satisfied
                        try:
                            result = subprocess.run(
                                ["/bin/bash", "-l", "-c", "command -v xelatex"],
                                capture_output=True, text=True, timeout=5
                            )
                            if result.returncode == 0 and result.stdout.strip():
                                self.appendText_("\n[SUCCESS] XeLaTeX detected! Installation complete.\n")
                                self.performSelectorOnMainThread_withObject_waitUntilDone_(
                                    "setStatus:", "Installation complete ✓", False
                                )
                                if self.on_complete:
                                    self.on_complete(True, None)
                                return
                        except Exception:
                            pass
                    
                    if self.cancelled:
                        self.appendText_("\n[CANCELLED] Installation was cancelled by user.\n")
                        if self.on_complete:
                            self.on_complete(False, "cancelled")
                        return
                    
                    self.appendText_(
                        "\n[INFO] Polling timed out. The Terminal window may still be installing.\n"
                        "[INFO] You can close this window and check dependencies again later.\n"
                    )
                    self.performSelectorOnMainThread_withObject_waitUntilDone_(
                        "setStatus:", "Install running in Terminal (check later)", False
                    )
                    if self.on_complete:
                        self.on_complete(False, "timeout")
                    return
                
                # Try with osascript admin (for non-cask packages that genuinely need root)
                self.appendText_("\n[INFO] Retrying with administrator privileges...\n")
                self.performSelectorOnMainThread_withObject_waitUntilDone_(
                    "setStatus:", "Waiting for administrator password...", False
                )
                
                escaped_path = str(script_path).replace('\\', '\\\\').replace('"', '\\"')
                applescript = f'do shell script "/bin/bash -l \\"{escaped_path}\\" install" with administrator privileges'
                
                self.appendText_("[INFO] A system password dialog should appear.\n")
                
                self.process = subprocess.Popen(
                    ["osascript", "-e", applescript],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1
                )
                
                admin_output = []
                for line in self.process.stdout:
                    if self.cancelled:
                        break
                    admin_output.append(line)
                    self.appendText_(line)
                
                self.process.stdout.close()
                rc = self.process.wait()
                
                if self.cancelled:
                    self.appendText_("\n[CANCELLED] Installation was cancelled by user.\n")
                    if self.on_complete:
                        self.on_complete(False, "cancelled")
                    return
                
                if rc == 0:
                    self.appendText_("\n[SUCCESS] All dependencies installed successfully!\n")
                    self.performSelectorOnMainThread_withObject_waitUntilDone_(
                        "setStatus:", "Installation complete ✓", False
                    )
                    if self.on_complete:
                        self.on_complete(True, None)
                else:
                    admin_err = "".join(admin_output).lower()
                    if "running homebrew as root" in admin_err:
                        self.appendText_(
                            "\n[ERROR] Homebrew refuses to run as root.\n"
                            "[INFO] Please install XeLaTeX manually from https://www.tug.org/mactex/\n"
                        )
                        self.performSelectorOnMainThread_withObject_waitUntilDone_(
                            "setStatus:", "Manual install required (Homebrew/root conflict)", False
                        )
                        if self.on_complete:
                            self.on_complete(False, "homebrew_root")
                    else:
                        self.appendText_("\n[ERROR] Installation failed even with admin privileges.\n")
                        self.performSelectorOnMainThread_withObject_waitUntilDone_(
                            "setStatus:", "Installation failed", False
                        )
                        if self.on_complete:
                            self.on_complete(False, "admin_install_failed")
                
            except subprocess.TimeoutExpired:
                self.appendText_("\n[ERROR] Installation timed out.\n")
                self.performSelectorOnMainThread_withObject_waitUntilDone_(
                    "setStatus:", "Installation timed out", False
                )
                if self.on_complete:
                    self.on_complete(False, "timeout")
            except Exception as e:
                self.appendText_(f"\n[ERROR] {e}\n")
                if self.on_complete:
                    self.on_complete(False, str(e))
        
        t = threading.Thread(target=_install_thread, daemon=True)
        t.start()


class OwlangsDelegate(NSObject):
    """Menu bar and application delegate."""
    
    def init(self):
        self = objc.super(OwlangsDelegate, self).init()
        if self is None:
            return None
        self.backend_process = None
        self.is_running = False
        self.status_item = None
        self.status_check_thread = None
        self.log_window_controller = None
        self.start_time = None
        return self
    
    def applicationShouldTerminate_(self, sender):
        """Called when application is about to terminate. Clean up backend."""
        log_message("Application is terminating, cleaning up backend...")
        self._cleanup_backend()
        return True  # Allow termination
    
    def _cleanup_backend(self):
        """Forcefully stop the backend server and clean up all related processes."""
        try:
            # Terminate our tracked subprocess
            if self.backend_process and self.backend_process.poll() is None:
                log_message("Terminating backend subprocess...")
                self.backend_process.terminate()
                try:
                    self.backend_process.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    log_message("Backend did not terminate gracefully, killing...")
                    self.backend_process.kill()
                    self.backend_process.wait(timeout=2)
            
            # Kill any process still listening on our port
            try:
                result = subprocess.run(
                    ['lsof', '-ti', f':{PORT}'],
                    capture_output=True, text=True, timeout=5
                )
                if result.returncode == 0 and result.stdout.strip():
                    for pid_str in result.stdout.strip().split('\n'):
                        pid = pid_str.strip()
                        if pid:
                            try:
                                log_message(f"Killing process {pid} on port {PORT}")
                                os.kill(int(pid), 9)
                            except Exception:
                                pass
            except Exception as e:
                log_message(f"Error killing port processes: {e}")
            
            # Remove lock file
            if LOCK_FILE.exists():
                try:
                    LOCK_FILE.unlink()
                    log_message("Lock file removed")
                except Exception:
                    pass
            
            # Also try to find and kill any OwlangsBackend processes
            try:
                result = subprocess.run(
                    ['pgrep', '-f', 'OwlangsBackend'],
                    capture_output=True, text=True, timeout=3
                )
                if result.returncode == 0 and result.stdout.strip():
                    for pid_str in result.stdout.strip().split('\n'):
                        pid = pid_str.strip()
                        if pid and int(pid) != os.getpid():
                            try:
                                log_message(f"Killing orphaned OwlangsBackend process {pid}")
                                os.kill(int(pid), 9)
                            except Exception:
                                pass
            except Exception:
                pass
            
            self.is_running = False
            log_message("Backend cleanup completed")
            
        except Exception as e:
            log_message(f"Error during backend cleanup: {e}")
    
    def applicationDidFinishLaunching_(self, notification):
        """Called when application finishes launching."""
        log_message("Application did finish launching")
        
        # Create status bar item
        status_bar = NSStatusBar.systemStatusBar()
        self.status_item = status_bar.statusItemWithLength_(NSVariableStatusItemLength)
        
        # Set icon if available
        icon_path = self._get_icon_path()
        if icon_path and icon_path.exists():
            image = NSImage.alloc().initWithContentsOfFile_(str(icon_path))
            if image:
                # Use 20x20 for better visibility in menu bar
                image.setSize_(NSMakeSize(20, 20))
                # Template mode = gray when stopped, original color when running
                image.setTemplate_(True)
                self.status_icon = image
                self.status_item.setImage_(image)
                log_message(f"Icon loaded: {icon_path}")
            else:
                log_message(f"Failed to load icon from: {icon_path}")
                self.status_item.setTitle_("Owlangs")
        else:
            log_message("No icon found, using text")
            self.status_item.setTitle_("Owlangs")
        
        self.status_item.setHighlightMode_(True)
        
        # Create menu
        self._create_menu()
        
        # Start status check thread
        self.status_check_thread = threading.Thread(target=self._status_check_loop, daemon=True)
        self.status_check_thread.start()
        
        log_message("Menu bar initialized")
        
        # Auto-start server on launch (default behavior)
        log_message("Auto-starting server on launch...")
        # Delay slightly to let UI settle
        NSThread.sleepForTimeInterval_(1.5)
        self.performSelectorOnMainThread_withObject_waitUntilDone_(
            "startServer:", None, False
        )
        
        # Auto-check dependencies on launch
        if self._should_auto_check_deps():
            log_message("Auto-checking dependencies on launch...")
            NSThread.sleepForTimeInterval_(5.0)
            self.performSelectorOnMainThread_withObject_waitUntilDone_(
                "checkDependencies:", None, False
            )
    
    def showMenu(self):
        """Show the status bar menu."""
        if self.status_item is not None and self.status_item.menu() is not None:
            # Get the status bar button and simulate click
            button = self.status_item.button()
            if button is not None:
                # Perform click to show menu
                button.performClick_(None)
    
    def _get_icon_path(self):
        """Get path to icon file."""
        if getattr(sys, 'frozen', False):
            bundle_dir = Path(sys._MEIPASS)
        else:
            bundle_dir = Path(__file__).resolve().parent.parent.parent
        
        # Try different icon sources, prefer PNG for menu bar
        # Order: menu bar optimized > solid icon > favicon
        for icon_name in ["owlangs_owl_solid.png", "Owlangs.icns", "favicon.png"]:
            # Check in root directory first
            path = bundle_dir / icon_name
            if path.exists():
                return path
            # Check in assets directory
            path = bundle_dir / "assets" / icon_name
            if path.exists():
                return path
        return None
    
    def _create_menu(self):
        """Create the menu."""
        menu = NSMenu.alloc().init()
        
        # Status item
        self.status_menu_item = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
            "Status: Stopped", None, ""
        )
        menu.addItem_(self.status_menu_item)
        
        menu.addItem_(NSMenuItem.separatorItem())
        
        # Show Logs
        logs_item = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
            "Show Logs", "showLogs:", ""
        )
        logs_item.setTarget_(self)
        menu.addItem_(logs_item)
        
        # Open Browser
        open_item = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
            "Open Browser", "openBrowser:", ""
        )
        open_item.setTarget_(self)
        menu.addItem_(open_item)
        
        # Check Dependencies
        check_deps_item = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
            "Check Dependencies...", "checkDependencies:", ""
        )
        check_deps_item.setTarget_(self)
        menu.addItem_(check_deps_item)
        
        menu.addItem_(NSMenuItem.separatorItem())
        
        # Start Server
        self.start_menu_item = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
            "Start Server", "startServer:", ""
        )
        self.start_menu_item.setTarget_(self)
        menu.addItem_(self.start_menu_item)
        
        # Stop Server
        self.stop_menu_item = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
            "Stop Server", "stopServer:", ""
        )
        self.stop_menu_item.setTarget_(self)
        self.stop_menu_item.setEnabled_(False)
        menu.addItem_(self.stop_menu_item)
        
        menu.addItem_(NSMenuItem.separatorItem())
        
        # Preferences
        prefs_item = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
            "Preferences...", "showPreferences:", ","
        )
        prefs_item.setTarget_(self)
        menu.addItem_(prefs_item)
        
        menu.addItem_(NSMenuItem.separatorItem())
        
        # About
        about_item = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
            "About Owlangs", "showAbout:", ""
        )
        about_item.setTarget_(self)
        menu.addItem_(about_item)
        
        # Quit
        quit_item = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
            "Quit Owlangs", "terminate:", "q"
        )
        menu.addItem_(quit_item)
        
        self.status_item.setMenu_(menu)
    
    def _should_auto_start(self):
        """Check if should auto-start server."""
        try:
            if PREFERENCES_FILE.exists():
                import json
                prefs = json.loads(PREFERENCES_FILE.read_text())
                return prefs.get("auto_start", False)
        except:
            pass
        return False
    
    def _should_auto_check_deps(self):
        """Check if should auto-check dependencies on launch."""
        try:
            if PREFERENCES_FILE.exists():
                import json
                prefs = json.loads(PREFERENCES_FILE.read_text())
                return prefs.get("auto_check_deps", True)
        except:
            pass
        return True
    
    def _save_preference(self, key, value):
        """Save a preference."""
        try:
            PREFERENCES_FILE.parent.mkdir(parents=True, exist_ok=True)
            prefs = {}
            if PREFERENCES_FILE.exists():
                import json
                prefs = json.loads(PREFERENCES_FILE.read_text())
            prefs[key] = value
            PREFERENCES_FILE.write_text(json.dumps(prefs, indent=2))
        except Exception as e:
            log_message(f"Error saving preference: {e}")
    
    def _status_check_loop(self):
        """Background thread to check backend status."""
        while True:
            try:
                time.sleep(2)
                was_running = self.is_running
                self.is_running = self._check_backend_running()
                
                if was_running != self.is_running:
                    log_message(f"Status changed: running={self.is_running}")
                    self.performSelectorOnMainThread_withObject_waitUntilDone_(
                        "updateMenuState", None, False
                    )
            except Exception as e:
                log_message(f"Error in status check: {e}")
    
    def _check_backend_running(self):
        """Check if backend is running."""
        try:
            # Check our process first
            if self.backend_process and self.backend_process.poll() is None:
                return True
            
            # Check lock file
            if LOCK_FILE.exists():
                try:
                    pid = int(LOCK_FILE.read_text().strip())
                    os.kill(pid, 0)
                    return True
                except (ValueError, OSError, ProcessLookupError):
                    pass
            
            # Check port
            result = subprocess.run(['lsof', '-i', f':{PORT}'], capture_output=True, text=True)
            if result.returncode == 0 and result.stdout.strip():
                return True
        except Exception as e:
            log_message(f"Error checking status: {e}")
        return False
    
    def updateMenuState(self):
        """Update menu state based on running status."""
        status_text = f"Status: {'Running ✓' if self.is_running else 'Stopped'}"
        self.status_menu_item.setTitle_(status_text)
        
        # Enable/disable menu items
        self.start_menu_item.setEnabled_(not self.is_running)
        self.stop_menu_item.setEnabled_(self.is_running)
        
        # Toggle icon color: gray (template) when stopped, original color when running
        if self.status_icon is not None:
            self.status_icon.setTemplate_(not self.is_running)
            self.status_item.setImage_(self.status_icon)
        
        log_message(f"Menu updated: {status_text}")
    
    def get_backend_path(self):
        """Get path to backend executable."""
        if getattr(sys, 'frozen', False):
            exe_path = Path(sys.executable)
            resources_dir = exe_path.parent.parent / "Resources"
            backend_path = resources_dir / "OwlangsBackend"
            if backend_path.exists():
                return backend_path
            return Path(sys._MEIPASS) / "dist" / f"Owlangs-{APP_VERSION}-mac"
        else:
            return Path(__file__).resolve().parent.parent.parent / "dist" / f"Owlangs-{APP_VERSION}-mac"
    
    def showLogs_(self, sender):
        """Show the logs window."""
        if self.log_window_controller is None:
            self.log_window_controller = LogWindowController.alloc().init()
        self.log_window_controller.showWindow()
    
    def openBrowser_(self, sender):
        """Open browser."""
        log_message("Open browser requested")
        if not self.is_running:
            self._show_notification("Owlangs", "Not Running", "Please start the server first.")
            return
        import webbrowser
        webbrowser.open(f"http://localhost:{PORT}")
    
    def startServer_(self, sender):
        """Start the backend server."""
        log_message("Start server requested")
        
        if self.is_running:
            self._show_notification("Owlangs", "Already Running", "The backend is already running.")
            return
        
        try:
            backend_path = self.get_backend_path()
            if not backend_path.exists():
                self._show_alert("Error", f"Backend not found: {backend_path}")
                return
            
            # Show logs window
            self.showLogs_(None)
            
            log_message(f"Starting backend: {backend_path}")
            
            # Start backend with output capture
            self.backend_process = subprocess.Popen(
                [str(backend_path), "-i"],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                env=self._backend_subprocess_env(),
                cwd=str(Path(sys.executable).parent if getattr(sys, 'frozen', False) else Path(__file__).parent.parent.parent)
            )
            
            # Start thread to read output
            output_thread = threading.Thread(target=self._read_output, daemon=True)
            output_thread.start()
            
            # Wait a moment and check if it started
            time.sleep(3)
            
            if self.backend_process.poll() is None:
                self.is_running = True
                self.updateMenuState()
                self._show_notification("Owlangs", "Server Started", f"Running on port {PORT}")
                log_message("Server started successfully")
                
                # Open browser after a short delay
                NSThread.sleepForTimeInterval_(2.0)
                self.openBrowser_(None)
            else:
                stdout, _ = self.backend_process.communicate()
                self._show_alert("Error", f"Failed to start: {stdout[-500:] if stdout else 'Unknown error'}")
                
        except Exception as e:
            log_message(f"Error starting server: {e}")
            log_message(traceback.format_exc())
            self._show_alert("Error", f"Failed to start server: {e}")
    
    def _read_output(self):
        """Read output from backend process."""
        if self.backend_process is None:
            return
        
        log_message("Started reading backend output")
        
        try:
            # Simply iterate over stdout - this blocks until line is available
            for line in self.backend_process.stdout:
                if line:
                    log_queue.put(line)
            
            # Process ended
            log_queue.put("\n[Server process ended]\n")
                
        except Exception as e:
            log_message(f"Error reading output: {e}")
            log_message(traceback.format_exc())
    
    def stopServer_(self, sender):
        """Stop the backend server."""
        log_message("Stop server requested")
        
        if not self.is_running:
            self._show_notification("Owlangs", "Not Running", "The backend is not running.")
            return
        
        try:
            if self.backend_process and self.backend_process.poll() is None:
                self.backend_process.terminate()
                try:
                    self.backend_process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    self.backend_process.kill()
            
            # Kill processes on port
            try:
                result = subprocess.run(['lsof', '-ti', f':{PORT}'], capture_output=True, text=True)
                if result.returncode == 0 and result.stdout.strip():
                    for pid in result.stdout.strip().split('\n'):
                        if pid.strip():
                            try:
                                os.kill(int(pid.strip()), 9)
                            except:
                                pass
            except:
                pass
            
            if LOCK_FILE.exists():
                LOCK_FILE.unlink()
            
            self.is_running = False
            self.updateMenuState()
            self._show_notification("Owlangs", "Server Stopped", "Backend has been stopped.")
            log_queue.put("\n[Server stopped]\n")
            log_message("Server stopped")
            
        except Exception as e:
            log_message(f"Error stopping server: {e}")
            self._show_alert("Error", f"Error stopping server: {e}")
    
    def showPreferences_(self, sender):
        """Show preferences dialog."""
        current_auto_start = self._should_auto_start()
        
        # Create simple dialog using osascript
        result = subprocess.run([
            'osascript', '-e',
            f'display dialog "Auto-start server on launch?" buttons {{"No", "Yes"}} default button "{"Yes" if current_auto_start else "No"}" with title "Owlangs Preferences"'
        ], capture_output=True, text=True)
        
        if "Yes" in result.stdout:
            self._save_preference("auto_start", True)
            log_message("Auto-start enabled")
        elif "No" in result.stdout:
            self._save_preference("auto_start", False)
            log_message("Auto-start disabled")
    
    def get_dependencies_script_path(self):
        """Get path to install_dependencies.sh script."""
        script_name = "install_dependencies.sh"
        fallback = (
            Path(__file__).resolve().parent.parent
            / "setup"
            / "install_dependencies_macos.sh"
        )
        if getattr(sys, 'frozen', False):
            bundle_dir = Path(sys._MEIPASS)
            script_path = bundle_dir / "3rdParty" / "macos" / script_name
            if script_path.exists():
                return script_path
        else:
            script_path = Path(__file__).resolve().parent.parent.parent / "3rdParty" / "macos" / script_name
            if script_path.exists():
                return script_path
            if fallback.exists():
                return fallback
        return None

    @objc.python_method
    def _backend_subprocess_env(self):
        """Augment PATH so bundled/GUI backend finds Homebrew and TeX tools (typst, pandoc, xelatex)."""
        env = os.environ.copy()
        extra_paths = [
            "/opt/homebrew/bin",
            "/usr/local/bin",
            "/Library/TeX/texbin",
        ]
        current = env.get("PATH", "")
        prefix = os.pathsep.join(p for p in extra_paths if p not in current.split(os.pathsep))
        if prefix:
            env["PATH"] = f"{prefix}{os.pathsep}{current}" if current else prefix
        return env
    
    def _check_command_exists(self, cmd):
        """Check if a command exists, trying multiple methods to handle GUI app PATH limitations."""
        # Method 1: direct which
        try:
            result = subprocess.run(["which", cmd], capture_output=True, text=True)
            if result.returncode == 0 and result.stdout.strip():
                return True
        except Exception:
            pass
        
        # Method 2: bash login shell (loads ~/.bash_profile, ~/.profile, etc.)
        try:
            result = subprocess.run(["/bin/bash", "-l", "-c", f"command -v {cmd}"], capture_output=True, text=True)
            if result.returncode == 0 and result.stdout.strip():
                return True
        except Exception:
            pass
        
        # Method 3: zsh login shell (loads ~/.zshrc, ~/.zprofile, etc.)
        try:
            result = subprocess.run(["/bin/zsh", "-l", "-c", f"command -v {cmd}"], capture_output=True, text=True)
            if result.returncode == 0 and result.stdout.strip():
                return True
        except Exception:
            pass
        
        # Method 4: check common paths
        common_paths = ["/opt/homebrew/bin", "/usr/local/bin", "/usr/bin", "/bin", "/usr/sbin", "/sbin", "/Library/TeX/texbin"]
        for p in common_paths:
            if (Path(p) / cmd).exists():
                return True
        
        return False
    
    def _show_dependency_help(self):
        """Open dependency installation help in default browser."""
        help_html = '''<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Owlangs 依赖安装指南</title>
    <style>
        body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; max-width: 800px; margin: 0 auto; padding: 30px 20px; line-height: 1.7; color: #333; background: #fafafa; }
        h1 { color: #1d1d1f; border-bottom: 3px solid #007AFF; padding-bottom: 12px; margin-bottom: 24px; }
        h2 { color: #333; margin-top: 32px; font-size: 1.3em; }
        h3 { color: #007AFF; margin-top: 20px; font-size: 1.1em; }
        .dep { background: #fff; border-radius: 12px; padding: 20px; margin: 16px 0; box-shadow: 0 1px 3px rgba(0,0,0,0.08); }
        .dep h3 { margin-top: 0; }
        code { background: #f0f0f5; padding: 2px 8px; border-radius: 6px; font-size: 0.9em; font-family: "SF Mono", Monaco, monospace; }
        pre { background: #1d1d1f; color: #f5f5f7; padding: 16px; border-radius: 10px; overflow-x: auto; font-size: 0.9em; line-height: 1.5; }
        a { color: #007AFF; text-decoration: none; }
        a:hover { text-decoration: underline; }
        .note { background: #fffbe6; border-left: 4px solid #ffc107; padding: 14px 18px; margin: 18px 0; border-radius: 0 8px 8px 0; }
        .note strong { color: #b45309; }
        .tip { background: #e6f7ff; border-left: 4px solid #007AFF; padding: 14px 18px; margin: 18px 0; border-radius: 0 8px 8px 0; }
        .tip strong { color: #0056b3; }
        ul { padding-left: 20px; }
        li { margin: 8px 0; }
        .footer { margin-top: 40px; padding-top: 20px; border-top: 1px solid #ddd; color: #666; font-size: 0.9em; text-align: center; }
    </style>
</head>
<body>
    <h1>📦 Owlangs 依赖安装指南</h1>
    <p>Owlangs 需要以下第三方依赖才能正常运行。如果自动安装失败，请按照下方步骤手动安装。</p>

    <div class="note">
        <strong>macOS 12 用户注意：</strong>Homebrew 官方已停止对 macOS 12 的正式支持。如果 Homebrew 命令无法运行，请直接访问各依赖官网下载安装包进行安装。
    </div>

    <div class="dep">
        <h3>1. Homebrew（包管理器）</h3>
        <p>Homebrew 是 macOS 上最常用的包管理器，用于安装 Redis、Pandoc 等工具。</p>
        <p><strong>官网：</strong><a href="https://brew.sh" target="_blank">https://brew.sh</a></p>
        <p>在终端中运行以下命令安装：</p>
        <pre>/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"</pre>
        <p>安装完成后，根据提示将 Homebrew 添加到 PATH（Apple Silicon Mac 通常需要）：</p>
        <pre>echo 'eval "$(/opt/homebrew/bin/brew shellenv)"' >> ~/.zprofile\neval "$(/opt/homebrew/bin/brew shellenv)"</pre>
    </div>

    <div class="dep">
        <h3>2. Redis（缓存数据库）</h3>
        <p>Redis 用于任务队列和缓存，Owlangs 运行时必须启动 Redis 服务。</p>
        <p><strong>官网：</strong><a href="https://redis.io" target="_blank">https://redis.io</a></p>
        <p>使用 Homebrew 安装：</p>
        <pre>brew install redis\nbrew services start redis</pre>
        <p>验证安装：</p>
        <pre>redis-server --version</pre>
    </div>

    <div class="dep">
        <h3>3. Pandoc（文档格式转换）</h3>
        <p>Pandoc 用于文档格式转换，如 DOCX、HTML 等。</p>
        <p><strong>官网下载：</strong><a href="https://pandoc.org/installing.html" target="_blank">https://pandoc.org/installing.html</a></p>
        <p>使用 Homebrew 安装：</p>
        <pre>brew install pandoc</pre>
        <p>或直接从官网下载 .pkg 安装包，双击安装即可。</p>
        <p>验证安装：</p>
        <pre>pandoc --version</pre>
    </div>

    <div class="dep">
        <h3>4. Typst（PDF 原位翻译）</h3>
        <p>Typst 用于 PDF 原位翻译导出（<code>typst_overlay</code>），在保留原 PDF 版式的前提下叠加译文。</p>
        <p><strong>官网：</strong><a href="https://github.com/typst/typst/releases" target="_blank">https://github.com/typst/typst/releases</a></p>
        <p>使用 Homebrew 安装：</p>
        <pre>brew install typst</pre>
        <p>验证安装：</p>
        <pre>typst --version</pre>
    </div>

    <div class="dep">
        <h3>5. XeLaTeX（PDF 重排导出引擎）</h3>
        <p>XeLaTeX 用于 PDF 导出功能。推荐安装 MacTeX（完整版）或 TinyTeX（轻量版）。</p>
        <p><strong>MacTeX 官网：</strong><a href="https://www.tug.org/mactex/" target="_blank">https://www.tug.org/mactex/</a></p>
        <p>使用 Homebrew 安装 MacTeX（约 4GB）：</p>
        <pre>brew install --cask mactex</pre>
        <p>安装后需要将 LaTeX 添加到 PATH：</p>
        <pre>export PATH="/Library/TeX/texbin:$PATH"</pre>
        <p>添加到 <code>~/.zshrc</code> 或 <code>~/.bash_profile</code> 使其永久生效。</p>
        <p>如果只需要轻量版，可安装 TinyTeX：</p>
        <pre>brew install --cask tinytex</pre>
        <p>验证安装：</p>
        <pre>xelatex --version</pre>
    </div>

    <div class="tip">
        <strong>💡 提示：</strong>安装完所有依赖后，点击 MenuBar 中的 <strong>Check Dependencies</strong> 再次检查，确认所有依赖都已正确安装。
    </div>

    <div class="footer">
        Owlangs 文档翻译工具 | 如遇问题请访问 <a href="https://github.com/zampher/owlangs" target="_blank">GitHub</a>
    </div>
</body>
</html>'''
        
        try:
            help_dir = Path.home() / "Library" / "Application Support" / "Owlangs"
            help_dir.mkdir(parents=True, exist_ok=True)
            help_path = help_dir / "dependency_help.html"
            help_path.write_text(help_html, encoding="utf-8")
            subprocess.run(["open", str(help_path)])
            log_message(f"Opened dependency help: {help_path}")
        except Exception as e:
            log_message(f"Error opening help: {e}")
            self._show_alert("Error", f"Could not open help document: {e}")

    def checkDependencies_(self, sender):
        """Check if required dependencies are installed."""
        log_message("Checking dependencies...")
        
        deps = {
            "Homebrew": "brew",
            "Redis": "redis-server",
            "Pandoc": "pandoc",
            "Typst": "typst",
            "XeLaTeX": "xelatex",
        }
        
        missing = []
        installed = []
        
        for name, cmd in deps.items():
            if self._check_command_exists(cmd):
                installed.append(name)
            else:
                missing.append(name)
                log_message(f"Dependency not found: {name} ({cmd})")
        
        if not missing:
            self._show_alert(
                "Dependencies",
                "All dependencies are installed! ✓\\n\\n"
                "Homebrew, Redis, Pandoc, Typst, and XeLaTeX are all ready.",
            )
            log_message("All dependencies are installed")
            return
        
        missing_str = "\\n• ".join([""] + missing)
        script_path = self.get_dependencies_script_path()
        
        if script_path and script_path.exists():
            # Use NSAlert for richer UI (checkbox + multiple buttons)
            alert = NSAlert.alloc().init()
            alert.setMessageText_("Missing Dependencies")
            alert.setInformativeText_(
                f"The following dependencies are missing:{missing_str}\\n\\n"
                "You can install them automatically or view the manual guide.\\n"
                "NOTE: You may be asked to enter your password."
            )
            alert.addButtonWithTitle_("Install")
            alert.addButtonWithTitle_("Help")
            alert.addButtonWithTitle_("Cancel")
            
            # Add "Don't remind me again" checkbox
            checkbox = NSButton.alloc().initWithFrame_(NSMakeRect(0, 0, 240, 18))
            checkbox.setButtonType_(3)  # NSSwitchButton
            checkbox.setTitle_("Don't remind me again on launch")
            alert.setAccessoryView_(checkbox)
            
            result = alert.runModal()
            
            if checkbox.state() == 1:
                self._save_preference("auto_check_deps", False)
                log_message("User disabled auto dependency check on launch")
            
            if result == 1000:      # Install
                log_message(f"Installing dependencies via {script_path}")
                self._install_dependencies(script_path)
            elif result == 1001:    # Help
                log_message("User opened dependency help")
                self._show_dependency_help()
            else:                   # Cancel (1002) or closed
                log_message("User dismissed dependency dialog")
        else:
            # Script not found - show help-focused dialog
            result = subprocess.run([
                'osascript', '-e',
                f'display dialog "The following dependencies are missing:{missing_str}\\n\\nThe automatic installer script was not found. Please install dependencies manually." buttons {{"Close", "View Help"}} default button "View Help" with title "Missing Dependencies"'
            ], capture_output=True, text=True)
            
            if "View Help" in result.stdout or "Help" in result.stdout:
                self._show_dependency_help()
    
    def _install_dependencies(self, script_path):
        """Run the dependency installation script with real-time progress window and cancel support."""
        try:
            # Create and show the install progress window
            if not hasattr(self, 'install_window') or self.install_window is None:
                self.install_window = InstallWindowController.alloc().init()
            self.install_window.showWindow()
            
            def on_complete(success, error):
                if success:
                    self._show_notification("Owlangs", "Success", "Dependencies installed successfully!")
                    self._show_alert("Success", "All dependencies have been installed successfully!")
                elif error == "cancelled":
                    self._show_notification("Owlangs", "Cancelled", "Installation was cancelled.")
                    self._show_alert("Cancelled", "Installation was cancelled. Some dependencies may still be missing.")
                elif error == "timeout":
                    self._show_alert("Timeout", "Dependency installation took too long. Please try running the script manually.")
                elif error == "tty_required":
                    self._show_alert(
                        "Manual Install Required",
                        "The automatic installer cannot enter your password in GUI mode.\n\n"
                        "Please open Terminal and run:\n"
                        f"/bin/bash -l {script_path} install\n\n"
                        "Or install XeLaTeX manually from https://www.tug.org/mactex/"
                    )
                elif error == "homebrew_root":
                    self._show_alert(
                        "Homebrew Conflict",
                        "Homebrew refuses to run with administrator privileges.\n\n"
                        "Please open Terminal and run without sudo:\n"
                        f"/bin/bash -l {script_path} install\n\n"
                        "Or install XeLaTeX manually from https://www.tug.org/mactex/"
                    )
                elif error == "admin_install_failed":
                    self._show_install_failed_dialog("Installation failed even with administrator privileges.")
                else:
                    self._show_install_failed_dialog(error or "Unknown installation error.")
            
            self.install_window.runInstall(script_path, on_complete)
            
        except Exception as e:
            log_message(f"Error starting installation: {e}")
            self._show_alert("Error", f"Failed to start installation: {e}")
    
    def _analyze_install_error(self, error_detail):
        """Analyze installation error and return user-friendly reason + action."""
        error_lower = error_detail.lower() if error_detail else ""
        
        if "not a tty" in error_lower or "non-interactive" in error_lower:
            return (
                "The installer requires an interactive terminal.",
                "Please open Terminal and run:\n/bin/bash -l install_dependencies.sh install"
            )
        elif "root" in error_lower and ("don't run" in error_lower or "do not run" in error_lower):
            return (
                "Homebrew cannot be installed as root user.",
                "Please run without sudo. The installer will ask for your password when needed."
            )
        elif "certificate" in error_lower or "ssl" in error_lower or "tls" in error_lower:
            return (
                "Network security certificate verification failed.",
                "Please check your internet connection and try again, or install manually via the guide."
            )
        elif "homebrew" in error_lower and ("not found" in error_lower or "command not found" in error_lower):
            return (
                "Homebrew is not installed on this Mac.",
                "Please install Homebrew first from https://brew.sh, then try again."
            )
        elif "unsupported" in error_lower or ("macos" in error_lower and "version" in error_lower):
            return (
                "Your macOS version may be too old for the latest Homebrew.",
                "Please install dependencies manually by downloading from their official websites."
            )
        elif "permission denied" in error_lower or "eacces" in error_lower:
            return (
                "The installer does not have permission to write to the required directories.",
                "Please click Install again and enter your administrator password when prompted."
            )
        elif "timeout" in error_lower:
            return (
                "The installation took too long and was cancelled.",
                "Please check your network connection and try again, or install manually via the guide."
            )
        else:
            return (
                "The automatic installer encountered an unexpected error.",
                "You can install dependencies manually by following the guide."
            )
    
    def _show_install_failed_dialog(self, error_detail):
        """Show a user-friendly dialog when automatic installation fails, offering manual install help."""
        reason, action = self._analyze_install_error(error_detail)
        
        # Write full error log to file for debugging
        try:
            log_dir = Path.home() / "Library" / "Application Support" / "Owlangs"
            log_dir.mkdir(parents=True, exist_ok=True)
            log_path = log_dir / "install_error.log"
            with open(log_path, "w") as f:
                f.write(f"Installation failed at {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write("=" * 60 + "\n")
                f.write(error_detail + "\n")
        except Exception:
            pass
        
        # Show user-friendly alert (display alert supports longer messages better than dialog)
        result = subprocess.run([
            'osascript', '-e',
            f'display alert "Installation Failed" message "{reason}\\n\\n{action}" buttons {{"Close", "View Help"}} default button "View Help"'
        ], capture_output=True, text=True)
        
        if "View Help" in result.stdout or "Help" in result.stdout:
            self._show_dependency_help()
    
    def showAbout_(self, sender):
        """Show about dialog."""
        subprocess.run([
            'osascript', '-e',
            f'display dialog "Owlangs v{APP_VERSION}\\n\\nA document translation tool powered by AI.\\n\\nOpen http://localhost:8800 in your browser to use." buttons {{"OK"}} default button "OK" with title "About Owlangs"'
        ], capture_output=True)
    
    def _show_notification(self, title, subtitle, message):
        """Show system notification."""
        try:
            notification = NSUserNotification.alloc().init()
            notification.setTitle_(title)
            notification.setSubtitle_(subtitle)
            notification.setInformativeText_(message)
            center = NSUserNotificationCenter.defaultUserNotificationCenter()
            center.deliverNotification_(notification)
        except:
            pass
    
    def _show_alert(self, title, message):
        """Show alert dialog."""
        try:
            subprocess.run([
                'osascript', '-e',
                f'display dialog "{message}" buttons {{"OK"}} default button "OK" with title "{title}"'
            ], capture_output=True)
        except:
            pass


def check_single_instance():
    """Check if another instance is already running."""
    lock_file = Path.home() / "Library" / "Application Support" / "Owlangs" / "menubar.lock"
    lock_file.parent.mkdir(parents=True, exist_ok=True)
    
    try:
        import fcntl
        fd = os.open(str(lock_file), os.O_RDWR | os.O_CREAT)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            os.ftruncate(fd, 0)
            os.write(fd, str(os.getpid()).encode())
            return fd, lock_file
        except IOError:
            os.close(fd)
            log_message("Another instance is already running")
            sys.exit(0)
    except ImportError:
        if lock_file.exists():
            try:
                pid = int(lock_file.read_text().strip())
                os.kill(pid, 0)
                log_message("Another instance is already running")
                sys.exit(0)
            except:
                pass
        lock_file.write_text(str(os.getpid()))
        return None, lock_file


if __name__ == "__main__":
    log_message("main() started")
    
    lock_fd = None
    lock_file = None
    _delegate = None
    
    def _signal_handler(signum, frame):
        """Handle SIGTERM/SIGINT by cleaning up backend and exiting."""
        log_message(f"Received signal {signum}, shutting down...")
        if _delegate is not None:
            _delegate._cleanup_backend()
        # Clean up lock file
        try:
            if lock_fd:
                import fcntl
                fcntl.flock(lock_fd, fcntl.LOCK_UN)
                os.close(lock_fd)
        except:
            pass
        try:
            if lock_file and lock_file.exists():
                lock_file.unlink()
        except:
            pass
        sys.exit(0)
    
    # Register signal handlers
    import signal
    signal.signal(signal.SIGTERM, _signal_handler)
    signal.signal(signal.SIGINT, _signal_handler)
    
    try:
        lock_fd, lock_file = check_single_instance()
        
        # Create application
        app = NSApplication.sharedApplication()
        app.setActivationPolicy_(NSApplicationActivationPolicyRegular)
        
        # Create delegate
        delegate = OwlangsDelegate.alloc().init()
        _delegate = delegate
        app.setDelegate_(delegate)
        
        log_message("Running app...")
        AppHelper.runEventLoop()
        
    except Exception as e:
        log_message(f"Fatal error: {e}")
        log_message(traceback.format_exc())
    finally:
        log_message("Cleaning up...")
        # Cleanup backend if delegate still exists
        if _delegate is not None:
            _delegate._cleanup_backend()
        try:
            if lock_fd:
                import fcntl
                fcntl.flock(lock_fd, fcntl.LOCK_UN)
                os.close(lock_fd)
        except:
            pass
        try:
            if lock_file and lock_file.exists():
                lock_file.unlink()
        except:
            pass
