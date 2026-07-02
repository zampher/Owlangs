using System;
using System.IO;
using System.Text.Json;
using Microsoft.Win32;

namespace OwlangsLauncher.Services
{
    /// <summary>
    /// Service for reading Launcher and Backend configuration.
    /// Launcher settings → launcher_config.json
    /// Backend settings (theme, frontend_type) → app_config.json
    /// Both stored in %ProgramData%\Owlangs\configs\.
    /// </summary>
    public class ConfigService
    {
        private static string? _configDir;
        private static string? _launcherConfigPath;
        private static JsonDocument? _launcherConfigCache;

        private const string LauncherConfigFile = "launcher_config.json";
        private const string AppConfigFile = "app_config.json";

        /// <summary>
        /// Get the configs directory.
        /// Priority: OWLANGS_CONFIG_PATH env var → %ProgramData%\Owlangs\configs\
        /// </summary>
        private static string GetConfigDir()
        {
            if (_configDir != null)
                return _configDir;

            var envDir = Environment.GetEnvironmentVariable("OWLANGS_CONFIG_PATH");
            if (!string.IsNullOrEmpty(envDir))
            {
                _configDir = Path.Combine(envDir, "configs");
                return _configDir;
            }

            var programData = Environment.GetFolderPath(Environment.SpecialFolder.CommonApplicationData);
            _configDir = Path.Combine(programData, "Owlangs", "configs");
            return _configDir;
        }

        // ── Launcher config (launcher_config.json) ──

        private static string GetLauncherConfigPath()
        {
            if (_launcherConfigPath != null)
                return _launcherConfigPath;
            _launcherConfigPath = Path.Combine(GetConfigDir(), LauncherConfigFile);
            return _launcherConfigPath;
        }

        private static JsonDocument? LoadLauncherConfig()
        {
            if (_launcherConfigCache != null)
                return _launcherConfigCache;

            try
            {
                EnsureLauncherConfigFile();
                var path = GetLauncherConfigPath();
                if (!File.Exists(path))
                {
                    LauncherLogger.Info($"ConfigService: {LauncherConfigFile} not found at {path}, using defaults");
                    return null;
                }

                var jsonText = File.ReadAllText(path);
                _launcherConfigCache = JsonDocument.Parse(jsonText);
                LauncherLogger.Info($"ConfigService: Loaded launcher config from {path}");
                return _launcherConfigCache;
            }
            catch (Exception ex)
            {
                LauncherLogger.Error($"ConfigService: Failed to load {LauncherConfigFile}: {ex.Message}");
                return null;
            }
        }

        /// <summary>
        /// Create launcher_config.json from launcher_config.json.template on first run.
        /// </summary>
        private static void EnsureLauncherConfigFile()
        {
            var configPath = GetLauncherConfigPath();
            if (File.Exists(configPath))
                return;

            var templatePath = Path.Combine(GetConfigDir(), "launcher_config.json.template");
            try
            {
                var configDir = GetConfigDir();
                if (!Directory.Exists(configDir))
                {
                    Directory.CreateDirectory(configDir);
                }

                if (File.Exists(templatePath))
                {
                    File.Copy(templatePath, configPath);
                    LauncherLogger.Info(
                        $"ConfigService: Created {LauncherConfigFile} from template at {templatePath}");
                    return;
                }

                const string defaultJson = """
                    {
                      "_schema_version": 1,
                      "launcher_auto_start_backend": true,
                      "launcher_auto_start_frontend": true,
                      "launcher_auto_open_browser": false
                    }
                    """;
                File.WriteAllText(configPath, defaultJson);
                LauncherLogger.Info(
                    $"ConfigService: Created {LauncherConfigFile} with built-in defaults at {configPath}");
            }
            catch (Exception ex)
            {
                LauncherLogger.Error(
                    $"ConfigService: Failed to create {LauncherConfigFile} from template: {ex.Message}");
            }
        }

        // ── App config (app_config.json, read-only from launcher) ──

        private static string GetAppConfigPath()
        {
            return Path.Combine(GetConfigDir(), AppConfigFile);
        }

        private static JsonDocument? LoadAppConfig()
        {
            try
            {
                var path = GetAppConfigPath();
                if (!File.Exists(path))
                {
                    LauncherLogger.Info($"ConfigService: {AppConfigFile} not found at {path}, using defaults");
                    return null;
                }

                var jsonText = File.ReadAllText(path);
                return JsonDocument.Parse(jsonText);
            }
            catch (Exception ex)
            {
                LauncherLogger.Error($"ConfigService: Failed to load {AppConfigFile}: {ex.Message}");
                return null;
            }
        }

        /// <summary>
        /// Get theme setting from backend's app_config.json ("light", "dark", or "auto")
        /// Returns "auto" if not found or on error.
        /// </summary>
        public static string GetTheme()
        {
            try
            {
                var config = LoadAppConfig();
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
        /// Determine if dark theme should be used based on theme setting.
        /// "dark" -> true, "light" -> false, "auto" -> use system preference.
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
                using (var key = Microsoft.Win32.Registry.CurrentUser.OpenSubKey(
                    @"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize"))
                {
                    if (key != null)
                    {
                        var appsUseLightTheme = key.GetValue("AppsUseLightTheme");
                        if (appsUseLightTheme is int value)
                        {
                            return value == 0; // 0 = dark, 1 = light
                        }
                    }
                }
            }
            catch (Exception ex)
            {
                LauncherLogger.Warn($"ConfigService: Could not detect system theme: {ex.Message}, defaulting to light");
            }

            return false;
        }

        // ── Launcher auto-start settings (launcher_config.json) ──

        public static bool GetAutoStartBackend()
        {
            return GetBooleanConfig("launcher_auto_start_backend", defaultValue: true);
        }

        public static bool GetAutoStartFrontend()
        {
            return GetBooleanConfig("launcher_auto_start_frontend", defaultValue: true);
        }

        public static bool GetAutoOpenBrowser()
        {
            return GetBooleanConfig("launcher_auto_open_browser", defaultValue: true);
        }

        /// <summary>
        /// Set a launcher boolean config value and persist to launcher_config.json.
        /// </summary>
        public static void SetBooleanConfig(string key, bool value)
        {
            try
            {
                var configPath = GetLauncherConfigPath();
                var jsonText = "{}";
                if (File.Exists(configPath))
                {
                    jsonText = File.ReadAllText(configPath);
                }

                using var doc = JsonDocument.Parse(jsonText);
                var root = doc.RootElement;

                using var stream = new MemoryStream();
                using var writer = new Utf8JsonWriter(stream, new JsonWriterOptions { Indented = true });
                writer.WriteStartObject();

                bool keyWritten = false;
                foreach (var prop in root.EnumerateObject())
                {
                    if (prop.Name == key)
                    {
                        writer.WriteBoolean(key, value);
                        keyWritten = true;
                    }
                    else
                    {
                        prop.WriteTo(writer);
                    }
                }
                if (!keyWritten)
                {
                    writer.WriteBoolean(key, value);
                }

                writer.WriteEndObject();
                writer.Flush();

                var dir = Path.GetDirectoryName(configPath);
                if (dir != null && !Directory.Exists(dir))
                {
                    Directory.CreateDirectory(dir);
                }

                File.WriteAllText(configPath, System.Text.Encoding.UTF8.GetString(stream.ToArray()));
                LauncherLogger.Info($"ConfigService: Set {key}={value} in {configPath}");

                ClearCache();
            }
            catch (Exception ex)
            {
                LauncherLogger.Error($"ConfigService: Failed to set {key}: {ex.Message}");
            }
        }

        private static bool GetBooleanConfig(string key, bool defaultValue)
        {
            try
            {
                var config = LoadLauncherConfig();
                if (config == null)
                    return defaultValue;

                if (config.RootElement.TryGetProperty(key, out var prop)
                    && (prop.ValueKind == System.Text.Json.JsonValueKind.True
                        || prop.ValueKind == System.Text.Json.JsonValueKind.False))
                {
                    return prop.GetBoolean();
                }
            }
            catch (Exception ex)
            {
                LauncherLogger.Error($"ConfigService: Error reading {key}: {ex.Message}");
            }
            return defaultValue;
        }

        public static void ClearCache()
        {
            _launcherConfigCache?.Dispose();
            _launcherConfigCache = null;
        }

        // ── Frontend type (from backend's app_config.json) ──

        /// <summary>
        /// Get frontend type. Auto-detects based on available frontend files:
        /// - Desktop exe exists → "both" (web is always available via backend)
        /// - Desktop exe absent → "web"
        /// The app_config.json value overrides auto-detection when no desktop exe is found.
        /// </summary>
        public static string GetFrontendType()
        {
            var appDir = AppDomain.CurrentDomain.BaseDirectory;
            var installDir = GetInstallDirectory(appDir);
            var frontendExePath = Path.Combine(installDir, "frontend", "owlangs.exe");
            bool hasDesktopExe = File.Exists(frontendExePath);

            if (hasDesktopExe)
            {
                // Desktop exe exists → this package has both desktop and web frontends.
                // Return "both" so the three auto-start checkboxes work independently.
                LauncherLogger.Info($"ConfigService: frontend_type auto-detected 'both' (found {frontendExePath})");
                return "both";
            }

            // No desktop exe: web-only package, or check app_config.json for override
            try
            {
                var config = LoadAppConfig();
                if (config != null)
                {
                    if (config.RootElement.TryGetProperty("frontend_type", out var frontendTypeProperty))
                    {
                        var frontendType = frontendTypeProperty.GetString();
                        if (!string.IsNullOrEmpty(frontendType))
                        {
                            LauncherLogger.Info($"ConfigService: frontend_type={frontendType} (from app_config.json)");
                            return frontendType.ToLower();
                        }
                    }
                }
            }
            catch (Exception ex)
            {
                LauncherLogger.Error($"ConfigService: Error reading frontend_type: {ex.Message}");
            }

            LauncherLogger.Info($"ConfigService: frontend_type defaulting to 'web' ({frontendExePath} not found)");
            return "web";
        }

        /// <summary>
        /// Get the package install directory (used for frontend-type auto-detection).
        /// BaseDirectory for launcher → "<installDir>\launcher\", go up one level.
        /// </summary>
        private static string GetInstallDirectory(string appDir)
        {
            var dir = new DirectoryInfo(appDir);
            var parent = dir.Parent;
            if (parent != null)
            {
                var dirName = dir.Name;
                if (parent.GetDirectories("bin").Length > 0)
                {
                    if (string.Equals(dirName, "launcher", StringComparison.OrdinalIgnoreCase))
                    {
                        return parent.FullName;
                    }
                }
            }
            return appDir;
        }
    }
}
