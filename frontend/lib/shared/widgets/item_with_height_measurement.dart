// SPDX-FileCopyrightText: 2025 QinHan
// SPDX-License-Identifier: MPL-2.0

import 'package:flutter/material.dart';
import '../../features/translation/utils/segment_height_cache.dart';

/// Widget that measures item height after rendering and updates the cache
///
/// This ensures the height cache uses actual measured heights instead of
/// pre-calculated estimates. Only updates the cache if the difference between
/// measured and pre-calculated height is at least [minHeightDiff] pixels
/// to avoid small calculation errors.
class ItemWithHeightMeasurement extends StatefulWidget {
  const ItemWithHeightMeasurement({
    required this.index,
    required this.itemKey,
    required this.heightCache,
    required this.child,
    super.key,
    this.minHeightDiff = 1.0,
  });

  /// Index of the item (for cache lookup)
  final int index;

  /// GlobalKey for the item widget to measure
  final GlobalKey? itemKey;

  /// Height cache to update
  final SegmentHeightCache heightCache;

  /// Child widget to wrap
  final Widget child;

  /// Minimum height difference (in pixels) to trigger cache update
  /// Default: 1.0 pixel to avoid small calculation errors
  final double minHeightDiff;

  @override
  State<ItemWithHeightMeasurement> createState() =>
      _ItemWithHeightMeasurementState();
}

class _ItemWithHeightMeasurementState extends State<ItemWithHeightMeasurement> {
  double? _lastMeasuredHeight;

  @override
  void didUpdateWidget(ItemWithHeightMeasurement oldWidget) {
    super.didUpdateWidget(oldWidget);
    // Reset last measured height if index or key changed
    if (oldWidget.index != widget.index ||
        oldWidget.itemKey != widget.itemKey) {
      _lastMeasuredHeight = null;
    }
    // Also reset if child changed (e.g., edit mode switch)
    // This ensures height is remeasured when content changes
    if (oldWidget.child != widget.child) {
      _lastMeasuredHeight = null;
    }
  }

  void _measureHeight() {
    if (!mounted) return;
    final BuildContext? context = widget.itemKey?.currentContext ?? this.context;
    if (context == null) return;

    final RenderBox? renderBox = context.findRenderObject() as RenderBox?;
    if (renderBox == null || !renderBox.hasSize) return;

    // Measure the entire widget (including separators if any)
    // The height should match what's actually rendered
    final double measuredHeight = renderBox.size.height;

    // If we've measured before, check if height changed significantly
    if (_lastMeasuredHeight != null) {
      final double heightChange = (measuredHeight - _lastMeasuredHeight!).abs();
      // If height changed significantly (e.g., edit mode switch), update cache
      if (heightChange >= widget.minHeightDiff) {
        widget.heightCache.recordMeasuredHeight(widget.index, measuredHeight);
        _lastMeasuredHeight = measuredHeight;
      }
    } else {
      // First measurement
      final double preCalculatedHeight =
          widget.heightCache.getHeight(widget.index);
      final double heightDiff = (measuredHeight - preCalculatedHeight).abs();

      // Only update cache if difference is >= minHeightDiff (avoid small calculation errors)
      if (heightDiff >= widget.minHeightDiff) {
        // Pass predicted height to calculate correction factor
        widget.heightCache.recordMeasuredHeight(
          widget.index,
          measuredHeight,
          predictedHeight: preCalculatedHeight,
        );
      }

      _lastMeasuredHeight = measuredHeight;
    }
  }

  @override
  Widget build(BuildContext context) {
    // Always schedule measurement to detect height changes (e.g., edit mode switch)
    // The _measureHeight method will check if height actually changed before updating cache
    // Use multiple frames to ensure accurate measurement after layout changes
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (!mounted) return;
      _measureHeight();
      // Also measure in next frame to catch delayed layout changes (e.g., edit mode switch)
      WidgetsBinding.instance.addPostFrameCallback((_) {
        if (!mounted) return;
        _measureHeight();
      });
    });

    return widget.child;
  }
}
