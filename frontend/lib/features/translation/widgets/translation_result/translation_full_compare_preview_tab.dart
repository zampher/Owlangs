// SPDX-FileCopyrightText: 2026 Zampher
// SPDX-License-Identifier: MPL-2.0

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../../app/app_config.dart';
import '../../../../l10n/app_localizations.dart';
import '../../../../shared/services/translation_service.dart';
import '../../providers/format_settings_provider.dart';
import '../pdf_compare_continuous_view.dart';
import 'html_compare_reader_view.dart';
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
    this.translatedHtmlUrl,
    this.initialSyncScroll = false,
    super.key,
    this.onRequestPreviewSettings,
    this.onDownload,
    this.onSyncScrollChanged,
  });

  final String taskId;
  final TranslationPreviewMode baseMode;
  final bool isPdfSource;
  final bool isPdfWorkflow;
  final String? translatedPdfUrl;
  final String? translatedHtmlUrl;
  final bool initialSyncScroll;
  final Future<PreviewSelection?> Function()? onRequestPreviewSettings;
  final void Function(String format, String url)? onDownload;
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

  @override
  void initState() {
    super.initState();
    _syncScrollEnabled = widget.initialSyncScroll;
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

  bool get _isPdfCompare =>
      widget.baseMode == TranslationPreviewMode.pdfPreserve ||
      widget.baseMode == TranslationPreviewMode.pdfReflow;

  @override
  void didUpdateWidget(covariant TranslationFullComparePreviewTab oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.initialSyncScroll != widget.initialSyncScroll) {
      _syncScrollEnabled = widget.initialSyncScroll;
    }
  }

  @override
  void dispose() {
    _fullscreenOverlay.dispose();
    _viewportController.dispose();
    super.dispose();
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

  Widget _buildPreviewBody(AppLocalizations l10n) {
    final FormatSettings formatSettings =
        ref.watch(formatSettingsProviderFamily(widget.taskId));
    final TranslationService svc = TranslationService();

    final Map<String, String> formatParams = buildPreviewExportQueryParams(
      formatSettings,
      isPdfWorkflow: widget.isPdfWorkflow,
      rendererType: widget.baseMode.rendererType,
    );

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
    final String targetPdfUrl =
        mergePreviewUrl(widget.translatedPdfUrl!, formatParams);
    return PreviewZoomableViewport(
      controller: _viewportController,
      childHandlesVerticalScroll: true,
      child: PdfCompareContinuousView(
        sourceDownloadUrl: sourcePdfUrl,
        targetDownloadUrl: targetPdfUrl,
        targetRendererType: widget.baseMode.rendererType,
        linkedScroll: _syncScrollEnabled,
      ),
    );
  }

  Widget _buildPreviewToolbar(
    BuildContext context,
    AppLocalizations l10n, {
    required bool isFullscreenView,
  }) {
    return Material(
      color: Theme.of(context).colorScheme.surfaceContainerHighest,
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
        child: Row(
          children: <Widget>[
            Icon(
              isFullscreenView ? Icons.fullscreen_exit : Icons.compare_arrows,
              size: 18,
            ),
            const SizedBox(width: 8),
            Text(
              l10n.translationPreviewFullDocumentCompare,
              style: const TextStyle(fontWeight: FontWeight.w600),
            ),
            if (_isPdfCompare || widget.baseMode.usesHtmlPreview) ...<Widget>[
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
            const Spacer(),
            PreviewZoomToolbarActions(
              viewportController: _viewportController,
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
