// SPDX-FileCopyrightText: 2025 QinHan
// SPDX-License-Identifier: MPL-2.0

import 'package:flutter/material.dart';
import 'package:pdfx/pdfx.dart';

import '../../../l10n/app_localizations.dart';
import '../../../shared/utils/compare_scroll_sync/compare_scroll_sync.dart';
import 'pdf_continuous_page.dart';
import 'pdf_continuous_scroll_view.dart';
import 'translation_result/preview_selection.dart';
import 'translation_result/preview_viewport.dart';

class PdfPreview extends StatefulWidget {
  const PdfPreview({
    required this.downloadUrl,
    required this.viewerUrl,
    super.key,
    this.rendererType,
    this.panelLabel,
    this.compact = false,
    this.onDownload,
    this.onRequestPreviewSettings,
    this.scrollSyncGroup,
    this.scrollSyncPaneId,
    this.navigationController,
    this.scrollController,
    this.showScrollbar = true,
    this.highlightPageNumber,
    this.highlightBboxes,
    this.bboxEditMode = false,
    this.onEditBboxChanged,
    this.onEditBboxReset,
  });

  final String downloadUrl;
  final String viewerUrl;
  final String? rendererType;
  final String? panelLabel;
  final bool compact;
  final void Function(String format, String url)? onDownload;
  final Future<PreviewSelection?> Function()? onRequestPreviewSettings;
  final CompareScrollSyncGroup? scrollSyncGroup;
  final String? scrollSyncPaneId;
  final PdfContinuousScrollController? navigationController;
  final ScrollController? scrollController;
  final bool showScrollbar;

  /// 1-based page number to render the highlight rectangle on.
  final int? highlightPageNumber;

  /// Bounding boxes in PDF points: each `[x0, y0, x1, y1]`.
  final List<List<double>>? highlightBboxes;

  /// Whether bbox edit mode is active.
  final bool bboxEditMode;

  /// Called when the user finishes dragging a bbox overlay.
  final BboxEditChangedCallback? onEditBboxChanged;

  /// Called when the user taps reset on a specific bbox overlay.
  final BboxEditResetCallback? onEditBboxReset;

  @override
  State<PdfPreview> createState() => _PdfPreviewIoState();
}

class _PdfPreviewIoState extends State<PdfPreview> {
  String? _rendererType;
  int _totalPages = 0;
  int _currentPage = 1;
  PreviewViewportController? _viewportController;
  PreviewFullscreenOverlay? _fullscreenOverlay;
  bool _isFullscreen = false;

  bool get _supportsViewportControls => !widget.compact;

  @override
  void initState() {
    super.initState();
    if (_supportsViewportControls) {
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
    }
    _rendererType = widget.rendererType;
  }

  @override
  void didUpdateWidget(covariant PdfPreview oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.rendererType != widget.rendererType ||
        oldWidget.downloadUrl != widget.downloadUrl) {
      _rendererType = widget.rendererType;
      _currentPage = 1;
      _totalPages = 0;
    }
  }

  Future<void> _openPreviewSettings() async {
    final Future<PreviewSelection?> Function()? callback =
        widget.onRequestPreviewSettings;
    if (callback == null) {
      return;
    }
    final PreviewSelection? selection = await callback();
    if (!mounted) {
      return;
    }
    if (selection == null || !selection.mode.usesPdfPreview) {
      return;
    }
    final String? nextRenderer = selection.mode.rendererType;
    if (nextRenderer != null && nextRenderer != _rendererType) {
      setState(() {
        _rendererType = nextRenderer;
      });
    }
  }

  void _toggleFullscreen() {
    if (!_supportsViewportControls || _fullscreenOverlay == null) {
      return;
    }
    if (_isFullscreen) {
      _fullscreenOverlay!.exit();
      return;
    }
    _fullscreenOverlay!.enter(
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

  @override
  void dispose() {
    _fullscreenOverlay?.dispose();
    _viewportController?.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    if (_isFullscreen && _supportsViewportControls) {
      return const SizedBox.shrink();
    }

    final AppLocalizations? l10n = AppLocalizations.of(context);
    return _buildPreviewShell(context, isFullscreenView: false, l10n: l10n);
  }

  Widget _buildPreviewShell(
    BuildContext context, {
    required bool isFullscreenView,
    AppLocalizations? l10n,
  }) {
    final Widget body = PdfContinuousPreviewLoader(
      key: ValueKey<String>('$_rendererType:${widget.downloadUrl}'),
      downloadUrl: widget.downloadUrl,
      rendererType: _rendererType,
      navigationController: widget.navigationController,
      scrollController: widget.scrollController,
      showScrollbar: widget.showScrollbar,
      highlightPageNumber: widget.highlightPageNumber,
      highlightBboxes: widget.highlightBboxes,
      bboxEditMode: widget.bboxEditMode,
      onEditBboxChanged: widget.onEditBboxChanged,
      onEditBboxReset: widget.onEditBboxReset,
      onDocumentLoaded: (PdfDocument document) {
        if (!mounted) {
          return;
        }
        setState(() {
          _totalPages = document.pagesCount;
          _currentPage = 1;
        });
      },
      onPageVisible: (int pageNumber) {
        if (!mounted || pageNumber == _currentPage) {
          return;
        }
        setState(() {
          _currentPage = pageNumber;
        });
      },
    );

    return Column(
      children: <Widget>[
        _buildToolbar(context, l10n, isFullscreenView: isFullscreenView),
        const Divider(height: 1),
        Expanded(
          child: _supportsViewportControls
              ? PreviewZoomableViewport(
                  controller: _viewportController!,
                  childHandlesVerticalScroll: true,
                  child: body,
                )
              : body,
        ),
      ],
    );
  }

  String _toolbarTitle(AppLocalizations? l10n) {
    if (widget.panelLabel != null) {
      return widget.panelLabel!;
    }
    if (_rendererType == 'typst_overlay') {
      return l10n?.translationExportPdfPreserveLayout ?? 'Preserve layout';
    }
    return l10n?.translationExportPdfReflow ?? 'Reflow PDF';
  }

  Widget _buildToolbar(
    BuildContext context,
    AppLocalizations? l10n, {
    bool isFullscreenView = false,
  }) =>
      Container(
        color: Theme.of(context).colorScheme.surfaceContainerHighest,
        padding: EdgeInsets.symmetric(
          horizontal: widget.compact ? 8 : 16,
          vertical: widget.compact ? 4 : 8,
        ),
        child: Row(
          children: <Widget>[
            Text(
              _toolbarTitle(l10n),
              style: Theme.of(context).textTheme.bodyMedium,
            ),
            if (_totalPages > 0) ...<Widget>[
              const SizedBox(width: 12),
              Text(
                l10n?.translationPreviewPdfPageIndicator(
                      _currentPage.toString(),
                      _totalPages.toString(),
                    ) ??
                    'Page $_currentPage / $_totalPages',
                style: Theme.of(context).textTheme.bodySmall?.copyWith(
                      color: Theme.of(context).colorScheme.onSurfaceVariant,
                    ),
              ),
            ],
            const Spacer(),
            if (_supportsViewportControls && _viewportController != null)
              PreviewZoomToolbarActions(
                viewportController: _viewportController!,
                iconSize: 20,
              ),
            if (!widget.compact &&
                widget.onRequestPreviewSettings != null) ...<Widget>[
              const SizedBox(width: 8),
              IconButton(
                tooltip:
                    l10n?.translationPreviewReopenSettings ?? 'Preview settings',
                onPressed: _openPreviewSettings,
                icon: const Icon(Icons.settings),
              ),
            ],
            if (!widget.compact && widget.onDownload != null)
              IconButton(
                tooltip: 'Download PDF',
                onPressed: () {
                  widget.onDownload?.call('pdf', widget.downloadUrl);
                },
                icon: const Icon(Icons.download),
              ),
            if (_supportsViewportControls && _viewportController != null)
              PreviewViewportTrailingActions(
                viewportController: _viewportController!,
                isFullscreen: _isFullscreen,
                onToggleFullscreen: _toggleFullscreen,
                iconSize: 20,
              ),
          ],
        ),
      );
}
