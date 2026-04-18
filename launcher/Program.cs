using System;
using System.Diagnostics;
using System.IO;
using System.Linq;
using System.Threading;
using System.Threading.Tasks;
using System.Windows;
using System.Windows.Threading;
using OwlangsLauncher.Services;
using OwlangsLauncher.Views;

namespace OwlangsLauncher
{
    /// <summary>
    /// Interaction logic for App.xaml
    /// </summary>
    public partial class App : Application
    {
        private static Mutex? _instanceMutex;
        private const string MutexName = "OwlangsLauncher_SingleInstance";
        
        private BackendService? _backendService;
        private FrontendService? _frontendService;
        private TrayService? _trayService;
        private IpcService? _ipcService;
        private ExitRequestListenerService? _exitRequestListener;
        private LogWindow? _logWindow;
        private RedisService? _redisService;
        private SplashWindow? _splashWindow;
        private FirstLaunchNotificationWindow? _firstLaunchNotification;
        private bool _hasShownFirstLaunchNotification = false;

        protected override void OnStartup(StartupEventArgs e)
        {
            base.OnStartup(e);

            LauncherLogger.Info("Launcher starting up");
            LauncherLogger.Info($"Base directory: {AppDomain.CurrentDomain.BaseDirectory}");
            LauncherLogger.Info($"Command line: {string.Join(" ", Environment.GetCommandLineArgs())}");
            
            // Check if another instance is already running
            bool createdNew;
            _instanceMutex = new Mutex(true, MutexName, out createdNew);
            
            if (!createdNew)
            {
                // Another instance is running, try to show its console
                LauncherLogger.Info("Another instance is already running, attempting to show console...");
                System.Diagnostics.Debug.WriteLine("Another instance is already running, attempting to show console...");
                try
                {
                    ShowConsoleInExistingInstance();
                    LauncherLogger.Info("Successfully sent show_console request to existing instance");
                }
                catch (Exception ex)
                {
                    LauncherLogger.Error($"Failed to communicate with existing instance: {ex.Message}");
                    LauncherLogger.Error($"Stack trace: {ex.StackTrace}");
                    System.Diagnostics.Debug.WriteLine($"Failed to communicate with existing instance: {ex.Message}");
                }
                
                // Exit this instance
                LauncherLogger.Info("Exiting duplicate instance");
                Shutdown();
                return;
            }

            // Show splash screen
            _splashWindow = new SplashWindow();
            _splashWindow.Show();
            Application.Current.Dispatcher.Invoke(() => { }, DispatcherPriority.Background); // Force UI update

            // Start initialization asynchronously
            _ = Task.Run(async () =>
            {
                try
                {
                    // Check shutdown token before initialization
                    ApplicationShutdownToken.ThrowIfShutdownRequested();
                    
                    await InitializeApplicationAsync();
                }
                catch (OperationCanceledException)
                {
                    // Shutdown requested during initialization
                    LauncherLogger.Info("Program: initialization cancelled due to shutdown");
                }
                catch (Exception ex)
                {
                    // Log full exception details for troubleshooting initialization failures
                    LauncherLogger.Error($"InitializeApplicationAsync failed: {ex}");
                    
                    if (!ApplicationShutdownToken.IsShutdownRequested)
                    {
                        Application.Current.Dispatcher.Invoke(() =>
                        {
                            MessageBox.Show($"Failed to initialize application: {ex.Message}", "Error", 
                                MessageBoxButton.OK, MessageBoxImage.Error);
                            Shutdown();
                        });
                    }
                }
            });
        }

        private async Task InitializeApplicationAsync()
        {
            LauncherLogger.Info("InitializeApplicationAsync: begin");
            // Step 1: Initialize services (10%)
            UpdateSplashStatus("Initializing services...", 10);
            await Task.Delay(100); // Small delay for UI update
            
            // Create services (non-UI operations can be done on background thread)
            LauncherLogger.Info("Initializing BackendService / FrontendService / RedisService");
            _backendService = new BackendService();
            _frontendService = new FrontendService();
            _redisService = new RedisService();
            
            // Step 2: Create IPC service (20%)
            UpdateSplashStatus("Setting up IPC service...", 20);
            await Task.Delay(100);
            
            _ipcService = new IpcService(_backendService, _frontendService);
            LauncherLogger.Info("IPC service created");
            
            // Step 3: Create Tray service (30%)
            UpdateSplashStatus("Initializing tray icon...", 30);
            await Task.Delay(100);
            
            // TrayService creation must be on UI thread (it creates UI components)
            await Application.Current.Dispatcher.InvokeAsync(() =>
            {
                _trayService = new TrayService(_backendService, _frontendService, _ipcService);
            });
            
            // Step 4: Create log window (40%)
            UpdateSplashStatus("Creating log window...", 40);
            await Task.Delay(100);
            
            // LogWindow creation must be on UI thread (it's a WPF Window)
            await Application.Current.Dispatcher.InvokeAsync(() =>
            {
                _logWindow = new LogWindow(_backendService, _frontendService, _redisService, onRequestExit: OnExit);
            });
            
            // Step 5: Start IPC server (50%)
            UpdateSplashStatus("Starting IPC server...", 50);
            await Task.Delay(100);
            
            _ipcService.Start();
            LauncherLogger.Info("IPC service started");

            _exitRequestListener = new ExitRequestListenerService();
            _exitRequestListener.Start();

            // Step 6: Setup event handlers (60%)
            UpdateSplashStatus("Configuring services...", 60);
            await Task.Delay(100);
            
            _backendService.StatusChanged += OnBackendStatusChanged;
            
            // Subscribe to frontend state changes to show first launch notification
            if (_frontendService != null)
            {
                _frontendService.RunningStateChanged += OnFrontendStateChanged;
            }
            
            // Setup event handlers on UI thread
            await Application.Current.Dispatcher.InvokeAsync(() =>
            {
                if (_trayService != null)
                {
                    _trayService.OnShowLogs += () => 
                    {
                        LauncherLogger.Info("Program: OnShowLogs event received (tray menu or double-click)");
                        if (_logWindow != null)
                        {
                            LauncherLogger.Info("Program: calling LogWindow.ShowWindow() from tray event");
                            _logWindow.ShowWindow();
                        }
                        else
                        {
                            LauncherLogger.Warn("Program: LogWindow is null, cannot show console");
                        }
                    };
                    _trayService.OnExit += OnExit;
                    LauncherLogger.Info("Tray service initialized and event handlers wired");
                }
            });
            
            _ipcService.OnShowConsole += () =>
            {
                LauncherLogger.Info("Program: OnShowConsole event received (IPC request)");
                try
                {
                    Application.Current.Dispatcher.Invoke(() =>
                    {
                        if (_logWindow != null)
                        {
                            LauncherLogger.Info("Program: calling LogWindow.ShowWindow() from IPC request");
                            _logWindow.ShowWindow();
                            LauncherLogger.Info("Program: LogWindow.ShowWindow() called successfully");
                        }
                        else
                        {
                            LauncherLogger.Warn("Program: LogWindow is null, cannot show console");
                        }
                    }, System.Windows.Threading.DispatcherPriority.Normal);
                }
                catch (Exception ex)
                {
                    LauncherLogger.Error($"Program: error showing console from IPC request: {ex.Message}");
                    LauncherLogger.Error($"Program: stack trace: {ex.StackTrace}");
                }
            };
            LauncherLogger.Info("Program: OnShowConsole event handler registered");
            
            // Step 7: Initialize tray icon (70%)
            UpdateSplashStatus("Setting up tray icon...", 70);
            await Task.Delay(100);
            
            await Application.Current.Dispatcher.InvokeAsync(() =>
            {
                _trayService?.Initialize();
                LauncherLogger.Info("Tray icon initialized");
            });
            
            // Step 8: Start backend (80%)
            UpdateSplashStatus("Starting backend service...", 80);
            await Task.Delay(200);
            
            // StartBackend can be called from any thread, but we'll do it on UI thread for consistency
            await Application.Current.Dispatcher.InvokeAsync(() =>
            {
            LauncherLogger.Info("Starting backend server from InitializeApplicationAsync");
            _backendService.StartBackend();
            });
            
            // Step 9: Wait for backend to start (90%)
            UpdateSplashStatus("Waiting for backend to initialize...", 90);
            
            // Wait for backend to be ready (with timeout)
            var timeout = DateTime.Now.AddSeconds(30);
            while (_backendService.Status != BackendStatus.Running && 
                   _backendService.Status != BackendStatus.Error && 
                   DateTime.Now < timeout)
            {
                await Task.Delay(500);
                var statusText = _backendService.Status switch
                {
                    BackendStatus.Starting => "Starting service...",
                    BackendStatus.Running => "Service ready",
                    BackendStatus.Error => "Service error",
                    _ => "Initializing service..."
                };
                UpdateSplashStatus(statusText, 90);
            }
            
            // Step 10: Complete (100%)
            UpdateSplashStatus("Ready!", 100);
            await Task.Delay(300);
            
            // Close splash screen (must be on UI thread)
            await Application.Current.Dispatcher.InvokeAsync(() =>
            {
                _splashWindow?.Close();
                _splashWindow = null;
            });
            
            LauncherLogger.Info($"InitializeApplicationAsync: completed with backend status = {_backendService.Status}");
        }

        private void UpdateSplashStatus(string status, int progress)
        {
            // Use BeginInvoke for non-blocking UI updates
            Application.Current.Dispatcher.BeginInvoke(new Action(() =>
            {
                _splashWindow?.UpdateStatus(status, progress);
            }), DispatcherPriority.Background);
        }

        private void OnBackendStatusChanged(object? sender, BackendStatus status)
        {
            // Auto-start frontend when backend is ready
            if (status == BackendStatus.Running && _frontendService != null && _frontendService.AutoStartEnabled)
            {
                // Wait a bit to ensure backend is fully ready
                System.Threading.Tasks.Task.Delay(2000).ContinueWith(_ =>
                {
                    // Check frontend_type from config
                    var frontendType = ConfigService.GetFrontendType();
                    LauncherLogger.Info($"OnBackendStatusChanged: frontend_type = {frontendType}");
                    
                    if (frontendType == "web")
                    {
                        // Web version: open browser instead of starting desktop frontend
                        LauncherLogger.Info("OnBackendStatusChanged: Opening browser for web version");
                        try
                        {
                            var startInfo = new ProcessStartInfo
                            {
                                FileName = "http://localhost:8800",
                                UseShellExecute = true
                            };
                            Process.Start(startInfo);
                            LauncherLogger.Info("OnBackendStatusChanged: Browser opened successfully");
                        }
                        catch (Exception ex)
                        {
                            LauncherLogger.Error($"OnBackendStatusChanged: Failed to open browser: {ex.Message}");
                        }
                    }
                    else if (_frontendService != null && !_frontendService.IsRunning)
                    {
                        // Desktop version: start desktop frontend
                        Application.Current.Dispatcher.Invoke(() =>
                        {
                            _frontendService.StartFrontend();
                        });
                    }
                });
            }
        }

        private void OnFrontendStateChanged(object? sender, bool isRunning)
        {
            // Show first launch notification when frontend starts for the first time
            if (isRunning && !_hasShownFirstLaunchNotification && _frontendService != null)
            {
                _hasShownFirstLaunchNotification = true;
                
                // Show notification window on UI thread
                Application.Current.Dispatcher.Invoke(() =>
                {
                    ShowFirstLaunchNotification();
                });
            }
        }

        private void ShowFirstLaunchNotification()
        {
            try
            {
                // Check if this is the first launch (check for a flag file or registry entry)
                bool isFirstLaunch = IsFirstLaunch();
                
                if (isFirstLaunch)
                {
                    _firstLaunchNotification = new FirstLaunchNotificationWindow();
                    _firstLaunchNotification.Show();
                    
                    // Mark that we've shown the notification
                    MarkFirstLaunchComplete();
                }
            }
            catch (Exception ex)
            {
                // Log error but don't crash
                System.Diagnostics.Debug.WriteLine($"Error showing first launch notification: {ex.Message}");
            }
        }

        private bool IsFirstLaunch()
        {
            try
            {
                // Check for a flag file in the public Owlangs directory
                var publicDir = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.CommonApplicationData), "Owlangs");
                var flagFile = Path.Combine(publicDir, ".first_launch_complete");
                
                // If the flag file doesn't exist, it's the first launch
                return !File.Exists(flagFile);
            }
            catch
            {
                // If we can't check, assume it's not the first launch to avoid annoying users
                return false;
            }
        }

        private void MarkFirstLaunchComplete()
        {
            try
            {
                // Create a flag file to mark that first launch notification has been shown
                var publicDir = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.CommonApplicationData), "Owlangs");
                Directory.CreateDirectory(publicDir);
                var flagFile = Path.Combine(publicDir, ".first_launch_complete");
                File.WriteAllText(flagFile, DateTime.Now.ToString("yyyy-MM-dd HH:mm:ss"));
            }
            catch
            {
                // Ignore errors when creating flag file
            }
        }

        private void OnExit()
        {
            // Request global shutdown first - this signals all threads to exit
            ApplicationShutdownToken.RequestShutdown();
            
            // Stop all services before shutting down (synchronously wait for backend to stop completely)
            // User has clicked Exit, so blocking is acceptable to ensure clean shutdown
            try
            {
                LauncherLogger.Info("OnExit: user requested exit from tray");
                LauncherLogger.Info($"OnExit: initial frontend IsRunning = {_frontendService?.IsRunning}, backend IsRunning = {_backendService?.IsRunning}");
                
                // Stop frontend first (it depends on backend)
                if (_frontendService != null && _frontendService.IsRunning)
                {
                    LauncherLogger.Info("OnExit: stopping frontend");
                    _frontendService.StopFrontend();
                    // Wait for frontend to stop (max 5 seconds)
                    var frontendStopTimeout = DateTime.Now.AddSeconds(5);
                    while (_frontendService.IsRunning && DateTime.Now < frontendStopTimeout)
                    {
                        System.Threading.Thread.Sleep(100);
                        Application.Current.Dispatcher.Invoke(() => { }, System.Windows.Threading.DispatcherPriority.Background);
                    }
                    if (_frontendService.IsRunning)
                    {
                        System.Diagnostics.Debug.WriteLine("[WARNING] Frontend did not stop within timeout");
                        LauncherLogger.Warn("OnExit: frontend did not stop within timeout");
                    }
                }
                
                // Stop backend (must complete before Launcher exits)
                if (_backendService != null && _backendService.IsRunning)
                {
                    LauncherLogger.Info("OnExit: stopping backend");
                    // Use synchronous stop method to avoid Task.Run scheduling delays
                    // OnExit is already on a background thread, so blocking is acceptable
                    try
                    {
                        _backendService.StopBackendSync();
                        LauncherLogger.Info("OnExit: backend stop completed");
                        LauncherLogger.Info($"OnExit: backend Status after stop = {_backendService.Status}");
                    }
                    catch (Exception ex)
                    {
                        System.Diagnostics.Debug.WriteLine($"[WARNING] Error stopping backend: {ex.Message}");
                        LauncherLogger.Warn($"OnExit: error stopping backend: {ex.Message}");
                    }
                    
                    // Quick verification: if IsRunning flag is still true, log a warning
                    // (StopBackendSync already handles killing processes, so this is just for debugging)
                    if (_backendService.IsRunning)
                    {
                        LauncherLogger.Warn("OnExit: backend IsRunning flag still true after StopBackendSync (may be stale flag)");
                    }
                }
                
                if (_exitRequestListener != null)
                {
                    LauncherLogger.Info("OnExit: stopping exit request listener");
                    _exitRequestListener.Stop();
                }

                // Stop IPC service and wait for it to fully stop
                if (_ipcService != null)
                {
                    LauncherLogger.Info("OnExit: stopping IPC service");
                    _ipcService.Stop();
                    // Wait a bit to ensure IPC service tasks are stopped
                    System.Threading.Thread.Sleep(300);
                    LauncherLogger.Info("OnExit: IPC service stopped");
                }
                
                // Stop all timers
                LauncherLogger.Info("OnExit: stopping all timers");
                if (_logWindow != null)
                {
                    Application.Current.Dispatcher.Invoke(() =>
                    {
                        try
                        {
                            // Stop status update timer
                            var statusTimerField = typeof(LogWindow).GetField("_statusUpdateTimer", 
                                System.Reflection.BindingFlags.NonPublic | System.Reflection.BindingFlags.Instance);
                            if (statusTimerField?.GetValue(_logWindow) is System.Windows.Threading.DispatcherTimer timer)
                            {
                                timer?.Stop();
                                LauncherLogger.Info("OnExit: LogWindow status timer stopped");
                            }
                        }
                        catch (Exception ex)
                        {
                            LauncherLogger.Warn($"OnExit: error stopping LogWindow timer: {ex.Message}");
                        }
                    }, System.Windows.Threading.DispatcherPriority.Normal);
                }
                
                // Stop Redis if it's still running
                if (_redisService != null && _redisService.IsRunning())
                {
                    _redisService.StopRedis();
                    // Wait a bit for Redis to stop (max 3 seconds)
                    var redisStopTimeout = DateTime.Now.AddSeconds(3);
                    while (_redisService.IsRunning() && DateTime.Now < redisStopTimeout)
                    {
                        System.Threading.Thread.Sleep(100);
                        Application.Current.Dispatcher.Invoke(() => { }, System.Windows.Threading.DispatcherPriority.Background);
                    }
                    LauncherLogger.Info("OnExit: Redis stop requested/completed");
                }
            }
            catch (Exception ex)
            {
                // Log error but continue with shutdown
                System.Diagnostics.Debug.WriteLine($"Error during shutdown: {ex.Message}");
                LauncherLogger.Error($"OnExit: error during shutdown: {ex.Message}");
            }
            finally
            {
                // Final cleanup: check and kill all remaining Owlangs processes (frontend and backend)
                LauncherLogger.Info("OnExit: performing final cleanup - checking for all Owlangs processes");
                try
                {
                    var currentProcessId = Process.GetCurrentProcess().Id;
                    var allProcesses = Process.GetProcesses();
                    var allOwlangsProcesses = allProcesses
                        .Where(p => p.ProcessName.StartsWith("Owlangs", StringComparison.OrdinalIgnoreCase) &&
                                    !p.HasExited)
                        .ToList();
                    
                    // Filter: exclude Launcher itself
                    var processesToKill = allOwlangsProcesses
                        .Where(p => p.Id != currentProcessId &&
                                    !p.ProcessName.Equals("OwlangsLauncher", StringComparison.OrdinalIgnoreCase))
                        .ToList();
                    
                    if (processesToKill.Count > 0)
                    {
                        LauncherLogger.Warn($"OnExit: found {processesToKill.Count} Owlangs process(es) still running: {string.Join(", ", processesToKill.Select(p => $"{p.ProcessName}({p.Id})"))}");
                        
                        foreach (var proc in processesToKill)
                        {
                            try
                            {
                                LauncherLogger.Info($"OnExit: killing process {proc.ProcessName} (PID: {proc.Id})");
                                proc.Kill();
                                if (!proc.WaitForExit(3000))
                                {
                                    LauncherLogger.Warn($"OnExit: process {proc.Id} did not exit within 3 seconds, forcing kill");
                                    try
                                    {
                                        var verify = Process.GetProcessById(proc.Id);
                                        if (verify != null && !verify.HasExited)
                                        {
                                            verify.Kill();
                                            verify.WaitForExit(2000);
                                        }
                                        verify?.Dispose();
                                    }
                                    catch (ArgumentException)
                                    {
                                        // Process already gone
                                    }
                                }
                            }
                            catch (Exception ex)
                            {
                                LauncherLogger.Warn($"OnExit: failed to kill process {proc.Id}: {ex.Message}");
                            }
                            finally
                            {
                                proc?.Dispose();
                            }
                        }
                        
                        // Wait a bit to ensure processes are terminated
                        System.Threading.Thread.Sleep(500);
                    }
                    
                    // Dispose all processes
                    foreach (var p in allProcesses)
                    {
                        p?.Dispose();
                    }
                }
                catch (Exception ex)
                {
                    LauncherLogger.Warn($"OnExit: error during final process cleanup: {ex.Message}");
                }
                
                // Wait a bit more to ensure all background tasks are stopped
                LauncherLogger.Info("OnExit: waiting for background tasks to complete");
                System.Threading.Thread.Sleep(500);
                
                // Shutdown application
                LauncherLogger.Info("OnExit: calling Application.Shutdown() on UI thread");
                
                // Use Dispatcher.Invoke with timeout to avoid deadlock (StatusChanged no longer blocks during shutdown)
                const int shutdownInvokeTimeoutMs = 5000;
                try
                {
                    Application.Current.Dispatcher.Invoke(
                        (Action)(() =>
                        {
                            try
                            {
                                Shutdown();
                                LauncherLogger.Info("OnExit: Shutdown() called successfully");
                            }
                            catch (Exception ex)
                            {
                                LauncherLogger.Error($"OnExit: error calling Shutdown(): {ex.Message}");
                                LauncherLogger.Error($"OnExit: stack trace: {ex.StackTrace}");
                                Environment.Exit(0);
                            }
                        }),
                        System.Windows.Threading.DispatcherPriority.Normal,
                        TimeSpan.FromMilliseconds(shutdownInvokeTimeoutMs));
                }
                catch (TimeoutException)
                {
                    LauncherLogger.Error("OnExit: Dispatcher.Invoke timed out waiting for UI thread - forcing exit");
                    Environment.Exit(0);
                }
                catch (Exception ex)
                {
                    LauncherLogger.Error($"OnExit: error invoking Shutdown on dispatcher: {ex.Message}");
                    Environment.Exit(0);
                }
                
                // If process still running after Shutdown(), force exit after a short delay
                System.Threading.Thread.Sleep(1500);
                try
                {
                    var launcherProcess = Process.GetCurrentProcess();
                    if (launcherProcess != null && !launcherProcess.HasExited)
                    {
                        LauncherLogger.Warn("OnExit: Launcher process still running after Shutdown(), forcing exit");
                        Environment.Exit(0);
                    }
                    else
                    {
                        LauncherLogger.Info("OnExit: Launcher process exited successfully");
                    }
                }
                catch (Exception ex)
                {
                    LauncherLogger.Error($"OnExit: error checking process status: {ex.Message}");
                    Environment.Exit(0);
                }
            }
        }
        
        private static void ShowConsoleInExistingInstance()
        {
            try
            {
                LauncherLogger.Info("ShowConsoleInExistingInstance: connecting to existing instance via named pipe");
                using (var pipeClient = new System.IO.Pipes.NamedPipeClientStream(
                    ".", "OwlangsLauncher", System.IO.Pipes.PipeDirection.InOut))
                {
                    LauncherLogger.Info("ShowConsoleInExistingInstance: attempting to connect (timeout: 2000ms)");
                    pipeClient.Connect(2000); // 2 second timeout
                    LauncherLogger.Info("ShowConsoleInExistingInstance: connected successfully");
                    
                    var request = new
                    {
                        action = "show_console"
                    };
                    
                    var requestJson = System.Text.Json.JsonSerializer.Serialize(request);
                    var requestBytes = System.Text.Encoding.UTF8.GetBytes(requestJson);
                    LauncherLogger.Info($"ShowConsoleInExistingInstance: sending request: {requestJson}");
                    
                    pipeClient.Write(requestBytes, 0, requestBytes.Length);
                    pipeClient.Flush();
                    LauncherLogger.Info("ShowConsoleInExistingInstance: request sent successfully");
                    
                    // Read response (optional)
                    var buffer = new byte[512];
                    var bytesRead = pipeClient.Read(buffer, 0, buffer.Length);
                    if (bytesRead > 0)
                    {
                        var response = System.Text.Encoding.UTF8.GetString(buffer, 0, bytesRead);
                        LauncherLogger.Info($"ShowConsoleInExistingInstance: received response: {response}");
                        System.Diagnostics.Debug.WriteLine($"Response from existing instance: {response}");
                    }
                    else
                    {
                        LauncherLogger.Warn("ShowConsoleInExistingInstance: no response received from existing instance");
                    }
                }
            }
            catch (TimeoutException ex)
            {
                LauncherLogger.Error($"ShowConsoleInExistingInstance: timeout connecting to existing instance: {ex.Message}");
                System.Diagnostics.Debug.WriteLine("Timeout connecting to existing instance");
            }
            catch (System.IO.IOException ex)
            {
                LauncherLogger.Error($"ShowConsoleInExistingInstance: IO error connecting to existing instance: {ex.Message}");
                System.Diagnostics.Debug.WriteLine($"IO error communicating with existing instance: {ex.Message}");
            }
            catch (Exception ex)
            {
                LauncherLogger.Error($"ShowConsoleInExistingInstance: error communicating with existing instance: {ex.Message}");
                LauncherLogger.Error($"ShowConsoleInExistingInstance: stack trace: {ex.StackTrace}");
                System.Diagnostics.Debug.WriteLine($"Error communicating with existing instance: {ex.Message}");
            }
        }
        
        protected override void OnExit(ExitEventArgs e)
        {
            // Final cleanup (services should already be stopped by OnExit())
            // But we'll ensure everything is cleaned up just in case
            try
            {
                LauncherLogger.Info("OnExit (override): final cleanup");
                
                // Stop IPC service again to ensure it's fully stopped
                _ipcService?.Stop();
                System.Threading.Thread.Sleep(200);
                
                // Force stop if still running
                if (_frontendService != null && _frontendService.IsRunning)
                {
                    LauncherLogger.Warn("OnExit (override): frontend still running, forcing stop");
                    _frontendService.StopFrontend();
                }
                
                if (_backendService != null && _backendService.IsRunning)
                {
                    LauncherLogger.Warn("OnExit (override): backend still running, forcing stop");
                    _backendService.StopBackend();
                }
                
                // Stop Redis if it's still running
                if (_redisService != null && _redisService.IsRunning())
                {
                    _redisService.StopRedis();
                }
                
                // Stop all timers
                if (_logWindow != null)
                {
                    try
                    {
                        var statusTimerField = typeof(LogWindow).GetField("_statusUpdateTimer", 
                            System.Reflection.BindingFlags.NonPublic | System.Reflection.BindingFlags.Instance);
                        if (statusTimerField?.GetValue(_logWindow) is System.Windows.Threading.DispatcherTimer timer)
                        {
                            timer?.Stop();
                        }
                    }
                    catch { }
                }
                
                _trayService?.Dispose();
                _logWindow?.Close();
                
                // Release mutex (only if we own it)
                try
                {
                    if (_instanceMutex != null)
                    {
                        _instanceMutex.ReleaseMutex();
                        _instanceMutex.Dispose();
                    }
                }
                catch (Exception ex)
                {
                    LauncherLogger.Warn($"OnExit (override): error releasing mutex: {ex.Message}");
                }
                _instanceMutex = null;
                
                LauncherLogger.Info("OnExit (override): cleanup completed, calling base.OnExit");
            }
            catch (Exception ex)
            {
                LauncherLogger.Error($"OnExit (override): error during cleanup: {ex.Message}");
                LauncherLogger.Error($"OnExit (override): stack trace: {ex.StackTrace}");
            }
            
            base.OnExit(e);
            
            // Force exit if process is still running after base.OnExit
            try
            {
                System.Threading.Thread.Sleep(500);
                var currentProcess = Process.GetCurrentProcess();
                if (currentProcess != null && !currentProcess.HasExited)
                {
                    LauncherLogger.Warn("OnExit (override): process still running after base.OnExit, forcing exit");
                    Environment.Exit(0);
                }
                else
                {
                    LauncherLogger.Info("OnExit (override): process exited successfully");
                }
            }
            catch (Exception ex)
            {
                LauncherLogger.Error($"OnExit (override): error checking process: {ex.Message}");
                // Last resort: force exit
                Environment.Exit(0);
            }
        }
    }
}

