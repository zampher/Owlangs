// SPDX-FileCopyrightText: 2025 QinHan
// SPDX-License-Identifier: MPL-2.0

import 'package:flutter/material.dart';
import 'package:flutter/rendering.dart';

/// Height calculator for segment items
/// Pre-calculates actual heights of all items without rendering them
/// This ensures stable maxScrollExtent and prevents scrollbar jitter
class SegmentHeightCalculator {
  SegmentHeightCalculator({
    required this.availableWidth,
    this.fontSize = 14.0,
    this.imageDataMap,
  });

  final double availableWidth;
  final double fontSize;
  final Map<String, Map<String, String>>? imageDataMap;

  /// Calculate height for a single segment item
  /// This calculates the actual height including:
  /// - Badge height
  /// - Text content height (using TextPainter)
  /// - Image heights (if any)
  /// - Padding and margins
  double calculateItemHeight(String text, {bool isExcluded = false}) {
    // Badge width: ~30-40px (padding 4*2 + text width varies by index)
    // Exclude badge width: ~80px (padding 4*2 + icon 12 + text "Excluded" + spacing)
    // Spacing: 4px between badge and content (reduced from 12px)
    // Padding: 2px vertical, 2px horizontal (Container padding, further reduced from 4px)
    // Badge padding: horizontal 4px, vertical 2px (reduced from 8px/4px)
    // Note: availableWidth already accounts for Card padding (12*2) and Container padding (2*2)
    const badgeWidth = 40; // Badge padding horizontal 4*2 = 8px + text width
    const excludeBadgeWidth =
        80; // Badge padding horizontal 4*2 = 8px + icon + text + spacing
    const spacing = 4; // Spacing between badge and content
    const verticalPadding =
        2.0 * 2; // top + bottom, further reduced from 4.0 * 2 to 2.0 * 2
    const badgeHeight =
        20; // Badge padding vertical 2*2 = 4px + text height (~16px)
    // NOTE: separatorHeight (Divider) is NOT included in itemHeight
    // It's added separately in _FixedHeightSliverChildDelegate.estimateMaxScrollOffset

    // Calculate available width for text content
    // availableWidth is the width of the Expanded widget (after Card and Container padding)
    // We need to subtract badge width and spacing
    var textWidth = availableWidth - badgeWidth - spacing;

    if (isExcluded) {
      textWidth -= excludeBadgeWidth + spacing;
    }

    // Ensure minimum width (should not happen, but safety check)
    textWidth = textWidth.clamp(100.0, availableWidth);

    // Calculate text height using TextPainter
    final textStyle = TextStyle(
      fontSize: fontSize,
      height: 1.35, // Line height
    );

    final textPainter = TextPainter(
      textDirection: TextDirection.ltr,
      textAlign: TextAlign.left,
    );

    // Check if text contains images
    final RegExp phPattern = RegExp('<ph-([a-zA-Z0-9]+)>');
    final RegExp base64ImagePattern =
        RegExp(r'data:image/[^;]+;base64,[^\s)]+');
    final RegExp filenameImagePattern =
        RegExp(r'!\[([^\]]*)\]\(([^)]+\.(jpg|jpeg|png|gif|webp))\)');

    final bool hasPlaceholders = phPattern.hasMatch(text);
    final bool hasBase64Images = base64ImagePattern.hasMatch(text);
    final bool hasFilenameImages = filenameImagePattern.hasMatch(text);
    final bool hasImages =
        hasPlaceholders || hasBase64Images || hasFilenameImages;

    double totalHeight = 0;

    if (hasImages && imageDataMap != null && imageDataMap!.isNotEmpty) {
      // For text with images, we need to calculate height more carefully
      // Split text by image placeholders and calculate each part
      final List<String> parts = <String>[];
      final Iterable<RegExpMatch> matches = phPattern.allMatches(text);
      var lastEnd = 0;

      for (final RegExpMatch match in matches) {
        if (match.start > lastEnd) {
          parts.add(text.substring(lastEnd, match.start));
        }
        parts.add(match.group(0)!); // Placeholder
        lastEnd = match.end;
      }
      if (lastEnd < text.length) {
        parts.add(text.substring(lastEnd));
      }

      // Calculate height for each part
      for (final String part in parts) {
        if (phPattern.hasMatch(part)) {
          // This is an image placeholder
          final String? placeholderId = phPattern.firstMatch(part)?.group(1);
          if (placeholderId != null &&
              imageDataMap!.containsKey(placeholderId)) {
            final Map<String, String> imageData = imageDataMap![placeholderId]!;
            final String? imageDataUri = imageData['data'];
            if (imageDataUri != null &&
                imageDataUri.startsWith('data:image/')) {
              // For base64 images, use a reasonable estimate for image height
              // In a production system, you might want to decode the image
              // to get actual dimensions, but that's expensive
              const imageMaxHeight = 400;
              // Estimate: assume images are roughly square or landscape
              // Use maxHeight as a conservative estimate
              totalHeight += imageMaxHeight.clamp(100.0, 400.0);
            } else {
              totalHeight += 200.0; // Default image height
            }
          } else {
            totalHeight += 200.0; // Default image height if not found
          }
        } else if (part.isNotEmpty) {
          // This is text, calculate its height
          textPainter.text = TextSpan(
            text: part,
            style: textStyle,
          );
          textPainter.layout(maxWidth: textWidth);
          totalHeight += textPainter.size.height;
        }
      }
    } else {
      // Simple text without images
      textPainter.text = TextSpan(
        text: text,
        style: textStyle,
      );
      textPainter.layout(maxWidth: textWidth);
      totalHeight = textPainter.size.height;
    }

    // Add badge height (badge is in a Row, so use max of badge and content)
    final contentHeight = totalHeight;
    final rowHeight = badgeHeight.toDouble() > contentHeight
        ? badgeHeight.toDouble()
        : contentHeight;

    // Add vertical padding
    final double itemHeight = rowHeight + verticalPadding;

    // NOTE: separatorHeight (Divider) is NOT included here because:
    // 1. In SliverList, each item includes its own Divider in the Column
    // 2. The last item doesn't have a Divider after it
    // 3. _FixedHeightSliverChildDelegate adds separatorHeight for all items (including last)
    // So we return itemHeight only, and let the delegate handle separatorHeight
    return itemHeight;
  }

  /// Pre-calculate heights for all segments
  /// Returns a map of index -> height
  Map<int, double> calculateAllHeights(
    List<String> segments,
    Set<int> excludedIndices,
  ) {
    final Map<int, double> heights = <int, double>{};

    for (var i = 0; i < segments.length; i++) {
      final bool isExcluded = excludedIndices.contains(i);
      final double height =
          calculateItemHeight(segments[i], isExcluded: isExcluded);
      heights[i] = height;
    }

    return heights;
  }
}
