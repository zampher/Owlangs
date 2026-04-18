using System;
using System.Collections.Generic;
using System.IO;
using System.IO.Pipes;
using System.Text;
using System.Threading;
using System.Threading.Tasks;
using System.Text.Json;

namespace OwlangsLauncher.Services
{
    public class IpcService
    {
        private readonly BackendService _backendService;
        private readonly FrontendService? _frontendService;
        private NamedPipeServerStream? _pipeServer;
        private CancellationTokenSource? _cancellationTokenSource;
        private const string PipeName = "OwlangsLauncher";

        public event Action? OnShowConsole;
        
        public IpcService(BackendService backendService, FrontendService? frontendService = null)
        {
            _backendService = backendService;
            _frontendService = frontendService;
        }

        public void Start()
        {
            _cancellationTokenSource = new CancellationTokenSource();
            _ = Task.Run(() => ListenForClients(_cancellationTokenSource.Token));
        }

        public void Stop()
        {
            try
            {
                LauncherLogger.Info("IpcService.Stop: stopping IPC service");
                _cancellationTokenSource?.Cancel();
                
                // Wait a bit for the listening task to exit
                System.Threading.Thread.Sleep(200);
                
                _pipeServer?.Dispose();
                _pipeServer = null;
                
                // Dispose CancellationTokenSource to release resources
                _cancellationTokenSource?.Dispose();
                _cancellationTokenSource = null;
                
                LauncherLogger.Info("IpcService.Stop: IPC service stopped");
            }
            catch (Exception ex)
            {
                LauncherLogger.Warn($"IpcService.Stop: error stopping service: {ex.Message}");
            }
        }

        private async Task ListenForClients(CancellationToken cancellationToken)
        {
            while (!cancellationToken.IsCancellationRequested && 
                   !ApplicationShutdownToken.IsShutdownRequested)
            {
                try
                {
                    // Check shutdown token before creating new pipe
                    ApplicationShutdownToken.ThrowIfShutdownRequested();
                    
                    _pipeServer = new NamedPipeServerStream(
                        PipeName,
                        PipeDirection.InOut,
                        1,
                        PipeTransmissionMode.Byte,
                        PipeOptions.Asynchronous);

                    await _pipeServer.WaitForConnectionAsync(cancellationToken);

                    // Handle client request (only if not shutting down)
                    if (!ApplicationShutdownToken.IsShutdownRequested)
                    {
                        _ = Task.Run(() => HandleClient(_pipeServer, cancellationToken));
                    }
                }
                catch (OperationCanceledException)
                {
                    break;
                }
                catch (Exception)
                {
                    // Log error and retry (only if not shutting down)
                    if (!ApplicationShutdownToken.IsShutdownRequested)
                    {
                        await Task.Delay(1000, cancellationToken);
                    }
                    else
                    {
                        break;
                    }
                }
            }
            
            LauncherLogger.Info("IpcService.ListenForClients: loop exited (shutdown requested or cancelled)");
        }

        private async Task HandleClient(NamedPipeServerStream pipe, CancellationToken cancellationToken)
        {
            try
            {
                // Check shutdown token before handling client
                ApplicationShutdownToken.ThrowIfShutdownRequested();
                
                var buffer = new byte[4096];
                var bytesRead = await pipe.ReadAsync(buffer, 0, buffer.Length, cancellationToken);
                
                if (bytesRead > 0 && !ApplicationShutdownToken.IsShutdownRequested)
                {
                    var request = Encoding.UTF8.GetString(buffer, 0, bytesRead);
                    var response = ProcessRequest(request);
                    
                    if (!ApplicationShutdownToken.IsShutdownRequested)
                    {
                        var responseBytes = Encoding.UTF8.GetBytes(response);
                        await pipe.WriteAsync(responseBytes, 0, responseBytes.Length, cancellationToken);
                    }
                }
            }
            catch (OperationCanceledException)
            {
                // Shutdown requested or cancellation token triggered
                LauncherLogger.Info("IpcService.HandleClient: cancelled due to shutdown");
            }
            catch (Exception ex)
            {
                // Log error but don't throw (client connection might be closed)
                if (!ApplicationShutdownToken.IsShutdownRequested)
                {
                    LauncherLogger.Warn($"IpcService.HandleClient: error handling client: {ex.Message}");
                }
            }
            finally
            {
                pipe.Dispose();
            }
        }

        private string ProcessRequest(string request)
        {
            try
            {
                LauncherLogger.Info($"IpcService.ProcessRequest: received request: {request}");
                
                var options = new JsonSerializerOptions
                {
                    PropertyNameCaseInsensitive = true
                };
                var requestObj = JsonSerializer.Deserialize<IpcRequest>(request, options);
                
                if (requestObj == null)
                {
                    LauncherLogger.Warn("IpcService.ProcessRequest: failed to deserialize request");
                    return CreateErrorResponse("Invalid request format");
                }
                
                LauncherLogger.Info($"IpcService.ProcessRequest: parsed action = '{requestObj.Action}'");
                
                return requestObj.Action switch
                {
                    "get_status" => GetStatusResponse(),
                    "restart_backend" => RestartBackend(),
                    "start_frontend" => StartFrontend(),
                    "stop_frontend" => StopFrontend(),
                    "get_frontend_status" => GetFrontendStatus(),
                    "show_console" => ShowConsole(),
                    "request_exit" => RequestExit(),
                    _ => CreateErrorResponse($"Unknown action: {requestObj.Action}")
                };
            }
            catch (Exception ex)
            {
                LauncherLogger.Error($"IpcService.ProcessRequest: error processing request: {ex.Message}");
                LauncherLogger.Error($"IpcService.ProcessRequest: stack trace: {ex.StackTrace}");
                return CreateErrorResponse($"Invalid request: {ex.Message}");
            }
        }

        private string GetStatusResponse()
        {
            var status = new IpcStatusResponse
            {
                Status = _backendService.Status.ToString().ToLower(),
                IsRunning = _backendService.IsRunning,
                FrontendRunning = _frontendService?.IsRunning ?? false
            };

            return JsonSerializer.Serialize(status);
        }

        private string GetFrontendStatus()
        {
            var status = new
            {
                isRunning = _frontendService?.IsRunning ?? false,
                autoStartEnabled = _frontendService?.AutoStartEnabled ?? false
            };
            return JsonSerializer.Serialize(status);
        }

        private string StartFrontend()
        {
            try
            {
                if (_frontendService == null)
                {
                    return CreateErrorResponse("Frontend service not available");
                }
                
                if (_frontendService.IsRunning)
                {
                    return CreateErrorResponse("Frontend is already running");
                }
                
                _frontendService.StartFrontend();
                return CreateSuccessResponse("Frontend start initiated");
            }
            catch (Exception ex)
            {
                return CreateErrorResponse($"Failed to start frontend: {ex.Message}");
            }
        }

        private string StopFrontend()
        {
            try
            {
                if (_frontendService == null)
                {
                    return CreateErrorResponse("Frontend service not available");
                }
                
                if (!_frontendService.IsRunning)
                {
                    return CreateErrorResponse("Frontend is not running");
                }
                
                _frontendService.StopFrontend();
                return CreateSuccessResponse("Frontend stop initiated");
            }
            catch (Exception ex)
            {
                return CreateErrorResponse($"Failed to stop frontend: {ex.Message}");
            }
        }

        private string RestartBackend()
        {
            try
            {
                // Start stopping backend (don't wait - restart operation can proceed asynchronously)
                _ = _backendService.StopBackend();
                // Wait a bit before starting (backend needs time to stop)
                System.Threading.Tasks.Task.Delay(2000).ContinueWith(_ =>
                {
                    _backendService.StartBackend();
                });
                
                return CreateSuccessResponse("Backend restart initiated");
            }
            catch (Exception ex)
            {
                return CreateErrorResponse($"Failed to restart backend: {ex.Message}");
            }
        }

        private string CreateSuccessResponse(string message, object? data = null)
        {
            var response = new Dictionary<string, object>
            {
                { "success", true },
                { "message", message }
            };
            
            if (data != null)
            {
                response["data"] = data;
            }
            
            return JsonSerializer.Serialize(response);
        }

        private string RequestExit()
        {
            try
            {
                LauncherLogger.Info("IpcService.RequestExit: received request_exit, triggering application shutdown");
                System.Windows.Application.Current.Dispatcher.BeginInvoke(new Action(() =>
                {
                    System.Windows.Application.Current.Shutdown();
                }), System.Windows.Threading.DispatcherPriority.Normal);
                return CreateSuccessResponse("Exit request sent");
            }
            catch (Exception ex)
            {
                return CreateErrorResponse($"Failed to request exit: {ex.Message}");
            }
        }

        private string ShowConsole()
        {
            try
            {
                LauncherLogger.Info("IpcService.ShowConsole: received show_console request");
                if (OnShowConsole == null)
                {
                    LauncherLogger.Warn("IpcService.ShowConsole: OnShowConsole event handler is null");
                    return CreateErrorResponse("OnShowConsole event handler is not registered");
                }
                
                LauncherLogger.Info("IpcService.ShowConsole: invoking OnShowConsole event");
                OnShowConsole.Invoke();
                LauncherLogger.Info("IpcService.ShowConsole: OnShowConsole event invoked successfully");
                return CreateSuccessResponse("Console show request sent");
            }
            catch (Exception ex)
            {
                LauncherLogger.Error($"IpcService.ShowConsole: error showing console: {ex.Message}");
                LauncherLogger.Error($"IpcService.ShowConsole: stack trace: {ex.StackTrace}");
                return CreateErrorResponse($"Failed to show console: {ex.Message}");
            }
        }

        private string CreateErrorResponse(string message, string? code = null)
        {
            var response = new Dictionary<string, object>
            {
                { "success", false },
                { "error", message }
            };
            
            if (!string.IsNullOrEmpty(code))
            {
                response["code"] = code;
            }
            
            return JsonSerializer.Serialize(response);
        }
    }

    public class IpcRequest
    {
        public string Action { get; set; } = string.Empty;
    }

    public class IpcStatusResponse
    {
        public string Status { get; set; } = string.Empty;
        public bool IsRunning { get; set; }
        public bool FrontendRunning { get; set; }
    }
}

