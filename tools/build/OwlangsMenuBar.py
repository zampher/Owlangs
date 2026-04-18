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
        NSLayoutAttributeTrailing, NSLayoutRelationEqual, NSLayoutFormatAlignAllLeading
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
                # Enable template mode for proper dark mode support
                image.setTemplate_(True)
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
    
    try:
        lock_fd, lock_file = check_single_instance()
        
        # Create application
        app = NSApplication.sharedApplication()
        app.setActivationPolicy_(NSApplicationActivationPolicyRegular)
        
        # Create delegate
        delegate = OwlangsDelegate.alloc().init()
        app.setDelegate_(delegate)
        
        log_message("Running app...")
        AppHelper.runEventLoop()
        
    except Exception as e:
        log_message(f"Fatal error: {e}")
        log_message(traceback.format_exc())
    finally:
        log_message("Cleaning up...")
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
