// SPDX-FileCopyrightText: 2026 Zampher
// SPDX-License-Identifier: MPL-2.0

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

/// Desktop HTML preview via WebView2 (temp file load, avoids data-URI crashes).
class DesktopHtmlWebView extends StatefulWidget {
  const DesktopHtmlWebView({
    required this.htmlContent,
    required this.fallback,
    super.key,
  });

  final String htmlContent;
  final Widget fallback;

  @override
  State<DesktopHtmlWebView> createState() => _DesktopHtmlWebViewState();
}

class _DesktopHtmlWebViewState extends State<DesktopHtmlWebView> {
  WebViewController? _controller;
  bool _loading = true;
  bool _failed = false;
  String? _loadedHtmlContent;

  @override
  void initState() {
    super.initState();
    _initController();
  }

  @override
  void didUpdateWidget(covariant DesktopHtmlWebView oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.htmlContent != widget.htmlContent) {
      _loadHtml(widget.htmlContent);
    }
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
