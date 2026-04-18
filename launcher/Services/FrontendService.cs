using System;
using System.Diagnostics;
using System.IO;
using System.Linq;
using System.Runtime.InteropServices;
using System.Text;
using System.Threading;
using System.Threading.Tasks;

namespace OwlangsLauncher.Services
{
    public class FrontendService
    {
        // Use short (8.3) path when path contains non-ASCII to avoid Flutter/runtime failing under CJK install dirs
        [DllImport("kernel32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
        private static extern uint GetShortPathNameW(
            [In] string lpszLongPath,
            [Out] StringBuilder lpszShortPath,
            [In] uint cchBuffer);

        [DllImport("kernel32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
        private static extern IntPtr FindFirstFileW([In] string lpFileName, out Win32FindDataW lpFindFileData);

        [DllImport("kernel32.dll", SetLastError = true)]
        private static extern bool FindClose(IntPtr hFindFile);

        [StructLayout(LayoutKind.Sequential, CharSet = CharSet.Unicode)]
        private struct Win32FindDataW
        {
            public uint dwFileAttributes;
            public System.Runtime.InteropServices.ComTypes.FILETIME ftCreationTime;
            public System.Runtime.InteropServices.ComTypes.FILETIME ftLastAccessTime;
            public System.Runtime.InteropServices.ComTypes.FILETIME ftLastWriteTime;
            public uint nFileSizeHigh;
            public uint nFileSizeLow;
            public uint dwReserved0;
            public uint dwReserved1;
            [MarshalAs(UnmanagedType.ByValTStr, SizeConst = 260)]
            public string cFileName;
            [MarshalAs(UnmanagedType.ByValTStr, SizeConst = 14)]
            public string cAlternateFileName;
        }

        private Process? _frontendProcess;
        private readonly string _frontendExePath;
        private bool _isRunning = false;
        private bool _autoStartEnabled = true;
        private int _retryCount = 0;
        private const int MaxRetries = 2;
        private StreamWriter? _logFileWriter;
        private readonly string _logFilePath;
        private const int MaxLogFileSizeMB = 10; // Maximum log file size in MB
        private const int MaxLogBackupCount = 7; // Maximum number of backup files

        public event EventHandler<string>? LogReceived;
        public event EventHandler<bool>? RunningStateChanged;

        public FrontendService()
        {
            // Get installation directory (same logic as BackendService)
            var appDir = AppDomain.CurrentDomain.BaseDirectory;
            var installDir = GetInstallDirectory(appDir);
            
            // Flutter Windows executable path (relative to installation root)
            // Try to find owlangs.exe in frontend directory
            var frontendDir = Path.Combine(installDir, "frontend");
            _frontendExePath = FindFrontendExecutable(frontendDir) ?? 
                              Path.Combine(frontendDir, "owlangs.exe");
            
            // Setup log file path (unified with backend: C:\Users\Public\Owlangs\logs\frontend.log)
            // Backend uses C:\Users\Public\Owlangs\logs by default on Windows (see backend.utils.path_utils.get_logs_dir).
            // Use the same directory here so all logs live under a single location.
            // Direct path: C:\Users\Public\Owlangs\logs\frontend.log
            var publicOwlangsDir = Path.Combine(
                Environment.GetFolderPath(Environment.SpecialFolder.UserProfile),
                "..",
                "Public",
                "Owlangs");
            // Normalize path to resolve ".." segments
            publicOwlangsDir = Path.GetFullPath(publicOwlangsDir);
            var logsDir = Path.Combine(publicOwlangsDir, "logs");
            Directory.CreateDirectory(logsDir);
            _logFilePath = Path.Combine(logsDir, "frontend.log");
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
                if (parent != null && Directory.Exists(parent.FullName))
                {
                    // Check if the parent directory contains the 'frontend' folder
                    // This helps confirm it's the actual install root, not just an arbitrary parent
                    if (Directory.Exists(Path.Combine(parent.FullName, "frontend")) || 
                        Directory.Exists(Path.Combine(parent.FullName, "bin")))
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

        private string? FindFrontendExecutable(string frontendDir)
        {
            if (!Directory.Exists(frontendDir))
            {
                return null;
            }

            // First, check for owlangs.exe directly in frontend directory (packaged location)
            var directExePath = Path.Combine(frontendDir, "owlangs.exe");
            if (File.Exists(directExePath))
            {
                return directExePath;
            }

            // Look for owlangs.exe in x64\runner\Release (Flutter Windows build output structure)
            var releaseDirX64 = Path.Combine(frontendDir, "x64", "runner", "Release");
            if (Directory.Exists(releaseDirX64))
            {
                var exePath = Path.Combine(releaseDirX64, "owlangs.exe");
                if (File.Exists(exePath))
                {
                    return exePath;
                }
            }

            // Fallback: Look for owlangs.exe in build/windows/runner/Release (old structure)
            var releaseDir = Path.Combine(frontendDir, "build", "windows", "runner", "Release");
            if (Directory.Exists(releaseDir))
            {
                var exePath = Path.Combine(releaseDir, "owlangs.exe");
                if (File.Exists(exePath))
                {
                    return exePath;
                }
            }

            // Also check for any .exe in the frontend directory
            var exeFiles = Directory.GetFiles(frontendDir, "*.exe", SearchOption.AllDirectories)
                .Where(f => Path.GetFileName(f).ToLower().Contains("owlangs"))
                .ToList();
            
            if (exeFiles.Count > 0)
            {
                return exeFiles.First();
            }

            return null;
        }

        /// <summary>
        /// Returns 8.3 short path for paths containing non-ASCII (e.g. CJK) so child process can start reliably.
        /// Tries GetShortPathNameW first; if it fails or returns path with non-ASCII, uses FindFirstFileW per segment.
        /// </summary>
        private static string ToShortPathIfNeeded(string path)
        {
            if (string.IsNullOrEmpty(path)) return path;
            if (path.All(c => c <= 127)) return path;

            var sb = new StringBuilder(256);
            uint len = GetShortPathNameW(path, sb, (uint)sb.Capacity);
            if (len > sb.Capacity)
            {
                sb.Capacity = (int)len;
                len = GetShortPathNameW(path, sb, len);
            }
            if (len > 0 && len <= 260)
            {
                var result = sb.ToString();
                if (result.All(c => c <= 127)) return result;
            }

            return BuildShortPathViaFindFirst(path);
        }

        /// <summary>
        /// Builds 8.3 short path by walking path segments and using cAlternateFileName when available.
        /// Used when GetShortPathNameW fails or returns a path that still contains non-ASCII.
        /// </summary>
        private static string BuildShortPathViaFindFirst(string path)
        {
            if (string.IsNullOrEmpty(path)) return path;
            var sep = Path.DirectorySeparatorChar;
            var segments = path.Split(sep, Path.AltDirectorySeparatorChar);
            if (segments.Length == 0) return path;

            var currentLong = segments[0];
            var currentShort = segments[0];
            if (segments.Length == 1) return path;

            for (int i = 1; i < segments.Length; i++)
            {
                var segment = segments[i];
                if (string.IsNullOrEmpty(segment)) continue;

                var searchPath = currentLong + sep + segment;
                var handle = FindFirstFileW(searchPath, out var fd);
                if (handle == IntPtr.Zero || handle == new IntPtr(-1))
                {
                    currentLong = searchPath;
                    currentShort = searchPath;
                    continue;
                }
                FindClose(handle);
                var shortName = string.IsNullOrEmpty(fd.cAlternateFileName) ? segment : fd.cAlternateFileName;
                currentShort = currentShort + sep + shortName;
                currentLong = searchPath;
            }
            return currentShort;
        }

        /// <summary>
        /// When 8.3 short path is unavailable (e.g. disabled on volume), create a directory junction
        /// from a safe ASCII path (LocalAppData\Owlangs\FrontendRun) to the frontend dir so we can
        /// launch the exe via the junction and avoid passing CJK path to the child process.
        /// </summary>
        private bool TryCreateJunctionForCjkLaunch(string targetDir, out string? junctionPath)
        {
            junctionPath = null;
            if (string.IsNullOrEmpty(targetDir) || !Directory.Exists(targetDir))
                return false;

            var safeBase = Path.Combine(
                Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
                "Owlangs");
            var junction = Path.Combine(safeBase, "FrontendRun");

            try
            {
                if (!Directory.Exists(safeBase))
                    Directory.CreateDirectory(safeBase);

                if (Directory.Exists(junction))
                {
                    try { Directory.Delete(junction); }
                    catch { return false; }
                }

                var startInfo = new ProcessStartInfo
                {
                    FileName = "cmd.exe",
                    Arguments = $"/c mklink /J \"{junction}\" \"{targetDir}\"",
                    UseShellExecute = false,
                    CreateNoWindow = true,
                    WorkingDirectory = safeBase
                };
                using (var p = Process.Start(startInfo))
                {
                    if (p == null) return false;
                    p.WaitForExit(5000);
                    if (p.ExitCode != 0) return false;
                }

                if (Directory.Exists(junction))
                {
                    junctionPath = junction;
                    return true;
                }
            }
            catch { /* ignore */ }

            return false;
        }

        public bool IsRunning => _isRunning && _frontendProcess != null && !_frontendProcess.HasExited;
        
        public bool AutoStartEnabled
        {
            get => _autoStartEnabled;
            set => _autoStartEnabled = value;
        }

        public void StartFrontend()
        {
            if (IsRunning)
            {
                Log("Frontend is already running");
                return;
            }

            if (string.IsNullOrEmpty(_frontendExePath) || !File.Exists(_frontendExePath))
            {
                Log($"[WARNING] Frontend executable not found: {_frontendExePath}");
                Log("  Frontend will not be started automatically");
                return;
            }

            try
            {
                Log($"Starting frontend: {_frontendExePath}");
                
                // Open log file for writing (append mode)
                try
                {
                    _logFileWriter = new StreamWriter(_logFilePath, append: true, System.Text.Encoding.UTF8)
                    {
                        AutoFlush = true
                    };
                    _logFileWriter.WriteLine($"[{DateTime.Now:yyyy-MM-dd HH:mm:ss}] Frontend process starting...");
                }
                catch (Exception ex)
                {
                    Log($"[WARNING] Failed to open log file: {ex.Message}");
                }

                var workDir = Path.GetDirectoryName(_frontendExePath) ?? "";
                var workDirToUse = ToShortPathIfNeeded(workDir);
                var exePathToStart = Path.Combine(workDirToUse, Path.GetFileName(_frontendExePath));
                if (workDirToUse != workDir)
                {
                    Log($"[INFO] Using short path for launch (CJK-safe): exe={exePathToStart}, workDir={workDirToUse}");
                }
                else if (workDir.Any(c => c > 127))
                {
                    if (TryCreateJunctionForCjkLaunch(workDir, out var junctionPath) && !string.IsNullOrEmpty(junctionPath))
                    {
                        workDirToUse = junctionPath;
                        exePathToStart = Path.Combine(junctionPath, Path.GetFileName(_frontendExePath));
                        Log($"[INFO] Using junction for launch (CJK-safe): exe={exePathToStart}, workDir={workDirToUse}");
                    }
                    else
                    {
                        Log($"[WARNING] Install path contains non-ASCII; short path and junction fallback failed. Frontend may fail (e.g. exit -1073740791). Consider installing to a path without CJK characters.");
                    }
                }

                Log($"[Frontend] Launch: FileName={exePathToStart}, WorkingDirectory={workDirToUse}");

                var startInfo = new ProcessStartInfo
                {
                    FileName = exePathToStart,
                    WorkingDirectory = workDirToUse,
                    UseShellExecute = false, // Must be false to capture output
                    RedirectStandardOutput = true,
                    RedirectStandardError = true,
                    StandardOutputEncoding = Encoding.UTF8,
                    StandardErrorEncoding = Encoding.UTF8,
                    CreateNoWindow = false, // Show window (Flutter will create its own window)
                    WindowStyle = ProcessWindowStyle.Normal
                };

                _frontendProcess = new Process
                {
                    StartInfo = startInfo,
                    EnableRaisingEvents = true
                };

                // Capture stdout (Flutter print statements go here)
                _frontendProcess.OutputDataReceived += (sender, e) =>
                {
                    if (!string.IsNullOrEmpty(e.Data))
                    {
                        var logMessage = $"[{DateTime.Now:yyyy-MM-dd HH:mm:ss}] [Frontend] {e.Data}";
                        Log(logMessage);
                        WriteToLogFile(logMessage);
                    }
                };

                // Capture stderr (Flutter errors go here)
                _frontendProcess.ErrorDataReceived += (sender, e) =>
                {
                    if (!string.IsNullOrEmpty(e.Data))
                    {
                        var logMessage = $"[{DateTime.Now:yyyy-MM-dd HH:mm:ss}] [Frontend] [ERROR] {e.Data}";
                        Log(logMessage);
                        WriteToLogFile(logMessage);
                    }
                };

                _frontendProcess.Exited += (sender, e) =>
                {
                    _isRunning = false;
                    var exitCode = _frontendProcess?.HasExited == true ? _frontendProcess.ExitCode : -1;
                    Log($"Frontend process exited with code {exitCode}");
                    WriteToLogFile($"[{DateTime.Now:yyyy-MM-dd HH:mm:ss}] Frontend process exited with code {exitCode}");
                    if (exitCode != 0)
                    {
                        Log($"[HINT] Non-zero exit often means: missing DLLs, wrong working dir, or install path with non-ASCII (e.g. CJK). Try installing to a path without Chinese/Japanese/Korean characters, or check frontend.log.");
                        WriteToLogFile($"[{DateTime.Now:yyyy-MM-dd HH:mm:ss}] [HINT] Non-zero exit: check install path (CJK), working dir, or dependencies.");
                    }
                    CloseLogFile();
                    RunningStateChanged?.Invoke(this, false);
                };

                _frontendProcess.Start();
                _frontendProcess.BeginOutputReadLine();
                _frontendProcess.BeginErrorReadLine();
                
                _isRunning = true;
                _retryCount = 0; // Reset retry count on successful start
                Log("Frontend process started");
                WriteToLogFile($"[{DateTime.Now:yyyy-MM-dd HH:mm:ss}] Frontend process started successfully");
                RunningStateChanged?.Invoke(this, true);
            }
            catch (Exception ex)
            {
                Log($"[ERROR] Failed to start frontend: {ex.Message}");
                if (ex.InnerException != null)
                    Log($"[ERROR] Inner: {ex.InnerException.Message}");
                WriteToLogFile($"[{DateTime.Now:yyyy-MM-dd HH:mm:ss}] [ERROR] Failed to start frontend: {ex}");
                _isRunning = false;
                RunningStateChanged?.Invoke(this, false);
                
                // Auto-retry if enabled and not manually started
                if (_autoStartEnabled && _retryCount < MaxRetries)
                {
                    _retryCount++;
                    Log($"[INFO] Retrying frontend start ({_retryCount}/{MaxRetries}) in 3 seconds...");
                    System.Threading.Tasks.Task.Delay(3000).ContinueWith(_ =>
                    {
                        if (!_isRunning && _autoStartEnabled)
                        {
                            StartFrontend();
                        }
                    });
                }
                else if (_retryCount >= MaxRetries)
                {
                    Log($"[WARNING] Frontend failed to start after {MaxRetries} attempts. You can manually start it from the tray menu.");
                }
            }
        }

        public void StopFrontend()
        {
            if (!IsRunning)
            {
                return;
            }

            // Run stop operation asynchronously to avoid blocking UI thread
            _ = Task.Run(() => StopFrontendAsync());
        }

        private void StopFrontendAsync()
        {
            try
            {
                Log("Stopping frontend...");
                WriteToLogFile($"[{DateTime.Now:yyyy-MM-dd HH:mm:ss}] Stopping frontend...");

                if (_frontendProcess != null && !_frontendProcess.HasExited)
                {
                    // Try graceful shutdown first
                    try
                    {
                        _frontendProcess.CloseMainWindow();
                        
                        if (!_frontendProcess.WaitForExit(3000))
                        {
                            // Force kill if graceful shutdown failed
                            Log("[WARNING] Frontend process did not exit gracefully, forcing termination...");
                            _frontendProcess.Kill();
                            _frontendProcess.WaitForExit(2000);
                        }
                    }
                    catch (Exception ex)
                    {
                        Log($"[WARNING] Error during graceful shutdown: {ex.Message}");
                        // Force kill as fallback
                        try
                        {
                            if (!_frontendProcess.HasExited)
                            {
                                _frontendProcess.Kill();
                                _frontendProcess.WaitForExit(2000);
                            }
                        }
                        catch
                        {
                            // Ignore errors during force kill
                        }
                    }
                }

                _frontendProcess?.Dispose();
                _frontendProcess = null;
                _isRunning = false;
                Log("Frontend stopped");
                WriteToLogFile($"[{DateTime.Now:yyyy-MM-dd HH:mm:ss}] Frontend stopped");
                CloseLogFile();
                RunningStateChanged?.Invoke(this, false);
            }
            catch (Exception ex)
            {
                Log($"[ERROR] Failed to stop frontend: {ex.Message}");
                WriteToLogFile($"[{DateTime.Now:yyyy-MM-dd HH:mm:ss}] [ERROR] Failed to stop frontend: {ex.Message}");
                // Ensure state is updated even on error
                _isRunning = false;
                RunningStateChanged?.Invoke(this, false);
            }
        }

        private void Log(string message)
        {
            var timestamp = DateTime.Now.ToString("yyyy-MM-dd HH:mm:ss");
            LogReceived?.Invoke(this, $"[{timestamp}] [Frontend] {message}");
        }

        private void WriteToLogFile(string message)
        {
            try
            {
                // Check if log file size exceeds limit before writing
                if (_logFileWriter != null && File.Exists(_logFilePath))
                {
                    var fileInfo = new FileInfo(_logFilePath);
                    long maxSizeBytes = MaxLogFileSizeMB * 1024 * 1024; // Convert MB to bytes
                    
                    if (fileInfo.Length >= maxSizeBytes)
                    {
                        // Rotate log file
                        RotateLogFile();
                    }
                }
                
                _logFileWriter?.WriteLine(message);
            }
            catch
            {
                // Ignore file write errors to avoid affecting main process
            }
        }

        private void RotateLogFile()
        {
            try
            {
                // Close current log file
                _logFileWriter?.Dispose();
                _logFileWriter = null;

                if (!File.Exists(_logFilePath))
                {
                    return;
                }

                // Rotate existing log files
                // frontend.log -> frontend.log.1
                // frontend.log.1 -> frontend.log.2
                // ... up to MaxLogBackupCount
                for (int i = MaxLogBackupCount - 1; i >= 1; i--)
                {
                    string oldFile = $"{_logFilePath}.{i}";
                    string newFile = $"{_logFilePath}.{i + 1}";
                    
                    if (File.Exists(oldFile))
                    {
                        if (i == MaxLogBackupCount - 1)
                        {
                            // Delete oldest backup
                            File.Delete(oldFile);
                        }
                        else
                        {
                            File.Move(oldFile, newFile);
                        }
                    }
                }

                // Move current log file to .1
                string firstBackup = $"{_logFilePath}.1";
                if (File.Exists(firstBackup))
                {
                    File.Delete(firstBackup);
                }
                File.Move(_logFilePath, firstBackup);

                // Create new log file
                _logFileWriter = new StreamWriter(_logFilePath, append: false, System.Text.Encoding.UTF8)
                {
                    AutoFlush = true
                };
                _logFileWriter.WriteLine($"[{DateTime.Now:yyyy-MM-dd HH:mm:ss}] Log file rotated");
            }
            catch (Exception ex)
            {
                // If rotation fails, try to reopen the log file
                try
                {
                    _logFileWriter = new StreamWriter(_logFilePath, append: true, System.Text.Encoding.UTF8)
                    {
                        AutoFlush = true
                    };
                    _logFileWriter.WriteLine($"[{DateTime.Now:yyyy-MM-dd HH:mm:ss}] [WARNING] Log rotation failed: {ex.Message}");
                }
                catch
                {
                    // Ignore errors
                }
            }
        }

        private void CloseLogFile()
        {
            try
            {
                _logFileWriter?.Dispose();
                _logFileWriter = null;
            }
            catch
            {
                // Ignore errors
            }
        }

        public void Dispose()
        {
            StopFrontend();
            CloseLogFile();
        }
    }
}

