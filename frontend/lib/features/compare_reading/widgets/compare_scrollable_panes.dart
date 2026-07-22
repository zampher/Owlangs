// SPDX-FileCopyrightText: 2026 Zampher
// SPDX-License-Identifier: MPL-2.0

import 'package:flutter/material.dart';

import '../../../shared/widgets/unified_preview.dart';
import '../../translation/mixins/synchronized_scroll_mixin.dart';
import '../models/compare_document_model.dart';

/// Dual scrollable panes (MD/HTML/plain) with bindable scroll sync.
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

  @override
  void initState() {
    super.initState();
    _sourceScrollController = ScrollController();
    _targetScrollController = ScrollController();
    synchronizedScrollEnabled = widget.linkedScroll;
    initSynchronizedScroll(
      controller1: _sourceScrollController,
      controller2: _targetScrollController,
    );
  }

  @override
  void didUpdateWidget(covariant CompareScrollablePanes oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.linkedScroll != widget.linkedScroll) {
      synchronizedScrollEnabled = widget.linkedScroll;
    }
  }

  @override
  void dispose() {
    // Mixin removes listeners first; then dispose controllers.
    super.dispose();
    _sourceScrollController.dispose();
    _targetScrollController.dispose();
  }

  Widget _buildPane({
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
        contentType: doc.contentType == 'html' ? 'html' : 'md',
        taskId: 'compare-$paneKey',
        comparePaneKey: paneKey,
        embedInCompareScroll: true,
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

  @override
  Widget build(BuildContext context) {
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
