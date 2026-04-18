using System;
using System.Threading;

namespace OwlangsLauncher.Services
{
    /// <summary>
    /// Global shutdown token for coordinating thread/task exit across the application.
    /// All background threads and tasks should check this token before continuing work.
    /// </summary>
    public static class ApplicationShutdownToken
    {
        private static volatile bool _isShutdownRequested = false;
        private static readonly object _lock = new object();

        /// <summary>
        /// Gets whether shutdown has been requested.
        /// Thread-safe property that can be checked by any thread.
        /// </summary>
        public static bool IsShutdownRequested
        {
            get
            {
                return _isShutdownRequested;
            }
        }

        /// <summary>
        /// Request application shutdown. This should be called from OnExit().
        /// Once set, this cannot be reset (application is shutting down).
        /// </summary>
        public static void RequestShutdown()
        {
            lock (_lock)
            {
                if (!_isShutdownRequested)
                {
                    _isShutdownRequested = true;
                    LauncherLogger.Info("ApplicationShutdownToken: shutdown requested");
                }
            }
        }

        /// <summary>
        /// Throws OperationCanceledException if shutdown has been requested.
        /// Useful for async methods that should exit immediately when shutdown is requested.
        /// </summary>
        public static void ThrowIfShutdownRequested()
        {
            if (_isShutdownRequested)
            {
                throw new OperationCanceledException("Application shutdown requested");
            }
        }
    }
}
