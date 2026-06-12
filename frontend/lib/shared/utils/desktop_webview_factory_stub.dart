// SPDX-FileCopyrightText: 2026 Zampher
// SPDX-License-Identifier: MPL-2.0

import 'package:webview_flutter/webview_flutter.dart';

/// Creates a [WebViewController] on platforms without desktop WebView2 setup.
Future<WebViewController> createDesktopWebViewController() async {
  return WebViewController();
}

/// Stub for non-IO platforms.
Future<Uri> writeDesktopPreviewHtmlFile(String htmlContent) async {
  throw UnsupportedError('writeDesktopPreviewHtmlFile requires dart:io');
}
