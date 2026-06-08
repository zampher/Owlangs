using System;
using System.Diagnostics;
using System.IO;
using System.Windows;
using Hardcodet.Wpf.TaskbarNotification;
using System.Windows.Controls;

namespace OwlangsLauncher.Services
{
    public class TrayService : IDisposable
    {
        private TaskbarIcon? _taskbarIcon;
        private readonly BackendService _backendService;
        private readonly FrontendService? _frontendService;
        private readonly IpcService _ipcService;

        public event Action? OnShowLogs;
        public event Action? OnExit;

        public TrayService(BackendService backendService, FrontendService? frontendService, IpcService ipcService)
        {
            _backendService = backendService;
            _frontendService = frontendService;
            _ipcService = ipcService;
            
            _backendService.StatusChanged += OnBackendStatusChanged;
            if (_frontendService != null)
            {
                _frontendService.RunningStateChanged += OnFrontendStateChanged;
            }
        }

        public void Initialize()
        {
            System.Drawing.Icon? icon = null;
            try
            {
                var iconPath = Path.Combine(AppDomain.CurrentDomain.BaseDirectory, "Resources", "icon.ico");
                if (File.Exists(iconPath))
                {
                    // Load an icon size that matches the current DPI so the tray icon looks crisp
                    // and not scaled-down from the 256x256 frame.
                    int desiredSize;
                    try
                    {
                        using var g = System.Drawing.Graphics.FromHwnd(System.IntPtr.Zero);
                        float dpiX = g.DpiX;
                        int scaled = (int)Math.Round(16 * dpiX / 96.0);
                        if (scaled <= 16) desiredSize = 16;
                        else if (scaled <= 24) desiredSize = 24;
                        else if (scaled <= 32) desiredSize = 32;
                        else desiredSize = 48;
                    }
                    catch
                    {
                        desiredSize = 32;
                    }
                    icon = new System.Drawing.Icon(iconPath, new System.Drawing.Size(desiredSize, desiredSize));
                }
            }
            catch
            {
                // Use default icon if custom icon fails to load
            }

            _taskbarIcon = new TaskbarIcon
            {
                Icon = icon,
                ToolTipText = "Owlangs Launcher",
                Visibility = Visibility.Visible
            };
            
            // Handle double-click on tray icon to show console panel
            _taskbarIcon.TrayMouseDoubleClick += (sender, e) =>
            {
                LauncherLogger.Info("TrayService: tray icon double-clicked, requesting to show console");
                System.Diagnostics.Debug.WriteLine("Tray icon double-clicked, showing console");
                OnShowLogs?.Invoke();
            };

            // Create context menu
            var contextMenu = new ContextMenu();
            
            var statusItem = new MenuItem { Header = "Status: Starting..." };
            contextMenu.Items.Add(statusItem);
            
            contextMenu.Items.Add(new Separator());
            
            var showLogsItem = new MenuItem 
            { 
                Header = "Show Logs",
                Command = new RelayCommand(() => OnShowLogs?.Invoke())
            };
            contextMenu.Items.Add(showLogsItem);
            
            var restartBackendItem = new MenuItem 
            { 
                Header = "Restart Backend",
                Command = new RelayCommand(() => 
                {
                    // Stop backend asynchronously, then start after delay
                    _backendService.StopBackend();
                    System.Threading.Tasks.Task.Delay(2000).ContinueWith(_ =>
                    {
                        _backendService.StartBackend();
                    });
                })
            };
            contextMenu.Items.Add(restartBackendItem);
            
            var browserItem = new MenuItem
            {
                Header = "Browser",
                Items =
                {
                    new MenuItem
                    {
                        Header = "Open",
                        Command = new RelayCommand(() =>
                        {
                            try
                            {
                                Process.Start(new ProcessStartInfo("http://localhost:8800") { UseShellExecute = true });
                            }
                            catch (Exception ex)
                            {
                                System.Windows.MessageBox.Show($"Failed to open browser: {ex.Message}",
                                    "Error", System.Windows.MessageBoxButton.OK, System.Windows.MessageBoxImage.Error);
                            }
                        })
                    }
                }
            };
            contextMenu.Items.Add(browserItem);

            // Frontend menu items
            if (_frontendService != null)
            {
                var startFrontendItem = new MenuItem
                {
                    Header = "Start App",
                    Command = new RelayCommand(() =>
                    {
                        try
                        {
                            _frontendService.StartFrontend();
                        }
                        catch (Exception ex)
                        {
                            System.Windows.MessageBox.Show($"Failed to start frontend: {ex.Message}",
                                "Error", System.Windows.MessageBoxButton.OK, System.Windows.MessageBoxImage.Error);
                        }
                    })
                };
                contextMenu.Items.Add(startFrontendItem);

                var stopFrontendItem = new MenuItem
                {
                    Header = "Stop App",
                    Command = new RelayCommand(() =>
                    {
                        try
                        {
                            // Show confirmation dialog
                            var result = System.Windows.MessageBox.Show(
                                "Closing the app will cause data loss. Are you sure you want to close?",
                                "Confirm Close",
                                System.Windows.MessageBoxButton.YesNo,
                                System.Windows.MessageBoxImage.Warning,
                                System.Windows.MessageBoxResult.No);

                            if (result != System.Windows.MessageBoxResult.Yes)
                            {
                                return; // User cancelled
                            }

                            _frontendService.StopFrontend();
                        }
                        catch (Exception ex)
                        {
                            System.Windows.MessageBox.Show($"Failed to stop frontend: {ex.Message}",
                                "Error", System.Windows.MessageBoxButton.OK, System.Windows.MessageBoxImage.Error);
                        }
                    })
                };
                contextMenu.Items.Add(stopFrontendItem);
            }
            
            contextMenu.Items.Add(new Separator());
            
            var exitItem = new MenuItem 
            { 
                Header = "Exit",
                Command = new RelayCommand(() => OnExit?.Invoke())
            };
            contextMenu.Items.Add(exitItem);
            
            _taskbarIcon.ContextMenu = contextMenu;
            
            // Update status menu item when status changes
            UpdateStatusMenuItem(statusItem);
        }

        private void OnBackendStatusChanged(object? sender, BackendStatus status)
        {
            Application.Current.Dispatcher.Invoke(() =>
            {
                UpdateStatusDisplay(status);
            });
        }

        private void OnFrontendStateChanged(object? sender, bool isRunning)
        {
            Application.Current.Dispatcher.Invoke(() =>
            {
                UpdateStatusDisplay(_backendService.Status);
            });
        }

        private void UpdateStatusDisplay(BackendStatus backendStatus)
        {
            var frontendStatus = _frontendService?.IsRunning == true ? " (Frontend: Running)" : " (Frontend: Stopped)";
            var statusText = GetStatusText(backendStatus) + frontendStatus;
            
            if (_taskbarIcon?.ContextMenu?.Items[0] is MenuItem statusItem)
            {
                statusItem.Header = $"Status: {statusText}";
            }
            
            // Update tooltip
            if (_taskbarIcon != null)
            {
                _taskbarIcon.ToolTipText = $"Owlangs Launcher - {statusText}";
            }
        }

        private string GetStatusText(BackendStatus status)
        {
            return status switch
            {
                BackendStatus.Stopped => "Stopped",
                BackendStatus.Starting => "Starting...",
                BackendStatus.Running => "Running",
                BackendStatus.Unhealthy => "Unhealthy",
                BackendStatus.Stopping => "Stopping...",
                BackendStatus.Error => "Error",
                _ => "Unknown"
            };
        }

        private void UpdateStatusMenuItem(MenuItem statusItem)
        {
            _backendService.StatusChanged += (s, status) =>
            {
                Application.Current.Dispatcher.Invoke(() =>
                {
                    UpdateStatusDisplay(status);
                });
            };
        }

        public void Dispose()
        {
            _taskbarIcon?.Dispose();
            _backendService.StatusChanged -= OnBackendStatusChanged;
            if (_frontendService != null)
            {
                _frontendService.RunningStateChanged -= OnFrontendStateChanged;
            }
        }
    }

    public class RelayCommand : System.Windows.Input.ICommand
    {
        private readonly Action _execute;

        public RelayCommand(Action execute)
        {
            _execute = execute;
        }

        // Required by ICommand interface, but not used in this implementation
        #pragma warning disable CS0067
        public event EventHandler? CanExecuteChanged;
        #pragma warning restore CS0067

        public bool CanExecute(object? parameter) => true;

        public void Execute(object? parameter)
        {
            _execute();
        }
    }
}

