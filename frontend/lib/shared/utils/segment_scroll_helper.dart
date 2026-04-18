// SPDX-FileCopyrightText: 2025 QinHan
// SPDX-License-Identifier: MPL-2.0

import 'package:flutter/material.dart';
import 'text_scroll_helper.dart';

/// Helper class for scrolling to specific segment indices
/// Supports both index-based and GlobalKey-based scrolling with retry mechanism
/// Used in both translation and anonymize panels
class SegmentScrollHelper {
  /// Scroll to segment using GlobalKey with retry mechanism (preferred method)
  /// This is more reliable than index-based scrolling
  ///
  /// [segmentKey] - GlobalKey for the segment widget
  /// [scrollController] - ScrollController for the scrollable widget
  /// [maxAttempts] - Maximum number of retry attempts (default: 8)
  /// [alignment] - Where to position the segment in viewport (0.0 = top, 0.5 = center, 1.0 = bottom)
  static Future<void> scrollToSegmentByKey({
    required GlobalKey? segmentKey,
    required ScrollController scrollController,
    int maxAttempts = 8,
    double alignment = 0.1,
  }) async {
    if (segmentKey == null || !scrollController.hasClients) {
      return;
    }

    final context = segmentKey.currentContext;
    if (context == null) {
      return; // Widget not rendered, cannot scroll using GlobalKey
    }

    // Use TextScrollHelper.isWidgetVisible for consistent visibility checking
    // This uses the same logic as TextScrollHelper.scrollUntilVisible
    final isVisible = TextScrollHelper.isWidgetVisible(
      context: context,
      scrollController: scrollController,
    );

    if (isVisible) {
      return; // Widget is already visible, no need to scroll
    }

    // Use TextScrollHelper's scrollUntilVisible which has retry mechanism
    await TextScrollHelper.scrollUntilVisible(
      widgetKey: segmentKey,
      scrollController: scrollController,
      maxAttempts: maxAttempts,
      alignment: alignment,
    );
  }

  /// Scroll to segment using index-based calculation (fallback method)
  /// Less reliable than GlobalKey-based scrolling, but works when keys are not available
  ///
  /// [index] - Segment index (0-based)
  /// [scrollController] - ScrollController for the scrollable widget
  /// [itemHeight] - Estimated height of each segment item (default: 120.0)
  /// [listPadding] - Padding of the list (default: 0.0, translation panel uses 8.0)
  /// [maxAttempts] - Maximum number of retry attempts (default: 3)
  /// [alignment] - Where to position the segment in viewport (0.0 = top, 0.5 = center, 1.0 = bottom)
  /// [segmentKey] - Optional GlobalKey to get actual widget height for better accuracy
  static Future<void> scrollToSegmentByIndex({
    required int index,
    required ScrollController scrollController,
    double itemHeight = 120.0,
    double listPadding = 0.0,
    int maxAttempts = 3,
    double alignment = 0.1,
    GlobalKey? segmentKey,
  }) async {
    if (!scrollController.hasClients || index < 0) {
      return;
    }

    // Simplified index-based scrolling: just get widget roughly into viewport
    // Don't try to be too precise - that's what GlobalKey-based scrolling is for
    final position = scrollController.position;
    final viewportHeight = position.viewportDimension;
    final targetOffset = viewportHeight * alignment;

    // Simple calculation: assume all items have the same height
    // This is just to get the widget into the viewport, not for precise positioning
    final itemTop = index * itemHeight + listPadding;
    final scrollOffset = itemTop - targetOffset;
    final clampedOffset = scrollOffset.clamp(0.0, position.maxScrollExtent);

    // Use a single smooth scroll to get widget into viewport
    await scrollController.animateTo(
      clampedOffset,
      duration: const Duration(milliseconds: 300),
      curve: Curves.easeInOut,
    );

    // Wait for scroll animation to complete
    await Future.delayed(const Duration(milliseconds: 350));
  }

  /// Scroll to segment using either GlobalKey (preferred) or index (fallback)
  /// This is the main method that should be used
  ///
  /// [segmentKey] - GlobalKey for the segment widget (preferred)
  /// [index] - Segment index (fallback if key is null)
  /// [scrollController] - ScrollController for the scrollable widget
  /// [itemHeight] - Estimated height of each segment item (for index-based scrolling)
  /// [sourceItemHeight] - Height for source items (for translation panel with different heights)
  /// [targetItemHeight] - Height for target items (for translation panel with different heights)
  /// [isTargetScroll] - Whether scrolling target list (uses targetItemHeight if provided)
  /// [listPadding] - Padding of the list (default: 0.0, translation panel uses 8.0)
  /// [maxAttempts] - Maximum number of retry attempts
  /// [alignment] - Where to position the segment in viewport
  static Future<void> scrollToSegment({
    required ScrollController scrollController,
    GlobalKey? segmentKey,
    int? index,
    double itemHeight = 120.0,
    double? sourceItemHeight,
    double? targetItemHeight,
    bool isTargetScroll = false,
    double listPadding = 0.0,
    int maxAttempts = 8,
    double alignment = 0.1,
  }) async {
    // Prefer GlobalKey-based scrolling (more reliable), but only if context is available
    if (segmentKey != null) {
      final context = segmentKey.currentContext;
      if (context != null) {
        await scrollToSegmentByKey(
          segmentKey: segmentKey,
          scrollController: scrollController,
          maxAttempts: maxAttempts,
          alignment: alignment,
        );
        return;
      }
    }

    // Fallback to index-based scrolling (when GlobalKey is null or context is not available)
    if (index != null) {
      // Use different heights for source/target if provided (for translation panel)
      final effectiveHeight = isTargetScroll
          ? (targetItemHeight ?? sourceItemHeight ?? itemHeight)
          : (sourceItemHeight ?? itemHeight);

      // First, do a quick index-based scroll to get widget into viewport
      await scrollToSegmentByIndex(
        index: index,
        scrollController: scrollController,
        itemHeight: effectiveHeight,
        listPadding: listPadding,
        maxAttempts: 2, // Reduced attempts - just get it roughly in view
        alignment: alignment,
        segmentKey: segmentKey,
      );

      // Immediately check if widget is now rendered and switch to GlobalKey-based scrolling
      if (segmentKey != null) {
        // Wait a bit for widget to render, but check multiple times
        for (int checkAttempt = 0; checkAttempt < 5; checkAttempt++) {
          await Future.delayed(const Duration(milliseconds: 100));
          final context = segmentKey.currentContext;
          if (context != null) {
            // Check if widget is already visible before attempting to scroll
            final isVisible = TextScrollHelper.isWidgetVisible(
              context: context,
              scrollController: scrollController,
            );

            if (isVisible) {
              return; // Widget is now visible, no need to scroll
            }

            // Widget is rendered but not visible, use GlobalKey-based scrolling for fine-tuning
            await scrollToSegmentByKey(
              segmentKey: segmentKey,
              scrollController: scrollController,
              maxAttempts:
                  5, // More attempts for GlobalKey-based (more reliable)
              alignment: alignment,
            );
            return;
          }
        }
      }
    }
  }
}
