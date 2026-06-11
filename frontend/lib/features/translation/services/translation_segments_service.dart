// SPDX-FileCopyrightText: 2025 QinHan
// SPDX-License-Identifier: MPL-2.0

import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../../shared/services/translation_service.dart';
import '../../../shared/services/config_service.dart';
import '../../../shared/utils/app_logger.dart';
import '../../settings/screens/ai_platform_settings.dart';
import '../providers/segment_undo_redo_provider.dart';

/// Service for managing translation segments data and operations
class TranslationSegmentsService {
  TranslationSegmentsService(this.taskId, this.ref);

  final String taskId;
  final WidgetRef ref;

  /// Fetch a page of segments (combines source preview and translation segments)
  Future<Map<String, dynamic>> fetchSegmentsPage(
    int offset,
    int limit,
    Map<int, Map<String, dynamic>> allSegmentsMetadata,
    int totalSegmentsCount,
    Future<void> Function() loadAllSegmentsMetadata,
  ) async {
    final svc = TranslationService();

    // Fetch source segments from source-preview API (paginated)
    final sourcePreview = await svc.getSourcePreview(
      taskId,
      offset: offset,
      limit: limit,
    );

    final totalSegments = sourcePreview['total_segments'] as int? ??
        sourcePreview['total'] as int? ??
        0;

    final sourceItems = sourcePreview['items'] as List<dynamic>? ??
        sourcePreview['segments'] as List<dynamic>? ??
        <dynamic>[];

    // Convert source items to strings and extract segment indices
    final sourceTexts = <String>[];
    final segmentIndices = <int>[];
    var itemsWithoutIndex = 0;

    for (int i = 0; i < sourceItems.length; i++) {
      final dynamic item = sourceItems[i];
      String sourceText;
      int segmentIndex;

      if (item is String) {
        sourceText = item;
        // Fallback: use offset + i if no index available
        segmentIndex = offset + i;
        itemsWithoutIndex++;
      } else if (item is Map) {
        sourceText = (item['source_text'] as String?) ??
            (item['text'] as String?) ??
            item.toString();
        // CRITICAL: Use segment_index from response if available, otherwise fallback to offset + i
        final providedIndex = item['segment_index'] as int?;
        if (providedIndex != null) {
          segmentIndex = providedIndex;
        } else {
          segmentIndex = offset + i;
          itemsWithoutIndex++;
        }
      } else {
        sourceText = item.toString();
        segmentIndex = offset + i;
        itemsWithoutIndex++;
      }

      sourceTexts.add(sourceText);
      segmentIndices.add(segmentIndex);
    }

    // Log warning if many items are missing segment_index
    if (itemsWithoutIndex > 0) {
      AppLogger.log(
        'TranslationSegmentsService',
        '[PAGINATION] WARNING: $itemsWithoutIndex items missing segment_index in page (offset=$offset, limit=$limit)',
        level: LogLevel.warn,
      );
    }

    // Fetch translation segments metadata if not loaded yet
    if (allSegmentsMetadata.isEmpty && totalSegmentsCount == 0) {
      await loadAllSegmentsMetadata();
    }

    // Build segment pairs for this page using actual segment indices from response
    final segmentPairs = <Map<String, dynamic>>[];
    var unmatchedCount = 0;

    for (int i = 0; i < sourceTexts.length; i++) {
      final globalIndex =
          segmentIndices[i]; // Use actual segment_index from response
      final sourceText = sourceTexts[i];
      final metadata = allSegmentsMetadata[globalIndex] ?? <String, dynamic>{};
      final hasMetadata = metadata.isNotEmpty;

      if (!hasMetadata) {
        unmatchedCount++;
      }

      // Determine target text:
      // - If we have metadata for this segment, respect the stored target/modified text.
      //   Empty string is a valid value (e.g. API explicitly returned an empty segment),
      //   and should NOT be replaced by source text.
      // - Only when there is no metadata at all for this segment (API truly didn't return it)
      //   do we fall back to source text.
      String targetText;
      if (hasMetadata) {
        final modified = metadata['modified_text'] as String?;
        final rawTarget = metadata['target_text'] as String?;
        targetText = modified ?? rawTarget ?? '';
      } else {
        targetText =
            sourceText; // Fallback to source if API didn't return this segment
      }

      segmentPairs.add(<String, dynamic>{
        'index': globalIndex,
        'source_text': sourceText,
        'target_text': targetText,
      });
    }

    // Log warning if many segments are unmatched
    if (unmatchedCount > 0) {
      AppLogger.log(
        'TranslationSegmentsService',
        '[PAGINATION] WARNING: $unmatchedCount segments have no metadata in page (offset=$offset, limit=$limit)',
        level: LogLevel.warn,
      );
    }

    return <String, dynamic>{
      'items': segmentPairs,
      'total': totalSegmentsCount > 0 ? totalSegmentsCount : totalSegments,
      'offset': offset,
      'limit': limit,
    };
  }

  /// Load all segments metadata from translation-segments API (one-time load)
  Future<Map<int, Map<String, dynamic>>> loadAllSegmentsMetadata() async {
    try {
      final svc = TranslationService();
      final segmentsData = await svc.getTranslationSegments(taskId);
      final segments = segmentsData['segments'] as List<dynamic>?;

      final metadata = <int, Map<String, dynamic>>{};

      if (segments != null) {
        for (final segment in segments) {
          final index = segment['segment_index'] as int? ?? 0;
          final targetText = segment['modified_text'] as String? ??
              segment['target_text'] as String? ??
              '';

          metadata[index] = <String, dynamic>{
            'target_text': targetText,
            'platform_used': segment['platform_used'] as String?,
            'is_image': segment['is_image'] as bool? ?? false,
            'is_failed': segment['is_failed'] as bool? ?? false,
            'failure_reason': segment['failure_reason'] as String?,
            'needs_retry': segment['needs_retry'] as bool? ?? false,
            'is_excluded': segment['is_excluded'] as bool? ?? false,
            'status': segment['status']
                as String?, // Include status (e.g., "cleared")
            'used_platforms':
                segment['used_platforms'] as List<dynamic>? ?? <dynamic>[],
          };
        }
      } else {
        AppLogger.log(
          'TranslationSegmentsService',
          '[PAGINATION] No segments in response: segments is null',
          level: LogLevel.warn,
        );
      }

      return metadata;
    } catch (e, stackTrace) {
      AppLogger.log(
        'TranslationSegmentsService',
        '[PAGINATION] Failed to load segments metadata: $e\nStack trace: $stackTrace',
        level: LogLevel.error,
      );
      return <int, Map<String, dynamic>>{};
    }
  }

  /// Update translation segment
  Future<void> updateSegment(
    int index,
    String newText, {
    required String oldText,
    required void Function(int, String) onUpdate,
  }) async {
    try {
      final svc = TranslationService();
      await svc.updateTranslationSegment(
        taskId,
        index,
        targetText: newText,
        modifiedBy: 'user', // TODO: Get actual user ID
      );

      onUpdate(index, newText);

      // Record revision in undo/redo history
      final undoRedoNotifier =
          ref.read(translationSegmentsUndoRedoProvider(taskId).notifier);
      undoRedoNotifier.pushRevision(index, newText, oldText: oldText);
    } catch (e) {
      AppLogger.log(
        'TranslationSegmentsService',
        'Failed to update segment: $e',
        level: LogLevel.error,
      );
      rethrow;
    }
  }

  /// Retry translation of a segment with platform rotation
  Future<Map<String, dynamic>> retrySegment(
    int index, {
    required List<String> usedPlatforms,
    required String? currentPlatform,
    required void Function(int, String, List<String>) onSuccess,
    required void Function(int, String?, String?) onFailure,
  }) async {
    // Get available platforms in order
    final aiPlatformSettings = ref.read(aiPlatformSettingsProvider);
    final availablePlatforms =
        aiPlatformSettings.getAvailablePlatformsInOrder();

    if (availablePlatforms.isEmpty) {
      throw Exception('No available AI platforms');
    }

    // Get used platforms for this segment
    final updatedUsedPlatforms = List<String>.from(usedPlatforms);
    if (currentPlatform != null &&
        !updatedUsedPlatforms.contains(currentPlatform)) {
      updatedUsedPlatforms.add(currentPlatform);
    }

    // Select next available platform (rotation algorithm)
    String? selectedPlatform;
    for (final platform in availablePlatforms) {
      if (!updatedUsedPlatforms.contains(platform.key)) {
        selectedPlatform = platform.key;
        break;
      }
    }

    // If all platforms have been used, start from the beginning (excluding the first one)
    if (selectedPlatform == null && availablePlatforms.length > 1) {
      // Skip the first platform (which was likely the original one)
      selectedPlatform = availablePlatforms.length > 1
          ? availablePlatforms[1].key
          : availablePlatforms[0].key;
    } else {
      selectedPlatform ??= availablePlatforms[0].key;
    }

    // Call retranslation API
    final svc = TranslationService();
    final response = await svc.retranslateSegment(
      taskId,
      index,
      platformKey: selectedPlatform,
    );

    // Check if retranslation succeeded
    final success = response['success'] as bool? ?? false;
    final segment = response['segment'] as Map<String, dynamic>?;
    final isFailed = segment?['is_failed'] as bool? ?? false;
    final failureReason = segment?['failure_reason'] as String?;

    if (success && !isFailed) {
      onSuccess(index, selectedPlatform, updatedUsedPlatforms);
    } else {
      onFailure(index, failureReason, selectedPlatform);
    }

    return response;
  }

  /// Mark segment for retry
  Future<void> markForRetry(int index) async {
    final svc = TranslationService();
    await svc.markSegmentForRetry(taskId, index);
  }

  /// Unmark segment for retry
  Future<void> unmarkForRetry(int index) async {
    final svc = TranslationService();
    await svc.unmarkSegmentForRetry(taskId, index);
  }

  /// Exclude segment
  Future<Map<String, dynamic>> excludeSegment(int index) async {
    final svc = TranslationService();
    return svc.excludeSegment(taskId, index);
  }

  /// Unexclude segment
  Future<Map<String, dynamic>> unexcludeSegment(int index) async {
    final svc = TranslationService();
    return svc.unexcludeSegment(taskId, index);
  }

  /// Exclude multiple segments in one API call
  Future<Map<String, dynamic>> excludeSegmentsBatch(List<int> indices) async {
    final svc = TranslationService();
    return svc.excludeSegmentsBatch(taskId, indices);
  }

  /// Unexclude multiple segments in one API call
  Future<Map<String, dynamic>> unexcludeSegmentsBatch(List<int> indices) async {
    final svc = TranslationService();
    return svc.unexcludeSegmentsBatch(taskId, indices);
  }

  /// Clear segment
  Future<void> clearSegment(
    int index, {
    required String oldText,
    required void Function(int) onClear,
  }) async {
    final svc = TranslationService();
    await svc.clearSegment(taskId, index);

    // Record revision in undo/redo history
    final undoRedoNotifier =
        ref.read(translationSegmentsUndoRedoProvider(taskId).notifier);
    undoRedoNotifier.pushRevision(index, '', oldText: oldText);

    onClear(index);
  }

  /// Update only specific segments without reloading all content
  Future<Map<int, Map<String, dynamic>>> updateSegmentsOnly(
    List<int> segmentIndices,
  ) async {
    if (segmentIndices.isEmpty) {
      return <int, Map<String, dynamic>>{};
    }

    try {
      final svc = TranslationService();
      final segmentsData = await svc.getTranslationSegments(taskId);
      final segments = segmentsData['segments'] as List<dynamic>?;

      if (segments == null || segments.isEmpty) {
        return <int, Map<String, dynamic>>{};
      }

      // Create a map of segment_index -> segment for quick lookup
      final segmentMap = <int, Map<String, dynamic>>{};
      for (final segment in segments) {
        final index = segment['segment_index'] as int?;
        if (index != null) {
          segmentMap[index] = segment;
        }
      }

      // Update only the specified segments
      final updatedMetadata = <int, Map<String, dynamic>>{};

      for (final index in segmentIndices) {
        final segment = segmentMap[index];
        if (segment == null) continue;

        // Update target text (even if empty - failed segments should show empty)
        final targetText = segment['modified_text'] as String? ??
            segment['target_text'] as String? ??
            '';

        updatedMetadata[index] = <String, dynamic>{
          'target_text': targetText,
          'platform_used': segment['platform_used'] as String?,
          'is_image': segment['is_image'] as bool? ?? false,
          'is_failed': segment['is_failed'] as bool? ?? false,
          'failure_reason': segment['failure_reason'] as String?,
          'needs_retry': segment['needs_retry'] as bool? ?? false,
          'is_excluded': segment['is_excluded'] as bool? ?? false,
          'status':
              segment['status'] as String?, // Include status (e.g., "cleared")
          'used_platforms': (segment['used_platforms'] as List<dynamic>?)
                  ?.map((e) => e.toString())
                  .toList() ??
              <String>[],
        };
      }

      AppLogger.log(
        'TranslationSegmentsService',
        '[UPDATE_SEGMENTS] Updated ${segmentIndices.length} segments: $segmentIndices',
      );

      return updatedMetadata;
    } catch (e) {
      AppLogger.log(
        'TranslationSegmentsService',
        '[UPDATE_SEGMENTS] Failed to update segments: $e',
        level: LogLevel.error,
      );
      return <int, Map<String, dynamic>>{};
    }
  }
}
