// SPDX-FileCopyrightText: 2026 Zampher
// SPDX-License-Identifier: MPL-2.0

import 'package:flutter/foundation.dart' show kIsWeb;
import 'package:flutter/material.dart';
import 'package:webview_flutter/webview_flutter.dart';

import '../../../../shared/utils/html_stub.dart' if (dart.library.html) 'dart:html'
    as html;
import '../../../../shared/utils/ui_web_stub.dart'
    if (dart.library.html) 'dart:ui_web' as ui_web;
import '../../../../shared/utils/dialog_helper.dart';
import '../../../../shared/widgets/desktop_url_webview.dart';
import 'preview_viewport.dart';

/// Embeds the backend compare reader page (linked unified scroll).
class HtmlCompareReaderView extends StatefulWidget {
  const HtmlCompareReaderView({
    required this.readerUrl,
    this.linkedScroll = false,
    this.viewportController,
    super.key,
  });

  final String readerUrl;
  final bool linkedScroll;
  final PreviewViewportController? viewportController;

  @override
  State<HtmlCompareReaderView> createState() => _HtmlCompareReaderViewState();
}

class _HtmlCompareReaderViewState extends State<HtmlCompareReaderView> {
  String? _viewId;
  html.IFrameElement? _iframe;
  bool _iframeRegistered = false;
  String? _loadedReaderUrl;
  WebViewController? _webViewController;

  @override
  void initState() {
    super.initState();
    widget.viewportController?.addListener(_syncScaleToReader);
  }

  @override
  void didUpdateWidget(covariant HtmlCompareReaderView oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.viewportController != widget.viewportController) {
      oldWidget.viewportController?.removeListener(_syncScaleToReader);
      widget.viewportController?.addListener(_syncScaleToReader);
    }
    if (oldWidget.readerUrl != widget.readerUrl ||
        oldWidget.linkedScroll != widget.linkedScroll) {
      _scheduleReaderSync();
    }
  }

  @override
  void dispose() {
    widget.viewportController?.removeListener(_syncScaleToReader);
    super.dispose();
  }

  void _scheduleReaderSync() {
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (mounted) {
        _syncScaleToReader();
        _syncLinkedScrollToReader();
      }
    });
  }

  void _scheduleScaleSync() {
    _scheduleReaderSync();
  }

  Future<void> _syncLinkedScrollToReader() async {
    final bool linked = widget.linkedScroll;
    if (kIsWeb) {
      _syncLinkedScrollToWebIframe(linked);
      return;
    }

    final WebViewController? webController = _webViewController;
    if (webController == null) {
      return;
    }
    try {
      await webController.runJavaScript(
        'window.owlangsCompareReader && window.owlangsCompareReader.setLinkedScroll($linked);',
      );
    } catch (_) {
      // Reader may still be loading.
    }
  }

  void _syncLinkedScrollToWebIframe(bool linked) {
    final html.IFrameElement? frame = _iframe;
    if (frame == null) {
      return;
    }
    try {
      frame.contentWindow?.postMessage(
        <String, Object>{
          'type': 'owlangs-set-linked-scroll',
          'linked': linked,
        },
        '*',
      );
    } catch (_) {
      // Not ready yet.
    }
  }

  Future<void> _syncScaleToReader() async {
    final PreviewViewportController? controller = widget.viewportController;
    if (controller == null) {
      return;
    }
    final double scale = controller.scale;
    if (kIsWeb) {
      _syncScaleToWebIframe(scale);
      return;
    }

    final WebViewController? webController = _webViewController;
    if (webController == null) {
      return;
    }
    try {
      await webController.runJavaScript(
        'window.owlangsCompareReader && window.owlangsCompareReader.setScale($scale);',
      );
    } catch (_) {
      // Reader may still be loading.
    }
  }

  void _syncScaleToWebIframe(double scale) {
    final html.IFrameElement? frame = _iframe;
    if (frame == null) {
      return;
    }
    try {
      frame.contentWindow?.postMessage(
        <String, Object>{
          'type': 'owlangs-set-scale',
          'scale': scale,
        },
        '*',
      );
    } catch (_) {
      // Not ready yet.
    }
  }

  @override
  Widget build(BuildContext context) {
    if (widget.readerUrl.isEmpty) {
      return const SizedBox.shrink();
    }

    if (kIsWeb) {
      return _buildWebIframe();
    }

    return DesktopUrlWebView(
      pageUrl: widget.readerUrl,
      onControllerReady: (WebViewController controller) {
        _webViewController = controller;
        _scheduleScaleSync();
      },
      onPageFinished: _scheduleScaleSync,
      fallback: Center(
        child: Padding(
          padding: const EdgeInsets.all(24),
          child: Text(
            'Compare reader failed to load.\n${widget.readerUrl}',
            textAlign: TextAlign.center,
          ),
        ),
      ),
    );
  }

  Widget _buildWebIframe() {
    _viewId ??=
        'html_compare_reader_${widget.readerUrl.hashCode}_${identityHashCode(this)}';

    if (_iframe == null) {
      _iframe = html.IFrameElement()
        ..style.border = 'none'
        ..style.width = '100%'
        ..style.height = '100%'
        ..allowFullscreen = true
        ..id = 'html_compare_reader_iframe_$_viewId';

      _iframe!.setAttribute('data-preview-iframe', 'true');

      if (!_iframeRegistered) {
        try {
          // ignore: undefined_prefixed_name
          ui_web.platformViewRegistry.registerViewFactory(
            _viewId!,
            (int viewId) => _iframe!,
          );
          _iframeRegistered = true;
        } catch (_) {
          _iframeRegistered = true;
        }
      }

      _iframe!.onLoad.listen((_) {
        _scheduleReaderSync();
      });
    }

    if (_loadedReaderUrl != widget.readerUrl) {
      _loadedReaderUrl = widget.readerUrl;
      _iframe!.src = widget.readerUrl;
    }

    return ValueListenableBuilder<int>(
      valueListenable: DialogHelper.activeDialogCount,
      builder: (BuildContext context, int openDialogs, Widget? child) {
        if (openDialogs > 0) {
          return const ColoredBox(color: Colors.white);
        }
        return child!;
      },
      child: HtmlElementView(viewType: _viewId!),
    );
  }
}
