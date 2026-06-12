// SPDX-FileCopyrightText: 2026 Zampher
// SPDX-License-Identifier: MPL-2.0

import 'package:flutter/material.dart';
import 'package:webview_flutter/webview_flutter.dart';
import 'package:webview_flutter_platform_interface/webview_flutter_platform_interface.dart';

import '../utils/app_logger.dart';
import '../utils/dialog_helper.dart';
import '../utils/desktop_webview_factory_stub.dart'
    if (dart.library.io) '../utils/desktop_webview_factory.dart';

void _desktopUrlWebViewLog(String message, {LogLevel level = LogLevel.debug}) {
  AppLogger.log('DesktopUrlWebView', message, level: level);
}

/// Desktop WebView that loads a remote/local page URL (compare reader shell).
class DesktopUrlWebView extends StatefulWidget {
  const DesktopUrlWebView({
    required this.pageUrl,
    required this.fallback,
    super.key,
    this.onControllerReady,
    this.onPageFinished,
  });

  final String pageUrl;
  final Widget fallback;
  final void Function(WebViewController controller)? onControllerReady;
  final VoidCallback? onPageFinished;

  @override
  State<DesktopUrlWebView> createState() => _DesktopUrlWebViewState();
}

class _DesktopUrlWebViewState extends State<DesktopUrlWebView> {
  WebViewController? _controller;
  bool _loading = true;
  bool _failed = false;
  String? _loadedPageUrl;

  @override
  void initState() {
    super.initState();
    _initController();
  }

  @override
  void didUpdateWidget(covariant DesktopUrlWebView oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.pageUrl != widget.pageUrl) {
      _loadPage(widget.pageUrl);
    }
  }

  Future<void> _initController() async {
    if (WebViewPlatform.instance == null) {
      _desktopUrlWebViewLog(
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
            _desktopUrlWebViewLog('Page finished: $url');
            widget.onPageFinished?.call();
          },
          onWebResourceError: (WebResourceError error) {
            _desktopUrlWebViewLog(
              'Web resource error: ${error.description} (${error.url})',
              level: LogLevel.warn,
            );
          },
        ),
      );
      _controller = controller;
      widget.onControllerReady?.call(controller);
      await _loadPage(widget.pageUrl);
    } catch (e, stackTrace) {
      _desktopUrlWebViewLog(
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

  Future<void> _loadPage(String pageUrl) async {
    final WebViewController? controller = _controller;
    if (controller == null || pageUrl.isEmpty) {
      return;
    }
    if (_loadedPageUrl == pageUrl && !_loading) {
      return;
    }

    setState(() {
      _loading = true;
      _failed = false;
    });

    try {
      _desktopUrlWebViewLog('Loading page: $pageUrl');
      await controller.loadRequest(Uri.parse(pageUrl));
      _loadedPageUrl = pageUrl;
      if (mounted) {
        setState(() {
          _loading = false;
        });
      }
    } catch (e, stackTrace) {
      _desktopUrlWebViewLog(
        'Failed to load page: $e\n$stackTrace',
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
