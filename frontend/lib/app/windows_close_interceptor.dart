// SPDX-FileCopyrightText: 2025 Owlangs
// SPDX-License-Identifier: MPL-2.0

/// Windows desktop close interceptor: show confirm dialog and notify backend + Launcher to exit.
/// Not used on web (Chrome) or other platforms.
library;

import 'dart:io' if (dart.library.html) 'package:owlangs/app/io_exit_stub.dart'
    show exit;

import 'package:flutter/foundation.dart'
    show kIsWeb, defaultTargetPlatform, TargetPlatform;
import 'package:flutter/material.dart';
import 'package:window_manager/window_manager.dart'
    if (dart.library.html) 'package:owlangs/app/window_manager_stub.dart';

import 'app_config.dart';
import 'package:dio/dio.dart';

/// Wraps the app on Windows desktop only. Intercepts window close, shows "Close service?" dialog,
/// and on confirm notifies Launcher (and thus backend) to exit, then closes the app.
class WindowsCloseInterceptor extends StatefulWidget {
  const WindowsCloseInterceptor({required this.child, super.key});

  final Widget child;

  @override
  State<WindowsCloseInterceptor> createState() =>
      _WindowsCloseInterceptorState();
}

class _WindowsCloseInterceptorState extends State<WindowsCloseInterceptor>
    with WindowListener {
  @override
  void initState() {
    super.initState();
    windowManager.addListener(this);
  }

  @override
  void dispose() {
    windowManager.removeListener(this);
    super.dispose();
  }

  @override
  void onWindowClose() {
    _showCloseConfirmDialog();
  }

  Future<void> _showCloseConfirmDialog() async {
    if (!mounted) return;
    final confirmed = await showDialog<bool>(
      context: context,
      barrierDismissible: false,
      builder: (BuildContext dialogContext) => AlertDialog(
        title: const Text('Close service?'),
        content: const Text(
          'Do you want to close the service? This will stop the backend server and the Launcher.',
        ),
        actions: <Widget>[
          TextButton(
            onPressed: () => Navigator.of(dialogContext).pop(false),
            child: const Text('Cancel'),
          ),
          FilledButton(
            onPressed: () => Navigator.of(dialogContext).pop(true),
            child: const Text('Close'),
          ),
        ],
      ),
    );
    if (confirmed != true || !mounted) return;
    await _requestLauncherExitAndClose();
  }

  /// Notify Launcher to exit (stops backend and Launcher), then close this app.
  Future<void> _requestLauncherExitAndClose() async {
    try {
      // Request Launcher to stop backend and exit
      await requestLauncherExit();
    } catch (_) {
      // Launcher may not be running; still close the window
    }
    if (!mounted) return;
    await windowManager.destroy();
    exit(0);
  }

  @override
  Widget build(BuildContext context) => widget.child;
}

/// Returns true if close interception (confirm dialog + notify Launcher) should be enabled.
bool get isWindowsDesktopCloseInterceptorEnabled =>
    !kIsWeb && defaultTargetPlatform == TargetPlatform.windows;

/// Request Launcher to exit (stops backend and Launcher). POST to Launcher HTTP endpoint.
/// May throw if Launcher is not running or request fails.
Future<void> requestLauncherExit() async {
  final dio = Dio(BaseOptions(connectTimeout: const Duration(seconds: 2)));
  await dio.post(AppConfig.kLauncherRequestExitUrl);
}
