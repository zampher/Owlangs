using System;
using System.Diagnostics;
using System.IO;
using System.Text;
using System.Threading.Tasks;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Input;
using System.Windows.Media;
using System.Windows.Media.Animation;
using System.Windows.Threading;
using Microsoft.Win32;
using System.Runtime.InteropServices;
using OwlangsLauncher.Services;

namespace OwlangsLauncher.Views
{
    public partial class LogWindow : Window
    {
        private enum LogLevelFilter
        {
            Error,
            Warning,
            Info
        }

        private readonly BackendService _backendService;
        private readonly FrontendService? _frontendService;
        private readonly RedisService? _redisService;
        private readonly Action? _onRequestExit;
        private DispatcherTimer? _statusUpdateTimer;
        private DispatcherTimer? _logRenderThrottleTimer;
        private bool _logRenderPending;

        // Cap memory and avoid UI freeze: keep last N lines only
        private const int MaxLogLines = 50000;
        // Only render last N lines into TextBox to keep UI responsive
        private const int MaxDisplayLines = 5000;

        // Store all log lines to support filtering
        private readonly System.Collections.Generic.List<string> _logLines = new System.Collections.Generic.List<string>();
        private LogLevelFilter _currentFilter = LogLevelFilter.Info;
        
        // Store original window position and size before animation
        private double _savedLeft = double.NaN;
        private double _savedTop = double.NaN;
        private double _savedWidth = double.NaN;
        private double _savedHeight = double.NaN;

        // For Shift+scrollbar: track last vertical offset to compute line delta
        private double _lastScrollVerticalOffset = double.NaN;
        private const double EstimatedLineHeight = 15.0; // Consolas 11pt approximate

        public LogWindow(BackendService backendService, FrontendService? frontendService = null, RedisService? redisService = null, Action? onRequestExit = null)
        {
            InitializeComponent();
            _backendService = backendService;
            _frontendService = frontendService;
            _redisService = redisService;
            _onRequestExit = onRequestExit;

            // Subscribe to log events
            _backendService.LogReceived += OnLogReceived;
            _backendService.StatusChanged += OnBackendStatusChanged;
            
            if (_frontendService != null)
            {
                _frontendService.LogReceived += OnLogReceived;
                _frontendService.RunningStateChanged += OnFrontendStateChanged;
            }
            
            if (_redisService != null)
            {
                _redisService.LogReceived += OnLogReceived;
            }
            
            // Initialize status display
            InitializeStatusColors();
            UpdateBackendStatus();
            UpdateFrontendStatus();
            UpdateControlButtons();
            
            // Start status update timer (update every second)
            _statusUpdateTimer = new DispatcherTimer
            {
                Interval = TimeSpan.FromSeconds(1)
            };
            _statusUpdateTimer.Tick += (s, e) => 
            {
                UpdateBackendStatus();
                UpdateFrontendStatus();
                UpdateControlButtons();
            };
            _statusUpdateTimer.Start();

            // Throttle log rendering so we do at most one full render every 300ms (avoids main-thread freeze when many lines arrive)
            _logRenderThrottleTimer = new DispatcherTimer
            {
                Interval = TimeSpan.FromMilliseconds(300)
            };
            _logRenderThrottleTimer.Tick += (s, e) =>
            {
                _logRenderThrottleTimer?.Stop();
                _logRenderPending = false;
                ApplyLogFilterAndRender();
            };

            // Shift+MouseWheel extends selection by lines (so user can select a long range by holding Shift and scrolling)
            LogScrollViewer.PreviewMouseWheel += LogScrollViewer_PreviewMouseWheel;
            // Shift+drag scrollbar: extend selection by the number of lines scrolled
            LogScrollViewer.ScrollChanged += LogScrollViewer_ScrollChanged;
            
            // Hide window initially
            Visibility = Visibility.Hidden;

            // When user restores from taskbar (or activates window), bring to foreground
            Activated += LogWindow_Activated;
            IsVisibleChanged += LogWindow_IsVisibleChanged;
        }

        private void LogWindow_Activated(object? sender, EventArgs e)
        {
            BringWindowToForeground();
        }

        private void LogWindow_IsVisibleChanged(object sender, DependencyPropertyChangedEventArgs e)
        {
            // When window becomes visible (e.g. restored from taskbar click), ensure it comes to front
            if (e.NewValue is true)
            {
                Dispatcher.BeginInvoke(new Action(BringWindowToForeground), DispatcherPriority.ApplicationIdle);
            }
        }

        private void BringWindowToForeground()
        {
            if (!IsVisible)
            {
                return;
            }
            try
            {
                var hWnd = new System.Windows.Interop.WindowInteropHelper(this).Handle;
                if (hWnd == IntPtr.Zero)
                {
                    return;
                }
                ShowWindow(hWnd, SW_RESTORE);
                ShowWindow(hWnd, SW_SHOW);
                BringWindowToTop(hWnd);
                SetForegroundWindow(hWnd);
            }
            catch (Exception ex)
            {
                LauncherLogger.Error($"LogWindow.BringWindowToForeground: {ex.Message}");
            }
        }

        /// <summary>
        /// Get 0-based line index from character index (treats \r\n and \n as line break).
        /// </summary>
        private static int GetLineIndexFromCharacterIndex(string text, int charIndex)
        {
            if (string.IsNullOrEmpty(text) || charIndex <= 0)
            {
                return 0;
            }
            int line = 0;
            for (int i = 0; i < charIndex && i < text.Length; i++)
            {
                if (text[i] == '\n')
                {
                    line++;
                }
            }
            return line;
        }

        /// <summary>
        /// Get character index of the start of the given 0-based line (treats \r\n and \n as line break).
        /// </summary>
        private static int GetCharacterIndexFromLineIndex(string text, int lineIndex)
        {
            if (string.IsNullOrEmpty(text) || lineIndex <= 0)
            {
                return 0;
            }
            int currentLine = 0;
            for (int i = 0; i < text.Length; i++)
            {
                if (text[i] == '\n')
                {
                    currentLine++;
                    if (currentLine == lineIndex)
                    {
                        return i + 1; // start of next line after \n
                    }
                }
            }
            return text.Length;
        }

        private void LogScrollViewer_PreviewMouseWheel(object sender, MouseWheelEventArgs e)
        {
            if (LogTextBox == null)
            {
                return;
            }
            // Only handle when Shift is held: extend selection by lines instead of scrolling
            if ((Keyboard.Modifiers & ModifierKeys.Shift) != ModifierKeys.Shift)
            {
                return;
            }
            e.Handled = true;
            // Wheel delta: positive = scroll up, so extend selection upward (negative line delta)
            int lineDelta = e.Delta > 0 ? -1 : 1;
            int linesToMove = Math.Max(1, Math.Abs(e.Delta) / 40);
            ExtendSelectionByLines(LogTextBox, lineDelta * linesToMove);
        }

        private void LogScrollViewer_ScrollChanged(object sender, System.Windows.Controls.ScrollChangedEventArgs e)
        {
            if (LogTextBox == null || (Keyboard.Modifiers & ModifierKeys.Shift) != ModifierKeys.Shift)
            {
                if (!double.IsNaN(e.VerticalOffset))
                {
                    _lastScrollVerticalOffset = e.VerticalOffset;
                }
                return;
            }
            if (string.IsNullOrEmpty(LogTextBox.Text))
            {
                return;
            }
            if (double.IsNaN(_lastScrollVerticalOffset))
            {
                _lastScrollVerticalOffset = e.VerticalOffset;
                return;
            }
            double delta = e.VerticalOffset - _lastScrollVerticalOffset;
            _lastScrollVerticalOffset = e.VerticalOffset;
            if (Math.Abs(delta) < 0.5)
            {
                return;
            }
            int lineDelta = delta > 0 ? 1 : -1;
            int linesToMove = Math.Max(1, (int)(Math.Abs(delta) / EstimatedLineHeight));
            ExtendSelectionByLines(LogTextBox, lineDelta * linesToMove);
        }

        private void ExtendSelectionByLines(System.Windows.Controls.TextBox box, int lineDelta)
        {
            var text = box.Text;
            if (string.IsNullOrEmpty(text))
            {
                return;
            }
            int lineCount = GetLineIndexFromCharacterIndex(text, text.Length) + 1;
            int anchor = box.SelectionStart;
            int caret = box.SelectionStart + box.SelectionLength;
            int caretLine = GetLineIndexFromCharacterIndex(text, caret);
            int newLine = Math.Clamp(caretLine + lineDelta, 0, lineCount - 1);
            int newCaret = GetCharacterIndexFromLineIndex(text, newLine);
            box.SelectionStart = Math.Min(anchor, newCaret);
            box.SelectionLength = Math.Abs(newCaret - anchor);
        }

        private void OnLogReceived(object? sender, string message)
        {
            // Avoid blocking background threads and potential deadlocks by using BeginInvoke
            if (!Dispatcher.CheckAccess())
            {
                Dispatcher.BeginInvoke(new Action(() => OnLogReceived(sender, message)));
                return;
            }

            _logLines.Add(message);
            // Cap size to avoid unbounded memory and O(n) render cost
            while (_logLines.Count > MaxLogLines)
            {
                _logLines.RemoveAt(0);
            }

            // Throttle: schedule one render; use longer interval when log is large to reduce main-thread load
            if (_logRenderThrottleTimer == null)
            {
                return;
            }
            if (!_logRenderPending)
            {
                _logRenderPending = true;
                _logRenderThrottleTimer.Stop();
                _logRenderThrottleTimer.Interval = TimeSpan.FromMilliseconds(_logLines.Count > 2000 ? 500 : 300);
                _logRenderThrottleTimer.Start();
            }
        }

        private void LogLevelFilterComboBox_SelectionChanged(object sender, System.Windows.Controls.SelectionChangedEventArgs e)
        {
            if (LogLevelFilterComboBox.SelectedItem is System.Windows.Controls.ComboBoxItem item)
            {
                var value = (item.Content as string) ?? string.Empty;
                switch (value)
                {
                    case "Error":
                        _currentFilter = LogLevelFilter.Error;
                        break;
                    case "Warning":
                        _currentFilter = LogLevelFilter.Warning;
                        break;
                    default:
                        _currentFilter = LogLevelFilter.Info;
                        break;
                }
                ApplyLogFilterAndRender();
            }
        }

        private enum LogLevel
        {
            Error,
            Warning,
            Info
        }

        private static LogLevel GetLogLevel(string message)
        {
            if (string.IsNullOrEmpty(message))
            {
                return LogLevel.Info;
            }

            var upper = message.ToUpperInvariant();
            if (upper.Contains("[ERROR]") || upper.Contains(" ERROR "))
            {
                return LogLevel.Error;
            }

            if (upper.Contains("[WARN") || upper.Contains(" WARNING "))
            {
                return LogLevel.Warning;
            }

            return LogLevel.Info;
        }

        private bool ShouldDisplay(string message)
        {
            var level = GetLogLevel(message);
            return _currentFilter switch
            {
                LogLevelFilter.Error => level == LogLevel.Error,
                LogLevelFilter.Warning => level == LogLevel.Error || level == LogLevel.Warning,
                _ => true
            };
        }

        private void ApplyLogFilterAndRender()
        {
            // Controls may not be fully initialized when SelectionChanged fires during InitializeComponent
            if (LogTextBox == null || LogCountText == null)
            {
                return;
            }

            // Do not replace content while the user has a selection (e.g. copying logs).
            // Otherwise Clear() + AppendText() resets the selection and makes it jump to "all above".
            if (LogTextBox.SelectionLength > 0)
            {
                return;
            }

            // Count filtered lines (first pass)
            int totalFiltered = 0;
            foreach (var line in _logLines)
            {
                if (ShouldDisplay(line))
                {
                    totalFiltered++;
                }
            }

            int skip = Math.Max(0, totalFiltered - MaxDisplayLines);
            var sb = new StringBuilder();
            int n = 0;
            int displayed = 0;
            foreach (var line in _logLines)
            {
                if (!ShouldDisplay(line))
                {
                    continue;
                }
                if (n < skip)
                {
                    n++;
                    continue;
                }
                if (sb.Length > 0)
                {
                    sb.AppendLine();
                }
                sb.Append(line);
                displayed++;
                n++;
            }

            // Single assignment to avoid thousands of layout passes from AppendText
            LogTextBox.Text = sb.ToString();
            LogTextBox.ScrollToEnd();
            // Scroll the outer ScrollViewer to bottom so the viewport shows latest logs (not top)
            LogScrollViewer?.ScrollToBottom();
            if (totalFiltered > MaxDisplayLines)
            {
                LogCountText.Text = $"Lines: {displayed} (last of {totalFiltered} filtered, {_logLines.Count} total)";
            }
            else
            {
                LogCountText.Text = $"Lines: {totalFiltered}";
            }
        }

        private void OnBackendStatusChanged(object? sender, BackendStatus status)
        {
            // BeginInvoke avoids blocking the backend thread and prevents main-thread freeze
            Dispatcher.BeginInvoke(() =>
            {
                UpdateBackendStatus();
                UpdateControlButtons();
            });
        }

        private void OnFrontendStateChanged(object? sender, bool isRunning)
        {
            Dispatcher.BeginInvoke(() =>
            {
                UpdateFrontendStatus();
                UpdateControlButtons();
            });
        }

        private void UpdateBackendStatus()
        {
            var status = _backendService.Status;
            var isRunning = _backendService.IsRunning;
            
            // Update status text
            BackendStatusText.Text = GetStatusText(status);
            
            // Update status detail
            if (isRunning && status == BackendStatus.Running)
            {
                BackendStatusDetail.Text = "Port: 8800 | Health: OK";
            }
            else if (status == BackendStatus.Starting)
            {
                BackendStatusDetail.Text = "Starting...";
            }
            else if (status == BackendStatus.Stopping)
            {
                BackendStatusDetail.Text = "Stopping...";
            }
            else if (status == BackendStatus.Unhealthy)
            {
                BackendStatusDetail.Text = "Port: 8800 | Health: Unhealthy";
            }
            else if (status == BackendStatus.Error)
            {
                BackendStatusDetail.Text = "Error occurred";
            }
            else
            {
                BackendStatusDetail.Text = "Not running";
            }
            
            // Update status indicator color (use theme-aware colors)
            Color color;
            var runningColor = (SolidColorBrush)Application.Current.TryFindResource("StatusIndicatorRunningBrush");
            var warningColor = (SolidColorBrush)Application.Current.TryFindResource("StatusIndicatorWarningBrush");
            var stoppedColor = (SolidColorBrush)Application.Current.TryFindResource("StatusIndicatorStoppedBrush");
            
            color = status switch
            {
                BackendStatus.Running => runningColor?.Color ?? Colors.Green,
                BackendStatus.Starting => warningColor?.Color ?? Colors.Orange,
                BackendStatus.Stopping => warningColor?.Color ?? Colors.Orange,
                BackendStatus.Unhealthy => warningColor?.Color ?? Colors.Yellow,
                BackendStatus.Error => stoppedColor?.Color ?? Colors.Red,
                _ => stoppedColor?.Color ?? Colors.Gray
            };
            BackendStatusBrush.Color = color;
        }

        private void UpdateFrontendStatus()
        {
            if (_frontendService == null)
            {
                FrontendStatusText.Text = "Not Available";
                FrontendStatusDetail.Text = "Frontend service not initialized";
                FrontendStatusBrush.Color = Colors.Gray;
                return;
            }
            
            var isRunning = _frontendService.IsRunning;
            
            // Update status text
            FrontendStatusText.Text = isRunning ? "Running" : "Stopped";
            
            // Update status detail
            if (isRunning)
            {
                FrontendStatusDetail.Text = "Process active";
            }
            else
            {
                FrontendStatusDetail.Text = "Not running";
            }
            
            // Update status indicator color (use theme-aware colors)
            var runningColor = (SolidColorBrush)Application.Current.TryFindResource("StatusIndicatorRunningBrush");
            var stoppedColor = (SolidColorBrush)Application.Current.TryFindResource("StatusIndicatorStoppedBrush");
            FrontendStatusBrush.Color = isRunning 
                ? (runningColor?.Color ?? Colors.Green) 
                : (stoppedColor?.Color ?? Colors.Gray);
        }

        private void UpdateControlButtons()
        {
            var backendRunning = _backendService.IsRunning;
            var frontendRunning = _frontendService?.IsRunning ?? false;
            
            // Backend controls
            BackendStartButton.IsEnabled = !backendRunning;
            BackendStopButton.IsEnabled = backendRunning;
            BackendRestartButton.IsEnabled = backendRunning;
            
            // Frontend controls
            FrontendStartButton.IsEnabled = !frontendRunning;
            FrontendStopButton.IsEnabled = frontendRunning;
            
            // Update main status
            UpdateMainStatus(backendRunning, frontendRunning);
        }
        
        private void InitializeStatusColors()
        {
            // Initialize status brushes with theme-aware default colors
            if (BackendStatusBrush != null)
            {
                var stoppedColor = (SolidColorBrush)Application.Current.TryFindResource("StatusIndicatorStoppedBrush");
                if (stoppedColor != null)
                {
                    BackendStatusBrush.Color = stoppedColor.Color;
                }
            }
            if (FrontendStatusBrush != null)
            {
                var stoppedColor = (SolidColorBrush)Application.Current.TryFindResource("StatusIndicatorStoppedBrush");
                if (stoppedColor != null)
                {
                    FrontendStatusBrush.Color = stoppedColor.Color;
                }
            }
            if (MainStatusBrush != null)
            {
                var stoppedColor = (SolidColorBrush)Application.Current.TryFindResource("StatusIndicatorStoppedBrush");
                if (stoppedColor != null)
                {
                    MainStatusBrush.Color = stoppedColor.Color;
                }
            }
        }

        private void UpdateMainStatus(bool backendRunning, bool frontendRunning)
        {
            if (MainStatusText == null || MainStatusBrush == null)
                return;
            
            if (frontendRunning)
            {
                MainStatusText.Text = "App is running";
                var runningColor = (SolidColorBrush)Application.Current.TryFindResource("StatusIndicatorRunningBrush");
                MainStatusBrush.Color = runningColor?.Color ?? Colors.Green;
            }
            else if (backendRunning)
            {
                MainStatusText.Text = "Ready to start app";
                var warningColor = (SolidColorBrush)Application.Current.TryFindResource("StatusIndicatorWarningBrush");
                MainStatusBrush.Color = warningColor?.Color ?? Colors.Orange;
            }
            else
            {
                MainStatusText.Text = "Start server first";
                var stoppedColor = (SolidColorBrush)Application.Current.TryFindResource("StatusIndicatorStoppedBrush");
                MainStatusBrush.Color = stoppedColor?.Color ?? Colors.Gray;
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

        private void BackendStartButton_Click(object sender, RoutedEventArgs e)
        {
            try
            {
                _backendService.StartBackend();
                StatusText.Text = "Starting service...";
            }
            catch (Exception ex)
            {
                MessageBox.Show($"Failed to start service: {ex.Message}", "Error", 
                    MessageBoxButton.OK, MessageBoxImage.Error);
            }
        }

        private void BackendStopButton_Click(object sender, RoutedEventArgs e)
        {
            try
            {
                // Disable button to prevent multiple clicks
                BackendStopButton.IsEnabled = false;
                StatusText.Text = "Stopping server...";
                
                // Stop backend asynchronously (it's already async, but we update UI immediately)
                _backendService.StopBackend();
                
                // Re-enable button after a delay (backend will update status when done)
                Task.Delay(1000).ContinueWith(_ =>
                {
                    Dispatcher.BeginInvoke(new Action(() =>
                    {
                        BackendStopButton.IsEnabled = true;
                    }));
                });
            }
            catch (Exception ex)
            {
                MessageBox.Show($"Failed to stop server: {ex.Message}", "Error", 
                    MessageBoxButton.OK, MessageBoxImage.Error);
                BackendStopButton.IsEnabled = true;
            }
        }

        private void BackendRestartButton_Click(object sender, RoutedEventArgs e)
        {
            try
            {
                StatusText.Text = "Restarting service...";
                _backendService.StopBackend();
                
                // Wait a bit before restarting
                System.Threading.Tasks.Task.Delay(1000).ContinueWith(_ =>
                {
                    Dispatcher.BeginInvoke(new Action(() =>
                    {
                        _backendService.StartBackend();
                    }));
                });
            }
            catch (Exception ex)
            {
                MessageBox.Show($"Failed to restart server: {ex.Message}", "Error", 
                    MessageBoxButton.OK, MessageBoxImage.Error);
            }
        }

        private void FrontendStartButton_Click(object sender, RoutedEventArgs e)
        {
            if (_frontendService == null)
            {
                MessageBox.Show("Frontend service is not available.", "Error", 
                    MessageBoxButton.OK, MessageBoxImage.Warning);
                return;
            }
            
            try
            {
                _frontendService.StartFrontend();
                StatusText.Text = "Starting app...";
            }
            catch (Exception ex)
            {
                MessageBox.Show($"Failed to start app: {ex.Message}", "Error", 
                    MessageBoxButton.OK, MessageBoxImage.Error);
            }
        }

        private void FrontendStopButton_Click(object sender, RoutedEventArgs e)
        {
            if (_frontendService == null)
            {
                return;
            }
            
            // Show confirmation dialog using themed message box
            var result = ThemedMessageBox.Show(
                this,
                "Closing the app will cause data loss. Are you sure you want to close?",
                "Confirm Close",
                MessageBoxButton.YesNo,
                MessageBoxImage.Warning);
            
            if (result != MessageBoxResult.Yes)
            {
                return; // User cancelled
            }
            
            try
            {
                _frontendService.StopFrontend();
                StatusText.Text = "Stopping app...";
            }
            catch (Exception ex)
            {
                MessageBox.Show($"Failed to stop app: {ex.Message}", "Error", 
                    MessageBoxButton.OK, MessageBoxImage.Error);
            }
        }

        private void OpenBrowserButton_Click(object sender, RoutedEventArgs e)
        {
            try
            {
                Process.Start(new ProcessStartInfo("http://localhost:8800") { UseShellExecute = true });
                StatusText.Text = "Opened browser at http://localhost:8800";
            }
            catch (Exception ex)
            {
                MessageBox.Show($"Failed to open browser: {ex.Message}", "Error",
                    MessageBoxButton.OK, MessageBoxImage.Error);
            }
        }

        private void ClearButton_Click(object sender, RoutedEventArgs e)
        {
            _logLines.Clear();
            LogTextBox.Clear();
            StatusText.Text = "Logs cleared";
            LogCountText.Text = "Lines: 0";
        }

        private void SaveButton_Click(object sender, RoutedEventArgs e)
        {
            var saveDialog = new SaveFileDialog
            {
                Filter = "Text files (*.txt)|*.txt|All files (*.*)|*.*",
                FileName = $"OwlangsLogs_{DateTime.Now:yyyyMMdd_HHmmss}.txt"
            };

            if (saveDialog.ShowDialog() == true)
            {
                try
                {
                    File.WriteAllText(saveDialog.FileName, LogTextBox.Text);
                    StatusText.Text = $"Logs saved to {Path.GetFileName(saveDialog.FileName)}";
                    MessageBox.Show("Logs saved successfully!", "Success", 
                        MessageBoxButton.OK, MessageBoxImage.Information);
                }
                catch (Exception ex)
                {
                    MessageBox.Show($"Failed to save logs: {ex.Message}", "Error", 
                        MessageBoxButton.OK, MessageBoxImage.Error);
                }
            }
        }

        private void CopyButton_Click(object sender, RoutedEventArgs e)
        {
            try
            {
                if (string.IsNullOrEmpty(LogTextBox.Text))
                {
                    StatusText.Text = "No logs to copy";
                    return;
                }

                // Retry clipboard access because Windows clipboard is a shared resource
                // and can be temporarily locked by other applications.
                Exception? lastException = null;
                for (int attempt = 0; attempt < 10; attempt++)
                {
                    try
                    {
                        System.Windows.Clipboard.SetText(LogTextBox.Text);
                        StatusText.Text = $"Copied {LogTextBox.LineCount} lines to clipboard";
                        return;
                    }
                    catch (Exception ex)
                    {
                        lastException = ex;
                        System.Threading.Thread.Sleep(100);
                    }
                }

                throw lastException ?? new InvalidOperationException("Failed to access clipboard after multiple attempts.");
            }
            catch (Exception ex)
            {
                MessageBox.Show($"Failed to copy logs: {ex.Message}", "Error",
                    MessageBoxButton.OK, MessageBoxImage.Error);
            }
        }

        private void Window_Closing(object sender, System.ComponentModel.CancelEventArgs e)
        {
            e.Cancel = true;

            // Custom dialog so button labels match the action (no Yes/No ambiguity)
            bool? minimizeToTray = ShowCloseWindowDialog(this);
            if (minimizeToTray == null)
                return;

            if (minimizeToTray == true)
            {
                AnimateToTray();
                _statusUpdateTimer?.Stop();
            }
            else
            {
                _statusUpdateTimer?.Stop();
                _onRequestExit?.Invoke();
            }
        }

        /// <summary>
        /// Shows a dialog with "Minimize to tray" and "Exit" buttons. Returns true = minimize, false = exit, null = cancelled.
        /// </summary>
        private static bool? ShowCloseWindowDialog(Window? owner)
        {
            bool? result = null;
            var dialog = new Window
            {
                Title = "Close window",
                Width = 380,
                Height = 160,
                WindowStartupLocation = WindowStartupLocation.CenterOwner,
                ResizeMode = ResizeMode.NoResize,
                WindowStyle = WindowStyle.None,
                AllowsTransparency = true,
                Background = System.Windows.Media.Brushes.Transparent,
                ShowInTaskbar = false
            };
            if (owner != null)
                dialog.Owner = owner;
            
            // Create themed border
            var border = new Border
            {
                CornerRadius = new CornerRadius(8),
                Background = (System.Windows.Media.Brush)Application.Current.TryFindResource("PanelBackgroundBrush") ?? System.Windows.Media.Brushes.White,
                BorderBrush = (System.Windows.Media.Brush)Application.Current.TryFindResource("BorderBrush") ?? System.Windows.Media.Brushes.Gray,
                BorderThickness = new Thickness(1),
                Padding = new Thickness(20)
            };
            
            var grid = new Grid();
            grid.RowDefinitions.Add(new RowDefinition { Height = GridLength.Auto });
            grid.RowDefinitions.Add(new RowDefinition { Height = new GridLength(1, GridUnitType.Star) });
            grid.RowDefinitions.Add(new RowDefinition { Height = GridLength.Auto });
            
            // Title
            var titleText = new TextBlock
            {
                Text = "Close window",
                FontSize = 18,
                FontWeight = FontWeights.Bold,
                Foreground = (System.Windows.Media.Brush)Application.Current.TryFindResource("TextForegroundBrush") ?? System.Windows.Media.Brushes.Black,
                Margin = new Thickness(0, 0, 0, 12)
            };
            Grid.SetRow(titleText, 0);
            grid.Children.Add(titleText);
            
            // Message
            var messageText = new TextBlock
            {
                Text = "What would you like to do?",
                FontSize = 14,
                Foreground = (System.Windows.Media.Brush)Application.Current.TryFindResource("TextForegroundBrush") ?? System.Windows.Media.Brushes.Black,
                TextWrapping = TextWrapping.Wrap,
                VerticalAlignment = VerticalAlignment.Center,
                Margin = new Thickness(0, 0, 0, 16)
            };
            Grid.SetRow(messageText, 1);
            grid.Children.Add(messageText);
            
            // Buttons
            var btnPanel = new StackPanel
            {
                Orientation = Orientation.Horizontal,
                HorizontalAlignment = HorizontalAlignment.Right
            };
            
            var minimizeBtn = new Button
            {
                Content = "Minimize to tray",
                IsDefault = true,
                Margin = new Thickness(0, 0, 8, 0),
                Padding = new Thickness(16, 8, 16, 8),
                MinWidth = 120
            };
            var primaryStyle = Application.Current.TryFindResource("PrimaryButtonStyle") as Style;
            if (primaryStyle != null)
                minimizeBtn.Style = primaryStyle;
            minimizeBtn.Click += (_, __) => { result = true; dialog.Close(); };
            
            var exitBtn = new Button
            {
                Content = "Exit",
                IsCancel = true,
                Padding = new Thickness(16, 8, 16, 8),
                MinWidth = 120
            };
            var dangerStyle = Application.Current.TryFindResource("DangerButtonStyle") as Style;
            if (dangerStyle != null)
                exitBtn.Style = dangerStyle;
            exitBtn.Click += (_, __) => { result = false; dialog.Close(); };
            
            btnPanel.Children.Add(minimizeBtn);
            btnPanel.Children.Add(exitBtn);
            Grid.SetRow(btnPanel, 2);
            grid.Children.Add(btnPanel);
            
            border.Child = grid;
            dialog.Content = border;
            dialog.ShowDialog();
            return result;
        }

        private void AnimateToTray()
        {
            // Save current window position and size BEFORE animation
            // Only save if we don't already have saved values (to preserve user's preferred position)
            if (double.IsNaN(_savedLeft) || double.IsNaN(_savedTop) || 
                double.IsNaN(_savedWidth) || double.IsNaN(_savedHeight))
            {
                _savedLeft = Left;
                _savedTop = Top;
                _savedWidth = Width;
                _savedHeight = Height;
                LauncherLogger.Info($"LogWindow.AnimateToTray: saved window position Left={_savedLeft}, Top={_savedTop}, Width={_savedWidth}, Height={_savedHeight}");
            }
            
            // Get taskbar position and size
            var taskbarRect = GetTaskbarRect();
            var screenWidth = SystemParameters.PrimaryScreenWidth;
            var screenHeight = SystemParameters.PrimaryScreenHeight;
            
            // Calculate target position (bottom-right corner, near system tray)
            double targetX, targetY;
            double targetWidth = 0;
            double targetHeight = 0;
            
            // Determine taskbar position
            if (taskbarRect.Top > screenHeight / 2)
            {
                // Taskbar at bottom
                targetX = screenWidth - 50; // Near right edge
                targetY = screenHeight - 50; // Near bottom edge
            }
            else if (taskbarRect.Left > screenWidth / 2)
            {
                // Taskbar at right
                targetX = screenWidth - 50;
                targetY = screenHeight - 50;
            }
            else if (taskbarRect.Top < screenHeight / 2 && taskbarRect.Bottom < screenHeight / 2)
            {
                // Taskbar at top
                targetX = screenWidth - 50;
                targetY = 50;
            }
            else
            {
                // Taskbar at left (uncommon) or default to bottom-right
                targetX = screenWidth - 50;
                targetY = screenHeight - 50;
            }
            
            // Use current values (may have been modified by animation)
            var originalWidth = Width;
            var originalHeight = Height;
            var originalX = Left;
            var originalY = Top;
            
            // Create animations
            var widthAnimation = new DoubleAnimation(originalWidth, targetWidth, TimeSpan.FromSeconds(0.3))
            {
                EasingFunction = new CubicEase { EasingMode = EasingMode.EaseInOut }
            };
            
            var heightAnimation = new DoubleAnimation(originalHeight, targetHeight, TimeSpan.FromSeconds(0.3))
            {
                EasingFunction = new CubicEase { EasingMode = EasingMode.EaseInOut }
            };
            
            var leftAnimation = new DoubleAnimation(originalX, targetX, TimeSpan.FromSeconds(0.3))
            {
                EasingFunction = new CubicEase { EasingMode = EasingMode.EaseInOut }
            };
            
            var topAnimation = new DoubleAnimation(originalY, targetY, TimeSpan.FromSeconds(0.3))
            {
                EasingFunction = new CubicEase { EasingMode = EasingMode.EaseInOut }
            };
            
            // Create opacity animation for fade effect
            var opacityAnimation = new DoubleAnimation(1.0, 0.0, TimeSpan.FromSeconds(0.3))
            {
                EasingFunction = new CubicEase { EasingMode = EasingMode.EaseInOut }
            };
            
            // Handle animation completion
            opacityAnimation.Completed += (s, e) =>
            {
                Hide();
            };
            
            // Start animations
            BeginAnimation(WidthProperty, widthAnimation);
            BeginAnimation(HeightProperty, heightAnimation);
            BeginAnimation(LeftProperty, leftAnimation);
            BeginAnimation(TopProperty, topAnimation);
            BeginAnimation(OpacityProperty, opacityAnimation);
        }

        [StructLayout(LayoutKind.Sequential)]
        private struct RECT
        {
            public int Left;
            public int Top;
            public int Right;
            public int Bottom;
        }

        [DllImport("user32.dll")]
        private static extern IntPtr FindWindow(string? lpClassName, string? lpWindowName);

        [DllImport("user32.dll")]
        private static extern bool GetWindowRect(IntPtr hWnd, out RECT lpRect);
        
        [DllImport("user32.dll")]
        private static extern bool ShowWindow(IntPtr hWnd, int nCmdShow);
        
        [DllImport("user32.dll")]
        private static extern bool SetForegroundWindow(IntPtr hWnd);
        
        [DllImport("user32.dll")]
        private static extern bool BringWindowToTop(IntPtr hWnd);
        
        private const int SW_RESTORE = 9;
        private const int SW_SHOW = 5;

        private RECT GetTaskbarRect()
        {
            // Find taskbar window
            var taskbarHandle = FindWindow("Shell_TrayWnd", null);
            
            if (taskbarHandle != IntPtr.Zero)
            {
                GetWindowRect(taskbarHandle, out RECT rect);
                return rect;
            }
            
            // Fallback: assume taskbar at bottom
            var screenWidth = (int)SystemParameters.PrimaryScreenWidth;
            var screenHeight = (int)SystemParameters.PrimaryScreenHeight;
            return new RECT
            {
                Left = 0,
                Top = screenHeight - 40, // Typical taskbar height
                Right = screenWidth,
                Bottom = screenHeight
            };
        }

        protected override void OnClosed(EventArgs e)
        {
            Activated -= LogWindow_Activated;
            IsVisibleChanged -= LogWindow_IsVisibleChanged;
            // This should not be called if Window_Closing cancels the close
            // But we'll handle cleanup just in case
            _statusUpdateTimer?.Stop();
            _statusUpdateTimer = null;
            
            // Unsubscribe from events
            _backendService.LogReceived -= OnLogReceived;
            _backendService.StatusChanged -= OnBackendStatusChanged;
            
            if (_frontendService != null)
            {
                _frontendService.LogReceived -= OnLogReceived;
                _frontendService.RunningStateChanged -= OnFrontendStateChanged;
            }
            
            if (_redisService != null)
            {
                _redisService.LogReceived -= OnLogReceived;
            }
            
            base.OnClosed(e);
        }
        
        public void ShowWindow()
        {
            // Ensure we're on the UI thread
            if (!Dispatcher.CheckAccess())
            {
                LauncherLogger.Info("LogWindow.ShowWindow: not on UI thread, invoking on dispatcher");
                Dispatcher.Invoke(() => ShowWindow());
                return;
            }
            
            try
            {
                LauncherLogger.Info($"LogWindow.ShowWindow: starting (WindowState={WindowState}, Visibility={Visibility}, IsVisible={IsVisible})");
                // Clear any existing animations to restore window to normal state
                BeginAnimation(WidthProperty, null);
                BeginAnimation(HeightProperty, null);
                BeginAnimation(LeftProperty, null);
                BeginAnimation(TopProperty, null);
                BeginAnimation(OpacityProperty, null);
                
                // Force reset window properties to ensure they are valid
                // Get default size from XAML (1100x700) or use reasonable defaults
                var defaultWidth = 1100.0;
                var defaultHeight = 700.0;
                
                // Check if window has valid size in XAML
                if (MinWidth > 0)
                    defaultWidth = Math.Max(defaultWidth, MinWidth);
                if (MinHeight > 0)
                    defaultHeight = Math.Max(defaultHeight, MinHeight);
                
                // Always reset size and position to ensure window is visible
                // Restore saved position and size if available, otherwise use defaults
                var screenWidth = SystemParameters.PrimaryScreenWidth;
                var screenHeight = SystemParameters.PrimaryScreenHeight;
                
                LauncherLogger.Info($"LogWindow.ShowWindow: current position Left={Left}, Top={Top}, Width={Width}, Height={Height}");
                LauncherLogger.Info($"LogWindow.ShowWindow: saved position Left={_savedLeft}, Top={_savedTop}, Width={_savedWidth}, Height={_savedHeight}");
                LauncherLogger.Info($"LogWindow.ShowWindow: screen size {screenWidth}x{screenHeight}");
                
                // Check if we have saved values and if they are valid
                bool useSavedValues = !double.IsNaN(_savedLeft) && !double.IsNaN(_savedTop) && 
                                      !double.IsNaN(_savedWidth) && !double.IsNaN(_savedHeight) &&
                                      _savedWidth >= MinWidth && _savedHeight >= MinHeight &&
                                      _savedLeft >= 0 && _savedTop >= 0 &&
                                      _savedLeft + _savedWidth <= screenWidth &&
                                      _savedTop + _savedHeight <= screenHeight;
                
                if (useSavedValues)
                {
                    // Restore saved position and size
                    Left = _savedLeft;
                    Top = _savedTop;
                    Width = _savedWidth;
                    Height = _savedHeight;
                    WindowStartupLocation = WindowStartupLocation.Manual;
                    LauncherLogger.Info($"LogWindow.ShowWindow: restored saved position Left={Left}, Top={Top}, Width={Width}, Height={Height}");
                }
                else
                {
                    // Check if current size is invalid (0, NaN, or too small)
                    bool sizeInvalid = double.IsNaN(Width) || Width <= 0 || Width < MinWidth ||
                                      double.IsNaN(Height) || Height <= 0 || Height < MinHeight ||
                                      Width < 200 || Height < 200; // Minimum reasonable size
                    
                    if (sizeInvalid)
                    {
                        Width = defaultWidth;
                        Height = defaultHeight;
                        LauncherLogger.Info($"LogWindow.ShowWindow: size was invalid, reset to Width={Width}, Height={Height}");
                    }
                    
                    // Check if current position is invalid (NaN, off-screen, or window extends beyond screen)
                    bool positionInvalid = double.IsNaN(Left) || double.IsNaN(Top) ||
                                          Left < -screenWidth || Top < -screenHeight ||
                                          Left > screenWidth || Top > screenHeight ||
                                          (Left + Width > screenWidth + 100) || // Allow some margin
                                          (Top + Height > screenHeight + 100);
                    
                    if (positionInvalid)
                    {
                        // Center window on screen
                        var newLeft = Math.Max(0, (screenWidth - Width) / 2);
                        var newTop = Math.Max(0, (screenHeight - Height) / 2);
                        Left = newLeft;
                        Top = newTop;
                        WindowStartupLocation = WindowStartupLocation.Manual;
                        LauncherLogger.Info($"LogWindow.ShowWindow: position was invalid, centered to Left={newLeft}, Top={newTop}");
                    }
                    else
                    {
                        LauncherLogger.Info($"LogWindow.ShowWindow: position is valid, keeping Left={Left}, Top={Top}");
                    }
                }
                
                // Always reset opacity to ensure window is visible
                Opacity = 1.0;
                
                // Ensure window is visible and not minimized
                Visibility = Visibility.Visible;
                
                // CRITICAL: Restore window state from minimized before showing
                if (WindowState == WindowState.Minimized)
                {
                    WindowState = WindowState.Normal;
                }
                
                // Show window if not visible
                if (!IsVisible)
                {
                    LauncherLogger.Info("LogWindow.ShowWindow: window not visible, calling Show()");
                    Show();
                }
                
                // Ensure window is in Normal state (not minimized or maximized)
                WindowState = WindowState.Normal;
                LauncherLogger.Info($"LogWindow.ShowWindow: after Show(), WindowState={WindowState}, Visibility={Visibility}, IsVisible={IsVisible}");
                
                // Force window to be visible (sometimes Show() doesn't work if window was hidden)
                Visibility = Visibility.Visible;
                
                // Use Win32 API to force window to foreground
                // Note: WindowInteropHelper.Handle may be zero if window hasn't been shown yet
                // We need to ensure window is shown first, then get handle
                try
                {
                    // Ensure window is loaded and has a handle
                    if (!IsLoaded)
                    {
                        LauncherLogger.Info("LogWindow.ShowWindow: window not loaded, waiting for Loaded event");
                        // Window needs to be loaded to get handle
                        // Force a layout update to ensure window is created
                        UpdateLayout();
                    }
                    
                    var helper = new System.Windows.Interop.WindowInteropHelper(this);
                    var hWnd = helper.Handle;
                    LauncherLogger.Info($"LogWindow.ShowWindow: window handle = {hWnd} (IsLoaded={IsLoaded})");
                    
                    // If handle is zero, try to ensure window is created
                    if (hWnd == IntPtr.Zero)
                    {
                        LauncherLogger.Warn("LogWindow.ShowWindow: window handle is zero, attempting to create window");
                        // Force window creation by setting owner or ensuring it's shown
                        Show();
                        UpdateLayout();
                        System.Threading.Thread.Sleep(50); // Small delay for window creation
                        hWnd = helper.Handle;
                        LauncherLogger.Info($"LogWindow.ShowWindow: after retry, window handle = {hWnd}");
                    }
                    
                    if (hWnd != IntPtr.Zero)
                    {
                        LauncherLogger.Info($"LogWindow.ShowWindow: calling Win32 API (SW_RESTORE, SW_SHOW, BringWindowToTop, SetForegroundWindow)");
                        // Restore window if minimized (using Win32 API)
                        var restoreResult = ShowWindow(hWnd, SW_RESTORE);
                        var showResult = ShowWindow(hWnd, SW_SHOW);
                        LauncherLogger.Info($"LogWindow.ShowWindow: ShowWindow(SW_RESTORE)={restoreResult}, ShowWindow(SW_SHOW)={showResult}");
                        
                        // Bring window to top and set foreground
                        var bringToTopResult = BringWindowToTop(hWnd);
                        var setForegroundResult = SetForegroundWindow(hWnd);
                        LauncherLogger.Info($"LogWindow.ShowWindow: BringWindowToTop={bringToTopResult}, SetForegroundWindow={setForegroundResult}");
                    }
                    else
                    {
                        LauncherLogger.Error("LogWindow.ShowWindow: window handle is still zero after retry, Win32 API calls skipped");
                    }
                }
                catch (Exception ex)
                {
                    LauncherLogger.Error($"LogWindow.ShowWindow: error using Win32 API: {ex.Message}");
                    LauncherLogger.Error($"LogWindow.ShowWindow: stack trace: {ex.StackTrace}");
                    System.Diagnostics.Debug.WriteLine($"Error using Win32 API to show window: {ex.Message}");
                }
                
                // Activate and focus window (WPF methods)
                Activate();
                Focus();
                
                // Bring window to foreground and top
                // Use Topmost trick to ensure window appears on top
                Topmost = true;
                Activate();
                Focus();
                Topmost = false;
                
                // Additional activation attempts to ensure window is visible
                if (!IsActive)
                {
                    Activate();
                }
                
                // Restart status update timer when window is shown
                if (_statusUpdateTimer != null && !_statusUpdateTimer.IsEnabled)
                {
                    _statusUpdateTimer.Start();
                }
                
                LauncherLogger.Info($"LogWindow.ShowWindow: completed successfully (WindowState={WindowState}, Visibility={Visibility}, IsVisible={IsVisible}, IsActive={IsActive})");
            }
            catch (Exception ex)
            {
                System.Diagnostics.Debug.WriteLine($"Error showing LogWindow: {ex.Message}");
                LauncherLogger.Error($"LogWindow.ShowWindow: error: {ex.Message}");
                LauncherLogger.Error($"LogWindow.ShowWindow: stack trace: {ex.StackTrace}");
            }
        }
    }
}
