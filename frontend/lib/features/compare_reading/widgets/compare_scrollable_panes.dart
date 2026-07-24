// SPDX-FileCopyrightText: 2026 Zampher
// SPDX-License-Identifier: MPL-2.0

import 'package:flutter/foundation.dart' show kIsWeb;
import 'package:flutter/material.dart';

import '../../../shared/utils/app_logger.dart';
import '../../../shared/widgets/unified_preview.dart';
import '../../translation/mixins/synchronized_scroll_mixin.dart';
import '../models/compare_document_model.dart';
import 'compare_desktop_html_panes.dart';

/// Dual scrollable panes (MD/HTML/plain) with bindable scroll sync.
///
/// HTML on desktop uses [DesktopHtmlWebView] and must receive bounded
/// constraints (no outer [SingleChildScrollView]), otherwise Windows hits
/// `semantics.parentDataDirty` assertion storms. Scroll linking for desktop
/// HTML is handled by [CompareDesktopHtmlPanes] via JS bridges.
class CompareScrollablePanes extends StatefulWidget {
  const CompareScrollablePanes({
    required this.source,
    required this.target,
    required this.linkedScroll,
    super.key,
  });

  final CompareDocumentModel source;
  final CompareDocumentModel target;
  final bool linkedScroll;

  @override
  State<CompareScrollablePanes> createState() => _CompareScrollablePanesState();
}

class _CompareScrollablePanesState extends State<CompareScrollablePanes>
    with SynchronizedScrollMixin {
  late final ScrollController _sourceScrollController;
  late final ScrollController _targetScrollController;

  bool get _bothHtml =>
      widget.source.contentType == 'html' &&
      widget.target.contentType == 'html';

  bool get _desktopHtmlWebViews => _bothHtml && !kIsWeb;

  @override
  void initState() {
    super.initState();
    _sourceScrollController = ScrollController();
    _targetScrollController = ScrollController();
    // Desktop HTML WebViews sync via JS; Flutter ScrollControllers are unused.
    synchronizedScrollEnabled = widget.linkedScroll && !_desktopHtmlWebViews;
    initSynchronizedScroll(
      controller1: _sourceScrollController,
      controller2: _targetScrollController,
    );
    if (_desktopHtmlWebViews) {
      AppLogger.log(
        'CompareScrollablePanes',
        'Desktop HTML compare: WebView JS scroll bridge '
        '(linkedScroll=${widget.linkedScroll})',
        level: LogLevel.info,
      );
    }
  }

  @override
  void didUpdateWidget(covariant CompareScrollablePanes oldWidget) {
    super.didUpdateWidget(oldWidget);
    synchronizedScrollEnabled = widget.linkedScroll && !_desktopHtmlWebViews;
  }

  @override
  void dispose() {
    // Mixin removes listeners first; then dispose controllers.
    super.dispose();
    _sourceScrollController.dispose();
    _targetScrollController.dispose();
  }

  Widget _buildHtmlPane({
    required CompareDocumentModel doc,
    required String paneKey,
  }) {
    final String content = doc.textContent ?? '';
    return Scrollbar(
      controller: paneKey == 'source'
          ? _sourceScrollController
          : _targetScrollController,
      thumbVisibility: true,
      child: SingleChildScrollView(
        controller: paneKey == 'source'
            ? _sourceScrollController
            : _targetScrollController,
        padding: const EdgeInsets.fromLTRB(12, 8, 12, 16),
        child: UnifiedPreview(
          content: content,
          contentType: 'html',
          taskId: 'compare-$paneKey',
          comparePaneKey: paneKey,
          embedInCompareScroll: true,
        ),
      ),
    );
  }

  Widget _buildTextPane({
    required CompareDocumentModel doc,
    required ScrollController controller,
    required String paneKey,
  }) {
    final String content = doc.textContent ?? '';
    final Widget body;
    if (doc.contentType == 'plain') {
      body = SelectableText(
        content,
        style: const TextStyle(fontFamily: 'monospace', fontSize: 13, height: 1.45),
      );
    } else {
      body = UnifiedPreview(
        content: content,
        contentType: 'md',
        taskId: 'compare-$paneKey',
        comparePaneKey: paneKey,
        embedInCompareScroll: false,
      );
    }

    return Scrollbar(
      controller: controller,
      thumbVisibility: true,
      child: SingleChildScrollView(
        controller: controller,
        padding: const EdgeInsets.fromLTRB(12, 8, 12, 16),
        child: body,
      ),
    );
  }

  Widget _buildPane({
    required CompareDocumentModel doc,
    required ScrollController controller,
    required String paneKey,
  }) {
    if (doc.contentType == 'html') {
      return _buildHtmlPane(doc: doc, paneKey: paneKey);
    }
    return _buildTextPane(
      doc: doc,
      controller: controller,
      paneKey: paneKey,
    );
  }

  @override
  Widget build(BuildContext context) {
    if (_desktopHtmlWebViews) {
      return CompareDesktopHtmlPanes(
        sourceHtml: widget.source.textContent ?? '',
        targetHtml: widget.target.textContent ?? '',
        linkedScroll: widget.linkedScroll,
      );
    }

    return Row(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: <Widget>[
        Expanded(
          child: _buildPane(
            doc: widget.source,
            controller: _sourceScrollController,
            paneKey: 'source',
          ),
        ),
        const VerticalDivider(width: 1),
        Expanded(
          child: _buildPane(
            doc: widget.target,
            controller: _targetScrollController,
            paneKey: 'target',
          ),
        ),
      ],
    );
  }
}
