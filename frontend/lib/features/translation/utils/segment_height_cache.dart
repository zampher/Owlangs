// SPDX-FileCopyrightText: 2025 QinHan
// SPDX-License-Identifier: MPL-2.0

import 'package:flutter/material.dart';

/// Cache manager for segment heights to enable smooth scrolling and fast navigation
/// Maintains both individual heights and cumulative height offsets for O(1) position calculation
class SegmentHeightCache {
  SegmentHeightCache({
    this.listPadding = 4.0, // Reduced from 8.0 to 4.0 for more compact display
    this.itemMargin =
        1.0, // Further reduced from 2.0 to 1.0 to match actual segment margin
    double estimatedHeight = 120.0,
  }) : _estimatedHeight = estimatedHeight;
  // Individual segment heights (including margin)
  final Map<int, double> _heights = <int, double>{};

  // Cumulative height offsets (for O(1) position calculation)
  // cumulativeOffsets[i] = sum of heights[0..i-1]
  final List<double> _cumulativeOffsets = <double>[];

  // Estimated height for segments not yet measured
  double _estimatedHeight = 120;

  // List padding (from ListView padding)
  final double listPadding;

  // Item margin (bottom margin for each segment pair)
  final double itemMargin;

  /// Get the height of a specific segment
  /// Returns cached height if available, otherwise returns estimated height
  /// If correction factor is available, applies it to the estimated height for better accuracy
  double getHeight(int index) {
    if (_heights.containsKey(index)) {
      return _heights[index]!;
    }

    // Apply correction factor to estimated height if available
    // This improves prediction accuracy based on actual measurements
    final double? correctionFactor = getCorrectionFactor(index);
    if (correctionFactor != null && correctionFactor > 0) {
      return _estimatedHeight * correctionFactor;
    }

    return _estimatedHeight;
  }

  /// Set the height of a specific segment
  /// Automatically updates cumulative offsets
  void setHeight(int index, double height) {
    _heights[index] = height;
    _updateCumulativeOffsets();
  }

  /// Get cumulative offset (position) for a segment index
  /// This is O(1) after initial calculation
  double getCumulativeOffset(int index) {
    if (index < 0) return listPadding;

    // Ensure cumulative offsets array is large enough
    while (_cumulativeOffsets.length <= index) {
      final int prevIndex = _cumulativeOffsets.length - 1;
      final double prevOffset =
          prevIndex >= 0 ? _cumulativeOffsets[prevIndex] : listPadding;
      final double height = getHeight(prevIndex + 1);
      _cumulativeOffsets.add(prevOffset + height);
    }

    return _cumulativeOffsets[index];
  }

  /// Calculate scroll offset to position segment at a specific alignment
  /// [index] - Segment index (0-based)
  /// [viewportHeight] - Height of the viewport
  /// [alignment] - Where to position the segment (0.0 = top, 0.5 = center, 1.0 = bottom)
  double calculateScrollOffset(
    int index,
    double viewportHeight,
    double alignment,
  ) {
    final double cumulativeOffset = getCumulativeOffset(index);
    // Adjust to position segment at alignment position
    return cumulativeOffset - (viewportHeight * alignment);
  }

  /// Update cumulative offsets after height changes
  void _updateCumulativeOffsets() {
    if (_heights.isEmpty) {
      _cumulativeOffsets.clear();
      return;
    }

    final int maxIndex = _heights.keys.reduce((int a, int b) => a > b ? a : b);
    _cumulativeOffsets.clear();

    var offset = listPadding;
    for (var i = 0; i <= maxIndex; i++) {
      _cumulativeOffsets.add(offset);
      offset += getHeight(i);
    }
  }

  /// Measure and cache height for a segment using GlobalKey
  /// Returns true if measurement was successful
  ///
  /// [predictedHeight] - Optional predicted height for comparison and correction
  /// Returns the actual measured height and the correction factor (actual / predicted)
  bool measureAndCacheHeight(
    int index,
    GlobalKey? key, {
    double? predictedHeight,
  }) {
    if (key == null) return false;

    final BuildContext? context = key.currentContext;
    if (context == null) return false;

    final RenderBox? renderBox = context.findRenderObject() as RenderBox?;
    if (renderBox == null || !renderBox.hasSize) return false;

    // Cache height including margin
    final double actualHeight = renderBox.size.height + itemMargin;
    setHeight(index, actualHeight);

    // If predicted height was provided, calculate correction factor
    // This can be used to correct predictions for other segments
    if (predictedHeight != null && predictedHeight > 0) {
      final double correctionFactor = actualHeight / predictedHeight;
      // Store correction factor for this index (can be used to correct nearby segments)
      _correctionFactors[index] = correctionFactor;

      // Update average correction factor for better prediction
      _updateAverageCorrectionFactor();
    }

    // Update estimated height based on measured heights (for better fallback)
    _updateEstimatedHeight();

    return true;
  }

  /// Record a measured height directly without needing a GlobalKey.
  ///
  /// This is useful when the caller already has access to the render box
  /// or when using [ItemWithHeightMeasurement] without a key.
  ///
  /// [height] should be the raw render box height (margin is added internally).
  /// [predictedHeight] - Optional predicted height for correction factor calculation.
  void recordMeasuredHeight(
    int index,
    double height, {
    double? predictedHeight,
  }) {
    final double actualHeight = height + itemMargin;
    setHeight(index, actualHeight);

    if (predictedHeight != null && predictedHeight > 0) {
      final double correctionFactor = actualHeight / predictedHeight;
      _correctionFactors[index] = correctionFactor;
      _updateAverageCorrectionFactor();
    }

    _updateEstimatedHeight();
  }

  // Correction factors: index -> correction factor (actual / predicted)
  final Map<int, double> _correctionFactors = <int, double>{};

  // Average correction factor for nearby segments
  double? _averageCorrectionFactor;

  /// Get correction factor for a specific index
  /// Returns the correction factor for this index, or the average if not available
  double? getCorrectionFactor(int index) =>
      _correctionFactors[index] ?? _averageCorrectionFactor;

  /// Update average correction factor based on recent measurements
  void _updateAverageCorrectionFactor() {
    if (_correctionFactors.isEmpty) {
      _averageCorrectionFactor = null;
      return;
    }

    final List<double> factors = _correctionFactors.values.toList();
    // Use median for more stable estimation
    factors.sort();
    if (factors.length == 1) {
      _averageCorrectionFactor = factors[0];
    } else if (factors.length % 2 == 0) {
      final int mid = factors.length ~/ 2;
      _averageCorrectionFactor = (factors[mid - 1] + factors[mid]) / 2;
    } else {
      final int mid = factors.length ~/ 2;
      _averageCorrectionFactor = factors[mid];
    }

    // Clamp to reasonable range (0.5x to 2.0x)
    _averageCorrectionFactor = _averageCorrectionFactor!.clamp(0.5, 2.0);
  }

  /// Apply correction factor to predicted height for better accuracy
  /// This is used when we have measured some segments and want to correct predictions for others
  double applyCorrectionFactor(int index, double predictedHeight) {
    final double? correctionFactor = getCorrectionFactor(index);
    if (correctionFactor != null && correctionFactor > 0) {
      return predictedHeight * correctionFactor;
    }
    return predictedHeight;
  }

  /// Update estimated height based on measured heights
  /// Uses median instead of mean for more stable estimation
  void _updateEstimatedHeight() {
    if (_heights.isEmpty) return;

    final List<double> heights = _heights.values.toList()..sort();

    // Use median for more stable estimation (less affected by outliers)
    if (heights.length == 1) {
      _estimatedHeight = heights[0];
    } else if (heights.length % 2 == 0) {
      // Even number of items: average of two middle values
      final int mid = heights.length ~/ 2;
      _estimatedHeight = (heights[mid - 1] + heights[mid]) / 2;
    } else {
      // Odd number of items: middle value
      final int mid = heights.length ~/ 2;
      _estimatedHeight = heights[mid];
    }

    // Clamp to reasonable range (avoid extreme values)
    _estimatedHeight = _estimatedHeight.clamp(50.0, 1000.0);
  }

  /// Clear all cached heights
  void clear() {
    _heights.clear();
    _cumulativeOffsets.clear();
  }

  /// Clear heights for a range of indices (useful when segments are updated)
  void clearRange(int startIndex, int endIndex) {
    for (var i = startIndex; i <= endIndex; i++) {
      _heights.remove(i);
    }
    // Recalculate cumulative offsets
    _updateCumulativeOffsets();
  }

  /// Get total content height (sum of all segment heights)
  double getTotalHeight(int totalSegments) {
    if (totalSegments <= 0) return listPadding;

    var total = listPadding;
    for (var i = 0; i < totalSegments; i++) {
      total += getHeight(i);
    }
    return total;
  }

  /// Check if height is cached for a specific index
  bool isHeightCached(int index) => _heights.containsKey(index);

  /// Get number of cached heights
  int getCacheSize() => _heights.length;

  /// Get estimated average height for prototype item
  /// This is used to provide ListView with a stable estimated height
  /// to prevent maxScrollExtent from fluctuating during scrolling
  double getEstimatedAverageHeight() {
    if (_heights.isEmpty) return _estimatedHeight;

    // Calculate average from cached heights
    final List<double> heights = _heights.values.toList();
    final double sum = heights.reduce((double a, double b) => a + b);
    final double avg = sum / heights.length;

    // Use median for more stable estimation (less affected by outliers)
    heights.sort();
    double median;
    if (heights.length == 1) {
      median = heights[0];
    } else if (heights.length % 2 == 0) {
      final int mid = heights.length ~/ 2;
      median = (heights[mid - 1] + heights[mid]) / 2;
    } else {
      final int mid = heights.length ~/ 2;
      median = heights[mid];
    }

    // Use weighted average: 70% median, 30% mean (median is more stable)
    final double estimated = median * 0.7 + avg * 0.3;

    // Clamp to reasonable range
    return estimated.clamp(50.0, 1000.0);
  }

  /// Batch measure heights for multiple segments
  /// Returns number of successfully measured segments
  int batchMeasureHeights(Map<int, GlobalKey?> keys) {
    var measured = 0;
    for (final MapEntry<int, GlobalKey<State<StatefulWidget>>?> entry
        in keys.entries) {
      if (measureAndCacheHeight(entry.key, entry.value)) {
        measured++;
      }
    }
    return measured;
  }
}
