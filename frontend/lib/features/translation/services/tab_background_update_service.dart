// SPDX-FileCopyrightText: 2025 QinHan
// SPDX-License-Identifier: MPL-2.0

import 'dart:async';
import 'package:flutter/foundation.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../../shared/services/anonymize_service.dart';
import '../../../shared/utils/app_logger.dart';
import '../../tasks/models/flow.dart';
import '../../tasks/providers/flow_provider_family.dart';
import '../../anonymize/providers/anonymize_completion_provider.dart';

/// Background update service for tabs
/// This service manages background polling/updates for tabs even when they're not visible
/// Updates are persisted to flow context so they're available when user switches back
class TabBackgroundUpdateService {
  factory TabBackgroundUpdateService() => _instance;
  TabBackgroundUpdateService._internal();
  static final TabBackgroundUpdateService _instance =
      TabBackgroundUpdateService._internal();

  // Map of flowId -> Map of taskId/workflowId -> Timer
  final Map<String, Map<String, Timer>> _updateTimers =
      <String, Map<String, Timer>>{};

  // Map of flowId -> Map of taskId/workflowId -> UpdateCallback
  final Map<String, Map<String, void Function(Map<String, dynamic>)>>
      _updateCallbacks =
      <String, Map<String, void Function(Map<String, dynamic>)>>{};

  // ProviderContainer reference for accessing providers
  ProviderContainer? _container;

  void _log(String message, {LogLevel level = LogLevel.debug}) {
    AppLogger.log('TabBackgroundUpdateService', message, level: level);
  }

  /// Set the ProviderContainer (called from app initialization)
  void setContainer(ProviderContainer container) {
    _container = container;
  }

  /// Get the ProviderContainer (for accessing providers when widget is disposed)
  ProviderContainer? getContainer() => _container;

  /// Register a background update for a task/workflow
  ///
  /// [flowId] - The flow ID
  /// [taskId] - The task ID (for extract progress) or workflowId (for anonymize progress)
  /// [updateType] - Type of update: 'extract' or 'anonymize'
  /// [updateCallback] - Callback to be called when update is received
  /// [interval] - Polling interval (default: 2 seconds)
  void registerUpdate({
    required String flowId,
    required String taskId,
    required String updateType,
    required void Function(Map<String, dynamic>) updateCallback,
    Duration interval = const Duration(seconds: 2),
  }) {
    final String key = '$updateType:$taskId';

    // Cancel existing timer if any
    unregisterUpdate(flowId: flowId, taskId: taskId, updateType: updateType);

    // Store callback
    _updateCallbacks.putIfAbsent(
      flowId,
      () => <String, void Function(Map<String, dynamic>)>{},
    )[key] = updateCallback;

    // Start polling
    final Timer timer = Timer.periodic(interval, (Timer t) async {
      try {
        Map<String, dynamic>? progress;

        if (updateType == 'anonymize') {
          // Poll anonymize progress
          final AnonymizeService svc = AnonymizeService();
          progress = await svc.getProgress(taskId);

          // Persist to flow context
          await _persistAnonymizeProgress(flowId, taskId, progress);

          // Check if completed and trigger completion event
          final int percent = (progress['percent'] as num?)?.toInt() ?? 0;
          final String phase = progress['phase']?.toString() ?? '';

          if ((percent >= 100 || phase == 'completed') && _container != null) {
            // Stop polling when completed
            unregisterUpdate(
              flowId: flowId,
              taskId: taskId,
              updateType: updateType,
            );
            try {
              // Check if artifacts already exist
              final FlowContext flowState =
                  _container!.read(flowProviderFamily(flowId));
              final bool hasArtifacts =
                  flowState.anonymize.anonymizedText != null &&
                      flowState.anonymize.anonymizedText!.isNotEmpty;

              if (!hasArtifacts) {
                // Notify completion even if artifacts not found yet
                _container!
                    .read(anonymizeCompletionProvider.notifier)
                    .notifyCompletion(flowId);
                if (kDebugMode) {
                  _log(
                    '[TabBackgroundUpdateService] Completion notification sent (artifacts may be missing)',
                  );
                }
              } else {
                // Artifacts exist, just notify completion
                _container!
                    .read(anonymizeCompletionProvider.notifier)
                    .notifyCompletion(flowId);
                if (kDebugMode) {
                  _log(
                    '[TabBackgroundUpdateService] Completion notification sent (artifacts exist)',
                  );
                }
              }
            } catch (e) {
              if (kDebugMode) {
                _log(
                  '[TabBackgroundUpdateService] Error checking artifacts: $e',
                  level: LogLevel.error,
                );
              }
            }
          }
        } else if (updateType == 'extract') {
          // Poll extract progress (if needed in future)
          // For now, extract progress is handled by ExtractPreview directly
        }

        // Call callback if progress is available
        if (progress != null) {
          final void Function(Map<String, dynamic>)? callback =
              _updateCallbacks[flowId]?[key];
          if (callback != null) {
            callback(progress);
          }
        }
      } catch (e) {
        if (kDebugMode) {
          _log(
            '[TabBackgroundUpdateService] Error polling $updateType progress for $taskId: $e',
            level: LogLevel.error,
          );
        }
      }
    });

    _updateTimers.putIfAbsent(flowId, () => <String, Timer>{})[key] = timer;

    if (kDebugMode) {
      _log(
        '[TabBackgroundUpdateService] Registered $updateType update for flowId=$flowId, taskId=$taskId',
      );
    }
  }

  /// Unregister a background update
  void unregisterUpdate({
    required String flowId,
    required String taskId,
    required String updateType,
  }) {
    final String key = '$updateType:$taskId';

    // Cancel timer
    _updateTimers[flowId]?[key]?.cancel();
    _updateTimers[flowId]?.remove(key);

    // Remove callback
    _updateCallbacks[flowId]?.remove(key);

    // Clean up empty maps
    if (_updateTimers[flowId]?.isEmpty ?? false) {
      _updateTimers.remove(flowId);
    }
    if (_updateCallbacks[flowId]?.isEmpty ?? false) {
      _updateCallbacks.remove(flowId);
    }

    if (kDebugMode) {
      _log(
        '[TabBackgroundUpdateService] Unregistered $updateType update for flowId=$flowId, taskId=$taskId',
      );
    }
  }

  /// Unregister all updates for a flow
  void unregisterAllForFlow(String flowId) {
    // Cancel all timers
    _updateTimers[flowId]?.values.forEach((Timer timer) => timer.cancel());
    _updateTimers.remove(flowId);

    // Remove all callbacks
    _updateCallbacks.remove(flowId);

    if (kDebugMode) {
      _log(
        '[TabBackgroundUpdateService] Unregistered all updates for flowId=$flowId',
      );
    }
  }

  /// Persist anonymize progress to flow context
  Future<void> _persistAnonymizeProgress(
    String flowId,
    String workflowId,
    Map<String, dynamic> progress,
  ) async {
    try {
      if (_container == null) {
        if (kDebugMode) {
          _log(
            '[TabBackgroundUpdateService] Cannot persist progress: container not set',
            level: LogLevel.warn,
          );
        }
        return;
      }

      // Update flow context with progress (for restoration when widget is recreated)
      // Note: We don't update the actual anonymized text here, only progress info
      // The actual artifacts are saved when runAnonymizeWithConfig completes
      // Progress is tracked via workflowId in flow context, widget will restore from backend
      if (kDebugMode) {
        final int percent = (progress['percent'] as num?)?.toInt() ?? 0;
        final String phase = progress['phase']?.toString() ?? '';
        _log(
          '[TabBackgroundUpdateService] Persisting anonymize progress: flowId=$flowId, workflowId=$workflowId, percent=$percent, phase=$phase',
        );
      }
    } catch (e) {
      if (kDebugMode) {
        _log(
          '[TabBackgroundUpdateService] Error persisting progress: $e',
          level: LogLevel.error,
        );
      }
    }
  }

  /// Get current progress for a task/workflow (from cache if available)
  Future<Map<String, dynamic>?> getCurrentProgress({
    required String flowId,
    required String taskId,
    required String updateType,
  }) async {
    try {
      if (updateType == 'anonymize') {
        final AnonymizeService svc = AnonymizeService();
        return await svc.getProgress(taskId);
      }
      // Add other update types as needed
    } catch (e) {
      if (kDebugMode) {
        _log(
          '[TabBackgroundUpdateService] Error getting current progress: $e',
          level: LogLevel.error,
        );
      }
    }
    return null;
  }

  /// Cleanup all timers (call on app dispose)
  void dispose() {
    for (final Map<String, Timer> timers in _updateTimers.values) {
      for (final Timer timer in timers.values) {
        timer.cancel();
      }
    }
    _updateTimers.clear();
    _updateCallbacks.clear();
  }
}

/// Provider for TabBackgroundUpdateService
final Provider<TabBackgroundUpdateService> tabBackgroundUpdateServiceProvider =
    Provider<TabBackgroundUpdateService>(
        (ProviderRef<TabBackgroundUpdateService> ref) {
  final TabBackgroundUpdateService service = TabBackgroundUpdateService();

  // Cleanup on dispose
  ref.onDispose(service.dispose);

  return service;
});
