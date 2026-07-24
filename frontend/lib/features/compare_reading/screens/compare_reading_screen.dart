// SPDX-FileCopyrightText: 2026 Zampher
// SPDX-License-Identifier: MPL-2.0

import 'dart:io' show File;
import 'dart:typed_data';

import 'package:file_picker/file_picker.dart';
import 'package:flutter/foundation.dart' show kIsWeb;
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../app/app_router.dart';
import '../../../core/utils/file_picker_helper.dart';
import '../../../l10n/app_localizations.dart';
import '../../../shared/utils/app_logger.dart';
import '../../../shared/utils/message_service.dart';
import '../../translation/widgets/pdf_compare_continuous_view.dart';
import '../../translation/widgets/translation_result/preview_viewport.dart';
import '../models/compare_document_model.dart';
import '../models/compare_reading_layout_mode.dart';
import '../providers/compare_reading_session_provider.dart';
import '../services/compare_document_loader.dart';
import '../widgets/compare_image_panes.dart';
import '../widgets/compare_layout_double_tap_detector.dart';
import '../widgets/compare_scrollable_panes.dart';
import '../widgets/compare_solo_document_view.dart';

/// Standalone side-by-side document compare reading (no translation/revision).
class CompareReadingScreen extends ConsumerStatefulWidget {
  const CompareReadingScreen({super.key});

  @override
  ConsumerState<CompareReadingScreen> createState() =>
      _CompareReadingScreenState();
}

class _CompareReadingScreenState extends ConsumerState<CompareReadingScreen> {
  final CompareDocumentLoader _loader = CompareDocumentLoader();
  final PreviewViewportController _viewportController =
      PreviewViewportController();

  bool _loadingSource = false;
  bool _loadingTarget = false;
  String? _loadError;

  @override
  void dispose() {
    _viewportController.dispose();
    super.dispose();
  }

  CompareReadingSessionNotifier get _sessionNotifier =>
      ref.read(compareReadingSessionProvider.notifier);

  Future<void> _pickDocument({required bool isSource}) async {
    final AppLocalizations l10n = AppLocalizations.of(context)!;
    setState(() {
      _loadError = null;
      if (isSource) {
        _loadingSource = true;
      } else {
        _loadingTarget = true;
      }
    });
    try {
      final FilePickerResult? result = await FilePickerHelper.pickFiles(
        type: FileType.custom,
        allowedExtensions: CompareDocumentLoader.supportedExtensions,
        withData: true,
        dialogTitle: isSource
            ? l10n.compareReadingPickSource
            : l10n.compareReadingPickTarget,
      );
      if (result == null || result.files.isEmpty) {
        AppLogger.log(
          'CompareReadingScreen',
          'File pick cancelled (isSource=$isSource)',
          level: LogLevel.info,
        );
        return;
      }
      final PlatformFile file = result.files.first;
      final String name = file.name;
      Uint8List? bytes = file.bytes;
      if (bytes == null &&
          !kIsWeb &&
          file.path != null &&
          file.path!.isNotEmpty) {
        AppLogger.log(
          'CompareReadingScreen',
          'bytes null; reading from path=${file.path}',
          level: LogLevel.info,
        );
        bytes = await File(file.path!).readAsBytes();
      }
      if (bytes == null) {
        AppLogger.log(
          'CompareReadingScreen',
          'Picked file has null bytes name=$name path=${file.path}',
          level: LogLevel.error,
        );
        throw StateError(l10n.compareReadingReadBytesFailed(name));
      }
      final CompareDocumentModel doc = await _loader.load(
        fileName: name,
        bytes: bytes,
      );
      if (!mounted) {
        return;
      }
      if (isSource) {
        _sessionNotifier.setSource(doc);
      } else {
        _sessionNotifier.setTarget(doc);
      }
      _viewportController.resetZoom();
      AppLogger.log(
        'CompareReadingScreen',
        'Loaded ${isSource ? 'source' : 'target'}: '
        'name=${doc.fileName} kind=${doc.kind} contentType=${doc.contentType}',
        level: LogLevel.info,
      );
    } catch (e, st) {
      AppLogger.log(
        'CompareReadingScreen',
        'Pick/load failed isSource=$isSource: $e\n$st',
        level: LogLevel.error,
      );
      if (!mounted) {
        return;
      }
      setState(() {
        _loadError = e.toString();
      });
      MessageService.showError(context, e.toString());
    } finally {
      if (mounted) {
        setState(() {
          if (isSource) {
            _loadingSource = false;
          } else {
            _loadingTarget = false;
          }
        });
      }
    }
  }

  Widget _buildEmptyPicker(
    AppLocalizations l10n,
    CompareReadingSession session,
  ) {
    return Center(
      child: ConstrainedBox(
        constraints: const BoxConstraints(maxWidth: 560),
        child: Padding(
          padding: const EdgeInsets.all(24),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: <Widget>[
              Text(
                l10n.compareReadingIntro,
                textAlign: TextAlign.center,
                style: Theme.of(context).textTheme.bodyLarge,
              ),
              const SizedBox(height: 8),
              Text(
                l10n.compareReadingSupportedFormats(
                  CompareDocumentLoader.supportedExtensions.join(', '),
                ),
                textAlign: TextAlign.center,
                style: Theme.of(context).textTheme.bodySmall?.copyWith(
                      color: Theme.of(context).colorScheme.onSurfaceVariant,
                    ),
              ),
              const SizedBox(height: 24),
              Row(
                children: <Widget>[
                  Expanded(
                    child: _buildPickCard(
                      title: l10n.translationPreviewPanelSource,
                      fileName: session.source?.fileName,
                      loading: _loadingSource,
                      onPick: () => _pickDocument(isSource: true),
                    ),
                  ),
                  const SizedBox(width: 16),
                  Expanded(
                    child: _buildPickCard(
                      title: l10n.translationPreviewPanelTarget,
                      fileName: session.target?.fileName,
                      loading: _loadingTarget,
                      onPick: () => _pickDocument(isSource: false),
                    ),
                  ),
                ],
              ),
              if (_loadError != null) ...<Widget>[
                const SizedBox(height: 16),
                Text(
                  _loadError!,
                  textAlign: TextAlign.center,
                  style: TextStyle(
                    color: Theme.of(context).colorScheme.error,
                  ),
                ),
              ],
              if (session.bothReady && !session.kindsMatch) ...<Widget>[
                const SizedBox(height: 16),
                Text(
                  l10n.compareReadingKindMismatch,
                  textAlign: TextAlign.center,
                  style: TextStyle(
                    color: Theme.of(context).colorScheme.error,
                  ),
                ),
              ],
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildPickCard({
    required String title,
    required String? fileName,
    required bool loading,
    required VoidCallback onPick,
  }) {
    final AppLocalizations l10n = AppLocalizations.of(context)!;
    final bool hasFile = fileName != null && fileName.isNotEmpty;
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: <Widget>[
            Text(title, style: const TextStyle(fontWeight: FontWeight.w600)),
            const SizedBox(height: 8),
            Text(
              fileName ?? '—',
              maxLines: 2,
              overflow: TextOverflow.ellipsis,
            ),
            const SizedBox(height: 12),
            FilledButton.icon(
              onPressed: loading ? null : onPick,
              icon: loading
                  ? const SizedBox(
                      width: 16,
                      height: 16,
                      child: CircularProgressIndicator(strokeWidth: 2),
                    )
                  : Icon(hasFile ? Icons.swap_horiz : Icons.folder_open),
              label: Text(
                hasFile
                    ? l10n.compareReadingReplaceFile
                    : l10n.compareReadingImport,
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildPaneFileBar({
    required String title,
    required String fileName,
    required bool loading,
    required VoidCallback onReplace,
  }) {
    final AppLocalizations l10n = AppLocalizations.of(context)!;
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
      child: Row(
        children: <Widget>[
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: <Widget>[
                Text(
                  title,
                  style: Theme.of(context).textTheme.labelMedium?.copyWith(
                        fontWeight: FontWeight.w600,
                      ),
                ),
                Text(
                  fileName,
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: Theme.of(context).textTheme.bodySmall,
                ),
              ],
            ),
          ),
          TextButton.icon(
            onPressed: loading ? null : onReplace,
            icon: loading
                ? const SizedBox(
                    width: 14,
                    height: 14,
                    child: CircularProgressIndicator(strokeWidth: 2),
                  )
                : const Icon(Icons.swap_horiz, size: 16),
            label: Text(l10n.compareReadingReplaceFile),
          ),
        ],
      ),
    );
  }

  Widget _buildFileBars(
    AppLocalizations l10n,
    CompareReadingSession session,
  ) {
    final CompareDocumentModel source = session.source!;
    final CompareDocumentModel target = session.target!;
    final CompareReadingLayoutMode mode = session.layoutMode;

    Widget sourceBar() => _buildPaneFileBar(
          title: l10n.translationPreviewPanelSource,
          fileName: source.fileName,
          loading: _loadingSource,
          onReplace: () => _pickDocument(isSource: true),
        );
    Widget targetBar() => _buildPaneFileBar(
          title: l10n.translationPreviewPanelTarget,
          fileName: target.fileName,
          loading: _loadingTarget,
          onReplace: () => _pickDocument(isSource: false),
        );

    switch (mode) {
      case CompareReadingLayoutMode.sourceOnly:
        return Material(
          color: Theme.of(context).colorScheme.surfaceContainerHighest,
          child: sourceBar(),
        );
      case CompareReadingLayoutMode.targetOnly:
        return Material(
          color: Theme.of(context).colorScheme.surfaceContainerHighest,
          child: targetBar(),
        );
      case CompareReadingLayoutMode.compare:
        return Material(
          color: Theme.of(context).colorScheme.surfaceContainerHighest,
          child: IntrinsicHeight(
            child: Row(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: <Widget>[
                Expanded(child: sourceBar()),
                const VerticalDivider(width: 1),
                Expanded(child: targetBar()),
              ],
            ),
          ),
        );
    }
  }

  Widget _buildSoloBody(
    CompareDocumentModel doc, {
    required String paneKey,
  }) {
    final bool isHtml = doc.contentType == 'html';
    // Scrollable panes (esp. HTML WebView) must own vertical scroll in a
    // bounded viewport — nesting platform views in outer scroll crashes Windows.
    _viewportController.childManagesZoom = isHtml && !kIsWeb;
    return PreviewZoomableViewport(
      key: ValueKey<String>('solo-$paneKey-${doc.fileName}-${doc.kind}'),
      controller: _viewportController,
      childHandlesVerticalScroll: true,
      child: CompareSoloDocumentView(
        document: doc,
        paneKey: paneKey,
        viewportController: _viewportController,
      ),
    );
  }

  Widget _buildSideBySideBody(
    AppLocalizations l10n,
    CompareReadingSession session,
  ) {
    final CompareDocumentModel source = session.source!;
    final CompareDocumentModel target = session.target!;
    final bool linked = session.linkedScroll && session.kindsMatch;
    final String pairKey =
        '${source.fileName}:${source.kind}|${target.fileName}:${target.kind}';
    final bool isHtmlPair =
        source.contentType == 'html' && target.contentType == 'html';

    if (source.kind == ComparePaneKind.pdf &&
        target.kind == ComparePaneKind.pdf) {
      _viewportController.childManagesZoom = true;
      return PreviewZoomableViewport(
        key: ValueKey<String>('pdf-$pairKey'),
        controller: _viewportController,
        childHandlesVerticalScroll: true,
        child: PdfCompareContinuousView(
          sourcePdfBytes: source.pdfBytes,
          targetPdfBytes: target.pdfBytes,
          linkedScroll: linked,
          viewportController: _viewportController,
        ),
      );
    }

    if (source.kind == ComparePaneKind.image &&
        target.kind == ComparePaneKind.image) {
      _viewportController.childManagesZoom = true;
      return PreviewZoomableViewport(
        key: ValueKey<String>('image-$pairKey'),
        controller: _viewportController,
        childHandlesVerticalScroll: true,
        child: CompareImagePanes(
          sourceBytes: source.imageBytes!,
          targetBytes: target.imageBytes!,
          linkedScroll: linked,
          viewportController: _viewportController,
        ),
      );
    }

    if (source.kind == ComparePaneKind.scrollable &&
        target.kind == ComparePaneKind.scrollable) {
      // Desktop HTML uses WebView2; avoid Transform.scale on platform views.
      _viewportController.childManagesZoom = isHtmlPair && !kIsWeb;
      return PreviewZoomableViewport(
        key: ValueKey<String>('text-$pairKey'),
        controller: _viewportController,
        childHandlesVerticalScroll: true,
        child: CompareScrollablePanes(
          source: source,
          target: target,
          linkedScroll: linked,
        ),
      );
    }

    AppLogger.log(
      'CompareReadingScreen',
      'Kind mismatch in body source=${source.kind} target=${target.kind}',
      level: LogLevel.error,
    );
    return Center(child: Text(l10n.compareReadingKindMismatch));
  }

  Widget _buildReadingShell(
    AppLocalizations l10n,
    CompareReadingSession session,
  ) {
    final Widget body;
    switch (session.layoutMode) {
      case CompareReadingLayoutMode.sourceOnly:
        body = _buildSoloBody(session.source!, paneKey: 'source');
      case CompareReadingLayoutMode.targetOnly:
        body = _buildSoloBody(session.target!, paneKey: 'target');
      case CompareReadingLayoutMode.compare:
        body = _buildSideBySideBody(l10n, session);
    }

    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: <Widget>[
        _buildFileBars(l10n, session),
        const Divider(height: 1),
        Expanded(
          child: CompareLayoutDoubleTapDetector(
            layoutMode: session.layoutMode,
            onToggleSourceSolo: _sessionNotifier.toggleSourceSolo,
            onToggleTargetSolo: _sessionNotifier.toggleTargetSolo,
            child: body,
          ),
        ),
      ],
    );
  }

  Widget _buildLayoutModeButtons(
    AppLocalizations l10n,
    CompareReadingLayoutMode mode,
  ) {
    return ToggleButtons(
      constraints: const BoxConstraints(minWidth: 36, minHeight: 36),
      borderRadius: BorderRadius.circular(8),
      isSelected: <bool>[
        mode == CompareReadingLayoutMode.compare,
        mode == CompareReadingLayoutMode.sourceOnly,
        mode == CompareReadingLayoutMode.targetOnly,
      ],
      onPressed: (int index) {
        final CompareReadingLayoutMode next;
        switch (index) {
          case 1:
            next = CompareReadingLayoutMode.sourceOnly;
          case 2:
            next = CompareReadingLayoutMode.targetOnly;
          default:
            next = CompareReadingLayoutMode.compare;
        }
        _sessionNotifier.setLayoutMode(next);
        AppLogger.log(
          'CompareReadingScreen',
          'Layout mode set to $next via toolbar',
          level: LogLevel.info,
        );
      },
      children: <Widget>[
        Tooltip(
          message: l10n.compareReadingModeCompare,
          child: const Icon(Icons.compare, size: 18),
        ),
        Tooltip(
          message: l10n.compareReadingModeSourceOnly,
          child: const Icon(Icons.menu_book_outlined, size: 18),
        ),
        Tooltip(
          message: l10n.compareReadingModeTargetOnly,
          child: const Icon(Icons.translate, size: 18),
        ),
      ],
    );
  }

  @override
  Widget build(BuildContext context) {
    final AppLocalizations l10n = AppLocalizations.of(context)!;
    final CompareReadingSession session =
        ref.watch(compareReadingSessionProvider);
    final bool showReading = session.canShowCompare;
    final bool showLinkScroll =
        showReading && session.layoutMode == CompareReadingLayoutMode.compare;

    return Scaffold(
      appBar: AppBar(
        title: Text(l10n.compareReadingTitle),
        leadingWidth: 220,
        leading: OwlangsAppBarLeading(
          onTap: () => context.go(AppRouter.homeRoute),
        ),
        actions: <Widget>[
          if (showReading) ...<Widget>[
            _buildLayoutModeButtons(l10n, session.layoutMode),
            const SizedBox(width: 8),
            if (showLinkScroll)
              Tooltip(
                message: l10n.translationPreviewSyncScrollDesc,
                child: Row(
                  mainAxisSize: MainAxisSize.min,
                  children: <Widget>[
                    Checkbox(
                      value: session.linkedScroll,
                      onChanged: session.kindsMatch
                          ? (bool? value) {
                              _sessionNotifier.setLinkedScroll(value ?? false);
                            }
                          : null,
                      visualDensity: VisualDensity.compact,
                    ),
                    Text(
                      l10n.translationPreviewSyncScroll,
                      style: Theme.of(context).textTheme.bodySmall,
                    ),
                    const SizedBox(width: 8),
                  ],
                ),
              ),
            PreviewZoomToolbarActions(
              viewportController: _viewportController,
              iconSize: 18,
              compact: true,
            ),
            const SizedBox(width: 4),
            TextButton(
              onPressed: () {
                _sessionNotifier.clearSession();
                _viewportController.resetZoom();
                setState(() {
                  _loadError = null;
                });
              },
              child: Text(l10n.compareReadingClearSession),
            ),
          ],
          IconButton(
            tooltip: l10n.homeNavTooltipHome,
            onPressed: () => context.go(AppRouter.homeRoute),
            icon: const Icon(Icons.home_outlined),
          ),
        ],
      ),
      body: SafeArea(
        child: showReading
            ? _buildReadingShell(l10n, session)
            : _buildEmptyPicker(l10n, session),
      ),
    );
  }
}
