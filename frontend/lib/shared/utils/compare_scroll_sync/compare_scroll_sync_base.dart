// SPDX-FileCopyrightText: 2026 Zampher
// SPDX-License-Identifier: MPL-2.0

import 'package:flutter/widgets.dart';

import 'compare_scroll_sync_web_binding.dart'
    if (dart.library.io) 'compare_scroll_sync_web_binding_stub.dart' as web;

/// Pane id for the source (left) panel in full-document compare preview.
const String compareScrollPaneSource = 'source';

/// Pane id for the target (right) panel in full-document compare preview.
const String compareScrollPaneTarget = 'target';

/// Callbacks for synchronizing PDF page navigation between compare panes.
class PdfPageSyncHandle {
  const PdfPageSyncHandle({
    required this.jumpToPage,
  });

  final void Function(int page) jumpToPage;
}

/// Coordinates a single master scrollbar for web HTML compare preview.
class CompareScrollSyncGroup {
  CompareScrollSyncGroup({this.enabled = false});

  bool enabled;
  bool _propagating = false;

  /// Max vertical scroll range across all registered panes (pixels).
  double masterScrollExtent = 0;

  final Map<String, PdfPageSyncHandle> _pdfHandles =
      <String, PdfPageSyncHandle>{};

  ScrollController? _masterController;
  VoidCallback? _onMetricsChanged;

  bool get isPropagating => _propagating;

  void beginPropagation() {
    _propagating = true;
  }

  void endPropagation() {
    _propagating = false;
  }

  void notifyMetricsChanged() {
    _onMetricsChanged?.call();
  }

  void attachMasterScroll({
    required ScrollController controller,
    required VoidCallback onMetricsChanged,
  }) {
    detachMasterScroll();
    _masterController = controller;
    _onMetricsChanged = onMetricsChanged;
    controller.addListener(_handleMasterControllerChanged);
    refreshScrollMetrics();
  }

  void detachMasterScroll() {
    _masterController?.removeListener(_handleMasterControllerChanged);
    _masterController = null;
    _onMetricsChanged = null;
  }

  void _handleMasterControllerChanged() {
    final ScrollController? controller = _masterController;
    if (!enabled || _propagating || controller == null || !controller.hasClients) {
      return;
    }
    web.applyMasterOffset(this, controller.offset);
  }

  void nudgeMasterScroll(double deltaPixels) {
    if (!enabled) {
      return;
    }
    final ScrollController? controller = _masterController;
    if (controller == null || !controller.hasClients) {
      return;
    }
    final double maxOffset = masterScrollExtent;
    final double nextOffset =
        (controller.offset + deltaPixels).clamp(0.0, maxOffset);
    if (nextOffset == controller.offset) {
      return;
    }
    controller.jumpTo(nextOffset);
  }

  void registerWebIframe(String paneId, dynamic iframe) {
    web.registerWebIframe(this, paneId, iframe);
  }

  void refreshScrollMetrics() {
    web.refreshScrollMetrics(this);
  }

  void setCompareScrollUiEnabled(bool value) {
    enabled = value;
    web.setCompareScrollUiEnabled(this, value);
    if (value) {
      refreshScrollMetrics();
    }
  }

  void registerPdfPane(String paneId, PdfPageSyncHandle handle) {
    _pdfHandles[paneId] = handle;
  }

  void unregisterPane(String paneId) {
    _pdfHandles.remove(paneId);
    web.unregisterWebPane(this, paneId);
    refreshScrollMetrics();
  }

  void notifyPdfPageChanged(String paneId, int page) {
    if (!enabled || _propagating) {
      return;
    }
    _propagating = true;
    for (final MapEntry<String, PdfPageSyncHandle> entry
        in _pdfHandles.entries) {
      if (entry.key == paneId) {
        continue;
      }
      entry.value.jumpToPage(page);
    }
    _propagating = false;
  }

  void dispose() {
    detachMasterScroll();
    web.disposeWeb(this);
    _pdfHandles.clear();
  }
}
