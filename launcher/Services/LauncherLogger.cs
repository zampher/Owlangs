using System;
using System.IO;

namespace OwlangsLauncher.Services
{
    /// <summary>
    /// Simple file logger for the Launcher itself.
    /// Logs to the unified logs directory used by backend/frontend:
    /// C:\Users\Public\Owlangs\logs\launcher.log
    /// </summary>
    public static class LauncherLogger
    {
        private static readonly object _lock = new object();
        private static readonly string _logFilePath;

        static LauncherLogger()
        {
            try
            {
                // Backend uses C:\Users\Public\Owlangs\logs by default on Windows
                // (see backend.utils.path_utils.get_logs_dir). Use the same location here.
                // Direct path: C:\Users\Public\Owlangs\logs\launcher.log
                var publicOwlangsDir = Path.Combine(
                    Environment.GetFolderPath(Environment.SpecialFolder.UserProfile),
                    "..",
                    "Public",
                    "Owlangs");
                // Normalize path to resolve ".." segments
                publicOwlangsDir = Path.GetFullPath(publicOwlangsDir);
                var logsDir = Path.Combine(publicOwlangsDir, "logs");
                Directory.CreateDirectory(logsDir);
                _logFilePath = Path.Combine(logsDir, "launcher.log");
            }
            catch
            {
                // Fallback: use temp directory if anything goes wrong
                var tempDir = Path.GetTempPath();
                _logFilePath = Path.Combine(tempDir, "OwlangsLauncher.log");
            }
        }

        public static void Info(string message) => Log("INFO", message);

        public static void Warn(string message) => Log("WARN", message);

        public static void Error(string message) => Log("ERROR", message);

        public static void Log(string level, string message)
        {
            try
            {
                var line = $"{DateTime.Now:yyyy-MM-dd HH:mm:ss} [{level}] {message}";
                lock (_lock)
                {
                    File.AppendAllText(_logFilePath, line + Environment.NewLine);
                }
            }
            catch
            {
                // Never throw from logger
            }
        }
    }
}

