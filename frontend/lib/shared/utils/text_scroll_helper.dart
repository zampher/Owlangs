// SPDX-FileCopyrightText: 2025 QinHan
// SPDX-License-Identifier: MPL-2.0

import 'package:flutter/material.dart';
import 'package:flutter/rendering.dart';

/// Helper class for scrolling to specific text positions
/// Uses the same approach as translation panel: Scrollable.ensureVisible with GlobalKey
class TextScrollHelper {
  /// Ensure a widget is visible in the scrollable viewport using Scrollable.ensureVisible
  /// This is the same method used in translation panel for reliable scrolling
  ///
  /// [context] - BuildContext of the widget to scroll to
  /// [alignment] - Where to position the widget in viewport (0.0 = top, 0.5 = center, 1.0 = bottom)
  /// [duration] - Animation duration
  /// [curve] - Animation curve
  ///
  /// Returns true if scrolling was successful, false otherwise
  static bool ensureVisible({
    required BuildContext? context,
    double alignment = 0.1,
    Duration duration = const Duration(milliseconds: 300),
    Curve curve = Curves.easeInOut,
  }) {
    if (context == null) return false;

    try {
      Scrollable.ensureVisible(
        context,
        duration: duration,
        curve: curve,
        alignment: alignment,
      );
      return true;
    } catch (e) {
      // Widget might not be in a scrollable, or scroll controller not ready
      return false;
    }
  }

  /// Scroll to a specific character position in text using TextPainter calculation
  /// Falls back to ensureVisible if a GlobalKey is provided
  ///
  /// [text] - The full text content
  /// [charPosition] - Character position to scroll to (0-based)
  /// [scrollController] - ScrollController for the scrollable widget
  /// [textStyle] - TextStyle used for rendering the text
  /// [padding] - Padding around the text (default: 16.0)
  /// [alignment] - Where to position the text in viewport (0.0 = top, 0.5 = center, 1.0 = bottom)
  /// [textKey] - Optional GlobalKey for the text widget (preferred method)
  static Future<void> scrollToTextPosition({
    required String text,
    required int charPosition,
    required ScrollController scrollController,
    TextStyle? textStyle,
    double padding = 16.0,
    double alignment = 0.1,
    GlobalKey? textKey,
  }) async {
    // Prefer ensureVisible if GlobalKey is provided (same as translation panel)
    if (textKey != null) {
      final BuildContext? context = textKey.currentContext;
      if (context != null) {
        final bool success = ensureVisible(
          context: context,
          alignment: alignment,
        );
        if (success) return;
      }
    }

    // Fallback to TextPainter calculation
    if (!scrollController.hasClients ||
        charPosition < 0 ||
        charPosition > text.length) {
      return;
    }

    try {
      // Use TextPainter to calculate text position
      final TextStyle style = textStyle ?? const TextStyle(fontSize: 14);
      final TextPainter textPainter = TextPainter(
        text: TextSpan(text: text, style: style),
        textDirection: TextDirection.ltr,
      );

      // Layout the text with a reasonable width (use viewport width if available)
      final double viewportWidth =
          scrollController.position.viewportDimension > 0
              ? scrollController.position.viewportDimension - (padding * 2)
              : 400.0;
      textPainter.layout(maxWidth: viewportWidth);

      // Get the position of the character
      final TextPosition textPosition = TextPosition(offset: charPosition);
      final Offset offset =
          textPainter.getOffsetForCaret(textPosition, Rect.zero);

      // Calculate scroll position
      // offset.dy is the Y position of the character in the text
      // We want to position it at 'alignment' of the viewport (e.g., 0.1 = 10% from top)
      final double viewportHeight = scrollController.position.viewportDimension;
      final double targetScrollOffset =
          offset.dy - (viewportHeight * alignment) + padding;

      // Animate to the calculated position
      await scrollController.animateTo(
        targetScrollOffset.clamp(
          0.0,
          scrollController.position.maxScrollExtent,
        ),
        duration: const Duration(milliseconds: 300),
        curve: Curves.easeInOut,
      );
    } catch (e) {
      // If calculation fails, try a simpler approach based on line estimation
      _scrollToTextPositionFallback(
        text: text,
        charPosition: charPosition,
        scrollController: scrollController,
        textStyle: textStyle,
        padding: padding,
      );
    }
  }

  /// Fallback method using line-based estimation
  static void _scrollToTextPositionFallback({
    required String text,
    required int charPosition,
    required ScrollController scrollController,
    TextStyle? textStyle,
    double padding = 16.0,
  }) {
    if (!scrollController.hasClients) return;

    try {
      final TextStyle style = textStyle ?? const TextStyle(fontSize: 14);
      final double fontSize = style.fontSize ?? 14.0;
      final double lineHeight = fontSize * 1.2; // Approximate line height

      // Estimate line number based on character position
      // This is a rough estimation - assumes average characters per line
      final double viewportWidth =
          scrollController.position.viewportDimension > 0
              ? scrollController.position.viewportDimension - (padding * 2)
              : 400.0;
      final int avgCharsPerLine =
          (viewportWidth / (fontSize * 0.6)).round(); // Rough estimate
      final int estimatedLine = (charPosition / avgCharsPerLine).floor();

      final double targetOffset = estimatedLine * lineHeight;

      scrollController.animateTo(
        targetOffset.clamp(0.0, scrollController.position.maxScrollExtent),
        duration: const Duration(milliseconds: 300),
        curve: Curves.easeInOut,
      );
    } catch (e) {
      // Silently fail if scroll is not possible
    }
  }

  /// Check if a text position is visible in the viewport
  static bool isTextPositionVisible({
    required String text,
    required int charPosition,
    required ScrollController scrollController,
    TextStyle? textStyle,
    double padding = 16.0,
  }) {
    if (!scrollController.hasClients ||
        charPosition < 0 ||
        charPosition > text.length) {
      return false;
    }

    try {
      final TextStyle style = textStyle ?? const TextStyle(fontSize: 14);
      final TextPainter textPainter = TextPainter(
        text: TextSpan(text: text, style: style),
        textDirection: TextDirection.ltr,
      );

      final double viewportWidth =
          scrollController.position.viewportDimension > 0
              ? scrollController.position.viewportDimension - (padding * 2)
              : 400.0;
      textPainter.layout(maxWidth: viewportWidth);

      final TextPosition textPosition = TextPosition(offset: charPosition);
      final Offset offset =
          textPainter.getOffsetForCaret(textPosition, Rect.zero);

      final double scrollOffset = scrollController.offset;
      final double viewportHeight = scrollController.position.viewportDimension;
      final double visibleTop = scrollOffset - padding;
      final double visibleBottom = scrollOffset + viewportHeight - padding;

      return offset.dy >= visibleTop && offset.dy <= visibleBottom;
    } catch (e) {
      return false;
    }
  }

  /// Check if a widget is visible in the viewport (same as translation panel)
  /// Uses ScrollPosition for accurate calculation that accounts for scrollbar
  static bool isWidgetVisible({
    required BuildContext? context,
    required ScrollController scrollController,
  }) {
    if (!scrollController.hasClients || context == null) {
      return false;
    }

    try {
      final RenderBox? renderBox = context.findRenderObject() as RenderBox?;
      if (renderBox == null || !renderBox.hasSize) {
        return false;
      }

      final ScrollableState scrollable = Scrollable.of(context);
      final RenderBox? scrollableRenderBox =
          scrollable.context.findRenderObject() as RenderBox?;
      if (scrollableRenderBox == null) {
        return false;
      }

      // Use ScrollPosition for accurate viewport calculation (accounts for scrollbar)
      final ScrollPosition position = scrollController.position;
      final double viewportHeight = position.viewportDimension;
      final double scrollOffset = position.pixels;

      // Get widget's position relative to scrollable content
      final Offset itemGlobalTop = renderBox.localToGlobal(Offset.zero);
      final Offset scrollableGlobalTop =
          scrollableRenderBox.localToGlobal(Offset.zero);

      // Calculate item's position in the scrollable content coordinate system
      // This accounts for scrollbar and padding
      final double itemRelativeY = itemGlobalTop.dy - scrollableGlobalTop.dy;
      final double itemContentPosition = scrollOffset + itemRelativeY;
      final Size itemSize = renderBox.size;
      final double itemContentBottom = itemContentPosition + itemSize.height;

      // Check if item is within visible viewport range
      // Widget is visible if:
      // - widget's bottom is below the visible area's top (itemContentBottom >= scrollOffset)
      // - widget's top is above the visible area's bottom (itemContentPosition <= scrollOffset + viewportHeight)
      final double visibleTop = scrollOffset;
      final double visibleBottom = scrollOffset + viewportHeight;
      final bool isVisible = itemContentBottom >= visibleTop &&
          itemContentPosition <= visibleBottom;

      return isVisible;
    } catch (e) {
      debugPrint('[TextScrollHelper] isWidgetVisible: Exception - $e');
      return false;
    }
  }

  /// Retry scrolling until widget is visible, up to maxAttempts times (same as translation panel)
  /// This provides correction logic when widget is outside viewport
  /// Enhanced with better handling for widgets at the end of the list
  static Future<void> scrollUntilVisible({
    required GlobalKey? widgetKey,
    required ScrollController scrollController,
    int attempt = 1,
    int maxAttempts = 8,
    double alignment = 0.1,
  }) async {
    if (attempt > maxAttempts || !scrollController.hasClients) {
      return;
    }

    final BuildContext? context = widgetKey?.currentContext;
    final bool hasContext = context != null;

    if (!hasContext) {
      // Widget not rendered yet - wait and retry
      await Future.delayed(const Duration(milliseconds: 200));
      await scrollUntilVisible(
        widgetKey: widgetKey,
        scrollController: scrollController,
        attempt: attempt + 1,
        maxAttempts: maxAttempts,
        alignment: alignment,
      );
      return;
    }

    // Widget is rendered - check current visibility first
    final bool isCurrentlyVisible = isWidgetVisible(
      context: context,
      scrollController: scrollController,
    );

    if (isCurrentlyVisible) {
      return;
    }

    // Try ensureVisible first
    ensureVisible(
      context: context,
      alignment: alignment,
    );

    // Wait for animation to complete
    await Future.delayed(const Duration(milliseconds: 400));

    if (!scrollController.hasClients) {
      return;
    }

    // Check if widget is now visible after scrolling
    final bool isVisible = isWidgetVisible(
      context: context,
      scrollController: scrollController,
    );

    if (isVisible) {
      return;
    }

    // Widget is still not visible, but check one more time after a short delay
    // Sometimes the widget position updates after the animation completes
    await Future.delayed(const Duration(milliseconds: 100));

    if (!scrollController.hasClients) {
      return;
    }

    final bool isVisibleAfterDelay = isWidgetVisible(
      context: context,
      scrollController: scrollController,
    );

    if (isVisibleAfterDelay) {
      return;
    }

    // Not visible yet, retry with next attempt
    if (attempt < maxAttempts) {
      // Enhanced correction logic
      if (hasContext) {
        try {
          final RenderBox? renderBox = context.findRenderObject() as RenderBox?;
          if (renderBox != null && renderBox.hasSize) {
            final ScrollableState scrollable = Scrollable.of(context);
            final RenderBox? scrollableRenderBox =
                scrollable.context.findRenderObject() as RenderBox?;
            if (scrollableRenderBox != null) {
              final Offset itemGlobalTop = renderBox.localToGlobal(Offset.zero);
              final Offset itemGlobalBottom =
                  itemGlobalTop + Offset(0, renderBox.size.height);
              final Offset scrollableGlobalTop =
                  scrollableRenderBox.localToGlobal(Offset.zero);
              final Offset scrollableGlobalBottom = scrollableGlobalTop +
                  Offset(0, scrollController.position.viewportDimension);

              final double viewportHeight =
                  scrollController.position.viewportDimension;
              final double targetOffset = viewportHeight * alignment;
              final double currentScroll = scrollController.offset;

              // Determine if widget is above or below viewport
              final bool isAboveViewport =
                  itemGlobalBottom.dy < scrollableGlobalTop.dy;
              final bool isBelowViewport =
                  itemGlobalTop.dy > scrollableGlobalBottom.dy;

              double targetScroll;

              if (isAboveViewport) {
                // Widget is above viewport - need to scroll up
                final double itemRelativeY =
                    itemGlobalTop.dy - scrollableGlobalTop.dy;
                targetScroll = currentScroll + itemRelativeY - targetOffset;
              } else if (isBelowViewport) {
                // Widget is below viewport - need to scroll down
                // For items at the end, we need to ensure they're fully visible
                final double itemRelativeY =
                    itemGlobalTop.dy - scrollableGlobalTop.dy;
                // Add extra margin to ensure full visibility, especially for last items
                final double extraMargin =
                    viewportHeight * 0.05; // 5% extra margin
                targetScroll =
                    currentScroll + itemRelativeY - targetOffset - extraMargin;
              } else {
                // Widget is partially visible - calculate precise position
                final double itemRelativeY =
                    itemGlobalTop.dy - scrollableGlobalTop.dy;
                targetScroll = currentScroll + itemRelativeY - targetOffset;
              }

              final double clampedScroll = targetScroll.clamp(
                0.0,
                scrollController.position.maxScrollExtent,
              );
              final double scrollDiff = (clampedScroll - currentScroll).abs();

              if (scrollDiff > 1.0) {
                // Use jumpTo for more precise positioning on later attempts
                if (attempt >= maxAttempts - 2) {
                  // Last few attempts: use jumpTo for immediate positioning
                  scrollController.jumpTo(clampedScroll);
                  await Future.delayed(const Duration(milliseconds: 100));
                } else {
                  // Earlier attempts: use animateTo with slight overshoot
                  final double adjustment = (clampedScroll - currentScroll) *
                      1.15; // More aggressive overshoot
                  await scrollController.animateTo(
                    (currentScroll + adjustment)
                        .clamp(0.0, scrollController.position.maxScrollExtent),
                    duration: const Duration(milliseconds: 250),
                    curve: Curves.easeInOut,
                  );
                  await Future.delayed(const Duration(milliseconds: 300));
                }
              }
            }
          }
        } catch (e) {
          // Ignore errors and continue with retry
          debugPrint(
            '[TextScrollHelper] scrollUntilVisible: Exception in correction logic - $e',
          );
        }
      }

      // Recursively retry
      await scrollUntilVisible(
        widgetKey: widgetKey,
        scrollController: scrollController,
        attempt: attempt + 1,
        maxAttempts: maxAttempts,
        alignment: alignment,
      );
    } else {
      debugPrint(
        '[TextScrollHelper] scrollUntilVisible: Max attempts reached (attempt=$attempt, maxAttempts=$maxAttempts), giving up',
      );
    }
  }
}
