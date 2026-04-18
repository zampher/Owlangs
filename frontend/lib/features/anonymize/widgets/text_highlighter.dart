// SPDX-FileCopyrightText: 2025 QinHan
// SPDX-License-Identifier: MPL-2.0

import 'package:flutter/material.dart';
import 'package:flutter/foundation.dart' show debugPrint;

/// Helper class for highlighting text in anonymized result view
class TextHighlighter {
  /// Build highlightable text widget with support for GlobalKey
  /// If highlightText is provided, highlights all occurrences of that text
  /// Otherwise, uses highlightStart and highlightEnd for single position highlighting
  static Widget buildHighlightableText({
    required String text,
    int? highlightStart,
    int? highlightEnd,
    String? highlightText,
    GlobalKey? highlightKey,
  }) {
    // Debug: Log the text being built
    debugPrint(
      '[TextHighlighter] buildHighlightableText: text.len=${text.length}, highlightText=$highlightText, highlightStart=$highlightStart, highlightEnd=$highlightEnd',
    );

    // Ensure text is not empty
    if (text.isEmpty) {
      debugPrint(
        '[TextHighlighter] buildHighlightableText: Text is empty, returning empty SelectableText',
      );
      return const SelectableText('', style: TextStyle(fontSize: 14));
    }

    // If highlightText is provided, highlight all occurrences
    if (highlightText != null && highlightText.isNotEmpty) {
      debugPrint(
        '[TextHighlighter] buildHighlightableText: Using multi-highlight mode',
      );
      return _buildMultiHighlightText(
        text: text,
        highlightText: highlightText,
        highlightKey: highlightKey,
      );
    }

    // Otherwise, use single position highlighting
    if (highlightStart == null ||
        highlightEnd == null ||
        highlightStart < 0 ||
        highlightEnd > text.length) {
      debugPrint(
        '[TextHighlighter] buildHighlightableText: Using simple SelectableText (no highlighting)',
      );
      return SelectableText(text, style: const TextStyle(fontSize: 14));
    }

    final String before = text.substring(0, highlightStart);
    final String highlighted = text.substring(highlightStart, highlightEnd);
    final String after = text.substring(highlightEnd);

    // Use WidgetSpan with key for scrolling support, but with same highlight style as Segment mode
    return SelectableText.rich(
      TextSpan(
        children: <InlineSpan>[
          TextSpan(text: before, style: const TextStyle(fontSize: 14)),
          WidgetSpan(
            alignment: PlaceholderAlignment.baseline,
            baseline: TextBaseline.alphabetic,
            child: Container(
              key: highlightKey,
              decoration: BoxDecoration(
                color: Colors.yellow.withOpacity(0.5),
              ),
              padding: EdgeInsets.zero,
              child: Text(
                highlighted,
                style: const TextStyle(
                  fontSize: 14,
                  fontWeight: FontWeight.bold,
                ),
              ),
            ),
          ),
          TextSpan(text: after, style: const TextStyle(fontSize: 14)),
        ],
      ),
    );
  }

  /// Build text widget with all occurrences of highlightText highlighted
  static Widget _buildMultiHighlightText({
    required String text,
    required String highlightText,
    GlobalKey? highlightKey,
  }) {
    final List<TextSpan> spans = <TextSpan>[];
    var lastIndex = 0;
    var occurrenceIndex = 0;

    while (true) {
      final int index = text.indexOf(highlightText, lastIndex);
      if (index == -1) break;

      // Add text before highlight
      if (index > lastIndex) {
        spans.add(
          TextSpan(
            text: text.substring(lastIndex, index),
            style: const TextStyle(fontSize: 14),
          ),
        );
      }

      // Add highlighted text (use WidgetSpan with key only for first occurrence for scrolling)
      final int highlightEnd = index + highlightText.length;
      final bool isFirstOccurrence = occurrenceIndex == 0;
      final String highlightedText = text.substring(index, highlightEnd);

      if (isFirstOccurrence && highlightKey != null) {
        // Use WidgetSpan for first occurrence to support scrolling with GlobalKey
        spans.add(
          TextSpan(
            children: <InlineSpan>[
              WidgetSpan(
                alignment: PlaceholderAlignment.baseline,
                baseline: TextBaseline.alphabetic,
                child: Container(
                  key: highlightKey,
                  decoration: BoxDecoration(
                    color: Colors.yellow.withOpacity(0.5),
                  ),
                  padding: EdgeInsets.zero,
                  child: Text(
                    highlightedText,
                    style: const TextStyle(
                      fontSize: 14,
                      fontWeight: FontWeight.bold,
                    ),
                  ),
                ),
              ),
            ],
          ),
        );
      } else {
        // Use TextSpan for other occurrences (same style as Segment mode)
        spans.add(
          TextSpan(
            text: highlightedText,
            style: TextStyle(
              fontSize: 14,
              fontWeight: FontWeight.bold,
              backgroundColor: Colors.yellow.withOpacity(0.5),
            ),
          ),
        );
      }

      lastIndex = highlightEnd;
      occurrenceIndex++;
    }

    // Add remaining text
    if (lastIndex < text.length) {
      spans.add(
        TextSpan(
          text: text.substring(lastIndex),
          style: const TextStyle(fontSize: 14),
        ),
      );
    }

    return SelectableText.rich(TextSpan(children: spans));
  }

  /// Find the position of replacement in anonymized text based on original position
  /// This calculates the position by tracking all replacements before the target entity
  static int? findReplacementPosition({
    required String originalText,
    required String anonymizedText,
    required int originalStart,
    required int originalEnd,
    required List<dynamic> entities,
    required int highlightedEntityIndex,
  }) {
    if (highlightedEntityIndex < 0 ||
        highlightedEntityIndex >= entities.length) {
      return null;
    }

    final Map<String, dynamic>? highlightedEntity =
        entities[highlightedEntityIndex] as Map<String, dynamic>?;
    if (highlightedEntity == null) {
      return null;
    }

    final String? placeholder = highlightedEntity['placeholder'] as String?;
    if (placeholder == null || placeholder.isEmpty) {
      return null;
    }

    // Sort all entities by start position (ascending) to calculate cumulative offset
    final List<Map<String, dynamic>> sortedEntities =
        List<Map<String, dynamic>>.from(entities)
          ..sort((Map<String, dynamic> a, Map<String, dynamic> b) {
            final int startA = (a['start'] as int?) ?? 0;
            final int startB = (b['start'] as int?) ?? 0;
            return startA.compareTo(startB); // Ascending order
          });

    // Calculate cumulative offset up to the target entity
    var offset = 0;
    for (final Map<String, dynamic> entity in sortedEntities) {
      final int entityStart = (entity['start'] as int?) ?? 0;
      final int entityEnd = (entity['end'] as int?) ?? entityStart;

      // Stop when we reach or pass the target entity
      if (entityStart >= originalStart) {
        break;
      }

      // Calculate offset from this replacement
      final String entityPlaceholder = (entity['placeholder'] as String?) ?? '';

      if (entityPlaceholder.isNotEmpty) {
        final int originalLength = entityEnd - entityStart;
        final int replacementLength = entityPlaceholder.length;
        offset += replacementLength - originalLength;
      }
    }

    // Calculate position in anonymized text
    final int anonymizedStart = originalStart + offset;

    // Verify the position is valid and contains the placeholder
    if (anonymizedStart >= 0 && anonymizedStart < anonymizedText.length) {
      final int expectedEnd = anonymizedStart + placeholder.length;
      if (expectedEnd <= anonymizedText.length) {
        final String actualPlaceholder =
            anonymizedText.substring(anonymizedStart, expectedEnd);
        if (actualPlaceholder == placeholder) {
          return anonymizedStart;
        }
      }
    }

    // Fallback: try to find placeholder near the calculated position
    const int searchWindow = 100;
    final int searchStart =
        (anonymizedStart - searchWindow).clamp(0, anonymizedText.length);
    final int searchEnd = (anonymizedStart + searchWindow + placeholder.length)
        .clamp(0, anonymizedText.length);
    final String searchText = anonymizedText.substring(searchStart, searchEnd);
    final int relativePos = searchText.indexOf(placeholder);

    if (relativePos >= 0) {
      return searchStart + relativePos;
    }

    // Final fallback: search in the entire text
    final int globalPos = anonymizedText.indexOf(placeholder);
    if (globalPos >= 0) {
      return globalPos;
    }

    return null;
  }
}
