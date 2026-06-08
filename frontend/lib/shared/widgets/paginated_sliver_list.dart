// SPDX-FileCopyrightText: 2025 QinHan
// SPDX-License-Identifier: MPL-2.0

import 'package:flutter/material.dart';
import '../../features/translation/utils/segment_height_cache.dart';
import '../utils/pagination.dart';
import 'fixed_height_sliver_delegate.dart';
import 'item_with_height_measurement.dart';

/// Unified paginated sliver list component for optimized scrolling
///
/// This component encapsulates the common pattern of:
/// - CustomScrollView + SliverList for stable scrolling
/// - FixedHeightSliverChildDelegate for stable maxScrollExtent
/// - ItemWithHeightMeasurement for automatic height measurement
/// - SegmentHeightCache for height caching
/// - PaginatedScrollManager for scroll position management
///
/// Usage:
/// ```dart
/// PaginatedSliverList<String>(
///   paginationController: _paginationController,
///   heightCache: _heightCache,
///   scrollController: _scrollController,
///   totalItems: _allItems.length,
///   itemKeys: _itemKeys,
///   itemBuilder: (context, index, item) => YourItemWidget(item: item),
///   separatorHeight: 2.0,
///   padding: EdgeInsets.all(8),
/// )
/// ```
class PaginatedSliverList<T> extends StatelessWidget {
  const PaginatedSliverList({
    required this.paginationController,
    required this.heightCache,
    required this.scrollController,
    required this.totalItems,
    required this.itemKeys,
    required this.itemBuilder,
    super.key,
    this.separatorHeight =
        2.0, // Reduced from 8.0 to 2.0 to match actual Divider height
    this.padding,
    this.cacheExtent = 500.0,
    this.enableHeightMeasurement = true,
    this.minHeightDiff = 1.0,
    this.initialBuffer = 100.0,
  });

  /// Pagination controller for managing paginated data
  final PagedListController<T> paginationController;

  /// Height cache for item heights
  final SegmentHeightCache heightCache;

  /// Scroll controller for the scrollable view
  final ScrollController scrollController;

  /// Total number of items across all pages
  final int totalItems;

  /// Map of item index to GlobalKey for height measurement
  final Map<int, GlobalKey> itemKeys;

  /// Builder function for creating item widgets
  /// [context] - Build context
  /// [index] - Local index within current page (0-based)
  /// [item] - The item data from pagination controller
  /// [itemKey] - GlobalKey for the item (for use by child widgets like SegmentNumberedItem)
  /// Returns: Widget for the item
  final Widget Function(
    BuildContext context,
    int index,
    T item,
    GlobalKey itemKey,
  ) itemBuilder;

  /// Height of separator between items (e.g., Divider height)
  /// Default: 8.0
  final double separatorHeight;

  /// Padding around the list
  /// If null, no padding is applied
  final EdgeInsets? padding;

  /// Cache extent for the scrollable view (in pixels)
  /// Default: 500.0
  final double cacheExtent;

  /// Whether to enable automatic height measurement
  /// Default: true
  final bool enableHeightMeasurement;

  /// Minimum height difference (in pixels) to trigger cache update
  /// Default: 1.0 pixel to avoid small calculation errors
  final double minHeightDiff;

  /// Initial buffer for view height in maxScrollExtent calculation
  /// Default: 100.0
  final double initialBuffer;

  @override
  Widget build(BuildContext context) => ListenableBuilder(
        listenable: paginationController,
        builder: (BuildContext context, _) {
          final List<T> items = paginationController.items;
          final int offset = paginationController.offset;

          if (items.isEmpty) {
            return Center(
              child: paginationController.isLoading
                  ? const CircularProgressIndicator()
                  : Text(
                      'No items available',
                      style: TextStyle(
                        color: Theme.of(context).colorScheme.onSurfaceVariant,
                      ),
                    ),
            );
          }

          return CustomScrollView(
            controller: scrollController,
            cacheExtent: cacheExtent,
            slivers: <Widget>[
              if (padding != null)
                SliverPadding(
                  padding: padding!,
                  sliver: _buildSliverList(items, offset),
                )
              else
                _buildSliverList(items, offset),
            ],
          );
        },
      );

  Widget _buildSliverList(List<T> items, int offset) => SliverList(
        delegate: FixedHeightSliverChildDelegate(
          builder: (BuildContext context, int i) {
            if (i >= items.length) {
              return const SizedBox.shrink();
            }

            final T item = items[i];
            final int globalIndex = offset + i;

            // Ensure key exists for this item
            if (!itemKeys.containsKey(globalIndex)) {
              itemKeys[globalIndex] = GlobalKey();
            }
            final GlobalKey<State<StatefulWidget>> itemKey =
                itemKeys[globalIndex]!;

            // Build the item widget
            // Note: itemBuilder should return the complete item widget including separators if needed
            // The widget will be measured as a whole by ItemWithHeightMeasurement
            // Pass itemKey to itemBuilder so child widgets (e.g., SegmentNumberedItem) can use it
            final Widget itemWidget = itemBuilder(context, i, item, itemKey);

            // Wrap with height measurement if enabled
            // ItemWithHeightMeasurement now measures its own context when itemKey is null,
            // avoiding the need for a separate GlobalKey that caused remounts on every rebuild.
            if (enableHeightMeasurement) {
              return ItemWithHeightMeasurement(
                index: globalIndex,
                itemKey: null, // Measure using own context
                heightCache: heightCache,
                minHeightDiff: minHeightDiff,
                child: RepaintBoundary(
                  child: itemWidget,
                ),
              );
            } else {
              return RepaintBoundary(
                key: itemKey,
                child: itemWidget,
              );
            }
          },
          childCount: items.length,
          heightCache: heightCache,
          paginationOffset: offset,
          totalItems: totalItems,
          scrollController: scrollController,
          separatorHeight: separatorHeight,
          initialBuffer: initialBuffer,
        ),
      );
}
