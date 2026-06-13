// SPDX-FileCopyrightText: 2025 QinHan
// SPDX-License-Identifier: MPL-2.0

import 'package:flutter/material.dart';
import 'package:pdfx/pdfx.dart';

import '../../../l10n/app_localizations.dart';
import '../../../shared/utils/compare_scroll_sync/compare_scroll_sync.dart';
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

  @override
  State<PdfPreview> createState() => _PdfPreviewWebState();
}

class _PdfPreviewWebState extends State<PdfPreview> {
  String? _rendererType;
  int _totalPages = 0;
  int _currentPage = 1;

  @override
  void initState() {
    super.initState();
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
    if (selection == null) {
      return;
    }
    if (selection.mode.usesPdfPreview) {
      final String? nextRenderer = selection.mode.rendererType;
      if (nextRenderer != null && nextRenderer != _rendererType) {
        setState(() {
          _rendererType = nextRenderer;
        });
      }
    }
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

  @override
  Widget build(BuildContext context) {
    final AppLocalizations? l10n = AppLocalizations.of(context);
    return Column(
      children: <Widget>[
        _buildToolbar(context, l10n),
        const Divider(height: 1),
        Expanded(
          child: PdfContinuousPreviewLoader(
            key: ValueKey<String>('$_rendererType:${widget.downloadUrl}'),
            downloadUrl: widget.downloadUrl,
            rendererType: _rendererType,
            navigationController: widget.navigationController,
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
          ),
        ),
      ],
    );
  }

  Widget _buildToolbar(BuildContext context, AppLocalizations? l10n) {
    return Container(
      color: Theme.of(context).colorScheme.surfaceContainerHighest,
      padding: EdgeInsets.symmetric(
        horizontal: widget.compact ? 8 : 16,
        vertical: widget.compact ? 4 : 8,
      ),
      child: Row(
        children: <Widget>[
          Text(_toolbarTitle(l10n)),
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
          if (!widget.compact && widget.onRequestPreviewSettings != null)
            IconButton(
              tooltip:
                  l10n?.translationPreviewReopenSettings ?? 'Preview settings',
              onPressed: _openPreviewSettings,
              icon: const Icon(Icons.settings),
            ),
          if (!widget.compact && widget.onDownload != null)
            IconButton(
              tooltip: 'Download PDF',
              onPressed: () {
                widget.onDownload?.call('pdf', widget.downloadUrl);
              },
              icon: const Icon(Icons.download),
            ),
        ],
      ),
    );
  }
}
