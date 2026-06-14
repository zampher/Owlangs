// SPDX-FileCopyrightText: 2026 Zampher
// SPDX-License-Identifier: MPL-2.0

import 'dart:async';

import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../../app/app_config.dart';
import '../../../../l10n/app_localizations.dart';
import '../../../../shared/services/translation_service.dart';
import '../../providers/format_settings_provider.dart';
import '../pdf_continuous_scroll_view.dart';
import '../pdf_compare_continuous_view.dart';
import '../pdf_preview.dart';
import 'segment_pdf_typography_dialog.dart';
import 'html_compare_reader_view.dart';
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
    required this.isPdfWorkflow,
    this.translatedPdfUrl,
    this.pdfRenderRevision = 0,
    this.pdfRenderRevisionListenable,
    this.pdfPreviewDirtySegmentsListenable,
    this.segmentUiRevisionListenable,
    this.translatedHtmlUrl,
    this.initialSyncScroll = false,
    this.initialLayoutMode = PdfCompareLayoutMode.comparePreview,
    this.pdfRevisionSegmentPanelBuilder,
    this.onBatchFontApply,
    this.onBatchLeadingApply,
    this.getFilteredSelectableSegmentIndices,
    this.onPdfRevisionModeEntered,
    this.pdfPreviewJumpPageListenable,
    this.pdfPreviewJumpPageTriggerListenable,
    this.autoFollowSegmentPdfPageListenable,
    this.onAutoFollowSegmentPdfPageChanged,
    this.segmentScrollController,
    super.key,
    this.onRequestPreviewSettings,
    this.onDownload,
    this.onShowDownload,
    this.onSyncScrollChanged,
  });

  final String taskId;
  final TranslationPreviewMode baseMode;
  final bool isPdfSource;
  final bool isPdfWorkflow;
  final String? translatedPdfUrl;
  final int pdfRenderRevision;
  final ValueListenable<int>? pdfRenderRevisionListenable;
  final ValueListenable<Set<int>>? pdfPreviewDirtySegmentsListenable;
  final ValueListenable<int>? segmentUiRevisionListenable;
  final String? translatedHtmlUrl;
  final bool initialSyncScroll;
  final PdfCompareLayoutMode initialLayoutMode;
  final PdfRevisionSegmentPanelBuilder? pdfRevisionSegmentPanelBuilder;
  final Future<void> Function(Set<int> selectedIndices)? onBatchFontApply;
  final Future<void> Function(Set<int> selectedIndices)? onBatchLeadingApply;
  final Set<int> Function()? getFilteredSelectableSegmentIndices;
  final Future<void> Function()? onPdfRevisionModeEntered;
  final ValueListenable<int?>? pdfPreviewJumpPageListenable;
  final ValueListenable<int>? pdfPreviewJumpPageTriggerListenable;
  final ValueListenable<bool>? autoFollowSegmentPdfPageListenable;
  final ValueChanged<bool>? onAutoFollowSegmentPdfPageChanged;
  final ScrollController? segmentScrollController;
  final Future<PreviewSelection?> Function()? onRequestPreviewSettings;
  final void Function(String format, String url)? onDownload;
  final Future<void> Function()? onShowDownload;
  final ValueChanged<bool>? onSyncScrollChanged;

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
  final ValueNotifier<Set<int>> _selectedSegmentIndicesNotifier =
      ValueNotifier<Set<int>>(<int>{});
  final PdfContinuousScrollController _pdfNavigationController =
      PdfContinuousScrollController();
  final PdfCompareContinuousScrollController _pdfCompareNavigationController =
      PdfCompareContinuousScrollController();
  int _comparePdfCurrentPage = 1;
  int _comparePdfTotalPages = 0;
  bool _revisionLinkedScrollEnabled = true;

  bool get _showsRevisionLinkedScroll =>
      _layoutMode == PdfCompareLayoutMode.compareRevision &&
      _supportsPdfRevision;

  bool get _supportsPdfRevision =>
      widget.baseMode == TranslationPreviewMode.pdfPreserve &&
      widget.isPdfSource &&
      widget.translatedPdfUrl != null &&
      widget.pdfRevisionSegmentPanelBuilder != null;

  @override
  void initState() {
    super.initState();
    _syncScrollEnabled = widget.initialSyncScroll;
    _displayPdfRevision = widget.pdfRenderRevision;
    _viewportController = PreviewViewportController();
    _fullscreenOverlay = PreviewFullscreenOverlay(
      onExit: () {
        if (mounted) {
          setState(() {
            _isFullscreen = false;
          });
        }
      },
    );
    widget.pdfRenderRevisionListenable?.addListener(_onPdfRevisionListenableChanged);
    widget.pdfPreviewJumpPageTriggerListenable
        ?.addListener(_onPdfPreviewJumpPageRequested);
    if (widget.initialLayoutMode != PdfCompareLayoutMode.comparePreview &&
        _supportsPdfRevision) {
      _layoutMode = widget.initialLayoutMode;
      // Enter revision layout on the first frame so we do not briefly mount
      // PdfCompareContinuousView (source + target downloads) before revision mode.
      WidgetsBinding.instance.addPostFrameCallback((_) {
        unawaited(_enterRevisionLayoutMode(widget.initialLayoutMode));
      });
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
      oldWidget.pdfRenderRevisionListenable
          ?.removeListener(_onPdfRevisionListenableChanged);
      widget.pdfRenderRevisionListenable
          ?.addListener(_onPdfRevisionListenableChanged);
      _onPdfRevisionListenableChanged();
    }
    if (oldWidget.pdfPreviewJumpPageTriggerListenable !=
        widget.pdfPreviewJumpPageTriggerListenable) {
      oldWidget.pdfPreviewJumpPageTriggerListenable
          ?.removeListener(_onPdfPreviewJumpPageRequested);
      widget.pdfPreviewJumpPageTriggerListenable
          ?.addListener(_onPdfPreviewJumpPageRequested);
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
    widget.pdfRenderRevisionListenable
        ?.removeListener(_onPdfRevisionListenableChanged);
    widget.pdfPreviewJumpPageTriggerListenable
        ?.removeListener(_onPdfPreviewJumpPageRequested);
    _pdfNavigationController.dispose();
    _pdfCompareNavigationController.dispose();
    _selectedSegmentIndicesNotifier.dispose();
    _fullscreenOverlay.dispose();
    _viewportController.dispose();
    super.dispose();
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

  void _maybeApplyPdfRevision(int revision) {
    if (_autoRefreshPdf && revision != _displayPdfRevision) {
      setState(() {
        _displayPdfRevision = revision;
        _displayDirtySegmentIndices = Set<int>.from(
          widget.pdfPreviewDirtySegmentsListenable?.value ?? const <int>{},
        );
      });
    }
  }

  void _refreshPdfManually() {
    final int revision =
        widget.pdfRenderRevisionListenable?.value ?? widget.pdfRenderRevision;
    setState(() {
      _displayPdfRevision = revision;
      _displayDirtySegmentIndices = Set<int>.from(
        widget.pdfPreviewDirtySegmentsListenable?.value ?? const <int>{},
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
  }

  Future<void> _enterRevisionLayoutMode([
    PdfCompareLayoutMode mode = PdfCompareLayoutMode.translationRevision,
  ]) async {
    if (!_supportsPdfRevision) {
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
    final Set<int> next =
        Set<int>.from(_selectedSegmentIndicesNotifier.value);
    next.addAll(indices);
    _selectedSegmentIndicesNotifier.value = next;
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
              widget.getFilteredSelectableSegmentIndices ?? () => <int>{},
          onBulkSelectAll: _bulkSelectAll,
          onBulkInvertSelection: _bulkInvertSelection,
          onBatchFontApply:
              widget.onBatchFontApply != null ? _applyBatchFont : null,
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
    return buildPreviewExportQueryParams(
      formatSettings,
      isPdfWorkflow: widget.isPdfWorkflow,
      rendererType: widget.baseMode.rendererType,
    );
  }

  String _buildTargetPdfUrl(Map<String, String> formatParams) {
    return mergePreviewUrl(
      widget.translatedPdfUrl!,
      {
        ...formatParams,
        ...previewCacheBustParams(_displayPdfRevision),
        ...pdfPreviewDirtySegmentParams(_displayDirtySegmentIndices),
      },
    );
  }

  String _resolveViewerUrl(String downloadUrl) {
    return downloadUrl.startsWith('http')
        ? downloadUrl
        : '${AppConfig.baseUrl}$downloadUrl';
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
      onDownload: widget.onDownload,
      onRequestPreviewSettings: widget.onRequestPreviewSettings,
    );
  }

  Widget _buildTranslationRevisionPanel(AppLocalizations l10n) {
    final Map<String, String> formatParams = _buildFormatParams();
    final String targetPdfUrl = _buildTargetPdfUrl(formatParams);
    final Widget segmentPanel = widget.segmentUiRevisionListenable == null
        ? _buildRevisionSegmentPanelWidget()
        : ValueListenableBuilder<int>(
            valueListenable: widget.segmentUiRevisionListenable!,
            builder: (BuildContext context, int _, Widget? __) {
              return _buildRevisionSegmentPanelWidget();
            },
          );

    return Row(
      children: <Widget>[
        Expanded(
          flex: 3,
          child: PreviewZoomableViewport(
            controller: _viewportController,
            childHandlesVerticalScroll: true,
            child: _buildTargetPdfPreview(l10n, targetPdfUrl: targetPdfUrl),
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
    final String sourcePdfUrl = svc.buildSourcePdfUrl(widget.taskId);
    final String targetPdfUrl = _buildTargetPdfUrl(formatParams);

    final Widget segmentPanel = widget.segmentUiRevisionListenable == null
        ? _buildRevisionSegmentPanelWidget()
        : ValueListenableBuilder<int>(
            valueListenable: widget.segmentUiRevisionListenable!,
            builder: (BuildContext context, int _, Widget? __) {
              return _buildRevisionSegmentPanelWidget();
            },
          );

    return Row(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: <Widget>[
        Expanded(
          flex: 4,
          child: PreviewZoomableViewport(
            controller: _viewportController,
            childHandlesVerticalScroll: true,
            child: PdfCompareContinuousView(
              sourceDownloadUrl: sourcePdfUrl,
              targetDownloadUrl: targetPdfUrl,
              targetRendererType: widget.baseMode.rendererType,
              linkedScroll: _revisionLinkedScrollEnabled,
              navigationController: _pdfCompareNavigationController,
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

    if (!widget.isPdfSource || widget.translatedPdfUrl == null) {
      return Center(child: Text(l10n.translationPreviewNoExtraOptions));
    }
    final String sourcePdfUrl = svc.buildSourcePdfUrl(widget.taskId);
    final String targetPdfUrl = _buildTargetPdfUrl(formatParams);
    return PreviewZoomableViewport(
      controller: _viewportController,
      childHandlesVerticalScroll: true,
      child: PdfCompareContinuousView(
        sourceDownloadUrl: sourcePdfUrl,
        targetDownloadUrl: targetPdfUrl,
        targetRendererType: widget.baseMode.rendererType,
        linkedScroll: _syncScrollEnabled,
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
      ),
    );
  }

  Widget _buildPreviewBody(AppLocalizations l10n) {
    if (_layoutMode.showsRevisionControls && _supportsPdfRevision) {
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

  Widget _buildPreviewToolbar(
    BuildContext context,
    AppLocalizations l10n, {
    required bool isFullscreenView,
  }) {
    final bool showPdfRevisionControls =
        _layoutMode.showsRevisionControls && _supportsPdfRevision;
    return Material(
      color: Theme.of(context).colorScheme.surfaceContainerHighest,
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
        child: Row(
          children: <Widget>[
            if (_supportsPdfRevision)
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
            if (showPdfRevisionControls) ...<Widget>[
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
              IconButton(
                icon: const Icon(Icons.refresh, size: 18),
                tooltip: l10n.translationPreviewRefreshPdf,
                onPressed: _refreshPdfManually,
              ),
              if (widget.autoFollowSegmentPdfPageListenable != null &&
                  widget.onAutoFollowSegmentPdfPageChanged != null)
                ValueListenableBuilder<bool>(
                  valueListenable: widget.autoFollowSegmentPdfPageListenable!,
                  builder: (BuildContext context, bool enabled, Widget? _) {
                    return Tooltip(
                      message: l10n.translationPreviewFollowSegmentPageDesc,
                      child: Row(
                        mainAxisSize: MainAxisSize.min,
                        children: <Widget>[
                          Checkbox(
                            value: enabled,
                            onChanged: (bool? value) {
                              widget.onAutoFollowSegmentPdfPageChanged!(
                                value ?? false,
                              );
                            },
                            visualDensity: VisualDensity.compact,
                          ),
                          Text(
                            l10n.translationPreviewFollowSegmentPage,
                            style: Theme.of(context).textTheme.bodySmall,
                          ),
                        ],
                      ),
                    );
                  },
                ),
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
                      message: l10n.translationPreviewBatchLeadingTooltip,
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
                (_isPdfCompare || widget.baseMode.usesHtmlPreview)) ...<Widget>[
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
                      color: Theme.of(context).colorScheme.onSurfaceVariant,
                      fontWeight: FontWeight.w600,
                    ),
              ),
            ],
            const Spacer(),
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
