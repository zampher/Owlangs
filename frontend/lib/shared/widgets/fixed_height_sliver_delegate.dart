// SPDX-FileCopyrightText: 2025 QinHan
// SPDX-License-Identifier: MPL-2.0

import 'package:flutter/material.dart';
import '../../features/translation/utils/segment_height_cache.dart';

/// Custom SliverChildDelegate that provides fixed item heights
/// to prevent maxScrollExtent from fluctuating during scrolling
///
/// This delegate calculates a stable maxScrollExtent based on cached heights
/// and dynamically adjusts when scrolling near the bottom or when all items
/// are rendered.
class FixedHeightSliverChildDelegate extends SliverChildBuilderDelegate {
  FixedHeightSliverChildDelegate({
    required Widget Function(BuildContext, int) builder,
    required int? childCount,
    required this.heightCache,
    required this.paginationOffset,
    required this.totalItems,
    required this.scrollController,
    this.separatorHeight =
        1.0, // Further reduced from 2.0 to 1.0 to match actual Divider height
    this.initialBuffer = 100.0,
  }) : super(
          builder,
          childCount: childCount,
        );

  /// Height cache for item heights
  final SegmentHeightCache heightCache;

  /// Pagination offset (starting index of current page)
  final int paginationOffset;

  /// Total number of items across all pages
  final int totalItems;

  /// Scroll controller to check scroll position
  final ScrollController scrollController;

  /// Height of separator between items (e.g., Divider height)
  /// Default: 2.0
  final double separatorHeight;

  /// Initial buffer for view height
  /// Default: 100.0
  final double initialBuffer;

  @override
  double? estimateMaxScrollOffset(
    int firstIndex,
    int lastIndex,
    double leadingScrollOffset,
    double trailingScrollOffset,
  ) {
    if (childCount == null) return null;

    // Calculate stats from cached heights in a single pass.
    double totalCachedHeight = 0;
    var cachedCount = 0;
    double maxCachedHeight = 0;

    for (var i = 0; i < totalItems; i++) {
      if (heightCache.isHeightCached(i)) {
        final double height = heightCache.getHeight(i);
        totalCachedHeight += height;
        cachedCount++;
        if (height > maxCachedHeight) {
          maxCachedHeight = height;
        }
      }
    }

    final double avgHeight = cachedCount > 0
        ? (totalCachedHeight / cachedCount) + separatorHeight
        : (heightCache.getEstimatedAverageHeight() + separatorHeight);

    // Use max height as a conservative estimate for unrendered items
    final double estimatedItemHeight =
        maxCachedHeight > 0 ? maxCachedHeight + separatorHeight : avgHeight;

    // Calculate total height using multiplication instead of O(n) per-item loop
    var totalHeight = heightCache.listPadding;
    totalHeight += totalCachedHeight + cachedCount * separatorHeight;
    totalHeight += (totalItems - cachedCount) * estimatedItemHeight;

    // Add buffer for viewport height to ensure smooth scrolling
    final totalUnrendered = totalItems - cachedCount;

    // Get viewport height to ensure we can scroll to the very bottom
    double viewportHeight = 0;
    try {
      if (scrollController.hasClients) {
        viewportHeight = scrollController.position.viewportDimension;
      }
    } catch (e) {
      // ScrollController not ready yet, use default
    }

    // Ensure viewportHeight is positive
    if (viewportHeight <= 0) {
      viewportHeight = 400.0; // Default to a reasonable value
    }

    // Calculate actual rendered height estimate up to lastIndex
    double actualRenderedHeight = 0;
    if (lastIndex >= 0 && lastIndex < totalItems) {
      actualRenderedHeight =
          totalCachedHeight + cachedCount * separatorHeight;
      final renderedBeyondCached = (lastIndex + 1) - cachedCount;
      if (renderedBeyondCached > 0) {
        actualRenderedHeight += renderedBeyondCached * estimatedItemHeight;
      }
    }

    // Calculate buffer
    var buffer = initialBuffer;
    if (totalUnrendered > 0) {
      buffer += totalUnrendered * estimatedItemHeight * 0.3;
    }
    buffer += viewportHeight;
    final safetyMargin = (totalHeight * 0.15).clamp(200.0, 1000.0);
    buffer += safetyMargin;

    totalHeight += buffer;

    // Ensure estimatedMaxScrollOffset is always >= actual scroll extent
    var minRequiredHeight = actualRenderedHeight +
        viewportHeight +
        500.0; // Large buffer for safety

    // Also consider trailingScrollOffset if available (from SliverList)
    if (trailingScrollOffset > 0) {
      final trailingBasedHeight = trailingScrollOffset + viewportHeight + 500.0;
      if (trailingBasedHeight > minRequiredHeight) {
        minRequiredHeight = trailingBasedHeight;
      }
    }

    // Return the maximum of all calculated values
    var result = totalHeight;
    if (minRequiredHeight > result) {
      result = minRequiredHeight;
    }

    // Add extra safety margin (5% more) to handle edge cases
    result = result * 1.05;

    return result;
  }
}
