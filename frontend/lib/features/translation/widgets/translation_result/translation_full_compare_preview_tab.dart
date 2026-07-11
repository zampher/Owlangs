// SPDX-FileCopyrightText: 2026 Zampher
// SPDX-License-Identifier: MPL-2.0

import 'dart:async';

import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../../app/app_config.dart';
import '../../../../l10n/app_localizations.dart';
import '../../../../shared/services/translation_service.dart';
import '../../../../shared/utils/app_logger.dart';
import '../../providers/format_settings_provider.dart';
import '../../utils/segment_type_utils.dart';
import '../pdf_continuous_scroll_view.dart';
import '../pdf_compare_continuous_view.dart';
import '../pdf_preview.dart';
import 'segment_pdf_typography_dialog.dart';
import 'html_compare_reader_view.dart';
import 'image_overlay_preview.dart';
import 'pdf_compare_layout_mode.dart';
import 'pdf_revision_segment_panel_builder.dart';
import 'preview_selection.dart';
import 'preview_url_utils.dart';
import 'preview_viewport.dart';

/// Side-by-side source vs translation export preview for all preview modes.
class TranslationFullComparePreviewTab extends ConsumerStatefulWidget {
  const TranslationFullComparePreviewTab({
    required this.taskId,
    required this.baseMode,
    required this.isPdfSource,
    this.isImageSource = false,
    this.overlayBboxReferenceSize,
    required this.isPdfWorkflow,
    this.translatedPdfUrl,
    this.translatedImageUrl,
    this.pdfRenderRevision = 0,
    this.pdfRenderRevisionListenable,
    this.pdfPreviewDirtySegmentsListenable,
    this.segmentUiRevisionListenable,
    this.translatedHtmlUrl,
    this.initialSyncScroll = false,
    this.initialLayoutMode = PdfCompareLayoutMode.comparePreview,
    this.pdfRevisionSegmentPanelBuilder,
    this.onBatchFontApply,
    this.onBatchFontSizeStep,
    this.onBatchLeadingApply,
    this.getFilteredSelectableSegmentIndices,
    this.onPdfRevisionModeEntered,
    this.pdfPreviewJumpPageListenable,
    this.pdfPreviewJumpPageTriggerListenable,
    this.autoFollowSegmentPdfPageListenable,
    this.pdfHighlightBboxPageListenable,
    this.pdfHighlightBboxListenable,
    this.sourceHighlightBboxListenable,
    this.showSelectedSegmentMarkerListenable,
    this.onShowSelectedSegmentMarkerChanged,
    this.onAutoFollowSegmentPdfPageChanged,
    this.segmentScrollController,
    super.key,
    this.onRequestPreviewSettings,
    this.onDownload,
    this.onShowDownload,
    this.onSyncScrollChanged,
    this.bboxEditModeListenable,
    this.onBboxEditModeChanged,
    this.onBboxOverrideChanged,
    this.onBboxOverrideReset,
  });

  final String taskId;
  final TranslationPreviewMode baseMode;
  final bool isPdfSource;
  final bool isImageSource;

  /// Raster reference size for bbox mapping (`overlay_source_image_size` from API).
  final Size? overlayBboxReferenceSize;
  final bool isPdfWorkflow;
  final String? translatedPdfUrl;
  final String? translatedImageUrl;
  final int pdfRenderRevision;
  final ValueListenable<int>? pdfRenderRevisionListenable;
  final ValueListenable<Set<int>>? pdfPreviewDirtySegmentsListenable;
  final ValueListenable<int>? segmentUiRevisionListenable;
  final String? translatedHtmlUrl;
  final bool initialSyncScroll;
  final PdfCompareLayoutMode initialLayoutMode;
  final PdfRevisionSegmentPanelBuilder? pdfRevisionSegmentPanelBuilder;
  final Future<void> Function(Set<int> selectedIndices)? onBatchFontApply;
  final Future<void> Function(Set<int> selectedIndices, double delta)?
      onBatchFontSizeStep;
  final Future<void> Function(Set<int> selectedIndices)? onBatchLeadingApply;
  final Set<int> Function()? getFilteredSelectableSegmentIndices;
  final Future<void> Function()? onPdfRevisionModeEntered;
  final ValueListenable<int?>? pdfPreviewJumpPageListenable;
  final ValueListenable<int>? pdfPreviewJumpPageTriggerListenable;
  final ValueListenable<bool>? autoFollowSegmentPdfPageListenable;
  final ValueListenable<int?>? pdfHighlightBboxPageListenable;
  final ValueListenable<List<List<double>>?>? pdfHighlightBboxListenable;
  /// Original (non-overridden) bboxes for source-side PDF preview highlight.
  final ValueListenable<List<List<double>>?>? sourceHighlightBboxListenable;
  final ValueListenable<bool>? showSelectedSegmentMarkerListenable;
  final ValueChanged<bool>? onShowSelectedSegmentMarkerChanged;
  final ValueChanged<bool>? onAutoFollowSegmentPdfPageChanged;
  final ScrollController? segmentScrollController;
  final Future<PreviewSelection?> Function()? onRequestPreviewSettings;
  final void Function(String format, String url)? onDownload;
  final Future<void> Function()? onShowDownload;
  final ValueChanged<bool>? onSyncScrollChanged;

  /// Whether bbox edit mode is active.
  final ValueListenable<bool>? bboxEditModeListenable;

  /// Called when the user toggles the bbox edit mode checkbox.
  final ValueChanged<bool>? onBboxEditModeChanged;

  /// Called when the user finishes dragging, with the new bbox in PDF points.
  final void Function(int bboxIndex, List<double> bbox)? onBboxOverrideChanged;

  /// Called when the user taps reset on a specific bbox overlay.
  final void Function(int bboxIndex)? onBboxOverrideReset;

  @override
  ConsumerState<TranslationFullComparePreviewTab> createState() =>
      _TranslationFullComparePreviewTabState();
}

class _TranslationFullComparePreviewTabState
    extends ConsumerState<TranslationFullComparePreviewTab> {
  late final PreviewViewportController _viewportController;
  late final PreviewFullscreenOverlay _fullscreenOverlay;
  late bool _syncScrollEnabled;
  bool _isFullscreen = false;
  PdfCompareLayoutMode _layoutMode = PdfCompareLayoutMode.comparePreview;
  bool _autoRefreshPdf = true;
  int _displayPdfRevision = 0;
  Set<int> _displayDirtySegmentIndices = <int>{};
  int? _highlightBboxPage;
  List<List<double>>? _highlightBboxes;
  /// Original (non-overridden) bboxes for source-side PDF highlight.
  List<List<double>>? _sourceHighlightBboxes;
  bool _bboxEditMode = true;
  bool _autoRotationEnabled = true;
  double _autoRotationAspectRatio = kDefaultAutoRotationAspectRatio;
  int _autoRotationDegrees = kDefaultAutoRotationDegrees;
  int _pdfPreviewManualRefreshNonce = 0;
  bool _pdfPreviewRefreshing = false;
  int _pdfPreviewLoadGeneration = 0;
  late final TextEditingController _autoRotationRatioController;
  late final TextEditingController _autoRotationDegreesController;
  bool _autoFollowSegmentPdfPage = true;
  bool _showSelectedSegmentMarker = true;

  final ValueNotifier<Set<int>> _selectedSegmentIndicesNotifier =
      ValueNotifier<Set<int>>(<int>{});
  final PdfContinuousScrollController _pdfNavigationController =
      PdfContinuousScrollController();
  final PdfCompareContinuousScrollController _pdfCompareNavigationController =
      PdfCompareContinuousScrollController();
  int _comparePdfCurrentPage = 1;
  int _comparePdfTotalPages = 0;
  bool _revisionLinkedScrollEnabled = true;
  bool _previewSignalsAlive = true;
  final GlobalKey _pdfCompareViewKey = GlobalKey();
  final List<(Listenable, VoidCallback)> _previewSignalBindings =
      <(Listenable, VoidCallback)>[];

  bool get _showsRevisionLinkedScroll =>
      _layoutMode == PdfCompareLayoutMode.compareRevision &&
      _supportsRevisionPreview;

  bool get _supportsRevisionPreview =>
      widget.pdfRevisionSegmentPanelBuilder != null &&
      ((_isPdfRevisionSource && widget.translatedPdfUrl != null) ||
          (_isImageRevisionSource && widget.translatedImageUrl != null));

  bool get _isPdfRevisionSource =>
      widget.baseMode == TranslationPreviewMode.pdfPreserve &&
      widget.isPdfSource;

  bool get _isImageRevisionSource =>
      widget.baseMode == TranslationPreviewMode.imageOriginalLayout &&
      widget.isImageSource;

  @override
  void initState() {
    super.initState();
    _syncScrollEnabled = widget.initialSyncScroll;
    _layoutMode = widget.initialLayoutMode;
    _displayPdfRevision = widget.pdfRenderRevision;
    AppLogger.log(
      'TranslationFullComparePreviewTab',
      'initState task=${widget.taskId} layout=$_layoutMode '
      'revisionReady=$_supportsRevisionPreview',
      level: LogLevel.info,
    );
    _viewportController = PreviewViewportController();
    _autoRotationRatioController = TextEditingController(
      text: _autoRotationAspectRatio.toStringAsFixed(0),
    );
    _autoRotationDegreesController = TextEditingController(
      text: _autoRotationDegrees.toString(),
    );
    _fullscreenOverlay = PreviewFullscreenOverlay(
      onExit: () {
        if (mounted) {
          setState(() {
            _isFullscreen = false;
          });
        }
      },
    );
    _previewSignalsAlive = _bindPreviewSignalListeners();
    if (_previewSignalsAlive) {
      _onPdfBboxHighlightChanged();
      _onBboxEditModeChanged();
      _onAutoFollowSegmentPdfPageChanged();
      _onShowSelectedSegmentMarkerChanged();
    }
  }

  @override
  void didUpdateWidget(covariant TranslationFullComparePreviewTab oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.initialSyncScroll != widget.initialSyncScroll) {
      _syncScrollEnabled = widget.initialSyncScroll;
    }
    if (oldWidget.pdfRenderRevisionListenable !=
        widget.pdfRenderRevisionListenable) {
      _rebindPreviewSignal(
        oldWidget.pdfRenderRevisionListenable,
        widget.pdfRenderRevisionListenable,
        _onPdfRevisionListenableChanged,
      );
      if (_previewSignalsAlive) {
        _onPdfRevisionListenableChanged();
      }
    }
    if (oldWidget.pdfPreviewJumpPageTriggerListenable !=
        widget.pdfPreviewJumpPageTriggerListenable) {
      _rebindPreviewSignal(
        oldWidget.pdfPreviewJumpPageTriggerListenable,
        widget.pdfPreviewJumpPageTriggerListenable,
        _onPdfPreviewJumpPageRequested,
      );
    }
    if (oldWidget.pdfHighlightBboxListenable !=
            widget.pdfHighlightBboxListenable ||
        oldWidget.pdfHighlightBboxPageListenable !=
            widget.pdfHighlightBboxPageListenable) {
      _rebindPreviewSignal(
        oldWidget.pdfHighlightBboxListenable,
        widget.pdfHighlightBboxListenable,
        _onPdfBboxHighlightChanged,
      );
      _rebindPreviewSignal(
        oldWidget.pdfHighlightBboxPageListenable,
        widget.pdfHighlightBboxPageListenable,
        _onPdfBboxHighlightChanged,
      );
      if (_previewSignalsAlive) {
        _onPdfBboxHighlightChanged();
      }
    }
    if (oldWidget.sourceHighlightBboxListenable !=
        widget.sourceHighlightBboxListenable) {
      _rebindPreviewSignal(
        oldWidget.sourceHighlightBboxListenable,
        widget.sourceHighlightBboxListenable,
        _onPdfBboxHighlightChanged,
      );
      if (_previewSignalsAlive) {
        _onPdfBboxHighlightChanged();
      }
    }
    if (oldWidget.bboxEditModeListenable != widget.bboxEditModeListenable) {
      _rebindPreviewSignal(
        oldWidget.bboxEditModeListenable,
        widget.bboxEditModeListenable,
        _onBboxEditModeChanged,
      );
      if (_previewSignalsAlive) {
        _onBboxEditModeChanged();
      }
    }
    if (oldWidget.autoFollowSegmentPdfPageListenable !=
        widget.autoFollowSegmentPdfPageListenable) {
      _rebindPreviewSignal(
        oldWidget.autoFollowSegmentPdfPageListenable,
        widget.autoFollowSegmentPdfPageListenable,
        _onAutoFollowSegmentPdfPageChanged,
      );
      if (_previewSignalsAlive) {
        _onAutoFollowSegmentPdfPageChanged();
      }
    }
    if (oldWidget.showSelectedSegmentMarkerListenable !=
        widget.showSelectedSegmentMarkerListenable) {
      _rebindPreviewSignal(
        oldWidget.showSelectedSegmentMarkerListenable,
        widget.showSelectedSegmentMarkerListenable,
        _onShowSelectedSegmentMarkerChanged,
      );
      if (_previewSignalsAlive) {
        _onShowSelectedSegmentMarkerChanged();
      }
    }
    if (oldWidget.pdfRenderRevision != widget.pdfRenderRevision &&
        widget.pdfRenderRevisionListenable == null) {
      _maybeApplyPdfRevision(widget.pdfRenderRevision);
    }
  }

  @override
  void setState(VoidCallback fn) {
    super.setState(fn);
    if (_isFullscreen) {
      _fullscreenOverlay.markNeedsBuild();
    }
  }

  @override
  void dispose() {
    AppLogger.log(
      'TranslationFullComparePreviewTab',
      'dispose task=${widget.taskId}',
      level: LogLevel.info,
    );
    _unbindPreviewSignalListeners();
    _pdfNavigationController.dispose();
    _pdfCompareNavigationController.dispose();
    _selectedSegmentIndicesNotifier.dispose();
    _autoRotationRatioController.dispose();
    _autoRotationDegreesController.dispose();
    _fullscreenOverlay.dispose();
    _viewportController.dispose();
    super.dispose();
  }

  void _unbindPreviewSignalListeners() {
    final List<(Listenable, VoidCallback)> bindings =
        List<(Listenable, VoidCallback)>.from(_previewSignalBindings);
    _previewSignalBindings.clear();
    for (final (Listenable target, VoidCallback listener) in bindings) {
      try {
        target.removeListener(listener);
      } on AssertionError {
        // Parent notifier already disposed.
      }
    }
  }

  bool _tryAddPreviewSignalListener(
    Listenable? target,
    VoidCallback listener,
  ) {
    if (target == null) {
      return true;
    }
    try {
      target.addListener(listener);
      _previewSignalBindings.add((target, listener));
      return true;
    } on AssertionError {
      return false;
    }
  }

  void _rebindPreviewSignal(
    Listenable? oldTarget,
    Listenable? newTarget,
    VoidCallback listener,
  ) {
    if (oldTarget != null) {
      try {
        oldTarget.removeListener(listener);
      } on AssertionError {
        // Parent notifier already disposed.
      }
      _previewSignalBindings.remove((oldTarget, listener));
    }
    if (!_tryAddPreviewSignalListener(newTarget, listener)) {
      _previewSignalsAlive = false;
    }
  }

  bool _bindPreviewSignalListeners() {
    _unbindPreviewSignalListeners();
    var alive = true;
    alive = _tryAddPreviewSignalListener(
          widget.pdfRenderRevisionListenable,
          _onPdfRevisionListenableChanged,
        ) &&
        alive;
    alive = _tryAddPreviewSignalListener(
          widget.pdfPreviewJumpPageTriggerListenable,
          _onPdfPreviewJumpPageRequested,
        ) &&
        alive;
    alive = _tryAddPreviewSignalListener(
          widget.pdfHighlightBboxListenable,
          _onPdfBboxHighlightChanged,
        ) &&
        alive;
    alive = _tryAddPreviewSignalListener(
          widget.pdfHighlightBboxPageListenable,
          _onPdfBboxHighlightChanged,
        ) &&
        alive;
    alive = _tryAddPreviewSignalListener(
          widget.sourceHighlightBboxListenable,
          _onPdfBboxHighlightChanged,
        ) &&
        alive;
    alive = _tryAddPreviewSignalListener(
          widget.bboxEditModeListenable,
          _onBboxEditModeChanged,
        ) &&
        alive;
    alive = _tryAddPreviewSignalListener(
          widget.autoFollowSegmentPdfPageListenable,
          _onAutoFollowSegmentPdfPageChanged,
        ) &&
        alive;
    alive = _tryAddPreviewSignalListener(
          widget.showSelectedSegmentMarkerListenable,
          _onShowSelectedSegmentMarkerChanged,
        ) &&
        alive;
    _previewSignalsAlive = alive;
    return alive;
  }

  Widget _buildStalePreviewPlaceholder(AppLocalizations l10n) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(24),
        child: Text(
          l10n.translationPreviewStaleSession,
          textAlign: TextAlign.center,
          style: Theme.of(context).textTheme.bodyMedium,
        ),
      ),
    );
  }

  void _onPdfRevisionListenableChanged() {
    final int revision =
        widget.pdfRenderRevisionListenable?.value ?? widget.pdfRenderRevision;
    _maybeApplyPdfRevision(revision);
  }

  void _onPdfPreviewJumpPageRequested() {
    final int? pageNumber = widget.pdfPreviewJumpPageListenable?.value;
    if (pageNumber == null || pageNumber < 1) {
      return;
    }
    if (_layoutMode == PdfCompareLayoutMode.compareRevision) {
      unawaited(_pdfCompareNavigationController.jumpToPage(pageNumber));
    } else {
      unawaited(_pdfNavigationController.jumpToPage(pageNumber));
    }
  }

  void _onPdfBboxHighlightChanged() {
    final int? page = widget.pdfHighlightBboxPageListenable?.value;
    final List<List<double>>? bboxes =
        widget.pdfHighlightBboxListenable?.value;
    final List<List<double>>? sourceBboxes =
        widget.sourceHighlightBboxListenable?.value;
    if (bboxes != null && bboxes.isNotEmpty) {
      setState(() {
        _highlightBboxes = bboxes;
        _sourceHighlightBboxes = sourceBboxes;
        if (page != null) {
          _highlightBboxPage = page;
        } else if (_isImageRevisionSource) {
          _highlightBboxPage = 1;
        } else {
          _highlightBboxPage = null;
        }
      });
      return;
    }
    setState(() {
      _highlightBboxPage = null;
      _highlightBboxes = null;
      _sourceHighlightBboxes = null;
    });
  }

  void _onBboxEditModeChanged() {
    final bool editMode = widget.bboxEditModeListenable?.value ?? false;
    if (mounted) {
      setState(() {
        _bboxEditMode = editMode;
      });
    }
  }

  void _onAutoFollowSegmentPdfPageChanged() {
    final bool enabled =
        widget.autoFollowSegmentPdfPageListenable?.value ?? true;
    if (mounted) {
      setState(() {
        _autoFollowSegmentPdfPage = enabled;
      });
    }
  }

  void _onShowSelectedSegmentMarkerChanged() {
    final bool enabled =
        widget.showSelectedSegmentMarkerListenable?.value ?? true;
    if (mounted) {
      setState(() {
        _showSelectedSegmentMarker = enabled;
      });
    }
  }

  /// Called by [PdfContinuousPage] when dragging ends in the edit overlay.
  /// [pdfRect] is already in PDF points (converted by PdfContinuousPage).
  void _onEditBboxChanged(int bboxIndex, Rect pdfRect) {
    if (widget.onBboxOverrideChanged == null) {
      return;
    }
    widget.onBboxOverrideChanged!(bboxIndex, <double>[
      pdfRect.left,
      pdfRect.top,
      pdfRect.right,
      pdfRect.bottom,
    ]);
  }

  void _onEditBboxReset(int bboxIndex) {
    widget.onBboxOverrideReset?.call(bboxIndex);
  }

  void _markPdfPreviewRefreshing() {
    _pdfPreviewLoadGeneration++;
    if (!_pdfPreviewRefreshing && mounted) {
      setState(() {
        _pdfPreviewRefreshing = true;
      });
    }
  }

  VoidCallback _pdfPreviewLoadSettledHandler() {
    final int expectedGeneration = _pdfPreviewLoadGeneration;
    return () {
      if (!mounted || expectedGeneration != _pdfPreviewLoadGeneration) {
        return;
      }
      if (_pdfPreviewRefreshing) {
        setState(() {
          _pdfPreviewRefreshing = false;
        });
      }
    };
  }

  Widget _wrapPdfPreviewRefreshingOverlay(
    AppLocalizations l10n,
    Widget child,
  ) {
    if (!_pdfPreviewRefreshing) {
      return child;
    }
    return Stack(
      fit: StackFit.expand,
      children: <Widget>[
        child,
        Positioned.fill(
          child: IgnorePointer(
            child: ColoredBox(
              color: Colors.black.withValues(alpha: 0.12),
              child: Center(
                child: Material(
                  elevation: 2,
                  borderRadius: BorderRadius.circular(8),
                  child: Padding(
                    padding: const EdgeInsets.symmetric(
                      horizontal: 16,
                      vertical: 12,
                    ),
                    child: Row(
                      mainAxisSize: MainAxisSize.min,
                      children: <Widget>[
                        const SizedBox(
                          width: 18,
                          height: 18,
                          child: CircularProgressIndicator(strokeWidth: 2),
                        ),
                        const SizedBox(width: 12),
                        Text(l10n.translationPreviewPdfUpdating),
                      ],
                    ),
                  ),
                ),
              ),
            ),
          ),
        ),
      ],
    );
  }

  void _maybeApplyPdfRevision(int revision) {
    if (_autoRefreshPdf && revision != _displayPdfRevision) {
      _markPdfPreviewRefreshing();
      setState(() {
        _displayPdfRevision = revision;
        _displayDirtySegmentIndices = Set<int>.from(
          widget.pdfPreviewDirtySegmentsListenable?.value ?? const <int>{},
        );
      });
    }
  }

  bool _commitAutoRotationAspectRatioFromField() {
    final double? parsed = double.tryParse(
      _autoRotationRatioController.text.trim(),
    );
    if (parsed == null || parsed <= 0) {
      _autoRotationRatioController.text =
          _autoRotationAspectRatio.toStringAsFixed(0);
      return false;
    }
    if ((_autoRotationAspectRatio - parsed).abs() < 1e-6) {
      return false;
    }
    _autoRotationAspectRatio = parsed;
    return true;
  }

  bool _commitAutoRotationDegreesFromField() {
    final int? parsed = int.tryParse(
      _autoRotationDegreesController.text.trim(),
    );
    if (parsed == null ||
        parsed == 0 ||
        !kPdfRotationOptionsDegrees.contains(parsed)) {
      _autoRotationDegreesController.text = _autoRotationDegrees.toString();
      return false;
    }
    if (_autoRotationDegrees == parsed) {
      return false;
    }
    _autoRotationDegrees = parsed;
    return true;
  }

  void _commitAutoRotationFieldsFromControllers() {
    _commitAutoRotationAspectRatioFromField();
    _commitAutoRotationDegreesFromField();
  }

  void _refreshPdfManually() {
    _commitAutoRotationFieldsFromControllers();
    final int revision =
        widget.pdfRenderRevisionListenable?.value ?? widget.pdfRenderRevision;
    _markPdfPreviewRefreshing();
    setState(() {
      _pdfPreviewManualRefreshNonce++;
      _displayPdfRevision = revision;
      // Auto rotation is global; incremental dirty_segments refresh is insufficient.
      _displayDirtySegmentIndices = _autoRotationEnabled
          ? <int>{}
          : Set<int>.from(
              widget.pdfPreviewDirtySegmentsListenable?.value ??
                  const <int>{},
            );
    });
  }

  void _setLayoutMode(PdfCompareLayoutMode mode) {
    if (mode == _layoutMode) {
      return;
    }
    if (mode == PdfCompareLayoutMode.comparePreview) {
      setState(() {
        _layoutMode = mode;
        _selectedSegmentIndicesNotifier.value = <int>{};
        _comparePdfCurrentPage = 1;
        _comparePdfTotalPages = 0;
      });
      return;
    }
    if (_layoutMode == PdfCompareLayoutMode.comparePreview) {
      unawaited(_enterRevisionLayoutMode(mode));
      return;
    }
    setState(() {
      _layoutMode = mode;
    });
    _onPdfBboxHighlightChanged();
  }

  void _setAutoRotationEnabled(bool enabled) {
    if (_autoRotationEnabled == enabled) {
      return;
    }
    setState(() {
      _autoRotationEnabled = enabled;
    });
    _refreshPdfManually();
  }

  void _applyAutoRotationDegreesFromField() {
    if (!_commitAutoRotationDegreesFromField()) {
      return;
    }
    setState(() {});
    if (_autoRotationEnabled) {
      _refreshPdfManually();
    }
  }

  Widget _buildAutoRotationNumberField({
    required TextEditingController controller,
    required bool allowDecimal,
    required VoidCallback onCommit,
  }) {
    return SizedBox(
      width: 52,
      child: TextField(
        controller: controller,
        style: Theme.of(context).textTheme.bodySmall,
        textAlign: TextAlign.right,
        textAlignVertical: TextAlignVertical.center,
        decoration: InputDecoration(
          isDense: true,
          contentPadding: const EdgeInsets.symmetric(
            horizontal: 6,
            vertical: 0,
          ),
          constraints: const BoxConstraints(
            minHeight: 26,
            maxHeight: 26,
          ),
          border: const OutlineInputBorder(),
        ),
        keyboardType: TextInputType.numberWithOptions(
          decimal: allowDecimal,
        ),
        onSubmitted: (_) => onCommit(),
        onEditingComplete: onCommit,
      ),
    );
  }

  Widget _buildAutoRotationFieldRow({
    required String label,
    required Widget field,
  }) {
    return Row(
      children: <Widget>[
        Expanded(
          child: Text(
            label,
            textAlign: TextAlign.right,
            style: Theme.of(context).textTheme.bodySmall,
          ),
        ),
        const SizedBox(width: 4),
        field,
      ],
    );
  }

  void _applyAutoRotationAspectRatioFromField() {
    if (!_commitAutoRotationAspectRatioFromField()) {
      return;
    }
    setState(() {});
    if (_autoRotationEnabled) {
      _refreshPdfManually();
    }
  }

  Future<void> _enterRevisionLayoutMode([
    PdfCompareLayoutMode mode = PdfCompareLayoutMode.translationRevision,
  ]) async {
    if (!_supportsRevisionPreview) {
      return;
    }
    if (_layoutMode == PdfCompareLayoutMode.comparePreview && mounted) {
      setState(() {
        _layoutMode = mode;
      });
    }
    final Future<void> Function()? enterHandler =
        widget.onPdfRevisionModeEntered;
    if (enterHandler != null) {
      unawaited(enterHandler());
    }
  }

  void _toggleSegmentSelection(int index, bool selected) {
    final Set<int> next =
        Set<int>.from(_selectedSegmentIndicesNotifier.value);
    if (selected) {
      next.add(index);
    } else {
      next.remove(index);
    }
    _selectedSegmentIndicesNotifier.value = next;
  }

  void _bulkSelectAll(Set<int> indices) {
    if (indices.isEmpty) {
      return;
    }
    _selectedSegmentIndicesNotifier.value = Set<int>.from(indices);
  }

  void _bulkInvertSelection(Set<int> indices) {
    if (indices.isEmpty) {
      return;
    }
    final Set<int> next =
        Set<int>.from(_selectedSegmentIndicesNotifier.value);
    for (final int index in indices) {
      if (next.contains(index)) {
        next.remove(index);
      } else {
        next.add(index);
      }
    }
    _selectedSegmentIndicesNotifier.value = next;
  }

  Widget _buildRevisionSegmentPanelWidget({bool showSegmentScrollbar = true}) {
    final PdfRevisionSegmentPanelBuilder? builder =
        widget.pdfRevisionSegmentPanelBuilder;
    if (builder == null) {
      return const SizedBox.shrink();
    }
    return ValueListenableBuilder<Set<int>>(
      valueListenable: _selectedSegmentIndicesNotifier,
      builder: (BuildContext context, Set<int> selectedSegmentIndices, _) {
        return builder(
          selectedSegmentIndices: selectedSegmentIndices,
          selectedSegmentIndicesListenable: _selectedSegmentIndicesNotifier,
          onSegmentSelectionToggle: _toggleSegmentSelection,
          getFilteredSelectableSegmentIndices:
              widget.getFilteredSelectableSegmentIndices,
          onBulkSelectAll: _bulkSelectAll,
          onBulkInvertSelection: _bulkInvertSelection,
          onBatchFontApply:
              widget.onBatchFontApply != null ? _applyBatchFont : null,
          onBatchFontSizeStep:
              widget.onBatchFontSizeStep != null ? _applyBatchFontSizeStep : null,
          segmentScrollController: widget.segmentScrollController,
          showSegmentScrollbar: showSegmentScrollbar,
        );
      },
    );
  }

  void _setAutoRefreshPdf(bool enabled) {
    setState(() {
      _autoRefreshPdf = enabled;
      if (enabled) {
        _displayPdfRevision = widget.pdfRenderRevisionListenable?.value ??
            widget.pdfRenderRevision;
        _displayDirtySegmentIndices = Set<int>.from(
          widget.pdfPreviewDirtySegmentsListenable?.value ?? const <int>{},
        );
      }
    });
  }

  Future<void> _applyBatchFont() async {
    final Set<int> selected = _selectedSegmentIndicesNotifier.value;
    if (selected.isEmpty || widget.onBatchFontApply == null) {
      return;
    }
    await widget.onBatchFontApply!(selected);
  }

  Future<void> _applyBatchFontSizeStep(double delta) async {
    final Set<int> selected = _selectedSegmentIndicesNotifier.value;
    if (selected.isEmpty || widget.onBatchFontSizeStep == null) {
      return;
    }
    await widget.onBatchFontSizeStep!(selected, delta);
  }

  Future<void> _applyBatchLeading() async {
    final Set<int> selected = _selectedSegmentIndicesNotifier.value;
    if (selected.isEmpty || widget.onBatchLeadingApply == null) {
      return;
    }
    await widget.onBatchLeadingApply!(selected);
  }

  void _toggleFullscreen() {
    if (_isFullscreen) {
      _fullscreenOverlay.exit();
      return;
    }
    _fullscreenOverlay.enter(
      context: context,
      builder: (BuildContext overlayContext) => _buildPreviewShell(
        overlayContext,
        isFullscreenView: true,
      ),
    );
    setState(() {
      _isFullscreen = true;
    });
  }

  void _setSyncScrollEnabled(bool enabled) {
    if (_syncScrollEnabled == enabled) {
      return;
    }
    setState(() {
      _syncScrollEnabled = enabled;
    });
    widget.onSyncScrollChanged?.call(enabled);
  }

  void _setRevisionLinkedScrollEnabled(bool enabled) {
    if (_revisionLinkedScrollEnabled == enabled) {
      return;
    }
    setState(() {
      _revisionLinkedScrollEnabled = enabled;
    });
  }

  Map<String, String> _buildFormatParams() {
    final FormatSettings formatSettings =
        ref.watch(formatSettingsProviderFamily(widget.taskId));
    return <String, String>{
      ...buildPreviewExportQueryParams(
        formatSettings,
        isPdfWorkflow: widget.isPdfWorkflow,
        isImageWorkflow: widget.isImageSource &&
            widget.baseMode == TranslationPreviewMode.imageOriginalLayout,
        rendererType: widget.baseMode.rendererType,
      ),
      ...autoRotationPreviewParams(
        enabled: _autoRotationEnabled,
        aspectRatio: _autoRotationAspectRatio,
        degrees: _autoRotationDegrees,
      ),
    };
  }

  Widget _buildPdfCompareContinuousView({
    required String sourcePdfUrl,
    required String targetPdfUrl,
    required bool linkedScroll,
    PdfCompareContinuousScrollController? navigationController,
  }) {
    return PdfCompareContinuousView(
      key: _pdfCompareViewKey,
      sourceDownloadUrl: sourcePdfUrl,
      targetDownloadUrl: targetPdfUrl,
      targetRendererType: widget.baseMode.rendererType,
      linkedScroll: linkedScroll,
      navigationController: navigationController,
      highlightPageNumber: _highlightBboxPage,
      highlightBboxes: _highlightBboxes,
      sourceHighlightBboxes: _bboxEditMode ? null : _sourceHighlightBboxes,
      viewportController: _viewportController,
      bboxEditMode: _bboxEditMode,
      onEditBboxChanged: _onEditBboxChanged,
      onEditBboxReset: _onEditBboxReset,
      onLoadSettled: _pdfPreviewLoadSettledHandler(),
      onVisiblePageChanged: (int page, int totalPages) {
        if (!mounted ||
            (page == _comparePdfCurrentPage &&
                totalPages == _comparePdfTotalPages)) {
          return;
        }
        setState(() {
          _comparePdfCurrentPage = page;
          _comparePdfTotalPages = totalPages;
        });
      },
    );
  }

  String _buildTargetImageUrl(Map<String, String> formatParams) {
    return mergePreviewUrl(
      widget.translatedImageUrl!,
      {
        ...formatParams,
        ...previewCacheBustParams(
          _displayPdfRevision,
          manualNonce: _pdfPreviewManualRefreshNonce,
        ),
      },
    );
  }

  String _buildTargetPdfUrl(Map<String, String> formatParams) {
    return mergePreviewUrl(
      widget.translatedPdfUrl!,
      {
        ...formatParams,
        ...previewCacheBustParams(
          _displayPdfRevision,
          manualNonce: _pdfPreviewManualRefreshNonce,
        ),
        ...pdfPreviewDirtySegmentParams(_displayDirtySegmentIndices),
      },
    );
  }

  String _resolveViewerUrl(String downloadUrl) {
    return downloadUrl.startsWith('http')
        ? downloadUrl
        : '${AppConfig.baseUrl}$downloadUrl';
  }

  List<Rect> _buildHighlightRects() {
    final List<List<double>>? bboxes = _highlightBboxes;
    if (bboxes == null || bboxes.isEmpty) {
      return const <Rect>[];
    }
    final List<Rect> rects = <Rect>[];
    for (final List<double> bbox in bboxes) {
      if (bbox.length < 4) {
        continue;
      }
      final Rect? rect = layoutBlockBboxToImageRect(bbox);
      if (rect != null) {
        rects.add(rect);
      }
    }
    return rects;
  }

  List<Rect> _buildSourceHighlightRects() {
    final List<List<double>>? bboxes = _sourceHighlightBboxes;
    if (bboxes == null || bboxes.isEmpty) {
      return _buildHighlightRects();
    }
    final List<Rect> rects = <Rect>[];
    for (final List<double> bbox in bboxes) {
      if (bbox.length < 4) {
        continue;
      }
      final Rect? rect = layoutBlockBboxToImageRect(bbox);
      if (rect != null) {
        rects.add(rect);
      }
    }
    return rects;
  }

  Widget _buildTargetImagePreview(
    AppLocalizations l10n, {
    required String targetImageUrl,
  }) {
    return ImageOverlayPreviewView(
      imageUrl: targetImageUrl,
      panelLabel: l10n.translationPreviewPanelTarget,
      highlightRects: _buildHighlightRects(),
      bboxReferenceSize: widget.overlayBboxReferenceSize,
    );
  }

  Widget _buildTargetPdfPreview(
    AppLocalizations l10n, {
    required String targetPdfUrl,
    bool enableNavigation = true,
    ScrollController? scrollController,
    bool showScrollbar = true,
  }) {
    return PdfPreview(
      downloadUrl: targetPdfUrl,
      viewerUrl: _resolveViewerUrl(targetPdfUrl),
      rendererType: widget.baseMode.rendererType,
      compact: true,
      panelLabel: l10n.translationPreviewPanelTarget,
      navigationController:
          enableNavigation ? _pdfNavigationController : null,
      scrollController: scrollController,
      showScrollbar: showScrollbar,
      highlightPageNumber: _highlightBboxPage,
      highlightBboxes: _highlightBboxes,
      bboxEditMode: _bboxEditMode,
      onEditBboxChanged: _onEditBboxChanged,
      onEditBboxReset: _onEditBboxReset,
      onLoadSettled: _pdfPreviewLoadSettledHandler(),
      onDownload: widget.onDownload,
      onRequestPreviewSettings: widget.onRequestPreviewSettings,
    );
  }

  Widget _buildTranslationRevisionPanel(AppLocalizations l10n) {
    final Map<String, String> formatParams = _buildFormatParams();
    final Widget segmentPanel = widget.segmentUiRevisionListenable == null
        ? _buildRevisionSegmentPanelWidget()
        : ValueListenableBuilder<int>(
            valueListenable: widget.segmentUiRevisionListenable!,
            builder: (BuildContext context, int _, Widget? __) {
              return _buildRevisionSegmentPanelWidget();
            },
          );

    if (_isImageRevisionSource) {
      final String targetImageUrl = _buildTargetImageUrl(formatParams);
      return Row(
        children: <Widget>[
          Expanded(
            flex: 3,
            child: PreviewZoomableViewport(
              controller: _viewportController,
              childHandlesVerticalScroll: true,
              child: _buildTargetImagePreview(
                l10n,
                targetImageUrl: targetImageUrl,
              ),
            ),
          ),
          const VerticalDivider(width: 1),
          Expanded(
            flex: 2,
            child: segmentPanel,
          ),
        ],
      );
    }

    final String targetPdfUrl = _buildTargetPdfUrl(formatParams);
    return Row(
      children: <Widget>[
        Expanded(
          flex: 3,
          child: PreviewZoomableViewport(
            controller: _viewportController,
            childHandlesVerticalScroll: true,
            child: _wrapPdfPreviewRefreshingOverlay(
              l10n,
              _buildTargetPdfPreview(l10n, targetPdfUrl: targetPdfUrl),
            ),
          ),
        ),
        const VerticalDivider(width: 1),
        Expanded(
          flex: 2,
          child: segmentPanel,
        ),
      ],
    );
  }

  Widget _buildCompareRevisionPanel(AppLocalizations l10n) {
    final Map<String, String> formatParams = _buildFormatParams();
    final TranslationService svc = TranslationService();

    final Widget segmentPanel = widget.segmentUiRevisionListenable == null
        ? _buildRevisionSegmentPanelWidget()
        : ValueListenableBuilder<int>(
            valueListenable: widget.segmentUiRevisionListenable!,
            builder: (BuildContext context, int _, Widget? __) {
              return _buildRevisionSegmentPanelWidget();
            },
          );

    if (_isImageRevisionSource) {
      final String targetImageUrl = _buildTargetImageUrl(formatParams);
      return Row(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: <Widget>[
          Expanded(
            flex: 4,
            child: PreviewZoomableViewport(
              controller: _viewportController,
              childHandlesVerticalScroll: true,
              child: ImageOverlayCompareView(
                sourceImageUrl: svc.buildSourceImageUrl(widget.taskId),
                targetImageUrl: targetImageUrl,
                linkedScroll: _revisionLinkedScrollEnabled,
                highlightRects: _buildHighlightRects(),
                sourceHighlightRects: _buildSourceHighlightRects(),
                bboxReferenceSize: widget.overlayBboxReferenceSize,
                viewportController: _viewportController,
              ),
            ),
          ),
          const VerticalDivider(width: 1),
          Expanded(
            flex: 2,
            child: segmentPanel,
          ),
        ],
      );
    }

    final String sourcePdfUrl = svc.buildSourcePdfUrl(widget.taskId);
    final String targetPdfUrl = _buildTargetPdfUrl(formatParams);

    return Row(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: <Widget>[
        Expanded(
          flex: 4,
          child: PreviewZoomableViewport(
            controller: _viewportController,
            childHandlesVerticalScroll: true,
            child: _wrapPdfPreviewRefreshingOverlay(
              l10n,
              _buildPdfCompareContinuousView(
                sourcePdfUrl: sourcePdfUrl,
                targetPdfUrl: targetPdfUrl,
                linkedScroll: _revisionLinkedScrollEnabled,
                navigationController: _pdfCompareNavigationController,
              ),
            ),
          ),
        ),
        const VerticalDivider(width: 1),
        Expanded(
          flex: 2,
          child: segmentPanel,
        ),
      ],
    );
  }

  Widget _buildPdfRevisionPanel(AppLocalizations l10n) {
    switch (_layoutMode) {
      case PdfCompareLayoutMode.translationRevision:
        return _buildTranslationRevisionPanel(l10n);
      case PdfCompareLayoutMode.compareRevision:
        return _buildCompareRevisionPanel(l10n);
      case PdfCompareLayoutMode.comparePreview:
        return _buildComparePreviewBody(l10n);
    }
  }

  Widget _buildComparePreviewBody(AppLocalizations l10n) {
    final Map<String, String> formatParams = _buildFormatParams();
    final TranslationService svc = TranslationService();

    if (widget.baseMode == TranslationPreviewMode.html) {
      final String? htmlBase = widget.translatedHtmlUrl;
      if (htmlBase == null) {
        return Center(child: Text(l10n.translationPreviewNoExtraOptions));
      }
      final String sourceHtmlUrl = mergePreviewUrl(
        svc.buildSourceHtmlUrl(
          widget.taskId,
          tableBodyFormat: formatParams['table_body_format'],
          equationFormat: formatParams['equation_format'],
          chartBodyFormat: formatParams['chart_body_format'],
        ),
        <String, String>{},
      );
      final String targetHtmlUrl = mergePreviewUrl(htmlBase, formatParams);
      final String readerUrl = buildHtmlCompareReaderUrl(
        apiBaseUrl: AppConfig.baseUrl,
        sourceHtmlUrl: sourceHtmlUrl,
        targetHtmlUrl: targetHtmlUrl,
        sourceLabel: l10n.translationPreviewPanelSource,
        targetLabel: l10n.translationPreviewPanelTarget,
        linkedScroll: _syncScrollEnabled,
      );
      return HtmlCompareReaderView(
        readerUrl: readerUrl,
        linkedScroll: _syncScrollEnabled,
        viewportController: _viewportController,
      );
    }

    if (widget.baseMode == TranslationPreviewMode.imageOriginalLayout) {
      if (!widget.isImageSource || widget.translatedImageUrl == null) {
        return Center(child: Text(l10n.translationPreviewNoExtraOptions));
      }
      final String targetImageUrl = _buildTargetImageUrl(formatParams);
      return PreviewZoomableViewport(
        controller: _viewportController,
        childHandlesVerticalScroll: true,
        child: ImageOverlayCompareView(
          sourceImageUrl: svc.buildSourceImageUrl(widget.taskId),
          targetImageUrl: targetImageUrl,
          linkedScroll: _syncScrollEnabled,
          highlightRects: _buildHighlightRects(),
          sourceHighlightRects: _buildSourceHighlightRects(),
          bboxReferenceSize: widget.overlayBboxReferenceSize,
          viewportController: _viewportController,
        ),
      );
    }

    if (!widget.isPdfSource || widget.translatedPdfUrl == null) {
      return Center(child: Text(l10n.translationPreviewNoExtraOptions));
    }
    final String sourcePdfUrl = svc.buildSourcePdfUrl(widget.taskId);
    final String targetPdfUrl = _buildTargetPdfUrl(formatParams);
    return PreviewZoomableViewport(
      controller: _viewportController,
      childHandlesVerticalScroll: true,
      child: _wrapPdfPreviewRefreshingOverlay(
        l10n,
        _buildPdfCompareContinuousView(
          sourcePdfUrl: sourcePdfUrl,
          targetPdfUrl: targetPdfUrl,
          linkedScroll: _syncScrollEnabled,
        ),
      ),
    );
  }

  Widget _buildPreviewBody(AppLocalizations l10n) {
    if (_layoutMode.showsRevisionControls) {
      if (!_supportsRevisionPreview) {
        return const Center(child: CircularProgressIndicator());
      }
      return _buildPdfRevisionPanel(l10n);
    }
    return _buildComparePreviewBody(l10n);
  }

  Widget _buildLayoutModeSelector(AppLocalizations l10n) {
    return PopupMenuButton<PdfCompareLayoutMode>(
      tooltip: l10n.translationPreviewLayoutComparePreview,
      initialValue: _layoutMode,
      onSelected: _setLayoutMode,
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 4, vertical: 2),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: <Widget>[
            Icon(_layoutMode.icon, size: 18),
            const SizedBox(width: 6),
            Text(
              _layoutMode.label(l10n),
              style: const TextStyle(fontWeight: FontWeight.w600),
            ),
            const Icon(Icons.arrow_drop_down, size: 20),
          ],
        ),
      ),
      itemBuilder: (BuildContext context) {
        return PdfCompareLayoutMode.values
            .map((PdfCompareLayoutMode mode) {
              return PopupMenuItem<PdfCompareLayoutMode>(
                value: mode,
                child: Row(
                  children: <Widget>[
                    Icon(
                      mode.icon,
                      size: 18,
                      color: mode == _layoutMode
                          ? Theme.of(context).colorScheme.primary
                          : null,
                    ),
                    const SizedBox(width: 8),
                    Text(mode.label(l10n)),
                  ],
                ),
              );
            })
            .toList(growable: false);
      },
    );
  }

  bool get _isPdfCompare =>
      widget.baseMode == TranslationPreviewMode.pdfPreserve ||
      widget.baseMode == TranslationPreviewMode.pdfReflow;

  bool get _isImageCompare =>
      widget.baseMode == TranslationPreviewMode.imageOriginalLayout &&
      widget.isImageSource;

  Widget _buildPreviewToolbar(
    BuildContext context,
    AppLocalizations l10n, {
    required bool isFullscreenView,
  }) {
    final bool showRevisionControls =
        _layoutMode.showsRevisionControls && _supportsRevisionPreview;
    return Material(
      color: Theme.of(context).colorScheme.surfaceContainerHighest,
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
        child: Row(
          children: <Widget>[
            if (_supportsRevisionPreview)
              _buildLayoutModeSelector(l10n)
            else ...<Widget>[
              Icon(
                isFullscreenView
                    ? Icons.fullscreen_exit
                    : _layoutMode.icon,
                size: 18,
              ),
              const SizedBox(width: 8),
              Text(
                _layoutMode.label(l10n),
                style: const TextStyle(fontWeight: FontWeight.w600),
              ),
            ],
            Expanded(
              child: SingleChildScrollView(
                scrollDirection: Axis.horizontal,
                clipBehavior: Clip.none,
                child: Row(
                  mainAxisSize: MainAxisSize.min,
                  children: <Widget>[
                    if (showRevisionControls) ...<Widget>[
                      const SizedBox(width: 8),
                      Tooltip(
                        message: l10n.translationPreviewAutoRefreshPdf,
                        child: Row(
                          mainAxisSize: MainAxisSize.min,
                          children: <Widget>[
                            Checkbox(
                              value: _autoRefreshPdf,
                              onChanged: (bool? value) {
                                _setAutoRefreshPdf(value ?? false);
                              },
                              visualDensity: VisualDensity.compact,
                            ),
                            Text(
                              l10n.translationPreviewAutoRefreshPdf,
                              style: Theme.of(context).textTheme.bodySmall,
                            ),
                          ],
                        ),
                      ),
                      if (widget.autoFollowSegmentPdfPageListenable != null &&
                          widget.onAutoFollowSegmentPdfPageChanged != null)
                        Tooltip(
                          message: l10n.translationPreviewFollowSegmentPageDesc,
                          child: Row(
                            mainAxisSize: MainAxisSize.min,
                            children: <Widget>[
                              Checkbox(
                                value: _autoFollowSegmentPdfPage,
                                onChanged: _previewSignalsAlive
                                    ? (bool? value) {
                                        widget
                                            .onAutoFollowSegmentPdfPageChanged!(
                                          value ?? false,
                                        );
                                      }
                                    : null,
                                visualDensity: VisualDensity.compact,
                              ),
                              Text(
                                l10n.translationPreviewFollowSegmentPage,
                                style: Theme.of(context).textTheme.bodySmall,
                              ),
                            ],
                          ),
                        ),
                      if (widget.showSelectedSegmentMarkerListenable != null &&
                          widget.onShowSelectedSegmentMarkerChanged != null)
                        Tooltip(
                          message:
                              l10n.translationPreviewMarkSelectedSegmentDesc,
                          child: Row(
                            mainAxisSize: MainAxisSize.min,
                            children: <Widget>[
                              Checkbox(
                                value: _showSelectedSegmentMarker,
                                onChanged: _previewSignalsAlive
                                    ? (bool? value) {
                                        widget
                                            .onShowSelectedSegmentMarkerChanged!(
                                          value ?? false,
                                        );
                                      }
                                    : null,
                                visualDensity: VisualDensity.compact,
                              ),
                              Text(
                                l10n.translationPreviewMarkSelectedSegment,
                                style: Theme.of(context).textTheme.bodySmall,
                              ),
                            ],
                          ),
                        ),
                      if (widget.bboxEditModeListenable != null)
                        Tooltip(
                          message: l10n.translationPreviewEditSegmentBboxDesc,
                          child: Row(
                            mainAxisSize: MainAxisSize.min,
                            children: <Widget>[
                              Checkbox(
                                value: _bboxEditMode,
                                onChanged: (bool? value) {
                                  widget.onBboxEditModeChanged
                                      ?.call(value ?? false);
                                },
                                visualDensity: VisualDensity.compact,
                              ),
                              Text(
                                l10n.translationPreviewEditSegmentBbox,
                                style: Theme.of(context).textTheme.bodySmall,
                              ),
                            ],
                          ),
                        ),
                      if (_isPdfRevisionSource) ...<Widget>[
                        Tooltip(
                          message:
                              l10n.translationPreviewAutoRotateSidewaysTextDesc,
                          child: Row(
                            mainAxisSize: MainAxisSize.min,
                            children: <Widget>[
                              Checkbox(
                                value: _autoRotationEnabled,
                                onChanged: (bool? value) {
                                  _setAutoRotationEnabled(value ?? false);
                                },
                                visualDensity: VisualDensity.compact,
                              ),
                              Text(
                                l10n.translationPreviewAutoRotateSidewaysText,
                                style: Theme.of(context).textTheme.bodySmall,
                              ),
                            ],
                          ),
                        ),
                        if (_autoRotationEnabled)
                          Tooltip(
                            message: l10n
                                .translationPreviewAutoRotateControlsDesc,
                            child: IntrinsicWidth(
                              child: Column(
                                mainAxisSize: MainAxisSize.min,
                                crossAxisAlignment: CrossAxisAlignment.stretch,
                                children: <Widget>[
                                  _buildAutoRotationFieldRow(
                                    label: l10n
                                        .translationPreviewAutoRotateAspectRatio,
                                    field: _buildAutoRotationNumberField(
                                      controller: _autoRotationRatioController,
                                      allowDecimal: true,
                                      onCommit:
                                          _applyAutoRotationAspectRatioFromField,
                                    ),
                                  ),
                                  const SizedBox(height: 2),
                                  _buildAutoRotationFieldRow(
                                    label: l10n
                                        .translationPreviewAutoRotateDegrees,
                                    field: _buildAutoRotationNumberField(
                                      controller:
                                          _autoRotationDegreesController,
                                      allowDecimal: false,
                                      onCommit:
                                          _applyAutoRotationDegreesFromField,
                                    ),
                                  ),
                                ],
                              ),
                            ),
                          ),
                      ],
                      if (kPdfLeadingTypographyUiEnabled &&
                          widget.onBatchLeadingApply != null)
                        ValueListenableBuilder<Set<int>>(
                          valueListenable: _selectedSegmentIndicesNotifier,
                          builder: (
                            BuildContext context,
                            Set<int> selectedSegmentIndices,
                            Widget? _,
                          ) {
                            if (selectedSegmentIndices.isEmpty) {
                              return const SizedBox.shrink();
                            }
                            return Tooltip(
                              message:
                                  l10n.translationPreviewBatchLeadingTooltip,
                              child: TextButton.icon(
                                onPressed: _applyBatchLeading,
                                icon: const Icon(
                                  Icons.format_line_spacing,
                                  size: 16,
                                ),
                                label: Text(l10n.translationPreviewBatchLeading),
                              ),
                            );
                          },
                        ),
                    ],
                    if (_layoutMode == PdfCompareLayoutMode.comparePreview &&
                        (_isPdfCompare ||
                            widget.baseMode.usesHtmlPreview ||
                            _isImageCompare)) ...<Widget>[
                      const SizedBox(width: 16),
                      Tooltip(
                        message: l10n.translationPreviewSyncScrollDesc,
                        child: Row(
                          mainAxisSize: MainAxisSize.min,
                          children: <Widget>[
                            Checkbox(
                              value: _syncScrollEnabled,
                              onChanged: (bool? value) {
                                _setSyncScrollEnabled(value ?? false);
                              },
                              visualDensity: VisualDensity.compact,
                            ),
                            Text(
                              l10n.translationPreviewSyncScroll,
                              style: Theme.of(context).textTheme.bodySmall,
                            ),
                          ],
                        ),
                      ),
                    ],
                    if (_showsRevisionLinkedScroll) ...<Widget>[
                      const SizedBox(width: 16),
                      Tooltip(
                        message: l10n.translationPreviewRevisionSyncScrollDesc,
                        child: Row(
                          mainAxisSize: MainAxisSize.min,
                          children: <Widget>[
                            Checkbox(
                              value: _revisionLinkedScrollEnabled,
                              onChanged: (bool? value) {
                                _setRevisionLinkedScrollEnabled(value ?? false);
                              },
                              visualDensity: VisualDensity.compact,
                            ),
                            Text(
                              l10n.translationPreviewSyncScroll,
                              style: Theme.of(context).textTheme.bodySmall,
                            ),
                          ],
                        ),
                      ),
                    ],
                    if (_layoutMode == PdfCompareLayoutMode.comparePreview &&
                        _isPdfCompare &&
                        _comparePdfTotalPages > 0) ...<Widget>[
                      const SizedBox(width: 12),
                      Text(
                        l10n.translationPreviewPdfPageIndicator(
                          _comparePdfCurrentPage.toString(),
                          _comparePdfTotalPages.toString(),
                        ),
                        style: Theme.of(context).textTheme.bodySmall?.copyWith(
                              color: Theme.of(context)
                                  .colorScheme
                                  .onSurfaceVariant,
                              fontWeight: FontWeight.w600,
                            ),
                      ),
                    ],
                  ],
                ),
              ),
            ),
            if (showRevisionControls)
              IconButton(
                icon: const Icon(Icons.refresh, size: 18),
                tooltip: l10n.translationPreviewRefreshPdf,
                onPressed: _refreshPdfManually,
              ),
            PreviewZoomToolbarActions(
              viewportController: _viewportController,
            ),
            if (widget.onShowDownload != null)
              IconButton(
                icon: const Icon(Icons.download, size: 18),
                tooltip: l10n.translationToolbarExportTooltip,
                onPressed: () {
                  unawaited(widget.onShowDownload!());
                },
              ),
            if (widget.onRequestPreviewSettings != null)
              IconButton(
                icon: const Icon(Icons.settings, size: 18),
                tooltip: l10n.translationPreviewReopenSettings,
                onPressed: () {
                  if (_isFullscreen) {
                    _fullscreenOverlay.exit();
                    setState(() {
                      _isFullscreen = false;
                    });
                  }
                  widget.onRequestPreviewSettings?.call();
                },
              ),
            PreviewViewportTrailingActions(
              viewportController: _viewportController,
              isFullscreen: _isFullscreen,
              onToggleFullscreen: _toggleFullscreen,
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildPreviewShell(
    BuildContext context, {
    required bool isFullscreenView,
  }) {
    final AppLocalizations l10n = AppLocalizations.of(context)!;
    if (!_previewSignalsAlive) {
      return Column(
        children: <Widget>[
          _buildPreviewToolbar(context, l10n, isFullscreenView: isFullscreenView),
          const Divider(height: 1),
          Expanded(child: _buildStalePreviewPlaceholder(l10n)),
        ],
      );
    }
    return Column(
      children: <Widget>[
        _buildPreviewToolbar(context, l10n, isFullscreenView: isFullscreenView),
        const Divider(height: 1),
        Expanded(child: _buildPreviewBody(l10n)),
      ],
    );
  }

  @override
  Widget build(BuildContext context) {
    if (_isFullscreen) {
      return const SizedBox.shrink();
    }
    return _buildPreviewShell(context, isFullscreenView: false);
  }
}
