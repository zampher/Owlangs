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
    this.initialPdfRevisionMode = false,
    this.pdfRevisionSegmentPanelBuilder,
    this.onBatchFontApply,
    this.onBatchLeadingApply,
    this.getFilteredSelectableSegmentIndices,
    this.onPdfRevisionModeEntered,
    this.pdfPreviewJumpPageListenable,
    this.pdfPreviewJumpPageTriggerListenable,
    this.autoFollowSegmentPdfPageListenable,
    this.onAutoFollowSegmentPdfPageChanged,
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
  final bool initialPdfRevisionMode;
  final PdfRevisionSegmentPanelBuilder? pdfRevisionSegmentPanelBuilder;
  final Future<void> Function(Set<int> selectedIndices)? onBatchFontApply;
  final Future<void> Function(Set<int> selectedIndices)? onBatchLeadingApply;
  final Set<int> Function()? getFilteredSelectableSegmentIndices;
  final Future<void> Function()? onPdfRevisionModeEntered;
  final ValueListenable<int?>? pdfPreviewJumpPageListenable;
  final ValueListenable<int>? pdfPreviewJumpPageTriggerListenable;
  final ValueListenable<bool>? autoFollowSegmentPdfPageListenable;
  final ValueChanged<bool>? onAutoFollowSegmentPdfPageChanged;
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
  bool _pdfRevisionMode = false;
  bool _autoRefreshPdf = true;
  int _displayPdfRevision = 0;
  Set<int> _displayDirtySegmentIndices = <int>{};
  final Set<int> _selectedSegmentIndices = <int>{};
  final PdfContinuousScrollController _pdfNavigationController =
      PdfContinuousScrollController();
  int _comparePdfCurrentPage = 1;
  int _comparePdfTotalPages = 0;

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
    if (widget.initialPdfRevisionMode && _supportsPdfRevision) {
      // Enter revision layout on the first frame so we do not briefly mount
      // PdfCompareContinuousView (source + target downloads) before revision mode.
      _pdfRevisionMode = true;
      WidgetsBinding.instance.addPostFrameCallback((_) {
        unawaited(_enterPdfRevisionMode());
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
  void dispose() {
    widget.pdfRenderRevisionListenable
        ?.removeListener(_onPdfRevisionListenableChanged);
    widget.pdfPreviewJumpPageTriggerListenable
        ?.removeListener(_onPdfPreviewJumpPageRequested);
    _pdfNavigationController.dispose();
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
    unawaited(_pdfNavigationController.jumpToPage(pageNumber));
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

  void _togglePdfRevisionMode() {
    if (!_pdfRevisionMode) {
      unawaited(_enterPdfRevisionMode());
      return;
    }
    setState(() {
      _pdfRevisionMode = false;
      _selectedSegmentIndices.clear();
      _comparePdfCurrentPage = 1;
      _comparePdfTotalPages = 0;
    });
  }

  Future<void> _enterPdfRevisionMode() async {
    if (!_supportsPdfRevision) {
      return;
    }
    if (!_pdfRevisionMode && mounted) {
      setState(() {
        _pdfRevisionMode = true;
      });
    }
    final Future<void> Function()? enterHandler =
        widget.onPdfRevisionModeEntered;
    if (enterHandler != null) {
      unawaited(enterHandler());
    }
  }

  void _toggleSegmentSelection(int index, bool selected) {
    setState(() {
      if (selected) {
        _selectedSegmentIndices.add(index);
      } else {
        _selectedSegmentIndices.remove(index);
      }
    });
  }

  void _bulkSelectAll(Set<int> indices) {
    if (indices.isEmpty) {
      return;
    }
    setState(() {
      _selectedSegmentIndices.addAll(indices);
    });
  }

  void _bulkInvertSelection(Set<int> indices) {
    if (indices.isEmpty) {
      return;
    }
    setState(() {
      for (final int index in indices) {
        if (_selectedSegmentIndices.contains(index)) {
          _selectedSegmentIndices.remove(index);
        } else {
          _selectedSegmentIndices.add(index);
        }
      }
    });
  }

  Widget _buildRevisionSegmentPanel() {
    final PdfRevisionSegmentPanelBuilder? builder =
        widget.pdfRevisionSegmentPanelBuilder;
    if (builder == null) {
      return const SizedBox.shrink();
    }
    return builder(
      selectedSegmentIndices: _selectedSegmentIndices,
      onSegmentSelectionToggle: _toggleSegmentSelection,
      getFilteredSelectableSegmentIndices:
          widget.getFilteredSelectableSegmentIndices ?? () => <int>{},
      onBulkSelectAll: _bulkSelectAll,
      onBulkInvertSelection: _bulkInvertSelection,
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
    if (_selectedSegmentIndices.isEmpty || widget.onBatchFontApply == null) {
      return;
    }
    await widget.onBatchFontApply!(_selectedSegmentIndices);
  }

  Future<void> _applyBatchLeading() async {
    if (_selectedSegmentIndices.isEmpty ||
        widget.onBatchLeadingApply == null) {
      return;
    }
    await widget.onBatchLeadingApply!(_selectedSegmentIndices);
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

  Widget _buildPdfRevisionPanel(AppLocalizations l10n) {
    final Map<String, String> formatParams = _buildFormatParams();
    final String targetPdfUrl = _buildTargetPdfUrl(formatParams);
    final String viewerUrl = targetPdfUrl.startsWith('http')
        ? targetPdfUrl
        : '${AppConfig.baseUrl}$targetPdfUrl';

    final Widget segmentPanel = widget.segmentUiRevisionListenable == null
        ? _buildRevisionSegmentPanel()
        : ValueListenableBuilder<int>(
            valueListenable: widget.segmentUiRevisionListenable!,
            builder: (BuildContext context, int _, Widget? __) {
              return _buildRevisionSegmentPanel();
            },
          );

    return Row(
      children: <Widget>[
        Expanded(
          flex: 2,
          child: segmentPanel,
        ),
        const VerticalDivider(width: 1),
        Expanded(
          flex: 3,
          child: PreviewZoomableViewport(
            controller: _viewportController,
            childHandlesVerticalScroll: true,
            child: PdfPreview(
              downloadUrl: targetPdfUrl,
              viewerUrl: viewerUrl,
              rendererType: widget.baseMode.rendererType,
              compact: true,
              navigationController: _pdfNavigationController,
              onDownload: widget.onDownload,
              onRequestPreviewSettings: widget.onRequestPreviewSettings,
            ),
          ),
        ),
      ],
    );
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
    if (_pdfRevisionMode && _supportsPdfRevision) {
      return _buildPdfRevisionPanel(l10n);
    }
    return _buildComparePreviewBody(l10n);
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
        _pdfRevisionMode && _supportsPdfRevision;
    return Material(
      color: Theme.of(context).colorScheme.surfaceContainerHighest,
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
        child: Row(
          children: <Widget>[
            Icon(
              isFullscreenView
                  ? Icons.fullscreen_exit
                  : (_pdfRevisionMode ? Icons.edit_note : Icons.compare_arrows),
              size: 18,
            ),
            const SizedBox(width: 8),
            Text(
              _pdfRevisionMode
                  ? l10n.translationPreviewPdfRevision
                  : l10n.translationPreviewFullDocumentCompare,
              style: const TextStyle(fontWeight: FontWeight.w600),
            ),
            if (_supportsPdfRevision) ...<Widget>[
              const SizedBox(width: 8),
              TextButton.icon(
                onPressed: _togglePdfRevisionMode,
                icon: Icon(
                  _pdfRevisionMode ? Icons.compare_arrows : Icons.edit_note,
                  size: 16,
                ),
                label: Text(
                  _pdfRevisionMode
                      ? l10n.translationPreviewPdfRevisionCompare
                      : l10n.translationPreviewPdfRevision,
                ),
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
              if (_selectedSegmentIndices.isNotEmpty &&
                  widget.onBatchFontApply != null)
                Tooltip(
                  message: l10n.translationPreviewBatchFontTooltip,
                  child: TextButton.icon(
                    onPressed: _applyBatchFont,
                    icon: const Icon(Icons.format_size, size: 16),
                    label: Text(l10n.translationPreviewBatchFont),
                  ),
                ),
              if (kPdfLeadingTypographyUiEnabled &&
                  _selectedSegmentIndices.isNotEmpty &&
                  widget.onBatchLeadingApply != null)
                Tooltip(
                  message: l10n.translationPreviewBatchLeadingTooltip,
                  child: TextButton.icon(
                    onPressed: _applyBatchLeading,
                    icon: const Icon(Icons.format_line_spacing, size: 16),
                    label: Text(l10n.translationPreviewBatchLeading),
                  ),
                ),
            ],
            if (!_pdfRevisionMode &&
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
            if (!_pdfRevisionMode &&
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
