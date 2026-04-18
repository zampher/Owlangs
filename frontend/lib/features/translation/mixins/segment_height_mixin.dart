// SPDX-FileCopyrightText: 2025 QinHan
// SPDX-License-Identifier: MPL-2.0

import 'package:flutter/material.dart';

/// Mixin for segment height calculation
mixin SegmentHeightMixin<T extends StatefulWidget> on State<T> {
  Map<int, GlobalKey> get sourceItemKeys;
  Map<int, GlobalKey> get targetItemKeys;
  double? get cachedSourceItemHeight;
  double? get cachedTargetItemHeight;
  set cachedSourceItemHeight(double? value);
  set cachedTargetItemHeight(double? value);

  /// Get or measure the average item height for source items
  double getSourceItemHeight() {
    if (cachedSourceItemHeight != null) {
      return cachedSourceItemHeight!;
    }

    for (var i = 0; i < sourceItemKeys.length; i++) {
      final GlobalKey<State<StatefulWidget>>? key = sourceItemKeys[i];
      if (key != null) {
        final BuildContext? context = key.currentContext;
        if (context != null) {
          final RenderBox? renderBox = context.findRenderObject() as RenderBox?;
          if (renderBox != null && renderBox.hasSize) {
            final double measuredHeight = renderBox.size.height + 8;
            cachedSourceItemHeight = measuredHeight;
            return measuredHeight;
          }
        }
      }
    }

    return 130;
  }

  /// Get or measure the average item height for target items
  double getTargetItemHeight() {
    if (cachedTargetItemHeight != null) {
      return cachedTargetItemHeight!;
    }

    for (var i = 0; i < targetItemKeys.length; i++) {
      final GlobalKey<State<StatefulWidget>>? key = targetItemKeys[i];
      if (key != null) {
        final BuildContext? context = key.currentContext;
        if (context != null) {
          final RenderBox? renderBox = context.findRenderObject() as RenderBox?;
          if (renderBox != null && renderBox.hasSize) {
            final double measuredHeight = renderBox.size.height + 8;
            cachedTargetItemHeight = measuredHeight;
            return measuredHeight;
          }
        }
      }
    }

    return 130;
  }

  /// Check if GlobalKey has valid context
  bool hasValidContext(GlobalKey? itemKey) {
    if (itemKey == null) return false;
    final BuildContext? context = itemKey.currentContext;
    if (context == null) return false;
    final RenderBox? renderBox = context.findRenderObject() as RenderBox?;
    return renderBox != null && renderBox.hasSize;
  }

  /// Find the range of rendered items in the viewport
  ({int minIndex, int maxIndex})? findRenderedItemRange({
    bool isTarget = false,
  }) {
    final Map<int, GlobalKey<State<StatefulWidget>>> itemKeys =
        isTarget ? targetItemKeys : sourceItemKeys;
    int? minIndex;
    int? maxIndex;

    for (var i = 0; i < itemKeys.length; i++) {
      if (hasValidContext(itemKeys[i])) {
        if (minIndex == null || i < minIndex) {
          minIndex = i;
        }
        if (maxIndex == null || i > maxIndex) {
          maxIndex = i;
        }
      }
    }

    if (minIndex != null && maxIndex != null) {
      return (minIndex: minIndex, maxIndex: maxIndex);
    }

    return null;
  }

  /// Calculate the actual average item height based on rendered items
  double? calculateActualItemHeight(
    int minIndex,
    int maxIndex,
    ScrollController controller, {
    bool isTarget = false,
  }) {
    if (maxIndex <= minIndex) return null;

    final Map<int, GlobalKey<State<StatefulWidget>>> itemKeys =
        isTarget ? targetItemKeys : sourceItemKeys;
    final GlobalKey<State<StatefulWidget>>? firstKey = itemKeys[minIndex];
    final GlobalKey<State<StatefulWidget>>? lastKey = itemKeys[maxIndex];

    if (firstKey == null || lastKey == null) return null;

    final BuildContext? firstContext = firstKey.currentContext;
    final BuildContext? lastContext = lastKey.currentContext;

    if (firstContext == null || lastContext == null) return null;

    final RenderBox? firstBox = firstContext.findRenderObject() as RenderBox?;
    final RenderBox? lastBox = lastContext.findRenderObject() as RenderBox?;

    if (firstBox == null ||
        !firstBox.hasSize ||
        lastBox == null ||
        !lastBox.hasSize) {
      return null;
    }

    final Offset firstGlobalTop = firstBox.localToGlobal(Offset.zero);
    final Offset lastGlobalTop = lastBox.localToGlobal(Offset.zero);
    final double distance = (lastGlobalTop.dy - firstGlobalTop.dy).abs();
    final int itemCount = maxIndex - minIndex;

    if (itemCount == 0) return null;

    return distance / itemCount;
  }
}
