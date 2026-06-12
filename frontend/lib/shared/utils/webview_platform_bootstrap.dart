// SPDX-FileCopyrightText: 2026 Zampher
// SPDX-License-Identifier: MPL-2.0

import 'dart:io' show Platform;

import 'package:flutter/foundation.dart' show kIsWeb;
import 'package:webview_flutter_platform_interface/webview_flutter_platform_interface.dart';
import 'package:webview_win_floating/webview_plugin.dart' as win_webview;

import 'app_logger.dart';

/// Register desktop WebView2 implementation for webview_flutter on Windows/Linux.
void ensureWebViewPlatformRegistered() {
  if (kIsWeb) {
    return;
  }
  if (!Platform.isWindows && !Platform.isLinux) {
    return;
  }
  if (WebViewPlatform.instance != null) {
    return;
  }
  win_webview.WindowsWebViewPlatform.registerWith();
  AppLogger.log(
    'WebViewBootstrap',
    'Registered webview_win_floating for ${Platform.operatingSystem}',
    level: LogLevel.info,
  );
}
