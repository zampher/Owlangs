using System;
using System.IO;
using System.Text.Json;
using Microsoft.Win32;

namespace OwlangsLauncher.Services
{
    /// <summary>
    /// Service for reading application configuration from configs/app_config.json
    /// </summary>
    public class ConfigService
    {
        private static string? _configPath;
        private static JsonDocument? _configCache;

        /// <summary>
        /// Get the path to app_config.json
        /// </summary>
        private static string GetConfigPath()
        {
            if (_configPath != null)
                return _configPath;

            // Get installation directory (same logic as BackendService)
            var appDir = AppDomain.CurrentDomain.BaseDirectory;
            var installDir = GetInstallDirectory(appDir);
            _configPath = Path.Combine(installDir, "configs", "app_config.json");
            return _configPath;
        }

        private static string GetInstallDirectory(string appDir)
        {
            // BaseDirectory for the launcher points to "<installDir>\launcher\".
            // We need to go up one level to get the install root.
            var dir = new DirectoryInfo(appDir);
            var parent = dir.Parent;
            if (parent != null)
            {
                var dirName = dir.Name;
                // Standard layout: install root has both "bin" and "launcher"; backend exe lives in bin.
                if (parent.GetDirectories("bin").Length > 0)
                {
                    // Prefer returning parent when we look like we're inside "launcher" (typical install)
                    if (string.Equals(dirName, "launcher", StringComparison.OrdinalIgnoreCase))
                    {
                        return parent.FullName;
                    }
                }
            }
            return appDir;
        }

        /// <summary>
        /// Load configuration from app_config.json
        /// </summary>
        private static JsonDocument? LoadConfig()
        {
            if (_configCache != null)
                return _configCache;

            try
            {
                var configPath = GetConfigPath();
                if (!File.Exists(configPath))
                {
                    LauncherLogger.Warn($"ConfigService: app_config.json not found at {configPath}, using defaults");
                    return null;
                }

                var jsonText = File.ReadAllText(configPath);
                _configCache = JsonDocument.Parse(jsonText);
                return _configCache;
            }
            catch (Exception ex)
            {
                LauncherLogger.Error($"ConfigService: Failed to load app_config.json: {ex.Message}");
                return null;
            }
        }

        /// <summary>
        /// Get theme setting from config ("light", "dark", or "auto")
        /// Returns "auto" if not found or on error
        /// </summary>
        public static string GetTheme()
        {
            try
            {
                var config = LoadConfig();
                if (config == null)
                    return "auto";

                if (config.RootElement.TryGetProperty("theme", out var themeProperty))
                {
                    var theme = themeProperty.GetString();
                    if (!string.IsNullOrEmpty(theme))
                    {
                        return theme.ToLower();
                    }
                }
            }
            catch (Exception ex)
            {
                LauncherLogger.Error($"ConfigService: Error reading theme: {ex.Message}");
            }

            return "auto";
        }

        /// <summary>
        /// Determine if dark theme should be used based on theme setting
        /// "dark" -> true, "light" -> false, "auto" -> use system preference
        /// </summary>
        public static bool ShouldUseDarkTheme()
        {
            var theme = GetTheme();

            if (theme == "dark")
                return true;
            if (theme == "light")
                return false;

            // "auto" - detect system preference
            try
            {
                // Check Windows theme via registry
                using (var key = Microsoft.Win32.Registry.CurrentUser.OpenSubKey(
                    @"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize"))
                {
                    if (key != null)
                    {
                        var appsUseLightTheme = key.GetValue("AppsUseLightTheme");
                        if (appsUseLightTheme is int value)
                        {
                            // 0 = dark theme, 1 = light theme
                            return value == 0;
                        }
                    }
                }
            }
            catch (Exception ex)
            {
                LauncherLogger.Warn($"ConfigService: Could not detect system theme: {ex.Message}, defaulting to light");
            }

            // Default to light theme if detection fails
            return false;
        }

        /// <summary>
        /// Clear config cache (useful for testing or when config changes)
        /// </summary>
        public static void ClearCache()
        {
            _configCache?.Dispose();
            _configCache = null;
        }

        /// <summary>
        /// Get frontend type from config ("desktop", "web", or "both")
        /// If not configured, auto-detects: returns "desktop" when owlangs.exe exists
        /// in the frontend/ directory, otherwise "web".
        /// </summary>
        public static string GetFrontendType()
        {
            try
            {
                var config = LoadConfig();
                if (config != null)
                {
                    if (config.RootElement.TryGetProperty("frontend_type", out var frontendTypeProperty))
                    {
                        var frontendType = frontendTypeProperty.GetString();
                        if (!string.IsNullOrEmpty(frontendType))
                        {
                            LauncherLogger.Info($"ConfigService: frontend_type={frontendType} (from config)");
                            return frontendType.ToLower();
                        }
                    }
                }
            }
            catch (Exception ex)
            {
                LauncherLogger.Error($"ConfigService: Error reading frontend_type: {ex.Message}");
            }

            // Auto-detect: if owlangs.exe exists in <installDir>\frontend\, use "desktop"
            var appDir = AppDomain.CurrentDomain.BaseDirectory;
            var installDir = GetInstallDirectory(appDir);
            var frontendExePath = Path.Combine(installDir, "frontend", "owlangs.exe");
            if (File.Exists(frontendExePath))
            {
                LauncherLogger.Info($"ConfigService: frontend_type not configured, auto-detected 'desktop' (found {frontendExePath})");
                return "desktop";
            }

            LauncherLogger.Info($"ConfigService: frontend_type not configured, defaulting to 'web' ({frontendExePath} not found)");
            return "web";
        }
    }
}
