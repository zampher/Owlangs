// SPDX-FileCopyrightText: 2025 QinHan
// SPDX-License-Identifier: MPL-2.0

// Stub file for webview_flutter on Web platform
// Web platform uses iframe instead of WebView

import 'package:flutter/material.dart';

/// Stub JavaScriptMode for Web platform
enum JavaScriptMode {
  unrestricted,
  disabled;
}

/// Stub WebResourceError for Web platform
class WebResourceError {
  const WebResourceError({
    this.description = '',
    this.errorCode = 0,
    this.errorType = '',
    this.url = '',
  });
  final String description;
  final int errorCode;
  final String errorType;
  final String url;
}

/// Stub NavigationDelegate for Web platform
class NavigationDelegate {
  const NavigationDelegate({
    this.onPageFinished,
    this.onWebResourceError,
  });
  final void Function(String)? onPageFinished;
  final void Function(WebResourceError)? onWebResourceError;
}

/// Stub WebViewController for Web platform
class WebViewController {
  WebViewController();

  WebViewController setJavaScriptMode(JavaScriptMode mode) {
    // No-op on Web platform
    return this;
  }

  WebViewController setBackgroundColor(Color color) {
    // No-op on Web platform
    return this;
  }

  WebViewController setNavigationDelegate(NavigationDelegate delegate) {
    // No-op on Web platform
    return this;
  }

  Future<void> loadHtmlString(String html, {String? baseUrl}) async {
    // No-op on Web platform
  }
}

/// Stub WebViewWidget for Web platform
class WebViewWidget extends StatelessWidget {
  const WebViewWidget({
    required this.controller,
    super.key,
  });
  final WebViewController controller;

  @override
  Widget build(BuildContext context) {
    throw UnsupportedError(
      'WebViewWidget is not supported on Web platform. Use iframe instead.',
    );
  }
}
