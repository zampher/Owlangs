using System;
using System.IO;
using System.Net;
using System.Text;
using System.Threading;
using System.Threading.Tasks;
using System.Windows;
using System.Windows.Threading;

namespace OwlangsLauncher.Services
{
    /// <summary>
    /// Listens for HTTP POST /request_exit from the Flutter Windows desktop app.
    /// When received, triggers Launcher shutdown (backend + Launcher exit).
    /// Port 13131 to avoid conflict with backend (e.g. 8800/8010).
    /// </summary>
    public class ExitRequestListenerService
    {
        private const int Port = 13131;
        private const string PathRequestExit = "/request_exit";
        private HttpListener? _listener;
        private CancellationTokenSource? _cts;

        public void Start()
        {
            if (_listener != null)
            {
                return;
            }

            try
            {
                _listener = new HttpListener();
                _listener.Prefixes.Add($"http://127.0.0.1:{Port}/");
                _listener.Start();
                _cts = new CancellationTokenSource();
                _ = ListenAsync(_cts.Token);
                LauncherLogger.Info($"ExitRequestListenerService: listening on http://127.0.0.1:{Port}/");
            }
            catch (Exception ex)
            {
                LauncherLogger.Warn($"ExitRequestListenerService: failed to start: {ex.Message}");
            }
        }

        public void Stop()
        {
            try
            {
                _cts?.Cancel();
                _listener?.Stop();
                _listener?.Close();
                _listener = null;
                _cts?.Dispose();
                _cts = null;
                LauncherLogger.Info("ExitRequestListenerService: stopped");
            }
            catch (Exception ex)
            {
                LauncherLogger.Warn($"ExitRequestListenerService: error stopping: {ex.Message}");
            }
        }

        private async Task ListenAsync(CancellationToken cancellationToken)
        {
            while (!cancellationToken.IsCancellationRequested && !ApplicationShutdownToken.IsShutdownRequested)
            {
                try
                {
                    var context = await _listener!.GetContextAsync().WaitAsync(cancellationToken);
                    _ = Task.Run(() => HandleRequest(context), cancellationToken);
                }
                catch (OperationCanceledException)
                {
                    break;
                }
                catch (ObjectDisposedException)
                {
                    break;
                }
                catch (Exception ex)
                {
                    if (!ApplicationShutdownToken.IsShutdownRequested)
                    {
                        LauncherLogger.Warn($"ExitRequestListenerService: listen error: {ex.Message}");
                    }
                    await Task.Delay(1000, cancellationToken);
                }
            }
        }

        private void HandleRequest(HttpListenerContext context)
        {
            var request = context.Request;
            var response = context.Response;

            try
            {
                if (request.HttpMethod != "POST" || request.Url?.AbsolutePath != PathRequestExit)
                {
                    response.StatusCode = 404;
                    response.Close();
                    return;
                }

                LauncherLogger.Info("ExitRequestListenerService: received request_exit from Flutter desktop");
                response.StatusCode = 200;
                response.ContentType = "application/json; charset=utf-8";
                var body = Encoding.UTF8.GetBytes("{\"success\":true}");
                response.ContentLength64 = body.Length;
                response.OutputStream.Write(body, 0, body.Length);
                response.Close();

                Application.Current.Dispatcher.Invoke(() =>
                {
                    Application.Current.Shutdown();
                }, DispatcherPriority.Normal);
            }
            catch (Exception ex)
            {
                LauncherLogger.Warn($"ExitRequestListenerService: handle request error: {ex.Message}");
                try
                {
                    response.StatusCode = 500;
                    response.Close();
                }
                catch { }
            }
        }
    }
}
