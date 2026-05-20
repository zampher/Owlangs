import 'package:flutter/foundation.dart' show kDebugMode;
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'dart:async';
import '../../../../shared/services/anonymize_service.dart';
import '../../../../shared/utils/app_logger.dart';
import '../../../tasks/providers/flow_provider.dart';
import '../../../tasks/models/flow.dart';
import '../../providers/translation_state_provider_family.dart';
import '../extract_preview.dart';
import 'extract_preview_state.dart';

/// Mixin for handling data loading in ExtractPreview
///
/// This mixin provides methods for:
/// - Loading initial data from backend
/// - Restoring segments from cache
/// - Reloading data when target language changes
/// - Waiting for real taskId (for pending tabs)
/// - Restoring anonymization progress
///
/// **Note**: Due to the complexity and length of these methods (each can be 200-1000+ lines),
/// and their dependencies on widget properties, ref, setState, and other methods,
/// we recommend moving them incrementally. This file serves as a placeholder for future refactoring.
///
/// **Current Status**:
/// - ✅ Framework created
/// - ✅ Small methods moved (tryRestoreSegmentsFromCache, waitForRealTaskId, checkAndRestoreAnonymizeProgress)
/// - ⏳ Large methods to be moved (loadInitialData, reloadLayoutDataForTargetLang, reloadSourcePreviewDataForTargetLang)
mixin ExtractPreviewDataLoaderMixin<T extends ConsumerStatefulWidget>
    on ConsumerState<T>, ExtractPreviewStateMixin<T> {
  // ============================================================================
  // Required Methods (inherited from State class)
  // ============================================================================

  // Note: The following are available from ConsumerState<T>:
  // - BuildContext get context
  // - T get widget
  // - void setState(VoidCallback fn)
  // - bool get mounted

  /// Set total tokens (delegated to State class)
  /// The State class provides a delegate method that calls the actual implementation
  // ignore: unused_element
  void _setTotalTokens(int tokens, String source) {
    // Implementation provided by State class via delegate method
  }

  /// Start anonymization progress polling (delegated to State class)
  /// The State class provides a delegate method that calls ExtractPreviewProgressMixin.startAnonymizeProgressPolling
  // ignore: unused_element
  void _startAnonymizeProgressPolling(String workflowId) {
    // Implementation provided by State class via delegate method
  }

  /// Start prepare polling (delegated to State class)
  /// The State class provides a delegate method that calls ExtractPreviewProgressMixin.startPreparePolling
  // ignore: unused_element
  void _startPreparePolling() {
    // Implementation provided by State class via delegate method
  }

  // ============================================================================
  // Data Loading Methods
  // ============================================================================

  /// Try to restore segments from FlowContext cache
  /// This avoids reloading segments if they were already loaded before
  void tryRestoreSegmentsFromCache() {
    final extractWidget = widget as ExtractPreview;
    if (extractWidget.flowId == null) return;

    try {
      final flow = ref.read(flowProviderFamily(extractWidget.flowId!));
      final artifacts = flow.context.anonymize;

      // Check if we have cached segments
      if (artifacts.segments != null &&
          artifacts.segments!.isNotEmpty &&
          artifacts.separators != null &&
          artifacts.separators!.isNotEmpty) {
        // Restore segments from cache
        allSegments = List<String>.from(artifacts.segments!);
        allSeparators = List<String>.from(artifacts.separators!);

        // Segments are already loaded in allSegments
        // Chunks will be loaded from backend API

        if (kDebugMode) {
          AppLogger.log(
            'ExtractPreview',
            '_tryRestoreSegmentsFromCache: Restored ${allSegments.length} segments from FlowContext cache, flowId=${extractWidget.flowId}',
          );
        }

        // Mark as loaded to skip loadInitialData's segment loading
        // But still need to load first page for pagination
        if (mounted) {
          setState(() {
            initialDataLoaded = true;
            isPreparing = false;
          });
        }
      } else {
        if (kDebugMode) {
          AppLogger.log(
            'ExtractPreview',
            '_tryRestoreSegmentsFromCache: No cached segments found, will load from backend, flowId=${extractWidget.flowId}',
          );
        }
      }
    } catch (e) {
      if (kDebugMode) {
        AppLogger.log(
          'ExtractPreview',
          '_tryRestoreSegmentsFromCache: Error restoring segments from cache: $e',
        );
      }
      // Continue with normal loading if cache restore fails
    }
  }

  /// Wait for real taskId to be available (for pending tabs)
  /// This method polls translation state until a real taskId is available
  Future<void> waitForRealTaskId() async {
    final extractWidget = widget as ExtractPreview;
    if (!extractWidget.isPending || extractWidget.flowId == null) return;

    // Show waiting state
    if (mounted) {
      setState(() {
        isPreparing = true;
        prepareProgress = 0.0;
        prepareStatus = 'Waiting for file processing...';
        prepareTaskType = '';
      });
    }

    // Poll translation state for real taskId (max 30 seconds)
    int checkCount = 0;
    const maxChecks = 30;

    Timer.periodic(const Duration(seconds: 1), (timer) async {
      checkCount++;

      if (!mounted) {
        timer.cancel();
        return;
      }

      try {
        // For pending tabs, we only check if flowId is set (no global provider needed)
        if (extractWidget.flowId == null) {
          timer.cancel();
          return;
        }

        final dynamic translationState =
            ref.read(translationStateProviderFamily(extractWidget.flowId!));
        final realTaskId = (translationState as dynamic).taskId as String?;

        // Check if we have a real taskId (not pending)
        if (realTaskId != null &&
            realTaskId.isNotEmpty &&
            !realTaskId.startsWith('pending_')) {
          // Real taskId is available
          timer.cancel();

          if (kDebugMode) {
            AppLogger.log(
              'ExtractPreview',
              'Real taskId detected: $realTaskId',
            );
          }

          // Note: The parent (AnonymizeScreen) will replace this pending tab
          // with a real one when it detects the real taskId via _replacePendingExtractTab
          // So we don't need to do anything here except wait
          return;
        }

        // If max checks reached, stop polling and show message
        if (checkCount >= maxChecks) {
          timer.cancel();
          if (mounted) {
            setState(() {
              isPreparing = false;
              prepareStatus =
                  'File processing is taking longer than expected...';
            });
            if (kDebugMode) {
              AppLogger.log(
                'ExtractPreview',
                'Max checks reached, still waiting for real taskId',
              );
            }
          }
        }
      } catch (e) {
        if (kDebugMode) {
          AppLogger.log(
            'ExtractPreview',
            'Error checking for real taskId: $e',
          );
        }
      }
    });
  }

  /// Check if anonymization is in progress and restore the progress state
  /// This is needed when switching back to a flow that has an ongoing anonymize task
  Future<void> checkAndRestoreAnonymizeProgress() async {
    final extractWidget = widget as ExtractPreview;
    if (extractWidget.flowId == null) return;

    try {
      // Check flow context for workflow ID
      final flow = ref.read(flowProviderFamily(extractWidget.flowId!));
      final workflowId = flow.context.anonymize.workflowId;

      if (workflowId == null || workflowId.isEmpty) {
        AppLogger.log(
          'ExtractPreview',
          '_checkAndRestoreAnonymizeProgress: No workflowId found',
        );
        return; // No workflow, nothing to restore
      }

      // Check if anonymization is already completed (has artifacts)
      final anonymizeArtifacts = flow.context.anonymize;
      if (anonymizeArtifacts.anonymizedText != null &&
          anonymizeArtifacts.anonymizedText!.isNotEmpty) {
        AppLogger.log(
          'ExtractPreview',
          '_checkAndRestoreAnonymizeProgress: Anonymization already completed, skipping restore',
        );
        return;
      }

      // CRITICAL: Only check backend progress if anonymization was actually started.
      // The workflowId may be set for translation-only workflows (same workflowId),
      // but the backend doesn't have an /api/anonymize/progress/ endpoint for
      // translation workflows — it would return 404.
      // Anonymization is considered "started" if entitiesExpanded or anonymizedText
      // has data. If neither is set, anonymization hasn't been triggered yet.
      if ((anonymizeArtifacts.entitiesExpanded == null ||
          anonymizeArtifacts.entitiesExpanded!.isEmpty) &&
          anonymizeArtifacts.anonymizedText == null) {
        AppLogger.log(
          'ExtractPreview',
          '_checkAndRestoreAnonymizeProgress: No anonymization data found (entitiesExpanded is empty and anonymizedText is null), skipping backend check',
        );
        return;
      }

      // Check backend progress to see if task is still running
      AppLogger.log(
        'ExtractPreview',
        '_checkAndRestoreAnonymizeProgress: Checking backend progress for workflowId=$workflowId',
      );
      final svc = AnonymizeService();
      final progress = await svc.getProgress(workflowId);

      if (!mounted) return;

      final percent = (progress['percent'] as num?)?.toInt() ?? 0;
      final phase = progress['phase']?.toString() ?? '';
      final message = progress['message']?.toString() ?? '';

      AppLogger.log(
        'ExtractPreview',
        '_checkAndRestoreAnonymizeProgress: Backend progress: percent=$percent, phase=$phase, message=$message',
      );

      // If task is completed (100%) or failed, don't restore
      if (percent >= 100 || phase == 'failed' || phase == 'cancelled') {
        AppLogger.log(
          'ExtractPreview',
          '_checkAndRestoreAnonymizeProgress: Task completed or failed, skipping restore',
        );
        return;
      }

      // If task is still in progress (0 < percent < 100), restore the progress state
      if (percent > 0 && percent < 100) {
        AppLogger.log(
          'ExtractPreview',
          'Restoring anonymize progress: percent=$percent, phase=$phase, workflowId=$workflowId',
          level: LogLevel.info,
        );

        // Build status text
        String statusText = '';
        if (message.isNotEmpty) {
          statusText = message;
        } else if (phase.isNotEmpty) {
          statusText = phase;
        } else if (percent > 0) {
          statusText = '$percent%';
        }

        if (mounted) {
          setState(() {
            isAnonymizing = true;
            anonymizeProgress = percent.clamp(0, 100) / 100.0;
            anonymizeStatus = statusText;
          });

          // Restart anonymization progress polling
          _startAnonymizeProgressPolling(workflowId);
          AppLogger.log(
            'ExtractPreview',
            '_checkAndRestoreAnonymizeProgress: Progress restored and polling restarted',
            level: LogLevel.info,
          );
        }
      } else {
        AppLogger.log(
          'ExtractPreview',
          '_checkAndRestoreAnonymizeProgress: Task not in progress (percent=$percent), skipping restore',
        );
      }
    } catch (e) {
      AppLogger.log(
        'ExtractPreview',
        '_checkAndRestoreAnonymizeProgress: Error restoring anonymize progress: $e',
        level: LogLevel.warn,
      );
      // Continue without restoring progress if error occurs
    }
  }

  /// Load initial data from backend
  /// This is the main data loading method that handles both PDF/DOCX and other formats
  ///
  /// **TODO**: Move implementation from extract_preview.dart
  /// Current location: ~line 1671
  /// **Complexity**: Very high (~1000+ lines), many dependencies
  Future<void> loadInitialData({bool forceReload = false}) async {
    // Implementation to be moved from extract_preview.dart
    // This is the most complex method and should be moved last
  }

  /// Reload layout data for PDF/DOCX files when target language changes
  ///
  /// **TODO**: Move implementation from extract_preview.dart
  /// Current location: ~line 5387
  Future<void> reloadLayoutDataForTargetLang(String targetLang) async {
    // Implementation to be moved from extract_preview.dart
    // This method is specific to PDF/DOCX files (~200 lines)
  }

  /// Reload source preview data for non-PDF files when target language changes
  ///
  /// **TODO**: Move implementation from extract_preview.dart
  /// Current location: ~line 5505
  Future<void> reloadSourcePreviewDataForTargetLang(String targetLang) async {
    // Implementation to be moved from extract_preview.dart
    // This method handles EPUB, MOBI, QT_TS, etc. (~200 lines)
  }
}
