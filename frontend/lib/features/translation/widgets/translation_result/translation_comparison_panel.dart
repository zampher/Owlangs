// SPDX-FileCopyrightText: 2025 QinHan
// SPDX-License-Identifier: MPL-2.0

import 'dart:math' as math;
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../../../l10n/app_localizations.dart';
import '../../../../shared/widgets/paginated_sliver_list.dart';
import '../../../../shared/utils/pagination.dart';
import '../../../../shared/providers/settings_provider.dart';
import '../../providers/segment_undo_redo_provider.dart';
import '../../models/segment_pair.dart';
import '../../utils/segment_height_cache.dart';
import 'translation_segment_item.dart';

/// Segment statistics data structure
class SegmentStatistics {
  const SegmentStatistics({
    required this.total,
    required this.translated,
    required this.pending,
    required this.excluded,
    required this.retry,
    required this.failed,
    required this.cleared,
    required this.images,
  });

  final int total;
  final int translated;
  final int pending;
  final int excluded;
  final int retry;
  final int failed;
  final int cleared;
  final int images;

  /// Calculate completion rate percentage
  double get completionRate {
    if (total == 0) return 0;
    return (translated / total) * 100;
  }
}

/// Comparison panel for displaying source and target segments side by side
class TranslationComparisonPanel extends ConsumerWidget {
  const TranslationComparisonPanel({
    required this.taskId,
    required this.isLoading,
    required this.sourceParagraphs,
    required this.targetParagraphs,
    required this.highlightedIndexNotifier,
    required this.scrollController,
    required this.segmentPairKeys,
    required this.sourceItemKeys,
    required this.targetItemKeys,
    required this.modifiedSegments,
    required this.imageDataMap,
    required this.segmentMetadata,
    required this.retranslatingSegments,
    required this.onHighlightParagraph,
    required this.onSegmentEdit,
    required this.onEditingStarted,
    required this.onRetrySegment,
    required this.onMarkForRetry,
    required this.onUnmarkForRetry,
    required this.onExcludeSegment,
    required this.onUnexcludeSegment,
    required this.onUndo, required this.onRedo, this.onClearSegment,
    this.onUnclearSegment,
    super.key,
    this.loadingError,
    this.segmentsPaginationController,
    this.totalSegmentsCount = 0,
    this.heightCache,
    this.translationState,
    this.tokenUsage,
    this.selectedExclusionFilters,
    this.onExclusionUpdated,
    this.onFormulaFix,
    this.isConvertOnly = false,
  });

  final String taskId;
  final bool isLoading;
  final String? loadingError;
  final List<String> sourceParagraphs;
  final List<String> targetParagraphs;
  final ValueNotifier<int?> highlightedIndexNotifier;
  final ScrollController scrollController;
  final PagedListController<SegmentPair>? segmentsPaginationController;
  final int totalSegmentsCount;
  final Map<int, GlobalKey> segmentPairKeys;
  final Map<int, GlobalKey> sourceItemKeys;
  final Map<int, GlobalKey> targetItemKeys;
  final Map<int, String> modifiedSegments;
  final Map<String, Map<String, String>> imageDataMap;
  final Map<int, Map<String, dynamic>> segmentMetadata;
  final Set<int> retranslatingSegments;
  final SegmentHeightCache? heightCache;
  final void Function(int) onHighlightParagraph;
  final void Function(int, String) onSegmentEdit;
  final void Function(int) onEditingStarted;
  final void Function(int) onRetrySegment;
  final void Function(int) onMarkForRetry;
  final void Function(int) onUnmarkForRetry;
  final void Function(int) onExcludeSegment;
  final void Function(int) onUnexcludeSegment;
  final void Function(int)? onClearSegment;
  final void Function(int)? onUnclearSegment;
  final void Function(int) onUndo;
  final void Function(int) onRedo;
  final void Function(int)? onExclusionUpdated;
  final dynamic translationState;
  final Map<String, int>? tokenUsage;
  final Set<String>? selectedExclusionFilters;
  final void Function(int)? onFormulaFix;
  final bool isConvertOnly;

  /// Check if a segment is cleared based on metadata
  bool _isSegmentCleared(Map<String, dynamic> metadata) {
    final status = metadata['status'] as String?;
    final targetText = metadata['target_text'] as String?;
    return status == 'cleared' || (targetText ?? '').isEmpty;
  }

  /// Calculate segment statistics from metadata
  SegmentStatistics _calculateStatistics(
    Map<int, Map<String, dynamic>> segmentMetadata,
  ) {
    var total = 0;
    var translated = 0;
    var pending = 0;
    var excluded = 0;
    var retry = 0;
    var failed = 0;
    var cleared = 0;
    var images = 0;

    for (final MapEntry<int, Map<String, dynamic>> entry
        in segmentMetadata.entries) {
      final metadata = entry.value;
      final isImage = metadata['is_image'] as bool? ?? false;
      final isExcluded = metadata['is_excluded'] as bool? ?? false;
      final targetText = metadata['target_text'] as String?;
      final status = metadata['status'] as String?;
      final needsRetry = metadata['needs_retry'] as bool? ?? false;
      final isFailed = metadata['is_failed'] as bool? ?? false;
      final isCleared = status == 'cleared';

      total++;

      // Count images (highest priority - images are not counted in other categories)
      if (isImage) {
        images++;
      }
      // Count excluded (excluding images and failed segments)
      // CRITICAL: Only count as excluded if explicitly marked as excluded AND not failed
      // Failed segments should be counted in retry/failed, not in excluded
      // This ensures failed segments are properly shown in retry count, not hidden in excluded count
      // If a segment is both isFailed and isExcluded, prioritize failed status (count as failed, not excluded)
      else if (isExcluded && !isFailed) {
        excluded++;
      }
      // Count cleared (excluding images, excluded, and failed)
      // Cleared segments should not be counted in translated/pending/retry/failed
      else if (isCleared) {
        cleared++;
      }
      // Count failed segments (excluding images, excluded, and cleared)
      // CRITICAL: Failed segments should NOT be counted in translated/pending
      // They should only be counted in failed (which appears in Retry count)
      // This prevents double counting: a failed segment should not be both translated and failed
      else if (isFailed) {
        // Failed segments are counted in the failed counter below
        // Do not count them here in translated/pending to avoid double counting
      }
      // Count translated or pending (excluding images, excluded, cleared, and failed)
      // Only count segments that are not failed, not excluded, not cleared, and not images
      else {
        if (targetText != null && targetText.isNotEmpty) {
          translated++;
        } else {
          pending++;
        }
      }

      // Count retry and failed separately (these can overlap with translated/pending)
      // BUT: excluded (without failed) and cleared segments should NOT be counted in retry/failed
      // failed: segments that failed during translation (isFailed, even if also isExcluded)
      // retry: segments manually marked for retry but not failed (needsRetry && !isFailed, but not excluded without failed)
      // Display: "Retry: X" where X = failed + retry (no overlap)
      // CRITICAL: Count failed segments even if they are also excluded (failed takes priority over excluded)
      // Only exclude from retry/failed count if cleared or if excluded but not failed
      if (!isCleared && !isImage) {
        // Count failed segments (even if also excluded - failed takes priority)
        if (isFailed) failed++;
        // Count retry segments (but not if failed, and not if excluded without failed)
        // Simplified: if excluded without failed, don't count as retry
        if (needsRetry && !isFailed && !(isExcluded && !isFailed)) retry++;
      }
    }

    return SegmentStatistics(
      total: total,
      translated: translated,
      pending: pending,
      excluded: excluded,
      retry: retry,
      failed:
          failed, // Failed segments are displayed as "Retry" but counted separately
      cleared: cleared,
      images: images,
    );
  }

  /// Build statistics widget
  Widget _buildStatisticsWidget(BuildContext context, SegmentStatistics stats) {
    final AppLocalizations l10n = AppLocalizations.of(context)!;
    final scheme = Theme.of(context).colorScheme;

    // Use Wrap to prevent overflow when statistics are too long
    return Wrap(
      runSpacing: 2,
      children: <Widget>[
        const SizedBox(width: 4), // Reduced spacing
        Text(
          '[${l10n.translationStatsTotal(stats.total.toString())}',
          style: TextStyle(
            fontSize: 10, // Reduced from 12 to 10
            color: scheme.onSurfaceVariant,
          ),
        ),
        Text(
          l10n.translationStatsTranslated(stats.translated.toString()),
          style: TextStyle(
            fontSize: 10, // Reduced from 12 to 10
            color: Colors.green.shade700,
            fontWeight: FontWeight.w500,
          ),
        ),
        Text(
          l10n.translationStatsPending(stats.pending.toString()),
          style: TextStyle(
            fontSize: 10, // Reduced from 12 to 10
            color: Colors.orange.shade700,
            fontWeight: FontWeight.w500,
          ),
        ),
        if (stats.excluded > 0)
          Text(
            l10n.translationStatsExcluded(stats.excluded.toString()),
            style: TextStyle(
              fontSize: 10, // Reduced from 12 to 10
              color: Colors.grey.shade700,
            ),
          ),
        // Display retry count (failed + manually marked retry, no overlap)
        if (stats.failed > 0 || stats.retry > 0)
          Text(
            l10n.translationStatsRetryCount(
              (stats.failed + stats.retry).toString(),
            ),
            style: TextStyle(
              fontSize: 10, // Reduced from 12 to 10
              color: Colors.orange.shade700,
            ),
          ),
        if (stats.cleared > 0)
          Text(
            l10n.translationStatsCleared(stats.cleared.toString()),
            style: TextStyle(
              fontSize: 10, // Reduced from 12 to 10
              color: Colors.purple.shade700,
            ),
          ),
        if (stats.images > 0)
          Text(
            l10n.translationStatsImages(stats.images.toString()),
            style: TextStyle(
              fontSize: 10, // Reduced from 12 to 10
              color: scheme.onSurfaceVariant,
            ),
          ),
        Text(
          ']',
          style: TextStyle(
            fontSize: 10, // Reduced from 12 to 10
            color: scheme.onSurfaceVariant,
          ),
        ),
      ],
    );
  }

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final theme = Theme.of(context);
    final scheme = theme.colorScheme;
    final effectiveTotal = segmentsPaginationController != null &&
            segmentsPaginationController!.total > 0
        ? segmentsPaginationController!.total
        : totalSegmentsCount;

    return RepaintBoundary(
      child: ColoredBox(
        color: scheme.surface,
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: <Widget>[
            // Header with both labels and pagination bar
            Container(
              padding: const EdgeInsets.symmetric(
                horizontal: 8,
                vertical: 4,
              ), // Reduced padding: from 12 to 4 vertical, 8 horizontal
              decoration: BoxDecoration(
                color: scheme.surfaceContainerHighest,
                border: Border(
                  bottom: BorderSide(color: theme.dividerColor),
                ),
              ),
              child: Row(
                children: <Widget>[
                  // Middle section: Statistics (left-aligned)
                  Expanded(
                    child: Row(
                      mainAxisSize: MainAxisSize.min,
                      children: <Widget>[
                        // Statistics display
                        if (segmentMetadata.isNotEmpty)
                          Flexible(
                            child: _buildStatisticsWidget(
                              context,
                              _calculateStatistics(segmentMetadata),
                            ),
                          ),
                      ],
                    ),
                  ),
                  // Right section: Segment info, Translated label and stats
                  Row(
                    mainAxisAlignment: MainAxisAlignment.end,
                    mainAxisSize: MainAxisSize.min,
                    children: <Widget>[
                      ValueListenableBuilder<int?>(
                        valueListenable: highlightedIndexNotifier,
                        builder: (context, highlightedIndex, _) {
                          if (highlightedIndex != null && effectiveTotal > 0) {
                            return Padding(
                              padding: const EdgeInsets.only(
                                right: 4,
                              ), // Reduced padding
                              child: Text(
                                AppLocalizations.of(context)!
                                    .translationStatsSegment(
                                  (highlightedIndex + 1).toString(),
                                  effectiveTotal.toString(),
                                ),
                                style: TextStyle(
                                  fontSize: 10, // Reduced from 12 to 10
                                  color: scheme.onSurfaceVariant,
                                  fontWeight: FontWeight.w500,
                                ),
                                overflow: TextOverflow.ellipsis,
                              ),
                            );
                          }
                          return const SizedBox.shrink();
                        },
                      ),
                      const SizedBox(width: 6), // Reduced spacing
                      Text(
                        AppLocalizations.of(context)!
                            .translationStatsDoubleClickToEdit,
                        style: TextStyle(
                          fontSize: 10, // Reduced from 12 to 10
                          color: scheme.onSurfaceVariant,
                        ),
                      ),
                      const SizedBox(width: 4), // Reduced spacing
                      // Translation completion stats (success/fail counts, duration, token usage)
                      if (translationState != null) ...<Widget>[
                        _buildTranslationStats(context, scheme),
                        const SizedBox(
                          width: 8,
                        ), // Spacing before Translated label
                      ],
                      Text(
                        AppLocalizations.of(context)!
                            .translationStatsTranslatedLabel,
                        style: TextStyle(
                          fontSize: 12, // Reduced from 14 to 12
                          fontWeight: FontWeight.w600,
                          color: scheme.primary,
                        ),
                      ),
                    ],
                  ),
                ],
              ),
            ),
            // Content area with unified ListView
            Expanded(
              child: isLoading
                  ? Center(
                      child: Column(
                        mainAxisAlignment: MainAxisAlignment.center,
                        children: <Widget>[
                          const CircularProgressIndicator(),
                          const SizedBox(height: 16),
                          Text(
                            loadingError ??
                                AppLocalizations.of(context)!
                                    .translationStatsLoadingContent,
                            style: TextStyle(color: scheme.onSurfaceVariant),
                          ),
                        ],
                      ),
                    )
                  : sourceParagraphs.isEmpty && targetParagraphs.isEmpty
                      ? Center(
                          child: Padding(
                            padding: const EdgeInsets.all(16),
                            child: Text(
                              loadingError ??
                                  AppLocalizations.of(context)!
                                      .translationStatsNoContentAvailable,
                              textAlign: TextAlign.center,
                              style: TextStyle(color: scheme.onSurfaceVariant),
                            ),
                          ),
                        )
                      : Consumer(
                          builder: (context, ref, _) {
                            // Watch globalSettings at outer level to avoid rebuilding all items
                            // when settings change (e.g., font size)
                            final GlobalSettings globalSettings =
                                ref.watch(globalSettingsProvider);

                            // Use pagination if available and total > 0, otherwise fallback to full list
                            if (segmentsPaginationController != null &&
                                totalSegmentsCount > 0) {
                              return ListenableBuilder(
                                listenable: segmentsPaginationController!,
                                builder: (context, _) {
                                  final items =
                                      segmentsPaginationController!.items;
                                  return Column(
                                    children: <Widget>[
                                      Expanded(
                                        child: items.isEmpty
                                            ? Center(
                                                child: segmentsPaginationController!
                                                        .isLoading
                                                    ? const CircularProgressIndicator()
                                                    : Text(
                                                        AppLocalizations.of(
                                                          context,
                                                        )!
                                                            .translationStatsNoSegmentsAvailable,
                                                        style: TextStyle(
                                                          color: scheme
                                                              .onSurfaceVariant,
                                                        ),
                                                      ),
                                              )
                                            : Scrollbar(
                                                controller: scrollController,
                                                thickness: 8,
                                                radius:
                                                    const Radius.circular(4),
                                                thumbVisibility: true,
                                                child: heightCache != null &&
                                                        segmentsPaginationController !=
                                                            null
                                                    ? PaginatedSliverList<
                                                        SegmentPair>(
                                                        paginationController:
                                                            segmentsPaginationController!,
                                                        heightCache:
                                                            heightCache!,
                                                        scrollController:
                                                            scrollController,
                                                        totalItems:
                                                            effectiveTotal,
                                                        itemKeys:
                                                            segmentPairKeys,
                                                        itemBuilder: (
                                                          context,
                                                          index,
                                                          pair,
                                                          itemKey,
                                                        ) {
                                                          // itemKey is provided but _buildComparisonRowFromPair
                                                          // already uses segmentPairKeys[pair.index] internally
                                                          // Pass globalSettings to avoid ref.watch in itemBuilder
                                                          return _buildComparisonRowFromPair(
                                                            context,
                                                            ref,
                                                            pair,
                                                            scheme,
                                                            theme,
                                                            globalSettings,
                                                          );
                                                        },
                                                        padding:
                                                            const EdgeInsets
                                                                .all(8),
                                                      )
                                                    : ListView.builder(
                                                        controller:
                                                            scrollController,
                                                        padding:
                                                            const EdgeInsets
                                                                .all(8),
                                                        itemCount: items.length,
                                                        cacheExtent: 500,
                                                        itemBuilder: (
                                                          context,
                                                          index,
                                                        ) {
                                                          final pair =
                                                              items[index];
                                                          return _buildComparisonRowFromPair(
                                                            context,
                                                            ref,
                                                            pair,
                                                            scheme,
                                                            theme,
                                                            globalSettings,
                                                          );
                                                        },
                                                      ),
                                              ),
                                      ),
                                    ],
                                  );
                                },
                              );
                            } else {
                              // Fallback to full list (for backward compatibility)
                              final int itemCount = math.max(
                                sourceParagraphs.length,
                                targetParagraphs.length,
                              );
                              return Scrollbar(
                                controller: scrollController,
                                thickness: 8,
                                radius: const Radius.circular(4),
                                thumbVisibility: true,
                                child: ListView.builder(
                                  controller: scrollController,
                                  padding: const EdgeInsets.all(8),
                                  itemCount: itemCount,
                                  cacheExtent: 500,
                                  itemBuilder: (context, index) =>
                                      _buildComparisonRow(
                                    context,
                                    ref,
                                    index,
                                    scheme,
                                    theme,
                                    globalSettings,
                                  ),
                                ),
                              );
                            }
                          },
                        ),
            ),
          ],
        ),
      ),
    );
  }

  /// Build a single row from a SegmentPair (for paginated view)
  /// Performance optimization:
  /// - globalSettings passed as parameter (read at outer level)
  /// - Use ref.read for undoRedoState to avoid unnecessary rebuilds
  Widget _buildComparisonRowFromPair(
    BuildContext context,
    WidgetRef ref,
    SegmentPair pair,
    ColorScheme scheme,
    ThemeData theme,
    GlobalSettings globalSettings,
  ) =>
      ValueListenableBuilder<int?>(
        valueListenable: highlightedIndexNotifier,
        builder: (context, highlightedIdx, child) {
          final isHighlighted = highlightedIdx == pair.index;
          // Use ref.read for undoRedoState (changes less frequently than settings)
          // globalSettings is passed as parameter to avoid ref.watch in itemBuilder
          final undoRedoState =
              ref.read(translationSegmentsUndoRedoProvider(taskId));

          final canUndo = undoRedoState.canUndo(pair.index);
          final canRedo = undoRedoState.canRedo(pair.index);

          final Map<String, dynamic> metadata =
              segmentMetadata[pair.index] ?? <String, dynamic>{};
          final isExcluded = metadata['is_excluded'] as bool? ?? false;
          final exclusionReason = metadata['exclusion_reason'] as String?;

          // Apply filter: if filters are selected, only show matching segments
          if (selectedExclusionFilters != null &&
              selectedExclusionFilters!.isNotEmpty) {
            // Special case: "failed" filter - show only failed segments
            if (selectedExclusionFilters!.contains('failed')) {
              final isFailed = metadata['is_failed'] as bool? ?? false;
              if (!isFailed) {
                return const SizedBox.shrink();
              }
            }
            // Special case: "included" filter - show only included segments (will be translated)
            else if (selectedExclusionFilters!.contains('included')) {
              if (isExcluded) {
                return const SizedBox.shrink();
              }
            }
            // Special case: "all_excluded" filter - show only excluded segments
            else if (selectedExclusionFilters!.contains('all_excluded')) {
              if (!isExcluded) {
                return const SizedBox.shrink();
              }
            }
            // Normal filter: show only segments matching selected exclusion reasons
            else {
              // If segment is not excluded, or exclusion reason is not in selected filters, hide it
              if (!isExcluded ||
                  exclusionReason == null ||
                  !selectedExclusionFilters!.contains(exclusionReason)) {
                return const SizedBox.shrink();
              }
            }
          }

          // Build target segment widget (reused for both single-column and dual-column modes)
          final Widget targetSegment = RepaintBoundary(
            key: ValueKey('target_${pair.index}'),
            child: TranslationSegmentItem(
              itemKey: targetItemKeys[pair.index],
              text: pair.targetText,
              sourceText: pair.sourceText,
              index: pair.index,
              isSource: false,
              isHighlighted: isHighlighted,
              isModified: modifiedSegments.containsKey(pair.index),
              platformUsed: pair.isImage
                  ? null
                  : (metadata['platform_used'] as String?),
              isFailed: pair.isImage
                  ? false
                  : (metadata['is_failed'] as bool? ?? false),
              failureReason: pair.isImage
                  ? null
                  : (metadata['failure_reason'] as String?),
              needsRetry: pair.isImage
                  ? false
                  : (metadata['needs_retry'] as bool? ?? false),
              isExcluded: pair.isExcluded,
              exclusionReason: pair.exclusionReason,
              isCleared:
                  pair.isImage ? false : _isSegmentCleared(metadata),
              onRetry: retranslatingSegments.contains(pair.index)
                  ? null
                  : onRetrySegment,
              onMarkForRetry: onMarkForRetry,
              onUnmarkForRetry: onUnmarkForRetry,
              onExclude: onExcludeSegment,
              onUnexclude: onUnexcludeSegment,
              onClear: onClearSegment,
              onUnclear: onUnclearSegment,
              onTap: () => onHighlightParagraph(pair.index),
              onEdit: (newText) => onSegmentEdit(pair.index, newText),
              onEditingStarted: onEditingStarted,
              onUndo: onUndo,
              onRedo: onRedo,
              canUndo: canUndo,
              canRedo: canRedo,
              previewFontSize: globalSettings.previewFontSize,
              editFontSize: globalSettings.editFontSize,
              imageDataMap: imageDataMap,
              taskId: taskId,
              onExclusionUpdated: onExclusionUpdated ??
                  (int index) {
                    // Fallback: Refresh segments to get updated exclusion reason
                    segmentsPaginationController?.refresh();
                  },
              onFormulaFix: onFormulaFix,
            ),
          );

          return Container(
            key: segmentPairKeys[pair.index],
            margin: const EdgeInsets.only(
              bottom: 1,
            ), // Further reduced from 2 to 1 for more compact display
            child: isConvertOnly
                ? targetSegment
                : Row(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: <Widget>[
                      // Source segment (left)
                      Expanded(
                        child: RepaintBoundary(
                          key: ValueKey('source_${pair.index}'),
                          child: TranslationSegmentItem(
                            itemKey: sourceItemKeys[pair.index],
                            text: pair.sourceText,
                            index: pair.index,
                            isSource: true,
                            isHighlighted: isHighlighted,
                            onTap: () => onHighlightParagraph(pair.index),
                            previewFontSize: globalSettings.previewFontSize,
                            editFontSize: globalSettings.editFontSize,
                            imageDataMap: imageDataMap,
                          ),
                        ),
                      ),
                      // Divider
                      Container(
                        width: 1,
                        color: theme.dividerColor.withOpacity(0.6),
                        margin: const EdgeInsets.symmetric(horizontal: 2),
                      ),
                      // Target segment (right)
                      Expanded(child: targetSegment),
                    ],
                  ),
          );
        },
      );

  /// Build a single row containing both source and target segments side by side
  /// Performance optimization: globalSettings passed as parameter
  Widget _buildComparisonRow(
    BuildContext context,
    WidgetRef ref,
    int index,
    ColorScheme scheme,
    ThemeData theme,
    GlobalSettings globalSettings,
  ) {
    // Ensure index is valid
    final hasSource = index < sourceParagraphs.length;
    final hasTarget = index < targetParagraphs.length;

    if (!hasSource && !hasTarget) {
      return const SizedBox.shrink();
    }

    return ValueListenableBuilder<int?>(
      valueListenable: highlightedIndexNotifier,
      builder: (context, highlightedIdx, child) {
        final isHighlighted = highlightedIdx == index;
        // Use ref.read for undoRedoState (changes less frequently)
        // globalSettings is passed as parameter to avoid ref.watch in itemBuilder
        final undoRedoState =
            ref.read(translationSegmentsUndoRedoProvider(taskId));

        // Get target segment metadata
        final metadata = segmentMetadata[index] ?? <String, dynamic>{};
        final platformUsed = metadata['platform_used'] as String?;
        final isImage = metadata['is_image'] as bool? ?? false;
        final isFailed = metadata['is_failed'] as bool? ?? false;
        final failureReason = metadata['failure_reason'] as String?;
        final needsRetry = metadata['needs_retry'] as bool? ?? false;
        final isRetranslating = retranslatingSegments.contains(index);
        final canUndo = undoRedoState.canUndo(index);
        final canRedo = undoRedoState.canRedo(index);
        final isExcluded = metadata['is_excluded'] as bool? ?? false;
        final exclusionReason = metadata['exclusion_reason'] as String?;
        final isCleared = isImage ? false : _isSegmentCleared(metadata);

        // Build target segment widget (reused for both modes)
        final Widget targetSegmentWidget = hasTarget
            ? RepaintBoundary(
                key: ValueKey('target_$index'),
                child: TranslationSegmentItem(
                  itemKey: targetItemKeys[index],
                  text: targetParagraphs[index],
                  sourceText:
                      hasSource ? sourceParagraphs[index] : null,
                  index: index,
                  isSource: false,
                  isHighlighted: isHighlighted,
                  isModified: modifiedSegments.containsKey(index),
                  platformUsed: isImage ? null : platformUsed,
                  isFailed: isImage ? false : isFailed,
                  failureReason: isImage ? null : failureReason,
                  needsRetry: isImage ? false : needsRetry,
                  isExcluded: isExcluded,
                  exclusionReason: exclusionReason,
                  isCleared: isCleared,
                  onRetry: isRetranslating ? null : onRetrySegment,
                  onMarkForRetry: onMarkForRetry,
                  onExclude: onExcludeSegment,
                  onUnexclude: onUnexcludeSegment,
                  onClear: onClearSegment,
                  onUnclear: onUnclearSegment,
                  onTap: () => onHighlightParagraph(index),
                  onEdit: (newText) => onSegmentEdit(index, newText),
                  onEditingStarted: onEditingStarted,
                  onUndo: onUndo,
                  onRedo: onRedo,
                  canUndo: canUndo,
                  canRedo: canRedo,
                  previewFontSize: globalSettings.previewFontSize,
                  editFontSize: globalSettings.editFontSize,
                  imageDataMap: imageDataMap,
                  taskId: taskId,
                  onExclusionUpdated: onExclusionUpdated ??
                      (int index) {
                        // Fallback: Refresh segments to get updated exclusion reason
                        segmentsPaginationController?.refresh();
                      },
                ),
              )
            : Container(
                // Placeholder if target is missing
                height: 50,
                color: scheme.surfaceContainerHighest,
              );

        return Container(
          key: segmentPairKeys[index],
          margin: const EdgeInsets.only(
            bottom: 1,
          ), // Further reduced from 2 to 1 for more compact display
          child: isConvertOnly
              ? targetSegmentWidget
              : Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: <Widget>[
                    // Source segment (left)
                    Expanded(
                      child: hasSource
                          ? RepaintBoundary(
                              key: ValueKey('source_$index'),
                              child: TranslationSegmentItem(
                                itemKey: sourceItemKeys[index],
                                text: sourceParagraphs[index],
                                index: index,
                                isSource: true,
                                isHighlighted: isHighlighted,
                                onTap: () => onHighlightParagraph(index),
                                previewFontSize: globalSettings.previewFontSize,
                                editFontSize: globalSettings.editFontSize,
                                imageDataMap: imageDataMap,
                              ),
                            )
                          : Container(
                              // Placeholder if source is missing
                              height: 50,
                              color: scheme.surfaceContainerHighest,
                            ),
                    ),
                    // Divider
                    Container(
                      width: 1,
                      color: theme.dividerColor.withOpacity(0.6),
                      margin: const EdgeInsets.symmetric(horizontal: 2),
                    ),
                    // Target segment (right)
                    Expanded(child: targetSegmentWidget),
                  ],
                ),
        );
      },
    );
  }

  /// Build translation completion statistics widget
  Widget _buildTranslationStats(BuildContext context, ColorScheme scheme) {
    final statusText = translationState?.statusText?.toString() ?? '';
    final isCompleted = statusText.toLowerCase() == 'completed' ||
        statusText.toLowerCase() == 'failed';

    if (!isCompleted) {
      return const SizedBox.shrink();
    }

    final successCount = translationState?.successCount;
    final failCount = translationState?.failCount;
    final totalSegments = translationState?.totalSegments;

    return Row(
      mainAxisSize: MainAxisSize.min,
      children: <Widget>[
        // Success/Fail counts
        if (totalSegments != null && totalSegments > 0) ...<Widget>[
          const Icon(
            Icons.check_circle,
            size: 11,
            color: Colors.green,
          ),
          const SizedBox(width: 2),
          Text(
            '${successCount ?? 0}',
            style: const TextStyle(
              fontSize: 10,
              fontWeight: FontWeight.w600,
              color: Colors.green,
            ),
          ),
          const SizedBox(width: 4),
          const Icon(Icons.error, size: 10, color: Colors.red),
          const SizedBox(width: 2),
          Text(
            '${failCount ?? 0}',
            style: const TextStyle(
              fontSize: 10,
              fontWeight: FontWeight.w600,
              color: Colors.red,
            ),
          ),
          const SizedBox(width: 2),
          Text(
            '/ $totalSegments',
            style: TextStyle(
              fontSize: 10,
              color: scheme.onSurfaceVariant,
            ),
          ),
          const SizedBox(width: 6),
        ],
        // Translation duration
        if (translationState?.totalDuration != null) ...<Widget>[
          Icon(
            Icons.timer,
            size: 11,
            color: Colors.orange.shade700,
          ),
          const SizedBox(width: 2),
          Text(
            _formatDuration(translationState!.totalDuration!),
            style: TextStyle(
              fontSize: 10,
              fontWeight: FontWeight.w600,
              color: Colors.orange.shade700,
            ),
          ),
          const SizedBox(width: 6),
        ],
        // Token usage statistics
        if (tokenUsage != null &&
            tokenUsage!['total_tokens'] != null &&
            tokenUsage!['total_tokens']! > 0) ...<Widget>[
          Icon(
            Icons.memory,
            size: 10,
            color: Colors.blue.shade700,
          ),
          const SizedBox(width: 2),
          Text(
            AppLocalizations.of(context)!.translationStatsTokenIn(
              _formatTokenCount(tokenUsage!['input_tokens'] ?? 0),
            ),
            style: TextStyle(
              fontSize: 10,
              fontWeight: FontWeight.w600,
              color: Colors.blue.shade700,
            ),
          ),
          const SizedBox(width: 3),
          Text(
            AppLocalizations.of(context)!.translationStatsTokenOut(
              _formatTokenCount(tokenUsage!['output_tokens'] ?? 0),
            ),
            style: TextStyle(
              fontSize: 10,
              fontWeight: FontWeight.w600,
              color: Colors.green.shade700,
            ),
          ),
          const SizedBox(width: 2),
          Text(
            AppLocalizations.of(context)!.translationStatsTokenTotal(
              _formatTokenCount(tokenUsage!['total_tokens']!),
            ),
            style: TextStyle(
              fontSize: 10,
              color: scheme.onSurfaceVariant,
            ),
          ),
        ],
      ],
    );
  }

  /// Format token count for display
  String _formatTokenCount(int count) {
    if (count < 1000) {
      return '$count';
    } else if (count < 1000000) {
      return '${(count / 1000).toStringAsFixed(1)}K';
    } else {
      return '${(count / 1000000).toStringAsFixed(1)}M';
    }
  }

  /// Format duration for display
  String _formatDuration(Duration duration) {
    final hours = duration.inHours;
    final minutes = duration.inMinutes.remainder(60);
    final seconds = duration.inSeconds.remainder(60);

    if (hours > 0) {
      return '${hours.toString().padLeft(2, '0')}:${minutes.toString().padLeft(2, '0')}:${seconds.toString().padLeft(2, '0')}';
    } else {
      return '${minutes.toString().padLeft(2, '0')}:${seconds.toString().padLeft(2, '0')}';
    }
  }
}
