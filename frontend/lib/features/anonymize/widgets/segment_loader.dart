// SPDX-FileCopyrightText: 2025 QinHan
// SPDX-License-Identifier: MPL-2.0

import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../../shared/services/translation_service.dart';

/// Helper class for loading and processing segments
class SegmentLoader {
  /// Load segments from translation service
  static Future<SegmentLoadResult> loadSegments({
    required String? flowId,
    required String? taskId,
    required List<dynamic> entities,
    required WidgetRef ref,
  }) async {
    if (flowId == null || taskId == null || taskId.isEmpty) {
      return SegmentLoadResult(
        originalSegments: <String>[],
        anonymizedSegments: <String>[],
        segmentBoundaries: <int>[],
      );
    }

    try {
      final TranslationService svc = TranslationService();
      final Map<String, dynamic> preview =
          await svc.getSourcePreview(taskId, limit: 500);
      final Map<String, dynamic> status = await svc.getStatus(taskId);

      final List<String> segs =
          (preview['segments'] as List<dynamic>? ?? <dynamic>[])
              .map((e) => e.toString())
              .toList();

      final Map<String, dynamic>? meta =
          status['segments_metadata'] as Map<String, dynamic>?;
      final List<String> seps =
          (meta != null && meta['separators_after'] is List)
              ? (meta['separators_after'] as List)
                  .map((e) => e?.toString() ?? '\n\n')
                  .toList()
              : List.generate(segs.length, (_) => '\n\n');

      // Calculate segment boundaries
      final List<int> segmentBoundaries = <int>[];
      var currentPos = 0;
      for (var i = 0; i < segs.length; i++) {
        segmentBoundaries.add(currentPos);
        currentPos += segs[i].length;
        if (i < seps.length) {
          currentPos += seps[i].length;
        }
      }
      segmentBoundaries.add(currentPos);

      // Generate anonymized segments
      final List<String> anonymizedSegments = _generateAnonymizedSegments(
        originalSegments: segs,
        entities: entities,
      );

      return SegmentLoadResult(
        originalSegments: segs,
        anonymizedSegments: anonymizedSegments,
        segmentBoundaries: segmentBoundaries,
      );
    } catch (e) {
      return SegmentLoadResult(
        originalSegments: <String>[],
        anonymizedSegments: <String>[],
        segmentBoundaries: <int>[],
      );
    }
  }

  /// Split text into segments as fallback
  static SegmentLoadResult splitTextIntoSegments({
    required String originalText,
    required List<dynamic> entities,
  }) {
    final List<String> originalParts = originalText.split(RegExp(r'\n\n+'));
    final List<String> originalSegments =
        originalParts.where((String s) => s.trim().isNotEmpty).toList();

    // Calculate segment boundaries
    final List<int> segmentBoundaries = <int>[];
    var currentPos = 0;
    for (var i = 0; i < originalSegments.length; i++) {
      segmentBoundaries.add(currentPos);
      currentPos += originalSegments[i].length;
      if (i < originalSegments.length - 1) {
        currentPos += 2; // Approximate separator length (double newline)
      }
    }
    segmentBoundaries.add(currentPos);

    // Generate anonymized segments
    final List<String> anonymizedSegments = _generateAnonymizedSegments(
      originalSegments: originalSegments,
      entities: entities,
    );

    return SegmentLoadResult(
      originalSegments: originalSegments,
      anonymizedSegments: anonymizedSegments,
      segmentBoundaries: segmentBoundaries,
    );
  }

  /// Generate anonymized segments using text-based matching
  static List<String> _generateAnonymizedSegments({
    required List<String> originalSegments,
    required List<dynamic> entities,
  }) {
    // Build a map of entity text -> placeholder for quick lookup
    final Map<String, String> entityTextToPlaceholder = <String, String>{};
    for (final entity in entities) {
      final Map<String, dynamic>? entityMap = entity as Map<String, dynamic>?;
      final String entityText = entityMap?['text']?.toString() ?? '';
      final String placeholder = entityMap?['placeholder']?.toString() ?? '';
      if (entityText.isNotEmpty && placeholder.isNotEmpty) {
        entityTextToPlaceholder[entityText] = placeholder;
      }
    }

    final List<String> anonymizedSegments = <String>[];
    for (var i = 0; i < originalSegments.length; i++) {
      var segmentText = originalSegments[i];

      // Find all entities that appear in this segment
      final List<Map<String, dynamic>> segmentReplacements =
          <Map<String, dynamic>>[];
      for (final String entityText in entityTextToPlaceholder.keys) {
        if (segmentText.contains(entityText)) {
          var searchStart = 0;
          while (true) {
            final int index = segmentText.indexOf(entityText, searchStart);
            if (index == -1) break;

            segmentReplacements.add(<String, dynamic>{
              'text': entityText,
              'placeholder': entityTextToPlaceholder[entityText],
              'start': index,
              'end': index + entityText.length,
              'length': entityText.length,
            });

            searchStart = index + 1;
          }
        }
      }

      // Sort replacements by length (descending) first, then by position (descending)
      segmentReplacements
          .sort((Map<String, dynamic> a, Map<String, dynamic> b) {
        final int lengthA = (a['length'] as int?) ?? 0;
        final int lengthB = (b['length'] as int?) ?? 0;
        if (lengthA != lengthB) {
          return lengthB.compareTo(lengthA); // Longer first
        }
        final int startA = (a['start'] as int?) ?? 0;
        final int startB = (b['start'] as int?) ?? 0;
        return startB.compareTo(startA);
      });

      // Apply replacements from end to start
      var anonymizedSegment = segmentText;
      for (final Map<String, dynamic> replacement in segmentReplacements) {
        final int start = (replacement['start'] as int?) ?? 0;
        final int end =
            (replacement['end'] as int?) ?? anonymizedSegment.length;
        final String placeholder = replacement['placeholder']?.toString() ?? '';

        if (start >= 0 &&
            end > start &&
            end <= anonymizedSegment.length &&
            placeholder.isNotEmpty) {
          final String currentText = anonymizedSegment.substring(start, end);
          final String expectedText = replacement['text']?.toString() ?? '';
          if (currentText == expectedText) {
            anonymizedSegment = anonymizedSegment.substring(0, start) +
                placeholder +
                anonymizedSegment.substring(end);
          }
        }
      }

      anonymizedSegments.add(anonymizedSegment);
    }

    return anonymizedSegments;
  }
}

/// Result of segment loading
class SegmentLoadResult {
  SegmentLoadResult({
    required this.originalSegments,
    required this.anonymizedSegments,
    required this.segmentBoundaries,
  });
  final List<String> originalSegments;
  final List<String> anonymizedSegments;
  final List<int> segmentBoundaries;
}
