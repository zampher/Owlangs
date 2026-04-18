using System.Windows;
using OwlangsLauncher.Services;

namespace OwlangsLauncher
{
    public partial class App : Application
    {
        private void App_Startup(object sender, StartupEventArgs e)
        {
            // Apply theme based on config before any windows are created
            ApplyTheme();
        }

        /// <summary>
        /// Apply theme from configs/app_config.json
        /// </summary>
        private void ApplyTheme()
        {
            try
            {
                var useDarkTheme = ConfigService.ShouldUseDarkTheme();
                var themeResource = useDarkTheme 
                    ? "Styles/DarkTheme.xaml" 
                    : "Styles/LightTheme.xaml";

                // Load theme resource dictionary
                var themeDict = new ResourceDictionary
                {
                    Source = new System.Uri(themeResource, System.UriKind.Relative)
                };

                // Insert theme dictionary BEFORE AppStyles so that DynamicResource references in styles can find theme resources
                // Resources.MergedDictionaries is a collection, insert at index 0 to ensure theme loads first
                var mergedDictionaries = Resources.MergedDictionaries;
                mergedDictionaries.Insert(0, themeDict);

                LauncherLogger.Info($"App: Theme applied - {(useDarkTheme ? "Dark" : "Light")}");
            }
            catch (System.Exception ex)
            {
                LauncherLogger.Error($"App: Failed to apply theme: {ex.Message}");
                // Fallback to light theme on error
                try
                {
                    var lightTheme = new ResourceDictionary
                    {
                        Source = new System.Uri("Styles/LightTheme.xaml", System.UriKind.Relative)
                    };
                    Resources.MergedDictionaries.Insert(0, lightTheme);
                }
                catch
                {
                    // If even fallback fails, continue without theme (will use default WPF colors)
                }
            }
        }
    }
}

