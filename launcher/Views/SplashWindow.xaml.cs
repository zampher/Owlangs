using System;
using System.Windows;
using System.Windows.Threading;

namespace OwlangsLauncher.Views
{
    public partial class SplashWindow : Window
    {
        private DispatcherTimer? _progressTimer;

        public SplashWindow()
        {
            InitializeComponent();
            
            // Start progress animation
            _progressTimer = new DispatcherTimer
            {
                Interval = TimeSpan.FromMilliseconds(50)
            };
            _progressTimer.Tick += ProgressTimer_Tick;
            _progressTimer.Start();
        }

        private void ProgressTimer_Tick(object? sender, EventArgs e)
        {
            // Animate progress bar (indeterminate mode)
            // This provides visual feedback that the app is loading
        }

        public void UpdateStatus(string status, int progress = -1)
        {
            Dispatcher.Invoke(() =>
            {
                StatusText.Text = status;
                
                if (progress >= 0 && progress <= 100)
                {
                    ProgressBar.IsIndeterminate = false;
                    ProgressBar.Value = progress;
                }
                else
                {
                    ProgressBar.IsIndeterminate = true;
                }
            });
        }

        public void SetProgress(int progress)
        {
            Dispatcher.Invoke(() =>
            {
                if (progress >= 0 && progress <= 100)
                {
                    ProgressBar.IsIndeterminate = false;
                    ProgressBar.Value = progress;
                }
            });
        }

        protected override void OnClosed(EventArgs e)
        {
            _progressTimer?.Stop();
            _progressTimer = null;
            base.OnClosed(e);
        }
    }
}

