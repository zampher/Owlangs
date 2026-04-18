// SPDX-FileCopyrightText: 2025 QinHan
// SPDX-License-Identifier: MPL-2.0

import 'dart:async';
import 'dart:io' if (dart.library.html) 'backend_status_io_stub.dart' as io;
import 'package:flutter/foundation.dart'
    show kIsWeb, debugPrint, defaultTargetPlatform, TargetPlatform;
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../app/app_config.dart';

/// Backend connection status
enum BackendStatus {
  /// Backend is starting up
  starting,

  /// Backend is running and healthy
  connected,

  /// Backend is disconnected or unreachable
  disconnected,

  /// Backend status is unknown (e.g., IPC not available)
  unknown,

  /// Connecting to backend (initial connection attempt)
  connecting,
}

/// Backend status notifier
class BackendStatusNotifier extends StateNotifier<BackendStatus> {
  BackendStatusNotifier() : super(BackendStatus.unknown) {
    _initialize();
  }

  Timer? _statusCheckTimer;
  Timer? _ipcCheckTimer;
  bool _isChecking = false;
  int _consecutiveFailures = 0;
  static const int _maxFailuresBeforeDisconnected = 3;
  /// Throttle health-check error logs (e.g. connection refused) when backend is overloaded or down.
  DateTime? _lastHealthErrorLogTime;
  static const Duration _healthErrorLogThrottle = Duration(seconds: 60);
  /// Poll interval; 5s reduces load when backend is busy (e.g. language detection for many segments).
  static const Duration _statusCheckInterval = Duration(seconds: 5);

  void _initialize() {
    // Only check backend status on Windows desktop
    if (!kIsWeb && defaultTargetPlatform == TargetPlatform.windows) {
      _startStatusChecking();
    } else {
      // On web or non-Windows, assume connected (backend runs separately)
      state = BackendStatus.connected;
    }
  }

  void _startStatusChecking() {
    // Set initial state to connecting if currently unknown
    if (state == BackendStatus.unknown) {
      state = BackendStatus.connecting;
    }

    // Check IPC availability first
    _checkIpcAvailability();

    // Then start periodic status checks
    _statusCheckTimer?.cancel();
    _statusCheckTimer = Timer.periodic(_statusCheckInterval, (_) {
      if (!_isChecking) {
        _checkBackendStatus();
      }
    });
  }

  /// Check if IPC service is available (Launcher is running)
  Future<void> _checkIpcAvailability() async {
    if (_isChecking) return;
    _isChecking = true;

    try {
      if (kIsWeb) {
        // IPC not available on Web, use HTTP
        await _checkBackendStatusViaHttp();
      } else {
        // Try to connect to Launcher IPC
        final client = await _connectToIpc();
        if (client != null) {
          // IPC is available, check backend status via IPC
          await _checkBackendStatusViaIpc(client);
          try {
            client.close();
          } catch (e) {
            // Ignore close errors
          }
        } else {
          // IPC not available, fallback to HTTP health check
          await _checkBackendStatusViaHttp();
        }
      }
    } catch (e) {
      debugPrint('[BackendStatus] IPC check error: $e');
      // Fallback to HTTP health check
      await _checkBackendStatusViaHttp();
    } finally {
      _isChecking = false;
    }
  }

  /// Check backend status via IPC (preferred method)
  Future<void> _checkBackendStatusViaIpc(client) async {
    if (kIsWeb) {
      // IPC not available on Web, fallback to HTTP
      await _checkBackendStatusViaHttp();
      return;
    }

    try {
      // Send status request
      const String request = '{"action":"get_status"}\n';
      client.write(request);
      await client.flush();

      // Read response (with timeout)
      final Completer<String> completer = Completer<String>();
      final subscription = client.listen(
        (data) {
          final String response = String.fromCharCodes(data);
          if (!completer.isCompleted) {
            completer.complete(response);
          }
        },
        onError: (error) {
          if (!completer.isCompleted) {
            completer.completeError(error);
          }
        },
      );

      final String response = await completer.future.timeout(
        const Duration(seconds: 1),
        onTimeout: () => throw TimeoutException('IPC response timeout'),
      );

      subscription.cancel();

      // Parse response
      final String statusJson = response.trim();
      if (statusJson.contains('"status"')) {
        if (statusJson.contains('"status":"running"') ||
            statusJson.contains('"status":"starting"')) {
          state = statusJson.contains('"status":"starting"')
              ? BackendStatus.starting
              : BackendStatus.connected;
        } else {
          state = BackendStatus.disconnected;
        }
      }
    } catch (e) {
      debugPrint('[BackendStatus] IPC status check error: $e');
      // Fallback to HTTP
      await _checkBackendStatusViaHttp();
    }
  }

  /// Check backend status via HTTP health endpoint (fallback)
  Future<void> _checkBackendStatusViaHttp() async {
    if (kIsWeb) {
      // On Web, use http package or fetch API
      // For now, assume connected on Web (backend runs separately)
      state = BackendStatus.connected;
      return;
    }

    // Only use dart:io on non-Web platforms
    // We need to use a dynamic approach to avoid compilation errors on Web
    try {
      // Use dynamic to avoid type checking issues with conditional imports
      final httpClient = _createHttpClient();
      if (httpClient == null) {
        _handleCheckFailure();
        return;
      }

      // Use 10s timeout so health check succeeds during heavy backend work (e.g. language detection)
      final request = await httpClient
          .getUrl(Uri.parse('${AppConfig.baseUrl}/api/health'))
          .timeout(const Duration(seconds: 10));
      final response =
          await request.close().timeout(const Duration(seconds: 10));

      if (response.statusCode == 200) {
        _consecutiveFailures = 0;
        state = BackendStatus.connected;
        _lastHealthErrorLogTime = null;
      } else {
        _handleCheckFailure();
      }

      httpClient.close();
    } catch (e) {
      _handleCheckFailure();
      // Throttle logs when backend is unreachable (e.g. overloaded with 270k+ segments or down)
      final now = DateTime.now();
      if (_lastHealthErrorLogTime == null ||
          now.difference(_lastHealthErrorLogTime!) > _healthErrorLogThrottle) {
        _lastHealthErrorLogTime = now;
        debugPrint(
          '[${now.toIso8601String()}][BackendStatus] HTTP health check error: $e',
        );
      }
    }
  }

  /// Create HTTP client (platform-specific)
  dynamic _createHttpClient() {
    if (kIsWeb) {
      return null;
    }
    // This will only compile on non-Web platforms due to conditional import
    // On Web, io.HttpClient is a stub that returns null
    try {
      return io.HttpClient();
    } catch (e) {
      // Fallback if HttpClient is not available
      return null;
    }
  }

  /// Check backend status (main method)
  Future<void> _checkBackendStatus() async {
    if (_isChecking) return;
    _isChecking = true;

    try {
      if (kIsWeb) {
        // On Web, only use HTTP
        await _checkBackendStatusViaHttp();
      } else {
        // Try IPC first, then HTTP fallback
        final client = await _connectToIpc();
        if (client != null) {
          await _checkBackendStatusViaIpc(client);
          try {
            client.close();
          } catch (e) {
            // Ignore close errors
          }
        } else {
          await _checkBackendStatusViaHttp();
        }
      }
    } catch (e) {
      final now = DateTime.now();
      if (_lastHealthErrorLogTime == null ||
          now.difference(_lastHealthErrorLogTime!) > _healthErrorLogThrottle) {
        _lastHealthErrorLogTime = now;
        debugPrint('[BackendStatus] Status check error: $e');
      }
      await _checkBackendStatusViaHttp();
    } finally {
      _isChecking = false;
    }
  }

  /// Connect to Launcher IPC (named pipe)
  Future<dynamic> _connectToIpc() async {
    if (kIsWeb) {
      // IPC not available on Web
      return null;
    }

    try {
      // Named pipe on Windows: \\.\pipe\OwlangsLauncher
      // Use RawSocket for named pipe connection
      // Note: Dart's Socket.connect doesn't support named pipes directly
      // We'll use a workaround with a TCP-like connection
      // For now, return null to use HTTP fallback
      // TODO: Implement proper named pipe connection using FFI or platform channels
      return null;
    } catch (e) {
      debugPrint('[BackendStatus] IPC connect error: $e');
      return null;
    }
  }

  /// Handle check failure - only set disconnected after multiple failures
  void _handleCheckFailure() {
    _consecutiveFailures++;

    // If we're still connecting or unknown, keep showing connecting state
    // Only show disconnected after multiple consecutive failures
    if (state == BackendStatus.connecting || state == BackendStatus.unknown) {
      // Keep connecting state for initial attempts
      if (_consecutiveFailures < _maxFailuresBeforeDisconnected) {
        state = BackendStatus.connecting;
      } else {
        state = BackendStatus.disconnected;
      }
    } else if (_consecutiveFailures >= _maxFailuresBeforeDisconnected) {
      // Only set disconnected if we've had multiple consecutive failures
      state = BackendStatus.disconnected;
    }
    // Otherwise, keep current state (e.g., if already connected, don't change)
  }

  /// Manually refresh backend status
  Future<void> refresh() async {
    await _checkBackendStatus();
  }

  @override
  void dispose() {
    _statusCheckTimer?.cancel();
    _ipcCheckTimer?.cancel();
    super.dispose();
  }
}

/// Backend status provider
final StateNotifierProvider<BackendStatusNotifier, BackendStatus>
    backendStatusProvider =
    StateNotifierProvider<BackendStatusNotifier, BackendStatus>(
  (StateNotifierProviderRef<BackendStatusNotifier, BackendStatus> ref) =>
      BackendStatusNotifier(),
);
