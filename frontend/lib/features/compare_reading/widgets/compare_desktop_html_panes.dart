// SPDX-FileCopyrightText: 2026 Zampher
// SPDX-License-Identifier: MPL-2.0

import 'dart:async';

import 'package:flutter/material.dart';

import '../../../shared/utils/app_logger.dart';
import '../../translation/utils/text_utils.dart' show extractTextFromHtml;
import '../../../shared/widgets/desktop_html_webview.dart';

/// Side-by-side desktop HTML compare with proportional WebView scroll linking.
///
/// Uses periodic [runJavaScriptReturningResult] polling (not JS channels),
/// which is reliable on Windows WebView2 / webview_win_floating.
class CompareDesktopHtmlPanes extends StatefulWidget {
  const CompareDesktopHtmlPanes({
    required this.sourceHtml,
    required this.targetHtml,
    required this.linkedScroll,
    super.key,
  });

  final String sourceHtml;
  final String targetHtml;
  final bool linkedScroll;

  @override
  State<CompareDesktopHtmlPanes> createState() =>
      _CompareDesktopHtmlPanesState();
}

class _CompareDesktopHtmlPanesState extends State<CompareDesktopHtmlPanes> {
  final DesktopHtmlScrollController _sourceScroll =
      DesktopHtmlScrollController();
  final DesktopHtmlScrollController _targetScroll =
      DesktopHtmlScrollController();

  Timer? _pollTimer;
  bool _syncing = false;
  double _lastSourceRatio = 0;
  double _lastTargetRatio = 0;
  int _pollLogCounter = 0;

  static const Duration _pollInterval = Duration(milliseconds: 80);
  static const double _ratioEpsilon = 0.008;

  @override
  void initState() {
    super.initState();
    _restartPolling();
  }

  @override
  void didUpdateWidget(covariant CompareDesktopHtmlPanes oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.linkedScroll != widget.linkedScroll ||
        oldWidget.sourceHtml != widget.sourceHtml ||
        oldWidget.targetHtml != widget.targetHtml) {
      AppLogger.log(
        'CompareDesktopHtmlPanes',
        'linkedScroll=${widget.linkedScroll} '
        'sourceLen=${widget.sourceHtml.length} '
        'targetLen=${widget.targetHtml.length}',
        level: LogLevel.info,
      );
      _lastSourceRatio = 0;
      _lastTargetRatio = 0;
      _restartPolling();
    }
  }

  @override
  void dispose() {
    _pollTimer?.cancel();
    super.dispose();
  }

  void _restartPolling() {
    _pollTimer?.cancel();
    if (!widget.linkedScroll) {
      AppLogger.log(
        'CompareDesktopHtmlPanes',
        'Scroll poll stopped (linkedScroll=false)',
        level: LogLevel.info,
      );
      return;
    }
    AppLogger.log(
      'CompareDesktopHtmlPanes',
      'Scroll poll started interval=${_pollInterval.inMilliseconds}ms',
      level: LogLevel.info,
    );
    _pollTimer = Timer.periodic(_pollInterval, (_) {
      unawaited(_pollAndSync());
    });
  }

  Future<void> _pollAndSync() async {
    if (!mounted || !widget.linkedScroll || _syncing) {
      return;
    }
    if (!_sourceScroll.isReady || !_targetScroll.isReady) {
      return;
    }

    final double? sourceRatio = await _sourceScroll.getScrollRatio();
    final double? targetRatio = await _targetScroll.getScrollRatio();
    if (sourceRatio == null || targetRatio == null) {
      return;
    }

    _pollLogCounter++;
    if (_pollLogCounter % 25 == 1) {
      AppLogger.log(
        'CompareDesktopHtmlPanes',
        'poll source=${sourceRatio.toStringAsFixed(3)} '
        'target=${targetRatio.toStringAsFixed(3)}',
        level: LogLevel.debug,
      );
    }

    final double sourceDelta = (sourceRatio - _lastSourceRatio).abs();
    final double targetDelta = (targetRatio - _lastTargetRatio).abs();

    // Prefer the pane that moved more since last poll.
    if (sourceDelta < _ratioEpsilon && targetDelta < _ratioEpsilon) {
      _lastSourceRatio = sourceRatio;
      _lastTargetRatio = targetRatio;
      return;
    }

    _syncing = true;
    try {
      if (sourceDelta >= targetDelta && sourceDelta >= _ratioEpsilon) {
        await _targetScroll.setScrollRatio(sourceRatio);
        _lastSourceRatio = sourceRatio;
        _lastTargetRatio = sourceRatio;
      } else if (targetDelta >= _ratioEpsilon) {
        await _sourceScroll.setScrollRatio(targetRatio);
        _lastSourceRatio = targetRatio;
        _lastTargetRatio = targetRatio;
      }
    } finally {
      _syncing = false;
    }
  }

  Widget _fallback(String html) {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(12),
      child: SelectableText(
        extractTextFromHtml(html),
        style: const TextStyle(fontSize: 13, height: 1.45),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Row(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: <Widget>[
        Expanded(
          child: DesktopHtmlWebView(
            htmlContent: widget.sourceHtml,
            fallback: _fallback(widget.sourceHtml),
            scrollController: _sourceScroll,
          ),
        ),
        const VerticalDivider(width: 1),
        Expanded(
          child: DesktopHtmlWebView(
            htmlContent: widget.targetHtml,
            fallback: _fallback(widget.targetHtml),
            scrollController: _targetScroll,
          ),
        ),
      ],
    );
  }
}
