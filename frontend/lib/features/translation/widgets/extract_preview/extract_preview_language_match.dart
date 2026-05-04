import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../../../shared/services/translation_service.dart';
import '../../../../shared/utils/app_logger.dart';
import '../../../../shared/utils/message_service.dart';
import '../../../../shared/config/pagination_config.dart';
import '../../../../shared/providers/settings_provider.dart';
import '../../models/exclusion_reason.dart';
import '../../providers/chunk_tokens_provider.dart';
import '../../providers/excluded_segments_provider.dart';
import '../extract_preview.dart';
import 'extract_preview_state.dart';

/// Mixin for language match handling in ExtractPreview
///
/// This mixin provides methods for:
/// - Validating and refreshing exclusions for target language changes
/// - Checking language exclusion state
/// - Setting total tokens
///
/// **Note**: These methods handle language-based exclusion detection and updates.
mixin ExtractPreviewLanguageMatchMixin<T extends ConsumerStatefulWidget>
    on ConsumerState<T>, ExtractPreviewStateMixin<T> {
  // ============================================================================
  // Required Methods (inherited from State class)
  // ============================================================================

  // Note: The following are available from ConsumerState<T>:
  // - BuildContext get context
  // - T get widget
  // - void setState(VoidCallback fn)
  // - bool get mounted
  //
  // The following should be provided by the State class:
  // - void _log(String message, {LogLevel level = LogLevel.debug})

  // ============================================================================
  // Language Match Methods
  // ============================================================================

  /// Validate and refresh exclusions for target language changes
  /// This is called when target language changes to trigger re-detection
  Future<void> validateAndRefreshExclusionsForTargetLang(
    String targetLang,
  ) async {
    if (!initialDataLoaded) {
      return; // Wait for data to load
    }

    // Skip if target_lang is empty or not set
    if (targetLang.isEmpty) {
      AppLogger.log(
        'ExtractPreview',
        'Target language is empty, skipping exclusion validation',
      );
      return;
    }

    // Prevent concurrent calls
    if (isValidatingExclusions) {
      AppLogger.log(
        'ExtractPreview',
        'Exclusion validation already in progress, skipping duplicate call for targetLang=$targetLang',
      );
      return;
    }

    isValidatingExclusions = true;
    try {
      final ExtractPreview extractWidget = widget as ExtractPreview;
      // CRITICAL: Get stored target language from backend to check consistency
      final TranslationService svc = TranslationService();
      final Map<String, dynamic> status =
          await svc.getStatus(extractWidget.taskId);
      final Map<String, dynamic>? segmentsMetadata =
          status['segments_metadata'] as Map<String, dynamic>?;
      final String? storedTargetLang =
          segmentsMetadata?['last_target_lang_for_language_match'] as String?;
      final String? originalFilename =
          status['original_filename'] as String?; // May be null
      final bool isPdfFile =
          originalFilename?.toLowerCase().endsWith('.pdf') ?? false;

      AppLogger.log(
        'ExtractPreview',
        'Validating exclusions for target_lang=$targetLang (stored: $storedTargetLang, current: $currentTargetLangForExclusion)',
        level: LogLevel.info,
      );

      // CRITICAL: Check if target_lang has changed by comparing with backend stored value
      // This ensures consistency even after page refresh
      final bool targetLangChanged =
          storedTargetLang != null && storedTargetLang != targetLang;
      final bool hasLanguageMatchSegments =
          languageMatchedSegmentIndices.isNotEmpty ||
              languageMatchedSegmentCount > 0;
      final bool isFirstTimeDetection =
          storedTargetLang == null && targetLang.isNotEmpty;
      // CRITICAL: For PDF files, check if data was already loaded with correct targetLang
      // If _loadInitialData() already called getLayoutExtract with targetLang and excludedSegmentIndices,
      // and targetLang hasn't changed, we can skip reloadLayoutDataForTargetLang to avoid duplicate API call
      final bool targetLangMatchesCurrent =
          currentTargetLangForExclusion == targetLang;
      final bool targetLangMatchesStored =
          storedTargetLang == targetLang || storedTargetLang == null;

      // If target_lang changed, is first time detection, or we have language_match segments, re-detect exclusions
      if (targetLangChanged ||
          isFirstTimeDetection ||
          hasLanguageMatchSegments) {
        if (isPdfFile) {
          // CRITICAL: Skip reloadLayoutDataForTargetLang if targetLang matches both stored and current values
          // This avoids duplicate API calls since _loadInitialData() already called getLayoutExtract
          // with excludedSegmentIndices and targetLang
          if (targetLangMatchesStored &&
              targetLangMatchesCurrent &&
              !isFirstTimeDetection) {
            AppLogger.log(
              'ExtractPreview',
              'Target language unchanged (PDF). Skipping reloadLayoutDataForTargetLang to avoid duplicate API call. targetLang=$targetLang, stored=$storedTargetLang, current=$currentTargetLangForExclusion',
              level: LogLevel.info,
            );
            // Still update currentTargetLangForExclusion to ensure consistency
            if (mounted) {
              setState(() {
                currentTargetLangForExclusion = targetLang;
              });
            }
          } else {
            // PDF: 直接依赖 layout-extract 的批量检测，避免重复跑一次 update-excluded-segments
            AppLogger.log(
              'ExtractPreview',
              'Target language changed or language_match segments detected (PDF). Reloading layout data with target_lang=$targetLang',
              level: LogLevel.info,
            );

            await reloadLayoutDataForTargetLang(targetLang);

            // reloadLayoutDataForTargetLang 已经根据最新 layoutData 更新了 languageMatchedSegmentCount
            if (mounted) {
              setState(() {
                currentTargetLangForExclusion = targetLang;
              });
            }
          }
        } else {
          AppLogger.log(
            'ExtractPreview',
            'Target language changed or language_match segments detected (non-PDF). Re-detecting exclusions with target_lang=$targetLang',
            level: LogLevel.info,
          );

          // 非 PDF 仍然通过 update-excluded-segments 做一次语言匹配检测
          final Map<String, dynamic> detectionResult =
              await svc.updateExcludedSegmentsForLanguage(
            extractWidget.taskId,
            targetLang,
          );

          final int languageMatchedCount =
              detectionResult['language_matched_count'] as int? ?? 0;

          AppLogger.log(
            'ExtractPreview',
            'Re-detection completed: language_matched_count=$languageMatchedCount',
            level: LogLevel.info,
          );

          if (mounted) {
            setState(() {
              currentTargetLangForExclusion = targetLang;
              languageMatchedSegmentCount = languageMatchedCount;
            });
          }

          // 非 PDF：通过 source-preview 刷新数据和统计
          await reloadSourcePreviewDataForTargetLang(targetLang);
        }
      } else {
        // Target language hasn't changed and no language_match segments, just check state
        await checkLanguageExclusionState(targetLang);
      }
    } catch (e) {
      AppLogger.log(
        'ExtractPreview',
        'Failed to validate and refresh exclusions for target_lang=$targetLang: $e',
        level: LogLevel.error,
      );

      // CRITICAL: Provide user-friendly error message for network errors
      if (mounted) {
        String errorMessage = 'Failed to update excluded segments';
        final String errorStr = e.toString().toLowerCase();
        if (errorStr.contains('connection error') ||
            errorStr.contains('xmlhttprequest') ||
            errorStr.contains('timeout') ||
            errorStr.contains('network')) {
          errorMessage = 'Network error occurred while updating exclusions. '
              'This may happen if the document has many segments. '
              'Please try again or check your network connection.';
        } else if (errorStr.contains('404')) {
          errorMessage = 'Task not found. Please refresh the page.';
        } else if (errorStr.contains('500')) {
          errorMessage = 'Server error occurred. Please try again later.';
        }

        MessageService.showError(
          context,
          errorMessage,
        );
      }

      // On error, still check language exclusion state
      await checkLanguageExclusionState(targetLang);
    } finally {
      // Always reset the flag, even if an error occurred
      isValidatingExclusions = false;
    }
  }

  /// Reload layout data for PDF files with correct target_lang
  Future<void> reloadLayoutDataForTargetLang(String targetLang) async {
    try {
      final ExtractPreview extractWidget = widget as ExtractPreview;
      AppLogger.log(
        'ExtractPreview',
        '_reloadLayoutDataForTargetLang called with targetLang=$targetLang',
        level: LogLevel.info,
      );

      // Get excluded segment indices from excludedSegmentsProviderFamily
      // CRITICAL: Use the same provider that exclusion handlers update for consistency
      final String providerKey = extractWidget.flowId ?? extractWidget.taskId;
      final Set<int> excludedSegments =
          ref.read(excludedSegmentsProviderFamily(providerKey));
      final List<int> excludedIndices = excludedSegments.toList();

      AppLogger.log(
        'ExtractPreview',
        'Calling getLayoutExtract API: taskId=${extractWidget.taskId}, excludedIndices=${excludedIndices.length}, targetLang=$targetLang',
        level: LogLevel.info,
      );

      final TranslationService svc = TranslationService();
      final Map<String, dynamic> layoutData = await svc.getLayoutExtract(
        extractWidget.taskId,
        excludedSegmentIndices: excludedIndices,
        targetLang: targetLang,
      );

      if (layoutData['ready'] == true &&
          layoutData['segments'] != null &&
          mounted) {
        // Reload segments and update exclusion reasons
        final List<dynamic> segmentsData =
            layoutData['segments'] as List<dynamic>? ?? <dynamic>[];
        segmentExclusionReasons.clear();
        segmentTypeInfo.clear();

        final List<int> identifierSegmentIndices = <int>[];
        final List<int> languageMatchedSegmentIndices = <int>[];
        final List<int> userSelectedSegmentIndices = <int>[];

        allSegments = segmentsData.asMap().entries.map((entry) {
          final int index = entry.key;
          final seg = entry.value;
          if (seg is Map) {
            final String? exclusionReason = seg['exclusion_reason'] as String?;
            final String? detectedExclusionReason =
                seg['detected_exclusion_reason'] as String?;
            final String? reasonToUse =
                detectedExclusionReason ?? exclusionReason;

            if (reasonToUse != null) {
              segmentExclusionReasons[index] = reasonToUse;
              if (reasonToUse == ExclusionReason.identifier.value) {
                identifierSegmentIndices.add(index);
              } else if (reasonToUse == ExclusionReason.languageMatch.value) {
                languageMatchedSegmentIndices.add(index);
              } else if (reasonToUse == ExclusionReason.userSelected.value ||
                  reasonToUse == ExclusionReason.unknown.value) {
                userSelectedSegmentIndices.add(index);
              }
            }

            final String? blockType = seg['block_type'] as String?;
            final bool? isTableBody = seg['is_table_body'] as bool?;
            final bool? isImage = seg['is_image'] as bool?;
            if (blockType != null || isTableBody != null || isImage != null) {
              segmentTypeInfo[index] = <String, dynamic>{
                'block_type': blockType,
                'is_table_body': isTableBody,
                'is_image': isImage,
              };
            }
            return seg['text'] as String? ?? '';
          }
          return seg.toString();
        }).toList();

        if (mounted) {
          // CRITICAL: Update all state in setState to trigger rebuild of both ExclusionPanel and segment list
          // Note: Segment indices are already updated above, no need to reassign
          setState(() {
            // CRITICAL: Update count to match indices length for checkbox state calculation
            languageMatchedSegmentCount = languageMatchedSegmentIndices.length;
            // Note: segmentExclusionReasons was already updated above, but setState ensures UI rebuilds
          });

          // CRITICAL: Refresh pagination to reflect updated segment exclusion reasons
          // This ensures the UI displays the correct exclusion labels on segments
          WidgetsBinding.instance.addPostFrameCallback((_) async {
            if (mounted) {
              // CRITICAL: Use refresh() instead of loadFirstPage() to force rebuild of all items
              // This ensures segment labels (exclusionReason) are updated correctly
              paginationController.refresh();
              AppLogger.log(
                'ExtractPreview',
                'Refreshed pagination after reloading layout data for target_lang=$targetLang (exclusion reasons updated)',
                level: LogLevel.info,
              );
            }
          });
        }

        AppLogger.log(
          'ExtractPreview',
          'Reloaded layout data: identifier=${identifierSegmentIndices.length}, language_match=${languageMatchedSegmentIndices.length}',
          level: LogLevel.info,
        );
      }
    } catch (e) {
      AppLogger.log(
        'ExtractPreview',
        'Failed to reload layout data for target_lang=$targetLang: $e',
        level: LogLevel.error,
      );
    }
  }

  /// Reload source preview data for non-PDF files with correct target_lang
  Future<void> reloadSourcePreviewDataForTargetLang(String targetLang) async {
    try {
      final ExtractPreview extractWidget = widget as ExtractPreview;
      final TranslationService svc = TranslationService();

      // Load all segments with pagination support
      final Map<String, dynamic> firstPageRes = await svc.getSourcePreview(
        extractWidget.taskId,
        limit: defaultSegmentPreviewLimit,
        targetLang: targetLang,
      );

      final int? totalSegments = firstPageRes['total_segments'] as int? ??
          firstPageRes['total'] as int?;
      final List<dynamic>? firstPageList =
          firstPageRes['segments'] as List<dynamic>? ??
              firstPageRes['items'] as List<dynamic>?;

      AppLogger.log(
        'ExtractPreview',
        '_reloadSourcePreviewDataForTargetLang: First page - '
            'total_segments=$totalSegments, '
            'returned_count=${firstPageList?.length ?? 0}, '
            'targetLang=$targetLang',
        level: LogLevel.info,
      );

      if (firstPageRes['ready'] != true || firstPageList == null || !mounted) {
        return;
      }

      // Collect all segments
      final List<dynamic> allSegmentsList = <dynamic>[];
      allSegmentsList.addAll(firstPageList);

      // Load remaining segments if needed
      if (totalSegments != null && totalSegments > allSegmentsList.length) {
        var offset = allSegmentsList.length;
        int pageCount = 1;
        int consecutiveEmptyPages = 0;
        const int maxConsecutiveEmptyPages =
            3; // Stop after 3 consecutive empty pages

        while (offset < totalSegments) {
          pageCount++;
          final Map<String, dynamic> nextPageRes = await svc.getSourcePreview(
            extractWidget.taskId,
            offset: offset,
            limit: defaultSegmentPreviewLimit,
            targetLang: targetLang,
          );
          final List<dynamic>? nextPageList =
              nextPageRes['segments'] as List<dynamic>? ??
                  nextPageRes['items'] as List<dynamic>?;

          if (nextPageList == null || nextPageList.isEmpty) {
            consecutiveEmptyPages++;
            AppLogger.log(
              'ExtractPreview',
              '_reloadSourcePreviewDataForTargetLang: WARNING - Empty page at offset $offset '
                  '(consecutive empty: $consecutiveEmptyPages/$maxConsecutiveEmptyPages)',
              level: LogLevel.warn,
            );

            // Stop if we get too many consecutive empty pages
            if (consecutiveEmptyPages >= maxConsecutiveEmptyPages) {
              AppLogger.log(
                'ExtractPreview',
                '_reloadSourcePreviewDataForTargetLang: Stopping pagination after $consecutiveEmptyPages '
                    'consecutive empty pages. Backend may not have all segments despite total_segments=$totalSegments. '
                    'Loaded ${allSegmentsList.length} segments.',
                level: LogLevel.warn,
              );
              break;
            }

            // Try next offset (increment by limit to skip ahead)
            offset += defaultSegmentPreviewLimit;
            continue;
          }

          // Reset consecutive empty pages counter on successful page
          consecutiveEmptyPages = 0;
          allSegmentsList.addAll(nextPageList);
          offset = allSegmentsList.length;
        }

        AppLogger.log(
          'ExtractPreview',
          '_reloadSourcePreviewDataForTargetLang: Loaded all segments - '
              'total_pages=$pageCount, '
              'total_loaded=${allSegmentsList.length}, '
              'expected=$totalSegments',
          level: LogLevel.info,
        );
      }

      // Reload segments and update exclusion reasons (similar to initial load)
      final List<dynamic> segmentsList = allSegmentsList;

      if (!mounted) {
        return;
      }

      segmentTypeInfo.clear();
      segmentExclusionReasons.clear();

      final List<int> identifierSegmentIndices = <int>[];
      final List<int> languageMatchedSegmentIndices = <int>[];
      final List<int> userSelectedSegmentIndices = <int>[];

      allSegments = segmentsList.asMap().entries.map((entry) {
        final int index = entry.key;
        final seg = entry.value;
        if (seg is String) {
          return seg;
        } else if (seg is Map) {
          final String? exclusionReason = seg['exclusion_reason'] as String?;
          final String? detectedExclusionReason =
              seg['detected_exclusion_reason'] as String?;
          final String? reasonToUse =
              detectedExclusionReason ?? exclusionReason;

          if (reasonToUse != null) {
            segmentExclusionReasons[index] = reasonToUse;
            if (reasonToUse == ExclusionReason.identifier.value) {
              identifierSegmentIndices.add(index);
            } else if (reasonToUse == ExclusionReason.languageMatch.value) {
              languageMatchedSegmentIndices.add(index);
            } else if (reasonToUse == ExclusionReason.userSelected.value ||
                reasonToUse == ExclusionReason.unknown.value) {
              userSelectedSegmentIndices.add(index);
            }
          }

          final String? blockType = seg['block_type'] as String?;
          final bool? isTableBody = seg['is_table_body'] as bool?;
          final bool? isImage = seg['is_image'] as bool?;
          if (blockType != null || isTableBody != null || isImage != null) {
            segmentTypeInfo[index] = <String, dynamic>{
              'block_type': blockType,
              'is_table_body': isTableBody,
              'is_image': isImage,
            };
          }
          return (seg['text'] as String?) ??
              (seg['source_text'] as String?) ??
              '';
        }
        return seg.toString();
      }).toList();

      // CRITICAL: Update all state in setState to trigger rebuild of both ExclusionPanel and segment list
      // Note: Segment indices are already updated above, no need to reassign
      setState(() {
        // CRITICAL: Update count to match indices length for checkbox state calculation
        languageMatchedSegmentCount = languageMatchedSegmentIndices.length;
        // Note: segmentExclusionReasons was already updated above, but setState ensures UI rebuilds
      });

      // CRITICAL: Refresh pagination to reflect updated segment exclusion reasons
      // This ensures the UI displays the correct exclusion labels on segments
      WidgetsBinding.instance.addPostFrameCallback((_) async {
        if (mounted) {
          // CRITICAL: Use refresh() instead of loadFirstPage() to force rebuild of all items
          // This ensures segment labels (exclusionReason) are updated correctly
          paginationController.refresh();
          AppLogger.log(
            'ExtractPreview',
            'Refreshed pagination after reloading source preview data for target_lang=$targetLang (exclusion reasons updated)',
            level: LogLevel.info,
          );
        }
      });

      AppLogger.log(
        'ExtractPreview',
        'Reloaded source preview data: identifier=${identifierSegmentIndices.length}, language_match=${languageMatchedSegmentIndices.length}, total_segments=${allSegments.length}',
        level: LogLevel.info,
      );
    } catch (e) {
      AppLogger.log(
        'ExtractPreview',
        'Failed to reload source preview data for target_lang=$targetLang: $e',
        level: LogLevel.error,
      );
    }
  }

  /// Check language exclusion state
  Future<void> checkLanguageExclusionState(String targetLang) async {
    if (!initialDataLoaded) {
      return; // Wait for data to load
    }

    try {
      final ExtractPreview extractWidget = widget as ExtractPreview;
      final TranslationService svc = TranslationService();
      // Call API in detection mode to check if there are language-matched segments
      final Map<String, dynamic> detectionResult =
          await svc.updateExcludedSegmentsForLanguage(
        extractWidget.taskId,
        targetLang,
      );

      final bool requiresConfirmation =
          detectionResult['requires_confirmation'] as bool? ?? false;
      final int languageMatchedCount =
          detectionResult['language_matched_count'] as int? ?? 0;

      // If there are language-matched segments, check if they are currently excluded
      // by comparing with current excluded segments
      if (requiresConfirmation && languageMatchedCount > 0) {
        final String providerKey = extractWidget.flowId ?? extractWidget.taskId;
        final Set<int> currentExcluded =
            ref.read(excludedSegmentsProviderFamily(providerKey));

        // Get the indices of language-matched segments from API response
        final List<dynamic>? languageMatchedSegments =
            detectionResult['language_matched_segments'] as List<dynamic>?;

        if (languageMatchedSegments != null &&
            languageMatchedSegments.isNotEmpty) {
          // Check if any language-matched segments are in the excluded set
          final Set<int> languageMatchedIndices = languageMatchedSegments
              .map((seg) => seg['index'] as int? ?? -1)
              .where((idx) => idx >= 0)
              .toSet();

          // If language-matched segments are excluded, exclusion is active
          final bool hasExcludedLanguageSegments =
              languageMatchedIndices.intersection(currentExcluded).isNotEmpty;

          if (mounted) {
            setState(() {
              isLanguageExclusionActive = hasExcludedLanguageSegments;
              languageMatchedSegmentCount = languageMatchedCount;
            });
          }
        } else {
          // No language-matched segments found, but count is > 0, use count
          if (mounted) {
            setState(() {
              isLanguageExclusionActive = false;
              languageMatchedSegmentCount = languageMatchedCount;
            });
          }
        }
      } else {
        // No language-matched segments, exclusion is not active
        if (mounted) {
          setState(() {
            isLanguageExclusionActive = false;
            languageMatchedSegmentCount = 0;
          });
        }
      }
    } catch (e) {
      AppLogger.log(
        'ExtractPreview',
        'Failed to check language exclusion state: $e',
        level: LogLevel.error,
      );
      // On error, assume exclusion is not active
      if (mounted) {
        setState(() {
          isLanguageExclusionActive = false;
        });
      }
    }
  }

  /// Set total tokens and update provider
  void setTotalTokens(int tokens, String source) {
    final ExtractPreview extractWidget = widget as ExtractPreview;
    final StateController<int?> notifier =
        ref.read(chunkTokensProviderFamily(extractWidget.taskId).notifier);
    notifier.state = tokens;
    totalEstimatedInputTokens = tokens;
    if (mounted) setState(() {});
  }
}
