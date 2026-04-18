// SPDX-FileCopyrightText: 2025 QinHan
// SPDX-License-Identifier: MPL-2.0

import 'dart:typed_data';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:intl/intl.dart';
import 'package:flutter/foundation.dart' show kIsWeb, kDebugMode;
import 'package:file_picker/file_picker.dart';
import 'package:dio/dio.dart';
import '../../../l10n/app_localizations.dart';
import '../../../shared/utils/io_file_stub.dart' if (dart.library.io) 'dart:io'
    as io;
import '../../../shared/utils/message_service.dart';
import '../../../shared/services/translation_service.dart';
import '../../../shared/services/format_conversion_service.dart';
import '../../tasks/models/persisted_flow_state.dart';
import '../../tasks/providers/tasks_provider.dart';
import '../../tasks/models/task.dart';
import '../../tasks/services/flow_state_persistence.dart';
import '../../tasks/providers/flow_provider.dart';
import '../../tasks/models/flow.dart';
import '../../translation/providers/translation_state_provider_family.dart';
import '../../translation/providers/preview_tabs_provider.dart';
import '../../translation/models/preview_tab.dart';
import '../../translation/widgets/extract_preview.dart';
import '../../translation/widgets/translation_quick_settings.dart'
    show TranslationQuickSettings, translationQuickSettingsProviderFamily;
import '../../anonymize/providers/anonymize_completion_provider.dart';
import '../../../app/app_router.dart';

/// Widget for displaying recent activities (translations and anonymizations)
class RecentActivitiesWidget extends ConsumerStatefulWidget {
  const RecentActivitiesWidget({super.key});

  @override
  ConsumerState<RecentActivitiesWidget> createState() =>
      _RecentActivitiesWidgetState();
}

class _RecentActivitiesWidgetState
    extends ConsumerState<RecentActivitiesWidget> {
  List<Map<String, dynamic>> _recentActivities = <Map<String, dynamic>>[];
  bool _isLoadingActivities = false;
  bool _hasInitialLoad = false;
  
  // Static cache to persist across widget rebuilds
  static List<Map<String, dynamic>>? _cachedActivities;
  static DateTime? _lastCacheTime;
  static const Duration _cacheValidity = Duration(minutes: 5);

  /// Helper function to create File instance (handles web/desktop differences)
  dynamic _createFile(String path) {
    if (kIsWeb) {
      throw UnsupportedError('File operations not supported on web');
    }
    // On desktop, use dart:io File constructor via conditional import alias.
    return io.File(path);
  }

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (mounted && !_hasInitialLoad) {
        _hasInitialLoad = true;
        _loadRecentActivities();
      }
    });
  }

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    // Refresh Recent Activities when returning to Home screen (background refresh, no spinner)
    // Use longer delay to ensure navigation completes first
    if (_hasInitialLoad && mounted) {
      Future.delayed(const Duration(milliseconds: 1000), () {
        if (mounted) {
          _loadRecentActivities(isBackgroundRefresh: true);
        }
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    // Watch tasks and anonymize completion to refresh Recent Activities
    ref.watch(tasksProvider);
    ref.watch(anonymizeCompletionProvider);

    // Use ref.listen to react to changes instead of adding callbacks in build
    ref.listen<AnonymizeCompletionEvent?>(anonymizeCompletionProvider,
        (previous, next) {
      if (next != null && mounted && _hasInitialLoad) {
        // Debounce to avoid excessive calls
        Future.delayed(const Duration(milliseconds: 500), () {
          if (mounted) {
            _loadRecentActivities();
          }
        });
      }
    });

    // Also listen to tasks changes
    ref.listen<TasksState>(tasksProvider, (previous, next) {
      if (previous?.tasks.length != next.tasks.length &&
          mounted &&
          _hasInitialLoad) {
        // Debounce to avoid excessive calls
        Future.delayed(const Duration(milliseconds: 500), () {
          if (mounted) {
            _loadRecentActivities();
          }
        });
      }
    });

    final l10n = AppLocalizations.of(context)!;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      mainAxisSize: MainAxisSize.min,
      children: <Widget>[
        Row(
          mainAxisAlignment: MainAxisAlignment.spaceBetween,
          children: <Widget>[
            Text(
              l10n.homeRecentActivity,
              style: TextStyle(
                fontSize: 20,
                fontWeight: FontWeight.bold,
                color: Theme.of(context).colorScheme.primary,
              ),
            ),
            if (_recentActivities.isNotEmpty)
              TextButton.icon(
                onPressed: _loadRecentActivities,
                icon: const Icon(Icons.refresh, size: 16),
                label: Text(l10n.homeRecentRefresh),
                style: TextButton.styleFrom(
                  padding:
                      const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                ),
              ),
          ],
        ),
        const SizedBox(height: 16),
        Card(
          elevation: 2,
          child: _isLoadingActivities
              ? const Padding(
                  padding: EdgeInsets.all(24),
                  child: Center(
                    child: CircularProgressIndicator(),
                  ),
                )
              : _recentActivities.isEmpty
                  ? SingleChildScrollView(
                      padding: const EdgeInsets.all(16),
                      child: Column(
                        mainAxisSize: MainAxisSize.min,
                        children: <Widget>[
                          _buildActivityItem(
                            icon: Icons.translate,
                            title: l10n.homeRecentNoTranslations,
                            subtitle: l10n.homeRecentNoTranslationsHint,
                            color: Colors.grey,
                          ),
                          const SizedBox(height: 12),
                          _buildActivityItem(
                            icon: Icons.security,
                            title: l10n.homeRecentNoAnonymization,
                            subtitle: l10n.homeRecentNoAnonymizationHint,
                            color: Colors.grey,
                          ),
                        ],
                      ),
                    )
                  : ListView.separated(
                      padding: const EdgeInsets.all(8),
                      shrinkWrap: true,
                      physics: const NeverScrollableScrollPhysics(),
                      itemCount: _recentActivities.length,
                      separatorBuilder: (BuildContext context, int index) =>
                          const Divider(height: 1),
                      itemBuilder: (BuildContext context, int index) {
                        final Map<String, dynamic> activity =
                            _recentActivities[index];
                        return _buildRecentActivityItem(activity);
                      },
                    ),
        ),
      ],
    );
  }

  /// Load recent activities. When [isBackgroundRefresh] is true (e.g. returning to Home),
  /// keep showing previous list and do not show spinner to avoid perceived lag.
  // Maximum number of flows to load in parallel to avoid blocking UI
  static const int _maxFlowsToLoad = 50;
  
  Future<void> _loadRecentActivities({bool isBackgroundRefresh = false}) async {
    if (_isLoadingActivities) return;
    
    // Check cache first
    if (!isBackgroundRefresh && _cachedActivities != null && _lastCacheTime != null) {
      final cacheAge = DateTime.now().difference(_lastCacheTime!);
      if (cacheAge < _cacheValidity) {
        setState(() {
          _recentActivities = _cachedActivities!;
          _isLoadingActivities = false;
        });
        // Still refresh in background if cache is older than 1 minute
        if (cacheAge > const Duration(minutes: 1)) {
          Future.delayed(const Duration(milliseconds: 500), () {
            if (mounted) _loadRecentActivities(isBackgroundRefresh: true);
          });
        }
        return;
      }
    }

    if (!isBackgroundRefresh) {
      setState(() {
        _isLoadingActivities = true;
      });
    }

    try {
      final List<String> allFlowIds = await FlowStatePersistence.getAllFlowIds();
      
      // Only load the most recent flows to avoid blocking UI
      // Take the last N flows (most recent based on ID which is timestamp-based)
      final List<String> flowIds = allFlowIds.length > _maxFlowsToLoad
          ? allFlowIds.sublist(allFlowIds.length - _maxFlowsToLoad)
          : allFlowIds;
      
      final List<Map<String, dynamic>> activities = <Map<String, dynamic>>[];

      var loadStart = DateTime.now();
      // Load flows in batches to avoid overwhelming SharedPreferences
      // Process in chunks of 10 for better performance without contention
      const int batchSize = 10;
      for (int i = 0; i < flowIds.length; i += batchSize) {
        final batch = flowIds.skip(i).take(batchSize).toList();
        final batchFutures = batch.map((flowId) async {
          final PersistedFlowState? flowState =
              await FlowStatePersistence.loadFlowState(flowId);
          if (flowState == null || flowState.isExpired) return;

          final PersistedStepsState? stepsState = flowState.uiState.stepsState;
          final PersistedFlowContext context = flowState.context;

          if ((stepsState?.translateCompleted ?? false) &&
              context.translateTaskId != null) {
            activities.add(<String, dynamic>{
              'flowId': flowId,
              'title': flowState.title,
              'type': 'translation',
              'flowType': flowState.flowType,
              'fileName': context.sourceFileName ?? 'Text Input',
              'filePath': context.sourceFilePath,
              'completedAt':
                  context.translateTaskCreatedAt ?? flowState.updatedAt,
              'taskId': context.translateTaskId,
              'stats': context.translateStats,
              'flowState': flowState,
            });
          }
          if ((stepsState?.anonymizeCompleted ?? false) &&
              context.anonymizedText != null) {
            activities.add(<String, dynamic>{
              'flowId': flowId,
              'title': flowState.title,
              'type': 'anonymization',
              'flowType': flowState.flowType,
              'fileName': context.sourceFileName ?? 'Text Input',
              'filePath': context.sourceFilePath,
              'completedAt': flowState.updatedAt,
              'flowState': flowState,
            });
          }
        }).toList();
        
        await Future.wait(batchFutures);
        
        // Small yield between batches to allow UI to breathe
        if (i + batchSize < flowIds.length) {
          await Future.delayed(Duration.zero);
        }
      }

      activities.sort((Map<String, dynamic> a, Map<String, dynamic> b) {
        final DateTime aTime = a['completedAt'] as DateTime;
        final DateTime bTime = b['completedAt'] as DateTime;
        return bTime.compareTo(aTime);
      });

      if (mounted) {
        final displayActivities = activities.take(5).toList();
        setState(() {
          _recentActivities = displayActivities;
          _isLoadingActivities = false;
        });
        // Update cache
        _cachedActivities = List<Map<String, dynamic>>.from(displayActivities);
        _lastCacheTime = DateTime.now();
      }
    } catch (e) {
      debugPrint('Error loading recent activities: $e');
      if (mounted) {
        setState(() {
          _isLoadingActivities = false;
        });
      }
    }
  }

  String _formatRelativeTime(DateTime dateTime) {
    final l10n = AppLocalizations.of(context)!;
    final DateTime now = DateTime.now();
    final Duration difference = now.difference(dateTime);

    if (difference.inDays > 7) {
      return DateFormat('MMM d, yyyy').format(dateTime);
    } else if (difference.inDays > 0) {
      return difference.inDays == 1
          ? l10n.homeTimeOneDayAgo
          : l10n.homeTimeDaysAgo(difference.inDays);
    } else if (difference.inHours > 0) {
      return difference.inHours == 1
          ? l10n.homeTimeOneHourAgo
          : l10n.homeTimeHoursAgo(difference.inHours);
    } else if (difference.inMinutes > 0) {
      return difference.inMinutes == 1
          ? l10n.homeTimeOneMinuteAgo
          : l10n.homeTimeMinutesAgo(difference.inMinutes);
    } else {
      return l10n.homeTimeJustNow;
    }
  }

  IconData _getActivityIcon(String type, TaskFlow flowType) {
    if (type == 'translation') {
      return Icons.translate;
    } else if (type == 'anonymization') {
      return Icons.security;
    }
    return Icons.description;
  }

  Color _getActivityColor(String type, BuildContext context) {
    if (type == 'translation') {
      return Colors.blue;
    } else if (type == 'anonymization') {
      return Colors.orange;
    }
    return Theme.of(context).colorScheme.onSurfaceVariant;
  }

  String _getActivityTypeLabel(String type, TaskFlow flowType) {
    final l10n = AppLocalizations.of(context)!;
    if (type == 'translation') {
      if (flowType == TaskFlow.anonymizeAndTranslate) {
        return l10n.homeActivityTypeAnonymizeTranslate;
      }
      return l10n.homeActivityTypeTranslation;
    } else if (type == 'anonymization') {
      return l10n.homeActivityTypeAnonymization;
    }
    return l10n.homeActivityTypeActivity;
  }

  /// Check whether backend still has data for a translation task.
  Future<bool> _hasBackendDataForTranslation(String taskId) async {
    try {
      final TranslationService service = TranslationService();
      await service.getStatus(taskId);
      // If no exception thrown, backend still knows this task.
      return true;
    } on DioException catch (e) {
      final int? statusCode = e.response?.statusCode;
      if (statusCode == 404) {
        debugPrint('Translation task not found on backend (404): $taskId');
      } else {
        debugPrint(
          'Error checking translation task status ($taskId): $e (status=$statusCode)',
        );
      }
      return false;
    } catch (e) {
      debugPrint(
        'Unexpected error checking translation task status ($taskId): $e',
      );
      return false;
    }
  }

  /// Try to reopen existing Flow (strategy 1) when backend data still exists.
  /// Returns true if Flow was opened, false if caller should fallback to re-import (strategy 2).
  Future<bool> _tryOpenExistingFlowIfBackendAlive(
    Map<String, dynamic> activity,
  ) async {
    final String type = activity['type'] as String? ?? '';
    if (type != 'translation') {
      // Currently only translation flows depend on backend translation task.
      return false;
    }

    final String? taskId = activity['taskId'] as String?;
    final PersistedFlowState? flowState =
        activity['flowState'] as PersistedFlowState?;

    if (taskId == null || taskId.isEmpty || flowState == null) {
      return false;
    }

    final bool hasBackend = await _hasBackendDataForTranslation(taskId);
    if (!hasBackend) {
      return false;
    }

    try {
      final TasksNotifier notifier = ref.read(tasksProvider.notifier);
      await notifier.restoreFlowFromPersisted(flowState);

      if (mounted) {
        context.go(AppRouter.homeRoute);
      }
      return true;
    } catch (e) {
      debugPrint('Error restoring Flow from persisted state: $e');
      return false;
    }
  }

  /// Strategy 2 helper: when backend has no data, create a new Flow and
  /// start Extract by calling format-conversion, then open Extract tab.
  Future<void> _startExtractForNewFlow(Task task, PlatformFile selectedFile) async {
    try {
      final Uint8List? bytes = selectedFile.bytes;
      if (bytes == null) {
        debugPrint(
          '[_startExtractForNewFlow] Selected file has no bytes; skip auto-extract. name=${selectedFile.name}',
        );
        return;
      }

      // Get target language from Translation Quick Settings for this flow (if available)
      final TranslationQuickSettings qs =
          ref.read(translationQuickSettingsProviderFamily(task.id));
      final String? toLang = qs.toLang.isNotEmpty ? qs.toLang : null;

      final FormatConversionService formatSvc = FormatConversionService();
      final Map<String, dynamic> convertRes = await formatSvc.convertFormat(
        fileBytes: bytes,
        fileName: selectedFile.name,
        skipCache: true,
        toLang: toLang,
      );

      if (convertRes['success'] == true) {
        final Map<String, dynamic> data =
            (convertRes['data'] as Map).cast<String, dynamic>();
        final String? taskId = data['task_id']?.toString();
        if (taskId == null || taskId.isEmpty) {
          debugPrint(
            '[_startExtractForNewFlow] convert-format succeeded but task_id is null/empty',
          );
          return;
        }

        // Save taskId into translation state for this flow
        final TranslationStateFamilyNotifier translationNotifier = ref.read(
          translationStateProviderFamily(task.id).notifier,
        );
        translationNotifier.setTaskId(taskId);

        // Open Extract tab immediately
        final PreviewTabsNotifier tabsNotifier =
            ref.read(previewTabsProviderFamily(task.id).notifier);
        final ExtractPreview extractContent = ExtractPreview(
          taskId: taskId,
          flowId: task.id,
        );
        final PreviewTab tab = PreviewTab(
          id: 'extract_tab',
          type: PreviewTabType.translationResult,
          title: 'Extract',
          icon: Icons.fact_check,
          content: extractContent,
          dataRef: <String, dynamic>{
            'taskId': taskId,
            'flowId': task.id,
          },
        );
        tabsNotifier.updateOrAddTab(tab);
      } else {
        final Object? err = convertRes['error'];
        debugPrint(
          '[_startExtractForNewFlow] convert-format failed: $err',
        );
        if (mounted) {
          MessageService.showError(
            context,
            AppLocalizations.of(context)!.homeFileLoadFailed(
              err?.toString() ?? 'convert-format failed',
            ),
          );
        }
      }
    } catch (e, stack) {
      debugPrint(
        '[_startExtractForNewFlow] Unexpected error: $e\n$stack',
      );
      if (mounted) {
        MessageService.showError(
          context,
          AppLocalizations.of(context)!.homeFileLoadFailed(e.toString()),
        );
      }
    }
  }

  /// Handle activity item click - create new flow and load file
  Future<void> _handleActivityClick(Map<String, dynamic> activity) async {
    // Strategy 1: if backend still has data for this translation task,
    // reopen existing Flow instead of re-importing.
    final bool reopened =
        await _tryOpenExistingFlowIfBackendAlive(activity);
    if (reopened) {
      return;
    }

    final TaskFlow flowType = activity['flowType'] as TaskFlow;
    final String type = activity['type'] as String;
    final String? fileName = activity['fileName'] as String?;
    final String? filePath = activity['filePath'] as String?;

    // If it's text input, just create flow and navigate
    if (fileName == 'Text Input' || fileName == null) {
      _createFlowAndNavigate(flowType);
      return;
    }

    // Check if file exists first (only on desktop, not web)
    // If filePath is null, we'll use file picker (path was not persisted)
    var fileExists = false;
    var shouldCheckFile = false;

    if (!kIsWeb && filePath != null) {
      shouldCheckFile = true;
      try {
        final file = _createFile(filePath);
        fileExists = await file.exists() as bool;
      } catch (e) {
        debugPrint('Error checking file existence: $e');
        fileExists = false;
      }
    }

    // If file path was provided but file doesn't exist, show error and don't create flow
    if (shouldCheckFile && !fileExists) {
      if (mounted) {
        MessageService.showError(
          context,
          AppLocalizations.of(context)!.homeFileNotFound(fileName),
        );
      }
      return;
    }

    // If filePath is null, we'll use file picker to let user select the file
    // This is expected behavior when file path was not persisted

    // File exists (or on web where we can't check), create flow and load file
    try {
      // First create the flow
      final TasksNotifier notifier = ref.read(tasksProvider.notifier);
      final Task task = await notifier.createFlow(
        sourceType: TaskType.file,
        flowType: flowType,
      );

      // Navigate to workspace
      if (mounted) {
        context.go(AppRouter.homeRoute);
        await Future.delayed(const Duration(milliseconds: 300));
      }

      // Load the file
      if (mounted) {
        PlatformFile? selectedFile;

        if (!kIsWeb && filePath != null && fileExists) {
          // On desktop, try to load from path
          try {
            final file = _createFile(filePath);
            final List<int> bytes = await file.readAsBytes() as List<int>;
            selectedFile = PlatformFile(
              name: fileName,
              path: filePath,
              bytes: Uint8List.fromList(bytes),
              size: bytes.length,
            );
          } catch (e) {
            debugPrint('Error reading file from path: $e');
            // Fall through to file picker
          }
        }

        // If we couldn't load from path, use file picker
        if (selectedFile == null) {
          final FilePickerResult? result = await FilePicker.platform.pickFiles(
            type: FileType.custom,
            withData: true,
          );

          if (result != null) {
            final PlatformFile pickedFile = result.files.single;
            // Verify the file name matches (user should select the correct file)
            if (pickedFile.name != fileName) {
              if (mounted) {
                MessageService.showWarning(
                  context,
                  AppLocalizations.of(context)!.homeFileSelectedMismatch(
                    pickedFile.name,
                    fileName,
                  ),
                );
              }
              // Still allow loading if user confirms
            }
            selectedFile = pickedFile;
          }
        }

        if (selectedFile != null) {
          // File found, load it into the flow
          final FlowStateNotifier flowNotifier = ref.read(
            flowProviderFamily(task.id).notifier,
          );
          flowNotifier.updateSource(
            FlowSource(
              fileName: selectedFile.name,
              filePath: selectedFile.path,
            ),
          );

          // Set the file in the translation state (for TranslationScreen/AnonymizeScreen)
          // This ensures the file is available when the screen loads
          final TranslationStateFamilyNotifier translationNotifier = ref.read(
            translationStateProviderFamily(task.id).notifier,
          );
          translationNotifier.setPickedFile(selectedFile);

          if (mounted) {
            MessageService.showSuccess(
              context,
              AppLocalizations.of(context)!.homeFileLoaded(selectedFile.name),
            );
          }

          // For translation-type activities and when backend has no data,
          // auto-start Extract by running format-conversion.
          if (type == 'translation') {
            await _startExtractForNewFlow(task, selectedFile);
          }
        } else {
          // User cancelled file selection
          if (mounted) {
            MessageService.showInfo(
              context,
              AppLocalizations.of(context)!.homeFileSelectionCancelled,
            );
            // Remove the created flow since no file was selected
            notifier.closeTask(task.id);
          }
        }
      }
    } catch (e) {
      debugPrint('Error loading file for activity: $e');
      if (mounted) {
        MessageService.showError(
          context,
          AppLocalizations.of(context)!.homeFileLoadFailed(e.toString()),
        );
        // Try to clean up the flow if it was created
        try {
          final TasksNotifier notifier = ref.read(tasksProvider.notifier);
          final TasksState tasks = ref.read(tasksProvider);
          if (tasks.tasks.isNotEmpty) {
            notifier.closeTask(tasks.tasks.last.id);
          }
        } catch (_) {
          // Ignore cleanup errors
        }
      }
    }
  }

  /// Create flow and navigate (for text input or when file loading fails)
  Future<void> _createFlowAndNavigate(TaskFlow flowType) async {
    try {
      // Navigate to workspace first
      if (mounted) {
        context.go(AppRouter.homeRoute);
      }

      // Wait a bit for navigation to complete
      await Future.delayed(const Duration(milliseconds: 300));

      // Create flow
      if (mounted) {
        final TasksNotifier notifier = ref.read(tasksProvider.notifier);
        await notifier.createFlow(
          sourceType: TaskType.file,
          flowType: flowType,
        );
      }
    } catch (e) {
      debugPrint('Error creating flow: $e');
      if (mounted) {
        MessageService.showError(
          context,
          AppLocalizations.of(context)!.homeFlowCreateFailed(e.toString()),
        );
      }
    }
  }

  Widget _buildRecentActivityItem(Map<String, dynamic> activity) {
    final String type = activity['type'] as String;
    final TaskFlow flowType = activity['flowType'] as TaskFlow;
    final String title = activity['title'] as String;
    final String? fileName = activity['fileName'] as String?;
    final DateTime completedAt = activity['completedAt'] as DateTime;

    final IconData icon = _getActivityIcon(type, flowType);
    final Color color = _getActivityColor(type, context);
    final String typeLabel = _getActivityTypeLabel(type, flowType);

    return InkWell(
      onTap: () => _handleActivityClick(activity),
      borderRadius: BorderRadius.circular(8),
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 12),
        child: Row(
          children: <Widget>[
            Container(
              padding: const EdgeInsets.all(8),
              decoration: BoxDecoration(
                color: color.withOpacity(0.1),
                borderRadius: BorderRadius.circular(8),
              ),
              child: Icon(icon, color: color, size: 20),
            ),
            const SizedBox(width: 12),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: <Widget>[
                  // Title row
                  Row(
                    children: <Widget>[
                      Expanded(
                        child: Text(
                          title,
                          style: const TextStyle(
                            fontWeight: FontWeight.w600,
                            fontSize: 14,
                          ),
                          maxLines: 1,
                          overflow: TextOverflow.ellipsis,
                        ),
                      ),
                      const SizedBox(width: 8),
                      Container(
                        padding: const EdgeInsets.symmetric(
                          horizontal: 6,
                          vertical: 2,
                        ),
                        decoration: BoxDecoration(
                          color: color.withOpacity(0.1),
                          borderRadius: BorderRadius.circular(4),
                        ),
                        child: Text(
                          typeLabel,
                          style: TextStyle(
                            fontSize: 10,
                            fontWeight: FontWeight.w500,
                            color: color,
                          ),
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 6),
                  // File name row (more prominent)
                  if (fileName != null && fileName != 'Text Input')
                    Row(
                      children: <Widget>[
                        Icon(
                          Icons.description,
                          size: 14,
                          color: Theme.of(context).colorScheme.primary,
                        ),
                        const SizedBox(width: 4),
                        Expanded(
                          child: Text(
                            fileName,
                            style: TextStyle(
                              fontSize: 13,
                              fontWeight: FontWeight.w500,
                              color: Theme.of(context).colorScheme.primary,
                            ),
                            maxLines: 1,
                            overflow: TextOverflow.ellipsis,
                          ),
                        ),
                      ],
                    ),
                  const SizedBox(height: 4),
                  // Time row
                  Row(
                    children: <Widget>[
                      Icon(
                        Icons.access_time,
                        size: 12,
                        color: Theme.of(context).colorScheme.onSurfaceVariant,
                      ),
                      const SizedBox(width: 4),
                      Text(
                        _formatRelativeTime(completedAt),
                        style: TextStyle(
                          fontSize: 12,
                          color: Theme.of(context).colorScheme.onSurfaceVariant,
                        ),
                      ),
                    ],
                  ),
                ],
              ),
            ),
            const SizedBox(width: 8),
            Icon(
              Icons.chevron_right,
              size: 20,
              color: Theme.of(context).colorScheme.onSurfaceVariant,
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildActivityItem({
    required IconData icon,
    required String title,
    required String subtitle,
    required Color color,
  }) =>
      Row(
        children: <Widget>[
          Icon(icon, color: color, size: 20),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: <Widget>[
                Text(
                  title,
                  style: const TextStyle(fontWeight: FontWeight.w500),
                ),
                Text(
                  subtitle,
                  style: TextStyle(
                    fontSize: 12,
                    color: Theme.of(context).colorScheme.onSurfaceVariant,
                  ),
                ),
              ],
            ),
          ),
        ],
      );
}
