// SPDX-FileCopyrightText: 2025 QinHan
// SPDX-License-Identifier: MPL-2.0

import '../../features/translation/utils/segment_height_cache.dart';
import 'app_logger.dart';

/// Linear scroll position mapper with dynamic height correction
///
/// Core idea:
/// 1. Use linear mapping as base: scrollPosition = (index / totalItems) * estimatedTotalHeight
/// 2. Apply corrections for cached heights
/// 3. Dynamically update mapping as heights are measured
class LinearScrollMapper {
  LinearScrollMapper({
    required this.heightCache,
    required this.totalItems,
    double initialEstimatedHeight = 120.0,
  }) : _estimatedHeight = initialEstimatedHeight;

  final SegmentHeightCache heightCache;
  int totalItems;
  double _estimatedHeight;

  /// Get estimated total height based on cached and estimated heights
  /// Uses actual maxScrollExtent if available for better accuracy
  double getEstimatedTotalHeight({double? actualMaxScrollExtent}) {
    // If we have actual max scroll extent, use it directly (most accurate)
    if (actualMaxScrollExtent != null && actualMaxScrollExtent > 0) {
      AppLogger.log(
        'LinearScrollMapper',
        'getEstimatedTotalHeight: Using actual maxScrollExtent=${actualMaxScrollExtent.toStringAsFixed(1)}',
      );
      return actualMaxScrollExtent;
    }

    if (totalItems <= 0) return 0;

    // Calculate average height from cached items
    final cachedCount = heightCache.getCacheSize();
    double avgHeight = _estimatedHeight;

    if (cachedCount > 0) {
      double totalCached = 0;
      int count = 0;
      // Sample cached heights (up to 100 items for performance)
      for (int i = 0; i < totalItems && count < 100; i++) {
        if (heightCache.isHeightCached(i)) {
          totalCached += heightCache.getHeight(i);
          count++;
        }
      }
      if (count > 0) {
        avgHeight = totalCached / count;
        // Update estimated height: 80% new average, 20% old estimate
        _estimatedHeight = avgHeight * 0.8 + _estimatedHeight * 0.2;
      }
    }

    // Estimate total height: all items use average height
    final estimatedTotal = totalItems * avgHeight;

    AppLogger.log(
      'LinearScrollMapper',
      'getEstimatedTotalHeight: totalItems=$totalItems, cachedCount=$cachedCount, '
          'avgHeight=${avgHeight.toStringAsFixed(1)}, estimatedTotal=${estimatedTotal.toStringAsFixed(1)}',
    );

    return estimatedTotal;
  }

  /// Update total items count (called when data is loaded)
  void updateTotalItems(int newTotalItems) {
    if (newTotalItems != totalItems) {
      AppLogger.log(
        'LinearScrollMapper',
        'updateTotalItems: $totalItems -> $newTotalItems',
      );
      totalItems = newTotalItems;
    }
  }

  /// Convert scroll position to segment index using linear mapping + correction
  ///
  /// Algorithm:
  /// 1. Use linear mapping to get initial estimate
  /// 2. Find nearest cached height anchor points
  /// 3. Apply correction based on actual vs estimated heights
  int scrollPositionToIndex(
    double scrollPosition, {
    int? currentPageStart,
    int? currentPageEnd,
    double? actualMaxScrollExtent,
  }) {
    if (totalItems <= 0 || scrollPosition < 0) {
      AppLogger.log(
        'LinearScrollMapper',
        'scrollPositionToIndex: Invalid input - totalItems=$totalItems, scrollPosition=$scrollPosition',
        level: LogLevel.warn,
      );
      return 0;
    }

    final estimatedTotal =
        getEstimatedTotalHeight(actualMaxScrollExtent: actualMaxScrollExtent);
    if (estimatedTotal <= 0) {
      AppLogger.log(
        'LinearScrollMapper',
        'scrollPositionToIndex: estimatedTotal=$estimatedTotal is invalid',
        level: LogLevel.warn,
      );
      return 0;
    }

    // Step 1: Linear mapping to get initial estimate
    final linearRatio = scrollPosition / estimatedTotal;
    // Clamp with safe bounds check
    final estimatedIndex = totalItems > 0
        ? (linearRatio * totalItems).clamp(0, totalItems - 1).toInt()
        : 0;

    AppLogger.log(
      'LinearScrollMapper',
      'scrollPositionToIndex: scrollPosition=${scrollPosition.toStringAsFixed(1)}, '
          'estimatedTotal=${estimatedTotal.toStringAsFixed(1)}, linearRatio=${linearRatio.toStringAsFixed(4)}, '
          'estimatedIndex=$estimatedIndex, totalItems=$totalItems',
    );

    // Step 2: Simple linear mapping only - no correction to avoid jitter
    // Core principle: Let scroll position naturally follow user input
    // Height cache is only used for scrollToIndex, not for position-to-index conversion
    // This ensures: scroll wheel -> scrollbar -> current segment rendering (no feedback loop)
    int resultIndex = estimatedIndex;

    // Clamp to valid range (with safe bounds check)
    if (totalItems > 0) {
      resultIndex = resultIndex.clamp(0, totalItems - 1);
    } else {
      resultIndex = 0;
    }

    return resultIndex;
  }

  /// Convert segment index to scroll position using linear mapping + correction
  ///
  /// Algorithm:
  /// 1. If height is cached, use actual cumulative offset
  /// 2. Otherwise, use linear mapping with correction from nearest cached anchors
  double indexToScrollPosition(
    int index, {
    double viewportHeight = 0.0,
    double alignment = 0.0,
  }) {
    if (index < 0 || index >= totalItems) return 0;

    // If height is cached, use actual offset
    if (heightCache.isHeightCached(index)) {
      final cumulativeOffset = heightCache.getCumulativeOffset(index);
      if (viewportHeight > 0) {
        return cumulativeOffset - (viewportHeight * alignment);
      }
      return cumulativeOffset;
    }

    // Otherwise, use linear mapping with correction
    final estimatedTotal = getEstimatedTotalHeight();
    if (estimatedTotal <= 0) return 0;

    // Find nearest cached anchors
    int? lowerAnchorIndex;
    int? upperAnchorIndex;
    double? lowerAnchorOffset;
    double? upperAnchorOffset;

    // Search backwards for lower anchor
    for (int i = index; i >= 0; i--) {
      if (heightCache.isHeightCached(i)) {
        lowerAnchorIndex = i;
        lowerAnchorOffset = heightCache.getCumulativeOffset(i);
        break;
      }
    }

    // Search forwards for upper anchor
    for (int i = index; i < totalItems; i++) {
      if (heightCache.isHeightCached(i)) {
        upperAnchorIndex = i;
        upperAnchorOffset = heightCache.getCumulativeOffset(i);
        break;
      }
    }

    double scrollPosition;

    if (lowerAnchorIndex != null && lowerAnchorOffset != null) {
      // Calculate from lower anchor
      double offsetFromAnchor = 0;
      for (int i = lowerAnchorIndex + 1; i <= index; i++) {
        offsetFromAnchor += heightCache.getHeight(i);
      }
      scrollPosition = lowerAnchorOffset + offsetFromAnchor;
    } else if (upperAnchorIndex != null && upperAnchorOffset != null) {
      // Calculate from upper anchor (backwards)
      double offsetFromAnchor = 0;
      for (int i = upperAnchorIndex - 1; i >= index; i--) {
        offsetFromAnchor += heightCache.getHeight(i);
      }
      scrollPosition = upperAnchorOffset - offsetFromAnchor;
    } else {
      // No anchors, use pure linear mapping
      final linearRatio = index / totalItems;
      scrollPosition = linearRatio * estimatedTotal;
    }

    // Apply alignment if viewport height is provided
    if (viewportHeight > 0) {
      scrollPosition -= viewportHeight * alignment;
    }

    return scrollPosition;
  }

  /// Update estimated height based on new measurements
  void updateEstimatedHeight() {
    final cachedCount = heightCache.getCacheSize();
    if (cachedCount < 5) return; // Need at least 5 samples

    // Calculate average of cached heights
    double totalCached = 0;
    int count = 0;
    for (int i = 0; i < totalItems && count < 100; i++) {
      // Sample up to 100 items
      if (heightCache.isHeightCached(i)) {
        totalCached += heightCache.getHeight(i);
        count++;
      }
    }

    if (count > 0) {
      final avgHeight = totalCached / count;
      // Weighted update: 80% new average, 20% old estimate
      _estimatedHeight = avgHeight * 0.8 + _estimatedHeight * 0.2;
    }
  }
}
