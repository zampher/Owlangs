import 'dart:async';
import 'package:flutter/material.dart';
import 'package:flutter/foundation.dart' show kDebugMode;
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../../../l10n/app_localizations.dart';
import '../../../../shared/services/anonymize_service.dart';
import '../../../../shared/services/translation_service.dart';
import '../../../../shared/utils/app_logger.dart';
import '../../../../shared/utils/message_service.dart';
import '../../../../shared/providers/settings_provider.dart';
import '../../../tasks/models/flow.dart';
import '../../../tasks/providers/flow_provider.dart';
import '../../../anonymize/providers/anonymize_completion_provider.dart';
import '../../services/tab_background_update_service.dart';
import '../../providers/translation_state_provider_family.dart';
import '../../providers/translation_refresh_provider.dart';
import '../extract_preview.dart';
import 'extract_preview_state.dart';

/// Mixin for progress tracking in ExtractPreview
///
/// This mixin provides methods for:
/// - Starting prepare polling (upload + splitting progress)
/// - Handling progress updates
/// - Starting progress polling for anonymization
/// - Handling extraction cancellation
///
/// **Note**: These methods handle progress state management and polling logic.
mixin ExtractPreviewProgressMixin<T extends ConsumerStatefulWidget>
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
  // Progress Tracking State
  // ============================================================================

  // Note: These state variables will be moved from ExtractPreviewStateMixin
  // when methods are moved from extract_preview.dart
  // - progressTimer (Timer?)
  // - currentPollingWorkflowId (String?)
  // - progressInFlight (bool)

  // ============================================================================
  // Progress Methods
  // ============================================================================

  String _localizePrepareTaskType(BuildContext context, String rawTaskType) {
    if (rawTaskType.isEmpty) {
      return '';
    }
    final loc = AppLocalizations.of(context)!;
    switch (rawTaskType) {
      case 'Detect Identifier':
        return loc.extractTaskTypeDetectIdentifier;
      case 'Detect Language':
        return loc.extractTaskTypeDetectLanguage;
      case 'Detect Exclusions':
        return loc.extractTaskTypeDetectExclusions;
      default:
        return rawTaskType;
    }
  }

  /// Start prepare polling (upload + splitting progress)
  ///
  /// **Note**: This method calls `_loadInitialData` and `_showMineruSettingsDialog`
  /// which are still in the main State class. These will be moved later.
  void startPreparePolling() {
    final extractWidget = widget as ExtractPreview;
    prepareTimer?.cancel();
    isPreparing = true;
    prepareProgress = 0.0;
    simulatedProgressPercent = 0; // Reset simulated progress
    // Get current chunk size from global settings for status display
    final globalSettings = ref.read(globalSettingsProvider);
    final chunkSize = globalSettings.chunkSize;
    prepareStatus = 'Preparing... (chunk size: $chunkSize)';
    prepareTaskType = '';
    prepareErrorMessage = '';

    // Check if chunk_size has changed since last load
    // If changed, force reload to get new chunks
    if (lastKnownChunkSize != null && lastKnownChunkSize != chunkSize) {
      if (kDebugMode) {
        AppLogger.log(
          'ExtractPreview',
          'Chunk size changed from $lastKnownChunkSize to $chunkSize, will force reload',
        );
      }
      // Clear existing data to force reload
      setState(() {
        allSegments = <String>[];
        allChunks = <String>[];
        allSeparators = <String>[];
        initialDataLoaded = false;
      });
      // Force reload initial data with new chunk_size
      // Note: _loadInitialData is still in main State class, will be moved later
      // Access via this since Mixin is mixed into State class
      // Fire and forget - don't await here as this is not an async function
      (this as dynamic)
          .loadInitialDataForMixin(forceReload: true)
          .catchError((e) {
        AppLogger.log('ExtractPreview', 'Error loading initial data: $e');
      });
    }
    lastKnownChunkSize = chunkSize;

    prepareTimer = Timer.periodic(const Duration(seconds: 1), (t) async {
      // Don't stop polling if we haven't loaded segments yet, even if initialDataLoaded is true
      // This allows us to detect when preview becomes ready after conversion completes
      if (!mounted) {
        prepareTimer?.cancel();
        prepareTimer = null;
        return;
      }

      // Simulate progress: increase by 1% per second up to 90%
      // This provides visual feedback while waiting for backend response
      if (simulatedProgressPercent < 90) {
        simulatedProgressPercent += 1;
        if (mounted && !prepareInFlight) {
          // Only update UI if we don't have actual progress from backend yet
          // or if backend progress is less than simulated progress
          final currentBackendProgress = (prepareProgress * 100).toInt();
          if (currentBackendProgress < simulatedProgressPercent) {
            setState(() {
              prepareProgress = simulatedProgressPercent / 100.0;
              // Get current chunk size from global settings for status display
              final globalSettings = ref.read(globalSettingsProvider);
              final chunkSize = globalSettings.chunkSize;
              prepareStatus =
                  'Preparing... ($simulatedProgressPercent%) (chunk size: $chunkSize)';
            });
          }
        }
      }

      // Only stop polling if we have both loaded data AND segments are displayed
      // Check if segments are both loaded and displayed in the UI
      final hasSegmentsLoaded = allSegments.isNotEmpty;
      final hasSegmentsDisplayed = paginationController.items.isNotEmpty;

      // CRITICAL: Extract polling should STOP when translation starts
      // Translation has its own independent polling (translationTimer)
      // Check if translation has started (currentTranslationTaskId is set)
      if (currentTranslationTaskId != null &&
          currentTranslationTaskId!.isNotEmpty) {
        AppLogger.log(
          'ExtractPreview',
          '_startPreparePolling: Translation has started (taskId=$currentTranslationTaskId), stopping Extract polling',
          level: LogLevel.info,
        );
        prepareTimer?.cancel();
        prepareTimer = null;
        prepareInFlight = false;
        return;
      }

      // Stop Extract polling if segments are loaded and displayed
      // Also check status to avoid stopping if translation just started
      String? currentStatus;
      try {
        final svc = TranslationService();
        final quickStatus = await svc.getStatus(extractWidget.taskId);
        currentStatus = (quickStatus['status'] ?? '').toString().toLowerCase();
      } catch (e) {
        // If status check fails, continue polling
        AppLogger.log(
          'ExtractPreview',
          '_startPreparePolling: Failed to check status: $e',
        );
      }

      // Stop Extract polling if segments are loaded and displayed AND status is not 'processing'
      // If status is 'processing', translation polling will handle it
      if (initialDataLoaded &&
          hasSegmentsLoaded &&
          hasSegmentsDisplayed &&
          currentStatus != 'processing') {
        if (kDebugMode) {
          AppLogger.log(
            'ExtractPreview',
            '_startPreparePolling: Segments loaded and displayed, completing progress (${allSegments.length} segments), status=$currentStatus',
          );
        }

        // Set progress to 100% and complete
        if (mounted) {
          setState(() {
            prepareProgress = 1.0;
            prepareStatus = 'Complete';
            prepareTaskType = '';
          });
        }

        // Wait a brief moment to show 100% progress, then hide it
        Future.delayed(const Duration(milliseconds: 500), () {
          if (mounted) {
            setState(() {
              isPreparing = false;
              prepareErrorMessage = '';
            });
          }
        });

        prepareTimer?.cancel();
        prepareTimer = null;
        return;
      }

      // If segments are loaded but not yet displayed, update progress to 90%
      if (hasSegmentsLoaded && !hasSegmentsDisplayed && mounted) {
        setState(() {
          prepareProgress = 0.9;
          prepareStatus = 'Loading segments...';
          prepareTaskType = '';
          prepareTaskType = '';
        });
      }

      if (prepareInFlight) {
        return;
      }
      prepareInFlight = true;
      try {
        final pollStartTime = DateTime.now().millisecondsSinceEpoch;
        final svc = TranslationService();
        final status = await svc.getStatus(extractWidget.taskId);

        // Check mounted after async operation
        if (!mounted) {
          prepareInFlight = false;
          return;
        }

        final pollEndTime = DateTime.now().millisecondsSinceEpoch;
        final progress = (status['progress'] as num?)?.toInt() ?? 0;
        final message = status['message']?.toString() ?? '';
        final errorMessage = status['error']?.toString() ?? '';
        final String statusText = (status['status'] ?? '').toString();
        final String statusLower = statusText.toLowerCase();
        final sourcePreview = status['source_preview'] as Map<String, dynamic>?;
        final previewReady = sourcePreview?['ready'] == true;
        final hasSegments = allSegments.isNotEmpty;

        // CRITICAL: Extract polling should NOT handle translation progress.
        // However, extraction steps (e.g. "Detect Language") also report
        // status=processing, so we must distinguish by message prefix instead
        // of relying solely on `status == processing`.
        final String messageLower = message.toLowerCase();
        final bool isTranslatePhase =
            messageLower.startsWith('translate ') ||
                messageLower.startsWith('translation ') ||
                messageLower.startsWith('translating ');
        // Only stop Extract polling when we are clearly in translation phase.
        if (statusLower == 'processing' && isTranslatePhase) {
          AppLogger.log(
            'ExtractPreview',
            '_startPreparePolling: Detected translation phase '
            '(status=processing, message=$message). '
            'Stopping Extract polling - translation polling will handle progress.',
            level: LogLevel.info,
          );
          // Stop Extract polling - translation polling will take over
          prepareTimer?.cancel();
          prepareTimer = null;
          prepareInFlight = false;
          return;
        }

        if (statusLower == 'failed') {
          final combinedMessage = message.isNotEmpty
              ? message
              : (errorMessage.isNotEmpty
                  ? errorMessage
                  : 'Format conversion failed.');
          AppLogger.log(
            'ExtractPreview',
            'Prepare polling detected failure: $combinedMessage',
          );
          prepareTimer?.cancel();
          prepareTimer = null;
          prepareInFlight = false;
          if (mounted) {
            setState(() {
              isPreparing = false;
              initialDataLoaded = true;
              prepareProgress = 0.0;
              prepareStatus = '';
              prepareTaskType = '';
              prepareErrorMessage = combinedMessage;
            });
            MessageService.showError(context, combinedMessage);

            // Check if this is a MinerU connection error
            final isMineruError = combinedMessage
                    .toLowerCase()
                    .contains('failed to connect to mineru') ||
                combinedMessage.toLowerCase().contains('mineru api') ||
                combinedMessage.toLowerCase().contains('ssl: unexpected_eof') ||
                combinedMessage
                    .toLowerCase()
                    .contains('ssl: unexpected_eof_while_reading');

            if (isMineruError && !hasShownMineruSettingsDialog) {
              hasShownMineruSettingsDialog = true;
              WidgetsBinding.instance.addPostFrameCallback((_) async {
                if (mounted && context.mounted) {
                  // Note: _showMineruSettingsDialog is still in main State class, will be moved later
                  // Access via this since Mixin is mixed into State class
                  await (this as dynamic)
                      .showMineruSettingsDialogForMixin(combinedMessage);
                }
              });
            }
          }
          return;
        }

        // If backend reports completion but source preview is still not ready and we have no segments,
        // this is a terminal state for Extract UI (otherwise it will poll forever).
        // Example: backend may complete conversion but fail to generate source preview/segments.
        if (statusLower == 'completed' &&
            progress >= 100 &&
            !previewReady &&
            !hasSegments) {
          // Build a more informative error message
          String combinedMessage;
          if (errorMessage.isNotEmpty) {
            combinedMessage = errorMessage;
          } else {
            // Check if filename suggests WPS format
            final originalFilename = status['original_filename']?.toString();
            final isWpsFile = originalFilename != null &&
                (originalFilename.toLowerCase().contains('_wps.') ||
                    originalFilename.toLowerCase().contains('.wps'));

            if (isWpsFile) {
              combinedMessage =
                  'Failed to extract segments from file. This appears to be a WPS format file (.wps.docx), which is not supported. Please convert the file to standard DOCX format using Microsoft Word or another compatible application.';
            } else if (message.isNotEmpty &&
                message.toLowerCase() !=
                    'format conversion completed successfully') {
              // Use message if it's not the generic success message
              combinedMessage = 'Failed to extract segments: $message';
            } else {
              // Generic error message
              combinedMessage =
                  'Failed to extract segments from file. The file may be corrupted, in an unsupported format (e.g., WPS format), or incompatible with the extraction process. Please try converting the file to a standard format (e.g., standard DOCX) and try again.';
            }
          }

          AppLogger.log(
            'ExtractPreview',
            'Prepare polling detected terminal state (completed but preview not ready): $combinedMessage',
            level: LogLevel.warn,
          );
          prepareTimer?.cancel();
          prepareTimer = null;
          prepareInFlight = false;
          if (mounted) {
            setState(() {
              isPreparing = false;
              initialDataLoaded = true;
              prepareProgress = 0.0;
              prepareStatus = '';
              prepareTaskType = '';
              prepareErrorMessage = combinedMessage;
            });
            MessageService.showError(context, combinedMessage);
          }
          return;
        }
        final setStateStartTime = DateTime.now().millisecondsSinceEpoch;

        // Double-check mounted before setState
        if (mounted) {
          setState(() {
            // Use backend progress if it's >= 90%, otherwise use the higher of backend or simulated progress
            // Simulated progress increases by 1% per second up to 90%
            final backendProgressPercent = progress.clamp(0, 100);
            final effectiveProgressPercent = backendProgressPercent >= 90
                ? backendProgressPercent
                : (backendProgressPercent > simulatedProgressPercent
                    ? backendProgressPercent
                    : simulatedProgressPercent);

            prepareProgress = effectiveProgressPercent / 100.0;

            // Extract task type from message (e.g., "Detect Identifier", "Detect Language")
            var extractedTaskType = '';
            if (message.isNotEmpty) {
              // Parse message format: "Detect Identifier: 100/500 segments (20%)"
              // or "Detect Language: 250/500 segments (50%)"
              final int colonIndex = message.indexOf(':');
              if (colonIndex > 0) {
                extractedTaskType = message.substring(0, colonIndex).trim();
              }
            }

            // Get current chunk size from global settings for status display
            final globalSettings = ref.read(globalSettingsProvider);
            final chunkSize = globalSettings.chunkSize;
            if (message.isNotEmpty) {
              // If message already contains chunk size info, use it as-is
              // Otherwise, append chunk size info
              prepareStatus = message.contains('chunk size')
                  ? message
                  : '$message (chunk size: $chunkSize)';
            } else {
              prepareStatus =
                  'Preparing... ($effectiveProgressPercent%) (chunk size: $chunkSize)';
            }

            // Set task type for display (localized for known task types)
            prepareTaskType =
                _localizePrepareTaskType(context, extractedTaskType);
            if (prepareErrorMessage.isNotEmpty) {
              prepareErrorMessage = '';
            }
          });
        }
        // Log slow operations only
        if (kDebugMode) {
          final setStateEndTime = DateTime.now().millisecondsSinceEpoch;
          final pollDuration = pollEndTime - pollStartTime;
          final setStateDuration = setStateEndTime - setStateStartTime;
          if (pollDuration > 200 || setStateDuration > 20) {
            // Slow polling detected
          }
        }

        // Check if chunk_size has changed (e.g., after resplit)
        final globalSettings = ref.read(globalSettingsProvider);
        final currentChunkSize = globalSettings.chunkSize;
        if (lastKnownChunkSize != null &&
            lastKnownChunkSize != currentChunkSize) {
          if (kDebugMode) {
            AppLogger.log(
              'ExtractPreview',
              'Chunk size changed from $lastKnownChunkSize to $currentChunkSize during polling, forcing reload',
            );
          }
          // Reset scroll controllers to prevent ScrollPosition errors
          if (segmentsScrollController.hasClients) {
            segmentsScrollController.jumpTo(0);
          }
          if (chunksScrollController.hasClients) {
            chunksScrollController.jumpTo(0);
          }
          // Clear existing data and force reload
          setState(() {
            allSegments = <String>[];
            allChunks = <String>[];
            allSeparators = <String>[];
            initialDataLoaded = false;
          });
          // Note: _loadInitialData is still in main State class, will be moved later
          // Access via this since Mixin is mixed into State class
          await (this as dynamic).loadInitialDataForMixin(forceReload: true);
          lastKnownChunkSize = currentChunkSize;
          prepareInFlight = false;
          return;
        }

        // If preview is ready but we don't have segments yet, reload initial data
        // This handles the case where preview becomes ready after conversion completes
        if (previewReady && !hasSegments) {
          AppLogger.log(
            'ExtractPreview',
            'Preview is ready but no segments loaded, reloading initial data...',
          );
          // Reload initial data to get segments
          // Note: _loadInitialData is still in main State class, will be moved later
          // Access via this since Mixin is mixed into State class
          await (this as dynamic).loadInitialDataForMixin();
          // After loading, check if segments are displayed
          final hasSegmentsDisplayed = paginationController.items.isNotEmpty;
          if (allSegments.isNotEmpty && hasSegmentsDisplayed) {
            AppLogger.log(
              'ExtractPreview',
              'Segments loaded and displayed, completing progress',
            );
            // Set progress to 100% and complete
            if (mounted) {
              setState(() {
                prepareProgress = 1.0;
                prepareStatus = 'Complete';
                prepareTaskType = '';
                prepareTaskType = '';
              });
            }
            // Wait a brief moment to show 100% progress, then hide it
            Future.delayed(const Duration(milliseconds: 500), () {
              if (mounted) {
                setState(() {
                  isPreparing = false;
                  initialDataLoaded = true;
                  prepareErrorMessage = '';
                });
              }
            });
            prepareTimer?.cancel();
            prepareTimer = null;
            prepareInFlight = false;
            return;
          } else if (allSegments.isNotEmpty && !hasSegmentsDisplayed) {
            // Segments loaded but not yet displayed, update progress to 90%
            if (mounted) {
              setState(() {
                prepareProgress = 0.9;
                // Get current chunk size from global settings for status display
                final globalSettings = ref.read(globalSettingsProvider);
                final chunkSize = globalSettings.chunkSize;
                prepareStatus = 'Loading segments... (chunk size: $chunkSize)';
                prepareTaskType = '';
                initialDataLoaded = true;
              });
            }
          }
        }

        // If progress is 100% and preview is ready, but we still don't have segments,
        // try one more time to load them (even if initialDataLoaded is true, in case it failed before)
        if (progress >= 100 && previewReady && !hasSegments) {
          AppLogger.log(
            'ExtractPreview',
            'Progress 100% and preview ready, but no segments. Attempting final load...',
          );
          // Note: _loadInitialData is still in main State class, will be moved later
          // Access via this since Mixin is mixed into State class
          await (this as dynamic).loadInitialDataForMixin(forceReload: true);
          final hasSegmentsDisplayed = paginationController.items.isNotEmpty;
          if (allSegments.isNotEmpty && hasSegmentsDisplayed) {
            AppLogger.log(
              'ExtractPreview',
              'Final load successful, segments displayed, completing progress',
            );
            // Set progress to 100% and complete
            if (mounted) {
              setState(() {
                prepareProgress = 1.0;
                prepareStatus = 'Complete';
                prepareTaskType = '';
                prepareTaskType = '';
              });
            }
            // Wait a brief moment to show 100% progress, then hide it
            Future.delayed(const Duration(milliseconds: 500), () {
              if (mounted) {
                setState(() {
                  isPreparing = false;
                  initialDataLoaded = true;
                  prepareErrorMessage = '';
                });
              }
            });
            prepareTimer?.cancel();
            prepareTimer = null;
            prepareInFlight = false;
            return;
          } else if (allSegments.isNotEmpty && !hasSegmentsDisplayed) {
            // Segments loaded but not yet displayed, update progress to 90%
            if (mounted) {
              setState(() {
                prepareProgress = 0.9;
                // Get current chunk size from global settings for status display
                final globalSettings = ref.read(globalSettingsProvider);
                final chunkSize = globalSettings.chunkSize;
                prepareStatus = 'Loading segments... (chunk size: $chunkSize)';
                prepareTaskType = '';
                initialDataLoaded = true;
              });
            }
          } else {
            AppLogger.log(
              'ExtractPreview',
              'Final load failed, segments still empty. Will continue polling.',
            );
          }
        }

        // If progress is 100% and we have segments loaded, check if they're displayed
        if (progress >= 100 && hasSegments) {
          final hasSegmentsDisplayed = paginationController.items.isNotEmpty;
          if (hasSegmentsDisplayed) {
            AppLogger.log(
              'ExtractPreview',
              'Progress 100% and segments displayed, completing progress',
            );
            // Set progress to 100% and complete
            if (mounted) {
              setState(() {
                prepareProgress = 1.0;
                prepareStatus = 'Complete';
                prepareTaskType = '';
                prepareTaskType = '';
              });
            }
            // Wait a brief moment to show 100% progress, then hide it
            Future.delayed(const Duration(milliseconds: 500), () {
              if (mounted) {
                setState(() {
                  isPreparing = false;
                  initialDataLoaded = true;
                  prepareErrorMessage = '';
                });
              }
            });
            prepareTimer?.cancel();
            prepareTimer = null;
            prepareInFlight = false;
            return;
          } else {
            // Segments loaded but not yet displayed, update progress to 90%
            if (mounted) {
              setState(() {
                prepareProgress = 0.9;
                // Get current chunk size from global settings for status display
                final globalSettings = ref.read(globalSettingsProvider);
                final chunkSize = globalSettings.chunkSize;
                prepareStatus = 'Loading segments... (chunk size: $chunkSize)';
                prepareTaskType = '';
              });
            }
          }
        }
      } catch (e) {
        AppLogger.log('ExtractPreview', '_startPreparePolling: error: $e');
        // Ignore transient errors during polling
      } finally {
        prepareInFlight = false;
      }
    });
  }

  /// Start translation progress polling (independent from Extract polling)
  /// This method polls /service/status/{taskId} for translation progress updates
  void startTranslationPolling(String taskId) {
    // Cancel any existing translation polling
    translationTimer?.cancel();
    translationTimer = null;

    // Set current translation task ID to prevent duplicate polling
    currentTranslationTaskId = taskId;

    AppLogger.log(
      'ExtractPreview',
      'startTranslationPolling: Starting translation polling for taskId=$taskId',
      level: LogLevel.info,
    );

    // Set translation state
    if (mounted) {
      setState(() {
        isTranslating = true;
        translationProgress = 0.1; // Start at 10% (translation starts at 10%)
        translationStatus = 'Translating...';
      });
    }

    // Start polling timer
    translationTimer = Timer.periodic(const Duration(seconds: 1), (t) async {
      if (!mounted) {
        translationTimer?.cancel();
        translationTimer = null;
        translationInFlight = false;
        translationInFlightStartTime = null;
        return;
      }

      // Prevent concurrent polling
      // CRITICAL: If translationInFlight is true, check if it's been too long (>10 seconds)
      // If so, reset it to allow progress updates (handles cases where API call takes a long time)
      if (translationInFlight) {
        final now = DateTime.now().millisecondsSinceEpoch;
        final startTime = translationInFlightStartTime;
        if (startTime != null && (now - startTime) > 10000) {
          // Reset stale lock after 10 seconds
          AppLogger.log(
            'ExtractPreview',
            '_startTranslationPolling timer: translationInFlight has been true for ${now - startTime}ms (>10s), resetting to allow progress updates',
            level: LogLevel.warn,
          );
          translationInFlight = false;
          translationInFlightStartTime = null;
        } else {
          AppLogger.log(
            'ExtractPreview',
            '_startTranslationPolling timer: translationInFlight is true, skipping this tick (previous request still in progress)',
          );
          return;
        }
      }

      translationInFlight = true;
      translationInFlightStartTime = DateTime.now().millisecondsSinceEpoch;

      try {
        final pollStartTime = DateTime.now().millisecondsSinceEpoch;
        final svc = TranslationService();

        // Use the translation taskId (which is the workflowId)
        final status = await svc.getStatus(taskId);

        if (!mounted) {
          translationInFlight = false;
          translationInFlightStartTime = null;
          return;
        }

        // CRITICAL: Reset translationInFlight immediately after getting status
        // This allows the next timer tick to proceed even if this tick takes a long time
        // We do this BEFORE processing the status to ensure progress updates are not blocked
        translationInFlight = false;
        translationInFlightStartTime = null;

        final pollEndTime = DateTime.now().millisecondsSinceEpoch;
        final progress = (status['progress'] as num?)?.toInt() ?? 0;
        final message = status['message']?.toString() ?? '';
        final statusText = (status['status'] ?? '').toString();
        final statusLower = statusText.toLowerCase();

        AppLogger.log(
          'ExtractPreview',
          '_startTranslationPolling: Status check - status=$statusLower, progress=$progress, message="$message", pollDuration=${pollEndTime - pollStartTime}ms, taskId=$taskId',
          level: LogLevel.info,
        );

        // Update translation progress
        if (statusLower == 'processing' || statusLower == 'completed') {
          final oldProgress = translationProgress;
          final newProgress = progress.clamp(0, 100) / 100.0;

          if (mounted) {
            setState(() {
              translationProgress = newProgress;
              translationStatus =
                  message.isNotEmpty ? message : 'Translating...';
            });
          }

          // Log progress change
          if ((oldProgress * 100).round() != (newProgress * 100).round()) {
            AppLogger.log(
              'ExtractPreview',
              'Translation progress changed: ${(oldProgress * 100).toStringAsFixed(1)}% -> ${(newProgress * 100).toStringAsFixed(1)}% (taskId=$taskId, message: "$message")',
              level: LogLevel.info,
            );
          }
        }

        // Stop polling only when backend reports a terminal status.
        // Do NOT treat (status=processing, progress=100) as terminal because
        // backend may still run post-processing (e.g. auto formula repair) after
        // the main translation steps, and we need to keep polling for updates.
        final isCompletedState = statusLower == 'completed';
        final isFailedState = statusLower == 'failed';
        final isCancelledState = statusLower == 'cancelled';

        if (isCompletedState || isFailedState || isCancelledState) {
          AppLogger.log(
            'ExtractPreview',
            'Translation polling completed: status=$statusLower, progress=$progress, taskId=$taskId',
            level: LogLevel.info,
          );

          // Push downloads from status into translation state so Export dialog has formats
          final extractWidget = widget as ExtractPreview;
          final flowId = extractWidget.flowId;
          if (flowId != null && mounted) {
            final dynamic dv = status['downloads'];
            if (dv != null && dv is Map && dv.isNotEmpty) {
              final map =
                  dv.map((k, v) => MapEntry(k.toString(), v.toString()));
              ref
                  .read(translationStateProviderFamily(flowId).notifier)
                  .setDownloads(map);
              AppLogger.log(
                'ExtractPreview',
                'Set downloads from translation polling completed: flowId=$flowId, keys=${map.keys.toList()}',
              );
            } else {
              AppLogger.log(
                'ExtractPreview',
                'Translation completed but status downloads empty or invalid: flowId=$flowId, type=${dv.runtimeType}',
              );
            }

            // CRITICAL: Update translationStateProvider status so Translate All button and Retry button work correctly
            final TranslationStateFamilyNotifier translationNotifier =
                ref.read(translationStateProviderFamily(flowId).notifier);
            if (isCompletedState && progress >= 100 && !isFailedState) {
              translationNotifier.setStatusText('completed');
              translationNotifier.setTranslating(false);
              translationNotifier.setProgress(100);

              // Get translation statistics (success/fail counts) from segments API
              try {
                final svc = TranslationService();
                // CRITICAL: Force refresh here because backend may run post-translate
                // normalization (e.g. auto formula repair) after segments were first loaded.
                final segmentsData =
                    await svc.getTranslationSegments(taskId, forceRefresh: true);
                final segments =
                    segmentsData['segments'] as List<dynamic>? ?? <dynamic>[];

                var successCount = 0;
                var failCount = 0;
                for (final segment in segments) {
                  final isFailed = segment['is_failed'] as bool? ?? false;
                  final isExcluded = segment['is_excluded'] as bool? ?? false;
                  final segmentStatus = segment['status'] as String?;
                  // Count failed segments (excluding excluded and cleared)
                  if (isFailed && !isExcluded && segmentStatus != 'cleared') {
                    failCount++;
                  } else if (!isExcluded && segmentStatus != 'cleared') {
                    successCount++;
                  }
                }

                translationNotifier.setTranslationStats(
                  successCount: successCount,
                  failCount: failCount,
                  totalSegments: segments.length,
                );

                AppLogger.log(
                  'ExtractPreview',
                  'Updated translation stats: success=$successCount, fail=$failCount, total=${segments.length}',
                );

                // Force TranslationResultPreview to reload latest segments.
                // This matters when backend runs post-translation normalization
                // (e.g. auto formula repair) after the first segments fetch.
                triggerTranslationRefresh(ref);
              } catch (e) {
                AppLogger.log(
                  'ExtractPreview',
                  'Failed to get translation stats: $e',
                  level: LogLevel.warn,
                );
                // Set default stats if API call fails
                translationNotifier.setTranslationStats(
                  successCount: 0,
                  failCount: 0,
                  totalSegments: 0,
                );
              } finally {
                // Always trigger a refresh on completion so the Translate view
                // can pick up any post-processing changes (e.g. auto formula repair),
                // even if stats fetching failed.
                triggerTranslationRefresh(ref);
              }
            } else if (isFailedState) {
              translationNotifier.setStatusText('failed');
              translationNotifier.setTranslating(false);
            } else if (isCancelledState) {
              translationNotifier.setStatusText('cancelled');
              translationNotifier.setTranslating(false);
            }

            AppLogger.log(
              'ExtractPreview',
              'Updated translationStateProvider: statusText=${isCompletedState ? 'completed' : isFailedState ? 'failed' : 'cancelled'}, isTranslating=false, progress=$progress',
            );
          }

          if (mounted) {
            setState(() {
              if (isCompletedState && progress >= 100 && !isFailedState) {
                translationProgress = 1.0;
                translationStatus =
                    message.isNotEmpty ? message : 'Translation completed';
              } else {
                translationProgress = 0.0;
                translationStatus = '';
              }
              isTranslating = false;
            });
          }

          translationTimer?.cancel();
          translationTimer = null;
          // CRITICAL: DO NOT clear currentTranslationTaskId here!
          // Keep it to prevent build() from restarting polling when workflowId still exists in flow context
          // currentTranslationTaskId = null;  // ❌ Removed to prevent infinite loop
        }
      } catch (e) {
        AppLogger.log(
          'ExtractPreview',
          '_startTranslationPolling: Error polling translation status: $e',
          level: LogLevel.warn,
        );
        // Ensure translationInFlight is reset on error
        translationInFlight = false;
        translationInFlightStartTime = null;
      }
      // Note: translationInFlight is already reset after getting status (see line 614)
      // This ensures progress updates are not blocked by long-running API calls
    });
  }

  /// Handle progress update (shared by both local timer and background service)
  /// This is ONLY for anonymization workflow, NOT for translation
  void handleProgressUpdate(Map<String, dynamic> progress, String workflowId) {
    if (!mounted || !isAnonymizing) return;

    final percent = (progress['percent'] as num?)?.toInt() ?? 0;
    final phase = progress['phase']?.toString() ?? '';
    final message = progress['message']?.toString() ?? '';
    AppLogger.log(
      'ExtractPreview',
      'progress response: percent=$percent, phase=$phase, message="$message"',
    );

    // If backend returned empty object (e.g., {}), skip updating UI to avoid regress to 0%
    if (percent == 0 && phase.isEmpty && message.isEmpty) {
      AppLogger.log(
        'ExtractPreview',
        'skip UI update due to empty progress payload',
      );
      return;
    }

    // Build status text: prefer message, fallback to phase, include percent if available
    String statusText = '';
    if (message.isNotEmpty) {
      statusText = message;
    } else if (phase.isNotEmpty) {
      statusText = phase;
    }
    // If message contains chunk info (X/Y chunks), it's already included
    // Otherwise, add percent if no message
    if (statusText.isEmpty && percent > 0) {
      statusText = '$percent%';
    }

    if (mounted) {
      setState(() {
        anonymizeProgress = percent.clamp(0, 100) / 100.0;
        anonymizeStatus = statusText;
      });
    }
  }

  /// Start anonymization progress polling (independent from Extract and Translate polling)
  /// This method polls /api/anonymize/progress/{workflowId} for anonymization workflow progress
  void startAnonymizeProgressPolling(String workflowId) {
    final extractWidget = widget as ExtractPreview;
    if (extractWidget.flowId == null) return;

    // Cancel any existing polling (both local timer and background service)
    progressTimer?.cancel();
    progressTimer = null;

    // Unregister from background service if already registered
    final bgService = ref.read(tabBackgroundUpdateServiceProvider);
    bgService.unregisterUpdate(
      flowId: extractWidget.flowId!,
      taskId: workflowId,
      updateType: 'anonymize',
    );

    // Store the workflowId we're polling for
    currentPollingWorkflowId = workflowId;

    // Register with background service for persistent updates
    bgService.registerUpdate(
      flowId: extractWidget.flowId!,
      taskId: workflowId,
      updateType: 'anonymize',
      updateCallback: (progress) {
        // This callback is called even when widget is not mounted
        // We need to check mounted before calling setState
        if (!mounted) {
          // Widget not mounted, but we can still persist progress to flow context
          // The progress is already persisted by the service
          return;
        }

        // Update UI if widget is mounted
        handleProgressUpdate(progress, workflowId);
      },
    );

    // Local timer for immediate UI updates
    progressTimer = Timer.periodic(const Duration(seconds: 2), (t) async {
      // Check if widget is still mounted and we're still anonymizing
      if (!mounted || !isAnonymizing) {
        AppLogger.log(
          'ExtractPreview',
          'stop polling: mounted=$mounted, isAnonymizing=$isAnonymizing',
        );
        progressTimer?.cancel();
        progressTimer = null;
        currentPollingWorkflowId = null;
        return;
      }

      // Verify that flowId and workflowId still match (prevent cross-flow pollution)
      if (extractWidget.flowId != null && mounted) {
        try {
          final flow = ref.read(flowProviderFamily(extractWidget.flowId!));
          final currentWorkflowId = flow.context.anonymize.workflowId;
          if (currentWorkflowId != workflowId ||
              currentWorkflowId != currentPollingWorkflowId) {
            AppLogger.log(
              'ExtractPreview',
              'workflowId mismatch, stopping polling: expected=$workflowId, current=$currentWorkflowId',
            );
            progressTimer?.cancel();
            progressTimer = null;
            currentPollingWorkflowId = null;
            if (mounted) {
              setState(() {
                isAnonymizing = false;
                anonymizeProgress = 0.0;
                anonymizeStatus = '';
              });
            }
            return;
          }
        } catch (e) {
          AppLogger.log('ExtractPreview', 'Error checking flow state: $e');
          // Continue polling if check fails (flow might not be available yet)
        }
      }

      if (progressInFlight) {
        return;
      }
      try {
        progressInFlight = true;
        final svc = AnonymizeService();
        final progress = await svc.getProgress(workflowId);
        if (!mounted || !isAnonymizing) {
          progressInFlight = false;
          return;
        }

        // Double-check workflowId still matches after async call
        if (currentPollingWorkflowId != workflowId) {
          progressInFlight = false;
          return;
        }

        // Extract progress values
        final percent = (progress['percent'] as num?)?.toInt() ?? 0;
        final phase = progress['phase']?.toString() ?? '';
        final message = progress['message']?.toString() ?? '';

        // Use shared progress handler
        handleProgressUpdate(progress, workflowId);

        // Only stop polling if explicitly completed or failed
        if (percent >= 100 ||
            phase == 'completed' ||
            phase == 'failed' ||
            phase == 'cancelled') {
          // If completed, check if we need to trigger completion event
          // This handles the case where completion is detected via polling rather than runAnonymizeWithConfig return
          if ((percent >= 100 || phase == 'completed') &&
              extractWidget.flowId != null) {
            // Check if artifacts are already saved (to avoid duplicate processing)
            try {
              final flow = ref.read(flowProviderFamily(extractWidget.flowId!));
              final hasArtifacts =
                  flow.context.anonymize.anonymizedText != null &&
                      flow.context.anonymize.anonymizedText!.isNotEmpty;

              if (!hasArtifacts) {
                // Artifacts not saved yet, but backend says completed
                // This can happen if runAnonymizeWithConfig returned before backend fully completed
                // or if completion was detected via polling before runAnonymizeWithConfig returned
                AppLogger.log(
                  'ExtractPreview',
                  'Polling detected completion but artifacts not found. Notifying completion anyway...',
                );
                // Notify completion - _onAnonymizeCompleteFromExtract will check for artifacts
                // If artifacts don't exist, it will try to get them from flow context or handle gracefully
                if (extractWidget.flowId != null) {
                  ref
                      .read(anonymizeCompletionProvider.notifier)
                      .notifyCompletion(extractWidget.flowId!);
                  AppLogger.log(
                    'ExtractPreview',
                    'Completion notification sent via polling detection (artifacts may be missing)',
                  );
                }
              } else {
                // Artifacts already exist, just notify completion if not already done
                AppLogger.log(
                  'ExtractPreview',
                  'Polling detected completion and artifacts already exist',
                );
                if (extractWidget.flowId != null) {
                  ref
                      .read(anonymizeCompletionProvider.notifier)
                      .notifyCompletion(extractWidget.flowId!);
                  AppLogger.log(
                    'ExtractPreview',
                    'Completion notification sent (artifacts already exist)',
                  );
                }
              }
            } catch (e) {
              AppLogger.log(
                'ExtractPreview',
                'Error checking artifacts after polling completion: $e',
              );
            }
          }

          progressTimer?.cancel();
          progressTimer = null;
          currentPollingWorkflowId = null;

          if (mounted) {
            setState(() {
              isAnonymizing = false;
              if (percent >= 100 || phase == 'completed') {
                anonymizeProgress = 1.0;
                anonymizeStatus = 'Completed';
              } else if (phase == 'failed') {
                anonymizeProgress = 0.0;
                anonymizeStatus = '';
                // Use addPostFrameCallback to ensure context is fully initialized
                WidgetsBinding.instance.addPostFrameCallback((_) {
                  if (mounted && context.mounted) {
                    MessageService.showError(
                      context,
                      message.isNotEmpty ? message : 'Anonymization failed',
                    );
                  }
                });
              }
            });
          }
        }
      } catch (e, stackTrace) {
        AppLogger.log('ExtractPreview', 'Progress polling error: $e');
        AppLogger.log(
          'ExtractPreview',
          'Progress polling stackTrace: $stackTrace',
        );
        // Don't stop polling on error, just log it
      } finally {
        progressInFlight = false;
      }
    });
  }

  /// Handle extraction cancellation
  Future<void> handleCancelExtraction() async {
    final extractWidget = widget as ExtractPreview;
    if (extractWidget.taskId == 'pending' || extractWidget.taskId.isEmpty) {
      // Task not yet started, just stop polling
      prepareTimer?.cancel();
      prepareTimer = null;
      if (mounted) {
        setState(() {
          isPreparing = false;
          prepareProgress = 0.0;
          prepareStatus = '';
          prepareTaskType = '';
          prepareErrorMessage = 'Extraction cancelled';
        });
        MessageService.showInfo(context, 'Extraction cancelled');
      }
      return;
    }

    // Show confirmation dialog
    final AppLocalizations l10n = AppLocalizations.of(context)!;
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (dialogContext) => AlertDialog(
        title: Text(l10n.extractCancelExtractionTitle),
        content: Text(l10n.extractCancelExtractionContent),
        actions: <Widget>[
          TextButton(
            onPressed: () => Navigator.of(dialogContext).pop(false),
            child: Text(l10n.extractCancelExtractionNo),
          ),
          TextButton(
            onPressed: () => Navigator.of(dialogContext).pop(true),
            child: Text(l10n.extractCancelExtractionYes),
          ),
        ],
      ),
    );

    if (confirmed != true) {
      return;
    }

    try {
      // Cancel the task on backend
      final svc = TranslationService();
      await svc.cancelTask(extractWidget.taskId);

      // Stop polling timer
      prepareTimer?.cancel();
      prepareTimer = null;
      prepareInFlight = false;

      // Update UI state
      if (mounted) {
        setState(() {
          isPreparing = false;
          prepareProgress = 0.0;
          prepareStatus = '';
          prepareTaskType = '';
          prepareErrorMessage = 'Extraction cancelled';
        });
        MessageService.showSuccess(context, 'Extraction cancelled');
      }
    } catch (e) {
      AppLogger.log(
        'ExtractPreview',
        'Failed to cancel extraction: $e',
        level: LogLevel.error,
      );
      if (mounted) {
        MessageService.showError(
          context,
          'Failed to cancel extraction: $e',
        );
      }
    }
  }
}
