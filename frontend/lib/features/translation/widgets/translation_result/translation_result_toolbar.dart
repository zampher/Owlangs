// SPDX-FileCopyrightText: 2025 QinHan
// SPDX-License-Identifier: MPL-2.0

import 'package:flutter/material.dart';
import 'package:flutter/foundation.dart'
    show kIsWeb, defaultTargetPlatform, TargetPlatform;
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../../../l10n/app_localizations.dart';
import '../../../../shared/widgets/pagination_bar.dart';
import '../../../../shared/utils/pagination.dart';
import '../../providers/segment_undo_redo_provider.dart';
import '../../providers/translation_state_provider_family.dart';
import '../../models/segment_pair.dart';
import '../common/exclusion_panel_button.dart';
import '../../../../shared/providers/settings_provider.dart';

/// Toolbar for translation result preview
class TranslationResultToolbar extends ConsumerWidget {
  const TranslationResultToolbar({
    required this.taskId,
    super.key,
    this.flowId,
    this.translationState,
    this.tokenUsage,
    this.failedSegmentsCount = 0,
    this.loadingHtmlPreview = false,
    this.isFullscreen = false,
    this.isFullscreenView = false,
    this.fileName,
    this.downloads,
    this.segmentsPaginationController,
    this.onCancelTranslation,
    this.onGlobalUndo,
    this.onGlobalRedo,
    this.onNavigateToFailedSegment,
    this.onViewPreview,
    this.onEnterPdfRevisionMode,
    this.onShowDownload,
    this.onToggleFullscreen,
    this.excludedCount = 0,
    this.isExclusionPanelExpanded = false,
    this.onToggleExclusionPanel,
    // Search functionality (optional)
    this.isSearchBoxVisible,
    this.searchQuery,
    this.searchMatchCount,
    this.currentSearchMatchIndex,
    this.onToggleSearch,
    this.onSearch,
    this.onNextSearchMatch,
    this.onPreviousSearchMatch,
    this.onCheckPdfFormulas,
    this.onRepairDocxMath,
    this.isMergedView = false,
    this.onToggleMergedView,
  });

  final String taskId;
  final String? flowId;
  final dynamic translationState;
  final Map<String, int>? tokenUsage;
  final int failedSegmentsCount;
  final bool loadingHtmlPreview;
  final bool isFullscreen;
  final bool isFullscreenView;
  final String? fileName;
  final Map<String, String>? downloads;
  final PagedListController<SegmentPair>? segmentsPaginationController;
  final VoidCallback? onCancelTranslation;
  final VoidCallback? onGlobalUndo;
  final VoidCallback? onGlobalRedo;
  final void Function(int direction)? onNavigateToFailedSegment;
  final VoidCallback? onViewPreview;
  final VoidCallback? onEnterPdfRevisionMode;
  final VoidCallback? onShowDownload;
  final VoidCallback? onToggleFullscreen;
  final int excludedCount;
  final bool isExclusionPanelExpanded;
  final VoidCallback? onToggleExclusionPanel;
  // Search functionality (optional)
  final bool? isSearchBoxVisible;
  final String? searchQuery;
  final int? searchMatchCount;
  final int? currentSearchMatchIndex;
  final VoidCallback? onToggleSearch;
  final void Function(String)? onSearch;
  final VoidCallback? onNextSearchMatch;
  final VoidCallback? onPreviousSearchMatch;
  // PDF 公式检测按钮回调（仅在 PDF 流程中可见）
  final VoidCallback? onCheckPdfFormulas;
  /// DOCX / texmath LLM repair（markdown_based 流程）
  final VoidCallback? onRepairDocxMath;
  /// Merged paragraph view toggle
  final bool isMergedView;
  final VoidCallback? onToggleMergedView;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final AppLocalizations l10n = AppLocalizations.of(context)!;
    final isTranslating = translationState?.isTranslating ?? false;
    final progress = translationState?.progress ?? 0;
    final statusText = translationState?.statusText?.toString() ?? '';
    final currentOperation =
        translationState?.currentOperation ?? TranslationOperation.none;
    final statusLower = statusText.toLowerCase();
    final hasDownloads = downloads != null && downloads!.isNotEmpty;
    // Treat status='processing' with 100% progress as a completed state.
    final isCompletedLike = statusLower == 'completed' ||
        (statusLower == 'processing' && progress >= 100);
    // Consider task completed when:
    // - backend explicitly reports completed/processing+100, OR
    // - translation is no longer running, no active operation, and progress>=100, OR
    // - we already have downloads from backend (only when NOT actively translating).
    // CRITICAL: hasDownloads must NOT hide progress bar during active translation,
    // because format conversion may leave downloads before translation starts.
    final isCompletedByArtifacts = isCompletedLike ||
        (!isTranslating &&
            ((currentOperation == TranslationOperation.none &&
                    progress >= 100) ||
                hasDownloads));
    // Show progress bar only when actively translating (not after completion)
    final isActive = !isCompletedByArtifacts &&
        (isTranslating ||
            currentOperation == TranslationOperation.translating ||
            currentOperation == TranslationOperation.retranslating ||
            statusLower == 'processing');
    // Hide progress bar when translation is completed (including processing+100%)
    final isCompleted = isCompletedByArtifacts ||
        statusLower == 'failed' ||
        statusLower == 'cancelled';
    final showProgressBar = isActive && !isCompleted;
    // Block entering reading mode during translation; allow switching back to segment view.
    final bool mergedViewEnabled =
        onToggleMergedView != null && (!isActive || isMergedView);

    return Container(
      padding: const EdgeInsets.symmetric(
        horizontal: 12,
        vertical: 2,
      ),
      constraints: const BoxConstraints(
        minHeight: 30,
        maxHeight: 30,
      ),
      decoration: BoxDecoration(
        color: Theme.of(context).colorScheme.surfaceContainerHighest,
        border: Border(
          bottom: BorderSide(color: Theme.of(context).dividerColor),
        ),
      ),
      child: Row(
        children: <Widget>[
          // Progress bar (shown only during active translation, hidden after completion)
          // Progress bar should expand to fill available space
          if (showProgressBar) ...<Widget>[
            Expanded(
              child: Row(
                children: <Widget>[
                  const SizedBox(width: 6), // Further reduced spacing
                  Expanded(
                    child: SizedBox(
                      height: 4, // Reduced from 6 to 4
                      child: LinearProgressIndicator(
                        value: progress / 100.0,
                        backgroundColor: Colors.grey.shade300,
                        valueColor: AlwaysStoppedAnimation<Color>(
                          _getStatusColor(statusText),
                        ),
                        minHeight: 4, // Reduced from 6 to 4
                      ),
                    ),
                  ),
                  // Cancel button and status text (progress% included here to avoid empty width flicker)
                  if (isActive) ...<Widget>[
                    const SizedBox(width: 4), // Further reduced spacing
                    // Cancel button placed before status text so its position never shifts
                    TextButton.icon(
                      onPressed: onCancelTranslation,
                      icon: const Icon(
                        Icons.cancel,
                        size: 12,
                      ), // Further reduced from 14 to 12
                      label: Text(
                        l10n.translationToolbarCancelButton,
                        style: const TextStyle(fontSize: 10),
                      ), // Further reduced font size
                      style: TextButton.styleFrom(
                        foregroundColor: Colors.red,
                        padding: const EdgeInsets.symmetric(
                          horizontal: 4, // Further reduced from 6
                          vertical: 2, // Further reduced from 4
                        ),
                        minimumSize:
                            const Size(0, 28), // Increased button height
                      ),
                    ),
                    const SizedBox(width: 4), // Further reduced spacing
                    Icon(
                      _getStatusIcon(statusText),
                      size: 14, // Further reduced from 16 to 14
                      color: _getStatusColor(statusText),
                    ),
                    const SizedBox(width: 4), // Further reduced spacing
                    SizedBox(
                      width: 12, // Further reduced from 14 to 12
                      height: 12, // Further reduced from 14 to 12
                      child: CircularProgressIndicator(
                        strokeWidth: 2,
                        valueColor: AlwaysStoppedAnimation<Color>(
                          _getStatusColor(statusText),
                        ),
                      ),
                    ),
                    const SizedBox(width: 4), // Further reduced spacing
                    Flexible(
                      child: Text(
                        () {
                          final msg = _getStatusDisplayText(l10n, statusText);
                          return msg.isNotEmpty ? msg : '$progress%';
                        }(),
                        style: TextStyle(
                          fontSize: 10, // Further reduced from 11 to 10
                          fontWeight: FontWeight.w600,
                          color: _getStatusColor(statusText),
                        ),
                        overflow: TextOverflow.ellipsis,
                        maxLines: 1,
                      ),
                    ),
                  ],
                ],
              ),
            ),
          ],
          // Left group: segment/text display operations (shown after translation)
          if (!showProgressBar) ...<Widget>[
            // Exclusion panel toggle button
            if (onToggleExclusionPanel != null) ...<Widget>[
              ExclusionPanelButton(
                excludedCount: excludedCount,
                isExpanded: isExclusionPanelExpanded,
                onToggle: onToggleExclusionPanel!,
              ),
              const SizedBox(width: 3),
            ],
            // Font size controls
            _buildFontSizeControls(context, ref),
            // Global Undo/Redo buttons
            _buildUndoRedoButtons(context, ref),
            // Search button (shown when segments are available)
            if (segmentsPaginationController != null &&
                segmentsPaginationController!.total > 0 &&
                onToggleSearch != null)
              IconButton(
                icon: Icon(
                  (isSearchBoxVisible ?? false)
                      ? Icons.search_off
                      : Icons.search,
                  size: 16,
                ),
                tooltip: l10n.translationToolbarSearchTooltip,
                onPressed: onToggleSearch,
                padding: EdgeInsets.zero,
                constraints: const BoxConstraints(
                  minWidth: 28,
                  minHeight: 28,
                ),
              ),
            // Navigate to failed segments buttons
            if (failedSegmentsCount > 0) ...<Widget>[
              IconButton(
                icon: const Icon(
                  Icons.arrow_upward,
                  size: 16,
                ),
                tooltip: l10n.translationToolbarPrevRetryTooltip,
                onPressed: onNavigateToFailedSegment != null
                    ? () => onNavigateToFailedSegment!(-1)
                    : null,
                color: Theme.of(context).colorScheme.error,
                padding: EdgeInsets.zero,
                constraints: const BoxConstraints(
                  minWidth: 28,
                  minHeight: 28,
                ),
              ),
              IconButton(
                icon: const Icon(
                  Icons.arrow_downward,
                  size: 16,
                ),
                tooltip: l10n.translationToolbarNextRetryTooltip,
                onPressed: onNavigateToFailedSegment != null
                    ? () => onNavigateToFailedSegment!(1)
                    : null,
                color: Theme.of(context).colorScheme.error,
                padding: EdgeInsets.zero,
                constraints: const BoxConstraints(
                  minWidth: 28,
                  minHeight: 28,
                ),
              ),
              const SizedBox(width: 3),
            ],
            // PDF revision mode (PDF workflow only, after translation completes)
            if (isCompletedByArtifacts &&
                onEnterPdfRevisionMode != null) ...<Widget>[
              IconButton(
                icon: loadingHtmlPreview
                    ? const SizedBox(
                        width: 16,
                        height: 16,
                        child: CircularProgressIndicator(strokeWidth: 2),
                      )
                    : const Icon(Icons.edit_note, size: 16),
                tooltip: l10n.translationPreviewPdfRevision,
                onPressed: loadingHtmlPreview ? null : onEnterPdfRevisionMode,
                padding: EdgeInsets.zero,
                constraints: const BoxConstraints(
                  minWidth: 28,
                  minHeight: 28,
                ),
              ),
              const SizedBox(width: 3),
            ],
            // AI修复公式按钮（左侧分组最右边）
            if (onRepairDocxMath != null &&
                isCompleted &&
                (statusLower == 'completed' ||
                    statusLower == 'failed' ||
                    hasDownloads)) ...<Widget>[
              IconButton(
                icon: const Icon(Icons.auto_fix_high, size: 16),
                tooltip: 'AI 修复 DOCX 公式（Pandoc/texmath）',
                onPressed: onRepairDocxMath,
                padding: EdgeInsets.zero,
                constraints: const BoxConstraints(
                  minWidth: 28,
                  minHeight: 28,
                ),
              ),
              const SizedBox(width: 3),
            ],
            // PDF 公式完整性检查（左侧末尾）
            if (onCheckPdfFormulas != null)
              IconButton(
                icon: const Icon(Icons.rule, size: 16),
                tooltip: '检查 PDF 中的公式完整性',
                onPressed: onCheckPdfFormulas,
                padding: EdgeInsets.zero,
                constraints: const BoxConstraints(
                  minWidth: 28,
                  minHeight: 28,
                ),
              ),
            if (onCheckPdfFormulas != null) const SizedBox(width: 3),
            // Spacer to push right group to the end
            const Spacer(),
          ],
          // Right group: document download/reading operations (shown after translation)
          if (!showProgressBar) ...<Widget>[
            // Pagination bar and page size selector (when completed) - leftmost in right group
            if (isCompleted &&
                segmentsPaginationController != null) ...<Widget>[
              // Pagination bar (only show when there are multiple pages)
              if (segmentsPaginationController!.totalPages > 1) ...<Widget>[
                ListenableBuilder(
                  listenable: segmentsPaginationController!,
                  builder: (context, _) => PaginationBar(
                    currentPage: segmentsPaginationController!.currentPage,
                    totalPages: segmentsPaginationController!.totalPages,
                    hasPrev: segmentsPaginationController!.hasPrev,
                    hasNext: segmentsPaginationController!.hasMore,
                    onPrevPage: segmentsPaginationController!.isLoading
                        ? null
                        : (segmentsPaginationController!.hasPrev
                            ? () async {
                                await segmentsPaginationController!
                                    .loadPrevPage();
                              }
                            : null),
                    onNextPage: segmentsPaginationController!.isLoading
                        ? null
                        : (segmentsPaginationController!.hasMore
                            ? () async {
                                await segmentsPaginationController!
                                    .loadNextPage();
                              }
                            : null),
                    onJumpToPage: segmentsPaginationController!.isLoading
                        ? null
                        : (int page) async {
                            await segmentsPaginationController!
                                .jumpToPage(page);
                          },
                    showPageJump: false,
                    height: 28,
                  ),
                ),
              ],
            ],
            // Unified preview button (HTML / side-by-side / PDF via dialog)
            if (isCompleted &&
                onViewPreview != null &&
                (statusLower == 'completed' ||
                    statusLower == 'failed' ||
                    hasDownloads)) ...<Widget>[
              IconButton(
                icon: loadingHtmlPreview
                    ? const SizedBox(
                        width: 16,
                        height: 16,
                        child: CircularProgressIndicator(strokeWidth: 2),
                      )
                    : const Icon(Icons.preview, size: 16),
                tooltip: l10n.translationToolbarPreviewTooltip,
                onPressed: loadingHtmlPreview ? null : onViewPreview,
                padding: EdgeInsets.zero,
                constraints: const BoxConstraints(
                  minWidth: 28,
                  minHeight: 28,
                ),
              ),
              const SizedBox(width: 3),
            ],
            // Download button
            if (isCompleted &&
                (statusLower == 'completed' ||
                    statusLower == 'failed' ||
                    hasDownloads)) ...<Widget>[
              IconButton(
                icon: const Icon(Icons.download, size: 16),
                tooltip: l10n.translationToolbarExportTooltip,
                onPressed: onShowDownload,
                padding: EdgeInsets.zero,
                constraints: const BoxConstraints(
                  minWidth: 28,
                  minHeight: 28,
                ),
              ),
              const SizedBox(width: 3),
            ],
            // Merged paragraph view toggle button (before fullscreen in right group)
            IconButton(
              icon: Icon(
                isMergedView ? Icons.label_outlined : Icons.chrome_reader_mode,
                size: 16,
              ),
              tooltip: isMergedView
                  ? l10n.translationToolbarSegmentView
                  : l10n.translationToolbarMergedView,
              onPressed: mergedViewEnabled ? onToggleMergedView : null,
              padding: EdgeInsets.zero,
              constraints: const BoxConstraints(
                minWidth: 28,
                minHeight: 28,
              ),
            ),
            // Fullscreen button
            IconButton(
              icon: Icon(
                isFullscreen && isFullscreenView
                    ? Icons.fullscreen_exit
                    : Icons.fullscreen,
                size: 16,
              ),
              tooltip: isFullscreen && isFullscreenView
                  ? l10n.translationToolbarExitFullscreenTooltip
                  : l10n.translationToolbarEnterFullscreenTooltip,
              onPressed: onToggleFullscreen,
              padding: EdgeInsets.zero,
              constraints: const BoxConstraints(
                minWidth: 28,
                minHeight: 28,
              ),
            ),
          ],
          // Fallback during progress: exclusion button + merged view + fullscreen
          if (showProgressBar) ...<Widget>[
            const Spacer(),
            if (onToggleExclusionPanel != null) ...<Widget>[
              ExclusionPanelButton(
                excludedCount: excludedCount,
                isExpanded: isExclusionPanelExpanded,
                onToggle: onToggleExclusionPanel!,
              ),
              const SizedBox(width: 3),
            ],
            IconButton(
              icon: Icon(
                isMergedView ? Icons.label_outlined : Icons.chrome_reader_mode,
                size: 16,
              ),
              tooltip: isMergedView
                  ? l10n.translationToolbarSegmentView
                  : l10n.translationToolbarMergedView,
              onPressed: mergedViewEnabled ? onToggleMergedView : null,
              padding: EdgeInsets.zero,
              constraints: const BoxConstraints(
                minWidth: 28,
                minHeight: 28,
              ),
            ),
            IconButton(
              icon: Icon(
                isFullscreen && isFullscreenView
                    ? Icons.fullscreen_exit
                    : Icons.fullscreen,
                size: 16,
              ),
              tooltip: isFullscreen && isFullscreenView
                  ? l10n.translationToolbarExitFullscreenTooltip
                  : l10n.translationToolbarEnterFullscreenTooltip,
              onPressed: onToggleFullscreen,
              padding: EdgeInsets.zero,
              constraints: const BoxConstraints(
                minWidth: 28,
                minHeight: 28,
              ),
            ),
          ],
        ],
      ),
    );
  }

  Widget _buildUndoRedoButtons(BuildContext context, WidgetRef ref) => Consumer(
        builder: (BuildContext context, WidgetRef ref, Widget? child) {
          final TranslationSegmentsUndoRedoState undoRedoState =
              ref.watch(translationSegmentsUndoRedoProvider(taskId));
          // Determine platform-specific shortcut hints
          final bool isMac =
              !kIsWeb && defaultTargetPlatform == TargetPlatform.macOS;
          final String undoShortcut = isMac ? 'Cmd+Z' : 'Ctrl+Z';
          final String redoShortcut =
              isMac ? 'Cmd+Shift+Z' : 'Ctrl+Y / Ctrl+Shift+Z';

          return Row(
            mainAxisSize: MainAxisSize.min,
            children: <Widget>[
              IconButton(
                icon: const Icon(Icons.undo, size: 18), // Reduced from 20 to 18
                tooltip: 'Undo\nShortcut: $undoShortcut',
                onPressed: undoRedoState.canGlobalUndo ? onGlobalUndo : null,
                color: undoRedoState.canGlobalUndo
                    ? Theme.of(context).colorScheme.primary
                    : Theme.of(context).colorScheme.onSurfaceVariant,
                padding: EdgeInsets.zero,
                constraints: const BoxConstraints(
                  minWidth: 32,
                  minHeight: 32,
                ), // Reduced button size
              ),
              IconButton(
                icon: const Icon(Icons.redo, size: 18), // Reduced from 20 to 18
                tooltip: 'Redo\nShortcut: $redoShortcut',
                onPressed: undoRedoState.canGlobalRedo ? onGlobalRedo : null,
                color: undoRedoState.canGlobalRedo
                    ? Theme.of(context).colorScheme.primary
                    : Theme.of(context).colorScheme.onSurfaceVariant,
                padding: EdgeInsets.zero,
                constraints: const BoxConstraints(
                  minWidth: 32,
                  minHeight: 32,
                ), // Reduced button size
              ),
            ],
          );
        },
      );

  /// Build font size increase/decrease controls
  Widget _buildFontSizeControls(BuildContext context, WidgetRef ref) {
    final settings = ref.watch(globalSettingsProvider);
    final currentSize = settings.previewFontSize;
    final l10n = AppLocalizations.of(context)!;

    return Row(
      mainAxisSize: MainAxisSize.min,
      children: <Widget>[
        IconButton(
          icon: const Icon(Icons.text_decrease, size: 16),
          tooltip: l10n.translationToolbarDecreaseFontSize,
          onPressed: currentSize > 8
              ? () {
                  final newSize = currentSize - 1;
                  ref
                      .read(globalSettingsProvider.notifier)
                      .updateGeneralSettings(
                    previewFontSize: newSize,
                    editFontSize: newSize + 2,
                  );
                }
              : null,
          padding: EdgeInsets.zero,
          constraints: const BoxConstraints(
            minWidth: 28,
            minHeight: 28,
          ),
        ),
        SizedBox(
          width: 20,
          child: Text(
            currentSize.toStringAsFixed(0),
            style: const TextStyle(
              fontSize: 11,
              fontWeight: FontWeight.w500,
            ),
            textAlign: TextAlign.center,
          ),
        ),
        IconButton(
          icon: const Icon(Icons.text_increase, size: 16),
          tooltip: l10n.translationToolbarIncreaseFontSize,
          onPressed: currentSize < 32
              ? () {
                  final newSize = currentSize + 1;
                  ref
                      .read(globalSettingsProvider.notifier)
                      .updateGeneralSettings(
                    previewFontSize: newSize,
                    editFontSize: newSize + 2,
                  );
                }
              : null,
          padding: EdgeInsets.zero,
          constraints: const BoxConstraints(
            minWidth: 28,
            minHeight: 28,
          ),
        ),
      ],
    );
  }

  Color _getStatusColor(String status) {
    switch (status.toLowerCase()) {
      case 'completed':
        return Colors.green;
      case 'failed':
      case 'error':
        return Colors.red;
      case 'cancelled':
        return Colors.orange;
      default:
        return Colors.blue;
    }
  }

  IconData _getStatusIcon(String status) {
    switch (status.toLowerCase()) {
      case 'completed':
        return Icons.check_circle;
      case 'failed':
      case 'error':
        return Icons.error;
      case 'cancelled':
        return Icons.cancel;
      default:
        return Icons.info;
    }
  }

  String _getStatusDisplayText(AppLocalizations l10n, String status) {
    final lower = status.toLowerCase();
    switch (lower) {
      case 'completed':
        return l10n.translationStatusCompleted;
      case 'failed':
      case 'error':
        return l10n.translationStatusFailed;
      case 'cancelled':
        return l10n.translationStatusCancelled;
      case 'processing':
      case 'pending':
        return ''; // Fixed label removed; caller falls back to '$progress%' to avoid flicker
      default:
        return status.isNotEmpty
            ? status
            : l10n.translationStatusTranslatingFallback;
    }
  }
}
