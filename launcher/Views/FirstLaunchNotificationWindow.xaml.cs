using System;
using System.Windows;
using System.Windows.Threading;

namespace OwlangsLauncher.Views
{
    public partial class FirstLaunchNotificationWindow : Window
    {
        private DispatcherTimer? _autoCloseTimer;

        public FirstLaunchNotificationWindow()
        {
            InitializeComponent();
            
            // Auto-close after 2 seconds
            _autoCloseTimer = new DispatcherTimer
            {
                Interval = TimeSpan.FromSeconds(2)
            };
            _autoCloseTimer.Tick += AutoCloseTimer_Tick;
            _autoCloseTimer.Start();
        }

        private void AutoCloseTimer_Tick(object? sender, EventArgs e)
        {
            _autoCloseTimer?.Stop();
            _autoCloseTimer = null;
            
            // Close the window (it will minimize to tray)
            Close();
        }

        protected override void OnClosed(EventArgs e)
        {
            _autoCloseTimer?.Stop();
            _autoCloseTimer = null;
            base.OnClosed(e);
        }
    }
}

