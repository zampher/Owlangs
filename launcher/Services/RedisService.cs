using System;
using System.Diagnostics;
using System.IO;
using System.Linq;
using System.Net.NetworkInformation;
using System.Threading;

namespace OwlangsLauncher.Services
{
    public class RedisService
    {
        private const int RedisPort = 6379;
        private const string RedisProcessName = "redis-server";

        /// <summary>
        /// Check if Redis is running by checking if port 6379 is in use
        /// </summary>
        public bool IsRunning()
        {
            try
            {
                // Check if port 6379 is in use
                var connections = IPGlobalProperties.GetIPGlobalProperties()
                    .GetActiveTcpListeners()
                    .Any(listener => listener.Port == RedisPort);
                
                if (connections)
                {
                    // Also check if redis-server process exists
                    var processes = Process.GetProcessesByName(RedisProcessName);
                    return processes.Length > 0;
                }
                
                return false;
            }
            catch
            {
                // If we can't check, assume it's not running
                return false;
            }
        }

        /// <summary>
        /// Stop Redis service by terminating redis-server processes
        /// </summary>
        public void StopRedis()
        {
            try
            {
                var processes = Process.GetProcessesByName(RedisProcessName);
                if (processes.Length == 0)
                {
                    Log("Redis is not running");
                    return;
                }

                Log($"Found {processes.Length} Redis process(es), stopping...");

                foreach (var process in processes)
                {
                    try
                    {
                        if (!process.HasExited)
                        {
                            Log($"Stopping Redis process (PID: {process.Id})...");
                            
                            // Try graceful shutdown first
                            process.CloseMainWindow();
                            
                            if (!process.WaitForExit(3000))
                            {
                                // Force kill if graceful shutdown failed
                                Log($"Force killing Redis process (PID: {process.Id})...");
                                process.Kill();
                                process.WaitForExit();
                            }
                            
                            Log($"Redis process (PID: {process.Id}) stopped");
                        }
                        
                        process.Dispose();
                    }
                    catch (Exception ex)
                    {
                        Log($"[ERROR] Failed to stop Redis process (PID: {process.Id}): {ex.Message}");
                    }
                }

                // Wait a bit and verify Redis is stopped
                Thread.Sleep(500);
                if (IsRunning())
                {
                    Log("[WARNING] Redis may still be running after stop attempt");
                }
                else
                {
                    Log("Redis stopped successfully");
                }
            }
            catch (Exception ex)
            {
                Log($"[ERROR] Error stopping Redis: {ex.Message}");
            }
        }

        public event EventHandler<string>? LogReceived;

        private void Log(string message)
        {
            var timestamp = DateTime.Now.ToString("yyyy-MM-dd HH:mm:ss");
            LogReceived?.Invoke(this, $"[{timestamp}] [Redis] {message}");
        }
    }
}

