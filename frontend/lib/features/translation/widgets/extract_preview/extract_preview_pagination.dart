import 'package:flutter/material.dart';
import 'package:flutter/foundation.dart' show kDebugMode;
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../../../shared/utils/app_logger.dart';
import '../../providers/excluded_segments_provider.dart';
import '../../utils/segment_height_calculator.dart';
import '../extract_preview.dart';
import 'extract_preview_state.dart';

/// Mixin for pagination and scrolling in ExtractPreview
///
/// This mixin provides methods for:
/// - Handling pagination changes
/// - Updating segment keys for scroll management
/// - Highlighting segments
/// - Pre-calculating segment heights
/// - Managing filter mode pagination
///
/// **Note**: These methods handle pagination state and scroll position management.
mixin ExtractPreviewPaginationMixin<T extends ConsumerStatefulWidget>
    on ConsumerState<T>, ExtractPreviewStateMixin<T> {
  // ============================================================================
  // Required Methods (inherited from State class)
  // ============================================================================

  // Note: The following are available from ConsumerState<T>:
  // - BuildContext get context
  // - T get widget
  // - void setState(VoidCallback fn)
  // - bool get mounted
  //
  // The following should be provided by the State class:
  // - void _log(String message, {LogLevel level = LogLevel.debug})

  // ============================================================================
  // Pagination Methods
  // ============================================================================

  /// Handle pagination changes
  /// Called when pagination offset or page size changes
  void onPaginationChanged() {
    if (mounted) {
      final int currentOffset = paginationController.offset;
      final bool isRealPaginationChange = lastPaginationOffset != currentOffset;
      lastPaginationOffset = currentOffset;

      // Only save/restore scroll position if:
      // 1. User is NOT actively scrolling
      // 2. This is a REAL pagination change (offset changed), not just data refresh
      final bool isUserScrolling =
          (segmentsScrollManager?.scrollController.hasClients ?? false) &&
              segmentsScrollManager!
                  .scrollController.position.isScrollingNotifier.value;

      if (!isUserScrolling && isRealPaginationChange) {
        // Save current scroll position before updating keys
        segmentsScrollManager?.saveScrollPosition();
      }

      setState(updateSegmentKeys);

      // Only restore if user is NOT actively scrolling AND this is a real pagination change
      if (!isUserScrolling && isRealPaginationChange) {
        // Restore scroll position after layout
        segmentsScrollManager?.restoreScrollPosition();
      }
    }
  }

  /// Update segment keys for scroll management
  void updateSegmentKeys() {
    segmentKeys.clear();
    final items = paginationController.items;
    final offset = paginationController.offset;
    // Use global index for keys to match height cache
    for (int i = 0; i < items.length; i++) {
      int globalIndex;
      if (filterMode == 'rebuild' &&
          selectedExclusionFilters.isNotEmpty &&
          filteredSegmentIndices != null) {
        // Rebuild mode: use filtered indices
        final List<int> filteredIndices = filteredSegmentIndices!;
        if (offset + i < filteredIndices.length) {
          globalIndex = filteredIndices[offset + i];
        } else {
          // Fallback (should not happen)
          globalIndex = offset + i;
        }
      } else {
        // Page mode or no filters: use direct offset
        globalIndex = offset + i;
      }
      segmentKeys[globalIndex] = GlobalKey();
    }
  }

  /// Highlight a segment and scroll to it
  void highlightSegment(int localIndex) {
    // CRITICAL: Use addPostFrameCallback to avoid setState during layout
    // This prevents "RenderObject was mutated during layout" errors
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (!mounted) return;
      setState(() {
        highlightedIndex = localIndex;
      });
      // Scroll to segment using scroll manager (supports cross-page navigation)
      final int globalIndex = paginationController.offset + localIndex;
      segmentsScrollManager?.scrollToIndex(
        globalIndex,
        animate: true,
      );
    });
  }

  /// Pre-calculate all segment heights using SegmentHeightCalculator
  /// This ensures stable maxScrollExtent and prevents scrollbar jitter
  /// For large segment counts, calculation is batched across frames to avoid
  /// CanvasKit WASM memory overflow.
  void precalculateAllHeights([double? actualWidth]) {
    if (allSegments.isEmpty || segmentsHeightCache == null) {
      return;
    }

    // Get available width from context
    if (!mounted) return;
    final BuildContext context = this.context;

    // Use actual width if provided, otherwise estimate
    double availableWidth;
    if (actualWidth != null && actualWidth > 0) {
      // Use actual width from LayoutBuilder
      // Account for Card padding (12px * 2) and Container padding (8px * 2)
      availableWidth = actualWidth - 12.0 * 2 - 8.0 * 2;
    } else {
      // Fallback: estimate from screen width
      final MediaQueryData mediaQuery = MediaQuery.of(context);
      final double screenWidth = mediaQuery.size.width;
      // Left panel is ~2/3 of screen, minus Card padding (12*2), Container padding (8*2), and margins
      availableWidth = (screenWidth * 2.0 / 3.0) -
          12.0 * 2 -
          8.0 * 2 -
          16.0; // 16px for spacing between panels
    }

    // Ensure minimum width
    availableWidth = availableWidth.clamp(200.0, double.infinity);

    // Get excluded segments
    final extractWidget = widget as ExtractPreview;
    final providerKey = extractWidget.flowId ?? extractWidget.taskId;
    final excludedSegments = ref.read(
      excludedSegmentsProviderFamily(providerKey),
    );

    // Create height calculator
    final SegmentHeightCalculator calculator = SegmentHeightCalculator(
      availableWidth: availableWidth,
      imageDataMap: imageDataMap,
    );

    // For large segment counts, batch calculation across frames to avoid
    // CanvasKit WASM memory overflow from too many TextPainter.layout() calls.
    const int batchSize = 200;
    if (allSegments.length > batchSize) {
      _precalculateAllHeightsBatched(
        calculator,
        allSegments,
        excludedSegments,
        batchSize,
      );
      return;
    }

    // Small count: calculate synchronously
    final Map<int, double> heights = calculator.calculateAllHeights(
      allSegments,
      excludedSegments,
    );

    _cacheHeightsAndLog(heights);
  }

  /// Batched height calculation to avoid blocking UI and CanvasKit memory overflow.
  void _precalculateAllHeightsBatched(
    SegmentHeightCalculator calculator,
    List<String> segments,
    Set<int> excludedSegments,
    int batchSize,
  ) {
    var start = 0;

    void calculateBatch() {
      if (!mounted || segmentsHeightCache == null) return;

      final end = (start + batchSize < segments.length)
          ? start + batchSize
          : segments.length;
      for (var i = start; i < end; i++) {
        final bool isExcluded = excludedSegments.contains(i);
        final height = calculator.calculateItemHeight(
          segments[i],
          isExcluded: isExcluded,
        );
        segmentsHeightCache!.setHeight(i, height);
      }

      start = end;
      if (start < segments.length) {
        // Schedule next batch in next frame to yield to event loop
        // and give CanvasKit time to reclaim WASM memory.
        WidgetsBinding.instance.addPostFrameCallback(
          (_) => calculateBatch(),
        );
      }
    }

    calculateBatch();
  }

  void _cacheHeightsAndLog(Map<int, double> heights) {
    if (segmentsHeightCache == null) return;

    var totalCalculatedHeight = 0;
    var minHeight = double.infinity;
    var maxHeight = 0;
    for (final MapEntry<int, double> entry in heights.entries) {
      segmentsHeightCache!.setHeight(entry.key, entry.value);
      totalCalculatedHeight += entry.value.round();
      if (entry.value < minHeight) minHeight = entry.value;
      if (entry.value > maxHeight) maxHeight = entry.value.round();
    }

    // Calculate expected maxScrollExtent (for debugging)
    // Each item has a Divider (2px) after it in the Column
    const dividerHeight =
        2; // Reduced from 8.0 to 2.0 to match actual Divider height
    final expectedMaxExtent =
        totalCalculatedHeight + (heights.length * dividerHeight);

    if (kDebugMode) {
      AppLogger.log(
        'ExtractPreview',
        'Pre-calculated ${heights.length} segment heights: '
            'totalHeight=${totalCalculatedHeight.toStringAsFixed(1)}, '
            'minHeight=${minHeight.toStringAsFixed(1)}, '
            'maxHeight=${maxHeight.toStringAsFixed(1)}, '
            'expectedMaxExtent=${expectedMaxExtent.toStringAsFixed(1)}',
        level: LogLevel.info,
      );
    }
  }

  /// Calculate filtered segments count based on current filters
  /// This is used to update pagination totalItems when filters are active
  ///
  /// **TODO**: Move implementation from extract_preview.dart
  /// Current location: ~line 3804
  /// **Note**: This method may be moved to ExtractPreviewExclusionHandlerMixin instead
  int calculateFilteredSegmentCount() {
    // Implementation to be moved from extract_preview.dart
    return 0;
  }

  /// Update pagination for filter mode changes
  ///
  /// **TODO**: Move implementation from extract_preview.dart
  /// Current location: ~line 3850
  /// **Note**: This method may be moved to ExtractPreviewExclusionHandlerMixin instead
  void updatePaginationForFilterMode() {
    // Implementation to be moved from extract_preview.dart
    // This method handles pagination updates when filter mode changes
  }
}
