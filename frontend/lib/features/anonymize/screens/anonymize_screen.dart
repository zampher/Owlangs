// SPDX-FileCopyrightText: 2025 QinHan
// SPDX-License-Identifier: MPL-2.0

import 'dart:io';
import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:file_picker/file_picker.dart';
import 'package:flutter/foundation.dart' show kDebugMode, debugPrint;
import '../../../core/utils/file_picker_helper.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../../shared/services/anonymize_service.dart';
import '../../../shared/services/format_conversion_service.dart';
import '../../../shared/services/glossary_generation_service.dart';
import '../../../shared/services/translation_service.dart';
import '../../../shared/providers/settings_provider.dart';
import '../../../shared/utils/message_service.dart';
import '../../translation/widgets/translation_quick_settings.dart';
import '../../settings/screens/ai_platform_settings.dart';
import '../../translation/providers/translation_refresh_provider.dart';
import 'dart:typed_data';
import 'dart:convert';
import '../../tasks/providers/flow_provider.dart';
import '../../tasks/models/flow.dart';
import '../../tasks/providers/tasks_provider.dart';
import '../../tasks/models/task.dart';
import '../../tasks/models/persisted_flow_state.dart';
import '../../tasks/services/flow_state_persistence.dart';
import '../widgets/anonymization_quick_settings.dart';
import '../../translation/providers/translation_state_provider.dart';
import '../../translation/providers/translation_state_provider_family.dart';
import '../../translation/providers/preview_tabs_provider.dart';
import '../../translation/models/preview_tab.dart';
import '../../translation/widgets/extract_preview.dart';
import '../../translation/widgets/glossary_preview.dart';
import '../../tasks/providers/version_stack_provider.dart';
import '../../../shared/widgets/file_upload_area.dart';
import '../../../shared/widgets/document_card.dart';
import '../../../shared/widgets/text_input_area.dart';
import '../../../shared/widgets/preview_panel.dart';
import '../widgets/anonymized_result_view.dart';
import '../../tasks/services/flow_data_cache.dart';
import '../providers/anonymize_completion_provider.dart';
import '../../translation/services/tab_background_update_service.dart';

class AnonymizeScreen extends ConsumerStatefulWidget {
  const AnonymizeScreen({super.key, this.flowId});
  final String? flowId;

  @override
  ConsumerState<AnonymizeScreen> createState() => _AnonymizeScreenState();
}

class _AnonymizeScreenState extends ConsumerState<AnonymizeScreen> {
  final bool _isTextMode = false; // false = File mode, true = Text mode
  late final TextEditingController _textController;
  bool _isPickingFile = false; // Flag to prevent duplicate file picker dialogs
  bool _hasShownMineruTokenPrompt = false;

  final List<String> _supportedFileExtensions = <String>[
    'pdf',
    'docx',
    'txt',
    'md',
    'html',
    'epub',
    'mobi',
    'azw',
  ];

  PersistedStepsState? _persistedStepsState; // Cache persisted steps state

  @override
  void initState() {
    super.initState();
    _textController = TextEditingController();
    // Initialize text version stack if flowId exists
    if (widget.flowId != null) {
      WidgetsBinding.instance.addPostFrameCallback((_) {
        ref
            .read(textVersionStackProvider(widget.flowId!).notifier)
            .initialize('');
      });
    }
    // Load persisted steps state immediately (lightweight, uses cache)
    WidgetsBinding.instance.addPostFrameCallback((_) {
      _loadPersistedStepsState();
    });
    // Load persisted tabs in background (delayed to avoid blocking UI)
    WidgetsBinding.instance.addPostFrameCallback((_) {
      Future.delayed(const Duration(milliseconds: 100), () {
        if (mounted) {
          _loadPersistedTabs();
        }
      });
    });
  }

  @override
  void dispose() {
    _textController.dispose();
    super.dispose();
  }

  /// Load persisted steps state from Flow state (using cache)
  Future<void> _loadPersistedStepsState() async {
    if (widget.flowId == null) return;
    try {
      // Use cache to avoid repeated SharedPreferences reads
      final cache = FlowDataCache();
      final stepsState = await cache.getStepsState(widget.flowId!);
      if (stepsState != null && mounted) {
        setState(() {
          _persistedStepsState = stepsState;
        });
      }
    } catch (_) {
      // Ignore errors
    }
  }

  Future<void> _loadPersistedTabs() async {
    if (widget.flowId == null) return;
    final tabsNotifier = widget.flowId != null
        ? ref.read(previewTabsProviderFamily(widget.flowId!).notifier)
        : ref.read(previewTabsProvider.notifier);

    // Use cache to avoid repeated SharedPreferences reads
    final cache = FlowDataCache();
    final tabsData = await cache.getTabsData(widget.flowId);
    final closedTabsData = await cache.getClosedTabsData(widget.flowId);

    // Recreate tabs from persisted data
    // Allow Extract tabs to be restored (they use translationResult type but are essential)
    for (final tabData in tabsData) {
      final typeStr = tabData['type'] as String? ?? '';
      final title = tabData['title'] as String? ?? '';

      // Skip translationResult tabs EXCEPT Extract tabs (which are essential for file upload flows)
      if (typeStr == 'PreviewTabType.translationResult' && title != 'Extract') {
        continue;
      }

      final tab = _recreateTabFromData(tabData);
      if (tab != null) {
        tabsNotifier.addTab(tab);
      }
    }

    // Recreate closed tabs (also allow Extract tabs)
    final closedTabs = <PreviewTab>[];
    for (final tabData in closedTabsData) {
      final typeStr = tabData['type'] as String? ?? '';
      final title = tabData['title'] as String? ?? '';

      // Skip translationResult tabs EXCEPT Extract tabs
      if (typeStr == 'PreviewTabType.translationResult' && title != 'Extract') {
        continue;
      }

      final tab = _recreateTabFromData(tabData);
      if (tab != null) {
        closedTabs.add(tab);
      }
    }
    if (closedTabs.isNotEmpty) {
      tabsNotifier.setClosedTabs(closedTabs);
    }
  }

  PreviewTab? _recreateTabFromData(Map<String, dynamic> tabData) {
    try {
      final type = PreviewTabType.values.firstWhere(
        (e) => e.toString() == tabData['type'],
        orElse: () => PreviewTabType.translationResult,
      );
      final dataRef = tabData['dataRef'] is Map
          ? (tabData['dataRef'] as Map).cast<String, dynamic>()
          : null;

      Widget content;
      final title =
          tabData['title'] is String ? tabData['title'] as String : 'Preview';

      switch (type) {
        case PreviewTabType.formatConversion:
          final taskId = dataRef?['taskId'] as String? ?? '';
          content = Container(
            padding: const EdgeInsets.all(16),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: <Widget>[
                Row(
                  children: <Widget>[
                    Icon(
                      Icons.transform,
                      size: 20,
                      color: Theme.of(context).colorScheme.primary,
                    ),
                    const SizedBox(width: 8),
                    Text(
                      'Format Conversion Result',
                      style: TextStyle(
                        fontSize: 16,
                        fontWeight: FontWeight.bold,
                        color: Theme.of(context).colorScheme.primary,
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 16),
                Text('Task ID: $taskId'),
              ],
            ),
          );
          break;
        case PreviewTabType.translationResult:
          // Handle Extract tab restoration
          if (title == 'Extract') {
            final taskId = dataRef?['taskId'] as String? ?? '';
            final flowId = dataRef?['flowId'] as String? ?? widget.flowId;

            if (taskId.isNotEmpty) {
              content = ExtractPreview(
                key: ValueKey('extract_${flowId}_$taskId'),
                taskId: taskId,
                flowId: flowId,
                onAnonymizeComplete: _onAnonymizeCompleteFromExtract,
              );
              break;
            } else {
              // No taskId, cannot restore Extract tab
              if (kDebugMode) {
                debugPrint(
                  '[AnonymizeScreen] _recreateTabFromData: Extract tab missing taskId, skipping',
                );
              }
              return null;
            }
          }
          // For other translationResult tabs (e.g., Translation Result, Anonymized Result),
          // they should be handled by their respective screens or return null
          return null;
        default:
          return null;
      }

      // Create tab without icon - will use defaultIcon (compile-time constant)
      // This ensures IconData is a compile-time constant for tree-shaking
      return PreviewTab(
        id: tabData['id'] as String? ?? '',
        type: type,
        title: title,
        content: content,
        createdAt: tabData['createdAt'] != null
            ? DateTime.parse(tabData['createdAt'] as String)
            : null,
        dataRef: dataRef,
      );
    } catch (e) {
      if (kDebugMode) {
        debugPrint('Error recreating tab: $e');
      }
      return null;
    }
  }

  bool _shouldShowTopToolbar(state) {
    // Check if this is Anonymize+Translate flow
    final tasks = widget.flowId != null ? ref.watch(tasksProvider) : null;
    final task = tasks?.tasks.firstWhere(
      (t) => t.id == widget.flowId,
      orElse: () => Task(
        id: widget.flowId!,
        type: TaskType.file,
        title: '',
        createdAt: DateTime.now(),
        updatedAt: DateTime.now(),
        currentFlow: TaskFlow.anonymize,
        plannedPhases: <PipelinePhase>[],
      ),
    );
    final isAnonymizeAndTranslate =
        task?.currentFlow == TaskFlow.anonymizeAndTranslate;

    // Show toolbar for Anonymize+Translate flow (has Glossary, Translate All buttons)
    // For pure Anonymize flow, toolbar is in Extract tab
    return isAnonymizeAndTranslate;
  }

  @override
  Widget build(BuildContext context) {
    // Listen to anonymize completion events (even when flow is not active)
    // This allows handling completion events from ExtractPreview even when this screen is hidden
    final completionEvent = ref.watch(anonymizeCompletionProvider);
    if (completionEvent != null && completionEvent.flowId == widget.flowId) {
      // Handle completion event asynchronously to avoid build-time side effects
      // Use a small delay to ensure the event is stable and all listeners can process it
      WidgetsBinding.instance.addPostFrameCallback((_) {
        if (mounted) {
          // Double-check the event is still for this flow (in case it was cleared)
          final currentEvent = ref.read(anonymizeCompletionProvider);
          if (currentEvent != null && currentEvent.flowId == widget.flowId) {
            _handleAnonymizeCompletionEvent();
          }
        }
      });
    }

    // Verify that this widget's flowId matches the active task to prevent state confusion
    if (widget.flowId != null) {
      final tasks = ref.watch(tasksProvider);
      // Only render content if this flow is currently active
      if (tasks.activeTaskId != widget.flowId) {
        // This flow is not active, return empty widget to prevent state confusion
        // But we still listen to completion events above, so completion will be handled
        return const SizedBox.shrink();
      }
    }

    final dynamic translationState = widget.flowId != null
        ? ref.watch(translationStateProviderFamily(widget.flowId!))
        : ref.watch(translationStateProvider);
    final dynamic translationNotifier = widget.flowId != null
        ? ref.read(translationStateProviderFamily(widget.flowId!).notifier)
        : ref.read(translationStateProvider.notifier);
    final tabsState = widget.flowId != null
        ? ref.watch(previewTabsProviderFamily(widget.flowId!))
        : ref.watch(previewTabsProvider);

    // Check if flow just became active and switch to the appropriate tab based on flow state
    // This handles the case where steps completed while flow was inactive
    if (widget.flowId != null) {
      final tasks = ref.watch(tasksProvider);
      if (tasks.activeTaskId == widget.flowId) {
        // Flow is active, check if we need to switch to the appropriate tab
        // Use a small delay to ensure tabs are loaded before checking
        WidgetsBinding.instance.addPostFrameCallback((_) {
          if (mounted) {
            // Use a small delay to ensure all state is ready
            Future.delayed(const Duration(milliseconds: 100), () {
              if (mounted) {
                _checkAndSwitchToCurrentStepTab();
              }
            });
          }
        });
      }
    }

    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: <Widget>[
        // Toolbar at the top (only for Anonymize+Translate flow)
        // For pure Anonymize flow, toolbar is moved to Extract tab
        if (_shouldShowTopToolbar(translationState))
          _buildToolbar(translationState, translationNotifier),
        // Content area
        Expanded(
          child: Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: <Widget>[
              // Left Panel (1/4 width)
              Expanded(
                child: SingleChildScrollView(
                  padding: const EdgeInsets.all(16),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.stretch,
                    children: <Widget>[
                      // Document Card
                      DocumentCard(pickedFile: translationState.pickedFile),
                      const SizedBox(height: 24),
                      // Anonymization Quick Settings
                      AnonymizationQuickSettingsWidget(flowId: widget.flowId),
                    ],
                  ),
                ),
              ),
              const SizedBox(width: 16),
              // Right Panel - Preview Area (3/4 width)
              Expanded(
                flex: 3,
                child: _buildPreviewPanel(
                  translationState,
                  translationNotifier,
                  tabsState,
                ),
              ),
            ],
          ),
        ),
      ],
    );
  }

  Widget _buildToolbar(state, notifier) {
    // Verify that this widget's flowId matches the active task to prevent state confusion
    if (widget.flowId != null) {
      final tasks = ref.watch(tasksProvider);
      // Only show toolbar if this flow is currently active
      if (tasks.activeTaskId != widget.flowId) {
        // This flow is not active, return empty toolbar to prevent state confusion
        return const SizedBox.shrink();
      }
    }

    // Double-check: verify flow is still active before accessing providers
    // This prevents accessing providers for inactive flows
    final tasks = ref.watch(tasksProvider);
    if (widget.flowId != null && tasks.activeTaskId != widget.flowId) {
      return const SizedBox.shrink();
    }

    // Get flow context to check completion status
    // Only access providers if flow is active (checked above)
    final flow = widget.flowId != null
        ? ref.watch(flowProviderFamily(widget.flowId!))
        : null;
    final flowNotifier = widget.flowId != null
        ? ref.read(flowProviderFamily(widget.flowId!).notifier)
        : null;

    // Check if this is Anonymize+Translate flow
    final task = tasks.tasks.firstWhere(
      (t) => t.id == widget.flowId,
      orElse: () => Task(
        id: widget.flowId!,
        type: TaskType.file,
        title: '',
        createdAt: DateTime.now(),
        updatedAt: DateTime.now(),
        currentFlow: TaskFlow.anonymize,
        plannedPhases: <PipelinePhase>[],
      ),
    );

    // Triple-check: ensure task ID matches widget flowId and is active
    if (task.id != widget.flowId || tasks.activeTaskId != widget.flowId) {
      return const SizedBox.shrink();
    }

    final isAnonymizeAndTranslate =
        task.currentFlow == TaskFlow.anonymizeAndTranslate;

    // Verify state belongs to this flow (state should already be isolated by flowId, but double-check)
    // Check if file exists: either pickedFile is set, or taskId exists (file was processed), or source fileName exists (restored from persistence)
    final sourceFileName = flow?.context.source.fileName;
    final hasFile = state.pickedFile != null ||
        (state.taskId != null && (state.taskId as String).isNotEmpty) ||
        (sourceFileName != null && sourceFileName.isNotEmpty) ||
        (_isTextMode && _textController.text.trim().isNotEmpty);
    final isAnonymizeCompleted = flow?.context.anonymize.anonymizedText != null;
    final workflowId = flow?.context.anonymize.workflowId;

    // De-anonymize is handled in dedicated view when needed; no inline check required

    return Container(
      constraints: const BoxConstraints(
        minHeight: 36,
        maxHeight: 36,
      ), // Fixed height at 36px
      decoration: BoxDecoration(
        color: Theme.of(context).colorScheme.surfaceContainerHighest,
        border: Border(
          bottom: BorderSide(
            color: Theme.of(context).dividerColor,
          ),
        ),
      ),
      padding: const EdgeInsets.symmetric(
        horizontal: 16,
        vertical: 8,
      ), // Reduced vertical padding to fit 36px height
      child: Row(
        children: <Widget>[
          // Left side: Main operations
          if (isAnonymizeAndTranslate) ...<Widget>[
            // Extract button (only for Anonymize+Translate)
            OutlinedButton.icon(
              onPressed: (hasFile &&
                      !state.isTranslating &&
                      tasks.activeTaskId == widget.flowId)
                  ? () {
                      // Final check before executing
                      final currentTasks = ref.read(tasksProvider);
                      if (currentTasks.activeTaskId == widget.flowId &&
                          mounted) {
                        _onResplitSource(state);
                      }
                    }
                  : null,
              icon: const Icon(Icons.segment, size: 16),
              label: const Text('Extract'),
              style: OutlinedButton.styleFrom(
                padding:
                    const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
              ),
            ),
            const SizedBox(width: 12),
          ],

          // Anonymize button (main operation)
          // Double-check flow is active before allowing button press
          ElevatedButton.icon(
            onPressed: (hasFile &&
                    workflowId != null &&
                    !state.isTranslating &&
                    tasks.activeTaskId == widget.flowId)
                ? () {
                    // Final check before executing
                    final currentTasks = ref.read(tasksProvider);
                    if (currentTasks.activeTaskId == widget.flowId && mounted) {
                      _runAnonymize(state, notifier, flowNotifier);
                    }
                  }
                : null,
            icon: const Icon(Icons.visibility_off, size: 18),
            label: const Text('Anonymize'),
            style: ElevatedButton.styleFrom(
              backgroundColor: Colors.orange.shade700,
              foregroundColor: Colors.white,
              padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
              shape: RoundedRectangleBorder(
                borderRadius: BorderRadius.circular(8),
              ),
            ),
          ),
          const SizedBox(width: 12),

          if (isAnonymizeAndTranslate && isAnonymizeCompleted) ...<Widget>[
            // Glossary button (only for Anonymize+Translate)
            OutlinedButton.icon(
              onPressed:
                  (!state.isTranslating && tasks.activeTaskId == widget.flowId)
                      ? () {
                          // Final check before executing
                          final currentTasks = ref.read(tasksProvider);
                          if (currentTasks.activeTaskId == widget.flowId &&
                              mounted) {
                            _onGenerateGlossary(state, notifier);
                          }
                        }
                      : null,
              icon: state.isTranslating && state.statusText.contains('glossary')
                  ? const SizedBox(
                      width: 16,
                      height: 16,
                      child: CircularProgressIndicator(strokeWidth: 2),
                    )
                  : const Icon(Icons.library_books, size: 16),
              label: Text(
                state.isTranslating && state.statusText.contains('glossary')
                    ? 'Generating...'
                    : 'Glossary',
              ),
              style: OutlinedButton.styleFrom(
                padding:
                    const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
              ),
            ),
            const SizedBox(width: 12),

            // Translate All button (only for Anonymize+Translate)
            ElevatedButton.icon(
              onPressed: (isAnonymizeCompleted &&
                      !state.isTranslating &&
                      tasks.activeTaskId == widget.flowId)
                  ? () {
                      // Final check before executing
                      final currentTasks = ref.read(tasksProvider);
                      if (currentTasks.activeTaskId == widget.flowId &&
                          mounted) {
                        _startTranslation(state, notifier);
                      }
                    }
                  : null,
              icon: const Icon(Icons.translate, size: 18),
              label: const Text('Translate All'),
              style: ElevatedButton.styleFrom(
                backgroundColor: Colors.blue.shade700,
                foregroundColor: Colors.white,
                padding:
                    const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
                shape: RoundedRectangleBorder(
                  borderRadius: BorderRadius.circular(8),
                ),
              ),
            ),
            const SizedBox(width: 12),
          ],

          // Translate Failed button (conditional, only for Anonymize+Translate)
          if (isAnonymizeAndTranslate &&
              isAnonymizeCompleted &&
              state.taskId != null &&
              !state.isTranslating &&
              tasks.activeTaskId == widget.flowId)
            OutlinedButton.icon(
              onPressed: () {
                // Final check before executing
                final currentTasks = ref.read(tasksProvider);
                if (currentTasks.activeTaskId == widget.flowId && mounted) {
                  _retranslateFailedSegments(state);
                }
              },
              icon: const Icon(Icons.refresh, size: 16),
              label: const Text('Translate Failed'),
              style: OutlinedButton.styleFrom(
                padding:
                    const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
                shape: RoundedRectangleBorder(
                  borderRadius: BorderRadius.circular(8),
                ),
              ),
            ),

          const Spacer(),
        ],
      ),
    );
  }

  Future<void> _runAnonymize(
    state,
    notifier,
    flowNotifier,
  ) async {
    if (widget.flowId == null || flowNotifier == null) return;
    if (!mounted) return; // Widget disposed, skip

    // Verify flow is still active before proceeding
    final tasks = ref.read(tasksProvider);
    if (tasks.activeTaskId != widget.flowId) {
      if (kDebugMode) {
        debugPrint(
          '[AnonymizeScreen] _runAnonymize: Flow is not active, aborting. flowId=${widget.flowId}, activeTaskId=${tasks.activeTaskId}',
        );
      }
      return;
    }

    try {
      // Get Quick Settings configuration
      if (!mounted) return;

      // Double-check flow is still active
      final currentTasks = ref.read(tasksProvider);
      if (currentTasks.activeTaskId != widget.flowId) {
        if (kDebugMode) {
          debugPrint(
            '[AnonymizeScreen] _runAnonymize: Flow became inactive, aborting',
          );
        }
        return;
      }

      final anonymizeQs =
          ref.read(anonymizationQuickSettingsProviderFamily(widget.flowId!));
      if (!mounted) return;

      // Triple-check flow is still active
      final tasksAfterQs = ref.read(tasksProvider);
      if (tasksAfterQs.activeTaskId != widget.flowId) {
        if (kDebugMode) {
          debugPrint(
            '[AnonymizeScreen] _runAnonymize: Flow became inactive after reading Quick Settings, aborting',
          );
        }
        return;
      }

      final flow = ref.read(flowProviderFamily(widget.flowId!));
      final workflowId = flow.context.anonymize.workflowId;

      if (workflowId == null || workflowId.isEmpty) {
        if (mounted) {
          MessageService.showError(
            context,
            'No workflow ID found. Please upload a file first.',
          );
        }
        return;
      }

      // Final check before modifying state
      final tasksBeforeState = ref.read(tasksProvider);
      if (tasksBeforeState.activeTaskId != widget.flowId) {
        if (kDebugMode) {
          debugPrint(
            '[AnonymizeScreen] _runAnonymize: Flow became inactive before setting state, aborting',
          );
        }
        return;
      }

      notifier.setTranslating(true);
      notifier.setStatusText('Anonymizing...');

      // Get segment boundaries from translation service if available (for accurate segment index calculation)
      List<int>? segmentBoundaries;
      final translationState =
          ref.read(translationStateProviderFamily(widget.flowId!));
      final taskId = translationState.taskId;
      String? segmentText; // Declare outside try-catch to preserve it

      if (taskId != null && taskId.isNotEmpty) {
        try {
          final translationService = TranslationService();
          final preview =
              await translationService.getSourcePreview(taskId, limit: 500);
          final status = await translationService.getStatus(taskId);

          final segs = (preview['segments'] as List<dynamic>? ?? <dynamic>[])
              .map((e) => e.toString())
              .toList();

          final meta = status['segments_metadata'] as Map<String, dynamic>?;
          final seps = (meta != null && meta['separators_after'] is List)
              ? (meta['separators_after'] as List)
                  .map((e) => e?.toString() ?? '\n\n')
                  .toList()
              : List.generate(segs.length, (_) => '\n\n');

          // Calculate segment boundaries and build segment text (same logic as SegmentLoader.loadSegments)
          final boundaries = <int>[];
          final segmentTextBuffer = StringBuffer();
          int currentPos = 0;
          for (int i = 0; i < segs.length; i++) {
            boundaries.add(currentPos);
            segmentTextBuffer.write(segs[i]);
            currentPos += segs[i].length;
            if (i < seps.length) {
              segmentTextBuffer.write(seps[i]);
              currentPos += seps[i].length;
            }
          }
          boundaries.add(currentPos);
          segmentBoundaries = boundaries;
          segmentText = segmentTextBuffer.toString(); // Store in outer variable
        } catch (e) {
          // If failed to get translation segments, continue without them
          // segmentText remains null, will use fallback
        }
      }

      // Final check before calling backend
      final tasksBeforeBackend = ref.read(tasksProvider);
      if (tasksBeforeBackend.activeTaskId != widget.flowId) {
        if (kDebugMode) {
          debugPrint(
            '[AnonymizeScreen] _runAnonymize: Flow became inactive before calling backend, aborting',
          );
        }
        if (mounted) {
          notifier.setTranslating(false);
        }
        return;
      }

      // Run unified backend pipeline (with or without segment text)
      final anonymizeService = AnonymizeService();
      final result = await anonymizeService.runUnified(
        workflowId,
        enabledEntities: anonymizeQs.selectedEntityTypes,
        mode: anonymizeQs.anonymizeMode,
        confidenceThreshold: anonymizeQs.anonymizeConfidence,
        detectionLanguage: anonymizeQs.detectionLanguage != 'auto'
            ? anonymizeQs.detectionLanguage
            : anonymizeQs.detectedLanguage,
        customPlaceholder: anonymizeQs.customPlaceholder,
        segmentBoundaries: segmentBoundaries,
        segmentText:
            segmentText, // Pass segmentText whether from try block or null
      );

      if (!mounted) return; // Widget disposed after async operation

      // Check flow is still active after backend call
      final tasksAfterBackend = ref.read(tasksProvider);
      if (tasksAfterBackend.activeTaskId != widget.flowId) {
        if (kDebugMode) {
          debugPrint(
            '[AnonymizeScreen] _runAnonymize: Flow became inactive after backend call, aborting',
          );
        }
        if (mounted) {
          notifier.setTranslating(false);
        }
        return;
      }

      notifier.setTranslating(false);

      if (result.isNotEmpty) {
        final originalText = result['original_text']?.toString() ?? '';
        final anonymizedText = result['anonymized_text']?.toString() ?? '';
        final entitiesExpanded =
            result['entities_expanded'] as List<dynamic>? ?? <dynamic>[];
        final mappings = result['mappings'] as Map<String, dynamic>?;
        final statistics = result['stats'] as Map<String, dynamic>?;
        // segments are used by the result view; we rely on backend to ensure consistency

        if (anonymizedText.isNotEmpty) {
          flowNotifier.setAnonymizeArtifacts(
            AnonymizeArtifacts(
              anonymizedText: anonymizedText,
              originalText: originalText.isNotEmpty ? originalText : null,
              mappings:
                  mappings?.map((k, v) => MapEntry(k.toString(), v.toString())),
              workflowId: workflowId,
              entitiesExpanded: entitiesExpanded,
            ),
          );

          if (mounted) {
            final tabsNotifier = widget.flowId != null
                ? ref.read(previewTabsProviderFamily(widget.flowId!).notifier)
                : ref.read(previewTabsProvider.notifier);
            final tabsState = widget.flowId != null
                ? ref.read(previewTabsProviderFamily(widget.flowId!))
                : ref.read(previewTabsProvider);

            String? resultTabId;
            final existingTabIndex = tabsState.tabs.indexWhere(
              (tab) => tab.title == 'Anonymized Result',
            );
            if (existingTabIndex >= 0) {
              final existingTabId = tabsState.tabs[existingTabIndex].id;
              tabsNotifier.replaceTabContent(
                existingTabId,
                _buildAnonymizedResultWidget(
                  originalText: originalText,
                  anonymizedText: anonymizedText,
                  entities: entitiesExpanded,
                  statistics: statistics,
                ),
                dataRef: _buildAnonymizedDataRef(
                  originalText: originalText,
                  anonymizedText: anonymizedText,
                  entities: entitiesExpanded,
                  statistics: statistics,
                ),
              );
              resultTabId = existingTabId;
            } else {
              resultTabId = _addAnonymizedResultTab(
                originalText: originalText,
                anonymizedText: anonymizedText,
                entities: entitiesExpanded,
                statistics: statistics,
              );
            }

            // Automatically switch to the new tab
            if (resultTabId != null) {
              try {
                final tabsNotifier = widget.flowId != null
                    ? ref.read(
                        previewTabsProviderFamily(widget.flowId!).notifier,
                      )
                    : ref.read(previewTabsProvider.notifier);
                final tabsState = widget.flowId != null
                    ? ref.read(previewTabsProviderFamily(widget.flowId!))
                    : ref.read(previewTabsProvider);
                final tabIndex =
                    tabsState.tabs.indexWhere((tab) => tab.id == resultTabId);
                if (tabIndex >= 0) {
                  tabsNotifier.switchToTab(tabIndex);
                }
              } catch (e) {
                if (kDebugMode) {
                  debugPrint(
                    '[AnonymizeScreen] _runAnonymize: Failed to switch to result tab: $e',
                  );
                }
              }
            }
          }

          notifier.setStatusText('completed');
          if (widget.flowId != null) {
            final currentHasUpload = state.pickedFile != null ||
                (_isTextMode && _textController.text.trim().isNotEmpty);
            _saveStepsState(anonymizeCompleted: true);
            setState(() {
              _persistedStepsState = PersistedStepsState(
                uploadCompleted:
                    _persistedStepsState?.uploadCompleted ?? currentHasUpload,
                extractCompleted:
                    _persistedStepsState?.extractCompleted ?? false,
                glossaryCompleted:
                    _persistedStepsState?.glossaryCompleted ?? false,
                glossarySkipped: _persistedStepsState?.glossarySkipped ?? false,
                translateCompleted:
                    _persistedStepsState?.translateCompleted ?? false,
                anonymizeCompleted: true,
                deAnonymizeCompleted:
                    _persistedStepsState?.deAnonymizeCompleted ?? false,
              );
            });
          }

          if (mounted) {
            MessageService.showSuccess(context, 'Anonymization completed');
          }
        } else {
          notifier.setStatusText('failed');
          if (mounted) {
            MessageService.showError(
              context,
              'Anonymization failed: No anonymized text returned',
            );
          }
        }
      } else {
        notifier.setStatusText('failed');
        if (mounted) {
          MessageService.showError(
            context,
            'Anonymization failed: Empty response',
          );
        }
      }
    } catch (e) {
      if (!mounted) return; // Widget disposed, skip ref access

      final dynamic translationNotifier = widget.flowId != null
          ? ref.read(translationStateProviderFamily(widget.flowId!).notifier)
          : ref.read(translationStateProvider.notifier);
      translationNotifier.setTranslating(false);
      translationNotifier.setStatusText('failed');
      if (mounted) {
        MessageService.showError(context, 'Failed to anonymize: $e');
      }
    }
  }

  Future<void> _pickFile(notifier) async {
    // Prevent duplicate file picker dialogs
    if (_isPickingFile) {
      return;
    }

    // Check if there's an active task
    final dynamic state = widget.flowId != null
        ? ref.read(translationStateProviderFamily(widget.flowId!))
        : ref.read(translationStateProvider);
    final hasTask = state.taskId != null && (state.taskId as String).isNotEmpty;
    final isTranslating = state.isTranslating;

    if (hasTask || isTranslating) {
      if (mounted) {
        MessageService.showWarning(
          context,
          'File selection is disabled while processing is in progress. Please cancel the current task first.',
        );
      }
      return;
    }

    // Set flag to prevent duplicate calls
    _isPickingFile = true;

    try {
      // Use FilePickerHelper to ensure Web uses browser-native file picker
      final result = await FilePickerHelper.pickFiles(
        type: FileType.custom,
        allowedExtensions: _supportedFileExtensions,
        withData: true,
      );

      if (result != null) {
        final file = result.files.single;

        // Check if file is .doc (not .docx) - unsupported format
        final fileName = file.name.toLowerCase();
        if (fileName.endsWith('.doc') && !fileName.endsWith('.docx')) {
          if (mounted) {
            MessageService.showError(
              context,
              'DOC files are not supported. Please convert the file to DOCX format and import again.',
            );
          }
          return;
        }

        // Check if file is .ppt (not .pptx) - unsupported format
        if (fileName.endsWith('.ppt') && !fileName.endsWith('.pptx')) {
          if (mounted) {
            MessageService.showError(
              context,
              'PPT files are not supported. Please convert the file to PPTX format and import again.',
            );
          }
          return;
        }

        notifier.setPickedFile(file);

        // Save state to persistence after file is picked
        if (widget.flowId != null && mounted) {
          try {
            final flowNotifier =
                ref.read(flowProviderFamily(widget.flowId!).notifier);

            // Save file name to flow context
            flowNotifier.updateSource(
              FlowSource(
                fileName: file.name,
                filePath: file.path,
              ),
            );
          } catch (e) {
            if (kDebugMode) {
              debugPrint('Failed to save state after file pick: $e');
            }
          }
        }

        // Create Extract Tab immediately with a pending taskId
        // This ensures the tab exists even if user switches flow before format conversion completes
        // The tab will show "Preparing..." state until real taskId is available
        if (widget.flowId != null && mounted) {
          // Generate a temporary pending taskId that will be replaced when real taskId is available
          final pendingTaskId =
              'pending_${widget.flowId}_${DateTime.now().millisecondsSinceEpoch}';
          if (kDebugMode) {
            debugPrint(
              '[AnonymizeScreen] Creating Extract Tab with pending taskId: $pendingTaskId',
            );
          }
          _addExtractTab(pendingTaskId, isPending: true);
        }

        // Auto init preview by running format-conversion (no token usage)
        // Note: We capture flowId before async operation to ensure we can replace pending tab
        // even if user switches flow before conversion completes
        final currentFlowId = widget.flowId;
        if (currentFlowId == null) {
          notifier.setTranslating(false);
          return;
        }

        if (mounted) {
          try {
            final formatSvc = FormatConversionService();
            final bytes = file.bytes ?? (await File(file.path!).readAsBytes());
            final GlobalSettings globalSettings =
                ref.read(globalSettingsProvider);
            final FormatConvertParserOptions parserOpts =
                await formatSvc.resolveParserOptions(
              parsingEngine: globalSettings.parsingEngine,
              formulaOcr: globalSettings.formulaOcr,
              tableOcr: globalSettings.tableOcr,
            );

            final convertRes = await formatSvc.convertFormat(
              fileBytes: bytes,
              fileName: file.name,
              convertEngine: parserOpts.convertEngine,
              formulaOcr: parserOpts.formulaOcr,
              tableOcr: parserOpts.tableOcr,
              modelVersion: parserOpts.modelVersion,
              mineruToken: parserOpts.mineruToken,
            );

            // Always replace pending tab, even if flow is not active (mounted check)
            // This ensures pending tabs are replaced even if user switched flows
            if (convertRes['success'] == true) {
              final data = (convertRes['data'] as Map).cast<String, dynamic>();
              final taskId = data['task_id']?.toString();
              if (taskId != null && taskId.isNotEmpty) {
                // Set taskId in translation state (even if flow is not active)
                if (mounted) {
                  notifier.setTaskId(taskId);
                }

                // Replace the pending Extract Tab with the real one
                // Use captured flowId to ensure we update the correct flow's tabs
                // Use WidgetsBinding to ensure we're in a valid context
                WidgetsBinding.instance.addPostFrameCallback((_) {
                  if (mounted && widget.flowId == currentFlowId) {
                    _replacePendingExtractTab(taskId);
                  } else {
                    // Flow is not active, but we still need to replace the pending tab
                    // Access providers using global container (widget may be disposed)
                    try {
                      final container =
                          TabBackgroundUpdateService().getContainer();
                      if (container == null) {
                        if (kDebugMode) {
                          debugPrint(
                            '[AnonymizeScreen] Cannot replace pending tab: container not available',
                          );
                        }
                        return;
                      }
                      final tabsNotifier = container.read(
                        previewTabsProviderFamily(currentFlowId).notifier,
                      );
                      final tabsState = container
                          .read(previewTabsProviderFamily(currentFlowId));

                      // Find the pending Extract tab
                      final pendingTabIndex = tabsState.tabs.indexWhere(
                        (tab) =>
                            tab.id == 'extract_pending_$currentFlowId' ||
                            (tab.dataRef?['isPending'] == true &&
                                tab.title == 'Extract'),
                      );

                      if (pendingTabIndex >= 0) {
                        // Close the pending tab
                        tabsNotifier.closeTab(pendingTabIndex);

                        // Add the real Extract tab
                        final content = ExtractPreview(
                          key: ValueKey('extract_${currentFlowId}_$taskId'),
                          taskId: taskId,
                          flowId: currentFlowId,
                          onAnonymizeComplete: () {
                            // This callback won't work if flow is not active, but that's OK
                            // The completion will be handled via AnonymizeCompletionProvider
                          },
                        );
                        final tab = PreviewTab(
                          id: 'extract_$taskId',
                          type: PreviewTabType.translationResult,
                          title: 'Extract',
                          icon: Icons.fact_check,
                          content: content,
                          dataRef: <String, dynamic>{
                            'taskId': taskId,
                            'flowId': currentFlowId,
                            'isPending': false,
                          },
                        );
                        tabsNotifier.addTab(tab);

                        if (kDebugMode) {
                          debugPrint(
                            '[AnonymizeScreen] Replaced pending Extract Tab with real taskId: $taskId (flow not active)',
                          );
                        }
                      }
                    } catch (e) {
                      if (kDebugMode) {
                        debugPrint(
                          '[AnonymizeScreen] Error replacing pending tab when flow not active: $e',
                        );
                      }
                    }
                  }
                });
              }
            } else {
              await _handleMineruAuthError(convertRes['error']?.toString());
              // Format conversion failed, remove the pending tab
              WidgetsBinding.instance.addPostFrameCallback((_) {
                if (mounted && widget.flowId == currentFlowId) {
                  _removePendingExtractTab();
                } else {
                  // Flow is not active, but we still need to remove the pending tab
                  // Access providers using global container (widget may be disposed)
                  try {
                    final container =
                        TabBackgroundUpdateService().getContainer();
                    if (container == null) {
                      if (kDebugMode) {
                        debugPrint(
                          '[AnonymizeScreen] Cannot remove pending tab: container not available',
                        );
                      }
                      return;
                    }
                    final tabsNotifier = container.read(
                      previewTabsProviderFamily(currentFlowId).notifier,
                    );
                    final tabsState = container
                        .read(previewTabsProviderFamily(currentFlowId));

                    final pendingTabIndex = tabsState.tabs.indexWhere(
                      (tab) =>
                          tab.id == 'extract_pending_$currentFlowId' ||
                          (tab.dataRef?['isPending'] == true &&
                              tab.title == 'Extract'),
                    );

                    if (pendingTabIndex >= 0) {
                      tabsNotifier.closeTab(pendingTabIndex);
                      if (kDebugMode) {
                        debugPrint(
                          '[AnonymizeScreen] Removed pending Extract Tab (flow not active)',
                        );
                      }
                    }
                  } catch (e) {
                    if (kDebugMode) {
                      debugPrint(
                        '[AnonymizeScreen] Error removing pending tab when flow not active: $e',
                      );
                    }
                  }
                }
              });
            }
          } catch (e) {
            await _handleMineruAuthError(e.toString());
            // Format conversion error, remove the pending tab
            WidgetsBinding.instance.addPostFrameCallback((_) {
              if (mounted && widget.flowId == currentFlowId) {
                _removePendingExtractTab();
              } else {
                // Flow is not active, but we still need to remove the pending tab
                // Access providers using global container (widget may be disposed)
                try {
                  final container = TabBackgroundUpdateService().getContainer();
                  if (container == null) {
                    if (kDebugMode) {
                      debugPrint(
                        '[AnonymizeScreen] Cannot remove pending tab: container not available',
                      );
                    }
                    return;
                  }
                  final tabsNotifier = container
                      .read(previewTabsProviderFamily(currentFlowId).notifier);
                  final tabsState =
                      container.read(previewTabsProviderFamily(currentFlowId));

                  final pendingTabIndex = tabsState.tabs.indexWhere(
                    (tab) =>
                        tab.id == 'extract_pending_$currentFlowId' ||
                        (tab.dataRef?['isPending'] == true &&
                            tab.title == 'Extract'),
                  );

                  if (pendingTabIndex >= 0) {
                    tabsNotifier.closeTab(pendingTabIndex);
                  }
                } catch (e2) {
                  if (kDebugMode) {
                    debugPrint(
                      '[AnonymizeScreen] Error removing pending tab when flow not active: $e2',
                    );
                  }
                }
              }
            });
            if (kDebugMode) {
              debugPrint('[AnonymizeScreen] Format conversion error: $e');
            }
          }
        }

        // For anonymize flows: create workflow and detect language
        if (widget.flowId != null && mounted) {
          try {
            final anonymizeService = AnonymizeService();
            final fileBytes =
                file.bytes ?? (await File(file.path!).readAsBytes());

            // Check mounted after file read
            if (!mounted) return;

            // Create anonymize workflow
            final createResult =
                await anonymizeService.createWorkflow(fileBytes, file.name);

            // Check mounted after async operation
            if (!mounted) return;

            if (createResult['success'] == true) {
              final workflowId = createResult['workflow_id']?.toString();
              if (workflowId != null && workflowId.isNotEmpty) {
                // Store workflow ID in flow context (preserve existing artifacts)
                if (!mounted) return;
                final flowNotifier =
                    ref.read(flowProviderFamily(widget.flowId!).notifier);
                final currentFlowState =
                    ref.read(flowProviderFamily(widget.flowId!));
                final existingArtifacts = currentFlowState.context.anonymize;

                // Update workflow ID
                flowNotifier.setAnonymizeArtifacts(
                  existingArtifacts.copyWith(workflowId: workflowId),
                );

                // Trigger rebuild to update toolbar
                if (mounted) {
                  setState(() {});
                }

                // Detect language
                if (mounted) {
                  try {
                    final langResult =
                        await anonymizeService.detectLanguage(workflowId);

                    // Check mounted after async operation
                    if (!mounted) return;

                    final detectedLang =
                        langResult['detected_language']?.toString();
                    if (detectedLang != null && detectedLang.isNotEmpty) {
                      // Update Quick Settings with detected language
                      if (mounted) {
                        final anonymizeQsNotifier = ref.read(
                          anonymizationQuickSettingsProviderFamily(
                            widget.flowId!,
                          ).notifier,
                        );
                        anonymizeQsNotifier
                            .updateDetectedLanguage(detectedLang);
                      }
                    }
                  } catch (e) {
                    if (kDebugMode) {
                      debugPrint('Failed to detect language: $e');
                    }
                  }
                }
              }
            }

            // Save steps state: upload completed
            if (mounted) {
              _saveStepsState(uploadCompleted: true);
            }
          } catch (e) {
            if (kDebugMode) {
              debugPrint('Failed to create anonymize workflow: $e');
            }
          }
        }
      } else {
        if (mounted) {
          MessageService.showWarning(
            context,
            'File selection cancelled or failed.',
          );
        }
      }
    } catch (e) {
      if (mounted) {
        MessageService.showError(context, 'Error picking file: $e');
      }
    } finally {
      // Reset flag after file picker is closed (whether user selected a file or cancelled)
      _isPickingFile = false;
    }
  }

  Future<void> _cancelCurrentTask(notifier) async {
    // Show confirmation dialog
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Cancel Current Task'),
        content: const Text(
          'This will cancel the current task and clear the selected file. Do you want to continue?',
        ),
        actions: <Widget>[
          TextButton(
            onPressed: () => Navigator.of(context).pop(false),
            child: const Text('No'),
          ),
          TextButton(
            onPressed: () => Navigator.of(context).pop(true),
            style: TextButton.styleFrom(
              foregroundColor: Theme.of(context).colorScheme.error,
            ),
            child: const Text('Yes, Cancel'),
          ),
        ],
      ),
    );

    if (confirmed != true) return;

    // Clear all tabs
    final tabsNotifier = widget.flowId != null
        ? ref.read(previewTabsProviderFamily(widget.flowId!).notifier)
        : ref.read(previewTabsProvider.notifier);
    tabsNotifier.clearAllTabs();

    // Reset translation state
    notifier.resetTranslation();

    if (mounted) {
      MessageService.showInfo(
        context,
        'Task cancelled. You can now select a new file.',
      );
    }
  }

  Widget _buildPreviewPanel(
    state,
    notifier,
    tabsState,
  ) {
    // Check if file selection should be disabled
    final hasTask = state.taskId != null && (state.taskId as String).isNotEmpty;
    final isTranslating = state.isTranslating;
    final isFileSelectionDisabled = hasTask || isTranslating;

    // Build empty state widget
    Widget? emptyStateWidget;
    if (tabsState.tabs.isEmpty) {
      if (_isTextMode) {
        emptyStateWidget = TextInputArea(
          flowId: widget.flowId,
          controller: _textController,
          onCancelTask: () => _cancelCurrentTask(notifier),
        );
      } else {
        emptyStateWidget = FileUploadArea(
          isDisabled: isFileSelectionDisabled,
          onTap: () => _pickFile(notifier),
          onCancel: isFileSelectionDisabled
              ? () => _cancelCurrentTask(notifier)
              : null,
        );
      }
    }

    return PreviewPanel(
      flowId: widget.flowId,
      emptyState: emptyStateWidget,
    );
  }

  void _addExtractTab(String taskId, {bool isPending = false}) {
    final tabsNotifier = widget.flowId != null
        ? ref.read(previewTabsProviderFamily(widget.flowId!).notifier)
        : ref.read(previewTabsProvider.notifier);

    final content = ExtractPreview(
      key: ValueKey(
        'extract_${widget.flowId}_$taskId',
      ), // Ensure unique key per flow+task
      taskId: taskId,
      flowId: widget.flowId,
      isPending:
          isPending, // Indicate if this is a pending tab waiting for real taskId
      onAnonymizeComplete: _onAnonymizeCompleteFromExtract,
    );
    final tab = PreviewTab(
      id: isPending ? 'extract_pending_${widget.flowId}' : 'extract_$taskId',
      type: PreviewTabType.translationResult, // reuse type for tab behavior
      title: 'Extract',
      icon: Icons.fact_check,
      content: content,
      dataRef: <String, dynamic>{
        'taskId': taskId,
        'flowId': widget.flowId,
        'isPending': isPending,
      },
    );
    tabsNotifier.addTab(tab);
  }

  /// Replace the pending Extract Tab with a real one using the actual taskId
  void _replacePendingExtractTab(String realTaskId) {
    if (widget.flowId == null) return;

    final tabsNotifier = widget.flowId != null
        ? ref.read(previewTabsProviderFamily(widget.flowId!).notifier)
        : ref.read(previewTabsProvider.notifier);
    final tabsState = widget.flowId != null
        ? ref.read(previewTabsProviderFamily(widget.flowId!))
        : ref.read(previewTabsProvider);

    // Find the pending Extract tab
    final pendingTabIndex = tabsState.tabs.indexWhere(
      (tab) =>
          tab.id == 'extract_pending_${widget.flowId}' ||
          (tab.dataRef?['isPending'] == true && tab.title == 'Extract'),
    );

    if (pendingTabIndex >= 0) {
      // Close the pending tab
      tabsNotifier.closeTab(pendingTabIndex);

      // Add the real Extract tab
      _addExtractTab(realTaskId);

      if (kDebugMode) {
        debugPrint(
          '[AnonymizeScreen] Replaced pending Extract Tab with real taskId: $realTaskId',
        );
      }
    } else {
      // Pending tab not found, just add the real one
      _addExtractTab(realTaskId);
      if (kDebugMode) {
        debugPrint(
          '[AnonymizeScreen] Pending Extract Tab not found, added real tab with taskId: $realTaskId',
        );
      }
    }
  }

  /// Remove the pending Extract Tab (e.g., when format conversion fails)
  void _removePendingExtractTab() {
    if (widget.flowId == null) return;

    final tabsNotifier = widget.flowId != null
        ? ref.read(previewTabsProviderFamily(widget.flowId!).notifier)
        : ref.read(previewTabsProvider.notifier);
    final tabsState = widget.flowId != null
        ? ref.read(previewTabsProviderFamily(widget.flowId!))
        : ref.read(previewTabsProvider);

    // Find the pending Extract tab
    final pendingTabIndex = tabsState.tabs.indexWhere(
      (tab) =>
          tab.id == 'extract_pending_${widget.flowId}' ||
          (tab.dataRef?['isPending'] == true && tab.title == 'Extract'),
    );

    if (pendingTabIndex >= 0) {
      tabsNotifier.closeTab(pendingTabIndex);
      if (kDebugMode) {
        debugPrint(
          '[AnonymizeScreen] Removed pending Extract Tab due to format conversion failure',
        );
      }
    }
  }

  Future<void> _onResplitSource(state) async {
    try {
      final svc = TranslationService();
      if (state.taskId == null) {
        if (mounted) {
          MessageService.showWarning(
            context,
            'No task yet. Please start format conversion or translation first.',
          );
        }
        return;
      }
      await svc.resplitSource(state.taskId!);
      // trigger preview widgets to refresh
      if (mounted) {
        setState(() {});
      }
      // Optionally refresh preview tab if open
      if (mounted) {
        MessageService.showSuccess(context, 'Source re-split completed');
      }
    } catch (e) {
      if (mounted) {
        String message = 'Failed to re-split: $e';
        if (e is DioException) {
          final data = e.response?.data;
          if (data is Map && data['detail'] is String) {
            message = data['detail'] as String;
          }
        }
        MessageService.showError(context, message);
      }
    }
  }

  String _convertLangCodeToName(String langCode) {
    const languageMap = <String, String>{
      'zh': 'Chinese',
      'en': 'English',
      'ja': 'Japanese',
      'ko': 'Korean',
      'fr': 'French',
      'de': 'German',
      'es': 'Spanish',
      'ru': 'Russian',
    };
    return languageMap[langCode] ?? langCode;
  }

  Future<void> _onGenerateGlossary(state, notifier) async {
    // For Anonymize+Translate flow, use anonymized text if available
    final flow = widget.flowId != null
        ? ref.read(flowProviderFamily(widget.flowId!))
        : null;
    final anonymizedText = flow?.context.anonymize.anonymizedText;

    // Check if we have file or text input
    final hasFile = state.pickedFile != null;
    final hasText = _isTextMode && _textController.text.trim().isNotEmpty;

    if (!hasFile && !hasText && anonymizedText == null) {
      if (mounted) {
        MessageService.showError(
          context,
          'Please select a file, enter text, or complete anonymization first',
        );
      }
      return;
    }

    // Show detection mode selection dialog
    final selectedMode = await showDialog<String>(
      context: context,
      builder: (dialogContext) {
        String selectedMode = 'uncertain'; // Default to uncertain mode
        return StatefulBuilder(
          builder: (context, setDialogState) => AlertDialog(
            title: const Text('Select Glossary Detection Mode'),
            content: SizedBox(
              width: 400,
              child: Column(
                mainAxisSize: MainAxisSize.min,
                crossAxisAlignment: CrossAxisAlignment.start,
                children: <Widget>[
                  const Text(
                    'Choose how to detect glossary terms:',
                    style: TextStyle(fontSize: 14, fontWeight: FontWeight.bold),
                  ),
                  const SizedBox(height: 16),
                  RadioListTile<String>(
                    title: const Text(
                      'Uncertain Terms (Default)',
                      style: TextStyle(fontWeight: FontWeight.bold),
                    ),
                    subtitle: const Text(
                      'Focus on terms that may have translation errors. '
                      'Excludes terms with very clear, standard translations. '
                      'Useful for correcting translation mistakes.',
                      style: TextStyle(fontSize: 12),
                    ),
                    value: 'uncertain',
                    groupValue: selectedMode,
                    onChanged: (String? value) {
                      if (value != null) {
                        setDialogState(() {
                          selectedMode = value;
                        });
                      }
                    },
                  ),
                  const SizedBox(height: 8),
                  RadioListTile<String>(
                    title: const Text(
                      'Deep Detection',
                      style: TextStyle(fontWeight: FontWeight.bold),
                    ),
                    subtitle: const Text(
                      'Comprehensive extraction of all domain-specific terms. '
                      'Includes technical terms, proper nouns, abbreviations, etc. '
                      'Useful for building a complete glossary.',
                      style: TextStyle(fontSize: 12),
                    ),
                    value: 'deep',
                    groupValue: selectedMode,
                    onChanged: (String? value) {
                      if (value != null) {
                        setDialogState(() {
                          selectedMode = value;
                        });
                      }
                    },
                  ),
                ],
              ),
            ),
            actions: <Widget>[
              TextButton(
                onPressed: () {
                  Navigator.of(dialogContext).pop();
                },
                child: const Text('Cancel'),
              ),
              ElevatedButton(
                onPressed: () {
                  Navigator.of(dialogContext).pop(selectedMode);
                },
                child: const Text('Continue'),
              ),
            ],
          ),
        );
      },
    );

    // User cancelled the dialog
    if (selectedMode == null) {
      return;
    }

    Uint8List fileBytes;
    String fileName;

    // Prefer anonymized text for Anonymize+Translate flow
    if (anonymizedText != null && anonymizedText.isNotEmpty) {
      fileBytes = Uint8List.fromList(utf8.encode(anonymizedText));
      fileName = 'anonymized_text.md';
    } else if (_isTextMode && hasText && !hasFile) {
      fileBytes = Uint8List.fromList(utf8.encode(_textController.text.trim()));
      fileName = 'text_input.md';
    } else {
      if (state.pickedFile == null) {
        if (mounted) {
          MessageService.showError(context, 'Please select a file first');
        }
        return;
      }
      fileBytes = state.pickedFile!.bytes ??
          (await File(state.pickedFile!.path!).readAsBytes());
      fileName = state.pickedFile!.name;
    }

    notifier.setTranslating(true);
    notifier.setStatusText('Generating glossary...');

    try {
      final qs = widget.flowId != null
          ? ref.read(translationQuickSettingsProviderFamily(widget.flowId!))
          : ref.read(translationQuickSettingsProvider);
      final globalSettings = ref.read(globalSettingsProvider);

      // Convert language code to language name for backend
      final languageName = _convertLangCodeToName(qs.toLang);

      final glossaryService = GlossaryGenerationService();
      final result = await glossaryService.generateGlossary(
        fileBytes: fileBytes,
        fileName: fileName,
        targetLanguage: languageName,
        customPrompt: globalSettings.customPrompt,
        detectionMode: selectedMode, // Pass selected detection mode
      );

      if (result['success'] == true) {
        final data = result['data'];
        if (data['glossary'] != null) {
          _addGlossaryTab(data['glossary']);
          if (mounted) {
            MessageService.showSuccess(
              context,
              'Glossary generated and applied successfully!',
            );
          }
        } else {
          if (mounted) {
            MessageService.showWarning(
              context,
              'Glossary generated but no data received',
            );
          }
        }
      } else {
        if (mounted) {
          MessageService.showError(
            context,
            'Failed to generate glossary: ${result['error']}',
          );
        }
      }
    } catch (e) {
      if (mounted) {
        MessageService.showError(context, 'Error generating glossary: $e');
      }
    } finally {
      notifier.setTranslating(false);
      notifier.setStatusText('');
    }
  }

  Future<void> _startTranslation(state, notifier) async {
    // For Anonymize+Translate flow, use anonymized text
    final flow = widget.flowId != null
        ? ref.read(flowProviderFamily(widget.flowId!))
        : null;
    final anonymizedText = flow?.context.anonymize.anonymizedText;

    if (anonymizedText == null || anonymizedText.isEmpty) {
      if (mounted) {
        MessageService.showError(
          context,
          'Please complete anonymization first.',
        );
      }
      return;
    }

    // Create a virtual file from anonymized text
    final bytes = Uint8List.fromList(utf8.encode(anonymizedText));
    final virtualFile = PlatformFile(
      name: 'anonymized_text.md',
      size: bytes.length,
      bytes: bytes,
    );
    notifier.setPickedFile(virtualFile);

    // Continue with translation using the anonymized text
    // Note: This is a simplified version - full implementation would need
    // to handle glossary, workflow selection, etc. similar to TranslationScreen
    if (mounted) {
      MessageService.showInfo(
        context,
        'Translation will use anonymized text. Full implementation pending.',
      );
    }
  }

  Future<void> _retranslateFailedSegments(state) async {
    if (state.taskId == null) return;

    try {
      final svc = TranslationService();
      final segmentsData = await svc.getTranslationSegments(state.taskId!);
      final segments =
          segmentsData['segments'] as List<dynamic>? ?? <dynamic>[];

      final failedIndices = <int>[];
      for (final segment in segments) {
        final index = segment['segment_index'] as int?;
        final isFailed = segment['is_failed'] as bool? ?? false;
        final needsRetry = segment['needs_retry'] as bool? ?? false;
        if (index != null && (isFailed || needsRetry)) {
          failedIndices.add(index);
        }
      }

      if (failedIndices.isEmpty) {
        if (mounted) {
          MessageService.showInfo(context, 'No failed segments found');
        }
        return;
      }

      if (mounted) {
        MessageService.showWarning(
          context,
          'Retranslating ${failedIndices.length} failed segment(s)...',
        );
      }

      final aiPlatformSettings = ref.read(aiPlatformSettingsProvider);
      final selectedPlatform = aiPlatformSettings.defaultPlatform;

      if (selectedPlatform.isEmpty) {
        if (mounted) {
          MessageService.showError(context, 'No LLM Platform selected');
        }
        return;
      }

      // Per-platform concurrent is now read by backend from platforms.json
      final batchSize = 5;

      final dynamic translationNotifier = widget.flowId != null
          ? ref.read(translationStateProviderFamily(widget.flowId!).notifier)
          : ref.read(translationStateProvider.notifier);

      int successCount = 0;
      int failCount = 0;
      final totalToRetranslate = failedIndices.length;

      translationNotifier.setTranslating(true);
      translationNotifier.setStatusText('retranslating');

      for (int batchStart = 0;
          batchStart < failedIndices.length;
          batchStart += batchSize) {
        final batchEnd = (batchStart + batchSize < failedIndices.length)
            ? batchStart + batchSize
            : failedIndices.length;
        final batch = failedIndices.sublist(batchStart, batchEnd);

        final progress =
            ((batchStart + batch.length) / totalToRetranslate * 100)
                .round()
                .clamp(0, 100);
        translationNotifier.setProgress(progress);
        translationNotifier.setTranslationStats(
          successCount: successCount,
          failCount: failCount,
          totalSegments: totalToRetranslate,
        );

        final results = await Future.wait(
          batch.map((index) async {
            try {
              final response = await svc.retranslateSegment(
                state.taskId!,
                index,
                platformKey: selectedPlatform,
              );

              final apiSuccess = response['success'] == true;
              if (!apiSuccess) {
                final errorMsg = response['error'] ?? 'Translation failed';
                return <String, dynamic>{
                  'success': false,
                  'index': index,
                  'error': errorMsg,
                };
              }

              return <String, Object>{'success': true, 'index': index};
            } catch (e) {
              return <String, Object>{
                'success': false,
                'index': index,
                'error': e,
              };
            }
          }),
        );

        for (final result in results) {
          if (result['success'] == true) {
            successCount++;
          } else {
            failCount++;
          }
        }
      }

      translationNotifier.setTranslating(false);
      translationNotifier.setProgress(100);
      translationNotifier.setStatusText('completed');
      translationNotifier.setTranslationStats(
        successCount: successCount,
        failCount: failCount,
        totalSegments: totalToRetranslate,
      );

      if (mounted) {
        if (failCount > 0) {
          MessageService.showWarning(
            context,
            'Retranslation complete: $successCount succeeded, $failCount failed',
          );
        }
        triggerTranslationRefresh(ref);
      }
    } catch (e) {
      final dynamic translationNotifier = widget.flowId != null
          ? ref.read(translationStateProviderFamily(widget.flowId!).notifier)
          : ref.read(translationStateProvider.notifier);
      translationNotifier.setTranslating(false);
      translationNotifier.setStatusText('failed');
      if (mounted) {
        MessageService.showError(context, 'Failed to retranslate: $e');
      }
    }
  }

  /// Save steps state to persistence
  Future<void> _saveStepsState({
    bool? uploadCompleted,
    bool? anonymizeCompleted,
  }) async {
    if (widget.flowId == null) return;
    try {
      final flowNotifier =
          ref.read(flowProviderFamily(widget.flowId!).notifier);
      final existingStepsState =
          await FlowStatePersistence.getPersistedStepsState(widget.flowId!);
      final stepsState = PersistedStepsState(
        uploadCompleted:
            uploadCompleted ?? existingStepsState?.uploadCompleted ?? false,
        extractCompleted: existingStepsState?.extractCompleted ?? false,
        glossaryCompleted: existingStepsState?.glossaryCompleted ?? false,
        glossarySkipped: existingStepsState?.glossarySkipped ?? false,
        translateCompleted: existingStepsState?.translateCompleted ?? false,
        anonymizeCompleted: anonymizeCompleted ??
            existingStepsState?.anonymizeCompleted ??
            false,
        deAnonymizeCompleted: existingStepsState?.deAnonymizeCompleted ?? false,
      );
      await flowNotifier
          .saveStateWithGlossaryIds(<String>[], stepsState: stepsState);
    } catch (e) {
      if (kDebugMode) {
        debugPrint('Failed to save steps state: $e');
      }
    }
  }

  /// Handle anonymize completion event from provider
  /// This is called when ExtractPreview notifies completion through the provider
  Future<void> _handleAnonymizeCompletionEvent() async {
    if (kDebugMode) {
      debugPrint(
        '[AnonymizeScreen] _handleAnonymizeCompletionEvent: flowId=${widget.flowId}, mounted=$mounted',
      );
    }

    // Verify flow is still valid
    if (widget.flowId == null) {
      if (kDebugMode) {
        debugPrint(
          '[AnonymizeScreen] _handleAnonymizeCompletionEvent: flowId is null, aborting',
        );
      }
      return;
    }

    // Check if flow is active (for UI updates)
    final tasks = ref.read(tasksProvider);
    final isActiveFlow = tasks.activeTaskId == widget.flowId;

    if (kDebugMode) {
      debugPrint(
        '[AnonymizeScreen] _handleAnonymizeCompletionEvent: isActiveFlow=$isActiveFlow',
      );
    }

    // Clear the event to prevent duplicate handling
    ref.read(anonymizeCompletionProvider.notifier).clear();

    // Delegate to the existing handler
    // Use a small delay to ensure the event is fully processed
    await Future.delayed(const Duration(milliseconds: 100));

    if (mounted) {
      _onAnonymizeCompleteFromExtract();
    } else if (kDebugMode) {
      debugPrint(
        '[AnonymizeScreen] _handleAnonymizeCompletionEvent: Widget not mounted, skipping handler',
      );
    }
  }

  /// Handle anonymize completion from ExtractPreview
  /// This reads the anonymize artifacts from flow context and adds the Anonymized Result tab
  Future<void> _onAnonymizeCompleteFromExtract() async {
    if (widget.flowId == null) {
      if (kDebugMode) {
        debugPrint(
          '[AnonymizeScreen] _onAnonymizeCompleteFromExtract: flowId is null',
        );
      }
      return;
    }

    // Note: We don't check mounted here because this callback might be called
    // even when the widget is not visible (e.g., when flow is not active).
    // The widget might be hidden (SizedBox.shrink) but still mounted.
    // We'll check mounted before any UI operations.

    // Check if this flow is currently active (for UI feedback)
    final tasks = ref.read(tasksProvider);
    final isActiveFlow = tasks.activeTaskId == widget.flowId;

    if (kDebugMode) {
      debugPrint(
        '[AnonymizeScreen] _onAnonymizeCompleteFromExtract: flowId=${widget.flowId}, isActiveFlow=$isActiveFlow, mounted=$mounted',
      );
    }

    // Note: We still add the tab even if flow is not active, because:
    // 1. Tabs are isolated by flowId (previewTabsProviderFamily)
    // 2. When user switches back to this flow, they should see the result
    // 3. The tab will be visible when this flow becomes active again

    try {
      // Get anonymize artifacts from flow context
      final flow = ref.read(flowProviderFamily(widget.flowId!));
      final anonymizeArtifacts = flow.context.anonymize;

      if (anonymizeArtifacts.anonymizedText == null ||
          anonymizeArtifacts.anonymizedText!.isEmpty) {
        if (kDebugMode) {
          debugPrint(
            '[AnonymizeScreen] _onAnonymizeCompleteFromExtract: No anonymized text in flow context',
          );
        }
        return;
      }

      // Get original text from flow context (saved from anonymize result)
      // If not available, try to get from translation service as fallback
      String originalText = anonymizeArtifacts.originalText ?? '';

      // If original text is not in flow context, try to get from translation service
      if (originalText.isEmpty) {
        final translationState =
            ref.read(translationStateProviderFamily(widget.flowId!));
        final taskId = translationState.taskId;

        if (taskId != null && taskId.isNotEmpty) {
          try {
            final translationService = TranslationService();
            // Use smaller limit to avoid 422 error
            final preview = await translationService.getSourcePreview(
              taskId,
              limit: 500,
            );
            final status = await translationService.getStatus(taskId);

            final segs = (preview['segments'] as List<dynamic>? ??
                    preview['items'] as List<dynamic>? ??
                    <dynamic>[])
                .map((e) => e.toString())
                .toList();

            final meta = status['segments_metadata'] as Map<String, dynamic>?;
            final seps = (meta != null && meta['separators_after'] is List)
                ? (meta['separators_after'] as List)
                    .map((e) => e?.toString() ?? '\n\n')
                    .toList()
                : List.generate(segs.length, (_) => '\n\n');

            // Reconstruct original text from segments
            final buf = StringBuffer();
            for (int i = 0; i < segs.length; i++) {
              buf.write(segs[i]);
              if (i < seps.length) buf.write(seps[i]);
            }
            originalText = buf.toString();
          } catch (e) {
            if (kDebugMode) {
              debugPrint(
                '[AnonymizeScreen] _onAnonymizeCompleteFromExtract: Failed to get original text: $e',
              );
            }
            // If we can't get original text, use anonymized text as fallback
            originalText = anonymizeArtifacts.anonymizedText!;
          }
        } else {
          // No taskId, use anonymized text as fallback
          originalText = anonymizeArtifacts.anonymizedText!;
        }
      }

      // Ensure we have a valid original text
      if (originalText.isEmpty) {
        originalText = anonymizeArtifacts.anonymizedText ?? '';
      }

      // Debug: Log the data being passed
      if (kDebugMode) {
        debugPrint(
          '[AnonymizeScreen] _onAnonymizeCompleteFromExtract: Adding tab with originalText.len=${originalText.length}, anonymizedText.len=${anonymizeArtifacts.anonymizedText?.length ?? 0}, entities.len=${anonymizeArtifacts.entitiesExpanded?.length ?? 0}',
        );
      }

      // Add Anonymized Result tab (even if flow is not active, so it's available when user switches back)
      // This operation doesn't require mounted check because it only modifies provider state
      String? resultTabId;
      final tabsNotifier = widget.flowId != null
          ? ref.read(previewTabsProviderFamily(widget.flowId!).notifier)
          : ref.read(previewTabsProvider.notifier);
      final tabsState = widget.flowId != null
          ? ref.read(previewTabsProviderFamily(widget.flowId!))
          : ref.read(previewTabsProvider);

      final existingTabIndex =
          tabsState.tabs.indexWhere((tab) => tab.title == 'Anonymized Result');
      if (existingTabIndex >= 0) {
        final existingTabId = tabsState.tabs[existingTabIndex].id;
        tabsNotifier.replaceTabContent(
          existingTabId,
          _buildAnonymizedResultWidget(
            originalText: originalText,
            anonymizedText: anonymizeArtifacts.anonymizedText!,
            entities: anonymizeArtifacts.entitiesExpanded ?? <dynamic>[],
          ),
          dataRef: _buildAnonymizedDataRef(
            originalText: originalText,
            anonymizedText: anonymizeArtifacts.anonymizedText!,
            entities: anonymizeArtifacts.entitiesExpanded ?? <dynamic>[],
          ),
        );
        resultTabId = existingTabId;
      } else {
        resultTabId = _addAnonymizedResultTab(
          originalText: originalText,
          anonymizedText: anonymizeArtifacts.anonymizedText!,
          entities: anonymizeArtifacts.entitiesExpanded ?? <dynamic>[],
        );
      }

      if (kDebugMode) {
        debugPrint(
          '[AnonymizeScreen] _onAnonymizeCompleteFromExtract: Tab added with id=$resultTabId, isActiveFlow=$isActiveFlow, mounted=$mounted',
        );
      }

      // If flow is active, automatically switch to the new tab
      if (isActiveFlow && mounted && resultTabId != null) {
        // Use a small delay to ensure tab is fully added before switching
        await Future.delayed(const Duration(milliseconds: 50));

        // Double-check flow is still active after delay
        final tasksAfterDelay = ref.read(tasksProvider);
        if (tasksAfterDelay.activeTaskId != widget.flowId) {
          if (kDebugMode) {
            debugPrint(
              '[AnonymizeScreen] _onAnonymizeCompleteFromExtract: Flow became inactive during delay, skipping tab switch',
            );
          }
        } else if (mounted) {
          try {
            final tabsNotifier = widget.flowId != null
                ? ref.read(previewTabsProviderFamily(widget.flowId!).notifier)
                : ref.read(previewTabsProvider.notifier);
            final tabsState = widget.flowId != null
                ? ref.read(previewTabsProviderFamily(widget.flowId!))
                : ref.read(previewTabsProvider);

            if (kDebugMode) {
              debugPrint(
                '[AnonymizeScreen] _onAnonymizeCompleteFromExtract: Looking for tab with id=$resultTabId, total tabs=${tabsState.tabs.length}',
              );
              for (int i = 0; i < tabsState.tabs.length; i++) {
                debugPrint(
                  '[AnonymizeScreen] _onAnonymizeCompleteFromExtract: Tab[$i]: id=${tabsState.tabs[i].id}',
                );
              }
            }

            final tabIndex =
                tabsState.tabs.indexWhere((tab) => tab.id == resultTabId);
            if (tabIndex >= 0) {
              tabsNotifier.switchToTab(tabIndex);
              if (kDebugMode) {
                debugPrint(
                  '[AnonymizeScreen] _onAnonymizeCompleteFromExtract: Switched to tab index=$tabIndex',
                );
              }
            } else {
              if (kDebugMode) {
                debugPrint(
                  '[AnonymizeScreen] _onAnonymizeCompleteFromExtract: Tab not found in tabs list, tabId=$resultTabId, tabsCount=${tabsState.tabs.length}',
                );
              }
              // Try to find the tab by title as fallback
              final tabIndexByTitle = tabsState.tabs.indexWhere(
                (tab) => tab.title == 'Anonymized Result',
              );
              if (tabIndexByTitle >= 0) {
                tabsNotifier.switchToTab(tabIndexByTitle);
                if (kDebugMode) {
                  debugPrint(
                    '[AnonymizeScreen] _onAnonymizeCompleteFromExtract: Switched to tab by title at index=$tabIndexByTitle',
                  );
                }
              }
            }
          } catch (e) {
            if (kDebugMode) {
              debugPrint(
                '[AnonymizeScreen] _onAnonymizeCompleteFromExtract: Failed to switch to result tab: $e',
              );
            }
          }
        }
      } else if (!isActiveFlow && kDebugMode) {
        debugPrint(
          '[AnonymizeScreen] _onAnonymizeCompleteFromExtract: Flow is not active, tab added but not switched. User will see it when switching back to this flow.',
        );
      }

      // Update steps state
      if (widget.flowId != null) {
        // Get current upload state from persisted state or assume true if we have anonymized text
        final currentHasUpload = _persistedStepsState?.uploadCompleted ?? true;
        _saveStepsState(anonymizeCompleted: true);
        // Only update UI state if this flow is active (to avoid unnecessary rebuilds)
        if (isActiveFlow && mounted) {
          setState(() {
            _persistedStepsState = PersistedStepsState(
              uploadCompleted:
                  _persistedStepsState?.uploadCompleted ?? currentHasUpload,
              extractCompleted: _persistedStepsState?.extractCompleted ?? false,
              glossaryCompleted:
                  _persistedStepsState?.glossaryCompleted ?? false,
              glossarySkipped: _persistedStepsState?.glossarySkipped ?? false,
              translateCompleted:
                  _persistedStepsState?.translateCompleted ?? false,
              anonymizeCompleted: true,
              deAnonymizeCompleted:
                  _persistedStepsState?.deAnonymizeCompleted ?? false,
            );
          });
        }
      }

      // Only show success message if this flow is active
      if (isActiveFlow && mounted) {
        MessageService.showSuccess(context, 'Anonymization completed');
      } else if (kDebugMode) {
        debugPrint(
          '[AnonymizeScreen] _onAnonymizeCompleteFromExtract: Anonymization completed for flow ${widget.flowId}, but flow is not active. Tab added and will be visible when flow becomes active.',
        );
      }
    } catch (e) {
      if (kDebugMode) {
        debugPrint(
          '[AnonymizeScreen] _onAnonymizeCompleteFromExtract: Error: $e',
        );
      }
      if (mounted) {
        MessageService.showError(
          context,
          'Failed to add anonymized result tab: $e',
        );
      }
    }
  }

  /// Check the entire flow state and switch to the appropriate tab
  /// This is called when flow becomes active to ensure user sees the correct step
  /// Priority: Anonymized Result > Translation Result > Extract > (no switch if none exist)
  Future<void> _checkAndSwitchToCurrentStepTab() async {
    if (widget.flowId == null) return;

    // Double-check flow is still active
    final tasks = ref.read(tasksProvider);
    if (tasks.activeTaskId != widget.flowId) {
      if (kDebugMode) {
        debugPrint(
          '[AnonymizeScreen] _checkAndSwitchToCurrentStepTab: Flow is not active, skipping',
        );
      }
      return;
    }

    try {
      // Get flow state and persisted steps state
      final flow = ref.read(flowProviderFamily(widget.flowId!));
      final stepsState = await FlowDataCache().getStepsState(widget.flowId!);

      // Get tabs state
      final tabsState = widget.flowId != null
          ? ref.read(previewTabsProviderFamily(widget.flowId!))
          : ref.read(previewTabsProvider);

      if (kDebugMode) {
        debugPrint(
            '[AnonymizeScreen] _checkAndSwitchToCurrentStepTab: Checking flow state - '
            'uploadCompleted=${stepsState?.uploadCompleted}, '
            'extractCompleted=${stepsState?.extractCompleted}, '
            'anonymizeCompleted=${stepsState?.anonymizeCompleted}, '
            'translateCompleted=${stepsState?.translateCompleted}');
      }

      // Priority 0: Check if Extract tab should exist but doesn't (e.g., file uploaded but tab not created yet)
      // This handles the case where user switched flow before Extract tab was created
      final extractTabIndex =
          tabsState.tabs.indexWhere((tab) => tab.title == 'Extract');
      if (extractTabIndex < 0) {
        // Check if we have a taskId in translation state (indicates file was uploaded)
        final dynamic translationState = widget.flowId != null
            ? ref.read(translationStateProviderFamily(widget.flowId!))
            : ref.read(translationStateProvider);
        final taskId = (translationState as dynamic).taskId as String?;

        if (taskId != null && taskId.isNotEmpty) {
          if (kDebugMode) {
            debugPrint(
              '[AnonymizeScreen] _checkAndSwitchToCurrentStepTab: Extract tab missing but taskId exists ($taskId). Creating Extract tab...',
            );
          }

          // Create Extract tab
          _addExtractTab(taskId);

          // Wait a bit for tab to be added, then switch to it
          await Future.delayed(const Duration(milliseconds: 50));

          // Re-check tabs state after adding
          final tasksAfterDelay = ref.read(tasksProvider);
          if (tasksAfterDelay.activeTaskId == widget.flowId && mounted) {
            final tabsStateAfterAdd = widget.flowId != null
                ? ref.read(previewTabsProviderFamily(widget.flowId!))
                : ref.read(previewTabsProvider);
            final newExtractTabIndex = tabsStateAfterAdd.tabs
                .indexWhere((tab) => tab.title == 'Extract');
            if (newExtractTabIndex >= 0) {
              final tabsNotifier = widget.flowId != null
                  ? ref.read(previewTabsProviderFamily(widget.flowId!).notifier)
                  : ref.read(previewTabsProvider.notifier);
              tabsNotifier.switchToTab(newExtractTabIndex);
              if (kDebugMode) {
                debugPrint(
                  '[AnonymizeScreen] _checkAndSwitchToCurrentStepTab: Created and switched to Extract tab at index=$newExtractTabIndex',
                );
              }
              return; // Exit early after creating and switching to Extract tab
            }
          }
        }
      }

      // Priority 1: Check for Anonymized Result tab (if anonymize is completed)
      // Check both stepsState and flow context for completion status
      final hasAnonymizeCompleted = stepsState?.anonymizeCompleted ?? false;
      final hasAnonymizedText = flow.context.anonymize.anonymizedText != null &&
          flow.context.anonymize.anonymizedText!.isNotEmpty;

      if (hasAnonymizeCompleted || hasAnonymizedText) {
        if (kDebugMode) {
          debugPrint(
              '[AnonymizeScreen] _checkAndSwitchToCurrentStepTab: Anonymize completed detected - '
              'stepsState.anonymizeCompleted=$hasAnonymizeCompleted, hasAnonymizedText=$hasAnonymizedText');
        }

        final anonymizedResultTabIndex = tabsState.tabs
            .indexWhere((tab) => tab.title == 'Anonymized Result');

        if (anonymizedResultTabIndex >= 0) {
          // Tab exists, switch to it if not already on it
          if (tabsState.activeTabIndex != anonymizedResultTabIndex) {
            final tabsNotifier = widget.flowId != null
                ? ref.read(previewTabsProviderFamily(widget.flowId!).notifier)
                : ref.read(previewTabsProvider.notifier);
            tabsNotifier.switchToTab(anonymizedResultTabIndex);
            if (kDebugMode) {
              debugPrint(
                '[AnonymizeScreen] _checkAndSwitchToCurrentStepTab: Switched to Anonymized Result tab at index=$anonymizedResultTabIndex',
              );
            }
            return;
          } else {
            if (kDebugMode) {
              debugPrint(
                '[AnonymizeScreen] _checkAndSwitchToCurrentStepTab: Already on Anonymized Result tab',
              );
            }
            return;
          }
        } else {
          // Tab doesn't exist but anonymize is completed - try to create it
          if (hasAnonymizedText) {
            if (kDebugMode) {
              debugPrint(
                '[AnonymizeScreen] _checkAndSwitchToCurrentStepTab: Anonymized Result tab not found, but artifacts exist. Adding tab...',
              );
            }

            final anonymizeArtifacts = flow.context.anonymize;
            String originalText = anonymizeArtifacts.originalText ?? '';
            if (originalText.isEmpty) {
              originalText = anonymizeArtifacts.anonymizedText ?? '';
            }

            final resultTabId = _addAnonymizedResultTab(
              originalText: originalText,
              anonymizedText: anonymizeArtifacts.anonymizedText!,
              entities: anonymizeArtifacts.entitiesExpanded ?? <dynamic>[],
            );

            if (resultTabId != null && mounted) {
              await Future.delayed(const Duration(milliseconds: 50));
              final tasksAfterDelay = ref.read(tasksProvider);
              if (tasksAfterDelay.activeTaskId == widget.flowId && mounted) {
                final tabsStateAfterAdd = widget.flowId != null
                    ? ref.read(previewTabsProviderFamily(widget.flowId!))
                    : ref.read(previewTabsProvider);
                final newTabIndex = tabsStateAfterAdd.tabs
                    .indexWhere((tab) => tab.id == resultTabId);
                if (newTabIndex >= 0) {
                  final tabsNotifier = widget.flowId != null
                      ? ref.read(
                          previewTabsProviderFamily(widget.flowId!).notifier,
                        )
                      : ref.read(previewTabsProvider.notifier);
                  tabsNotifier.switchToTab(newTabIndex);
                  if (kDebugMode) {
                    debugPrint(
                      '[AnonymizeScreen] _checkAndSwitchToCurrentStepTab: Switched to newly added Anonymized Result tab at index=$newTabIndex',
                    );
                  }
                  return;
                }
              }
            }
          }
        }
      }

      // Priority 2: Check for Translation Result tab (if translate is completed)
      if (stepsState?.translateCompleted ?? false) {
        final translationResultTabIndex = tabsState.tabs.indexWhere(
          (tab) =>
              tab.title == 'Translation Result' ||
              tab.title.contains('Translation'),
        );

        if (translationResultTabIndex >= 0 &&
            tabsState.activeTabIndex != translationResultTabIndex) {
          final tabsNotifier = widget.flowId != null
              ? ref.read(previewTabsProviderFamily(widget.flowId!).notifier)
              : ref.read(previewTabsProvider.notifier);
          tabsNotifier.switchToTab(translationResultTabIndex);
          if (kDebugMode) {
            debugPrint(
              '[AnonymizeScreen] _checkAndSwitchToCurrentStepTab: Switched to Translation Result tab at index=$translationResultTabIndex',
            );
          }
          return;
        }
      }

      // Priority 3: Check for Extract tab (if extract is completed or in progress)
      // Note: Extract tab creation is handled in Priority 0, so we only need to switch to it here
      if ((stepsState?.extractCompleted ?? false) ||
          (stepsState?.uploadCompleted ?? false)) {
        final extractTabIndex =
            tabsState.tabs.indexWhere((tab) => tab.title == 'Extract');

        // If Extract tab exists, switch to it if appropriate
        if (extractTabIndex >= 0) {
          // Only switch to Extract if anonymize is not completed (user should see anonymize result if available)
          // Check both stepsState and flow context
          final anonymizeNotCompleted =
              stepsState?.anonymizeCompleted != true && !hasAnonymizedText;
          if (anonymizeNotCompleted &&
              tabsState.activeTabIndex != extractTabIndex) {
            final tabsNotifier = widget.flowId != null
                ? ref.read(previewTabsProviderFamily(widget.flowId!).notifier)
                : ref.read(previewTabsProvider.notifier);
            tabsNotifier.switchToTab(extractTabIndex);
            if (kDebugMode) {
              debugPrint(
                '[AnonymizeScreen] _checkAndSwitchToCurrentStepTab: Switched to Extract tab at index=$extractTabIndex',
              );
            }
            return;
          }
        }
      }

      if (kDebugMode) {
        debugPrint(
          '[AnonymizeScreen] _checkAndSwitchToCurrentStepTab: No appropriate tab found to switch to. Current tab index=${tabsState.activeTabIndex}',
        );
      }
    } catch (e) {
      if (kDebugMode) {
        debugPrint(
          '[AnonymizeScreen] _checkAndSwitchToCurrentStepTab: Error: $e',
        );
      }
    }
  }

  Widget _buildAnonymizedResultWidget({
    required String originalText,
    required String anonymizedText,
    List<dynamic>? entities,
    Map<String, dynamic>? statistics,
    Map<String, dynamic>? report,
  }) =>
      AnonymizedResultView(
        originalText: originalText,
        anonymizedText: anonymizedText,
        entities: entities ?? <dynamic>[],
        statistics: statistics,
        report: report,
        flowId: widget.flowId,
      );

  Map<String, dynamic> _buildAnonymizedDataRef({
    required String originalText,
    required String anonymizedText,
    List<dynamic>? entities,
    Map<String, dynamic>? statistics,
    Map<String, dynamic>? report,
  }) =>
      <String, dynamic>{
        'originalText': originalText,
        'anonymizedText': anonymizedText,
        'entities': entities,
        'statistics': statistics,
        'report': report,
        'flowId': widget.flowId,
      };

  /// Add Anonymized Result tab and return the tab ID
  String? _addAnonymizedResultTab({
    required String originalText,
    required String anonymizedText,
    List<dynamic>? entities,
    Map<String, dynamic>? statistics,
    Map<String, dynamic>? report,
  }) {
    // Debug: Log the data being passed to AnonymizedResultView
    if (kDebugMode) {
      debugPrint(
        '[AnonymizeScreen] _addAnonymizedResultTab: originalText.len=${originalText.length}, anonymizedText.len=${anonymizedText.length}, entities.len=${entities?.length ?? 0}',
      );
    }

    final tabsNotifier = widget.flowId != null
        ? ref.read(previewTabsProviderFamily(widget.flowId!).notifier)
        : ref.read(previewTabsProvider.notifier);
    final resultId = 'anonymized_${DateTime.now().millisecondsSinceEpoch}';

    final previewContent = _buildAnonymizedResultWidget(
      originalText: originalText,
      anonymizedText: anonymizedText,
      entities: entities,
      statistics: statistics,
      report: report,
    );

    final tab = PreviewTab(
      id: resultId,
      type: PreviewTabType.translationResult,
      title: 'Anonymized Result',
      icon: Icons.visibility_off,
      content: previewContent,
      dataRef: _buildAnonymizedDataRef(
        originalText: originalText,
        anonymizedText: anonymizedText,
        entities: entities,
        statistics: statistics,
        report: report,
      ),
    );
    tabsNotifier.addTab(tab);
    return resultId;
  }

  bool _isMineruAuthError(String? message) {
    if (message == null) return false;
    final lower = message.toLowerCase();
    return lower.contains('mineru') &&
        (lower.contains('token') || lower.contains('api key')) &&
        (lower.contains('unauthorized') ||
            lower.contains('authentication failed'));
  }

  Future<bool> _handleMineruAuthError(String? message) async {
    if (!_isMineruAuthError(message)) {
      return false;
    }
    if (!mounted) {
      return true;
    }

    const instruction =
        'MinerU parsing engine requires a valid Token. Please open Settings -> AI Platform -> MinerU to configure it.';
    MessageService.showWarning(
      context,
      instruction,
      duration: const Duration(seconds: 4),
    );

    if (!_hasShownMineruTokenPrompt && mounted) {
      _hasShownMineruTokenPrompt = true;
      await showDialog(
        context: context,
        builder: (dialogContext) => AlertDialog(
          title: const Text('MinerU Token Required'),
          content: Text(
            (message == null || message.isEmpty)
                ? instruction
                : '$instruction\n\nDetails:\n$message',
          ),
          actions: <Widget>[
            TextButton(
              onPressed: () => Navigator.of(dialogContext).pop(),
              child: const Text('Later'),
            ),
            TextButton(
              onPressed: () {
                Navigator.of(dialogContext).pop();
                Navigator.of(context).push(
                  MaterialPageRoute(
                    builder: (_) => const AIPlatformSettingsScreen(),
                  ),
                );
              },
              child: const Text('Open Settings'),
            ),
          ],
        ),
      );
    }

    return true;
  }

  void _addGlossaryTab(Map<String, dynamic> glossaryData) {
    final tabsNotifier = widget.flowId != null
        ? ref.read(previewTabsProviderFamily(widget.flowId!).notifier)
        : ref.read(previewTabsProvider.notifier);
    final glossaryId = 'glossary_${DateTime.now().millisecondsSinceEpoch}';

    if (widget.flowId != null) {
      try {
        final flowNotifier =
            ref.read(flowProviderFamily(widget.flowId!).notifier);
        final terms = glossaryData.entries
            .map(
              (e) => <String, String>{
                'src': e.key.toString(),
                'dst': e.value.toString(),
              },
            )
            .toList();
        flowNotifier.setGlossaryArtifacts(
          GlossaryArtifacts(terms: terms, confirmedTerms: terms),
        );
      } catch (_) {}
    }

    final qs = widget.flowId != null
        ? ref.read(translationQuickSettingsProviderFamily(widget.flowId!))
        : ref.read(translationQuickSettingsProvider);
    final targetLang = _convertLangCodeToName(qs.toLang);

    final previewContent = GlossaryPreview(
      glossaryId: glossaryId,
      glossaryData: glossaryData,
      flowId: widget.flowId,
      targetLang: targetLang,
      onSave: (updatedGlossary) {
        if (mounted) {
          MessageService.showSuccess(context, 'Glossary saved and applied');
        }
      },
    );

    final tab = PreviewTab(
      id: glossaryId,
      type: PreviewTabType.glossary,
      title: 'Generated Glossary',
      icon: Icons.book,
      content: previewContent,
      dataRef: <String, dynamic>{
        'glossaryData': glossaryData,
        'flowId': widget.flowId,
        'targetLang': targetLang,
      },
    );
    tabsNotifier.addTab(tab);
  }
}
