// SPDX-FileCopyrightText: 2026 Zampher
// SPDX-License-Identifier: MPL-2.0

import 'dart:async';

import 'package:flutter/material.dart';
import 'package:webview_flutter/webview_flutter.dart';
import 'package:webview_flutter_platform_interface/webview_flutter_platform_interface.dart';

import '../utils/app_logger.dart';
import '../utils/dialog_helper.dart';
import '../utils/desktop_webview_factory_stub.dart'
    if (dart.library.io) '../utils/desktop_webview_factory.dart';

void _desktopHtmlWebViewLog(String message, {LogLevel level = LogLevel.debug}) {
  AppLogger.log('DesktopHtmlWebView', message, level: level);
}

/// Handle for reading/driving scroll position on a [DesktopHtmlWebView].
class DesktopHtmlScrollController {
  _DesktopHtmlWebViewState? _state;

  void _attach(_DesktopHtmlWebViewState state) {
    _state = state;
  }

  void _detach(_DesktopHtmlWebViewState state) {
    if (identical(_state, state)) {
      _state = null;
    }
  }

  bool get isReady => _state?._controller != null && _state?._loading == false;

  /// Current document scroll ratio in \[0, 1\], or null if unavailable.
  Future<double?> getScrollRatio() async {
    return _state?._readScrollRatio();
  }

  /// Set document scroll position as a ratio in \[0, 1\].
  Future<void> setScrollRatio(double ratio) async {
    await _state?._setScrollRatio(ratio);
  }
}

/// Desktop HTML preview via WebView2 (temp file load, avoids data-URI crashes).
class DesktopHtmlWebView extends StatefulWidget {
  const DesktopHtmlWebView({
    required this.htmlContent,
    required this.fallback,
    super.key,
    this.scrollController,
  });

  final String htmlContent;
  final Widget fallback;

  /// Optional scroll driver for linked compare panes (poll + set via JS).
  final DesktopHtmlScrollController? scrollController;

  @override
  State<DesktopHtmlWebView> createState() => _DesktopHtmlWebViewState();
}

class _DesktopHtmlWebViewState extends State<DesktopHtmlWebView> {
  WebViewController? _controller;
  bool _loading = true;
  bool _failed = false;
  String? _loadedHtmlContent;

  static const String _scrollReadJs = '''
(function(){
  var el = document.scrollingElement || document.documentElement || document.body;
  if (!el) { return 0; }
  var max = el.scrollHeight - el.clientHeight;
  if (max <= 0) { return 0; }
  return el.scrollTop / max;
})()
''';

  @override
  void initState() {
    super.initState();
    widget.scrollController?._attach(this);
    _initController();
  }

  @override
  void didUpdateWidget(covariant DesktopHtmlWebView oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.scrollController != widget.scrollController) {
      oldWidget.scrollController?._detach(this);
      widget.scrollController?._attach(this);
    }
    if (oldWidget.htmlContent != widget.htmlContent) {
      _loadHtml(widget.htmlContent);
    }
  }

  @override
  void dispose() {
    widget.scrollController?._detach(this);
    super.dispose();
  }

  Future<void> _initController() async {
    if (WebViewPlatform.instance == null) {
      _desktopHtmlWebViewLog(
        'WebView platform not registered',
        level: LogLevel.error,
      );
      if (mounted) {
        setState(() {
          _failed = true;
          _loading = false;
        });
      }
      return;
    }

    try {
      final WebViewController controller = await createDesktopWebViewController();
      await controller.setJavaScriptMode(JavaScriptMode.unrestricted);
      await controller.setBackgroundColor(Colors.white);
      await controller.setNavigationDelegate(
        NavigationDelegate(
          onPageFinished: (String url) {
            _desktopHtmlWebViewLog('Page finished: $url');
          },
          onWebResourceError: (WebResourceError error) {
            _desktopHtmlWebViewLog(
              'Web resource error: ${error.description} (${error.url})',
              level: LogLevel.warn,
            );
          },
        ),
      );
      _controller = controller;
      await _loadHtml(widget.htmlContent);
    } catch (e, stackTrace) {
      _desktopHtmlWebViewLog(
        'Failed to init WebView: $e\n$stackTrace',
        level: LogLevel.error,
      );
      if (mounted) {
        setState(() {
          _failed = true;
          _loading = false;
        });
      }
    }
  }

  Future<double?> _readScrollRatio() async {
    final WebViewController? controller = _controller;
    if (controller == null || _loading || _failed) {
      return null;
    }
    try {
      final Object raw = await controller.runJavaScriptReturningResult(
        _scrollReadJs,
      );
      if (raw is num) {
        return raw.toDouble().clamp(0.0, 1.0);
      }
      if (raw is String) {
        final double? parsed = double.tryParse(raw);
        return parsed?.clamp(0.0, 1.0);
      }
      _desktopHtmlWebViewLog(
        'Unexpected scroll ratio type=${raw.runtimeType} value=$raw',
        level: LogLevel.warn,
      );
      return null;
    } catch (e) {
      _desktopHtmlWebViewLog('readScrollRatio failed: $e', level: LogLevel.warn);
      return null;
    }
  }

  Future<void> _setScrollRatio(double ratio) async {
    final WebViewController? controller = _controller;
    if (controller == null || _loading || _failed) {
      return;
    }
    final double clamped = ratio.clamp(0.0, 1.0);
    try {
      await controller.runJavaScript('''
(function(){
  var el = document.scrollingElement || document.documentElement || document.body;
  if (!el) { return; }
  var max = el.scrollHeight - el.clientHeight;
  if (max <= 0) { return; }
  el.scrollTop = $clamped * max;
})();
''');
    } catch (e) {
      _desktopHtmlWebViewLog('setScrollRatio failed: $e', level: LogLevel.warn);
    }
  }

  Future<void> _loadHtml(String htmlContent) async {
    final WebViewController? controller = _controller;
    if (controller == null || htmlContent.isEmpty) {
      return;
    }
    if (_loadedHtmlContent == htmlContent && !_loading) {
      return;
    }

    setState(() {
      _loading = true;
      _failed = false;
    });

    try {
      final Uri fileUri = await writeDesktopPreviewHtmlFile(htmlContent);
      _desktopHtmlWebViewLog(
        'Loading preview HTML from file (${htmlContent.length} chars): $fileUri',
      );
      await controller.loadRequest(fileUri);
      _loadedHtmlContent = htmlContent;
      if (mounted) {
        setState(() {
          _loading = false;
        });
      }
    } catch (e, stackTrace) {
      _desktopHtmlWebViewLog(
        'Failed to load HTML file: $e\n$stackTrace',
        level: LogLevel.error,
      );
      if (mounted) {
        setState(() {
          _failed = true;
          _loading = false;
        });
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    if (_failed) {
      return widget.fallback;
    }
    if (_loading || _controller == null) {
      return const Center(child: CircularProgressIndicator());
    }
    return ValueListenableBuilder<int>(
      valueListenable: DialogHelper.activeDialogCount,
      builder: (BuildContext context, int openDialogs, Widget? child) {
        if (openDialogs > 0) {
          return const ColoredBox(color: Colors.white);
        }
        return child!;
      },
      child: WebViewWidget(controller: _controller!),
    );
  }
}
