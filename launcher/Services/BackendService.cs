using System;
using System.Diagnostics;
using System.IO;
using System.Linq;
using System.Net.Http;
using System.Threading;
using System.Threading.Tasks;
using System.Text.RegularExpressions;

namespace OwlangsLauncher.Services
{
    public class BackendService
    {
        private Process? _backendProcess;
        private readonly HttpClient _httpClient;
        private readonly string _backendExePath;
        private readonly string _backendWorkingDir;
        private bool _isRunning = false;
        private CancellationTokenSource? _healthCheckCts;
        private int _retryCount = 0;
        private const int MaxRetries = 3;
        private const int RetryDelaySeconds = 5;

        public event EventHandler<string>? LogReceived;
        public event EventHandler<BackendStatus>? StatusChanged;

        public BackendService()
        {
            // 5s timeout for health check: backend cold start (frozen exe) can take several seconds
            _httpClient = new HttpClient { Timeout = TimeSpan.FromSeconds(5) };
            
            // Get installation directory
            var appDir = AppDomain.CurrentDomain.BaseDirectory;
            var installDir = GetInstallDirectory(appDir);
            
            // Backend executable path (relative to launcher)
            // Find backend exe in bin: Owlangs-*-win.exe (unified) or Owlangs_full-*-win.exe (legacy)
            var binDir = Path.Combine(installDir, "bin");
            _backendWorkingDir = binDir;
            
            // Find backend executable dynamically (fixed name, no version, for simpler version updates)
            _backendExePath = FindBackendExecutable(binDir) ?? Path.Combine(binDir, "Owlangs-win.exe");

            LauncherLogger.Info($"BackendService: installDir={installDir}, binDir={binDir}, backendExePath={_backendExePath}");
        }

        private static string GetInstallDirectory(string appDir)
        {
            if (string.IsNullOrEmpty(appDir))
            {
                return appDir;
            }

            try
            {
                // BaseDirectory for the launcher points to "<installDir>\launcher\".
                // We need to go one level up to reach the actual installation root.
                var trimmed = appDir.TrimEnd(Path.DirectorySeparatorChar, Path.AltDirectorySeparatorChar);
                var parent = Directory.GetParent(trimmed);
                if (parent == null || !Directory.Exists(parent.FullName))
                {
                    return appDir;
                }

                var binDirUnderParent = Path.Combine(parent.FullName, "bin");
                // Standard layout: install root has both "bin" and "launcher"; backend exe lives in bin.
                if (Directory.Exists(binDirUnderParent))
                {
                    // Prefer returning parent when we look like we're inside "launcher" (typical install)
                    var dirName = Path.GetFileName(trimmed);
                    if (string.Equals(dirName, "launcher", StringComparison.OrdinalIgnoreCase))
                    {
                        return parent.FullName;
                    }
                    // Also accept if backend exe is present in parent\bin (any layout)
                    var standard = Directory.GetFiles(binDirUnderParent, "Owlangs-*-win.exe");
                    var full = Directory.GetFiles(binDirUnderParent, "Owlangs_full-*-win.exe");
                    if (standard.Length > 0 || full.Length > 0)
                    {
                        return parent.FullName;
                    }
                }
            }
            catch
            {
                // Ignore and fall back to appDir
            }

            return appDir;
        }

        private string? FindBackendExecutable(string binDir)
        {
            if (!Directory.Exists(binDir))
            {
                return null;
            }

            // Prefer unified name Owlangs-*-win.exe, then legacy Owlangs_full-*-win.exe
            var standard = Directory.GetFiles(binDir, "Owlangs-*-win.exe");
            if (standard.Length > 0)
            {
                return standard.OrderByDescending(f => Path.GetFileName(f)).First();
            }
            var full = Directory.GetFiles(binDir, "Owlangs_full-*-win.exe");
            if (full.Length > 0)
            {
                return full.OrderByDescending(f => Path.GetFileName(f)).First();
            }
            return null;
        }

        public BackendStatus Status { get; private set; } = BackendStatus.Stopped;

        public bool IsRunning => _isRunning && _backendProcess != null && !_backendProcess.HasExited;

        public void StartBackend()
        {
            if (IsRunning)
            {
                Log("Backend is already running");
                return;
            }

            // Before starting, check for and stop any existing backend process (e.g. from a previous
            // Launcher run or orphaned backend). We can only kill processes owned by the same user.
            if (TryKillExistingBackendProcesses())
            {
                Log("[INFO] Stopped existing backend process(es). Waiting for port to be released...");
                Thread.Sleep(500);
            }

            try
            {
                Log($"Starting backend server: {_backendExePath}");
                UpdateStatus(BackendStatus.Starting);

                var startInfo = new ProcessStartInfo
                {
                    FileName = _backendExePath,
                    Arguments = "-i --no-browser",
                    WorkingDirectory = _backendWorkingDir,
                    UseShellExecute = false,
                    RedirectStandardOutput = true,
                    RedirectStandardError = true,
                    CreateNoWindow = true,
                    WindowStyle = ProcessWindowStyle.Hidden
                };
                
                // Disable Redis for desktop version (use in-memory session storage)
                // This reduces resource usage, simplifies deployment, and speeds up startup
                startInfo.EnvironmentVariables["REDIS_ENABLED"] = "false";

                _backendProcess = new Process
                {
                    StartInfo = startInfo,
                    EnableRaisingEvents = true
                };

                _backendProcess.OutputDataReceived += (sender, e) =>
                {
                    if (!string.IsNullOrEmpty(e.Data))
                    {
                        // Backend logs already contain timestamp and log level, pass through as-is
                        LogRaw(e.Data);
                        
                        // Check for backend startup success indicators
                        var data = e.Data.Trim();
                        if (data.Contains("Uvicorn running on", StringComparison.OrdinalIgnoreCase) ||
                            data.Contains("Application startup complete", StringComparison.OrdinalIgnoreCase) ||
                            data.Contains("Started server process", StringComparison.OrdinalIgnoreCase))
                        {
                            // Backend is ready, trigger immediate health check
                            Log("[INFO] Detected backend startup success indicator, checking health...");
                            _ = Task.Run(async () =>
                            {
                                // Wait a bit longer to ensure server is fully ready (especially after "Application startup complete")
                                await Task.Delay(1000);
                                if (IsRunning && (Status == BackendStatus.Starting || Status == BackendStatus.Unhealthy))
                                {
                                    Log("[INFO] Performing health check...");
                                    var isHealthy = await CheckHealthAsync();
                                    if (isHealthy)
                                    {
                                        Log("[INFO] Health check passed, updating status to Running");
                                        UpdateStatus(BackendStatus.Running);
                                    }
                                    else
                                    {
                                        Log("[WARNING] Health check failed, backend may not be fully ready yet");
                                    }
                                }
                            });
                        }
                    }
                };

                _backendProcess.ErrorDataReceived += (sender, e) =>
                {
                    if (!string.IsNullOrEmpty(e.Data))
                    {
                        // Python libraries (like uvicorn) output logs to stderr by convention
                        var data = e.Data.Trim();
                        
                        // Check for backend startup success indicators in stderr logs
                        // Note: Logs may contain ANSI escape codes, so we check for the key phrases
                        if (data.Contains("Uvicorn running on", StringComparison.OrdinalIgnoreCase) ||
                            data.Contains("Application startup complete", StringComparison.OrdinalIgnoreCase) ||
                            data.Contains("Started server process", StringComparison.OrdinalIgnoreCase))
                        {
                            // Backend is ready, trigger immediate health check
                            Log("[INFO] Detected backend startup success indicator, checking health...");
                            _ = Task.Run(async () =>
                            {
                                // Wait a bit longer to ensure server is fully ready (especially after "Application startup complete")
                                await Task.Delay(1000);
                                if (IsRunning && (Status == BackendStatus.Starting || Status == BackendStatus.Unhealthy))
                                {
                                    Log("[INFO] Performing health check...");
                                    var isHealthy = await CheckHealthAsync();
                                    if (isHealthy)
                                    {
                                        Log("[INFO] Health check passed, updating status to Running");
                                        UpdateStatus(BackendStatus.Running);
                                    }
                                    else
                                    {
                                        Log("[WARNING] Health check failed, backend may not be fully ready yet");
                                    }
                                }
                            });
                        }
                        
                        // Backend logs already contain timestamp and log level, pass through as-is
                        // Check if it's a formatted log message (has timestamp or log level)
                        bool hasLogLevel = data.Contains("[INFO]", StringComparison.OrdinalIgnoreCase) ||
                                         data.Contains("[WARNING]", StringComparison.OrdinalIgnoreCase) ||
                                         data.Contains("[WARN]", StringComparison.OrdinalIgnoreCase) ||
                                         data.Contains("[ERROR]", StringComparison.OrdinalIgnoreCase) ||
                                         data.Contains("[DEBUG]", StringComparison.OrdinalIgnoreCase) ||
                                         data.Contains("[SYS]", StringComparison.OrdinalIgnoreCase) ||
                                         data.Contains("[CRITICAL]", StringComparison.OrdinalIgnoreCase) ||
                                         data.Contains("[TRACE]", StringComparison.OrdinalIgnoreCase) ||
                                         data.Contains("[SUCCESS]", StringComparison.OrdinalIgnoreCase) ||
                                         data.Contains("INFO:", StringComparison.OrdinalIgnoreCase) ||
                                         data.Contains("WARNING:", StringComparison.OrdinalIgnoreCase) ||
                                         data.Contains("ERROR:", StringComparison.OrdinalIgnoreCase);
                        
                        // Check for timestamp patterns (YYYY-MM-DD or YYYY-MM-DD HH:MM:SS)
                        bool hasTimestamp = System.Text.RegularExpressions.Regex.IsMatch(data, @"^\d{4}-\d{2}-\d{2}");
                        
                        // If it has a log level or timestamp, it's a formatted log message from backend - use as-is
                        if (hasLogLevel || hasTimestamp)
                        {
                            LogRaw(data);
                        }
                        else
                        {
                            // No log level prefix or timestamp, this might be a raw message
                            // Add Launcher's own prefix for unformatted messages
                            Log($"[INFO] {data}");
                        }
                    }
                };

                _backendProcess.Exited += (sender, e) =>
                {
                    _isRunning = false;
                    Log("Backend process exited");
                    UpdateStatus(BackendStatus.Stopped);
                    
                    // Stop health check loop
                    try
                    {
                        _healthCheckCts?.Cancel();
                        // Wait a bit for health check loop to exit
                        System.Threading.Thread.Sleep(100);
                        _healthCheckCts?.Dispose();
                        _healthCheckCts = null;
                    }
                    catch (Exception ex)
                    {
                        LauncherLogger.Warn($"BackendService: error stopping health check on process exit: {ex.Message}");
                    }
                };

                _backendProcess.Start();
                _backendProcess.BeginOutputReadLine();
                _backendProcess.BeginErrorReadLine();
                
                _isRunning = true;
                _retryCount = 0; // Reset retry count on successful start
                Log("Backend process started");

                // Start health check immediately (don't wait for first delay)
                _healthCheckCts = new CancellationTokenSource();
                _ = Task.Run(() => HealthCheckLoop(_healthCheckCts.Token));
                
                // Also check for startup success indicators in logs
                // This provides faster status update when backend is ready
                _ = Task.Run(async () =>
                {
                    try
                    {
                        // Wait a bit for backend to initialize
                        await Task.Delay(3000);
                        
                        // Check shutdown token before doing work
                        ApplicationShutdownToken.ThrowIfShutdownRequested();
                        
                        // Check if backend is healthy
                        if (IsRunning && Status == BackendStatus.Starting && !ApplicationShutdownToken.IsShutdownRequested)
                        {
                            var isHealthy = await CheckHealthAsync();
                            if (isHealthy && !ApplicationShutdownToken.IsShutdownRequested)
                            {
                                UpdateStatus(BackendStatus.Running);
                            }
                        }
                    }
                    catch (OperationCanceledException)
                    {
                        // Shutdown requested, exit silently
                        LauncherLogger.Info("BackendService: startup check task cancelled due to shutdown");
                    }
                });
            }
            catch (Exception ex)
            {
                Log($"[ERROR] Failed to start backend: {ex.Message}");
                UpdateStatus(BackendStatus.Error);
                
                // Auto-retry if enabled
                if (_retryCount < MaxRetries && !ApplicationShutdownToken.IsShutdownRequested)
                {
                    _retryCount++;
                    Log($"[INFO] Retrying backend start ({_retryCount}/{MaxRetries}) in {RetryDelaySeconds} seconds...");
                    _ = Task.Run(async () =>
                    {
                        try
                        {
                            await Task.Delay(RetryDelaySeconds * 1000);
                            
                            // Check shutdown token before retrying
                            ApplicationShutdownToken.ThrowIfShutdownRequested();
                            
                            if (Status == BackendStatus.Error && !ApplicationShutdownToken.IsShutdownRequested)
                            {
                                StartBackend();
                            }
                        }
                        catch (OperationCanceledException)
                        {
                            // Shutdown requested, exit silently
                            LauncherLogger.Info("BackendService: retry task cancelled due to shutdown");
                        }
                    });
                }
                else
                {
                    Log($"[ERROR] Backend failed to start after {MaxRetries} attempts. Please check logs and configuration.");
                }
            }
        }

        public Task StopBackend()
        {
            if (!IsRunning)
            {
                LauncherLogger.Info("BackendService.StopBackend: backend not running, returning immediately");
                return Task.CompletedTask;
            }

            LauncherLogger.Info($"BackendService.StopBackend: creating stop task (IsRunning={IsRunning}, _backendProcess={_backendProcess != null}, HasExited={_backendProcess?.HasExited})");
            // Run stop operation asynchronously to avoid blocking UI thread
            // Use Task.Run with TaskCreationOptions.LongRunning to ensure it gets scheduled immediately
            var task = Task.Run(() =>
            {
                LauncherLogger.Info("BackendService.StopBackend: Task.Run callback executing, calling StopBackendAsync");
                StopBackendAsync();
            }, CancellationToken.None);
            
            // Don't wait here - let caller wait if needed
            return task;
        }
        
        /// <summary>
        /// Synchronously stop the backend process. Use this when you're already on a background thread
        /// and need immediate execution without Task.Run scheduling delays.
        /// </summary>
        public void StopBackendSync()
        {
            if (!IsRunning)
            {
                LauncherLogger.Info("BackendService.StopBackendSync: backend not running");
                return;
            }
            
            LauncherLogger.Info($"BackendService.StopBackendSync: calling StopBackendAsync directly (no Task.Run delay)");
            StopBackendAsync();
        }

        private void StopBackendAsync()
        {
            try
            {
                Log("Stopping backend...");
                LauncherLogger.Info("BackendService.StopBackendAsync: begin");
                UpdateStatus(BackendStatus.Stopping);

                if (_backendProcess == null)
                {
                    LauncherLogger.Warn("BackendService.StopBackendAsync: _backendProcess is null");
                    _isRunning = false;
                    UpdateStatus(BackendStatus.Stopped);
                    return;
                }

                if (_backendProcess.HasExited)
                {
                    LauncherLogger.Info($"BackendService.StopBackendAsync: process already exited (PID: {_backendProcess.Id})");
                    _backendProcess.Dispose();
                    _backendProcess = null;
                    _isRunning = false;
                    UpdateStatus(BackendStatus.Stopped);
                    Log("Backend stopped (already exited)");
                    LauncherLogger.Info("BackendService.StopBackendAsync: completed (process already exited)");
                    return;
                }

                var processId = _backendProcess.Id;
                var processName = _backendProcess.ProcessName;
                Log($"[INFO] Stopping backend process: {processName} (PID: {processId})");
                LauncherLogger.Info($"BackendService.StopBackendAsync: stopping process {processName} (PID: {processId})");
                
                try
                {
                    // Try to kill the process
                    LauncherLogger.Info($"BackendService.StopBackendAsync: calling Kill() on process {processId}");
                    _backendProcess.Kill();
                    
                    // Wait for process to exit (max 5 seconds)
                    LauncherLogger.Info($"BackendService.StopBackendAsync: waiting for process {processId} to exit (max 5 seconds)");
                    if (!_backendProcess.WaitForExit(5000))
                    {
                        // Process didn't exit, try to force kill again
                        Log("[WARNING] Backend process did not exit within 5 seconds, forcing termination...");
                        LauncherLogger.Warn($"BackendService.StopBackendAsync: process {processId} did not exit within 5 seconds, forcing kill");
                        try
                        {
                            if (!_backendProcess.HasExited)
                            {
                                LauncherLogger.Info($"BackendService.StopBackendAsync: second Kill() attempt on process {processId}");
                                _backendProcess.Kill();
                                LauncherLogger.Info($"BackendService.StopBackendAsync: waiting additional 3 seconds for process {processId}");
                                _backendProcess.WaitForExit(3000);
                            }
                        }
                        catch (Exception killEx)
                        {
                            Log($"[WARNING] Error during force kill: {killEx.Message}");
                            LauncherLogger.Warn($"BackendService.StopBackendAsync: error during force kill: {killEx.Message}");
                        }
                    }
                    
                    // Verify process actually exited - use GetProcessById to double-check
                    bool processReallyGone = _backendProcess.HasExited;
                    if (processReallyGone)
                    {
                        // HasExited is true, but verify with GetProcessById to be sure
                        try
                        {
                            var verifyProc = System.Diagnostics.Process.GetProcessById(processId);
                            if (verifyProc != null && !verifyProc.HasExited)
                            {
                                // Process still exists despite HasExited=true, kill it again
                                LauncherLogger.Warn($"BackendService.StopBackendAsync: process {processId} still exists (HasExited mismatch), killing again");
                                verifyProc.Kill();
                                verifyProc.WaitForExit(3000);
                                processReallyGone = verifyProc.HasExited;
                            }
                            verifyProc?.Dispose();
                        }
                        catch (ArgumentException)
                        {
                            // Process doesn't exist - confirmed gone
                            processReallyGone = true;
                        }
                    }
                    
                    if (processReallyGone)
                    {
                        Log($"[INFO] Backend process {processId} exited successfully");
                        LauncherLogger.Info($"BackendService.StopBackendAsync: process {processId} confirmed terminated");
                    }
                    else
                    {
                        // Process still running, try alternative kill method
                        Log("[WARNING] Backend process still running after Kill(), attempting alternative method...");
                        LauncherLogger.Warn($"BackendService.StopBackendAsync: process {processId} still running, trying GetProcessById kill");
                        try
                        {
                            var proc = System.Diagnostics.Process.GetProcessById(processId);
                            if (proc != null && !proc.HasExited)
                            {
                                proc.Kill();
                                proc.WaitForExit(2000);
                                LauncherLogger.Info($"BackendService.StopBackendAsync: process {processId} killed via GetProcessById");
                            }
                            proc?.Dispose();
                        }
                        catch (Exception procEx)
                        {
                            LauncherLogger.Warn($"BackendService.StopBackendAsync: failed to kill process {processId}: {procEx.Message}");
                        }
                    }
                    
                    // Check for any remaining Owlangs backend processes (excluding Launcher itself)
                    KillRemainingOwlangsProcesses(processId);
                }
                catch (Exception ex)
                {
                    Log($"[WARNING] Error during process termination: {ex.Message}");
                    LauncherLogger.Warn($"BackendService.StopBackendAsync: error during process termination: {ex.Message}");
                    // Force kill as fallback
                    try
                    {
                        if (_backendProcess != null && !_backendProcess.HasExited)
                        {
                            LauncherLogger.Info($"BackendService.StopBackendAsync: fallback kill attempt on process {_backendProcess.Id}");
                            _backendProcess.Kill();
                            _backendProcess.WaitForExit(2000);
                        }
                    }
                    catch (Exception killEx)
                    {
                        Log($"[WARNING] Fallback kill also failed: {killEx.Message}");
                        LauncherLogger.Warn($"BackendService.StopBackendAsync: fallback kill failed: {killEx.Message}");
                    }
                }

                // Stop health check loop
                LauncherLogger.Info("BackendService.StopBackendAsync: stopping health check loop");
                _healthCheckCts?.Cancel();
                // Wait a bit for health check loop to exit
                System.Threading.Thread.Sleep(200);
                _healthCheckCts?.Dispose();
                _healthCheckCts = null;
                
                // Clean up process reference
                LauncherLogger.Info($"BackendService.StopBackendAsync: disposing process reference (HasExited={_backendProcess?.HasExited})");
                try
                {
                    _backendProcess?.Dispose();
                }
                catch (Exception disposeEx)
                {
                    LauncherLogger.Warn($"BackendService.StopBackendAsync: dispose error: {disposeEx.Message}");
                }
                _backendProcess = null;
                _isRunning = false;
                UpdateStatus(BackendStatus.Stopped);
                Log("Backend stopped");
                LauncherLogger.Info("BackendService.StopBackendAsync: completed successfully (Status=Stopped)");
            }
            catch (Exception ex)
            {
                Log($"[ERROR] Failed to stop backend: {ex.Message}");
                LauncherLogger.Error($"BackendService.StopBackendAsync: exception: {ex.Message}");
                LauncherLogger.Error($"BackendService.StopBackendAsync: stack trace: {ex.StackTrace}");
                // Ensure state is updated even on error
                _isRunning = false;
                UpdateStatus(BackendStatus.Stopped);
                
                // Last resort: try to find and kill any Owlangs backend processes
                try
                {
                    Log("[INFO] Attempting to find and kill any remaining Owlangs backend processes...");
                    LauncherLogger.Info("BackendService.StopBackendAsync: attempting last resort - finding all Owlangs processes");
                    KillRemainingOwlangsProcesses(-1); // -1 means we don't know the main process ID
                }
                catch (Exception findEx)
                {
                    Log($"[WARNING] Error finding backend processes: {findEx.Message}");
                    LauncherLogger.Warn($"BackendService.StopBackendAsync: error finding processes: {findEx.Message}");
                }
            }
        }
        
        /// <summary>
        /// Before starting the backend, find and kill any existing Owlangs backend process (e.g. orphaned or from a previous run).
        /// Only processes owned by the current user can be killed; others are skipped with a log message.
        /// </summary>
        /// <returns>True if at least one process was killed.</returns>
        private bool TryKillExistingBackendProcesses()
        {
            var killedAny = false;
            Process[]? allProcesses = null;
            try
            {
                var currentProcessId = Process.GetCurrentProcess().Id;
                allProcesses = Process.GetProcesses();
                // Backend exe names are like Owlangs-1.0.0.0-win or Owlangs_full-*-win; process name is without .exe.
                // Exclude Launcher (OwlangsLauncher) and current process.
                var candidates = allProcesses
                    .Where(p => !p.HasExited &&
                                p.ProcessName.StartsWith("Owlangs", StringComparison.OrdinalIgnoreCase) &&
                                !string.Equals(p.ProcessName, "OwlangsLauncher", StringComparison.OrdinalIgnoreCase) &&
                                p.Id != currentProcessId)
                    .ToList();

                if (candidates.Count == 0)
                {
                    return false;
                }

                LauncherLogger.Info($"BackendService: found {candidates.Count} existing backend process(es): {string.Join(", ", candidates.Select(p => $"{p.ProcessName}(PID {p.Id})"))}");
                Log($"[INFO] Found {candidates.Count} existing backend process(es), stopping before start...");

                foreach (var proc in candidates)
                {
                    try
                    {
                        proc.Kill();
                        if (!proc.WaitForExit(2000))
                        {
                            LauncherLogger.Warn($"BackendService: process {proc.Id} did not exit within 2 seconds");
                        }
                        else
                        {
                            killedAny = true;
                        }
                    }
                    catch (System.ComponentModel.Win32Exception ex)
                    {
                        LauncherLogger.Warn($"BackendService: cannot stop process {proc.Id} (no permission or already exited): {ex.Message}");
                        Log($"[WARNING] Could not stop process PID {proc.Id}: {ex.Message}");
                    }
                    catch (UnauthorizedAccessException ex)
                    {
                        LauncherLogger.Warn($"BackendService: no permission to stop process {proc.Id}: {ex.Message}");
                        Log($"[WARNING] No permission to stop process PID {proc.Id}. Start may fail if port 8800 is in use.");
                    }
                    finally
                    {
                        proc?.Dispose();
                    }
                }
            }
            catch (Exception ex)
            {
                LauncherLogger.Warn($"BackendService: error checking/killing existing backend: {ex.Message}");
            }
            finally
            {
                if (allProcesses != null)
                {
                    foreach (var p in allProcesses)
                    {
                        p?.Dispose();
                    }
                }
            }

            return killedAny;
        }

        /// <summary>
        /// Helper method to find and kill any remaining Owlangs backend processes (excluding Launcher itself).
        /// </summary>
        private void KillRemainingOwlangsProcesses(int excludeProcessId)
        {
            try
            {
                var currentProcessId = System.Diagnostics.Process.GetCurrentProcess().Id;
                var allProcesses = System.Diagnostics.Process.GetProcesses();
                var allOwlangsProcesses = allProcesses
                    .Where(p => p.ProcessName.StartsWith("Owlangs", StringComparison.OrdinalIgnoreCase) &&
                                !p.HasExited)
                    .ToList();
                
                // Filter: exclude Launcher itself and optionally the main backend process
                var backendProcesses = allOwlangsProcesses
                    .Where(p => p.Id != currentProcessId && // Exclude Launcher itself
                                (excludeProcessId < 0 || p.Id != excludeProcessId) && // Exclude main backend if specified
                                !p.ProcessName.Equals("OwlangsLauncher", StringComparison.OrdinalIgnoreCase)) // Also exclude by name
                    .ToList();
                
                if (backendProcesses.Count > 0)
                {
                    LauncherLogger.Warn($"BackendService: found {backendProcesses.Count} remaining Owlangs backend process(es): {string.Join(", ", backendProcesses.Select(p => $"{p.ProcessName}({p.Id})"))}");
                    foreach (var proc in backendProcesses)
                    {
                        try
                        {
                            LauncherLogger.Info($"BackendService: killing process {proc.ProcessName} (PID: {proc.Id})");
                            proc.Kill();
                            if (!proc.WaitForExit(2000))
                            {
                                LauncherLogger.Warn($"BackendService: process {proc.Id} did not exit within 2 seconds");
                            }
                            
                            // Verify it's gone
                            try
                            {
                                var verify = System.Diagnostics.Process.GetProcessById(proc.Id);
                                if (verify != null && !verify.HasExited)
                                {
                                    verify.Kill();
                                    verify.WaitForExit(2000);
                                }
                                verify?.Dispose();
                            }
                            catch (ArgumentException)
                            {
                                // Process gone - good
                            }
                        }
                        catch (Exception ex)
                        {
                            LauncherLogger.Warn($"BackendService: failed to kill process {proc.Id}: {ex.Message}");
                        }
                        finally
                        {
                            proc?.Dispose();
                        }
                    }
                }
                
                // Dispose all processes
                foreach (var p in allProcesses)
                {
                    p?.Dispose();
                }
            }
            catch (Exception ex)
            {
                LauncherLogger.Warn($"BackendService: error finding/killing remaining processes: {ex.Message}");
            }
        }

        private async Task HealthCheckLoop(CancellationToken cancellationToken)
        {
            // First check immediately (no delay) to catch backend startup quickly
            bool firstCheck = true;
            
            while (!cancellationToken.IsCancellationRequested && 
                   !ApplicationShutdownToken.IsShutdownRequested && 
                   IsRunning)
            {
                try
                {
                    // Check shutdown token before doing work
                    ApplicationShutdownToken.ThrowIfShutdownRequested();
                    
                    if (!firstCheck)
                    {
                        await Task.Delay(2000, cancellationToken); // Check every 2 seconds after first check
                    }
                    firstCheck = false;
                    
                    var isHealthy = await CheckHealthAsync();
                    if (isHealthy)
                    {
                        // Update to Running if currently Starting or Unhealthy
                        if (Status == BackendStatus.Starting || Status == BackendStatus.Unhealthy)
                        {
                            UpdateStatus(BackendStatus.Running);
                            Log("[INFO] Backend is now running and healthy");
                        }
                        // Keep Running status if already Running
                    }
                    else
                    {
                        // Only update to Unhealthy if currently Running (don't override Starting)
                        if (Status == BackendStatus.Running)
                        {
                            UpdateStatus(BackendStatus.Unhealthy);
                            Log("[WARNING] Backend health check failed. Backend may be unresponsive.");
                        }
                        // If Starting, don't change status yet (backend may still be initializing)
                    }
                }
                catch (OperationCanceledException)
                {
                    break;
                }
                catch (Exception ex)
                {
                    Log($"[WARNING] Health check error: {ex.Message}");
                }
            }
        }

        private async Task<bool> CheckHealthAsync()
        {
            try
            {
                // Try to connect to backend health endpoint
                var response = await _httpClient.GetAsync("http://localhost:8800/api/health", CancellationToken.None);
                var isHealthy = response.IsSuccessStatusCode;
                
                // Log health check result for debugging (only if unhealthy to avoid spam)
                if (!isHealthy)
                {
                    Log($"[WARNING] Health check returned status code: {response.StatusCode}");
                }
                
                return isHealthy;
            }
            catch (Exception ex)
            {
                // Log connection errors for debugging
                Log($"[WARNING] Health check connection error: {ex.Message}");
                return false;
            }
        }

        private void UpdateStatus(BackendStatus newStatus)
        {
            if (Status != newStatus)
            {
                Status = newStatus;
                // During shutdown, do not raise StatusChanged to avoid blocking OnExit thread
                // (handlers use Dispatcher.Invoke and can deadlock if UI thread is blocked)
                if (!ApplicationShutdownToken.IsShutdownRequested)
                {
                    StatusChanged?.Invoke(this, newStatus);
                }
            }
        }

        private void Log(string message)
        {
            // During shutdown, do not invoke LogReceived to avoid blocking OnExit thread
            // (LogWindow.OnLogReceived uses Dispatcher.Invoke and can deadlock)
            if (ApplicationShutdownToken.IsShutdownRequested)
                return;
            // Add timestamp for Launcher's own log messages
            var timestamp = DateTime.Now.ToString("yyyy-MM-dd HH:mm:ss");
            LogReceived?.Invoke(this, $"[{timestamp}] {message}");
        }

        private void LogRaw(string message)
        {
            // During shutdown, do not invoke LogReceived to avoid blocking OnExit thread
            if (ApplicationShutdownToken.IsShutdownRequested)
                return;
            // Pass through backend logs as-is (they already contain timestamp and log level)
            LogReceived?.Invoke(this, message);
        }

        public void Dispose()
        {
            StopBackend();
            _httpClient?.Dispose();
            _healthCheckCts?.Dispose();
        }
    }

    public enum BackendStatus
    {
        Stopped,
        Starting,
        Running,
        Unhealthy,
        Stopping,
        Error
    }
}

