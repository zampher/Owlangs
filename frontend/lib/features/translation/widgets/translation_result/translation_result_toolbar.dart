// SPDX-FileCopyrightText: 2025 QinHan
// SPDX-License-Identifier: MPL-2.0

import 'package:flutter/material.dart';
import 'package:flutter/foundation.dart'
    show kIsWeb, kDebugMode, defaultTargetPlatform, TargetPlatform;
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../../../l10n/app_localizations.dart';
import '../../../../shared/widgets/pagination_bar.dart';
import '../../../../shared/widgets/page_size_selector.dart';
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
    this.onShowSettings,
    this.onShowDownload,
    this.onViewPdfPreview,
    this.onToggleFullscreen,
    this.excludedCount = 0,
    this.isExclusionPanelExpanded = false,
    this.onToggleExclusionPanel,
    // Filter buttons state (for toolbar filter buttons)
    this.selectedFilters,
    this.onFiltersChanged,
    this.totalSegments,
    this.failedCount,
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
  final VoidCallback? onShowSettings;
  final VoidCallback? onShowDownload;
  final VoidCallback? onViewPdfPreview;
  final VoidCallback? onToggleFullscreen;
  final int excludedCount;
  final bool isExclusionPanelExpanded;
  final VoidCallback? onToggleExclusionPanel;
  // Filter buttons state (for toolbar filter buttons)
  final Set<String>? selectedFilters;
  final void Function(Set<String>)? onFiltersChanged;
  final int? totalSegments;
  final int? failedCount;
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
            statusLower == 'processing');
    // Hide progress bar when translation is completed (including processing+100%)
    final isCompleted = isCompletedByArtifacts ||
        statusLower == 'failed' ||
        statusLower == 'cancelled';
    final showProgressBar = isActive && !isCompleted;

    return Container(
      padding: const EdgeInsets.symmetric(
        horizontal: 12,
        vertical: 4,
      ), // Adjusted padding to achieve 36px total height
      constraints: const BoxConstraints(
        minHeight: 36,
        maxHeight: 36,
      ), // Fixed height at 36px
      decoration: BoxDecoration(
        color: Theme.of(context).colorScheme.surfaceContainerHighest,
        border: Border(
          bottom: BorderSide(color: Theme.of(context).dividerColor),
        ),
      ),
      child: Row(
        children: <Widget>[
          // Filter buttons (shown only after translation completion, hidden during translation)
          if (!showProgressBar &&
              selectedFilters != null &&
              onFiltersChanged != null &&
              totalSegments != null) ...<Widget>[
            // Filter panel toggle button (moved from right to left)
            if (onToggleExclusionPanel != null)
              ExclusionPanelButton(
                excludedCount: excludedCount,
                isExpanded: isExclusionPanelExpanded,
                onToggle: onToggleExclusionPanel!,
              ),
            const SizedBox(width: 6),
            // All button (compact - only show count)
            _buildCompactFilterButton(
              context: context,
              label: l10n.translationToolbarFilterAll,
              count: totalSegments!,
              isSelected: selectedFilters!.isEmpty,
              onTap: () => onFiltersChanged!(<String>{}),
              color: Colors.blue,
            ),
            const SizedBox(width: 3),
            // Failed button (only show if there are failed segments, compact - only show count)
            if (failedCount != null && failedCount! > 0)
              _buildCompactFilterButton(
                context: context,
                label: l10n.translationToolbarFilterFailed,
                count: failedCount!,
                isSelected: selectedFilters!.contains('failed'),
                onTap: () => onFiltersChanged!(<String>{'failed'}),
                color: Colors.red,
              ),
            if (failedCount != null && failedCount! > 0)
              const SizedBox(width: 3),
            // Included button (compact - only show count)
            _buildCompactFilterButton(
              context: context,
              label: l10n.translationToolbarFilterIncluded,
              count: totalSegments! - excludedCount,
              isSelected: selectedFilters!.contains('included'),
              onTap: () => onFiltersChanged!(<String>{'included'}),
              color: Colors.green,
            ),
            const SizedBox(width: 3),
            // All Excluded button (compact - only show count)
            _buildCompactFilterButton(
              context: context,
              label: l10n.translationToolbarFilterExcluded,
              count: excludedCount,
              isSelected: selectedFilters!.contains('all_excluded'),
              onTap: () => onFiltersChanged!(<String>{'all_excluded'}),
              color: Colors.red,
            ),
            const SizedBox(width: 8), // Spacing after filter buttons
          ],
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
          // Other buttons (shown when not actively translating or after completion)
          // All buttons should be right-aligned when completed
          if (!showProgressBar) ...<Widget>[
            // Spacer at the beginning to push all buttons to the right
            const Spacer(),
            // Search button (shown when segments are available)
            if (totalSegments != null &&
                totalSegments! > 0 &&
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
                ), // Further reduced from 18 to 16
                tooltip: l10n.translationToolbarPrevRetryTooltip,
                onPressed: onNavigateToFailedSegment != null
                    ? () => onNavigateToFailedSegment!(-1)
                    : null,
                color: Theme.of(context).colorScheme.error,
                padding: EdgeInsets.zero,
                constraints: const BoxConstraints(
                  minWidth: 28,
                  minHeight: 28,
                ), // Further reduced button size
              ),
              IconButton(
                icon: const Icon(
                  Icons.arrow_downward,
                  size: 16,
                ), // Further reduced from 18 to 16
                tooltip: l10n.translationToolbarNextRetryTooltip,
                onPressed: onNavigateToFailedSegment != null
                    ? () => onNavigateToFailedSegment!(1)
                    : null,
                color: Theme.of(context).colorScheme.error,
                padding: EdgeInsets.zero,
                constraints: const BoxConstraints(
                  minWidth: 28,
                  minHeight: 28,
                ), // Further reduced button size
              ),
              const SizedBox(width: 3), // Further reduced spacing
            ],
            // Preview button
            if (_shouldShowPreviewButton()) ...<Widget>[
              IconButton(
                icon: loadingHtmlPreview
                    ? const SizedBox(
                        width: 16, // Further reduced from 18
                        height: 16, // Further reduced from 18
                        child: CircularProgressIndicator(strokeWidth: 2),
                      )
                    : const Icon(
                        Icons.preview,
                        size: 16,
                      ), // Further reduced from 18 to 16
                tooltip: l10n.translationToolbarPreviewTooltip,
                onPressed: loadingHtmlPreview ? null : onViewPreview,
                padding: EdgeInsets.zero,
                constraints: const BoxConstraints(
                  minWidth: 28,
                  minHeight: 28,
                ), // Further reduced button size
              ),
              const SizedBox(width: 3), // Further reduced spacing
            ],
            // Settings and Download buttons
            if (isCompleted &&
                (statusLower == 'completed' ||
                    statusLower == 'failed' ||
                    hasDownloads)) ...<Widget>[
              IconButton(
                icon: const Icon(
                  Icons.settings,
                  size: 16,
                ), // Further reduced from 18 to 16
                tooltip: l10n.translationToolbarFormatSettingsTooltip,
                onPressed: onShowSettings,
                padding: EdgeInsets.zero,
                constraints: const BoxConstraints(
                  minWidth: 28,
                  minHeight: 28,
                ), // Further reduced button size
              ),
              const SizedBox(width: 3), // Further reduced spacing
              IconButton(
                icon: const Icon(
                  Icons.download,
                  size: 16,
                ), // Further reduced from 18 to 16
                tooltip: l10n.translationToolbarExportTooltip,
                onPressed: onShowDownload,
                padding: EdgeInsets.zero,
                constraints: const BoxConstraints(
                  minWidth: 28,
                  minHeight: 28,
                ), // Further reduced button size
              ),
              const SizedBox(width: 3), // Further reduced spacing
              if (onRepairDocxMath != null) ...<Widget>[
                IconButton(
                  icon: const Icon(
                    Icons.auto_fix_high,
                    size: 16,
                  ),
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
            ],
            // PDF Preview button (Debug mode only)
            if (kDebugMode &&
                (fileName?.toLowerCase().endsWith('.pdf') ?? false) &&
                (downloads?.containsKey('pdf') ?? false)) ...<Widget>[
              IconButton(
                icon: const Icon(
                  Icons.picture_as_pdf,
                  size: 16,
                ), // Further reduced from 18 to 16
                tooltip: l10n.translationToolbarPdfPreviewTooltip,
                onPressed: onViewPdfPreview,
                padding: EdgeInsets.zero,
                constraints: const BoxConstraints(
                  minWidth: 28,
                  minHeight: 28,
                ), // Further reduced button size
              ),
              const SizedBox(width: 3), // Further reduced spacing
              // PDF 公式完整性检测按钮（仅 PDF 流程可见）
              if (onCheckPdfFormulas != null)
                IconButton(
                  icon: const Icon(
                    Icons.rule,
                    size: 16,
                  ),
                  tooltip: '检查 PDF 中的公式完整性',
                  onPressed: onCheckPdfFormulas,
                  padding: EdgeInsets.zero,
                  constraints: const BoxConstraints(
                    minWidth: 28,
                    minHeight: 28,
                  ),
                ),
              if (onCheckPdfFormulas != null)
                const SizedBox(width: 3), // Spacing after formula check button
            ],
            // Font size controls - Always shown when content is displayed
            const SizedBox(width: 6),
            _buildFontSizeControls(context, ref),
          ],
          // Global Undo/Redo buttons - Always shown, aligned to right
          _buildUndoRedoButtons(context, ref),
          // Pagination bar and page size selector (inserted between Undo/Redo and Filter when completed and visible)
          // CRITICAL: Show pagination controls when translation is completed, even if only one page
          // Page size selector should always be visible (allows changing page size), pagination bar only when multiple pages
          if (!showProgressBar &&
              isCompleted &&
              segmentsPaginationController != null) ...<Widget>[
            // Pagination bar (only show when there are multiple pages)
            if (segmentsPaginationController!.totalPages > 1) ...<Widget>[
              const SizedBox(width: 8), // Spacing before pagination
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
                          await segmentsPaginationController!.jumpToPage(page);
                        },
                  showPageJump: false,
                  height: 28, // Compact height to match toolbar
                ),
              ),
            ],
            // Page size selector (always show when translation is completed, allows changing page size)
            const SizedBox(width: 8), // Spacing before page size selector
            ListenableBuilder(
              listenable: segmentsPaginationController!,
              builder: (context, _) => PageSizeSelector(
                currentPageSize: segmentsPaginationController!.pageSize,
                onPageSizeChanged: (size) {
                  segmentsPaginationController!.setPageSize(size);
                },
                preferenceKey: 'translation_result_segments_page_size',
                pageSizeOptions: const <int>[
                  50,
                  100,
                  200,
                  500,
                  1000,
                  2000,
                ],
                showLabel: false, // Hide label to save space in toolbar
              ),
            ),
          ],
          // Exclusion panel button - Only show if filter buttons are not shown (fallback for edge cases)
          if (showProgressBar && onToggleExclusionPanel != null) ...<Widget>[
            const SizedBox(width: 3),
            ExclusionPanelButton(
              excludedCount: excludedCount,
              isExpanded: isExclusionPanelExpanded,
              onToggle: onToggleExclusionPanel!,
            ),
          ],
          // Merged paragraph view toggle button
          IconButton(
            icon: Icon(
              isMergedView ? Icons.edit_outlined : Icons.visibility_outlined,
              size: 16,
            ),
            tooltip: isMergedView
                ? l10n.translationToolbarSegmentView
                : l10n.translationToolbarMergedView,
            onPressed: onToggleMergedView,
            padding: EdgeInsets.zero,
            constraints: const BoxConstraints(
              minWidth: 28,
              minHeight: 28,
            ),
          ),
          // Fullscreen button - Always shown, rightmost
          IconButton(
            icon: Icon(
              isFullscreen && isFullscreenView
                  ? Icons.fullscreen_exit
                  : Icons.fullscreen,
              size: 16, // Further reduced from 18 to 16
            ),
            tooltip: isFullscreen && isFullscreenView
                ? l10n.translationToolbarExitFullscreenTooltip
                : l10n.translationToolbarEnterFullscreenTooltip,
            onPressed: onToggleFullscreen,
            padding: EdgeInsets.zero,
            constraints: const BoxConstraints(
              minWidth: 28,
              minHeight: 28,
            ), // Further reduced button size
          ),
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

  /// Build a compact filter button for the toolbar (simplified text, minimal margins)
  Widget _buildCompactFilterButton({
    required BuildContext context,
    required String label,
    required int count,
    required bool isSelected,
    required VoidCallback onTap,
    required MaterialColor color,
  }) =>
      Tooltip(
        message: '$label ($count)',
        child: ActionChip(
          label: Row(
            mainAxisSize: MainAxisSize.min,
            children: <Widget>[
              if (isSelected)
                Icon(
                  Icons.check,
                  size: 12, // Smaller checkmark icon
                  color: color.shade700,
                ),
              if (isSelected) const SizedBox(width: 2),
              Text(
                '$label ($count)', // Show label with count
                style: TextStyle(
                  fontSize: 10,
                  color: isSelected ? color.shade700 : Colors.grey.shade700,
                ),
              ),
            ],
          ),
          onPressed: onTap,
          backgroundColor: isSelected ? color.shade100 : Colors.grey.shade200,
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(999),
          ),
          padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
          visualDensity: VisualDensity.compact,
          side: BorderSide(
            color: isSelected ? color.shade300 : Colors.grey.shade400,
          ),
        ),
      );

  bool _shouldShowPreviewButton() {
    if (downloads == null || downloads!.isEmpty) {
      return false;
    }

    final isPdfFile = fileName?.toLowerCase().endsWith('.pdf') ?? false;
    final hasPdfDownload = downloads!.containsKey('pdf');

    // For PDF files, show viewer if PDF download is available
    if (isPdfFile && hasPdfDownload) {
      return true;
    }

    // For other files, show viewer if HTML or MD download is available
    final hasHtmlDownload = downloads!.containsKey('html');
    final hasMdDownload = downloads!.containsKey('md');
    if (hasHtmlDownload || hasMdDownload) {
      // Don't show viewer for DOCX, PPTX, XLSX, MD, or PNG files
      final fileNameLower = fileName?.toLowerCase() ?? '';
      final isDocxFile =
          fileNameLower.endsWith('.docx') || fileNameLower.endsWith('.doc');
      final isPptxFile =
          fileNameLower.endsWith('.pptx') || fileNameLower.endsWith('.ppt');
      final isXlsxFile = fileNameLower.endsWith('.xlsx') ||
          fileNameLower.endsWith('.xls') ||
          fileNameLower.endsWith('.csv');
      final isMdFile = fileNameLower.endsWith('.md');
      final isPngFile = fileNameLower.endsWith('.png') ||
          fileNameLower.endsWith('.jpg') ||
          fileNameLower.endsWith('.jpeg');

      return !isDocxFile &&
          !isPptxFile &&
          !isXlsxFile &&
          !isMdFile &&
          !isPngFile;
    }

    return false;
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
