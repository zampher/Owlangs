// SPDX-FileCopyrightText: 2025 QinHan
// SPDX-License-Identifier: MPL-2.0

import 'dart:math' as math;
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../../../l10n/app_localizations.dart';
import '../../../../shared/widgets/paginated_sliver_list.dart';
import '../../../../shared/widgets/page_size_selector.dart';
import '../../../../shared/utils/pagination.dart';
import '../../../../shared/providers/settings_provider.dart';
import '../../providers/segment_undo_redo_provider.dart';
import '../../models/segment_pair.dart';
import '../../utils/segment_height_cache.dart';
import '../../utils/segment_type_utils.dart';
import 'translation_segment_item.dart';

/// State-based filter keys (mutually exclusive - single select)
const Set<String> _stateFilterKeys = <String>{
  'translated',
  'pending',
  'failed',
  'excluded',
  'retry',
  'cleared',
  'images',
};

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
    this.onFiltersChanged,
    this.onExclusionUpdated,
    this.onFormulaFix,
    this.isConvertOnly = false,
    this.showPdfFontSize = false,
    this.onFontSizeChanged,
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
  final void Function(Set<String>)? onFiltersChanged;
  final void Function(int)? onFormulaFix;
  final bool isConvertOnly;
  final bool showPdfFontSize;
  final void Function(
    int index, {
    double? fontSizePt,
    String? fontWeight,
    String? fontStyle,
    double? leadingEm,
    bool reset,
  })? onFontSizeChanged;

  /// Check if a segment is cleared based on metadata
  bool _isSegmentCleared(Map<String, dynamic> metadata) {
    final status = metadata['status'] as String?;
    final targetText = metadata['target_text'] as String?;
    return status == 'cleared' || (targetText ?? '').isEmpty;
  }

  double? _readFontSizePt(Map<String, dynamic> metadata) {
    final dynamic raw = metadata['font_size_pt'];
    if (raw is num) {
      return raw.toDouble();
    }
    if (raw is String) {
      return double.tryParse(raw);
    }
    return null;
  }

  double? _readComputedFontSizePt(Map<String, dynamic> metadata) {
    final dynamic raw = metadata['computed_font_size_pt'];
    if (raw is num) {
      return raw.toDouble();
    }
    if (raw is String) {
      return double.tryParse(raw);
    }
    return null;
  }

  String? _readFontWeight(Map<String, dynamic> metadata) {
    final dynamic raw = metadata['font_weight'];
    return raw is String ? raw : null;
  }

  String? _readComputedFontWeight(Map<String, dynamic> metadata) {
    final dynamic raw = metadata['computed_font_weight'];
    return raw is String ? raw : null;
  }

  String? _readFontStyle(Map<String, dynamic> metadata) {
    final dynamic raw = metadata['font_style'];
    return raw is String ? raw : null;
  }

  String? _readComputedFontStyle(Map<String, dynamic> metadata) {
    final dynamic raw = metadata['computed_font_style'];
    return raw is String ? raw : null;
  }

  double? _readLeadingEm(Map<String, dynamic> metadata) {
    return _readOptionalDouble(metadata['leading_em']);
  }

  double? _readComputedLeadingEm(Map<String, dynamic> metadata) {
    return _readOptionalDouble(metadata['computed_leading_em']);
  }

  double? _readOptionalDouble(dynamic raw) {
    if (raw is num) {
      return raw.toDouble();
    }
    if (raw is String) {
      return double.tryParse(raw);
    }
    return null;
  }

  /// Calculate counts for state-based filter chips
  Map<String, int> _calculateFilterCounts(
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

      if (isImage) {
        images++;
      } else if (isExcluded && !isFailed) {
        excluded++;
      } else if (isCleared) {
        cleared++;
      } else if (isFailed) {
        // counted in failed below
      } else {
        if (targetText != null && targetText.isNotEmpty) {
          translated++;
        } else {
          pending++;
        }
      }

      if (!isCleared && !isImage) {
        if (isFailed) failed++;
        if (needsRetry && !isFailed && !(isExcluded && !isFailed)) retry++;
      }
    }

    return <String, int>{
      '': total,
      'translated': translated,
      'pending': pending,
      'failed': failed,
      'excluded': excluded,
      'retry': retry + failed, // "Retry" shows failed + manual retry
      'cleared': cleared,
      'images': images,
    };
  }

  /// Build filter chips bar (replaces the old statistics widget)
  Widget _buildFilterChipsBar(BuildContext context) {
    final l10n = AppLocalizations.of(context)!;
    final counts = _calculateFilterCounts(segmentMetadata);
    final selected = selectedExclusionFilters ?? <String>{};

    // Define filter chip configs: key, label, color
    final filters = <_FilterChipConfig>[
      _FilterChipConfig('', l10n.translationToolbarFilterAll, Colors.blue),
      _FilterChipConfig('translated', l10n.translationStatsTranslatedLabel, Colors.green),
      _FilterChipConfig('pending', l10n.translationStatsPendingLabel, Colors.orange),
      _FilterChipConfig('failed', l10n.translationToolbarFilterFailed, Colors.red),
      _FilterChipConfig('excluded', l10n.translationToolbarFilterExcluded, Colors.grey),
      _FilterChipConfig('retry', l10n.translationToolbarRetry, Colors.orange),
      _FilterChipConfig('cleared', l10n.translationStatsClearedLabel, Colors.purple),
      _FilterChipConfig('images', l10n.translationStatsImagesLabel, Colors.blue),
    ];

    return Row(
      mainAxisSize: MainAxisSize.min,
      children: <Widget>[
        Padding(
          padding: const EdgeInsets.only(right: 3),
          child: Text(
            '${l10n.settingsGlossaryFilterLabel} ',
            style: TextStyle(
              fontSize: 9,
              fontWeight: FontWeight.w600,
              color: Theme.of(context).colorScheme.onSurfaceVariant,
            ),
          ),
        ),
        Flexible(
          child: Wrap(
            spacing: 2,
            runSpacing: 1,
            children: filters.map((cfg) {
        final count = counts[cfg.key] ?? 0;
        // Hide chips with 0 count (except "All")
        if (count == 0 && cfg.key.isNotEmpty) {
          return const SizedBox.shrink();
        }
        final isSelected = cfg.key.isEmpty
            ? selected.isEmpty
            : selected.contains(cfg.key);
        return Tooltip(
          message: '${cfg.label} ($count)',
          child: ActionChip(
            label: Row(
              mainAxisSize: MainAxisSize.min,
              children: <Widget>[
                if (isSelected)
                  Icon(Icons.check, size: 10, color: cfg.color.shade700),
                if (isSelected) const SizedBox(width: 2),
                Text(
                  '${cfg.label} ($count)',
                  style: TextStyle(
                    fontSize: 9,
                    color: isSelected ? cfg.color.shade700 : Colors.grey.shade700,
                  ),
                ),
              ],
            ),
            onPressed: onFiltersChanged != null
                ? () {
                    if (cfg.key.isEmpty) {
                      // "All" clears all state filters
                      onFiltersChanged!(<String>{});
                    } else {
                      // Toggle: if already selected, clear; else set this filter
                      if (isSelected) {
                        onFiltersChanged!(<String>{});
                      } else {
                        onFiltersChanged!(<String>{cfg.key});
                      }
                    }
                  }
                : null,
            backgroundColor: isSelected ? cfg.color.shade100 : Colors.grey.shade200,
            shape: RoundedRectangleBorder(
              borderRadius: BorderRadius.circular(6),
            ),
            padding: const EdgeInsets.symmetric(horizontal: 2, vertical: 0),
            visualDensity: const VisualDensity(
              horizontal: -4,
              vertical: -4,
            ),
            side: BorderSide(
              color: isSelected ? cfg.color.shade300 : Colors.grey.shade400,
            ),
          ),
        );
      }).toList(),
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
                  // Filter chips bar (left-aligned)
                  if (segmentMetadata.isNotEmpty)
                    Expanded(
                      child: _buildFilterChipsBar(context),
                    ),
                  const SizedBox(width: 8),
                  // Segment info and stats (right-aligned)
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
                      // Translation completion stats
                      if (translationState != null)
                        _buildTranslationStats(context, scheme),
                      // Page size selector (right of stats)
                      if (segmentsPaginationController != null) ...<Widget>[
                        const SizedBox(width: 6),
                        ListenableBuilder(
                          listenable: segmentsPaginationController!,
                          builder: (context, _) => PageSizeSelector(
                            currentPageSize:
                                segmentsPaginationController!.pageSize,
                            onPageSizeChanged: (size) {
                              segmentsPaginationController!.setPageSize(size);
                            },
                            preferenceKey:
                                'translation_result_segments_page_size',
                            pageSizeOptions: const <int>[
                              50,
                              100,
                              200,
                              500,
                              1000,
                              2000,
                            ],
                            showLabel: false,
                          ),
                        ),
                      ],
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
                                                        key: ValueKey(
                                                          'comparison_sliver_${taskId}_$effectiveTotal',
                                                        ),
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
            // Check if a state-based filter is active (mutually exclusive)
            final String stateFilter = selectedExclusionFilters!.firstWhere(
              (k) => _stateFilterKeys.contains(k),
              orElse: () => '',
            );

            if (stateFilter.isNotEmpty) {
              // State-based filtering
              final isImage = metadata['is_image'] as bool? ?? false;
              final isFailed = metadata['is_failed'] as bool? ?? false;
              final targetText = metadata['target_text'] as String?;
              final status = metadata['status'] as String?;
              final needsRetry = metadata['needs_retry'] as bool? ?? false;
              final isCleared = status == 'cleared';

              bool show = false;
              switch (stateFilter) {
                case 'translated':
                  show = !isImage &&
                      !isExcluded &&
                      !isFailed &&
                      !isCleared &&
                      targetText != null &&
                      targetText.isNotEmpty;
                case 'pending':
                  show = !isImage &&
                      !isExcluded &&
                      !isFailed &&
                      !isCleared &&
                      (targetText == null || targetText.isEmpty);
                case 'failed':
                  show = isFailed;
                case 'excluded':
                  show = isExcluded && !isFailed;
                case 'retry':
                  show = needsRetry || isFailed;
                case 'cleared':
                  show = isCleared;
                case 'images':
                  show = isImage;
              }

              if (!show) {
                return const SizedBox.shrink();
              }
            } else {
              // Type-based filtering (detected segment type, not excluded state)
              if (!matchesSegmentTypeFilter(
                metadata,
                selectedExclusionFilters!,
              )) {
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
              showPdfFontSize: showPdfFontSize && !pair.isImage,
              fontSizePt: _readFontSizePt(metadata),
              computedFontSizePt: _readComputedFontSizePt(metadata),
              fontSizeSource: metadata['font_size_source'] as String?,
              fontWeight: _readFontWeight(metadata),
              computedFontWeight: _readComputedFontWeight(metadata),
              fontWeightSource: metadata['font_weight_source'] as String?,
              fontStyle: _readFontStyle(metadata),
              computedFontStyle: _readComputedFontStyle(metadata),
              fontStyleSource: metadata['font_style_source'] as String?,
              leadingEm: _readLeadingEm(metadata),
              computedLeadingEm: _readComputedLeadingEm(metadata),
              leadingEmSource: metadata['leading_em_source'] as String?,
              onFontSizeChanged: onFontSizeChanged,
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

        // Apply filter: if filters are selected, only show matching segments
        if (selectedExclusionFilters != null &&
            selectedExclusionFilters!.isNotEmpty) {
          final String stateFilter = selectedExclusionFilters!.firstWhere(
            (k) => _stateFilterKeys.contains(k),
            orElse: () => '',
          );

          if (stateFilter.isNotEmpty) {
            bool show = false;
            switch (stateFilter) {
              case 'translated':
                show = !isImage &&
                    !isExcluded &&
                    !isFailed &&
                    !isCleared &&
                    metadata['target_text'] != null &&
                    (metadata['target_text'] as String).isNotEmpty;
              case 'pending':
                show = !isImage &&
                    !isExcluded &&
                    !isFailed &&
                    !isCleared &&
                    (metadata['target_text'] == null ||
                        (metadata['target_text'] as String).isEmpty);
              case 'failed':
                show = isFailed;
              case 'excluded':
                show = isExcluded && !isFailed;
              case 'retry':
                show = needsRetry || isFailed;
              case 'cleared':
                show = isCleared;
              case 'images':
                show = isImage;
            }
            if (!show) {
              return const SizedBox.shrink();
            }
          } else {
            if (!matchesSegmentTypeFilter(
              metadata,
              selectedExclusionFilters!,
            )) {
              return const SizedBox.shrink();
            }
          }
        }

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
                  showPdfFontSize: showPdfFontSize && !isImage,
                  fontSizePt: _readFontSizePt(metadata),
                  computedFontSizePt: _readComputedFontSizePt(metadata),
                  fontSizeSource: metadata['font_size_source'] as String?,
                  fontWeight: _readFontWeight(metadata),
                  computedFontWeight: _readComputedFontWeight(metadata),
                  fontWeightSource: metadata['font_weight_source'] as String?,
                  fontStyle: _readFontStyle(metadata),
                  computedFontStyle: _readComputedFontStyle(metadata),
                  fontStyleSource: metadata['font_style_source'] as String?,
                  leadingEm: _readLeadingEm(metadata),
                  computedLeadingEm: _readComputedLeadingEm(metadata),
                  leadingEmSource: metadata['leading_em_source'] as String?,
                  onFontSizeChanged: onFontSizeChanged,
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

/// Configuration for a filter chip in the filter bar.
class _FilterChipConfig {
  const _FilterChipConfig(this.key, this.label, this.color);
  final String key;
  final String label;
  final MaterialColor color;
}
