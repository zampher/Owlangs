// SPDX-FileCopyrightText: 2026 Zampher
// SPDX-License-Identifier: MPL-2.0

import 'dart:io' show Directory, File, Platform;

import 'package:flutter/foundation.dart' show kIsWeb;
import 'package:path_provider/path_provider.dart';
import 'package:webview_flutter/webview_flutter.dart';
import 'package:webview_win_floating/webview_win_floating.dart';

import 'app_logger.dart';

/// Creates a [WebViewController] with a writable user-data folder on desktop.
Future<WebViewController> createDesktopWebViewController() async {
  if (kIsWeb) {
    return WebViewController();
  }
  if (Platform.isWindows || Platform.isLinux) {
    final Directory supportDir = await getApplicationSupportDirectory();
    final Directory webViewDir = Directory(
      '${supportDir.path}${Platform.pathSeparator}webview',
    );
    if (!webViewDir.existsSync()) {
      webViewDir.createSync(recursive: true);
    }
    AppLogger.log(
      'DesktopWebView',
      'Using WebView userDataFolder: ${webViewDir.path}',
      level: LogLevel.debug,
    );
    final WindowsWebViewControllerCreationParams params =
        WindowsWebViewControllerCreationParams(
      userDataFolder: webViewDir.path,
    );
    return WebViewController.fromPlatformCreationParams(params);
  }
  return WebViewController();
}

/// Writes HTML to a temp file and returns the file URI for WebView2 loading.
Future<Uri> writeDesktopPreviewHtmlFile(String htmlContent) async {
  final Directory tempDir = await getTemporaryDirectory();
  final File file = File(
    '${tempDir.path}${Platform.pathSeparator}'
    'owlangs_preview_${DateTime.now().millisecondsSinceEpoch}.html',
  );
  await file.writeAsString(htmlContent);
  return Uri.file(file.path);
}
