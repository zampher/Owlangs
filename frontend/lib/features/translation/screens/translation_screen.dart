import 'dart:io';
import 'dart:convert';
import 'dart:async';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:file_picker/file_picker.dart';
import 'package:go_router/go_router.dart';
import 'package:flutter/foundation.dart' show kIsWeb, debugPrint;
import 'package:shared_preferences/shared_preferences.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../../l10n/app_localizations.dart';
import '../../../app/app_config.dart';
import '../../../core/utils/file_picker_helper.dart';
import 'package:url_launcher/url_launcher.dart';
import 'package:file_saver/file_saver.dart';
import 'package:dio/dio.dart';
import '../../../shared/services/translation_service.dart';
import '../../../shared/services/translation_config_service.dart';
import '../../../shared/services/config_service.dart';
import '../../../shared/services/translation_stats_service.dart';
import '../../../shared/services/glossary_generation_service.dart';
import '../../../shared/services/format_conversion_service.dart';
import '../../../shared/services/glossary_api_service.dart';
import '../../../shared/services/file_format_service.dart';
import 'dart:typed_data';
import '../../../shared/providers/settings_provider.dart';
import '../../../shared/utils/download_filename_builder.dart';
import '../../../shared/utils/app_logger.dart';
import '../../../shared/utils/message_service.dart';
import '../../../shared/utils/dialog_helper.dart';
import '../widgets/translation_quick_settings.dart';
import '../../settings/screens/ai_platform_settings.dart';
import '../models/preview_tab.dart';
import '../providers/preview_tabs_provider.dart';
import '../providers/translation_state_provider.dart';
import '../providers/translation_state_provider_family.dart';
import '../providers/exclusion_update_provider.dart';
import '../../tasks/providers/flow_provider.dart';
import '../../tasks/models/flow.dart';
import '../../tasks/providers/tasks_provider.dart';
import '../../tasks/models/task.dart';
import '../../tasks/services/flow_state_persistence.dart';
import '../../tasks/models/persisted_flow_state.dart';
import '../providers/translation_refresh_provider.dart';
import '../providers/extract_refresh_provider.dart';
import '../providers/excluded_segments_provider.dart';
import '../providers/queue_persist_dirty_provider.dart';
import '../providers/chunk_tokens_provider.dart';
import '../providers/format_settings_provider.dart';
import '../widgets/translation_result/image_format_utils.dart';
import '../widgets/translation_result_preview.dart';
import '../widgets/glossary_preview.dart';
import '../widgets/extract_preview.dart';
import '../../home/widgets/translation_stats_widget.dart';
import '../widgets/convert_progress_widget.dart';
import '../../tasks/providers/version_stack_provider.dart';
import '../../../shared/widgets/file_upload_area.dart';
import '../../../shared/widgets/text_input_area.dart';
import '../../../shared/widgets/preview_panel.dart';
import '../../tasks/services/flow_data_cache.dart';
import '../../../app/app_router.dart';

void _translationScreenLog(String message, {LogLevel level = LogLevel.debug}) {
  AppLogger.log('TranslationScreen', message, level: level);
}

class TranslationScreen extends ConsumerStatefulWidget {
  // Optional per-flow scope
  const TranslationScreen({
    super.key,
    this.flowId,
    this.executionMode = 'immediate',
    this.reeditTaskId,
    this.reeditWorkflowType,
    this.reeditFileName,
    this.viewMode,
    this.autoPickFile = false,
  });
  final String? flowId;

  /// Backend `TranslateServiceRequest.execution_mode`: `immediate` or `queued`.
  final String executionMode;

  /// Re-edit mode: opens an existing completed task for segment editing.
  /// When set, the screen skips file upload/extract and opens the Translate tab directly.
  final String? reeditTaskId;

  /// Workflow type of the re-edited task (e.g. 'docx', 'html', 'json').
  final String? reeditWorkflowType;

  /// Original filename of the re-edited task, used for download naming.
  final String? reeditFileName;

  /// View mode: 'clean' to start in clean mode, null for default labeled mode.
  final String? viewMode;

  /// If true, auto-trigger the file picker on startup (desktop only).
  final bool autoPickFile;

  @override
  ConsumerState<TranslationScreen> createState() => _TranslationScreenState();
}

class _TranslationScreenState extends ConsumerState<TranslationScreen> {
  bool _glossarySkipped = false; // Track if glossary step is skipped
  bool _hasStartedTranslationInThisSession =
      false; // Track if translation has started in current screen session
  bool _isTextMode = false; // false = File mode, true = Text mode
  late final TextEditingController _textController;
  late final TextEditingController _urlController;
  bool _isFetchingUrl = false;
  CancelToken? _fetchUrlCancelToken;
  String _urlExtractMode = 'content';
  bool _showUrlInput = false;
  Timer?
      _glossaryProgressTimer; // Timer for glossary generation progress updates
  bool _isLeftPanelCollapsed = false; // Track left panel collapse state
  bool _hasShownLanguageWarning =
      false; // Track if language match warning has been shown for current task
  bool _hasRefreshedPlatformStatus =
      false; // Track if platform status has been refreshed after LLM test
  bool _isGlossaryEditing = false; // Track if glossary is in editing state
  bool _isUpdatingExcluded =
      false; // Track if excluded segments are being updated
  bool _queuePersistInFlight = false;
  final Set<String> _autoPersistedQueueTaskIds = <String>{};
  bool get _isReeditMode => widget.reeditTaskId != null &&
      widget.reeditTaskId!.isNotEmpty &&
      widget.flowId == null;
  
  // Batch retry cancellation
  Future<void> Function()? _currentBatchRetryCancel;
  bool _isBatchRetryCancelling = false;
  String?
      _previousTargetLang; // Track previous target language to detect changes
  // Remember user's choice for each target language: null=not chosen, true=exclude, false=don't exclude
  final Map<String, bool?> _languageExclusionChoices = <String, bool?>{};

  final FileFormatService _fileFormatService = FileFormatService();

  /// All supported file extensions for picker (all formats selectable; Pro-only show hint in _processFile if not activated)
  List<String> _getAllFileExtensions() => _fileFormatService.getAllFormats();

  PersistedStepsState? _persistedStepsState; // Cache persisted steps state
  bool _hasShownMineruTokenPrompt = false;

  @override
  void initState() {
    super.initState();
    _textController = TextEditingController();
    _urlController = TextEditingController();
    // Standalone queue flow: always start from a blank slate so a new queued task does not
    // reuse the previous task's file, tabs, or segment UI after the prior job moved to background.
    // Must run after the first frame: Riverpod forbids modifying providers during build/initState.
    // Skip for re-edit mode: we want to show the existing task, not start fresh.
    if (widget.flowId == null &&
        widget.executionMode == 'queued' &&
        !_isReeditMode) {
      WidgetsBinding.instance.addPostFrameCallback((_) {
        if (!mounted) {
          return;
        }
        _prepareFreshStandaloneQueuedSession();
      });
    }
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
    // Load persisted language exclusion choices
    WidgetsBinding.instance.addPostFrameCallback((_) {
      _loadLanguageExclusionChoices();
    });
    // Load persisted tabs in background (delayed to avoid blocking UI)
    WidgetsBinding.instance.addPostFrameCallback((_) {
      Future.delayed(const Duration(milliseconds: 100), () {
        if (mounted) {
          _loadPersistedTabs();
        }
      });
    });
    // Re-edit mode: bypass file upload flow, directly open the edit tab
    if (_isReeditMode) {
      WidgetsBinding.instance.addPostFrameCallback((_) {
        if (!mounted) return;
        _initStandaloneQueuedReeditSession();
      });
    }
    // Auto-pick file: programmatically open the file picker on startup
    if (widget.autoPickFile) {
      WidgetsBinding.instance.addPostFrameCallback((_) {
        if (!mounted || _isReeditMode) return;
        final notifier = widget.flowId != null
            ? ref.read(translationStateProviderFamily(widget.flowId!).notifier)
            : ref.read(translationStateProvider.notifier);
        _pickFile(notifier);
      });
    }
  }

  @override
  void dispose() {
    _textController.dispose();
    _urlController.dispose();
    super.dispose();
  }

  /// Load persisted steps state from Flow state (using cache)
  Future<void> _loadPersistedStepsState() async {
    if (widget.flowId == null) return;
    try {
      // Use cache to avoid repeated SharedPreferences reads
      final FlowDataCache cache = FlowDataCache();
      final PersistedStepsState? stepsState =
          await cache.getStepsState(widget.flowId!);
      if (stepsState != null && mounted) {
        setState(() {
          _persistedStepsState = stepsState;
        });
      }
    } catch (_) {
      // Ignore errors
    }
  }

  /// Load persisted language exclusion choices from SharedPreferences
  Future<void> _loadLanguageExclusionChoices() async {
    try {
      final SharedPreferences prefs = await SharedPreferences.getInstance();
      final String? choicesJson = prefs.getString('language_exclusion_choices');
      if (choicesJson != null) {
        final Map<String, dynamic> choicesMap =
            jsonDecode(choicesJson) as Map<String, dynamic>;
        setState(() {
          choicesMap.forEach((key, value) {
            if (value != null) {
              _languageExclusionChoices[key] = value as bool;
            }
          });
        });
        _translationScreenLog(
          '[UPDATE-EXCLUDED] Loaded persisted language exclusion choices: ${_languageExclusionChoices.length} languages',
        );
      }
    } catch (e) {
      _translationScreenLog(
        'Failed to load language exclusion choices: $e',
        level: LogLevel.warn,
      );
    }
  }

  /// Save language exclusion choices to SharedPreferences
  Future<void> _saveLanguageExclusionChoices() async {
    try {
      final SharedPreferences prefs = await SharedPreferences.getInstance();
      final Map<String, dynamic> choicesMap = <String, dynamic>{};
      _languageExclusionChoices.forEach((key, value) {
        if (value != null) {
          choicesMap[key] = value;
        }
      });
      final String choicesJson = jsonEncode(choicesMap);
      await prefs.setString('language_exclusion_choices', choicesJson);
      _translationScreenLog(
        '[UPDATE-EXCLUDED] Saved language exclusion choices: ${choicesMap.length} languages',
      );
    } catch (e) {
      _translationScreenLog(
        'Failed to save language exclusion choices: $e',
        level: LogLevel.warn,
      );
    }
  }

  /// Save steps state to persistence
  Future<void> _saveStepsState({
    required bool uploadCompleted,
    required bool extractCompleted,
    required bool glossaryCompleted,
    required bool glossarySkipped,
    required bool translateCompleted,
  }) async {
    if (widget.flowId == null) return;
    try {
      final FlowStateNotifier flowNotifier =
          ref.read(flowProviderFamily(widget.flowId!).notifier);
      final TranslationQuickSettings qs =
          ref.read(translationQuickSettingsProviderFamily(widget.flowId!));
      final PersistedStepsState stepsState = PersistedStepsState(
        uploadCompleted: uploadCompleted,
        extractCompleted: extractCompleted,
        glossaryCompleted: glossaryCompleted,
        glossarySkipped: glossarySkipped,
        translateCompleted: translateCompleted,
      );
      await flowNotifier.saveStateWithGlossaryIds(
        qs.selectedGlossaries,
        stepsState: stepsState,
      );
      // Update cache
      setState(() {
        _persistedStepsState = stepsState;
      });
    } catch (e) {
      _translationScreenLog('Failed to save steps state: $e');
    }
  }

  // ignore: unused_element
  Widget _buildStepBar() {
    // Derive step states
    final dynamic translationState = widget.flowId != null
        ? ref.watch(translationStateProviderFamily(widget.flowId!))
        : ref.watch(translationStateProvider);
    final PreviewTabsState tabsState = widget.flowId != null
        ? ref.watch(previewTabsProviderFamily(widget.flowId!))
        : ref.watch(previewTabsProvider);
    final PreviewTabsNotifier tabsNotifier = widget.flowId != null
        ? ref.read(previewTabsProviderFamily(widget.flowId!).notifier)
        : ref.read(previewTabsProvider.notifier);
    // Read quick settings to detect external glossary selection
    final TranslationQuickSettings qs = widget.flowId != null
        ? ref.watch(translationQuickSettingsProviderFamily(widget.flowId!))
        : ref.watch(translationQuickSettingsProvider);

    final bool hasUpload = translationState.pickedFile != null;
    final bool hasTask = translationState.taskId != null &&
        (translationState.taskId as String).isNotEmpty;
    final bool hasExtract =
        hasTask; // Import triggers Convert which prepares preview; treat as extracted
    final bool hasGlossaryTab = tabsState.tabs
        .any((PreviewTab t) => t.type.toString().endsWith('glossary'));
    final bool hasGlossarySelected = qs.selectedGlossaries.isNotEmpty;
    final bool glossarySkipped =
        _glossarySkipped && !hasGlossaryTab && !hasGlossarySelected;
    final bool hasTranslate =
        (translationState.statusText.toString().toLowerCase() == 'completed');

    // Use persisted state if available, otherwise use current state
    final bool effectiveUpload =
        _persistedStepsState?.uploadCompleted ?? hasUpload;
    final bool effectiveExtract =
        _persistedStepsState?.extractCompleted ?? hasExtract;
    final bool effectiveGlossary = _persistedStepsState?.glossaryCompleted ??
        (hasGlossaryTab || hasGlossarySelected);
    final bool effectiveGlossarySkipped =
        _persistedStepsState?.glossarySkipped ?? glossarySkipped;
    final bool effectiveTranslate =
        _persistedStepsState?.translateCompleted ?? hasTranslate;

    // Save steps state to persistence when it changes (debounced via FlowStateNotifier)
    if (widget.flowId != null) {
      WidgetsBinding.instance.addPostFrameCallback((_) {
        _saveStepsState(
          uploadCompleted: hasUpload,
          extractCompleted: hasExtract,
          glossaryCompleted: hasGlossaryTab || hasGlossarySelected,
          glossarySkipped: glossarySkipped,
          translateCompleted: hasTranslate,
        );
      });
    }

    Widget buildChip({
      required IconData icon,
      required String label,
      required bool on,
      bool skipped = false,
      VoidCallback? onTap,
      String? tooltip,
    }) {
      Color color;
      Color bg;
      if (skipped) {
        color = Colors.orange.shade600;
        bg = Colors.orange.shade50;
      } else if (on) {
        color = Colors.blue.shade700;
        bg = Colors.blue.shade50;
      } else {
        color = Colors.grey.shade400;
        bg = Colors.grey.shade100;
      }
      final Container child = Container(
        padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 8),
        decoration: BoxDecoration(
          color: bg,
          borderRadius: BorderRadius.circular(999),
          border: Border.all(color: color.withOpacity(0.6)),
        ),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: <Widget>[
            Icon(icon, size: 14, color: color),
            const SizedBox(width: 6),
            Text(
              label,
              style: TextStyle(
                fontSize: 12,
                fontWeight: FontWeight.w600,
                color: color,
                decoration: skipped ? TextDecoration.lineThrough : null,
              ),
            ),
          ],
        ),
      );
      return Padding(
        padding: const EdgeInsets.only(bottom: 8),
        child: Tooltip(
          message: tooltip ?? label,
          child: Material(
            color: Colors.transparent,
            child: InkWell(
              onTap: (on || skipped) ? onTap : null,
              borderRadius: BorderRadius.circular(999),
              child: child,
            ),
          ),
        ),
      );
    }

    final l10n = AppLocalizations.of(context)!;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: <Widget>[
        Row(
          children: <Widget>[
            Icon(
              Icons.route,
              size: 18,
              color: Theme.of(context).colorScheme.primary,
            ),
            const SizedBox(width: 6),
            Text(
              l10n.homeSteps,
              style: TextStyle(
                fontSize: 14,
                fontWeight: FontWeight.w600,
                color: Theme.of(context).colorScheme.primary,
              ),
            ),
          ],
        ),
        const SizedBox(height: 10),
        buildChip(
          icon: Icons.upload_file,
          label: l10n.homePhaseUpload,
          on: effectiveUpload,
          onTap: () {},
          tooltip: effectiveUpload
              ? l10n.translationStepsUploadTooltipReady
              : l10n.translationStepsUploadTooltipNotReady,
        ),
        buildChip(
          icon: Icons.fact_check,
          label: l10n.homePhaseExtract,
          on: effectiveExtract,
          onTap: () {
            final int idx = tabsState.tabs
                .indexWhere((PreviewTab t) => t.id == 'extract_tab');
            if (idx >= 0) tabsNotifier.switchToTab(idx);
          },
          tooltip: effectiveExtract
              ? l10n.translationStepsExtractTooltipReady
              : l10n.translationStepsExtractTooltipNotReady,
        ),
        buildChip(
          icon: Icons.book,
          label: l10n.homePhaseGlossary,
          on: effectiveGlossary && !effectiveGlossarySkipped,
          skipped: effectiveGlossarySkipped,
          onTap: () {
            if (hasGlossaryTab) {
              final int idx = tabsState.tabs.indexWhere(
                (PreviewTab t) => t.type.toString().endsWith('glossary'),
              );
              if (idx >= 0) tabsNotifier.switchToTab(idx);
            }
          },
          tooltip: effectiveGlossarySkipped
              ? l10n.translationStepsGlossaryTooltipSkipped
              : (effectiveGlossary
                  ? l10n.translationStepsGlossaryTooltipEnabled
                  : l10n.translationStepsGlossaryTooltipDisabled),
        ),
        buildChip(
          icon: Icons.translate,
          label: l10n.homePhaseTranslate,
          on: effectiveTranslate,
          onTap: () {
            int idx = tabsState.tabs
                .indexWhere((PreviewTab t) => t.id == 'translate_tab');
            if (idx < 0) {
              idx = tabsState.tabs
                  .indexWhere((PreviewTab t) => t.id == 'convert_tab');
            }
            if (idx >= 0) tabsNotifier.switchToTab(idx);
          },
          tooltip: effectiveTranslate
              ? l10n.translationStepsTranslateTooltipReady
              : l10n.translationStepsTranslateTooltipNotReady,
        ),
      ],
    );
  }

  Future<void> _loadPersistedTabs() async {
    if (widget.flowId == null) return;
    final PreviewTabsNotifier tabsNotifier = widget.flowId != null
        ? ref.read(previewTabsProviderFamily(widget.flowId!).notifier)
        : ref.read(previewTabsProvider.notifier);

    // Use cache to avoid repeated SharedPreferences reads
    final FlowDataCache cache = FlowDataCache();
    final List<Map<String, dynamic>> tabsData =
        await cache.getTabsData(widget.flowId);
    final List<Map<String, dynamic>> closedTabsData =
        await cache.getClosedTabsData(widget.flowId);

    // Recreate tabs from persisted data
    // Skip translationResult tabs - they are temporary and should only exist when translation completes
    // Note: Persistence is already scoped by flowId, so no need to filter here
    for (final Map<String, dynamic> tabData in tabsData) {
      final String typeStr = tabData['type'] as String? ?? '';
      if (typeStr == 'PreviewTabType.translationResult') {
        continue; // Skip translationResult tabs at startup
      }

      final PreviewTab? tab = _recreateTabFromData(tabData);
      if (tab != null) {
        tabsNotifier.addTab(tab);
      }
    }

    // Recreate closed tabs (also skip translationResult tabs)
    // Note: Persistence is already scoped by flowId, so no need to filter here
    final List<PreviewTab> closedTabs = <PreviewTab>[];
    for (final Map<String, dynamic> tabData in closedTabsData) {
      final String typeStr = tabData['type'] as String? ?? '';
      if (typeStr == 'PreviewTabType.translationResult') {
        continue; // Skip translationResult tabs in closed tabs
      }

      final PreviewTab? tab = _recreateTabFromData(tabData);
      if (tab != null) {
        closedTabs.add(tab);
      }
    }
    if (closedTabs.isNotEmpty) {
      // Update closed tabs using notifier method
      tabsNotifier.setClosedTabs(closedTabs);
    }
  }

  PreviewTab? _recreateTabFromData(Map<String, dynamic> tabData) {
    try {
      final PreviewTabType type = PreviewTabType.values.firstWhere(
        (PreviewTabType e) => e.toString() == tabData['type'],
        orElse: () => PreviewTabType.translationResult,
      );
      final Map<String, dynamic>? dataRef = tabData['dataRef'] is Map
          ? (tabData['dataRef'] as Map).cast<String, dynamic>()
          : null;

      Widget content;
      final String title =
          tabData['title'] is String ? tabData['title'] as String : 'Preview';

      switch (type) {
        case PreviewTabType.translationResult:
          final String taskId =
              dataRef?['taskId'] is String ? dataRef!['taskId'] as String : '';
          final String? fileName = dataRef?['fileName'] is String
              ? dataRef!['fileName'] as String
              : null;
          final downloadsValue = dataRef?['downloads'];
          final Map<String, dynamic>? downloads = downloadsValue is Map
              ? downloadsValue.cast<String, dynamic>()
              : null;
          final bool isTextModeFromData = dataRef?['isTextMode'] == true;
          final String? workflowTypeFromData =
              dataRef?['workflowType'] as String?;
          final bool initialMergedFromData =
              dataRef?['viewMode'] == 'clean';
          // Content will be loaded automatically when tab is opened
          content = TranslationResultPreview(
            taskId: taskId,
            flowId: dataRef?['flowId'] as String?,
            fileName: fileName,
            downloads: downloads
                ?.map((String k, v) => MapEntry(k.toString(), v.toString())),
            isTextMode: isTextModeFromData,
            workflowType: workflowTypeFromData,
            initialMergedView: initialMergedFromData,
          );
          break;
        case PreviewTabType.glossary:
          final glossaryDataValue = dataRef?['glossaryData'];
          debugPrint(
            '[TRANSLATION_SCREEN] _recreateTabFromData: Recreating glossary tab, glossaryDataValue type: ${glossaryDataValue.runtimeType}',
          );
          debugPrint(
            '[TRANSLATION_SCREEN] _recreateTabFromData: glossaryDataValue is Map: ${glossaryDataValue is Map}',
          );
          if (glossaryDataValue is Map) {
            debugPrint(
              '[TRANSLATION_SCREEN] _recreateTabFromData: glossaryDataValue keys: ${glossaryDataValue.keys.take(5).toList()}...',
            );
          }
          // Convert to regular Map to avoid IdentityMap issues
          final Map<String, dynamic> glossaryData = glossaryDataValue is Map
              ? Map<String, dynamic>.from(glossaryDataValue)
              : <String, dynamic>{};
          debugPrint(
            '[TRANSLATION_SCREEN] _recreateTabFromData: Final glossaryData length: ${glossaryData.length}',
          );
          final String? glossaryFlowId =
              dataRef?['flowId'] as String? ?? widget.flowId;
          final String? glossaryTargetLang = dataRef?['targetLang'] as String?;
          final Object currentNotifier = widget.flowId != null
              ? ref
                  .read(translationStateProviderFamily(widget.flowId!).notifier)
              : ref.read(translationStateProvider.notifier);
          content = GlossaryPreview(
            glossaryId: tabData['id'] as String? ?? '',
            glossaryData: glossaryData,
            flowId: glossaryFlowId,
            targetLang: glossaryTargetLang,
            onSave: (Map<String, dynamic> updatedGlossary) {
              // Save callback (glossary will be auto-applied to FlowContext if flowId is set)
              if (mounted) {
                _showSnackBar('Glossary saved', Colors.green);
              }
            },
            onCancelGlossary: () => _cancelGlossaryGeneration(currentNotifier),
            onEditingStateChanged: (bool isEditing) {
              // Update glossary editing state to disable/enable translate button
              if (mounted) {
                setState(() {
                  _isGlossaryEditing = isEditing;
                });
              }
            },
          );
          break;
        case PreviewTabType.formatConversion:
          final String taskId = dataRef?['taskId'] as String? ?? '';
          final downloadsValue = dataRef?['downloads'];
          final Map<String, String> downloads = downloadsValue is Map
              ? downloadsValue.cast<String, String>()
              : <String, String>{};
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
                if (downloads.isNotEmpty) ...<Widget>[
                  const SizedBox(height: 16),
                  const Text('Download files to view converted content.'),
                ],
              ],
            ),
          );
          break;
      }

      // Create tab without icon - will use defaultIcon (compile-time constant)
      // This ensures IconData is a compile-time constant for tree-shaking
      final PreviewTab tab = PreviewTab(
        id: tabData['id'] as String? ?? '',
        type: type,
        title: title,
        content: content,
        createdAt: tabData['createdAt'] != null
            ? DateTime.parse(tabData['createdAt'] as String)
            : null,
        dataRef: dataRef,
      );

      return tab;
    } catch (e) {
      print('Error recreating tab: $e');
      return null;
    }
  }

  @override
  Widget build(BuildContext context) {
    // Verify that this widget's flowId matches the active task to prevent state confusion
    if (widget.flowId != null) {
      final TasksState tasks = ref.watch(tasksProvider);
      // Only render content if this flow is currently active
      if (tasks.activeTaskId != widget.flowId) {
        // This flow is not active, return empty widget to prevent state confusion
        return const SizedBox.shrink();
      }
    }

    final dynamic translationState = widget.flowId != null
        ? ref.watch(translationStateProviderFamily(widget.flowId!))
        : ref.watch(translationStateProvider);
    final dynamic translationNotifier = widget.flowId != null
        ? ref.read(translationStateProviderFamily(widget.flowId!).notifier)
        : ref.read(translationStateProvider.notifier);
    final PreviewTabsState tabsState = widget.flowId != null
        ? ref.watch(previewTabsProviderFamily(widget.flowId!))
        : ref.watch(previewTabsProvider);
    final TranslationQuickSettings qs = widget.flowId != null
        ? ref.watch(translationQuickSettingsProviderFamily(widget.flowId!))
        : ref.watch(translationQuickSettingsProvider);

    // Monitor language changes and update excluded segments
    // CRITICAL: Also update on initial load if task exists (to ensure exclusion matches current language)
    final bool isLanguageChanged =
        _previousTargetLang != null && _previousTargetLang != qs.toLang;
    final bool isInitialLoad = _previousTargetLang == null &&
        translationState.taskId != null &&
        (translationState.taskId as String).isNotEmpty;

    if ((isLanguageChanged || isInitialLoad) &&
        translationState.taskId != null &&
        (translationState.taskId as String).isNotEmpty &&
        !_isUpdatingExcluded) {
      // Language changed or initial load, update excluded segments to match current language
      WidgetsBinding.instance.addPostFrameCallback((_) {
        _updateExcludedSegmentsForLanguage(
          translationState.taskId as String,
          qs.toLang,
        );
      });
    }
    _previousTargetLang = qs.toLang;

    // Save steps state to persistence when it changes (even though StepBar is not displayed)
    if (widget.flowId != null) {
      final bool hasUpload = translationState.pickedFile != null;
      final bool hasTask = translationState.taskId != null &&
          (translationState.taskId as String).isNotEmpty;
      final bool hasExtract =
          hasTask; // Import triggers Convert which prepares preview; treat as extracted
      final bool hasGlossaryTab = tabsState.tabs
          .any((PreviewTab t) => t.type.toString().endsWith('glossary'));
      final bool hasGlossarySelected = qs.selectedGlossaries.isNotEmpty;
      final bool glossarySkipped =
          _glossarySkipped && !hasGlossaryTab && !hasGlossarySelected;
      final bool hasTranslate =
          (translationState.statusText.toString().toLowerCase() == 'completed');

      WidgetsBinding.instance.addPostFrameCallback((_) {
        _saveStepsState(
          uploadCompleted: hasUpload,
          extractCompleted: hasExtract,
          glossaryCompleted: hasGlossaryTab || hasGlossarySelected,
          glossarySkipped: glossarySkipped,
          translateCompleted: hasTranslate,
        );
      });
    }

    final Widget body = Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: <Widget>[
        // Toolbar at the top
        _buildToolbar(translationState, translationNotifier),
        // URL fetch panel (shown below toolbar when button is clicked)
        if (_showUrlInput && !_isTextMode)
          _buildUrlInputPanel(translationNotifier),
        // Content area
        Expanded(
          child: Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: <Widget>[
                  // Left Panel (collapsible) - Fixed width so right panel gets all remaining space (no Flexible; Flexible was taking 1/4 of Row and left 86px gap)
                  if (!_isLeftPanelCollapsed)
                    ConstrainedBox(
                      constraints: const BoxConstraints(
                        minWidth:
                            200, // Minimum width
                        maxWidth: 260, // Maximum width
                      ),
                      child: DecoratedBox(
                        decoration: BoxDecoration(
                          color: Theme.of(context).colorScheme.surface,
                          border: Border(
                            right: BorderSide(
                              color: Theme.of(context).dividerColor,
                            ),
                          ),
                        ),
                        child: SingleChildScrollView(
                          padding:
                              const EdgeInsets.all(4), // Reduced from 16 to 4
                          child: Column(
                            crossAxisAlignment:
                                CrossAxisAlignment.stretch,
                            children: <Widget>[
                              // Steps are now shown in Workspace left panel
                              const SizedBox.shrink(),
                              // Document Card removed - file name now shown in toolbar
                              // Quick Settings Section - Show different Quick Settings based on flow type
                              _buildQuickSettings(),
                            ],
                          ),
                        ),
                      ),
                    ),
                  // Collapse/Expand button
                  Container(
                width: 12,
                decoration: BoxDecoration(
                  color: Theme.of(context).colorScheme.surfaceContainerHighest,
                  border: Border(
                    left: _isLeftPanelCollapsed
                        ? BorderSide.none
                        : BorderSide(
                            color: Theme.of(context).dividerColor,
                          ),
                    right: BorderSide(
                      color: Theme.of(context).dividerColor,
                    ),
                  ),
                ),
                child: Column(
                  mainAxisAlignment: MainAxisAlignment.center,
                  children: <Widget>[
                    IconButton(
                      icon: Icon(
                        _isLeftPanelCollapsed
                            ? Icons.chevron_right
                            : Icons.chevron_left,
                        size: 12,
                      ),
                      padding: EdgeInsets.zero,
                      constraints: const BoxConstraints(
                        minWidth: 12,
                        minHeight: 48,
                      ),
                      tooltip: _isLeftPanelCollapsed
                          ? AppLocalizations.of(context)!
                              .translationLeftPanelExpandTooltip
                          : AppLocalizations.of(context)!
                              .translationLeftPanelCollapseTooltip,
                      onPressed: () {
                        setState(() {
                          _isLeftPanelCollapsed = !_isLeftPanelCollapsed;
                        });
                      },
                    ),
                  ],
                ),
              ),
                  // Right Panel - Preview Area (takes remaining space); expand to fill parent
                  Expanded(
                    flex: _isLeftPanelCollapsed ? 1 : 3,
                    child: SizedBox.expand(
                      child: _buildPreviewPanel(translationState),
                    ),
                  ),
                ],
              ),
        ),
      ],
    );

    if (widget.flowId == null && widget.executionMode == 'queued') {
      return PopScope(
        canPop: false,
        onPopInvokedWithResult: (bool didPop, Object? result) {
          if (didPop) {
            return;
          }
          _exitStandaloneQueuedToQueue();
        },
        child: body,
      );
    }
    return body;
  }

  Widget _buildQuickSettings() {
    // Verify that this widget's flowId matches the active task to prevent state confusion
    if (widget.flowId != null) {
      final TasksState tasks = ref.watch(tasksProvider);
      // Only show quick settings if this flow is currently active
      if (tasks.activeTaskId != widget.flowId) {
        // This flow is not active, return empty widget to prevent state confusion
        return const SizedBox.shrink();
      }
    }

    return TranslationQuickSettingsWidget(flowId: widget.flowId);
  }

  Color _getStatusColor(state) {
    if (state.isTranslating) {
      return Colors.blue.shade700;
    }
    switch (state.statusText.toLowerCase()) {
      case 'completed':
        return Colors.green.shade700;
      case 'failed':
      case 'error':
        return Colors.red.shade700;
      case 'cancelled':
        return Colors.orange.shade700;
      default:
        return Colors.grey.shade600;
    }
  }

  IconData _getStatusIcon(state) {
    if (state.isTranslating) {
      return Icons.autorenew;
    }
    switch (state.statusText.toLowerCase()) {
      case 'completed':
        return Icons.check_circle;
      case 'failed':
      case 'error':
        return Icons.error;
      case 'cancelled':
        return Icons.cancel;
      default:
        return Icons.info;
    }
  }

  String _getStatusDisplayText(state) {
    final l10n = AppLocalizations.of(context)!;
    if (state.isTranslating) {
      return l10n.translationStatusTranslatingFallback;
    }
    switch (state.statusText.toLowerCase()) {
      case 'completed':
        return l10n.translationStatusCompleted;
      case 'failed':
      case 'error':
        return l10n.translationStatusFailed;
      case 'cancelled':
        return l10n.translationStatusCancelled;
      case 'pending':
        return l10n.translationStatusTaskPending;
      case 'processing':
        return l10n.translationStatusProcessing;
      default:
        return state.statusText.isNotEmpty
            ? state.statusText
            : l10n.translationStatusReady;
    }
  }

  String _getTranslationStatsText(state) {
    final l10n = AppLocalizations.of(context)!;
    if (state.totalSegments == null || state.totalSegments == 0) {
      return '';
    }
    final success = state.successCount ?? 0;
    final fail = state.failCount ?? 0;
    final total = state.totalSegments;
    if (fail > 0) {
      return l10n.translationStatsSuccessFailed(
        fail.toString(),
        success.toString(),
        total.toString(),
      );
    }
    return l10n.translationStatsSuccessOnly(
      success.toString(),
      total.toString(),
    );
  }

  /// Convert language code to language name for backend API
  String _convertLangCodeToName(String langCode) {
    // Handle specific regional/script variants first
    final String lower = langCode.toLowerCase().trim();
    if (lower == 'zh-tw' || lower == 'zh_hant') {
      return 'Chinese (Traditional)';
    }

    const Map<String, String> languageMap = <String, String>{
      'zh': 'Chinese',
      'en': 'English',
      'ja': 'Japanese',
      'ko': 'Korean',
      'fr': 'French',
      'de': 'German',
      'es': 'Spanish',
      'ru': 'Russian',
      'it': 'Italian',
      'pt': 'Portuguese',
      'ar': 'Arabic',
      'th': 'Thai',
      'vi': 'Vietnamese',
      'he': 'Hebrew',
      'hi': 'Hindi',
      'pl': 'Polish',
      'nl': 'Dutch',
      'da': 'Danish',
      'nb': 'Norwegian',
      'sv': 'Swedish',
      'fi': 'Finnish',
      'el': 'Greek',
      'lt': 'Lithuanian',
      'ro': 'Romanian',
      'uk': 'Ukrainian',
      'ca': 'Catalan',
      'cs': 'Czech',
      'hr': 'Croatian',
      'tr': 'Turkish',
      'ur': 'Urdu',
      'bn': 'Bengali',
      'ms': 'Malay',
      'sl': 'Slovenian',
      'mk': 'Macedonian',
      'km': 'Khmer',
      'fil': 'Filipino',
    };
    // Normalize language code (handle variations like 'zh-CN' -> 'zh')
    final String normalized = lower.split('-').first.trim();
    return languageMap[normalized] ?? langCode; // Fallback to code if not found
  }

  /// Normalize language code for comparison
  /// Maps various language code formats to a standard format
  String _normalizeLanguageCode(String langCode) {
    final String normalized = langCode.toLowerCase().trim();

    // Map common variations to standard codes
    const Map<String, String> langMap = <String, String>{
      'zh-cn': 'zh',
      'zh-tw': 'zh',
      'zh-hans': 'zh',
      'zh-hant': 'zh',
      'zh': 'zh',
      'en': 'en',
      'en-us': 'en',
      'en-gb': 'en',
      'ja': 'ja',
      'ko': 'ko',
      'fr': 'fr',
      'de': 'de',
      'es': 'es',
      'ru': 'ru',
      'pt': 'pt',
      'it': 'it',
      'ar': 'ar',
      'vi': 'vi',
    };

    return langMap[normalized] ?? normalized;
  }

  /// True if [filename] has an image extension (e.g. PNG, JPG).
  /// Used to skip Language Match Warning for image translation (OCR result language often matches target).
  /// Returns [value] if non-null and non-empty, otherwise [fallback].
  static String _nonEmpty(String? value, String fallback) {
    return (value != null && value.isNotEmpty) ? value : fallback;
  }

  static bool _isImageFileName(String? filename) {
    if (filename == null || filename.isEmpty) return false;
    const Set<String> imageExtensions = <String>{
      'png',
      'jpg',
      'jpeg',
      'gif',
      'webp',
      'bmp',
      'tiff',
      'tif',
    };
    final String ext = filename.split('.').last.toLowerCase();
    return imageExtensions.contains(ext);
  }

  String _formatDuration(Duration duration) {
    final int hours = duration.inHours;
    final int minutes = duration.inMinutes.remainder(60);
    final int seconds = duration.inSeconds.remainder(60);

    if (hours > 0) {
      return '${hours}h ${minutes}m ${seconds}s';
    } else if (minutes > 0) {
      return '${minutes}m ${seconds}s';
    } else {
      return '${seconds}s';
    }
  }

  Future<void> _cancelTranslation(state, notifier) async {
    if (state.taskId == null) return;

    try {
      final TranslationService svc = TranslationService();
      await svc.cancelTask(state.taskId!);
      notifier.setTranslating(false);
      notifier.setStatusText('cancelled');
      final DateTime endTime = DateTime.now();
      notifier.setEndTime(endTime);
      if (state.startTime != null) {
        notifier.setTotalDuration(endTime.difference(state.startTime!));
      }
      if (mounted) {
        final l10n = AppLocalizations.of(context)!;
        _showSnackBar(
          l10n.translationSnackTranslationCancelled,
          Colors.orange,
        );
      }
    } catch (e) {
      if (mounted) {
        final l10n = AppLocalizations.of(context)!;
        _showSnackBar(
          l10n.translationSnackFailedToCancel(e.toString()),
          Colors.red,
        );
      }
    }
  }

  void _resetTranslation(notifier) {
    notifier.resetTranslation();
  }

  String get _queuePersistScopeKey =>
      widget.flowId ?? kQueuePersistStandaloneScope;

  void _markQueuePersistDirty() {
    ref
        .read(queuePersistDirtyProvider(_queuePersistScopeKey).notifier)
        .markDirty();
  }

  void _clearQueuePersistDirty() {
    ref
        .read(queuePersistDirtyProvider(_queuePersistScopeKey).notifier)
        .clear();
  }

  /// Clears global translation UI state for `/translation?execution_mode=queued` (no flowId).
  void _prepareFreshStandaloneQueuedSession() {
    if (widget.flowId != null || widget.executionMode != 'queued') {
      return;
    }
    ref.read(translationStateProvider.notifier).resetTranslation();
    ref.read(previewTabsProvider.notifier).clearAllTabs();
    _textController.clear();
    _autoPersistedQueueTaskIds.clear();
    _clearQueuePersistDirty();
    _hasStartedTranslationInThisSession = false;
    _glossarySkipped = false;
    _hasShownLanguageWarning = false;
    _isTextMode = false;
  }

  /// Initializes the screen for re-editing a completed queued translation task.
  /// Bypasses file upload/extract and opens the Translate tab directly.
  void _initStandaloneQueuedReeditSession() {
    ref.read(translationStateProvider.notifier).resetTranslation();
    _textController.clear();
    _autoPersistedQueueTaskIds.clear();
    _clearQueuePersistDirty();
    _hasStartedTranslationInThisSession = false;
    _glossarySkipped = false;
    _hasShownLanguageWarning = false;
    _isTextMode = false;

    _addReeditTranslationResultTab();
  }

  Future<void> _persistQueueSnapshotAuto(String taskId) async {
    try {
      final TranslationService svc = TranslationService();
      final dynamic st = _getCurrentTranslationState();
      final String? fileName = _isReeditMode
          ? widget.reeditFileName
          : st.pickedFile?.name as String?;
      final bool primaryOnly = widget.executionMode != 'queued' &&
          isMineruLayoutImageFileName(fileName);
      await svc.persistQueueSnapshot(
        taskId,
        exportScope: primaryOnly ? 'primary_only' : 'full',
      );
      if (mounted) {
        _clearQueuePersistDirty();
      }
    } catch (e, st) {
      // Ignore 400 Bad Request errors during auto-persist (e.g., task not completed yet
      // or segments not ready). This is a non-critical background operation.
      final String errStr = e.toString();
      final bool isBadRequest = errStr.contains('400') || errStr.contains('bad response');
      _translationScreenLog(
        'Auto persist queue snapshot failed: $e${isBadRequest ? " (ignored, will retry later)" : ""}',
        level: isBadRequest ? LogLevel.info : LogLevel.warn,
      );
      // Only mark dirty for non-400 errors; 400 errors will auto-retry on next poll
      if (mounted && !isBadRequest) {
        _markQueuePersistDirty();
      }
    }
  }

  Future<void> _persistQueueSnapshotManual({
    bool showSuccessSnack = true,
  }) async {
    final dynamic st = _getCurrentTranslationState();
    final String? tid = _isReeditMode
        ? widget.reeditTaskId
        : st.taskId as String?;
    if (tid == null || tid.isEmpty) {
      return;
    }
    setState(() {
      _queuePersistInFlight = true;
    });
    try {
      final TranslationService svc = TranslationService();
      await svc.persistQueueSnapshot(tid);
      if (mounted) {
        _clearQueuePersistDirty();
        if (showSuccessSnack) {
          final AppLocalizations l10n = AppLocalizations.of(context)!;
          _showSnackBar(l10n.translationPersistQueueSuccess, Colors.green);
        }
      }
    } catch (e) {
      if (mounted) {
        final AppLocalizations l10n = AppLocalizations.of(context)!;
        _showSnackBar(
          l10n.translationPersistQueueFailed(e.toString()),
          Colors.red,
        );
      }
    } finally {
      if (mounted) {
        setState(() {
          _queuePersistInFlight = false;
        });
      }
    }
  }

  Future<String?> _showQueuePersistDiscardDialog(AppLocalizations l10n) => showDialog<String>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: Text(l10n.translationCloseTranslateTabTitle),
        content: SingleChildScrollView(
          child: Text(l10n.translationCloseTranslateTabMessage),
        ),
        actions: <Widget>[
          TextButton(
            onPressed: () => Navigator.of(ctx).pop('stay'),
            child: Text(l10n.translationCloseTranslateTabStay),
          ),
          TextButton(
            onPressed: () => Navigator.of(ctx).pop('close_anyway'),
            child: Text(l10n.translationCloseTranslateTabClose),
          ),
          FilledButton(
            onPressed: () => Navigator.of(ctx).pop('save_and_close'),
            child: Text(l10n.translationCloseTranslateTabSaveAndClose),
          ),
        ],
      ),
    );

  Future<bool> _confirmExitStandaloneQueuedIfNeeded() async {
    final bool dirty =
        ref.read(queuePersistDirtyProvider(_queuePersistScopeKey));
    if (!dirty) {
      return true;
    }
    final AppLocalizations l10n = AppLocalizations.of(context)!;
    final String? choice = await _showQueuePersistDiscardDialog(l10n);
    if (choice == null || choice == 'stay') {
      return false;
    }
    if (choice == 'close_anyway') {
      return true;
    }
    await _persistQueueSnapshotManual(showSuccessSnack: false);
    if (!mounted) {
      return false;
    }
    final bool stillDirty =
        ref.read(queuePersistDirtyProvider(_queuePersistScopeKey));
    if (stillDirty) {
      return false;
    }
    return true;
  }

  Future<void> _exitStandaloneQueuedToQueue() async {
    if (widget.flowId != null || widget.executionMode != 'queued') {
      return;
    }
    final bool ok = await _confirmExitStandaloneQueuedIfNeeded();
    if (!ok || !mounted) {
      return;
    }
    _prepareFreshStandaloneQueuedSession();
    if (!mounted) {
      return;
    }
    if (context.canPop()) {
      context.pop();
    } else {
      context.go(AppRouter.translationQueueRoute);
    }
  }

  Future<bool> _confirmTranslateTabCloseIfNeeded(PreviewTab tab) async {
    if (tab.id != 'translate_tab') {
      return true;
    }
    // When inside a flow, tab-level close is silent — the flow-level close
    // dialog (in workspace_screen._confirmCloseFlow) handles save / exit / destroy.
    if (widget.flowId != null) {
      return true;
    }
    // Check dirty state first (unsaved segment edits)
    final bool dirty =
        ref.read(queuePersistDirtyProvider(_queuePersistScopeKey));
    if (dirty) {
      final AppLocalizations l10n = AppLocalizations.of(context)!;
      final String? choice = await _showQueuePersistDiscardDialog(l10n);
      if (choice == null || choice == 'stay') {
        return false;
      }
      if (choice == 'close_anyway') {
        return true;
      }
      await _persistQueueSnapshotManual(showSuccessSnack: false);
      if (!mounted) {
        return false;
      }
      final bool stillDirty =
          ref.read(queuePersistDirtyProvider(_queuePersistScopeKey));
      if (stillDirty) {
        return false;
      }
      return true;
    }
    // Not dirty -- check if task is completed and ask whether to keep in queue
    final dynamic translationState = widget.flowId != null
        ? ref.read(translationStateProviderFamily(widget.flowId!))
        : ref.read(translationStateProvider);
    final String? taskId = translationState.taskId as String?;
    // Only show keep/discard dialog for completed tasks (has downloads, not translating)
    if (taskId != null &&
        taskId.isNotEmpty &&
        !taskId.startsWith('pending_') &&
        !(translationState.isTranslating == true) &&
        (translationState.downloads is Map &&
            (translationState.downloads as Map).isNotEmpty)) {
      final AppLocalizations l10n = AppLocalizations.of(context)!;
      final String? choice = await _showQueueKeepOrDiscardDialog(l10n);
      if (choice == null || choice == 'keep') {
        // Keep in queue -- just close the tab without releasing
        return true;
      }
      // Discard -- release task resources, then close
      try {
        final TranslationService svc = TranslationService();
        await svc.releaseTask(taskId);
      } catch (_) {
        // Ignore release errors; proceed with close anyway
      }
    }
    return true;
  }

  Future<String?> _showQueueKeepOrDiscardDialog(AppLocalizations l10n) =>
      showDialog<String>(
        context: context,
        builder: (ctx) => AlertDialog(
          title: Text(l10n.translationCloseTranslateTabKeepTitle),
          content: Text(l10n.translationCloseTranslateTabKeepMessage),
          actions: <Widget>[
            TextButton(
              onPressed: () => Navigator.of(ctx).pop('keep'),
              child: Text(l10n.translationCloseTranslateTabKeepInQueue),
            ),
            TextButton(
              onPressed: () => Navigator.of(ctx).pop('discard'),
              style: TextButton.styleFrom(
                foregroundColor: Theme.of(context).colorScheme.error,
              ),
              child: Text(l10n.translationCloseTranslateTabDiscard),
            ),
          ],
        ),
      );

  String _formatTokenCount(int count) {
    if (count < 1000) return '$count';
    if (count < 1000000) return '${(count / 1000).toStringAsFixed(1)}K';
    return '${(count / 1000000).toStringAsFixed(1)}M';
  }

  bool _supportsRevisionPreviewTask(dynamic state) {
    final String? fileName = state.pickedFile?.name ?? widget.reeditFileName;
    if (fileName == null || fileName.isEmpty) {
      return false;
    }
    if (fileName.toLowerCase().endsWith('.pdf')) {
      return true;
    }
    return isMineruLayoutImageFileName(fileName);
  }

  void _switchToTranslationResultTabIfNeeded() {
    final PreviewTabsState tabsState = widget.flowId != null
        ? ref.read(previewTabsProviderFamily(widget.flowId!))
        : ref.read(previewTabsProvider);
    final int tabIndex = tabsState.tabs.indexWhere(
      (PreviewTab tab) =>
          tab.type == PreviewTabType.translationResult ||
          tab.id == 'translate_tab' ||
          tab.id == 'translate_reedit_tab',
    );
    if (tabIndex < 0) {
      return;
    }
    if (tabIndex == tabsState.activeTabIndex) {
      return;
    }
    final dynamic tabsNotifier = widget.flowId != null
        ? ref.read(previewTabsProviderFamily(widget.flowId!).notifier)
        : ref.read(previewTabsProvider.notifier);
    tabsNotifier.switchToTab(tabIndex);
  }

  void _openPdfRevisionMode(dynamic state) {
    final String? taskId = state.taskId as String?;
    if (taskId == null || taskId.isEmpty) {
      return;
    }
    final String scopeKey = widget.flowId ?? taskId;
    _switchToTranslationResultTabIfNeeded();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (!mounted) {
        return;
      }
      WidgetsBinding.instance.addPostFrameCallback((_) {
        if (mounted) {
          triggerPdfRevisionLaunch(ref, scopeKey);
        }
      });
    });
  }

  Future<void> _retranslateFailedSegments(
    state,
    notifier,
  ) async {
    // Prevent re-entry
    if (state.currentOperation != TranslationOperation.none) {
      return;
    }

    if (state.taskId == null) return;

    try {
      notifier.setCurrentOperation(TranslationOperation.retranslating);
      // Get all translation segments to find failed ones
      final TranslationService svc = TranslationService();
      final Map<String, dynamic> segmentsData =
          await svc.getTranslationSegments(state.taskId!);
      final List<dynamic> segments =
          segmentsData['segments'] as List<dynamic>? ?? <dynamic>[];

      // Find all failed segments (excluding cleared and excluded segments)
      final List<int> failedIndices = <int>[];
      for (final segment in segments) {
        final int? index = segment['segment_index'] as int?;
        final bool isFailed = segment['is_failed'] as bool? ?? false;
        final bool needsRetry = segment['needs_retry'] as bool? ?? false;
        final bool isExcluded = segment['is_excluded'] as bool? ?? false;
        final String? status = segment['status'] as String?;
        // CRITICAL: Skip cleared segments - they should not be retranslated
        // Skip excluded segments - they should not be retranslated
        if (index != null &&
            (isFailed || needsRetry) &&
            !isExcluded &&
            status != 'cleared') {
          failedIndices.add(index);
        }
      }

      if (failedIndices.isEmpty) {
        // No segments need retry - finish the task directly
        final dynamic translationNotifier = widget.flowId != null
            ? ref.read(translationStateProviderFamily(widget.flowId!).notifier)
            : ref.read(translationStateProvider.notifier);
        translationNotifier.setTranslating(false);
        translationNotifier.setProgress(100);
        translationNotifier.setStatusText('completed');
        if (mounted) {
          triggerTranslationRefresh(ref);
        }
        notifier.setCurrentOperation(TranslationOperation.none);
        return;
      }

      // Proceed immediately without confirmation dialog
      // Store cancel function for this retry operation
      Future<void> cancelBatchRetry() async {
        if (_isBatchRetryCancelling) return;
        _isBatchRetryCancelling = true;
        
        // Call backend cancel API
        try {
          await svc.cancelBatchRetry(state.taskId!);
          _translationScreenLog('Batch retry cancel requested');
        } catch (e) {
          _translationScreenLog('Failed to send cancel request: $e');
        }
        
        if (mounted) {
          _showSnackBar(
            'Cancelling batch retry...',
            Colors.orange,
          );
        }
      }
      
      // Expose cancel function to UI
      _currentBatchRetryCancel = cancelBatchRetry;
      
      if (mounted) {
        _showSnackBar(
          'Retrying ${failedIndices.length} segment(s)...',
          Colors.orange,
        );
      }

      // Get the selected LLM platform (not rotation)
      final AIPlatformSettings aiPlatformSettings =
          ref.read(aiPlatformSettingsProvider);
      final String selectedPlatform = aiPlatformSettings.defaultPlatform;

      if (selectedPlatform.isEmpty) {
        if (mounted) {
          final l10n = AppLocalizations.of(context)!;
          _showSnackBar(
            l10n.translationSnackNoLlmpSelected,
            Colors.red,
          );
        }
        return;
      }

      // Get translation state notifier to update progress
      // NOTE: We pass all failed segments at once to backend, which will merge them
      // based on chunk_size (max token size), not fixed batch size
      final dynamic translationNotifier = widget.flowId != null
          ? ref.read(translationStateProviderFamily(widget.flowId!).notifier)
          : ref.read(translationStateProvider.notifier);

      // Retranslate failed segments concurrently with controlled concurrency
      // Process in batches using the same concurrent setting as main translation
      var successCount = 0;
      var failCount = 0;
      final int totalToRetranslate = failedIndices.length;
      final List<Map<String, dynamic>> allResults =
          <Map<String, dynamic>>[]; // Collect all results

      // Update status to show retranslation is in progress
      translationNotifier.setTranslating(true);
      translationNotifier.setStatusText('retranslating');
      // Start at 0% and let backend polling drive the actual progress.
      translationNotifier.setProgress(0);

      // CRITICAL: Pass all failed segments at once to enable backend chunk merging
      // Backend will merge segments based on chunk_size (max token size), not fixed batch size
      // This ensures retry uses the same chunking logic as translation process
      // CRITICAL: Get current target language and user prompt from QuickSettings (user's current selection)
      final TranslationQuickSettings qs = widget.flowId != null
          ? ref.read(translationQuickSettingsProviderFamily(widget.flowId!))
          : ref.read(translationQuickSettingsProvider);
      final String? toLang = qs.toLang.isNotEmpty ? qs.toLang : null;
      final String? userPrompt =
          (qs.taskNote != null && qs.taskNote!.trim().isNotEmpty)
              ? qs.taskNote!.trim()
              : null;

      // CRITICAL: Start polling for progress updates while retry is in progress
      // Backend updates task_state["progress"] during retry (10%-90%)
      // We need to poll to get these updates, similar to translation phase
      final TranslationService pollSvc = TranslationService();
      bool pollingActive = true;
      bool cancelRequested = false;

      // Start polling in background (don't await, let it run concurrently)
      // Use unawaited to avoid blocking
      pollSvc.pollUntilDone(
        state.taskId!,
        onUpdate: (Map<String, dynamic> status) {
          if (!pollingActive) return; // Stop updating if polling is cancelled
          if (_isBatchRetryCancelling) return; // Stop updating if user cancelled

          // Update progress from backend (10%-90% during retry)
          // Safely extract progress, handling null and invalid types
          final dynamic progressValue = status['progress'];
          final int progress = (progressValue is num)
              ? progressValue.toInt().clamp(0, 100)
              : ((progressValue is String && progressValue.isNotEmpty)
                  ? (int.tryParse(progressValue) ?? 0).clamp(0, 100)
                  : 0);
          final String statusText = (status['status'] ?? '').toString();
          final String message = (status['message'] ?? '').toString();

          // CRITICAL: Update progress during retry (status is 'processing' during batch retry)
          // Check both status and message to detect retry state reliably
          final bool isRetryInProgress = statusText == 'processing' && 
              (message.toLowerCase().contains('retranslat') || 
               message.toLowerCase().contains('preparing retranslation') ||
               message.toLowerCase().contains('batch retry'));
          final bool isTranslationPhase = statusText == 'processing' && 
              (message.startsWith('Translating') || 
               message.startsWith('Sending translation') ||
               message.startsWith('Generating output'));
          
          // Update progress during retry (but not during main translation to avoid conflicts)
          if (isRetryInProgress || (statusText == 'processing' && !isTranslationPhase)) {
            translationNotifier.setProgress(progress);
            if (message.isNotEmpty) {
              translationNotifier.setStatusText(message);
            }
          }
          
          // Check for cancellation in message
          if (message.toLowerCase().contains('cancelled')) {
            _isBatchRetryCancelling = true;
            pollingActive = false;
          }
        },
        intervalSec: 1, // Poll every 1 second for faster updates
      ).catchError((e) {
        // Ignore polling errors
        return <String, dynamic>{};
      });

      List<Map<String, dynamic>> results;
      try {
        // Start batch retry API call (this will update progress in backend)
        final Map<String, dynamic> batchResponse =
            await svc.retranslateSegmentsBatch(
          state.taskId!,
          failedIndices, // Pass all segments at once, not in batches
          platformKey: selectedPlatform,
          toLang: toLang,
          userPrompt: userPrompt, // User prompt (e.g. "请帮我翻译人名") for retry
        );

        // Stop polling and wait a bit for final status update
        pollingActive = false;
        await Future.delayed(
            const Duration(milliseconds: 500),); // Wait for final status

        // Check batch response
        final Map<String, dynamic>? segmentsMap =
            batchResponse['segments'] as Map<String, dynamic>?;
        final Map<String, dynamic>? errorsMap =
            batchResponse['errors'] as Map<String, dynamic>?;

        // Convert batch response to individual results format
        results = failedIndices.map((int index) {
          final String indexStr = index.toString();
          if (errorsMap != null && errorsMap.containsKey(indexStr)) {
            return <String, dynamic>{
              'success': false,
              'index': index,
              'error': errorsMap[indexStr],
            };
          }
          if (segmentsMap != null && segmentsMap.containsKey(indexStr)) {
            final segmentData = segmentsMap[indexStr] as Map<String, dynamic>?;
            if (segmentData != null) {
              final bool isFailed = segmentData['is_failed'] == true;
              if (isFailed) {
                final failureReason =
                    segmentData['failure_reason'] ?? 'Translation failed';
                return <String, dynamic>{
                  'success': false,
                  'index': index,
                  'error': failureReason,
                };
              }
            }
            return <String, Object>{'success': true, 'index': index};
          }
          // If segment not in response, assume failure
          return <String, dynamic>{
            'success': false,
            'index': index,
            'error': 'Segment not found in batch response',
          };
        }).toList();
      } catch (e) {
        // If batch API fails, fall back to individual retries (backward compatibility)
        // This should not happen, but provides a safety net
        results = await Future.wait(
          failedIndices.map((int index) async {
            try {
              // CRITICAL: Get current target language from QuickSettings (user's current selection)
              final TranslationQuickSettings qs = widget.flowId != null
                  ? ref.read(
                      translationQuickSettingsProviderFamily(widget.flowId!),)
                  : ref.read(translationQuickSettingsProvider);
              final String? toLang = qs.toLang.isNotEmpty ? qs.toLang : null;

              final Map<String, dynamic> response =
                  await svc.retranslateSegment(
                state.taskId!,
                index,
                platformKey: selectedPlatform,
                toLang: toLang,
                userPrompt: userPrompt,
              );

              final bool apiSuccess = response['success'] == true;
              if (!apiSuccess) {
                final errorMsg = response['error'] ?? 'Translation failed';
                return <String, dynamic>{
                  'success': false,
                  'index': index,
                  'error': errorMsg,
                };
              }

              final segmentData = response['segment'];
              if (segmentData != null && segmentData is Map) {
                final bool isFailed = segmentData['is_failed'] == true;
                if (isFailed) {
                  final failureReason =
                      segmentData['failure_reason'] ?? 'Translation failed';
                  return <String, dynamic>{
                    'success': false,
                    'index': index,
                    'error': failureReason,
                  };
                }
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
      }

      // Collect all results
      allResults.addAll(results);

      // Count retry results for logging
      for (final Map<String, dynamic> result in results) {
        if (result['success'] == true) {
          successCount++;
        } else {
          failCount++;
          if (mounted) {
            final int index = result['index'] as int;
            final error = result['error'];
            _translationScreenLog(
              'Failed to retranslate segment $index: $error',
            );
          }
        }
      }

      // Fetch overall statistics from backend (all segments, not just retried)
      // and set combined translation time (initial + retry)
      try {
        final Map<String, dynamic> allSegmentsData =
            await svc.getTranslationSegments(state.taskId!, forceRefresh: true);
        final List<dynamic> allSegments =
            allSegmentsData['segments'] as List<dynamic>? ?? <dynamic>[];

        var overallSuccess = 0;
        var overallFail = 0;
        for (final segment in allSegments) {
          final isFailed = segment['is_failed'] as bool? ?? false;
          final isExcluded = segment['is_excluded'] as bool? ?? false;
          final segmentStatus = segment['status'] as String?;
          if (isFailed && !isExcluded && segmentStatus != 'cleared') {
            overallFail++;
          } else if (!isExcluded && segmentStatus != 'cleared') {
            overallSuccess++;
          }
        }

        translationNotifier.setTranslationStats(
          successCount: overallSuccess,
          failCount: overallFail,
          totalSegments: allSegments.length,
        );
      } catch (e) {
        // Fallback: use retry-only counts if overall fetch fails
        _translationScreenLog(
          'Failed to fetch overall stats after retry: $e',
        );
        translationNotifier.setTranslationStats(
          successCount: successCount,
          failCount: failCount,
          totalSegments: totalToRetranslate,
        );
      }

      // Update translation time to include initial translation + retry time
      final DateTime retryEndTime = DateTime.now();
      translationNotifier.setEndTime(retryEndTime);
      final currentStateForTime = _getCurrentTranslationState();
      final DateTime? translationStartTime = currentStateForTime.startTime;
      if (translationStartTime != null) {
        translationNotifier.setTotalDuration(
          retryEndTime.difference(translationStartTime),
        );
      }

      // Update final status
      translationNotifier.setTranslating(false);
      translationNotifier.setProgress(100);
      translationNotifier.setStatusText('completed');

      // Show final result only if there are errors (progress is already shown in status bar)
      if (mounted) {
        if (failCount > 0) {
          // Only show message if there are failures
          final String message =
              'Retranslation complete: $successCount succeeded, $failCount failed';
          MessageService.showWarning(context, message);
        }
        // Success case: no message needed, status bar already shows the statistics

        // Update only the retranslated segments without full refresh
        // This preserves scroll position and only updates the changed segments
        final List<int> retranslatedIndices = <int>[];
        for (final Map<String, dynamic> result in allResults) {
          if (result['success'] == true) {
            final int index = result['index'] as int;
            retranslatedIndices.add(index);
          }
        }

        // Add a small delay to ensure backend has updated the segments
        // This prevents race condition where API returns stale data
        await Future.delayed(const Duration(milliseconds: 500));

        if (retranslatedIndices.isNotEmpty) {
          // Trigger partial update for successful segments
          triggerSegmentsUpdate(ref, retranslatedIndices);

          // Also trigger full refresh to ensure all metadata is updated
          // This ensures UI reflects the latest state even if partial update gets stale data
          triggerTranslationRefresh(ref);
        } else {
          // If no segments were successfully retranslated, do full refresh
          triggerTranslationRefresh(ref);
        }
        _markQueuePersistDirty();
      }
    } catch (e) {
      // Reset translation state on error
      final dynamic translationNotifier = widget.flowId != null
          ? ref.read(translationStateProviderFamily(widget.flowId!).notifier)
          : ref.read(translationStateProvider.notifier);
      translationNotifier.setTranslating(false);
      translationNotifier.setStatusText('failed');
      if (mounted) {
        MessageService.showError(context, 'Failed to retranslate: $e');
      }
    } finally {
      notifier.setCurrentOperation(TranslationOperation.none);
      // Clear batch retry cancel function
      _currentBatchRetryCancel = null;
      _isBatchRetryCancelling = false;
    }
  }

  Widget _buildToolbar(state, notifier) {
    // If widget.flowId is null, show toolbar (global translation screen)
    if (widget.flowId == null) {
      return _buildTranslationToolbar(state, notifier);
    }

    // Verify that this widget's flowId matches the active task to prevent state confusion
    final TasksState tasks = ref.watch(tasksProvider);
    // Only show toolbar if this flow is currently active
    if (tasks.activeTaskId != widget.flowId) {
      // This flow is not active, return empty toolbar to prevent state confusion
      return const SizedBox.shrink();
    }

    // Verify task exists and matches
    final Task task = tasks.tasks.firstWhere(
      (Task t) => t.id == widget.flowId,
      orElse: () => Task(
        id: widget.flowId!,
        type: TaskType.file,
        title: '',
        createdAt: DateTime.now(),
        updatedAt: DateTime.now(),
        plannedPhases: <PipelinePhase>[],
      ),
    );

    // Double-check: ensure task ID matches widget flowId
    if (task.id != widget.flowId) {
      return const SizedBox.shrink();
    }

    // Task is verified, show translation toolbar
    return _buildTranslationToolbar(state, notifier);
  }

  Widget _buildTranslationToolbar(state, notifier) {
    // Check if any operation is in progress
    final currentOperation =
        state.currentOperation ?? TranslationOperation.none;
    final bool isOperationInProgress =
        currentOperation != TranslationOperation.none;
    final hideDuringOperation =
        currentOperation == TranslationOperation.translating ||
            currentOperation == TranslationOperation.generatingGlossary ||
            currentOperation == TranslationOperation.converting;
    final hasImportedFile = !_isTextMode && state.pickedFile != null;
    final shouldShowModeToggle = !_isReeditMode && !hideDuringOperation && !hasImportedFile;
    // Disable Upload button if file is already uploaded and task is not cancelled
    final bool isTaskCancelled = state.statusText.toLowerCase() == 'cancelled';
    final bool shouldDisableUpload = _isReeditMode ||
        hasImportedFile &&
        state.taskId != null &&
        (state.taskId as String).isNotEmpty &&
        !isTaskCancelled;
    // Check if translation is completed (for button color changes)
    final bool isTranslationCompleted =
        state.statusText.toLowerCase() == 'completed';
    // Show Retry button whenever task is done (completed or progress 100), so it stays visible after retry
    final bool isTaskDone = isTranslationCompleted ||
        (state.progress != null && state.progress! >= 100);

    // Check if Extract is completed
    // Extract is considered completed when:
    // 1. There is no Extract tab yet (Extract hasn't started), OR
    // 2. There is an Extract tab AND segments can be rendered (Extract is complete when segments are ready), OR
    // 3. There is a Convert tab (Format Conversion completed, which includes Extract)
    // Key: When Extract tab exists and conversion is not in progress, segments should be ready to render
    final PreviewTabsState tabsState = widget.flowId != null
        ? ref.watch(previewTabsProviderFamily(widget.flowId!))
        : ref.watch(previewTabsProvider);
    final bool hasExtractTab =
        tabsState.tabs.any((PreviewTab t) => t.id == 'extract_tab');
    final bool hasConvertTab =
        tabsState.tabs.any((PreviewTab t) => t.id == 'convert_tab');
    final bool hasTaskId =
        state.taskId != null && (state.taskId as String).isNotEmpty;
    final bool isConverting =
        currentOperation == TranslationOperation.converting;
    // Extract is complete if:
    // - No Extract tab exists yet (Extract hasn't started), OR
    // - Extract tab exists AND conversion is not in progress (segments are ready to render), OR
    // - Convert tab exists (format conversion includes extract)
    final bool isExtractCompleted =
        !hasExtractTab || // No Extract tab yet, allow operations
            (hasExtractTab &&
                hasTaskId &&
                !isConverting) || // Extract tab exists, conversion is done, segments are ready
            hasConvertTab; // Convert tab indicates Extract/Format Conversion completed

    final l10n = AppLocalizations.of(context)!;

    return Container(
      decoration: BoxDecoration(
        color: Theme.of(context).colorScheme.surfaceContainerHighest,
        border: Border(
          bottom: BorderSide(
            color: Theme.of(context).dividerColor,
          ),
        ),
      ),
      padding: const EdgeInsets.symmetric(
        horizontal: 12,
        vertical: 4,
      ), // Adjusted padding to achieve 36px total height
      constraints: const BoxConstraints(
        minHeight: 36,
        maxHeight: 36,
      ), // Fixed height at 36px
      child: SingleChildScrollView(
        scrollDirection: Axis.horizontal,
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: <Widget>[
            if (widget.flowId == null && widget.executionMode == 'queued')
              IconButton(
                icon: const Icon(Icons.arrow_back),
                tooltip: l10n.translationQueueBackToQueueTooltip,
                padding: EdgeInsets.zero,
                constraints: const BoxConstraints(
                  minWidth: 36,
                  minHeight: 36,
                ),
                onPressed: _exitStandaloneQueuedToQueue,
              ),
          // Upload Button - Opens file picker and triggers Extract
          // CRITICAL: On Web, file picker must be called DIRECTLY in the callback to preserve user gesture context
          // Disabled if file is already uploaded and task is not cancelled
          OutlinedButton.icon(
            onPressed: shouldDisableUpload || isOperationInProgress
                ? null
                : (kIsWeb
                    ? () async {
                        // Web: Call picker IMMEDIATELY - no method calls, no checks, nothing before this
                        // Allow all supported formats in picker; Pro-only show hint in _processFile if not activated
                        FilePickerResult? result;
                        try {
                          final availableFormats = _getAllFileExtensions();
                          result = await FilePickerHelper.pickFiles(
                            type: FileType.custom,
                            allowedExtensions: availableFormats,
                            withData: true,
                          );
                        } catch (e, stackTrace) {
                          _translationScreenLog(
                            'File picker exception: $e\n$stackTrace',
                            level: LogLevel.error,
                          );
                          if (mounted) {
                            _showSnackBar(
                              'File selection error: ${e.toString()}. Please try again.',
                              Colors.red,
                            );
                          }
                          return;
                        }
                        // Now safe to check result and process
                        if (!mounted) return;
                        if (result == null) {
                          _translationScreenLog(
                            'File picker returned null. This could mean:\n'
                            '  1. User cancelled the file selection dialog\n'
                            '  2. Browser security policy blocked file access\n'
                            '  3. File picker dialog failed to open\n'
                            '  4. File was too large or inaccessible',
                            level: LogLevel.warn,
                          );
                          if (mounted) {
                            _showSnackBar(
                              'File selection was cancelled or blocked. Please drag and drop the file instead.',
                              Colors.orange,
                            );
                          }
                          return;
                        }
                        if (result.files.isEmpty) {
                          _translationScreenLog(
                            'File picker returned empty files',
                            level: LogLevel.warn,
                          );
                          if (mounted) {
                            _showSnackBar(
                              'No file was selected. Please try again.',
                              Colors.orange,
                            );
                          }
                          return;
                        }
                        final PlatformFile file = result.files.first;
                        // On Web, file.path is unavailable and accessing it causes an exception
                        // Only check path on non-Web platforms
                        String? filePathStr;
                        if (!kIsWeb) {
                          try {
                            filePathStr = file.path;
                          } catch (e) {
                            filePathStr = null;
                          }
                        }
                        _translationScreenLog(
                            'File selected: name=${file.name}, size=${file.size}, '
                            'hasBytes=${file.bytes != null}, hasPath=${filePathStr != null}');
                        if (file.bytes == null) {
                          _translationScreenLog(
                            'ERROR: file.bytes is null on Web! File may be too large or inaccessible.',
                            level: LogLevel.error,
                          );
                          if (mounted) {
                            _showSnackBar(
                              'File data not available. The file may be too large. Please try a smaller file or check browser console for errors.',
                              Colors.red,
                            );
                          }
                          return;
                        }
                        // Set operation state and process file
                        notifier.setCurrentOperation(
                          TranslationOperation.importing,
                        );
                        await _processFile(file, notifier);
                      }
                    : () => _pickFile(notifier)),
            icon: state.currentOperation == TranslationOperation.importing
                ? const SizedBox(
                    width: 16,
                    height: 16,
                    child: CircularProgressIndicator(strokeWidth: 2),
                  )
                : const Icon(Icons.upload_file, size: 16),
            label: Text(
              state.currentOperation == TranslationOperation.importing
                  ? l10n.translationToolbarUploading
                  : shouldDisableUpload
                      ? l10n.translationToolbarFileUploaded
                      : l10n.translationToolbarUpload,
              style: const TextStyle(fontSize: 13), // Reduced font size
            ),
            style: OutlinedButton.styleFrom(
              padding: const EdgeInsets.symmetric(
                horizontal: 12,
                vertical: 6,
              ), // Adjusted padding for 36px toolbar
              minimumSize: const Size(0, 32), // Increased button height
            ),
          ),
          const SizedBox(width: 8), // Reduced spacing
          // Re-split Source Button (supports both file mode and text mode)
          OutlinedButton.icon(
            onPressed: !_isReeditMode &&
                    !isOperationInProgress &&
                    (state.taskId != null ||
                        (_isTextMode &&
                            _textController.text.trim().isNotEmpty))
                ? () => _onResplitSource(state, notifier)
                : null,
            icon: state.currentOperation == TranslationOperation.extracting
                ? const SizedBox(
                    width: 14, // Reduced from 16
                    height: 14, // Reduced from 16
                    child: CircularProgressIndicator(strokeWidth: 2),
                  )
                : const Icon(Icons.segment, size: 16),
            label: Text(
              state.currentOperation == TranslationOperation.extracting
                  ? l10n.translationToolbarReextracting
                  : l10n.translationToolbarReextract,
              style: const TextStyle(fontSize: 13), // Reduced font size
            ),
            style: OutlinedButton.styleFrom(
              padding: const EdgeInsets.symmetric(
                horizontal: 12,
                vertical: 6,
              ), // Adjusted padding for 36px toolbar
              minimumSize: const Size(0, 32), // Increased button height
            ),
          ),
          // Display token usage: only actual consumed tokens after translation completed
          Builder(
            builder: (BuildContext context) {
              if (state.taskId == null) {
                return const SizedBox.shrink();
              }
              final String taskId = state.taskId as String;

              final tokenUsage = state.tokenUsage;
              if (tokenUsage != null && tokenUsage['total_tokens'] != null) {
                final int actualTokens =
                    tokenUsage['total_tokens'] as int? ?? 0;
                if (actualTokens > 0) {
                  final String formatted = _formatTokenCount(actualTokens);
                  return Padding(
                    padding: const EdgeInsets.symmetric(horizontal: 8),
                    child: Text(
                      l10n.translationToolbarTokensCount(formatted),
                      style: Theme.of(context).textTheme.bodySmall?.copyWith(
                            color:
                                Theme.of(context).colorScheme.onSurfaceVariant,
                          ),
                    ),
                  );
                }
              }

              // No fallback: hide when translation not completed or no usage returned
              return const SizedBox.shrink();
            },
          ),
          const SizedBox(width: 12),
          // Glossary Button - Opens/switches to Glossary tab
          // Disabled if no file imported and no text input, or if Extract is not completed
          Builder(
            builder: (BuildContext context) {
              final bool hasFile = state.pickedFile != null;
              final bool hasText =
                  _isTextMode && _textController.text.trim().isNotEmpty;
              final bool canUseGlossary = hasFile || hasText;
              // Only enable if Extract is completed (or no Extract tab exists yet)
              final bool isEnabled = !isOperationInProgress &&
                  canUseGlossary &&
                  (!hasExtractTab || isExtractCompleted);
              return Tooltip(
                message: isEnabled
                    ? l10n.translationToolbarOpenGlossaryTab
                    : (!canUseGlossary
                        ? l10n.translationSnackPleaseSelectFileOrText
                        : (hasExtractTab && !isExtractCompleted
                            ? l10n.translationToolbarHintWaitExtract
                            : l10n.translationToolbarHintOperationInProgress)),
                child: OutlinedButton.icon(
                  onPressed: isEnabled
                      ? () => _openGlossaryTab(state, notifier)
                      : null,
                  icon: const Icon(Icons.library_books),
                  label: Text(l10n.translationToolbarGlossary),
                  style: OutlinedButton.styleFrom(
                    padding: const EdgeInsets.symmetric(
                      horizontal: 12, // Reduced from 16
                      vertical: 6, // Adjusted padding for 36px toolbar
                    ),
                    minimumSize: const Size(0, 32), // Increased button height
                  ),
                ),
              );
            },
          ),
          const SizedBox(width: 8), // Reduced spacing
          // Convert: runs format conversion, Exclude All, then Translate All into the Convert tab
          Builder(
            builder: (BuildContext context) {
              final bool hasFileOrText = state.pickedFile != null ||
                  (_isTextMode && _textController.text.trim().isNotEmpty);
              final String exclusionKey =
                  widget.flowId ?? (state.taskId ?? 'translation');
              final int exclusionInFlight = ref.watch(
                  exclusionUpdateInFlightProviderFamily(exclusionKey),);
              final bool isConvertEnabled = !_isReeditMode &&
                  hasFileOrText &&
                  !isOperationInProgress &&
                  !_isGlossaryEditing &&
                  !_isUpdatingExcluded &&
                  exclusionInFlight == 0;
              final String convertTooltip = !hasFileOrText
                  ? l10n.translationSnackPleaseSelectFileOrText
                  : (!isConvertEnabled
                      ? l10n.translationToolbarHintOperationInProgress
                      : l10n.translationToolbarConvertHint);
              return Tooltip(
                message: convertTooltip,
                child: OutlinedButton.icon(
                  onPressed: isConvertEnabled
                      ? () async {
                          await _runConvertToolbarAutomation();
                        }
                      : null,
                  icon: const Icon(Icons.transform),
                  label: Text(l10n.translationToolbarConvert),
                  style: OutlinedButton.styleFrom(
                    padding: const EdgeInsets.symmetric(
                      horizontal: 12,
                      vertical: 6,
                    ),
                    minimumSize: const Size(0, 32),
                  ),
                ),
              );
            },
          ),
          const SizedBox(width: 8), // Reduced spacing
          // Translate Button
          // Change color to light when translation is completed
          // Disabled if glossary is in editing state or Extract is not completed
          Builder(
            builder: (BuildContext context) {
              final String exclusionKey =
                  widget.flowId ?? (state.taskId ?? 'translation');
              final int exclusionInFlight =
                  ref.watch(exclusionUpdateInFlightProviderFamily(exclusionKey));
              final bool hasFileOrText = state.pickedFile != null ||
                  (_isTextMode && _textController.text.trim().isNotEmpty);
              // Only enable if Extract is completed (or no Extract tab exists yet)
              final bool isTranslateEnabled = !_isReeditMode &&
                  hasFileOrText &&
                  !isOperationInProgress &&
                  !_isGlossaryEditing &&
                  !_isUpdatingExcluded &&
                  exclusionInFlight == 0 &&
                  (!hasExtractTab || isExtractCompleted);
              final String tooltipMessage = _isGlossaryEditing
                  ? l10n.translationToolbarHintSaveGlossaryFirst
                  : (_isUpdatingExcluded
                      ? l10n.translationToolbarHintUpdatingExcluded
                      : (exclusionInFlight > 0
                          ? l10n.translationToolbarHintUpdatingExcluded
                      : (!hasFileOrText
                          ? l10n.translationSnackPleaseSelectFileOrText
                          : (hasExtractTab && !isExtractCompleted
                              ? l10n.translationToolbarHintWaitExtract
                              : (isOperationInProgress
                                  ? l10n.translationToolbarHintOperationInProgress
                                  : l10n.translationToolbarStartTranslation)))));
              return Tooltip(
                message: tooltipMessage,
                child: ElevatedButton.icon(
                  onPressed: isTranslateEnabled
                      ? () async {
                          await _startTranslation(state, notifier);
                        }
                      : null,
                  icon:
                      state.currentOperation == TranslationOperation.translating
                          ? const SizedBox(
                              width: 16,
                              height: 16,
                              child: CircularProgressIndicator(
                                strokeWidth: 2,
                                valueColor:
                                    AlwaysStoppedAnimation<Color>(Colors.white),
                              ),
                            )
                          : const Icon(Icons.translate),
                  label: Text(
                    state.currentOperation == TranslationOperation.translating
                        ? l10n.translationToolbarTranslating
                        : l10n.translationToolbarTranslateAll,
                  ),
                  style: ElevatedButton.styleFrom(
                    backgroundColor: isTranslationCompleted
                        ? Colors.blue.shade300 // Light blue when completed
                        : Colors.blue.shade700, // Dark blue when not completed
                    foregroundColor: isTranslationCompleted
                        ? Colors.blue.shade900 // Dark text on light background
                        : Colors.white, // White text on dark background
                    padding: const EdgeInsets.symmetric(
                      horizontal: 12, // Reduced from 16
                      vertical: 6, // Adjusted padding for 36px toolbar
                    ),
                    minimumSize: const Size(0, 32), // Increased button height
                    shape: RoundedRectangleBorder(
                      borderRadius: BorderRadius.circular(8),
                    ),
                  ),
                ),
              );
            },
          ),
          const SizedBox(width: 8), // Reduced spacing
          // Retry Button (always visible after translation is done; stay visible after retry completes)
          // When no segments need retry, directly mark the task as completed. Disabled only while retry is in progress.
          if (state.taskId != null && isTaskDone)
            Tooltip(
              message: isOperationInProgress
                  ? l10n.translationToolbarRetryInProgress
                  : l10n.translationToolbarRetryTooltip,
              waitDuration: const Duration(milliseconds: 500),
              child: ElevatedButton.icon(
                onPressed: isOperationInProgress
                    ? null
                    : () => _retranslateFailedSegments(state, notifier),
                icon: state.currentOperation == TranslationOperation.retranslating
                    ? const SizedBox(
                        width: 16,
                        height: 16,
                        child: CircularProgressIndicator(
                          strokeWidth: 2,
                          valueColor:
                              AlwaysStoppedAnimation<Color>(Colors.white),
                        ),
                      )
                    : const Icon(Icons.refresh, size: 16),
                label: Text(
                  l10n.translationToolbarRetry,
                  style: const TextStyle(fontSize: 13),
                ), // Reduced font size
                style: ElevatedButton.styleFrom(
                  backgroundColor:
                      Colors.blue.shade700, // Dark blue when completed
                  foregroundColor: Colors.white,
                  padding: const EdgeInsets.symmetric(
                    horizontal: 12, // Reduced from 16
                    vertical: 6, // Adjusted padding for 36px toolbar
                  ),
                  minimumSize: const Size(0, 32), // Increased button height
                  shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(8),
                  ),
                ),
              ),
            ),
          if (state.taskId != null &&
              isTaskDone &&
              _supportsRevisionPreviewTask(state)) ...<Widget>[
            const SizedBox(width: 8),
            Tooltip(
              message: l10n.translationPreviewPdfRevision,
              waitDuration: const Duration(milliseconds: 500),
              child: ElevatedButton.icon(
                onPressed: isOperationInProgress
                    ? null
                    : () => _openPdfRevisionMode(state),
                icon: const Icon(Icons.edit_note, size: 16),
                label: Text(
                  l10n.translationPreviewPdfRevision,
                  style: const TextStyle(fontSize: 13),
                ),
                style: ElevatedButton.styleFrom(
                  backgroundColor: Colors.blue.shade700,
                  foregroundColor: Colors.white,
                  padding: const EdgeInsets.symmetric(
                    horizontal: 12,
                    vertical: 6,
                  ),
                  minimumSize: const Size(0, 32),
                  shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(8),
                  ),
                ),
              ),
            ),
          ],
          if (state.taskId != null && isTaskDone)
            Padding(
              padding: const EdgeInsets.only(right: 8),
              child: Builder(
                builder: (_) {
                  final bool queueDirty = ref.watch(
                    queuePersistDirtyProvider(_queuePersistScopeKey),
                  );
                  final String persistTooltip = queueDirty
                      ? l10n.translationPersistQueueTooltip
                      : l10n.translationPersistQueueAlreadySyncedTooltip;
                  return Tooltip(
                    message: persistTooltip,
                    child: IconButton(
                      onPressed: _queuePersistInFlight
                          ? null
                          : queueDirty
                              ? _persistQueueSnapshotManual
                              : null,
                      icon: _queuePersistInFlight
                          ? const SizedBox(
                              width: 16,
                              height: 16,
                              child: CircularProgressIndicator(strokeWidth: 2),
                            )
                          : const Icon(Icons.save_alt, size: 16),
                      padding: const EdgeInsets.all(4),
                      constraints: const BoxConstraints(
                        minWidth: 28,
                        minHeight: 28,
                      ),
                    ),
                  );
                },
              ),
            ),
          const SizedBox(width: 16),
          // File name display (adaptive width inside horizontal scroll)
          if (hasImportedFile)
            Flexible(
              child: Row(
                mainAxisSize: MainAxisSize.min,
                children: <Widget>[
                  Icon(
                    Icons.description,
                    size: 16,
                    color: Theme.of(context).colorScheme.onSurfaceVariant,
                  ),
                  const SizedBox(width: 6),
                  Flexible(
                    child: Text(
                      state.pickedFile?.name ?? 'No file selected',
                      style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                            color:
                                Theme.of(context).colorScheme.onSurfaceVariant,
                            fontWeight: FontWeight.w500,
                          ),
                      overflow: TextOverflow.ellipsis,
                      maxLines: 1,
                      softWrap: false,
                    ),
                  ),
                ],
              ),
            ),
          if (shouldShowModeToggle) ...<Widget>[
            if (hasImportedFile) const SizedBox(width: 8), // Reduced spacing
            OutlinedButton.icon(
              onPressed: _handleModeToggle,
              icon: Icon(
                _isTextMode ? Icons.upload_file : Icons.text_fields,
                size: 16,
              ), // Reduced icon size
              label: Text(
                _isTextMode
                    ? l10n.translationToolbarSwitchToFile
                    : l10n.translationToolbarSwitchToText,
                style: const TextStyle(fontSize: 13), // Reduced font size
              ),
              style: OutlinedButton.styleFrom(
                padding: const EdgeInsets.symmetric(
                  horizontal: 12,
                  vertical: 6,
                ), // Adjusted padding for 36px toolbar
                minimumSize: const Size(0, 32), // Increased button height
              ),
            ),
          ],
          // Fetch URL Button - only in file mode before file is uploaded, not in reedit mode
          if (!_isReeditMode && !_isTextMode && !hasImportedFile) ...<Widget>[
            const SizedBox(width: 8), // Reduced spacing
            OutlinedButton.icon(
              onPressed: isOperationInProgress
                  ? null
                  : () {
                      setState(() {
                        _showUrlInput = !_showUrlInput;
                      });
                    },
              icon: Icon(
                _showUrlInput ? Icons.close : Icons.link,
                size: 16,
              ),
              label: Text(
                _showUrlInput ? AppLocalizations.of(context)!.fetchUrlClose : AppLocalizations.of(context)!.fetchUrl,
                style: const TextStyle(fontSize: 13),
              ),
              style: OutlinedButton.styleFrom(
                padding: const EdgeInsets.symmetric(
                  horizontal: 12,
                  vertical: 6,
                ),
                minimumSize: const Size(0, 32),
              ),
            ),
          ],
          // Show filename on the right side in reedit mode
          if (_isReeditMode && widget.reeditFileName != null)
            Flexible(
              child: Padding(
                padding: const EdgeInsets.only(left: 12, right: 4),
                child: Text(
                  widget.reeditFileName!,
                  style: Theme.of(context).textTheme.bodySmall?.copyWith(
                    color: Theme.of(context).colorScheme.onSurfaceVariant,
                    fontWeight: FontWeight.w500,
                  ),
                  overflow: TextOverflow.ellipsis,
                  maxLines: 1,
                ),
              ),
            ),
        ],
        ),
      ),
    );
  }

  Widget _buildUrlInputPanel(translationNotifier) {
    final dynamic translationState = widget.flowId != null
        ? ref.read(translationStateProviderFamily(widget.flowId!))
        : ref.read(translationStateProvider);
    final bool isOperationInProgress =
        translationState.currentOperation != TranslationOperation.none;
    final bool isDisabled = isOperationInProgress;

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
      decoration: BoxDecoration(
        color: Theme.of(context).colorScheme.surfaceContainerHighest,
        border: Border(
          bottom: BorderSide(
            color: Theme.of(context).dividerColor,
          ),
        ),
      ),
      child: Row(
        children: <Widget>[
          Expanded(
            child: TextField(
              controller: _urlController,
              decoration: InputDecoration(
                hintText: 'https://example.com/article',
                prefixIcon: const Icon(Icons.link),
                border: const OutlineInputBorder(),
                contentPadding:
                    const EdgeInsets.symmetric(horizontal: 12, vertical: 14),
                filled: true,
                fillColor: Theme.of(context).colorScheme.surface,
              ),
              keyboardType: TextInputType.url,
              enabled: !_isFetchingUrl && !isDisabled,
              onChanged: (_) => setState(() {}),
              onSubmitted: (_) {
                if (!_isFetchingUrl &&
                    !isDisabled &&
                    _urlController.text.trim().isNotEmpty) {
                  _startFetchUrl(translationNotifier);
                }
              },
            ),
          ),
          const SizedBox(width: 8),
          DropdownButtonHideUnderline(
            child: DropdownButton<String>(
              value: _urlExtractMode,
              items: const <DropdownMenuItem<String>>[
                DropdownMenuItem<String>(
                    value: 'content', child: Text('Content'),),
                DropdownMenuItem<String>(
                    value: 'full', child: Text('Full HTML'),),
              ],
              onChanged: (_isFetchingUrl || isDisabled)
                  ? null
                  : (String? v) {
                      if (v != null) {
                        setState(() {
                          _urlExtractMode = v;
                        });
                      }
                    },
            ),
          ),
          const SizedBox(width: 8),
          ElevatedButton.icon(
            onPressed: isDisabled || _urlController.text.trim().isEmpty
                ? null
                : _isFetchingUrl
                    ? () => _cancelFetchUrl()
                    : () => _startFetchUrl(translationNotifier),
            icon: _isFetchingUrl
                ? const SizedBox(
                    width: 16,
                    height: 16,
                    child: CircularProgressIndicator(strokeWidth: 2),
                  )
                : const Icon(Icons.download),
            label: Text(_isFetchingUrl
                ? AppLocalizations.of(context)!.fetchUrlCancel
                : AppLocalizations.of(context)!.fetchUrl),
          ),
        ],
      ),
    );
  }

  Future<void> _convertTextToFile(notifier) async {
    // Convert text input to a virtual file (PlatformFile)
    final String text = _textController.text.trim();
    if (text.isEmpty) {
      if (mounted) {
        final l10n = AppLocalizations.of(context)!;
        _showSnackBar(l10n.translationSnackTextEmpty, Colors.red);
      }
      return;
    }

    try {
      // Create a virtual file from text
      // Use markdown_based workflow for text input (supports Markdown)
      final Uint8List bytes = Uint8List.fromList(utf8.encode(text));

      // Create a PlatformFile-like object
      // Note: PlatformFile is from file_picker package, we need to create a compatible object
      final PlatformFile virtualFile = PlatformFile(
        name: 'text_input.md',
        size: bytes.length,
        bytes: bytes,
      );

      // Set the virtual file as picked file
      notifier.setPickedFile(virtualFile);

      // Auto-init preview by running format-conversion
      try {
        // Get target language from Quick Settings for exclusion detection
        final TranslationQuickSettings qs = widget.flowId != null
            ? ref.read(translationQuickSettingsProviderFamily(widget.flowId!))
            : ref.read(translationQuickSettingsProvider);
        final String? toLang = qs.toLang.isNotEmpty ? qs.toLang : null;
        final sourceLang =
            qs.sourceLang.isNotEmpty ? qs.sourceLang : 'auto';

        final GlobalSettings globalSettings = ref.read(globalSettingsProvider);
        final FormatConversionService formatSvc = FormatConversionService();
        final FormatConvertParserOptions parserOpts =
            await formatSvc.resolveParserOptions(
          parsingEngine: globalSettings.parsingEngine,
          formulaOcr: qs.formulaOcr ?? globalSettings.formulaOcr,
          tableOcr: qs.tableOcr ?? globalSettings.tableOcr,
        );

        final Map<String, dynamic> convertRes = await formatSvc.convertFormat(
          fileBytes: bytes,
          fileName: 'text_input.md',
          convertEngine: parserOpts.convertEngine,
          formulaOcr: parserOpts.formulaOcr,
          tableOcr: parserOpts.tableOcr,
          modelVersion: parserOpts.modelVersion,
          mineruToken: parserOpts.mineruToken,
          skipCache: true, // Always skip cache for new sessions/page refresh
          toLang:
              toLang, // CRITICAL: Pass target language for exclusion detection
          sourceLang:
              sourceLang, // OCR language hint for MinerU (markdown_based)
        );
        if (convertRes['success'] == true) {
          final Map<String, dynamic> data =
              (convertRes['data'] as Map).cast<String, dynamic>();
          final String? taskId = data['task_id']?.toString();
          if (taskId != null && taskId.isNotEmpty) {
            notifier.setTaskId(taskId);
            // Open a preview tab immediately to show Extract view
            _addExtractTab(taskId);
            if (mounted) {
              _showSnackBar('Text converted to file format', Colors.green);
            }
          }
        } else {
          final bool handled =
              await _handleMineruAuthError(convertRes['error']?.toString());
          if (mounted && !handled) {
            _showSnackBar(convertRes['error']?.toString() ?? 'Request failed',
                Colors.red,);
          }
        }
      } catch (e) {
        _translationScreenLog('Failed to convert text format: $e');
        final bool handled = await _handleMineruAuthError(e.toString());
        if (mounted && !handled) {
          _showSnackBar('Failed to convert text format: $e', Colors.red);
        }
      }
    } catch (e) {
      if (mounted) {
        _showSnackBar('Failed to convert text: $e', Colors.red);
      }
    }
  }

  Future<void> _handleModeToggle() async {
    // Check if there's existing content that would be lost
    final dynamic translationState = widget.flowId != null
        ? ref.read(translationStateProviderFamily(widget.flowId!))
        : ref.read(translationStateProvider);
    final bool hasFile = translationState.pickedFile != null;
    final bool hasText = _textController.text.trim().isNotEmpty;

    if (_isTextMode && hasText) {
      // Switching from text to file, check if text has content
      final bool? confirmed = await showDialog<bool>(
        context: context,
        builder: (BuildContext context) => AlertDialog(
          title: Text(
            AppLocalizations.of(context)!.translationDialogSwitchToFileTitle,
          ),
          content: Text(
            AppLocalizations.of(context)!.translationDialogSwitchToFileBody,
          ),
          actions: <Widget>[
            TextButton(
              onPressed: () => Navigator.of(context).pop(false),
              child: Text(
                AppLocalizations.of(context)!.translationDialogCancelButton,
              ),
            ),
            TextButton(
              onPressed: () => Navigator.of(context).pop(true),
              child: Text(
                AppLocalizations.of(context)!.translationDialogContinueButton,
              ),
            ),
          ],
        ),
      );
      if (confirmed != true) return;

      // Clear text input
      _textController.clear();
      if (widget.flowId != null) {
        ref
            .read(textVersionStackProvider(widget.flowId!).notifier)
            .initialize('');
      }
    } else if (!_isTextMode && hasFile) {
      // Switching from file to text, check if file is selected
      final bool? confirmed = await showDialog<bool>(
        context: context,
        builder: (BuildContext context) => AlertDialog(
          title: Text(
            AppLocalizations.of(context)!.translationDialogSwitchToTextTitle,
          ),
          content: Text(
            AppLocalizations.of(context)!.translationDialogSwitchToTextBody,
          ),
          actions: <Widget>[
            TextButton(
              onPressed: () => Navigator.of(context).pop(false),
              child: Text(
                AppLocalizations.of(context)!.translationDialogCancelButton,
              ),
            ),
            TextButton(
              onPressed: () => Navigator.of(context).pop(true),
              child: Text(
                AppLocalizations.of(context)!.translationDialogContinueButton,
              ),
            ),
          ],
        ),
      );
      if (confirmed != true) return;

      // Clear file selection
      final dynamic translationNotifier = widget.flowId != null
          ? ref.read(translationStateProviderFamily(widget.flowId!).notifier)
          : ref.read(translationStateProvider.notifier);
      translationNotifier.resetTranslation();
    }

    setState(() {
      _isTextMode = !_isTextMode;
    });
  }

  Future<void> _onResplitSource(state, notifier) async {
    // Prevent re-entry
    if (state.currentOperation != TranslationOperation.none) {
      return;
    }

    try {
      notifier.setCurrentOperation(TranslationOperation.extracting);

      // If there is no task yet but we are in text mode with input,
      // first convert text input to a virtual file and run initial Extract.
      if (state.taskId == null &&
          _isTextMode &&
          _textController.text.trim().isNotEmpty &&
          state.pickedFile == null) {
        await _convertTextToFile(notifier);

        final dynamic updatedState = widget.flowId != null
            ? ref.read(translationStateProviderFamily(widget.flowId!))
            : ref.read(translationStateProvider);
        if (updatedState.taskId == null) {
          if (mounted) {
            _showSnackBar(
              'Failed to start extract from text input.',
              Colors.red,
            );
          }
          return;
        }

        if (mounted) {
          _showSnackBar(
            'Text extracted successfully.',
            Colors.green,
          );
        }
        return;
      }

      final TranslationService svc = TranslationService();
      if (state.taskId == null) {
        if (mounted) {
          _showSnackBar(
            'No task yet. Please start format conversion or translation first.',
            Colors.orange,
          );
        }
        return;
      }

      // CRITICAL: Get excluded segment indices from Flow-level state
      // This ensures Re-extract uses the same excluded segments (e.g., references)
      final excludedIndices = state.excludedSegmentIndices.isNotEmpty
          ? state.excludedSegmentIndices.toList()
          : null;

      // Current source language (MinerU OCR hint) from Quick Settings.
      final qs = widget.flowId != null
          ? ref.read(
              translationQuickSettingsProviderFamily(widget.flowId!),
            )
          : ref.read(translationQuickSettingsProvider);
      final sourceLang =
          qs.sourceLang.isNotEmpty ? qs.sourceLang : 'auto';

      await svc.resplitSource(
        state.taskId!,
        excludedSegmentIndices: excludedIndices,
        sourceLang: sourceLang,
      );

      // Trigger ExtractPreview refresh by incrementing refresh provider
      // This ensures ExtractPreview detects resplit completion and refreshes chunks
      triggerExtractRefresh(ref);

      if (mounted) {
        setState(() {});
      }

      // Optionally refresh preview tab if open
      if (mounted) {
        _showSnackBar('Source re-split completed', Colors.green);
      }
    } catch (e) {
      if (mounted) {
        String message = 'Failed to re-split: $e';
        // If backend returned a specific error message (HTTP 4xx/5xx),
        // prefer showing that instead of the generic DioException text.
        if (e is DioException) {
          final data = e.response?.data;
          if (data is Map && data['detail'] is String) {
            message = data['detail'] as String;
          }
        }
        _showSnackBar(message, Colors.red);
      }
    } finally {
      notifier.setCurrentOperation(TranslationOperation.none);
    }
  }

  /// Check language similarity before glossary generation (reusable function)
  /// Returns true if user confirmed to continue, false if cancelled
  Future<bool> _checkLanguageSimilarityForGlossary(
    state,
    bool hasFile,
  ) async {
    // Check if detected language matches target language (only for file mode)
    if (hasFile && state.taskId != null && state.taskId!.isNotEmpty) {
      try {
        final TranslationService svc = TranslationService();
        final Map<String, dynamic> statusResp =
            await svc.getStatus(state.taskId!);
        final String? detectedLang = statusResp['detected_language'] as String?;

        if (detectedLang != null && detectedLang.isNotEmpty) {
          final TranslationQuickSettings qs = widget.flowId != null
              ? ref.read(translationQuickSettingsProviderFamily(widget.flowId!))
              : ref.read(translationQuickSettingsProvider);
          final String targetLang = qs.toLang.toLowerCase();

          // Normalize language codes for comparison
          final String normalizedDetected =
              _normalizeLanguageCode(detectedLang);
          final String normalizedTarget = _normalizeLanguageCode(targetLang);

          if (normalizedDetected == normalizedTarget) {
            // Same as translation start: document language matches target -> may be wrong target, ask to continue
            final String detectedLangName =
                _convertLangCodeToName(detectedLang);
            final String targetLangName = _convertLangCodeToName(targetLang);
            final l10n = AppLocalizations.of(context)!;
            final bool? confirmed = await DialogHelper.showDialog<bool>(
              context: context,
              builder: (BuildContext context) => AlertDialog(
                title: Text(l10n.languageMatchWarningTitle),
                content: Text(
                  l10n.languageMatchWarningGlossaryBody(
                    detectedLangName,
                    targetLangName,
                  ),
                ),
                actions: <Widget>[
                  TextButton(
                    onPressed: () => Navigator.of(context).pop(false),
                    child: Text(l10n.translationDialogCancelButton),
                  ),
                  TextButton(
                    onPressed: () => Navigator.of(context).pop(true),
                    style: TextButton.styleFrom(
                      foregroundColor: Theme.of(context).colorScheme.error,
                    ),
                    child: Text(l10n.translationDialogContinueButton),
                  ),
                ],
              ),
            );

            if (confirmed != true) {
              return false; // User cancelled
            }
          }
        }
      } catch (e) {
        // If language detection check fails, continue with glossary generation
        _translationScreenLog('Failed to check detected language: $e');
      }
    }
    return true; // Continue
  }

  Future<void> _onGenerateGlossary(state, notifier) async {
    // Prevent re-entry (but allow if operation is generatingGlossary, as it might be stale)
    if (state.currentOperation != TranslationOperation.none &&
        state.currentOperation != TranslationOperation.generatingGlossary) {
      debugPrint(
        '[TRANSLATION_SCREEN] _onGenerateGlossary: Operation in progress: ${state.currentOperation}, skipping',
      );
      return;
    }

    // Reset operation state if it was stuck in generatingGlossary
    if (state.currentOperation == TranslationOperation.generatingGlossary) {
      debugPrint(
        '[TRANSLATION_SCREEN] _onGenerateGlossary: Resetting stale generatingGlossary state',
      );
      notifier.setCurrentOperation(TranslationOperation.none);
      notifier.setTranslating(false);
    }

    // Check if we have file or text input
    final bool hasFile = state.pickedFile != null;
    final bool hasText = _isTextMode && _textController.text.trim().isNotEmpty;
    debugPrint(
      '[TRANSLATION_SCREEN] _onGenerateGlossary: hasFile=$hasFile, hasText=$hasText',
    );

    if (!hasFile && !hasText) {
      debugPrint(
        '[TRANSLATION_SCREEN] _onGenerateGlossary: No file or text input, showing error',
      );
      if (mounted) {
        _showSnackBar('Please select a file or enter text first', Colors.red);
      }
      return;
    }

    // Check language similarity before glossary generation
    debugPrint(
      '[TRANSLATION_SCREEN] _onGenerateGlossary: Checking language similarity...',
    );
    final bool shouldContinue =
        await _checkLanguageSimilarityForGlossary(state, hasFile);
    if (!shouldContinue) {
      debugPrint(
        '[TRANSLATION_SCREEN] _onGenerateGlossary: Language similarity check failed or cancelled',
      );
      return; // User cancelled
    }
    debugPrint(
      '[TRANSLATION_SCREEN] _onGenerateGlossary: Language similarity check passed, proceeding to dialog',
    );

    // Check if current glossary has entries
    final PreviewTabsState tabsState = widget.flowId != null
        ? ref.read(previewTabsProviderFamily(widget.flowId!))
        : ref.read(previewTabsProvider);
    final int glossaryTabIndex = tabsState.tabs
        .indexWhere((PreviewTab t) => t.type.toString().endsWith('glossary'));
    final bool hasExistingGlossary = glossaryTabIndex >= 0 &&
        tabsState.tabs[glossaryTabIndex].id == 'glossary_tab' &&
        tabsState.tabs[glossaryTabIndex].dataRef != null &&
        tabsState.tabs[glossaryTabIndex].dataRef!['glossaryData'] != null;
    final Map<String, dynamic>? existingGlossaryData = hasExistingGlossary
        ? (tabsState.tabs[glossaryTabIndex].dataRef!['glossaryData']
            as Map<String, dynamic>?)
        : null;
    final bool hasEntries =
        existingGlossaryData != null && existingGlossaryData.isNotEmpty;
    debugPrint(
      '[TRANSLATION_SCREEN] _onGenerateGlossary: hasExistingGlossary=$hasExistingGlossary, hasEntries=$hasEntries, entriesCount=${existingGlossaryData?.length ?? 0}',
    );

    // Show detection mode selection dialog with replace/merge option if glossary has entries
    debugPrint(
      '[TRANSLATION_SCREEN] _onGenerateGlossary: Showing detection mode dialog...',
    );
    final Map<String, dynamic>? dialogResult =
        await showDialog<Map<String, dynamic>>(
      context: context,
      builder: (BuildContext dialogContext) => _GlossaryDetectionDialog(
        hasEntries: hasEntries,
        entriesCount: existingGlossaryData?.length ?? 0,
      ),
    );

    // User cancelled the dialog
    if (dialogResult == null) {
      return;
    }

    final String selectedMode = dialogResult['mode'] as String;
    final String actionMode = dialogResult['action'] as String? ?? 'replace';

    // If in text mode, convert text to file first
    Uint8List fileBytes;
    String fileName;
    if (_isTextMode && hasText && !hasFile) {
      fileBytes = Uint8List.fromList(utf8.encode(_textController.text.trim()));
      fileName = 'text_input.md';
    } else {
      if (state.pickedFile == null) {
        if (mounted) {
          _showSnackBar('Please select a file first', Colors.red);
        }
        return;
      }
      fileBytes = state.pickedFile!.bytes ??
          (await File(state.pickedFile!.path!).readAsBytes());
      fileName = state.pickedFile!.name;
    }

    notifier.setCurrentOperation(TranslationOperation.generatingGlossary);
    notifier.setTranslating(true);
    notifier.setStatusText('Generating glossary...');
    notifier.setProgress(0);

    try {
      final TranslationQuickSettings qs = widget.flowId != null
          ? ref.read(translationQuickSettingsProviderFamily(widget.flowId!))
          : ref.read(translationQuickSettingsProvider);
      final GlobalSettings globalSettings = ref.read(globalSettingsProvider);

      // Convert language code to language name for backend
      final String languageName = _convertLangCodeToName(qs.toLang);

      final GlossaryGenerationService glossaryService =
          GlossaryGenerationService();
      // Use taskId from Extract phase if available (to reuse chunks)
      final String? extractTaskId =
          state.taskId != null && (state.taskId as String).isNotEmpty
              ? state.taskId as String
              : null;

      // Simulate progress updates during glossary generation (since it's synchronous)
      // Update progress every second by 1%, until 99%
      var simulatedProgress = 0;
      _glossaryProgressTimer =
          Timer.periodic(const Duration(seconds: 1), (Timer timer) {
        if (simulatedProgress < 99) {
          simulatedProgress += 1;
          notifier.setProgress(simulatedProgress);
          notifier
              .setStatusText('Generating glossary... ($simulatedProgress%)');
        } else {
          // Stop at 99%, wait for completion
          timer.cancel();
        }
      });

      final Map<String, dynamic> result =
          await glossaryService.generateGlossary(
        fileBytes: fileBytes,
        fileName: fileName,
        targetLanguage: languageName,
        customPrompt: globalSettings.customPrompt,
        taskId: extractTaskId,
        detectionMode: selectedMode, // Pass selected detection mode
      );

      // Cancel progress timer (if still running)
      _glossaryProgressTimer?.cancel();
      _glossaryProgressTimer = null;
      // Set to 100% when completed
      notifier.setProgress(100);
      notifier.setStatusText('Glossary generation completed');

      if (result['success'] == true) {
        final data = result['data'];
        debugPrint(
          '[TRANSLATION_SCREEN] Glossary generation result: success=true, data keys: ${data.keys.toList()}',
        );
        debugPrint('[TRANSLATION_SCREEN] Data type: ${data.runtimeType}');
        if (data['download_url'] != null) {
          // Download the generated glossary
          await _openDownload(data['download_url']);
          if (mounted) {
            _showSnackBar('Glossary generated successfully!', Colors.green);
          }
        } else if (data['glossary'] != null) {
          final glossary = data['glossary'];
          debugPrint(
            '[TRANSLATION_SCREEN] Glossary type: ${glossary.runtimeType}',
          );
          debugPrint(
            '[TRANSLATION_SCREEN] Glossary is Map: ${glossary is Map}',
          );
          if (glossary is Map) {
            debugPrint(
              '[TRANSLATION_SCREEN] Glossary keys count: ${glossary.keys.length}',
            );
            debugPrint(
              '[TRANSLATION_SCREEN] Glossary keys (first 5): ${glossary.keys.take(5).toList()}',
            );
          }
          debugPrint(
            '[TRANSLATION_SCREEN] Adding glossary tab with ${glossary is Map ? glossary.length : 0} terms',
          );
          // Convert glossary to regular Map if needed
          final Map<String, dynamic> newGlossaryMap = glossary is Map
              ? Map<String, dynamic>.from(glossary)
              : <String, dynamic>{};
          debugPrint(
            '[TRANSLATION_SCREEN] Converted glossaryMap length: ${newGlossaryMap.length}',
          );

          // Handle replace or merge based on user selection
          if (actionMode == 'merge' && hasEntries) {
            // Merge mode: combine existing and new glossary
            final Map<String, dynamic> mergedGlossary =
                Map<String, dynamic>.from(existingGlossaryData);
            mergedGlossary
                .addAll(newGlossaryMap); // New entries override existing ones
            debugPrint(
              '[TRANSLATION_SCREEN] Merging glossaries: existing=${existingGlossaryData.length}, new=${newGlossaryMap.length}, merged=${mergedGlossary.length}',
            );
            _addGlossaryTab(mergedGlossary);
            if (mounted) {
              _showSnackBar(
                'Glossary merged successfully! (${newGlossaryMap.length} new terms added)',
                Colors.green,
              );
            }
          } else {
            // Replace mode: use new glossary directly
            debugPrint(
              '[TRANSLATION_SCREEN] Replacing glossary with ${newGlossaryMap.length} terms',
            );
            _addGlossaryTab(newGlossaryMap);
            if (mounted) {
              _showSnackBar(
                'Glossary generated and applied successfully!',
                Colors.green,
              );
            }
          }

          // Switch to the glossary tab after adding it (use postFrameCallback to ensure state is updated)
          WidgetsBinding.instance.addPostFrameCallback((_) {
            _switchToGlossaryTab();
          });
        } else {
          debugPrint(
            '[TRANSLATION_SCREEN] WARNING: Glossary generated but no glossary data in response',
          );
          debugPrint(
            '[TRANSLATION_SCREEN] Available data keys: ${data.keys.toList()}',
          );
          if (mounted) {
            _showSnackBar(
              'Glossary generated but no data received',
              Colors.orange,
            );
          }
        }
      } else {
        debugPrint(
          '[TRANSLATION_SCREEN] Glossary generation failed: ${result['error']}',
        );
        if (mounted) {
          _showSnackBar(
            'Failed to generate glossary: ${result['error']}',
            Colors.red,
          );
        }
      }
    } catch (e) {
      if (mounted) {
        _showSnackBar('Error generating glossary: $e', Colors.red);
      }
    } finally {
      // Cancel progress timer if still running
      _glossaryProgressTimer?.cancel();
      _glossaryProgressTimer = null;
      // Reset operation state
      notifier.setCurrentOperation(TranslationOperation.none);
      notifier.setTranslating(false);
      notifier.setStatusText('');
    }
  }

  /// Cancel glossary generation
  Future<void> _cancelGlossaryGeneration(notifier) async {
    // Show confirmation dialog
    final bool? confirmed = await showDialog<bool>(
      context: context,
      builder: (BuildContext context) => AlertDialog(
        title: const Text('Cancel Glossary Generation'),
        content: const Text(
          'Are you sure you want to cancel the glossary generation?',
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

    // Cancel progress timer
    _glossaryProgressTimer?.cancel();
    _glossaryProgressTimer = null;

    // Reset operation state
    notifier.setCurrentOperation(TranslationOperation.none);
    notifier.setTranslating(false);
    notifier.setStatusText('cancelled');
    notifier.setProgress(0);

    if (mounted) {
      _showSnackBar('Glossary generation cancelled', Colors.orange);
    }
  }

  /// Runs format conversion, then opens the **Convert** tab with source copied to target (no LLM).
  Future<void> _runConvertToolbarAutomation() async {
    final dynamic state = widget.flowId != null
        ? ref.read(translationStateProviderFamily(widget.flowId!))
        : ref.read(translationStateProvider);
    final dynamic notifier = widget.flowId != null
        ? ref.read(translationStateProviderFamily(widget.flowId!).notifier)
        : ref.read(translationStateProvider.notifier);

    await _onConvertFormat(state, notifier);

    if (!mounted) return;

    final l10n = AppLocalizations.of(context)!;
    final dynamic st = widget.flowId != null
        ? ref.read(translationStateProviderFamily(widget.flowId!))
        : ref.read(translationStateProvider);
    final dynamic nt = widget.flowId != null
        ? ref.read(translationStateProviderFamily(widget.flowId!).notifier)
        : ref.read(translationStateProvider.notifier);

    await _startTranslation(
      st,
      nt,
      translationResultTabId: 'convert_tab',
      translationResultTitle: l10n.translationToolbarConvert,
      translationResultIcon: Icons.transform,
      copySourceToTargetOnly: true,
    );
  }

  Future<void> _onConvertFormat(state, notifier) async {
    // Prevent re-entry
    if (state.currentOperation != TranslationOperation.none) {
      return;
    }

    // Check if we have file or text input
    final bool hasFile = state.pickedFile != null;
    final bool hasText = _isTextMode && _textController.text.trim().isNotEmpty;

    if (!hasFile && !hasText) {
      if (mounted) {
        _showSnackBar('Please select a file or enter text first', Colors.red);
      }
      return;
    }

    // If in text mode, convert text to file first
    Uint8List fileBytes;
    String fileName;
    if (_isTextMode && hasText && !hasFile) {
      fileBytes = Uint8List.fromList(utf8.encode(_textController.text.trim()));
      fileName = 'text_input.md';
      // Also set the virtual file in state
      final PlatformFile virtualFile = PlatformFile(
        name: fileName,
        size: fileBytes.length,
        bytes: fileBytes,
      );
      notifier.setPickedFile(virtualFile);
    } else {
      if (state.pickedFile == null) {
        if (mounted) {
          _showSnackBar('Please select a file first', Colors.red);
        }
        return;
      }
      fileBytes = state.pickedFile!.bytes ??
          (await File(state.pickedFile!.path!).readAsBytes());
      fileName = state.pickedFile!.name;
    }

    notifier.setCurrentOperation(TranslationOperation.converting);
    notifier.setTranslating(true);
    notifier.setStatusText('Converting format...');
    notifier.setDownloads(<String, String>{});
    notifier.setDownloading('', false); // Reset downloading state

    // Store existing Extract taskId before resetting (for potential reuse)
    final existingExtractTaskId = state.taskId;

    notifier.setTaskId(null);
    notifier.setProgress(0);
    notifier.setStartTime(DateTime.now());
    notifier.setEndTime(null);
    notifier.setTotalDuration(null);

    try {
      // Get Quick Settings for OCR overrides and language info
      final TranslationQuickSettings qs = widget.flowId != null
          ? ref.read(translationQuickSettingsProviderFamily(widget.flowId!))
          : ref.read(translationQuickSettingsProvider);

      // Get global settings for parsing engine config
      final GlobalSettings globalSettings = ref.read(globalSettingsProvider);
      final FormatConversionService formatService = FormatConversionService();
      final FormatConvertParserOptions parserOpts =
          await formatService.resolveParserOptions(
        parsingEngine: globalSettings.parsingEngine,
        formulaOcr: qs.formulaOcr ?? globalSettings.formulaOcr,
        tableOcr: qs.tableOcr ?? globalSettings.tableOcr,
      );

      // Determine skipCache based on whether Extract phase has been run
      // If Extract phase was run (existingExtractTaskId exists), use cache (skipCache=false)
      // If Extract phase was NOT run, we need to run Extract first (skipCache=true)
      final bool skipCache =
          existingExtractTaskId == null || existingExtractTaskId.isEmpty;
      if (skipCache) {
        _translationScreenLog(
          'Convert phase: No Extract results found, running Extract phase first (skipCache=true)',
        );
      } else {
        _translationScreenLog(
          'Convert phase: Using cached MinerU results from Extract phase (skipCache=false)',
        );
      }

      // Get target language from Quick Settings for exclusion detection
      final String? toLang = qs.toLang.isNotEmpty ? qs.toLang : null;
      final sourceLang =
          qs.sourceLang.isNotEmpty ? qs.sourceLang : 'auto';

      final Map<String, dynamic> result = await formatService.convertFormat(
        fileBytes: fileBytes,
        fileName: fileName,
        convertEngine: parserOpts.convertEngine,
        formulaOcr: parserOpts.formulaOcr,
        tableOcr: parserOpts.tableOcr,
        modelVersion: parserOpts.modelVersion,
        mineruToken: parserOpts.mineruToken,
        // deepSplit: Let backend use default from translation_config.json based on file format
        skipCache: skipCache, // Reuse cache if Extract results are available
        toLang:
            toLang, // CRITICAL: Pass target language for exclusion detection
        sourceLang:
            sourceLang, // OCR language hint for MinerU (markdown_based)
      );

      if (result['success'] == true) {
        final data = result['data'];
        final String? taskId = data['task_id']?.toString();

        if (taskId != null) {
          notifier.setTaskId(taskId);
          // Store backend task id into FlowContext
          if (widget.flowId != null) {
            try {
              final FlowStateNotifier flowNotifier =
                  ref.read(flowProviderFamily(widget.flowId!).notifier);
              flowNotifier.setTranslateArtifacts(
                TranslateArtifacts(
                  backendTaskId: taskId,
                  formatConversionTaskId: taskId,
                ),
              );
            } catch (_) {}
          }

          // Immediately create a Convert tab to show progress (even if window is minimized)
          // This ensures users can see Convert progress and results
          _addFormatConversionTab(taskId, <String, String>{});

          // Poll for status (similar to translation).
          // Large PDF files can take 15+ minutes for MinerU processing;
          // use 30-minute timeout with 4 s interval to reduce main-thread
          // pressure on Windows.
          final TranslationService svc = TranslationService();
          // Note: Format conversion does not require language detection,
          // so we skip the language match warning check for format conversion tasks
          final Map<String, dynamic> statusResp = await svc.pollUntilDone(
            taskId,
            timeoutSec: 1800,
            intervalSec: 4,
            onUpdate: (Map<String, dynamic> st) {
              final String backendStatus = (st['status'] ?? '').toString();
              final String backendMessage = (st['message'] ?? '').toString();
              notifier.setStatusText(backendMessage.isNotEmpty ? backendMessage : backendStatus);
              // Safely extract progress, handling null and invalid types
              final dynamic progressValue = st['progress'];
              final int progress = (progressValue is num)
                  ? progressValue.toInt().clamp(0, 100)
                  : ((progressValue is String && progressValue.isNotEmpty)
                      ? (int.tryParse(progressValue) ?? 0).clamp(0, 100)
                      : 0);
              notifier.setProgress(progress);

              // Skip language detection warning for format conversion tasks
              // Format conversion only converts document format (e.g., PDF to HTML),
              // it does not involve translation, so language detection is not needed

              final String statusText =
                  (st['status'] ?? '').toString().toLowerCase();
              if (statusText == 'completed' || statusText == 'failed') {
                final DateTime endTime = DateTime.now();
                notifier.setEndTime(endTime);
                if (state.startTime != null) {
                  notifier
                      .setTotalDuration(endTime.difference(state.startTime!));
                }
              }
            },
          );

          notifier.setTranslating(false);
          final String statusText = (statusResp['status'] ?? '').toString();
          notifier.setStatusText(statusText);
          // Safely extract progress, handling null and invalid types
          final dynamic progressValue = statusResp['progress'];
          final int progress = (progressValue is num)
              ? progressValue.toInt().clamp(0, 100)
              : ((progressValue is String && progressValue.isNotEmpty)
                  ? (int.tryParse(progressValue) ?? 0).clamp(0, 100)
                  : 0);
          notifier.setProgress(progress);
          final DateTime endTime = DateTime.now();
          notifier.setEndTime(endTime);
          if (state.startTime != null) {
            notifier.setTotalDuration(endTime.difference(state.startTime!));
          }
          // Safely handle downloads field - may be Map, String, or null
          final downloadsValue = statusResp['downloads'];
          Map<String, String> downloads = state.downloads;
          if (downloadsValue != null) {
            if (downloadsValue is Map) {
              downloads = downloadsValue
                  .map((k, v) => MapEntry(k.toString(), v.toString()));
              notifier.setDownloads(downloads);
            } else if (downloadsValue is String) {
              // If downloads is a string (error message), log it but don't set downloads
              _translationScreenLog(
                'Downloads field is a string instead of Map: $downloadsValue',
              );
            }
          }
          final String statusLower = statusText.toLowerCase();
          if (statusLower == 'completed' && downloads.isNotEmpty) {
            if (mounted) {
              _showSnackBar(
                'Format conversion completed. Downloads ready.',
                Colors.green,
              );
            }
            // Add format conversion preview tab
            _addFormatConversionTab(taskId, downloads);
          } else if (statusLower == 'failed') {
            _addFormatConversionTab(taskId, downloads);
            final rawFailure = statusResp['message'];
            final rawError = statusResp['error'];
            final String? failureMessage = rawFailure?.toString().trim();
            final String? errorMessage = rawError?.toString().trim();
            final String combinedMessage =
                (failureMessage != null && failureMessage.isNotEmpty)
                    ? failureMessage
                    : ((errorMessage != null && errorMessage.isNotEmpty)
                        ? errorMessage
                        : 'Format conversion failed.');
            final bool handled = await _handleMineruAuthError(combinedMessage);
            if (mounted && !handled) {
              _showSnackBar(combinedMessage, Colors.red);
            }
          } else {
            if (mounted) {
              _showSnackBar(
                'Format conversion status: $statusText',
                Colors.blue,
              );
            }
          }
        } else {
          throw Exception('No task_id returned');
        }
      } else {
        final String errMsg = result['error']?.toString() ?? 'Unknown error';
        final bool handled = await _handleMineruAuthError(errMsg);
        if (mounted && !handled) {
          _showSnackBar(errMsg, Colors.red);
        }
        return;
      }
    } catch (e) {
      notifier.setTranslating(false);
      notifier.setStatusText('failed');
      final bool handled = await _handleMineruAuthError(e.toString());
      if (mounted && !handled) {
        final String msg =
            e.toString().replaceFirst(RegExp(r'^Exception:\s*'), '');
        _showSnackBar(
            msg.isNotEmpty ? msg : 'Format conversion failed: $e', Colors.red,);
      }
    } finally {
      notifier.setCurrentOperation(TranslationOperation.none);
    }
  }

  Widget _buildGlossaryTable(Map<String, dynamic> glossary) {
    // Show in two columns: Source | Target (like Settings basic view)
    final List<MapEntry<String, dynamic>> rows = glossary.entries.toList();
    return Container(
      constraints: const BoxConstraints(maxHeight: 420),
      padding: const EdgeInsets.all(8),
      decoration: BoxDecoration(
        color: Theme.of(context).colorScheme.surfaceContainerHighest,
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: Theme.of(context).dividerColor),
      ),
      child: SingleChildScrollView(
        child: SingleChildScrollView(
          scrollDirection: Axis.horizontal,
          child: DataTable(
            columns: const <DataColumn>[
              DataColumn(label: Text('Source')),
              DataColumn(label: Text('Target')),
            ],
            rows: rows
                .map(
                  (MapEntry<String, dynamic> e) => DataRow(
                    cells: <DataCell>[
                      DataCell(Text(e.key.toString())),
                      DataCell(Text(e.value.toString())),
                    ],
                  ),
                )
                .toList(),
          ),
        ),
      ),
    );
  }

  Future<void> _downloadGlossaryCsv(Map<String, dynamic> glossary) async {
    // Export CSV in four-column header: src,dst,category,target_lang
    // For generated glossary, category is empty; target_lang from Quick Settings
    final TranslationQuickSettings qs = widget.flowId != null
        ? ref.read(translationQuickSettingsProviderFamily(widget.flowId!))
        : ref.read(translationQuickSettingsProvider);
    final String targetLang = qs.toLang;
    String q(String s) => '"${s.replaceAll('"', '""')}"';
    final List<String> lines = <String>[];
    lines.add('src,dst,category,target_lang');
    glossary.forEach((String k, v) {
      final String src = q(k.toString());
      final String dst = q(v.toString());
      final String category = q('');
      final String tl = q(targetLang);
      lines.add(<String>[src, dst, category, tl].join(','));
    });
    final String content = lines.join('\r\n');
    final List<int> bom = <int>[0xEF, 0xBB, 0xBF];
    final Uint8List bytes = Uint8List.fromList(bom + utf8.encode(content));
    final String fileName =
        'generated_glossary_${DateTime.now().millisecondsSinceEpoch}';
    if (kIsWeb) {
      await FileSaver.instance.saveFile(
        name: fileName,
        bytes: bytes,
        ext: 'csv',
        mimeType: MimeType.csv,
      );
    } else {
      final String? path = await FilePicker.platform.saveFile(
        dialogTitle: 'Save Glossary CSV',
        fileName: '$fileName.csv',
        type: FileType.custom,
        allowedExtensions: <String>['csv'],
      );
      if (path != null) {
        final File f = File(path);
        await f.writeAsBytes(bytes, flush: true);
      }
    }
  }

  // Target Language UI removed; use Quick Settings provider instead.

  /// Check if any operation is in progress (translation, extraction, etc.)
  bool _isOperationInProgress(state) {
    final bool hasTask =
        state.taskId != null && (state.taskId as String).isNotEmpty;
    final isTranslating = state.isTranslating;
    final bool isOperationInProgress =
        state.currentOperation != TranslationOperation.none;
    return hasTask || isTranslating || isOperationInProgress;
  }

  Future<void> _pickFile(notifier) async {
    // CRITICAL: On Web, file picker must be called IMMEDIATELY within user gesture context.
    // Browser security requires the picker to be the FIRST operation - any operation before it
    // (even logging, state reads, or condition checks) can break the user gesture context
    // and cause the picker to return null.

    FilePickerResult? result;

    if (kIsWeb) {
      // Web: Call picker FIRST, then do logging and state checks AFTER
      // DO NOT add any operations before pickFiles() call - not even DateTime.now()
      try {
        // CRITICAL: This must be the FIRST async operation - no operations before this
        // Even DateTime.now() or any other synchronous operation can break user gesture context
        // Allow all supported formats in picker; Pro-only show hint in _processFile if not activated
        final availableFormats = _getAllFileExtensions();
        result = await FilePickerHelper.pickFiles(
          type: FileType.custom,
          allowedExtensions: availableFormats,
          withData: true, // Required on Web to get file.bytes
        );

        // Now safe to do logging and other operations AFTER picker returns
        _translationScreenLog('File picker returned: '
            '${result != null ? "${result.files.length} file(s)" : "null"}');

        if (result == null) {
          // User cancelled or browser blocked access
          _translationScreenLog(
            'File picker returned null (user cancelled or blocked)',
            level: LogLevel.warn,
          );
          return;
        }

        if (result.files.isEmpty) {
          _translationScreenLog(
            'File picker returned empty files list',
            level: LogLevel.warn,
          );
          if (mounted) {
            _showSnackBar(
              'No file was selected. Please try again.',
              Colors.orange,
            );
          }
          return;
        }

        final PlatformFile file = result.files.first;
        _translationScreenLog(
          'File selected: ${file.name} (${file.size} bytes, hasBytes=${file.bytes != null})',
        );

        // On Web, file.path is always null, but file.bytes should be available
        if (file.bytes == null) {
          _translationScreenLog(
            'ERROR: file.bytes is null on Web!',
            level: LogLevel.error,
          );
          if (mounted) {
            _showSnackBar(
              'File data not available. Please try selecting the file again.',
              Colors.red,
            );
          }
          return;
        }
      } catch (e, stackTrace) {
        _translationScreenLog(
          'File picker exception: $e\n$stackTrace',
          level: LogLevel.error,
        );
        if (mounted) {
          _showSnackBar(
            'File selection error: ${e.toString()}. Please try again.',
            Colors.red,
          );
        }
        return;
      }

      // Now safe to do state checks AFTER picker call
      if (!mounted) return;

      final dynamic state = widget.flowId != null
          ? ref.read(translationStateProviderFamily(widget.flowId!))
          : ref.read(translationStateProvider);

      if (_isOperationInProgress(state)) {
        if (mounted) {
          _showSnackBar(
            'File selection is disabled while an operation is in progress.',
            Colors.orange,
            duration: const Duration(seconds: 3),
          );
        }
        return;
      }

      if (mounted) {
        notifier.setCurrentOperation(TranslationOperation.importing);
      }
    } else {
      // Desktop: Can do state checks first (no user gesture restrictions)
      if (!mounted) return;

      final dynamic state = widget.flowId != null
          ? ref.read(translationStateProviderFamily(widget.flowId!))
          : ref.read(translationStateProvider);

      if (_isOperationInProgress(state)) {
        if (mounted) {
          _showSnackBar(
            'File selection is disabled while an operation is in progress.',
            Colors.orange,
            duration: const Duration(seconds: 3),
          );
        }
        return;
      }

      // Prevent re-entry
      if (state.currentOperation == TranslationOperation.importing) {
        return;
      }

      // Small delay prevents double-click issues on desktop
      notifier.setCurrentOperation(TranslationOperation.importing);
      await Future.delayed(const Duration(milliseconds: 100));
      if (!mounted) {
        notifier.setCurrentOperation(TranslationOperation.none);
        return;
      }

      try {
        // Allow all supported formats in picker; Pro-only show hint in _processFile if not activated
        final availableFormats = _getAllFileExtensions();
        result = await FilePickerHelper.pickFiles(
          type: FileType.custom,
          allowedExtensions: availableFormats,
          withData: true,
        );
        _translationScreenLog(
          'File picker returned: ${result != null ? "${result.files.length} file(s)" : "null"}',
        );
      } catch (e, stackTrace) {
        _translationScreenLog(
          'File picker exception: $e\n$stackTrace',
          level: LogLevel.error,
        );
        if (mounted) {
          notifier.setCurrentOperation(TranslationOperation.none);
          _showSnackBar(
            'File selection error: ${e.toString()}. Please try again.',
            Colors.red,
          );
        }
        return;
      }
    }

    // Process the selected file (common for both Web and Desktop)
    if (result == null || result.files.isEmpty) {
      // User cancelled or empty result - reset operation state
      if (mounted) {
        notifier.setCurrentOperation(TranslationOperation.none);
      }
      if (result != null && result.files.isEmpty) {
        _translationScreenLog(
          'File picker returned empty files list',
          level: LogLevel.warn,
        );
        if (mounted) {
          _showSnackBar(
            'No file was selected. Please try again.',
            Colors.orange,
          );
        }
      }
      return;
    }

    final PlatformFile file = result.files.single;
    await _processFile(file, notifier);
  }

  Future<void> _handleDroppedFile(PlatformFile file, notifier) async {
    if (!mounted) return;

    final dynamic state = widget.flowId != null
        ? ref.read(translationStateProviderFamily(widget.flowId!))
        : ref.read(translationStateProvider);

    if (_isOperationInProgress(state)) {
      if (mounted) {
        _showSnackBar(
          'File selection is disabled while an operation is in progress.',
          Colors.orange,
          duration: const Duration(seconds: 3),
        );
      }
      return;
    }

    try {
      notifier.setCurrentOperation(TranslationOperation.importing);
      await _processFile(file, notifier);
    } catch (e, stackTrace) {
      _translationScreenLog(
        'Error in _handleDroppedFile: $e\n$stackTrace',
        level: LogLevel.error,
      );
      notifier.setCurrentOperation(TranslationOperation.none);
      if (mounted) {
        _showSnackBar(
          'Error processing dropped file: ${e.toString()}',
          Colors.red,
        );
      }
    }
  }

  Future<void> _processFile(PlatformFile file, notifier) async {
    // Log file selection details
    // Note: On Web, file.path is always null (browser security), but file.name and file.bytes are available
    _translationScreenLog(
      'Processing file: name=${file.name}, size=${file.size}, '
      'hasBytes=${file.bytes != null}',
    );

    // Check if file is .doc (not .docx) - unsupported format
    final String fileName = file.name.toLowerCase();
    if (fileName.endsWith('.doc') && !fileName.endsWith('.docx')) {
      if (mounted) {
        _showSnackBar(
          'DOC files are not supported. Please convert the file to DOCX format and import again.',
          Colors.red,
        );
      }
      notifier.setCurrentOperation(TranslationOperation.none);
      return;
    }

    // Check if file is .ppt (not .pptx) - unsupported format
    if (fileName.endsWith('.ppt') && !fileName.endsWith('.pptx')) {
      if (mounted) {
        _showSnackBar(
          'PPT files are not supported. Please convert the file to PPTX format and import again.',
          Colors.red,
        );
      }
      notifier.setCurrentOperation(TranslationOperation.none);
      return;
    }

    // Check if file format is supported for current user edition
    final fileExtension = fileName.split('.').last.toLowerCase();
    final isSupported =
        await _fileFormatService.isFormatSupported(fileExtension);
    if (!isSupported) {
      if (mounted) {
        final errorMessage =
            _fileFormatService.getUnsupportedFormatMessage(fileExtension);
        _showSnackBar(errorMessage, Colors.red);
      }
      notifier.setCurrentOperation(TranslationOperation.none);
      return;
    }

    // Validate file data is available
    // On Web, we must use file.bytes (file.path is always null)
    // On Desktop, prefer file.bytes, but can fall back to file.path if needed
    var hasData = file.bytes != null;
    if (!hasData && !kIsWeb) {
      // On Desktop, try to read from path if bytes not available
      try {
        hasData = file.path != null;
      } catch (e) {
        hasData = false;
      }
    }

    if (!hasData) {
      _translationScreenLog(
        'File data is not available: name=${file.name}, size=${file.size}',
        level: LogLevel.error,
      );
      if (mounted) {
        _showSnackBar(
          'File data is not available. Please try selecting the file again.',
          Colors.red,
        );
      }
      notifier.setCurrentOperation(TranslationOperation.none);
      return;
    }

    // Check file size (warn if very large, but don't block)
    if (file.size > 100 * 1024 * 1024) {
      _translationScreenLog(
        'Large file selected: ${file.name}, size=${file.size} bytes',
        level: LogLevel.warn,
      );
    }

    // If there is an existing translation task for this flow, release its resources
    // before starting a new Extract/import. This prevents orphaned tasks when users
    // re-import a file in the same workflow tab.
    if (widget.flowId != null) {
      final dynamic translationState =
          ref.read(translationStateProviderFamily(widget.flowId!));
      final String? existingTaskId = translationState.taskId as String?;
      if (existingTaskId != null &&
          existingTaskId.isNotEmpty &&
          !existingTaskId.startsWith('pending_')) {
        try {
          final TranslationService svc = TranslationService();
          await svc.releaseTask(existingTaskId);
          _translationScreenLog(
            'Released previous task resources before re-import: $existingTaskId',
            level: LogLevel.info,
          );
        } catch (e) {
          _translationScreenLog(
            'Failed to release previous task resources before re-import: $e',
            level: LogLevel.warn,
          );
        }
      }
    }

    // Clear all existing preview tabs when re-importing
    final PreviewTabsNotifier tabsNotifier = widget.flowId != null
        ? ref.read(previewTabsProviderFamily(widget.flowId!).notifier)
        : ref.read(previewTabsProvider.notifier);
    tabsNotifier.clearAllTabs();

    notifier.setPickedFile(file);

    // Queued mode: align Quick Settings target language with Settings default on import.
    if (widget.executionMode == 'queued' && !_isReeditMode) {
      final GlobalSettings globalSettings = ref.read(globalSettingsProvider);
      if (globalSettings.targetLanguage.isNotEmpty) {
        final TranslationQuickSettingsNotifier qsNotifier =
            widget.flowId != null
                ? ref.read(
                    translationQuickSettingsProviderFamily(widget.flowId!)
                        .notifier,
                  )
                : ref.read(translationQuickSettingsProvider.notifier);
        qsNotifier.applyDefaultTargetLanguage(globalSettings.targetLanguage);
      }
    }

    // Save state to persistence after file is picked
    if (widget.flowId != null) {
      try {
        // Set this flow as active when file is imported
        final TasksNotifier tasksNotifier = ref.read(tasksProvider.notifier);
        tasksNotifier.setActive(widget.flowId!);

        final FlowStateNotifier flowNotifier =
            ref.read(flowProviderFamily(widget.flowId!).notifier);
        final TranslationQuickSettings qs =
            ref.read(translationQuickSettingsProviderFamily(widget.flowId!));
        await flowNotifier.saveStateWithGlossaryIds(qs.selectedGlossaries);

        // Save file name to flow context
        // On Web, file.path is always null (browser security), so we pass null
        // On Desktop, file.path may be available, but we don't require it
        // We use file.name and file.bytes for all operations
        String? filePath;
        if (!kIsWeb) {
          try {
            filePath = file.path; // Optional: may be null even on desktop
          } catch (e) {
            filePath = null;
          }
        }
        flowNotifier.updateSource(
          FlowSource(
            fileName: file.name, // Always available (Web and Desktop)
            filePath: filePath, // Optional: null on Web, may be null on Desktop
          ),
        );
      } catch (e) {
        _translationScreenLog('Failed to save state after file pick: $e');
      }
    }

    // Auto init preview by running format-conversion (no token usage)
    try {
      final FormatConversionService formatSvc = FormatConversionService();
      // Get file bytes: prefer file.bytes (available on both Web and Desktop)
      // On Web, file.path is always null, so we must use file.bytes
      // On Desktop, file.bytes is preferred, but we can fall back to file.path if needed
      Uint8List bytes;
      if (file.bytes != null) {
        bytes = file.bytes!; // Preferred: available on both platforms
      } else if (!kIsWeb) {
        // On Desktop only: fall back to reading from path if bytes not available
        try {
          final String? filePath = file.path;
          if (filePath != null) {
            bytes = await File(filePath).readAsBytes();
          } else {
            throw Exception('File data not available: no bytes and no path');
          }
        } catch (e) {
          throw Exception('Failed to read file from path: $e');
        }
      } else {
        // On Web, bytes should always be available if withData=true
        throw Exception(
          'File bytes not available on Web platform (withData should be true)',
        );
      }
      // Get target language from Quick Settings for exclusion detection
      final TranslationQuickSettings qs = widget.flowId != null
          ? ref.read(translationQuickSettingsProviderFamily(widget.flowId!))
          : ref.read(translationQuickSettingsProvider);
      final String? toLang = qs.toLang.isNotEmpty ? qs.toLang : null;
      final sourceLang =
          qs.sourceLang.isNotEmpty ? qs.sourceLang : 'auto';

      final GlobalSettings globalSettings = ref.read(globalSettingsProvider);
      final FormatConvertParserOptions parserOpts =
          await formatSvc.resolveParserOptions(
        parsingEngine: globalSettings.parsingEngine,
        formulaOcr: qs.formulaOcr ?? globalSettings.formulaOcr,
        tableOcr: qs.tableOcr ?? globalSettings.tableOcr,
      );

      final Map<String, dynamic> convertRes = await formatSvc.convertFormat(
        fileBytes: bytes,
        fileName: file.name,
        convertEngine: parserOpts.convertEngine,
        formulaOcr: parserOpts.formulaOcr,
        tableOcr: parserOpts.tableOcr,
        modelVersion: parserOpts.modelVersion,
        mineruToken: parserOpts.mineruToken,
        skipCache:
            true, // Extract phase: Always access MinerU server directly (skipCache=true to force fresh conversion)
        toLang:
            toLang, // CRITICAL: Pass target language for exclusion detection
        sourceLang:
            sourceLang, // OCR language hint for MinerU (markdown_based)
      );
      if (convertRes['success'] == true) {
        final Map<String, dynamic> data =
            (convertRes['data'] as Map).cast<String, dynamic>();
        final String? taskId = data['task_id']?.toString();
        if (taskId != null && taskId.isNotEmpty) {
          notifier.setTaskId(taskId);
          _translationScreenLog(
            'File processed: taskId=$taskId, flowId=${widget.flowId}',
            level: LogLevel.info,
          );
          // Open a preview tab immediately to show Extract view
          _addExtractTab(taskId);
        } else {
          _translationScreenLog(
            'Format conversion succeeded but task_id is null or empty',
            level: LogLevel.warn,
          );
        }
      } else {
        final bool handled =
            await _handleMineruAuthError(convertRes['error']?.toString());
        if (mounted && !handled) {
          _showSnackBar(
              convertRes['error']?.toString() ?? 'Request failed', Colors.red,);
        }
      }
    } catch (e) {
      final bool handled = await _handleMineruAuthError(e.toString());
      if (mounted && !handled) {
        _showSnackBar('File import failed: $e', Colors.red);
      }
    }

    // Reset operation state after file processing completes.
    // MUST be done before the mounted check — the notifier persists across widget
    // lifecycles via Riverpod. If we skip this when !mounted, the next widget
    // instance for the same flow will see currentOperation stuck as "importing"
    // and ALL toolbar buttons (Translate, Glossary, Re-extract, etc.) will be
    // permanently disabled.
    notifier.setCurrentOperation(TranslationOperation.none);

    // Widget may have been disposed during the async file processing above.
    if (!mounted) return;

    // Auto-update workflow type if auto-select is enabled
    final TranslationQuickSettings qs = widget.flowId != null
        ? ref.read(translationQuickSettingsProviderFamily(widget.flowId!))
        : ref.read(translationQuickSettingsProvider);
    final TranslationQuickSettingsNotifier qsNotifier = widget.flowId != null
        ? ref.read(
            translationQuickSettingsProviderFamily(widget.flowId!).notifier,
          )
        : ref.read(translationQuickSettingsProvider.notifier);

    if (qs.autoSelectWorkflow) {
      final String ext = file.name.split('.').last.toLowerCase();
      final String? selectedWorkflow =
          qsNotifier.selectWorkflowFromExtension(ext);
      if (selectedWorkflow != null && selectedWorkflow != qs.workflowType) {
        // Update workflow type even when dropdown is disabled
        // This allows user to see the automatically selected workflow
        qsNotifier.updateWorkflowType(selectedWorkflow);
      }
    }

    // Log completion with current taskId from state
    final dynamic currentState = widget.flowId != null
        ? ref.read(translationStateProviderFamily(widget.flowId!))
        : ref.read(translationStateProvider);
    _translationScreenLog(
      'File processing completed: currentOperation reset to none, taskId=${currentState.taskId}',
    );
  }

  Future<void> _startFetchUrl(translationNotifier) async {
    final String url = _urlController.text.trim();
    if (url.isEmpty) return;

    setState(() {
      _isFetchingUrl = true;
    });
    translationNotifier.setCurrentOperation(TranslationOperation.importing);

    try {
      // If there is an existing translation task for this flow, release its resources
      if (widget.flowId != null) {
        final dynamic translationState =
            ref.read(translationStateProviderFamily(widget.flowId!));
        final String? existingTaskId = translationState.taskId as String?;
        if (existingTaskId != null &&
            existingTaskId.isNotEmpty &&
            !existingTaskId.startsWith('pending_')) {
          try {
            final TranslationService svc = TranslationService();
            await svc.releaseTask(existingTaskId);
            _translationScreenLog(
              'Released previous task resources before URL fetch: $existingTaskId',
              level: LogLevel.info,
            );
          } catch (e) {
            _translationScreenLog(
              'Failed to release previous task resources before URL fetch: $e',
              level: LogLevel.warn,
            );
          }
        }
      }

      // Clear all existing preview tabs when re-importing
      final PreviewTabsNotifier tabsNotifier = widget.flowId != null
          ? ref.read(previewTabsProviderFamily(widget.flowId!).notifier)
          : ref.read(previewTabsProvider.notifier);
      tabsNotifier.clearAllTabs();

      // Save state to persistence
      if (widget.flowId != null) {
        try {
          final TasksNotifier tasksNotifier = ref.read(tasksProvider.notifier);
          tasksNotifier.setActive(widget.flowId!);

          final FlowStateNotifier flowNotifier =
              ref.read(flowProviderFamily(widget.flowId!).notifier);
          final TranslationQuickSettings qs =
              ref.read(translationQuickSettingsProviderFamily(widget.flowId!));
          await flowNotifier.saveStateWithGlossaryIds(qs.selectedGlossaries);

          flowNotifier.updateSource(
            const FlowSource(fileName: 'fetched.html'),
          );
        } catch (e) {
          _translationScreenLog('Failed to save state after URL fetch start: $e');
        }
      }

      final FormatConversionService formatSvc = FormatConversionService();
      final TranslationQuickSettings qs = widget.flowId != null
          ? ref.read(translationQuickSettingsProviderFamily(widget.flowId!))
          : ref.read(translationQuickSettingsProvider);
      final String? toLang = qs.toLang.isNotEmpty ? qs.toLang : null;

      final cancelToken = CancelToken();
      _fetchUrlCancelToken = cancelToken;

      final Map<String, dynamic> fetchRes = await formatSvc.fetchUrl(
        url: url,
        extractMode: _urlExtractMode,
        workflowType: 'html',
        toLang: toLang,
        cancelToken: cancelToken,
      );

      if (fetchRes['success'] == true) {
        final Map<String, dynamic> data =
            (fetchRes['data'] as Map).cast<String, dynamic>();
        final String? taskId = data['task_id']?.toString();
        if (taskId != null && taskId.isNotEmpty) {
          translationNotifier.setTaskId(taskId);
          _translationScreenLog(
            'URL fetched successfully: taskId=$taskId, flowId=${widget.flowId}',
            level: LogLevel.info,
          );
          _addExtractTab(taskId);

          // Decode base64 HTML content from backend so Convert/Translate
          // can reuse the actual file bytes instead of empty bytes.
          Uint8List fileBytes = Uint8List(0);
          final String? fileContentB64 = data['file_content']?.toString();
          if (fileContentB64 != null && fileContentB64.isNotEmpty) {
            try {
              fileBytes = base64Decode(fileContentB64);
              _translationScreenLog(
                'URL fetch: decoded ${fileBytes.length} bytes from file_content',
                level: LogLevel.info,
              );
            } catch (e) {
              _translationScreenLog(
                'Failed to decode file_content from fetch-url response: $e',
                level: LogLevel.warn,
              );
            }
          } else {
            _translationScreenLog(
              'URL fetch: file_content missing or empty in response',
              level: LogLevel.warn,
            );
          }

          // Set a virtual picked file so toolbar buttons
          // (glossary, convert, translate) are enabled
          final PlatformFile virtualFile = PlatformFile(
            name: 'fetched.html',
            size: fileBytes.length,
            bytes: fileBytes,
          );
          translationNotifier.setPickedFile(virtualFile);
        } else {
          _translationScreenLog(
            'URL fetch succeeded but task_id is null or empty',
            level: LogLevel.warn,
          );
        }
      } else {
        if (mounted) {
          _showSnackBar(
            fetchRes['error']?.toString() ?? 'URL fetch failed',
            Colors.red,
          );
        }
      }
    } on DioException catch (e) {
      if (e.type == DioExceptionType.cancel) {
        _translationScreenLog(
          'URL fetch cancelled by user',
          level: LogLevel.info,
        );
        // Silently reset state; no error toast
      } else {
        _translationScreenLog(
          'URL fetch DioException: $e',
          level: LogLevel.error,
        );
        if (mounted) {
          _showSnackBar('URL fetch failed: $e', Colors.red);
        }
      }
    } catch (e, stackTrace) {
      _translationScreenLog(
        'URL fetch error: $e\n$stackTrace',
        level: LogLevel.error,
      );
      if (mounted) {
        _showSnackBar('URL fetch failed: $e', Colors.red);
      }
    } finally {
      _fetchUrlCancelToken = null;
    }

    // Reset operation state after URL fetch completes.
    // MUST be done before the mounted check to prevent permanently-disabled
    // toolbar buttons if the widget was disposed during async fetch.
    translationNotifier.setCurrentOperation(TranslationOperation.none);

    if (!mounted) return;

    // Auto-update workflow type to html
    final TranslationQuickSettings qs = widget.flowId != null
        ? ref.read(translationQuickSettingsProviderFamily(widget.flowId!))
        : ref.read(translationQuickSettingsProvider);
    final TranslationQuickSettingsNotifier qsNotifier = widget.flowId != null
        ? ref.read(translationQuickSettingsProviderFamily(widget.flowId!).notifier)
        : ref.read(translationQuickSettingsProvider.notifier);

    if (qs.autoSelectWorkflow || qs.workflowType != 'html') {
      qsNotifier.updateWorkflowType('html');
    }

    translationNotifier.setCurrentOperation(TranslationOperation.none);

    // Re-read current state to check if fetch succeeded (taskId set)
    final dynamic currentState = widget.flowId != null
        ? ref.read(translationStateProviderFamily(widget.flowId!))
        : ref.read(translationStateProvider);

    setState(() {
      _isFetchingUrl = false;
      // Hide URL panel on success so user can continue with normal workflow.
      // If fetch failed, _showUrlInput stays true so user can retry.
      if (currentState.taskId != null &&
          (currentState.taskId as String).isNotEmpty) {
        _showUrlInput = false;
      }
    });
  }

  void _cancelFetchUrl() {
    _fetchUrlCancelToken?.cancel('User cancelled fetch URL');
  }

  Future<void> _cancelCurrentTask(notifier) async {
    // Show confirmation dialog
    final bool? confirmed = await showDialog<bool>(
      context: context,
      builder: (BuildContext context) => AlertDialog(
        title: Text(
          AppLocalizations.of(context)!.translationDialogCancelTaskTitle,
        ),
        content: Text(
          AppLocalizations.of(context)!.translationDialogCancelTaskBody,
        ),
        actions: <Widget>[
          TextButton(
            onPressed: () => Navigator.of(context).pop(false),
            child: Text(
              AppLocalizations.of(context)!.translationDialogCancelTaskNo,
            ),
          ),
          TextButton(
            onPressed: () => Navigator.of(context).pop(true),
            style: TextButton.styleFrom(
              foregroundColor: Theme.of(context).colorScheme.error,
            ),
            child: Text(
              AppLocalizations.of(context)!.translationDialogCancelTaskYesCancel,
            ),
          ),
        ],
      ),
    );

    if (confirmed != true) return;

    // Clear all tabs
    final PreviewTabsNotifier tabsNotifier = widget.flowId != null
        ? ref.read(previewTabsProviderFamily(widget.flowId!).notifier)
        : ref.read(previewTabsProvider.notifier);
    tabsNotifier.clearAllTabs();

    // Release backend task resources before resetting translation state
    try {
      final dynamic translationState = widget.flowId != null
          ? ref.read(translationStateProviderFamily(widget.flowId!))
          : ref.read(translationStateProvider);
      final String? taskId = translationState.taskId as String?;
      if (taskId != null &&
          taskId.isNotEmpty &&
          !taskId.startsWith('pending_')) {
        final TranslationService svc = TranslationService();
        await svc.releaseTask(taskId);
        _translationScreenLog(
          'Released task resources on resetFlow: $taskId',
          level: LogLevel.info,
        );
      }
    } catch (e) {
      _translationScreenLog(
        'Failed to release task resources on resetFlow: $e',
        level: LogLevel.warn,
      );
    }

    // Reset translation state
    notifier.resetTranslation();

    // Clear persisted steps state
    if (widget.flowId != null) {
      try {
        final FlowStateNotifier flowNotifier =
            ref.read(flowProviderFamily(widget.flowId!).notifier);
        // Clear steps state by saving with empty steps state
        await flowNotifier.saveStateWithGlossaryIds(
          <String>[],
          stepsState: PersistedStepsState(),
        );
      } catch (e) {
        _translationScreenLog('Failed to clear steps state: $e');
      }
    }

    // Reset local state
    setState(() {
      _glossarySkipped = false;
      _persistedStepsState = null;
    });

    if (mounted) {
      _showSnackBar(
        'Task cancelled. You can now select a new file.',
        Colors.blue,
      );
    }
  }

  /// Returns true if at least one LLM platform is configured and available.
  ///
  /// 优先使用后端 `/auth/ai-platform-status` 返回的实时状态判断是否可用，
  /// 仅在没有状态数据时，才退回到检查是否存在非空的 API Key（主要用于兼容旧逻辑）。
  bool _hasAnyUsableLlmPlatform(
    Map<String, dynamic>? appConfig,
    Map<String, dynamic>? secretsConfig,
    Map<String, dynamic>? statusMap,
  ) {
    final aiPlatforms = appConfig?['ai_platforms'] as Map<String, dynamic>?;
    if (aiPlatforms == null || aiPlatforms.isEmpty) return false;

    final platformsStatus =
        statusMap?['platforms'] as Map<String, dynamic>?;
    final platformApiKeys =
        secretsConfig?['platform_api_keys'] as Map<String, dynamic>?;

    // 1. 如果有平台状态数据，优先根据 isApiAvailable 判断
    if (platformsStatus != null && platformsStatus.isNotEmpty) {
      for (final entry in aiPlatforms.entries) {
        final key = entry.key;
        if (key == 'default_platform' || key == 'mineru') continue;
        if (entry.value is! Map<String, dynamic>) continue;

        final status = platformsStatus[key];
        if (status is Map<String, dynamic>) {
          final dynamic available = status['isApiAvailable'];
          if (available == true) {
            return true;
          }
        }
      }
      // 有状态数据但都不可用
      return false;
    }

    // 2. 没有状态数据时，兼容旧逻辑：检查是否存在至少一个非空的 API Key
    if (platformApiKeys == null || platformApiKeys.isEmpty) return false;
    for (final entry in aiPlatforms.entries) {
      final key = entry.key;
      if (key == 'default_platform' || key == 'mineru') continue;
      if (entry.value is! Map<String, dynamic>) continue;
      final apiKey = platformApiKeys[key];
      final keyStr = apiKey?.toString().trim() ?? '';
      if (keyStr.isEmpty) continue;
      return true;
    }

    return false;
  }

  /// Shows dialog when no LLM is available. Returns null = cancel, false = go configure, true = continue (format only).
  Future<bool?> _showNoLlmAvailableDialog(BuildContext context) async {
    final l10n = AppLocalizations.of(context)!;
    return DialogHelper.showDialog<bool>(
      context: context,
      builder: (BuildContext ctx) => AlertDialog(
        title: Text(l10n.translationNoLlmAvailableTitle),
        content: SingleChildScrollView(
          child: Text(l10n.translationNoLlmAvailableMessage),
        ),
        actions: <Widget>[
          TextButton(
            onPressed: () => Navigator.of(ctx).pop(),
            child: Text(l10n.translationDialogCancelButton),
          ),
          TextButton(
            onPressed: () => Navigator.of(ctx).pop(false),
            child: Text(l10n.translationNoLlmConfigureButton),
          ),
          FilledButton(
            onPressed: () => Navigator.of(ctx).pop(true),
            child: Text(l10n.translationNoLlmContinueFormatOnlyButton),
          ),
        ],
      ),
    );
  }

  Future<void> _startTranslation(
    state,
    notifier, {
    String translationResultTabId = 'translate_tab',
    String? translationResultTitle,
    IconData? translationResultIcon,
    bool copySourceToTargetOnly = false,
  }) async {
    // Prevent re-entry
    if (state.currentOperation != TranslationOperation.none) {
      return;
    }

    // Reset per-translation flags
    _hasRefreshedPlatformStatus = false;

    // Check if there's an ongoing translation task
    final bool hasOngoingTranslation = state.isTranslating ||
        state.currentOperation == TranslationOperation.translating ||
        (state.taskId != null &&
            state.taskId!.isNotEmpty &&
            (state.statusText.toLowerCase() != 'completed' &&
                state.statusText.toLowerCase() != 'failed' &&
                state.statusText.toLowerCase() != 'cancelled'));

    if (hasOngoingTranslation) {
      // Cancel old translation task if exists
      final oldTaskId = state.taskId;
      if (oldTaskId != null && oldTaskId.isNotEmpty) {
        try {
          final TranslationService svc = TranslationService();
          // Check task status first to avoid unnecessary cancellation
          final taskStatus = await svc.getStatus(oldTaskId);
          final status = (taskStatus['status'] ?? '').toString().toLowerCase();
          final isTaskDone = status == 'completed' ||
              status == 'failed' ||
              status == 'cancelled';

          // Only cancel if task is still processing
          if (!isTaskDone) {
            await svc.cancelTask(oldTaskId);
            // Show user-facing message only if this screen instance has already
            // started at least one translation in the current session.
            // This avoids confusing users on first run when an old background
            // task is being cleaned up silently.
            if (mounted && _hasStartedTranslationInThisSession) {
              final l10n = AppLocalizations.of(context)!;
              _showSnackBar(
                l10n.translationSnackPreviousTranslationCancelled,
                Colors.orange,
              );
            }
          }
        } catch (e) {
          // Log error but continue
          _translationScreenLog('Failed to cancel old translation task: $e');
        }
      }

      // Clean up old translation results
      // 1. Close translate tab (without releasing task - task will be released when user closes tab)
      final PreviewTabsNotifier tabsNotifier = widget.flowId != null
          ? ref.read(previewTabsProviderFamily(widget.flowId!).notifier)
          : ref.read(previewTabsProvider.notifier);
      // Use closeTabByIdSilently to close tab without triggering onTabClose callback
      // This prevents releasing the task when starting a new translation
      // The task should only be released when user explicitly closes the tab
      tabsNotifier.closeTabByIdSilently('translate_tab');
      tabsNotifier.closeTabByIdSilently('convert_tab');

      // 2. Clear translation state (but keep file and other settings)
      notifier.setTranslating(false);
      notifier.setStatusText('');
      notifier.setProgress(0);
      notifier.setTaskId(null);
      notifier.setDownloads(<String, String>{});
      notifier.setStartTime(null);
      notifier.setEndTime(null);
      notifier.setTotalDuration(null);
      notifier.setTranslationStats(
        successCount: null,
        failCount: null,
        totalSegments: null,
      );
      notifier.setCurrentOperation(TranslationOperation.none);
      // Reset language warning flag when clearing translation state
      _hasShownLanguageWarning = false;
      _autoPersistedQueueTaskIds.clear();
      _clearQueuePersistDirty();

      // 3. Clear translation artifacts from FlowContext
      if (widget.flowId != null) {
        try {
          final FlowStateNotifier flowNotifier =
              ref.read(flowProviderFamily(widget.flowId!).notifier);
          flowNotifier.setTranslateArtifacts(const TranslateArtifacts());
        } catch (e) {
          _translationScreenLog('Failed to clear translate artifacts: $e');
        }
      }

      // Small delay to ensure cleanup is complete
      await Future.delayed(const Duration(milliseconds: 100));
    }

    // Check if we have file or text input
    final bool hasFile = state.pickedFile != null;
    final bool hasText = _textController.text.trim().isNotEmpty;

    if (!hasFile && !hasText) {
      if (mounted) {
        _showSnackBar('Please select a file or enter text first.', Colors.red);
      }
      return;
    }

    // Check if detected language matches target language (only for file mode)
    if (hasFile && state.taskId != null && state.taskId!.isNotEmpty) {
      try {
        final TranslationService svc = TranslationService();
        final Map<String, dynamic> statusResp =
            await svc.getStatus(state.taskId!);
        final String? detectedLang = statusResp['detected_language'] as String?;

        if (detectedLang != null && detectedLang.isNotEmpty) {
          final TranslationQuickSettings qs = widget.flowId != null
              ? ref.read(translationQuickSettingsProviderFamily(widget.flowId!))
              : ref.read(translationQuickSettingsProvider);
          final String targetLang = qs.toLang.toLowerCase();

          // Normalize language codes for comparison
          // Map common language codes to standard format
          final String normalizedDetected =
              _normalizeLanguageCode(detectedLang);
          final String normalizedTarget = _normalizeLanguageCode(targetLang);

          if (normalizedDetected == normalizedTarget) {
            // Document language matches target -> may be wrong target, ask to continue
            final String detectedLangName =
                _convertLangCodeToName(detectedLang);
            final String targetLangName = _convertLangCodeToName(targetLang);
            final l10n = AppLocalizations.of(context)!;
            final bool? confirmed = await DialogHelper.showDialog<bool>(
              context: context,
              builder: (BuildContext context) => AlertDialog(
                title: Text(l10n.languageMatchWarningTitle),
                content: Text(
                  l10n.languageMatchWarningTranslationBody(
                    detectedLangName,
                    targetLangName,
                  ),
                ),
                actions: <Widget>[
                  TextButton(
                    onPressed: () => Navigator.of(context).pop(false),
                    child: Text(l10n.translationDialogCancelButton),
                  ),
                  TextButton(
                    onPressed: () => Navigator.of(context).pop(true),
                    style: TextButton.styleFrom(
                      foregroundColor: Theme.of(context).colorScheme.error,
                    ),
                    child: Text(l10n.translationDialogContinueButton),
                  ),
                ],
              ),
            );

            if (confirmed != true) {
              return; // User cancelled
            }
          }

          // Check if document is multilingual
          final bool isMultilingual =
              statusResp['is_multilingual'] as bool? ?? false;
          final Map<String, dynamic>? languageDistribution =
              statusResp['language_distribution'] as Map<String, dynamic>?;

          if (isMultilingual && languageDistribution != null) {
            // Show multilingual prompt dialog
            final bool? result = await _showMultilingualPromptDialog(
              detectedLang,
              languageDistribution.cast<String, double>(),
            );

            if (result == null) {
              // User cancelled
              return;
            }
          }
        }
      } catch (e) {
        // If language detection check fails, continue with translation
        _translationScreenLog('Failed to check detected language: $e');
      }
    }

    // If in text mode and has text, convert text to file format
    if (_isTextMode && hasText && !hasFile) {
      await _convertTextToFile(notifier);
      // After conversion, state.pickedFile should be set, so we can continue
      // Re-read state to get updated pickedFile
      final Object updatedState = widget.flowId != null
          ? ref.read(translationStateProviderFamily(widget.flowId!))
          : ref.read(translationStateProvider);
      // Check if pickedFile is set (using dynamic access since state type varies)
      final dynamic updatedStateDynamic = updatedState;
      if (updatedStateDynamic.pickedFile == null) {
        if (mounted) {
          _showSnackBar('Failed to convert text to file format.', Colors.red);
        }
        return;
      }
      // Continue with updated state (will check re-entry again in recursive call)
      return _startTranslation(
        updatedStateDynamic,
        notifier,
        translationResultTabId: translationResultTabId,
        translationResultTitle: translationResultTitle,
        translationResultIcon: translationResultIcon,
        copySourceToTargetOnly: copySourceToTargetOnly,
      );
    }

    if (state.pickedFile == null) {
      if (mounted) {
        _showSnackBar('Please select a document first.', Colors.red);
      }
      return;
    }

    // Check if glossary tab exists; if not, mark as skipped
    final PreviewTabsState tabsState = widget.flowId != null
        ? ref.read(previewTabsProviderFamily(widget.flowId!))
        : ref.read(previewTabsProvider);
    final bool hasGlossaryTab = tabsState.tabs
        .any((PreviewTab t) => t.type.toString().endsWith('glossary'));
    if (!hasGlossaryTab && !_glossarySkipped) {
      setState(() {
        _glossarySkipped = true;
      });
    }

    // Note: Unsaved changes check is handled by GlossaryPreview widget
    // If user is editing, they should save before translating

    // Get glossary from FlowContext and apply it to task after submission
    Map<String, dynamic>? glossaryToApply;
    if (widget.flowId != null) {
      try {
        final FlowStateModel flowState =
            ref.read(flowProviderFamily(widget.flowId!));
        final GlossaryArtifacts glossaryArtifacts = flowState.context.glossary;
        _translationScreenLog(
          '[DEBUG] FlowContext glossary check for flowId ${widget.flowId}:',
        );
        _translationScreenLog(
          '[DEBUG]   - confirmedTerms: ${glossaryArtifacts.confirmedTerms?.length ?? 0} entries',
        );
        _translationScreenLog(
          '[DEBUG]   - terms: ${glossaryArtifacts.terms?.length ?? 0} entries',
        );
        if (glossaryArtifacts.confirmedTerms != null &&
            glossaryArtifacts.confirmedTerms!.isNotEmpty) {
          // Convert to simple dict format
          glossaryToApply = <String, dynamic>{};
          for (final Map<String, dynamic> term
              in glossaryArtifacts.confirmedTerms!) {
            final String src = term['src']?.toString() ?? '';
            final String dst = term['dst']?.toString() ?? '';
            if (src.isNotEmpty && dst.isNotEmpty) {
              glossaryToApply[src] = dst;
            }
          }
          _translationScreenLog(
            '[DEBUG] Prepared glossaryToApply: ${glossaryToApply.length} entries',
          );
          if (glossaryToApply.isNotEmpty) {
            final String sample = glossaryToApply.entries
                .take(3)
                .map((MapEntry<String, dynamic> e) => '${e.key}->${e.value}')
                .join(', ');
            _translationScreenLog('[DEBUG] Sample entries: $sample');
          }
        } else {
          _translationScreenLog(
            '[DEBUG] No confirmedTerms found in FlowContext glossary',
          );
        }
      } catch (e) {
        _translationScreenLog('[DEBUG] Error reading FlowContext glossary: $e');
      }
    } else {
      _translationScreenLog(
        '[DEBUG] No flowId, skipping FlowContext glossary check',
      );
    }

    // Skip LLM availability check for format-only conversion (no LLM needed)
    if (!copySourceToTargetOnly) {
      // Check if at least one LLM platform is configured and available
      final ConfigService appConfigService = ConfigService();
      final Map<String, dynamic>? appConfig =
          await appConfigService.getAppConfig();
      final Map<String, dynamic>? secretsConfig =
          await appConfigService.getSecretsConfig();
      final Map<String, dynamic>? statusMap =
          await appConfigService.getAiPlatformStatus();
      final bool hasUsableLlm =
          _hasAnyUsableLlmPlatform(appConfig, secretsConfig, statusMap);
      if (!hasUsableLlm && mounted) {
        final bool? continueAnyway =
            await _showNoLlmAvailableDialog(context);
        if (continueAnyway == null) return;
        if (continueAnyway == false) {
          if (mounted) {
            context.push('${AppRouter.settingsRoute}?tab=1');
          }
          return;
        }
      }
    }

    // Set current phase to translate when starting translation (if flowId exists)
    if (widget.flowId != null) {
      final TasksNotifier tasksNotifier = ref.read(tasksProvider.notifier);
      tasksNotifier.setPhase(widget.flowId!, PipelinePhase.translate);
    }

    notifier.setCurrentOperation(TranslationOperation.translating);
    _hasStartedTranslationInThisSession = true;
    notifier.setTranslating(true);
    notifier.setDownloads(<String, String>{});
    notifier.setDownloading('', false); // Reset downloading state
    notifier.setTaskId(null);
    notifier.setProgress(0);
    notifier.setStatusText('starting');
    notifier.setStartTime(DateTime.now());
    notifier.setEndTime(null);
    notifier.setTotalDuration(null);

    // Create translate tab immediately so progress bar and cancel button can be displayed
    // Use a temporary taskId 'pending' which will be updated once we get the real taskId
    final l10n = AppLocalizations.of(context)!;
    final String uiResultTitle =
        translationResultTitle ?? l10n.homePhaseTranslate;
    final IconData uiResultIcon =
        translationResultIcon ?? Icons.translate;
    _addTranslationResultTab(
      'pending',
      <String, String>{},
      title: uiResultTitle,
      tabId: translationResultTabId,
      tabIcon: uiResultIcon,
    );

    try {
      final ext = (state.pickedFile!.extension ?? '').toLowerCase();

      // Auto-select workflow if enabled, otherwise use manual selection or fallback
      final TranslationQuickSettings qs = widget.flowId != null
          ? ref.read(translationQuickSettingsProviderFamily(widget.flowId!))
          : ref.read(translationQuickSettingsProvider);
      final TranslationQuickSettingsNotifier qsNotifier = widget.flowId != null
          ? ref.read(
              translationQuickSettingsProviderFamily(widget.flowId!).notifier,
            )
          : ref.read(translationQuickSettingsProvider.notifier);

      // Get the expected workflow for this file extension
      final String expectedWorkflow =
          qsNotifier.selectWorkflowFromExtension(ext) ?? _extToWorkflow(ext);

      // Determine the actual workflow to use
      final String workflow = qs.autoSelectWorkflow
          ? expectedWorkflow
          : (qs.workflowType.isNotEmpty
              ? qs.workflowType
              : _extToWorkflow(ext));

      // Debug logging for workflow determination
      print('[TRANSLATION] Workflow determination: '
          'ext=$ext, '
          'autoSelectWorkflow=${qs.autoSelectWorkflow}, '
          'qs.workflowType=${qs.workflowType}, '
          'expectedWorkflow=$expectedWorkflow, '
          'final workflow=$workflow');

      // Check if workflow matches file extension and show warning if not
      if (!qs.autoSelectWorkflow && workflow != expectedWorkflow) {
        final extDisplay = ext.isEmpty ? 'unknown' : ext;
        final String workflowDisplay = _getWorkflowDisplayName(workflow);
        final String expectedWorkflowDisplay =
            _getWorkflowDisplayName(expectedWorkflow);
        if (mounted) {
          _showSnackBar(
            '⚠️ Warning: Selected workflow "$workflowDisplay" may not match file extension ".$extDisplay". Recommended: "$expectedWorkflowDisplay". Task will continue.',
            Colors.orange,
            duration: const Duration(seconds: 5),
          );
        }
      }

      // Get translation parameters from global settings
      final GlobalSettings globalSettings = ref.read(globalSettingsProvider);
      final TranslationConfigService configService = TranslationConfigService();
      final Map<String, dynamic> translationParams =
          configService.getTranslationParamsFromSettings(globalSettings);

      // Get base_url and model_id from app config (required for translation)
      final ConfigService appConfigService = ConfigService();
      final Map<String, dynamic>? appConfig =
          await appConfigService.getAppConfig();
      final Map<String, dynamic>? secretsConfig =
          await appConfigService.getSecretsConfig();

      // Get default platform info from runtime settings (reflects Quick Settings changes)
      final AIPlatformSettings aiPlatformSettings =
          ref.read(aiPlatformSettingsProvider);
      final String defaultPlatform = aiPlatformSettings.defaultPlatform;
      final AIPlatformInfo? platformInfo =
          aiPlatformSettings.platforms[defaultPlatform];
      final Map<String, dynamic> platformApiKeys =
          secretsConfig?['platform_api_keys'] as Map<String, dynamic>? ??
              <String, dynamic>{};

      // Get API key for default platform
      final String apiKey = platformApiKeys[defaultPlatform] as String? ?? '';

      // Get MinerU token if needed (for markdown_based workflow with mineru convert_engine)
      final Map<String, dynamic>? mineruTokenData =
          secretsConfig?['translator_mineru_token_meta']
              as Map<String, dynamic>?;
      final String mineruToken = mineruTokenData?['key'] as String? ?? '';

      // Convert language code to language name for backend
      final String languageName = _convertLangCodeToName(qs.toLang);

      // Get excluded segments from Extract page (if available)
      // Use flowId as primary key since it's consistent across Extract and Translate
      // taskId changes between format conversion and translation, but flowId stays the same
      // CRITICAL: Get excluded segment indices from Flow-level state
      // This ensures we use the complete set of excluded segments (including references)
      var excludedSegmentIndices = <int>{};
      try {
        // Try multiple keys to find excluded segments:
        // 1. flowId (most reliable, consistent across workflow)
        // 2. Current taskId (format conversion taskId)
        // 3. Previous taskId from translation state (if available)
        String? providerKey;
        if (widget.flowId != null) {
          providerKey = widget.flowId;
        } else if (state.taskId != null && state.taskId!.isNotEmpty) {
          providerKey = state.taskId;
        } else {
          final Object translationState = widget.flowId != null
              ? ref.read(translationStateProviderFamily(widget.flowId!))
              : ref.read(translationStateProvider);
          final String? taskIdFromState =
              (translationState as dynamic).taskId as String?;
          if (taskIdFromState != null && taskIdFromState.isNotEmpty) {
            providerKey = taskIdFromState;
          }
        }
        if (widget.flowId != null) {
          excludedSegmentIndices = ref
              .read(translationStateProviderFamily(widget.flowId!))
              .excludedSegmentIndices;
          if (excludedSegmentIndices.isNotEmpty) {
            _translationScreenLog(
              '[EXCLUDED_SEGMENTS] Found ${excludedSegmentIndices.length} excluded segments from Flow-level state: ${excludedSegmentIndices.toList()}',
              level: LogLevel.info,
            );
          }
        } else if (providerKey != null) {
          // Fallback to task-level provider if flowId is not available
          excludedSegmentIndices =
              ref.read(excludedSegmentsProviderFamily(providerKey));
          if (excludedSegmentIndices.isNotEmpty) {
            _translationScreenLog(
              '[EXCLUDED_SEGMENTS] Found ${excludedSegmentIndices.length} excluded segments using key "$providerKey": ${excludedSegmentIndices.toList()}',
              level: LogLevel.info,
            );
          }
        }
      } catch (e) {
        _translationScreenLog(
          '[EXCLUDED_SEGMENTS] Error reading excluded segments: $e',
        );
      }

      // NOTE: References (bibliography) exclusion is handled in Extract phase (extract_preview.dart)
      // The user's choice is stored in Flow-level excludedSegmentIndices state,
      // which is already read above. No need to prompt again during translation start.

      // Try to get format settings from Convert phase taskId (if available)
      // This ensures format settings are passed to Translate phase
      // Prefer format-convert task id (not copy_source_only translate task id).
      String? convertTaskId;
      if (widget.flowId != null) {
        try {
          final flowState = ref.read(flowProviderFamily(widget.flowId!));
          convertTaskId = flowState.context.translate.formatConversionTaskId ??
              flowState.context.translate.backendTaskId;
          _translationScreenLog(
            'Found Convert phase taskId from FlowState: $convertTaskId '
            '(formatConversionTaskId=${flowState.context.translate.formatConversionTaskId})',
            level: LogLevel.info,
          );
        } catch (e) {
          _translationScreenLog(
            'Failed to get Convert phase taskId from FlowState: $e',
          );
        }
      }
      // Also check current state.taskId (might be Convert phase taskId if Convert just completed)
      if ((convertTaskId == null || convertTaskId.isEmpty) &&
          state.taskId != null) {
        convertTaskId = state.taskId?.toString();
        _translationScreenLog(
          'Using current state.taskId as Convert phase taskId: $convertTaskId',
          level: LogLevel.info,
        );
      }

      String? tableFormatFromConvert;
      String? equationFormatFromConvert;
      if (convertTaskId != null && convertTaskId.isNotEmpty) {
        try {
          final formatSettings = ref.read(
            formatSettingsProviderFamily(convertTaskId),
          );
          tableFormatFromConvert = formatSettings.tableFormat;
          equationFormatFromConvert = formatSettings.equationFormat;
          if (tableFormatFromConvert != null ||
              equationFormatFromConvert != null) {
            _translationScreenLog(
              'Found format settings from Convert phase: table=$tableFormatFromConvert, equation=$equationFormatFromConvert',
              level: LogLevel.info,
            );
          }
        } catch (e) {
          // If format settings not available, try to load from backend
          try {
            final translationService = TranslationService();
            final flowSettings =
                await translationService.getFormatSettings(convertTaskId);
            tableFormatFromConvert =
                flowSettings['table_body_format'] as String?;
            equationFormatFromConvert =
                flowSettings['equation_format'] as String?;
            if (tableFormatFromConvert != null ||
                equationFormatFromConvert != null) {
              _translationScreenLog(
                'Loaded format settings from Convert phase backend: table=$tableFormatFromConvert, equation=$equationFormatFromConvert',
                level: LogLevel.info,
              );
            }
          } catch (_) {
            // Ignore errors
          }
        }
      }

      final Map<String, dynamic> payload = <String, dynamic>{
        'workflow_type': workflow,
        'from_lang': 'auto',
        'to_lang': qs.toLang,
        // Required LLM fields at top-level per backend schema
        'base_url': platformInfo?.url ??
            translationParams['base_url'] ??
            'https://api.openai.com/v1',
        'api_key': apiKey.isNotEmpty
            ? apiKey
            : (translationParams['api_key'] as String? ?? ''),
        'model_id': platformInfo?.model ??
            translationParams['model_id'] ??
            'gpt-4o',
        // Core controls expected at top-level
        // chunk_size and concurrent are now per-platform settings, read by backend from platforms.json
        // thinking is now per-platform setting (thinking_mode/thinking_mode_supported in platforms.json)
        'temperature': translationParams['temperature'],
        'timeout': platformInfo?.timeout ?? 120,
        'write_timeout': platformInfo?.writeTimeout ?? 300,
        'retry': translationParams['retry'],
        'segment_auto_retry_rounds':
            translationParams['segment_auto_retry_rounds'],
        // Platform routing (optional for backend)
        'platform_key': defaultPlatform,
        // Prompt settings from Quick Settings
        'prompt_mode': qs.promptMode,
        if (qs.promptStyle != null) 'prompt_style': qs.promptStyle,
        if (qs.taskNote != null && qs.taskNote!.isNotEmpty)
          'custom_note': qs.taskNote,
        // Keep nested params for forward compatibility (backend ignores unknown)
        'translation_params': <String, dynamic>{
          ...translationParams,
          'base_url': platformInfo?.url ??
              translationParams['base_url'] ??
              'https://api.openai.com/v1',
          'api_key': apiKey.isNotEmpty
              ? apiKey
              : (translationParams['api_key'] as String? ?? ''),
          'model_id': platformInfo?.model ??
              translationParams['model_id'] ??
              'gpt-4o',
        },
        // Do NOT send glossary_ids (backend model does not define it). Glossary selection is applied server-side.
        if (workflow == 'markdown_based') ...<String, dynamic>{
          'convert_engine': globalSettings.parsingEngine,
          'formula_ocr': globalSettings.formulaOcr,
          'table_ocr': globalSettings.tableOcr,
          'model_version': _nonEmpty(
                aiPlatformSettings.platforms[globalSettings.parsingEngine]?.model,
                (globalSettings.parsingEngine == 'paddle' || globalSettings.parsingEngine == 'paddle_local')
                    ? 'PaddleOCR-VL-1.6'
                    : 'hybrid-auto-engine',
              ),
          if (globalSettings.parsingEngine == 'mineru' &&
              mineruToken.isNotEmpty) ...<String, dynamic>{
            'mineru_token': mineruToken,
          },
        },
        if (workflow == 'qt_ts') ...<String, dynamic>{
          'skip_existing_translations': qs.qtTsSkipExistingTranslations,
          'translate_unfinished': qs.qtTsTranslateUnfinished,
          'translate_vanished': qs.qtTsTranslateVanished,
          'translate_obsolete': qs.qtTsTranslateObsolete,
        },
        // deep_split: Let backend use default from translation_config.json based on file format
        // Excluded segments from Extract page
        if (excludedSegmentIndices.isNotEmpty)
          'excluded_segments': excludedSegmentIndices.toList(),
        // Include glossary in payload if available (ensures it's available when workflow config is built)
        // Note: Backend model expects 'glossary_dict' field name, not 'glossary'
        if (glossaryToApply != null && glossaryToApply.isNotEmpty)
          'glossary_dict': glossaryToApply,
        // Include format settings from Convert phase (if available)
        // This ensures format settings are preserved when starting translation
        if (tableFormatFromConvert != null)
          'table_body_format': tableFormatFromConvert,
        if (equationFormatFromConvert != null)
          'equation_format': equationFormatFromConvert,
        // Link Translate task to Convert/Extract task so backend can reuse cached assets (e.g., images).
        if (convertTaskId != null && convertTaskId.isNotEmpty)
          'convert_task_id': convertTaskId,
        if (copySourceToTargetOnly) 'copy_source_only': true,
      };

      // Debug log: confirm whether payload actually contains convert_task_id
      _translationScreenLog(
        '[DEBUG] Payload convert_task_id: ${convertTaskId ?? '(null)'}; '
        'payloadHasKey=${payload.containsKey('convert_task_id')}',
        level: LogLevel.info,
      );

      // Log payload glossary for debugging
      if (glossaryToApply != null && glossaryToApply.isNotEmpty) {
        _translationScreenLog(
          '[DEBUG] Payload contains glossary_dict: ${payload.containsKey('glossary_dict')}, size: ${glossaryToApply.length}',
        );
        final String sample = glossaryToApply.entries
            .take(3)
            .map((MapEntry<String, dynamic> e) => '${e.key}->${e.value}')
            .join(', ');
        _translationScreenLog(
          '[DEBUG] Payload glossary_dict sample: $sample',
        );
      } else {
        _translationScreenLog(
          '[DEBUG] Payload does NOT contain glossary_dict (glossaryToApply is null or empty)',
        );
      }

      // Prepare glossary before submitting task (if available from FlowContext)
      // Note: Glossary is also included in payload above for immediate availability
      String? tempGlossaryId;
      if (glossaryToApply != null && glossaryToApply.isNotEmpty) {
        try {
          // Create a temporary glossary BEFORE submitting the task
          final String tempGlossaryName =
              'temp_${widget.flowId ?? 'glossary'}_${DateTime.now().millisecondsSinceEpoch}';
          final Map<String, dynamic> created =
              await GlossaryApiService.createEmptyGlossary(
            name: tempGlossaryName,
            isGlobal: false,
          );
          tempGlossaryId =
              (created['id'] ?? created['glossary_id'] ?? '').toString();

          if (tempGlossaryId.isNotEmpty) {
            // Import glossary entries
            final List<String> csvLines = <String>[
              'src,dst,category,target_lang',
            ];
            for (final MapEntry<String, dynamic> entry
                in glossaryToApply.entries) {
              final String src = '"${entry.key.replaceAll('"', '""')}"';
              final String dst =
                  '"${entry.value.toString().replaceAll('"', '""')}"';
              csvLines.add('$src,$dst,,');
            }
            final String csvContent = csvLines.join('\r\n');
            final Uint8List csvBytes =
                Uint8List.fromList(utf8.encode(csvContent));
            await GlossaryApiService.importCsv(
              tempGlossaryId,
              csvBytes,
            );
            _translationScreenLog(
              'Prepared temporary glossary $tempGlossaryId with ${glossaryToApply.length} entries',
            );
          }
        } catch (e) {
          // Log error but don't fail translation
          _translationScreenLog(
            'Failed to prepare glossary before task submission: $e',
          );
          tempGlossaryId = null; // Clear it so we don't try to apply it later
        }
      }

      final bytes = state.pickedFile!.bytes ??
          (await File(state.pickedFile!.path!).readAsBytes());
      // Log payload before submission for debugging
      if (excludedSegmentIndices.isNotEmpty) {
        _translationScreenLog(
          '[EXCLUDED_SEGMENTS] Submitting translation with ${excludedSegmentIndices.length} excluded segments: ${excludedSegmentIndices.toList()}',
          level: LogLevel.info,
        );
        _translationScreenLog(
          '[EXCLUDED_SEGMENTS] Payload contains excluded_segments: ${payload.containsKey('excluded_segments')}',
          level: LogLevel.info,
        );
      }

      final TranslationService svc = TranslationService();
      final Map<String, dynamic> submitResp = await svc.submitTask(
        fileBytes: bytes,
        fileName: state.pickedFile!.name,
        payload: payload,
        executionMode: widget.executionMode,
      );
      final String? taskId = submitResp['task_id']?.toString();
      if (taskId == null) {
        throw Exception('No task_id returned');
      }
      notifier.setTaskId(taskId);

      // Standalone queued submit: go to queue page without blocking on pollUntilDone.
      if (widget.executionMode == 'queued' && widget.flowId == null) {
        if (mounted) {
          final AppLocalizations l10n = AppLocalizations.of(context)!;
          MessageService.showInfo(context, l10n.translationQueuedStarted);
          _prepareFreshStandaloneQueuedSession();
          context.go(AppRouter.translationQueueRoute);
        }
        return;
      }

      // CRITICAL: Set taskId as workflowId in flow context for translation progress tracking
      // This allows ExtractPreview to detect when translation starts and switch to translation progress polling
      // Note: For translation tasks, we use taskId as workflowId (unlike anonymize tasks which have separate workflowId)
      if (widget.flowId != null) {
        try {
          final FlowStateNotifier flowNotifier =
              ref.read(flowProviderFamily(widget.flowId!).notifier);
          final FlowStateModel currentFlow =
              ref.read(flowProviderFamily(widget.flowId!));
          final AnonymizeArtifacts currentArtifacts =
              currentFlow.context.anonymize;
          // Update workflowId with taskId for translation progress tracking
          flowNotifier.setAnonymizeArtifacts(
            currentArtifacts.copyWith(workflowId: taskId),
          );
          _translationScreenLog(
            'Set workflowId=$taskId in flow context for translation progress tracking',
            level: LogLevel.info,
          );
        } catch (e) {
          _translationScreenLog(
            'Failed to set workflowId in flow context: $e',
            level: LogLevel.warn,
          );
        }
      }

      // Record task creation timestamp for ordering and diagnostics
      final DateTime taskCreatedAt = DateTime.now();

      // Update translate tab with real taskId
      _addTranslationResultTab(
        taskId,
        <String, String>{},
        title: uiResultTitle,
        tabId: translationResultTabId,
        tabIcon: uiResultIcon,
      );

      // Reload format settings from Flow state after taskId is set
      // This ensures format settings from Convert phase are loaded into Translate phase
      try {
        final formatNotifier = ref.read(
          formatSettingsProviderFamily(taskId).notifier,
        );
        // Wait a bit for backend to copy format settings from Convert phase
        await Future.delayed(const Duration(milliseconds: 500));
        await formatNotifier.reloadFromFlowState();
      } catch (e) {
        // Silently fail to avoid disrupting translation start
        _translationScreenLog(
          'Failed to reload format settings after taskId set: $e',
        );
      }

      // Apply glossary to task IMMEDIATELY after task submission (before task starts processing)
      if (tempGlossaryId != null && tempGlossaryId.isNotEmpty) {
        try {
          await GlossaryApiService.applyGlossaryToTask(tempGlossaryId, taskId);
          _translationScreenLog(
            'Applied glossary $tempGlossaryId to task $taskId immediately after submission',
          );
          if (mounted) {
            _showSnackBar('Glossary applied to translation task', Colors.green);
          }
        } catch (e) {
          // Log error but don't fail translation
          _translationScreenLog(
            'Failed to apply glossary to task immediately: $e',
          );
          if (mounted) {
            _showSnackBar(
              'Warning: Glossary not applied to task: $e',
              Colors.orange,
            );
          }
        }
      }

      // Save state to persistence after translation starts (with taskId and glossary selection)
      if (widget.flowId != null) {
        try {
          final FlowStateNotifier flowNotifier =
              ref.read(flowProviderFamily(widget.flowId!).notifier);
          final TranslationQuickSettings qs =
              ref.read(translationQuickSettingsProviderFamily(widget.flowId!));
          await flowNotifier.saveStateWithGlossaryIds(qs.selectedGlossaries);
        } catch (e) {
          _translationScreenLog(
            'Failed to save state after translation start: $e',
          );
        }
      }

      final Map<String, dynamic> statusResp = await svc.pollUntilDone(
        taskId,
        timeoutSec: 1800,
        intervalSec: 3,
        onUpdate: (Map<String, dynamic> st) async {
          final String backendStatus = (st['status'] ?? '').toString();
          final String backendMessage = (st['message'] ?? '').toString();
          notifier.setStatusText(backendMessage.isNotEmpty ? backendMessage : backendStatus);
          // Safely extract progress, handling null and invalid types
          final dynamic progressValue = st['progress'];
          final int progress = (progressValue is num)
              ? progressValue.toInt().clamp(0, 100)
              : ((progressValue is String && progressValue.isNotEmpty)
                  ? (int.tryParse(progressValue) ?? 0).clamp(0, 100)
                  : 0);
          notifier.setProgress(progress);

          // Refresh platform status if backend signals it has changed
          // (e.g. LLM connectivity test failed during translation start)
          if (!_hasRefreshedPlatformStatus &&
              st['platform_status_changed'] == true) {
            _hasRefreshedPlatformStatus = true;
            try {
              final aiPlatformNotifier =
                  ref.read(aiPlatformSettingsProvider.notifier);
              await aiPlatformNotifier.refreshPlatformStatus();
            } catch (e) {
              // Silently ignore refresh errors
            }
          }

          // Check language match warning (only once per task).
          // Skip for image files: OCR result language often matches target; warning is not useful.
          if (!_hasShownLanguageWarning && mounted) {
            final String? originalFilename = st['original_filename'] as String?;
            final bool isImageFile = _isImageFileName(originalFilename);
            final String? detectedLang = st['detected_language'] as String?;
            if (detectedLang != null &&
                detectedLang.isNotEmpty &&
                !isImageFile) {
              final TranslationQuickSettings qs = widget.flowId != null
                  ? ref.read(
                      translationQuickSettingsProviderFamily(widget.flowId!),
                    )
                  : ref.read(translationQuickSettingsProvider);
              final String targetLang = qs.toLang.toLowerCase();

              // Normalize language codes for comparison
              final String normalizedDetected =
                  _normalizeLanguageCode(detectedLang);
              final String normalizedTarget =
                  _normalizeLanguageCode(targetLang);

              if (normalizedDetected == normalizedTarget) {
                _hasShownLanguageWarning = true;
                // Show warning dialog asynchronously to avoid blocking status updates
                final String detectedLangName =
                    _convertLangCodeToName(detectedLang);
                final String targetLangName =
                    _convertLangCodeToName(targetLang);
                Future.microtask(() async {
                  if (!mounted) return;
                  await DialogHelper.showDialog<bool>(
                    context: context,
                    builder: (BuildContext context) => AlertDialog(
                      title: const Text('Language Match Warning'),
                      content: Text(
                        'The detected source language ($detectedLangName) is the same as the target language ($targetLangName). '
                        'Translation is already in progress. Please verify your language settings for future translations.',
                      ),
                      actions: <Widget>[
                        TextButton(
                          onPressed: () => Navigator.of(context).pop(true),
                          child: const Text('OK'),
                        ),
                      ],
                    ),
                  );
                  // Note: We don't cancel translation here as it's already in progress
                  // The warning is informational only
                });
              }
            }
          }

          // Update translation statistics if available
          final stats = st['translation_stats'];
          final String statusText =
              (st['status'] ?? '').toString().toLowerCase();

          if (stats != null && stats is Map) {
            // Extract token usage only when translation is completed
            Map<String, int>? tokenUsage;
            if (statusText == 'completed') {
              final tokenUsageData = st['token_usage'];
              if (tokenUsageData != null && tokenUsageData is Map) {
                tokenUsage = <String, int>{
                  'input_tokens': tokenUsageData['input_tokens'] is int
                      ? tokenUsageData['input_tokens']
                      : 0,
                  'cached_tokens': tokenUsageData['cached_tokens'] is int
                      ? tokenUsageData['cached_tokens']
                      : 0,
                  'output_tokens': tokenUsageData['output_tokens'] is int
                      ? tokenUsageData['output_tokens']
                      : 0,
                  'reasoning_tokens': tokenUsageData['reasoning_tokens'] is int
                      ? tokenUsageData['reasoning_tokens']
                      : 0,
                  'total_tokens': tokenUsageData['total_tokens'] is int
                      ? tokenUsageData['total_tokens']
                      : 0,
                };
              }
            }

            notifier.setTranslationStats(
              successCount:
                  stats['success_count'] is int ? stats['success_count'] : null,
              failCount:
                  stats['fail_count'] is int ? stats['fail_count'] : null,
              totalSegments: stats['total_segments'] is int
                  ? stats['total_segments']
                  : null,
              tokenUsage: tokenUsage,
            );
          }

          // Update end time and duration if completed
          if (statusText == 'completed' || statusText == 'failed') {
            if (!mounted) return;
            final DateTime endTime = DateTime.now();
            notifier.setEndTime(endTime);
            final currentDurationState = _getCurrentTranslationState();
            final DateTime? startTime = currentDurationState.startTime;
            if (startTime != null) {
              notifier.setTotalDuration(endTime.difference(startTime));
            }
            // Set downloads as soon as we see completed/failed so tab and Export use them
            final dynamic dv = st['downloads'];
            if (dv != null && dv is Map && dv.isNotEmpty) {
              notifier.setDownloads(
                dv.map((k, v) => MapEntry(k.toString(), v.toString())),
              );
            }
          }
        },
      );

      notifier.setTranslating(false);
      final String statusText = (statusResp['status'] ?? '').toString();
      notifier.setStatusText(statusText);
      // Safely extract progress, handling null and invalid types
      final dynamic progressValue = statusResp['progress'];
      final int progress = (progressValue is num)
          ? progressValue.toInt().clamp(0, 100)
          : ((progressValue is String && progressValue.isNotEmpty)
              ? (int.tryParse(progressValue) ?? 0).clamp(0, 100)
              : 0);
      notifier.setProgress(progress);

      // Update translation statistics from final status
      final stats = statusResp['translation_stats'];
      final String finalStatusText =
          (statusResp['status'] ?? '').toString().toLowerCase();

      if (stats != null && stats is Map) {
        // Extract token usage only when translation is completed
        Map<String, int>? tokenUsage;
        if (finalStatusText == 'completed') {
          final tokenUsageData = statusResp['token_usage'];
          if (tokenUsageData != null && tokenUsageData is Map) {
            tokenUsage = <String, int>{
              'input_tokens': tokenUsageData['input_tokens'] is int
                  ? tokenUsageData['input_tokens']
                  : 0,
              'cached_tokens': tokenUsageData['cached_tokens'] is int
                  ? tokenUsageData['cached_tokens']
                  : 0,
              'output_tokens': tokenUsageData['output_tokens'] is int
                  ? tokenUsageData['output_tokens']
                  : 0,
              'reasoning_tokens': tokenUsageData['reasoning_tokens'] is int
                  ? tokenUsageData['reasoning_tokens']
                  : 0,
              'total_tokens': tokenUsageData['total_tokens'] is int
                  ? tokenUsageData['total_tokens']
                  : 0,
            };
          }
        }

        notifier.setTranslationStats(
          successCount:
              stats['success_count'] is int ? stats['success_count'] : null,
          failCount: stats['fail_count'] is int ? stats['fail_count'] : null,
          totalSegments:
              stats['total_segments'] is int ? stats['total_segments'] : null,
          tokenUsage: tokenUsage,
        );
        // Also persist stats into FlowContext
        if (widget.flowId != null) {
          try {
            final FlowStateModel flowState =
                ref.read(flowProviderFamily(widget.flowId!));
            final FlowStateNotifier flowNotifier =
                ref.read(flowProviderFamily(widget.flowId!).notifier);
            final currentState = _getCurrentTranslationState();
            final Map<String, String> currentDownloads =
                currentState.downloads as Map<String, String>;
            final String currentTaskId =
                currentState.taskId as String? ?? taskId;
            flowNotifier.setTranslateArtifacts(
              flowState.context.translate.copyWith(
                backendTaskId: currentTaskId,
                downloads:
                    currentDownloads.isNotEmpty ? currentDownloads : null,
                stats: stats.cast<String, dynamic>(),
              ),
            );
          } catch (_) {}
        }
      }

      final DateTime endTime = DateTime.now();
      notifier.setEndTime(endTime);
      final currentStateForDuration = _getCurrentTranslationState();
      final DateTime? startTime = currentStateForDuration.startTime;
      if (startTime != null) {
        notifier.setTotalDuration(endTime.difference(startTime));
      }
      // Safely handle downloads field - may be Map, String, or null
      final downloadsValue = statusResp['downloads'];
      if (downloadsValue != null) {
        if (downloadsValue is Map) {
          notifier.setDownloads(
            downloadsValue.map((k, v) => MapEntry(k.toString(), v.toString())),
          );
          // Persist downloads to FlowContext
          if (widget.flowId != null) {
            try {
              final FlowStateModel flowState =
                  ref.read(flowProviderFamily(widget.flowId!));
              final FlowStateNotifier flowNotifier =
                  ref.read(flowProviderFamily(widget.flowId!).notifier);
              final Map<String, String> mapped = downloadsValue
                  .map((k, v) => MapEntry(k.toString(), v.toString()));
              final currentState = _getCurrentTranslationState();
              final String currentTaskId =
                  currentState.taskId as String? ?? taskId;
              flowNotifier.setTranslateArtifacts(
                flowState.context.translate.copyWith(
                  backendTaskId: currentTaskId,
                  downloads: mapped,
                ),
              );
            } catch (_) {}
          }
        } else if (downloadsValue is String) {
          // If downloads is a string (error message), log it but don't set downloads
          _translationScreenLog(
            'Downloads field is a string instead of Map: $downloadsValue',
          );
        }
      }

      final latestState = _getCurrentTranslationState();
      final downloads = Map<String, String>.from(
        latestState.downloads as Map<String, String>,
      );

      // Save state to persistence after translation completes (with downloads and task creation time)
      if (widget.flowId != null) {
        try {
          final FlowStateModel flowState =
              ref.read(flowProviderFamily(widget.flowId!));
          final FlowStateNotifier flowNotifier =
              ref.read(flowProviderFamily(widget.flowId!).notifier);
          final TranslationQuickSettings qs =
              ref.read(translationQuickSettingsProviderFamily(widget.flowId!));

          // Get current persisted state to preserve existing data
          final PersistedFlowState? currentPersisted =
              await FlowStatePersistence.loadFlowState(widget.flowId!);

          // Create updated context with translateTaskCreatedAt
          final PersistedFlowContext updatedContext =
              PersistedFlowContext.fromFlowContext(
            flowState.context,
            flowCreatedAt: currentPersisted?.createdAt ?? DateTime.now(),
            translateTaskCreatedAt:
                taskCreatedAt, // Use the task creation time we recorded
            selectedGlossaryIds: qs.selectedGlossaries,
          );

          // Create updated persisted state
          final PersistedFlowState updatedPersisted = PersistedFlowState(
            flowId: widget.flowId!,
            title: currentPersisted?.title ?? flowState.title,
            sourceType: flowState.sourceType,
            flowType: flowState.flowType,
            activePhase: flowState.activeTaskType,
            phases: flowState.phases,
            context: updatedContext,
            uiState: PersistedFlowUIState(
              activeTabIndex: currentPersisted?.uiState.activeTabIndex ?? 0,
              quickSettings: currentPersisted?.uiState.quickSettings,
              stepsState: PersistedStepsState(
                uploadCompleted: state.pickedFile != null ||
                    (_isTextMode && _textController.text.trim().isNotEmpty),
                extractCompleted: true, // Translation implies extraction
                glossaryCompleted:
                    qs.selectedGlossaries.isNotEmpty || tempGlossaryId != null,
                translateCompleted: statusText.toLowerCase() == 'completed',
                anonymizeCompleted:
                    currentPersisted?.uiState.stepsState?.anonymizeCompleted ??
                        false,
                deAnonymizeCompleted: currentPersisted
                        ?.uiState.stepsState?.deAnonymizeCompleted ??
                    false,
              ),
            ),
            createdAt: currentPersisted?.createdAt ?? DateTime.now(),
            updatedAt: DateTime.now(),
            lastAccessedAt: DateTime.now(),
          );

          await FlowStatePersistence.saveFlowState(updatedPersisted);
        } catch (e) {
          _translationScreenLog(
            'Failed to save state after translation completes: $e',
          );
        }
      }

      // Show translation result preview for both completed and failed status
      // This allows users to see translated segments even if translation failed
      if (statusText == 'completed' || statusText == 'failed') {
        if (mounted) {
          // Check for LLM platform errors (e.g., insufficient balance)
          final String? llmError = statusResp['llm_error'] is String
              ? statusResp['llm_error'] as String
              : null;
          final String statusMessage =
              (statusResp['message'] ?? '').toString();
          final bool hasLlmError = llmError != null && llmError.isNotEmpty;
          final bool isBalanceError = statusMessage.toLowerCase().contains('insufficient balance') ||
              statusMessage.toLowerCase().contains('translation failed');

          if (hasLlmError || isBalanceError) {
            final String errorMsg = llmError ?? statusMessage;
            _showSnackBar(
              errorMsg,
              Colors.red,
            );
          } else if (statusText == 'completed') {
            if (downloads.isNotEmpty) {
              _showSnackBar(
                'Translation completed. Downloads ready.',
                Colors.green,
              );
            } else {
              _showSnackBar(
                'Translation completed (may have failed segments).',
                Colors.orange,
              );
            }

            // Update translation statistics when translation completes
            if (widget.flowId != null && mounted) {
              try {
                // Try to get page count from status response or downloads
                int pageCount = 0;
                final pageCountData = statusResp['page_count'];
                if (pageCountData != null) {
                  if (pageCountData is int) {
                    pageCount = pageCountData;
                  } else if (pageCountData is String) {
                    pageCount = int.tryParse(pageCountData) ?? 0;
                  }
                }

                // Record translation flow (only once per flow)
                final statsService = TranslationStatsService();
                await statsService.recordTranslationFlow(
                  flowId: widget.flowId!,
                  pageCount: pageCount,
                );
                // Refresh statistics widget to show updated data (only if still mounted)
                if (mounted) {
                  ref.invalidate(translationStatsProvider);
                }
              } catch (e) {
                if (mounted) {
                  _translationScreenLog(
                    'Failed to update translation statistics: $e',
                  );
                }
              }
            }
          } else {
            // Failed status - still show what was translated
            _showSnackBar(
              'Translation failed, but partial results are available.',
              Colors.orange,
            );
          }
        }
        // Add translation result preview tab even if downloads is empty or failed
        // The preview can load segments from API, including partial results
        _addTranslationResultTab(
          taskId,
          downloads,
          title: uiResultTitle,
          tabId: translationResultTabId,
          tabIcon: uiResultIcon,
        );

        if (statusText == 'completed' &&
            widget.executionMode != 'queued' &&
            !_autoPersistedQueueTaskIds.contains(taskId)) {
          _autoPersistedQueueTaskIds.add(taskId);
          unawaited(_persistQueueSnapshotAuto(taskId));
        }

        // Automatically switch to Review phase after translation completes (or fails)
        if (widget.flowId != null) {
          final TasksNotifier tasksNotifier = ref.read(tasksProvider.notifier);
          tasksNotifier.setPhase(widget.flowId!, PipelinePhase.review);
        }
      } else {
        if (mounted) {
          _showSnackBar('Task status: $statusText', Colors.blue);
        }
      }
    } catch (e) {
      notifier.setTranslating(false);
      notifier.setStatusText('failed');
      if (mounted) {
        _showSnackBar('Translation failed: $e', Colors.red);
      }
    } finally {
      notifier.setTranslating(false);
      notifier.setCurrentOperation(TranslationOperation.none);
    }
  }

  /// Picks taskId for format settings: state.taskId, or taskId parsed from download URL path.
  String? _taskIdForFormat(String url, state) {
    if (state.taskId != null && (state.taskId as String).isNotEmpty) {
      return state.taskId as String?;
    }
    // e.g. /service/download/{taskId}/pdf
    final List<String> segs = Uri.parse(url).pathSegments;
    if (segs.length >= 4 && segs[1] == 'download') {
      return segs[2];
    }
    return null;
  }

  Future<void> _downloadFile(
    String fileType,
    String url,
    state,
    notifier, {
    bool isConvertDownload = false,
  }) async {
    if (state.downloading[fileType] == true) return; // Already downloading

    // URL (including any format settings) is built by caller widgets.
    // Keep this method free of ref.read to avoid using Riverpod ref after
    // this widget is disposed.
    final String finalUrl = url;

    notifier.setDownloading(fileType, true);
    if (mounted) {
      _showSnackBar('Export task has been started, please wait.', Colors.blue);
    }

    try {
      final TranslationService svc = TranslationService();
      final List<int> bytes = await svc.downloadFile(finalUrl);

      // Check if this is MD with images folder (embed_images=false)
      // In this case, backend returns a ZIP file, so we need to use .zip extension
      final Uri uri = Uri.parse(finalUrl);
      final String? embedImagesParam = uri.queryParameters['embed_images'];
      final bool isMdWithImagesFolder = fileType.toLowerCase() == 'md' &&
          embedImagesParam != null &&
          embedImagesParam.toLowerCase() == 'false';

      // Generate filename with configurable suffix
      final originalName = state.pickedFile?.name ??
          widget.reeditFileName ??
          'translated';
      final String suffix = isConvertDownload
          ? ref.read(globalSettingsProvider).convertOutputSuffix
          : ref.read(globalSettingsProvider).translateOutputSuffix;
      final String actualFileType = isMdWithImagesFolder ? 'zip' : fileType;
      final String filename = buildDownloadFilename(
        originalName: originalName,
        extension: actualFileType,
        suffix: suffix,
      );
      final String baseName = filename.endsWith('.$actualFileType')
          ? filename.substring(0, filename.length - actualFileType.length - 1)
          : filename;

      // Save file
      if (kIsWeb) {
        // Web: use FileSaver
        // For MD with images folder, use ZIP mime type
        final MimeType mimeType =
            isMdWithImagesFolder ? MimeType.zip : _getMimeTypeEnum(fileType);
        await FileSaver.instance.saveFile(
          name: baseName,
          bytes: Uint8List.fromList(bytes),
          ext: actualFileType,
          mimeType: mimeType,
        );
        if (mounted) {
          _showSnackBar('File downloaded: $filename', Colors.green);
        }
      } else {
        // Desktop: use FilePicker to save
        final String? path = await FilePicker.platform.saveFile(
          dialogTitle: isConvertDownload
              ? 'Save Converted File'
              : 'Save Translated File',
          fileName: filename,
          type: FileType.custom,
          allowedExtensions: <String>[actualFileType],
        );
        if (path != null) {
          final File file = File(path);
          await file.writeAsBytes(bytes, flush: true);
          if (mounted) {
            _showSnackBar('File saved: $filename', Colors.green);
          }
        }
      }
    } catch (e) {
      if (mounted) {
        String message = 'Failed to download $fileType: $e';
        // Prefer backend-provided detail (e.g. LaTeX compile hint with segment index)
        // over the generic DioException text.
        if (e is DioException) {
          final dynamic data = e.response?.data;
          if (data is Map && data['detail'] is String) {
            message = data['detail'] as String;
          } else if (data is List<int> && data.isNotEmpty) {
            // When download uses ResponseType.bytes, backend JSON errors come back as raw bytes.
            try {
              final String text = utf8.decode(data, allowMalformed: true).trim();
              if (text.isNotEmpty) {
                final dynamic parsed = jsonDecode(text);
                if (parsed is Map && parsed['detail'] is String) {
                  message = parsed['detail'] as String;
                }
              }
            } catch (_) {
              // keep default message
            }
          } else if (data is String) {
            // Some endpoints may return plain text; still show it when meaningful.
            final String s = data.trim();
            if (s.isNotEmpty && s.length <= 2000) {
              message = s;
            }
          }
        }
        // If backend didn't provide a concrete segment index, show a helpful hint.
        if (!message.contains('Suspected bad segment') &&
            !message.contains('segment') &&
            fileType.toLowerCase() == 'pdf') {
          message =
              '$message\nHint: If the segment index is not available, the issue is likely in a mixed text+LaTeX segment (formula/table).';
        }
        _showSnackBar(message, Colors.red);
      }
    } finally {
      notifier.setDownloading(fileType, false);
    }
  }

  MimeType _getMimeTypeEnum(String fileType) {
    switch (fileType.toLowerCase()) {
      case 'docx':
        return MimeType.microsoftWord;
      case 'pdf':
        return MimeType.pdf;
      case 'html':
      case 'txt':
      case 'md':
      case 'epub':
      case 'mobi':
      case 'azw':
      case 'ts':
        return MimeType.other;
      default:
        return MimeType.other;
    }
  }

  // Deprecated: Keep for backward compatibility (used in glossary generation)
  Future<void> _openDownload(String url) async {
    final dynamic state = widget.flowId != null
        ? ref.read(translationStateProviderFamily(widget.flowId!))
        : ref.read(translationStateProvider);
    final dynamic notifier = widget.flowId != null
        ? ref.read(translationStateProviderFamily(widget.flowId!).notifier)
        : ref.read(translationStateProvider.notifier);

    // Try to extract file type from URL if possible
    final Uri uri = Uri.parse(url);
    final List<String> segments = uri.pathSegments;
    if (segments.isNotEmpty && segments.last.isNotEmpty) {
      // URL format: /service/download/taskId/fileType
      final String fileType = segments.last;
      // Find matching download entry
      for (final entry in state.downloads.entries) {
        if (entry.value.contains(fileType)) {
          await _downloadFile(entry.key, url, state, notifier);
          return;
        }
      }
    }

    // Fallback: try to open as URL
    String fullUrl;
    if (url.startsWith('http://') || url.startsWith('https://')) {
      fullUrl = url;
    } else {
      // 确保相对路径以 / 开头
      final String normalizedPath = url.startsWith('/') ? url : '/$url';
      fullUrl = '${AppConfig.baseUrl}$normalizedPath';
    }
    final Uri uriFull = Uri.parse(fullUrl);
    if (!await launchUrl(uriFull, mode: LaunchMode.externalApplication)) {
      if (mounted) {
        _showSnackBar('Failed to open download: $url', Colors.red);
      }
    }
  }

  String _extToWorkflow(String ext) {
    switch (ext) {
      case 'txt':
        return 'txt';
      case 'md':
        return 'markdown_based';
      case 'json':
        return 'json';
      case 'arb':
        return 'json';
      case 'xlsx':
        return 'xlsx';
      case 'srt':
        return 'srt';
      case 'epub':
        return 'epub';
      case 'mobi':
      case 'azw':
        return 'mobi';
      case 'html':
        return 'html';
      case 'ts':
        return 'qt_ts';
      case 'docx':
        return 'docx';
      case 'pptx':
        return 'pptx';
      default:
        return 'markdown_based';
    }
  }

  String _getWorkflowDisplayName(String workflow) {
    switch (workflow) {
      case 'txt':
        return 'Plain Text';
      case 'markdown_based':
        return 'Markdown-based';
      case 'json':
        return 'JSON';
      case 'xlsx':
        return 'XLSX';
      case 'docx':
        return 'DOCX';
      case 'pptx':
        return 'PPTX';
      case 'html':
        return 'HTML';
      case 'srt':
        return 'SRT';
      case 'epub':
        return 'EPUB';
      case 'mobi':
        return 'MOBI';
      case 'qt_ts':
        return 'Qt .ts';
      default:
        return workflow;
    }
  }

  String _removeFileExtension(String fileName) {
    final int dotIndex = fileName.lastIndexOf('.');
    if (dotIndex <= 0) {
      return fileName;
    }
    return fileName.substring(0, dotIndex);
  }

  dynamic _getCurrentTranslationState() => widget.flowId != null
      ? ref.read(translationStateProviderFamily(widget.flowId!))
      : ref.read(translationStateProvider);

  Widget _buildPreviewPanel(state) {
    final PreviewTabsState tabsState = widget.flowId != null
        ? ref.watch(previewTabsProviderFamily(widget.flowId!))
        : ref.watch(previewTabsProvider);
    final dynamic translationNotifier = widget.flowId != null
        ? ref.read(translationStateProviderFamily(widget.flowId!).notifier)
        : ref.read(translationStateProvider.notifier);

    // Check if file selection should be disabled
    final dynamic translationState = widget.flowId != null
        ? ref.read(translationStateProviderFamily(widget.flowId!))
        : ref.read(translationStateProvider);
    final bool hasTask = translationState.taskId != null &&
        (translationState.taskId as String).isNotEmpty;
    final isTranslating = translationState.isTranslating;
    final bool isOperationInProgress =
        translationState.currentOperation != TranslationOperation.none;
    final bool isFileSelectionDisabled =
        hasTask || isTranslating || isOperationInProgress || _isReeditMode;

    // Build empty state widget
    Widget? emptyStateWidget;
    if (tabsState.tabs.isEmpty) {
      // In re-edit mode, the tab is created asynchronously; show a loading
      // indicator instead of the file upload area during the brief gap.
      if (_isReeditMode) {
        emptyStateWidget = const Center(child: CircularProgressIndicator());
      } else if (_isTextMode) {
        emptyStateWidget = TextInputArea(
          flowId: widget.flowId,
          controller: _textController,
          onCancelTask: () => _cancelCurrentTask(translationNotifier),
        );
      } else {
        emptyStateWidget = FileUploadArea(
          isDisabled: isFileSelectionDisabled,
          supportedFormats:
              'Supported: ${_fileFormatService.getSupportedFormatsDisplayString()}',
          onTap: kIsWeb
              ? () async {
                  // Web: Call picker IMMEDIATELY - no method calls, no checks, nothing before this
                  // Inline extensions list to avoid any potential issues with instance variable access
                  FilePickerResult? result;
                  try {
                    // Allow all supported formats in picker; Pro-only show hint in _processFile if not activated
                    final availableFormats = _getAllFileExtensions();
                    result = await FilePickerHelper.pickFiles(
                      type: FileType.custom,
                      allowedExtensions: availableFormats,
                      withData: true,
                    );
                  } catch (e, stackTrace) {
                    _translationScreenLog(
                      'File picker exception: $e\n$stackTrace',
                      level: LogLevel.error,
                    );
                    if (mounted) {
                      _showSnackBar(
                        'File selection error: ${e.toString()}. Please try again.',
                        Colors.red,
                      );
                    }
                    return;
                  }
                  // Now safe to check result and process
                  if (!mounted) return;
                  if (result == null) {
                    _translationScreenLog(
                      'File picker returned null. This could mean:\n'
                      '  1. User cancelled the file selection dialog\n'
                      '  2. Browser security policy blocked file access\n'
                      '  3. File picker dialog failed to open\n'
                      '  4. File was too large or inaccessible',
                      level: LogLevel.warn,
                    );
                    if (mounted) {
                      _showSnackBar(
                        'File selection was cancelled or blocked. Please drag and drop the file instead.',
                        Colors.orange,
                      );
                    }
                    return;
                  }
                  if (result.files.isEmpty) {
                    _translationScreenLog(
                      'File picker returned empty files',
                      level: LogLevel.warn,
                    );
                    if (mounted) {
                      _showSnackBar(
                        'No file was selected. Please try again.',
                        Colors.orange,
                      );
                    }
                    return;
                  }
                  final PlatformFile file = result.files.first;
                  // On Web, file.path is unavailable and accessing it causes an exception
                  // Only check path on non-Web platforms
                  String? filePathStr;
                  if (!kIsWeb) {
                    try {
                      filePathStr = file.path;
                    } catch (e) {
                      filePathStr = null;
                    }
                  }
                  _translationScreenLog(
                      'File selected: name=${file.name}, size=${file.size}, '
                      'hasBytes=${file.bytes != null}, hasPath=${filePathStr != null}');
                  if (file.bytes == null) {
                    _translationScreenLog(
                      'ERROR: file.bytes is null on Web! File may be too large or inaccessible.',
                      level: LogLevel.error,
                    );
                    if (mounted) {
                      _showSnackBar(
                        'File data not available. The file may be too large. Please try a smaller file or check browser console for errors.',
                        Colors.red,
                      );
                    }
                    return;
                  }
                  // Set operation state and process file
                  translationNotifier
                      .setCurrentOperation(TranslationOperation.importing);
                  await _processFile(file, translationNotifier);
                }
              : () => _pickFile(translationNotifier),
          onFileDropped: (PlatformFile file) =>
              _handleDroppedFile(file, translationNotifier),
          onCancel: isFileSelectionDisabled
              ? () => _cancelCurrentTask(translationNotifier)
              : null,
          disabledMessage: 'File selection disabled (extraction in progress)',
        );
      }
    }

    // Use PreviewPanel but handle glossary tab closing specially
    return PreviewPanel(
      flowId: widget.flowId,
      emptyState: emptyStateWidget,
      onTabCloseConfirm: _confirmTranslateTabCloseIfNeeded,
      onTabClose: (PreviewTab tab) async {
        // Check if closing glossary tab
        if (tab.type.toString().endsWith('glossary')) {
          setState(() {
            _glossarySkipped = true;
            _isGlossaryEditing =
                false; // Reset editing state when glossary tab is closed
          });
        }

        // IMPORTANT: Do NOT release task resources when closing the Translate tab.
        // Users may close the translation result tab and go back to Extract to adjust
        // target language or exclusions. Releasing the task here would make subsequent
        // operations (status / update-excluded-segments) fail with 404.
      },
    );
  }

  void _addTranslationResultTab(
    String taskId,
    Map<String, String> downloads, {
    String? title,
    String tabId = 'translate_tab',
    IconData tabIcon = Icons.translate,
    String? overrideFileName,
    String? overrideWorkflowType,
  }) {
    final l10n = AppLocalizations.of(context)!;
    final PreviewTabsNotifier tabsNotifier = widget.flowId != null
        ? ref.read(previewTabsProviderFamily(widget.flowId!).notifier)
        : ref.read(previewTabsProvider.notifier);
    final dynamic state = widget.flowId != null
        ? ref.read(translationStateProviderFamily(widget.flowId!))
        : ref.read(translationStateProvider);
    final dynamic notifier = widget.flowId != null
        ? ref.read(translationStateProviderFamily(widget.flowId!).notifier)
        : ref.read(translationStateProvider.notifier);

    // Get file name from picked file, with override for re-edit mode
    final String? fileName = overrideFileName ?? state.pickedFile?.name;
    // Extract just the filename without path for display
    final displayFileName = fileName != null
        ? (kIsWeb ? fileName : fileName.split('/').last.split(r'\').last)
        : null;

    // Create preview - it will automatically load content from downloads
    // Use taskId as key to ensure widget is properly updated when taskId changes
    final TranslationQuickSettings currentSettings = widget.flowId != null
        ? ref.read(translationQuickSettingsProviderFamily(widget.flowId!))
        : ref.read(translationQuickSettingsProvider);
    final TranslationResultPreview previewContent = TranslationResultPreview(
      key: ValueKey('translation_result_$taskId'),
      taskId: taskId,
      flowId: widget.flowId,
      downloads: downloads,
      onDownload: (String fileType, String url) =>
          _downloadFile(fileType, url, state, notifier),
      onTranslationWorkspaceMutation: _markQueuePersistDirty,
      fileName: displayFileName,
      isTextMode: _isTextMode,
      workflowType: overrideWorkflowType ?? currentSettings.workflowType,
      initialMergedView: widget.viewMode == 'clean',
    );

    final PreviewTab tab = PreviewTab(
      id: tabId,
      type: PreviewTabType.translationResult,
      title: title ?? l10n.homePhaseTranslate,
      icon: tabIcon,
      content: previewContent,
      dataRef: <String, dynamic>{
        'taskId': taskId,
        'downloads': downloads,
        'fileName': displayFileName,
        'flowId': widget.flowId,
        'isTextMode': _isTextMode,
        'workflowType': overrideWorkflowType ?? currentSettings.workflowType,
        'viewMode': widget.viewMode,
      },
    );

    tabsNotifier.updateOrAddTab(tab);
  }

  /// Opens a Translate tab for re-editing a completed task.
  /// Uses re-edit override params since there is no picked file.
  /// Also updates the translation state so toolbar buttons (Retry, Translate All) become active.
  /// Restores original task parameters from the backend payload so the re-edit form reflects
  /// the user's original settings (target language, workflow type, prompt, etc.).
  void _addReeditTranslationResultTab() {
    final AppLocalizations l10n = AppLocalizations.of(context)!;
    final String taskId = widget.reeditTaskId!;

    // Set taskId and completed status so toolbar buttons (Retry, Translate All)
    // become visible and clickable in reedit/view mode.
    final dynamic notifier = widget.flowId != null
        ? ref.read(translationStateProviderFamily(widget.flowId!).notifier)
        : ref.read(translationStateProvider.notifier);
    notifier.setTaskId(taskId);
    notifier.setProgress(100);
    notifier.setStatusText('completed');

    // Get quick settings notifier for restoring original task params
    final dynamic qsNotifier = widget.flowId != null
        ? ref.read(translationQuickSettingsProviderFamily(widget.flowId!).notifier)
        : ref.read(translationQuickSettingsProvider.notifier);

    // Show a loading indicator while fetching task data
    final Map<String, String> downloads = <String, String>{};

    // Fetch downloads from backend status on-demand
    TranslationService()
        .getStatus(taskId)
        .then((Map<String, dynamic> status) {
      final dynamic dv = status['downloads'];
      if (dv is Map && dv.isNotEmpty) {
        downloads.addAll(
            dv.map((k, v) => MapEntry(k.toString(), v.toString())));
      }

      // Restore original task parameters (target language, workflow type, prompt, etc.)
      final dynamic taskParams = status['task_params'];
      if (taskParams is Map<String, dynamic> && taskParams.isNotEmpty) {
        qsNotifier.restoreFromTaskParams(taskParams);
      }
    }).catchError((Object e) {
      // Ignore; proceed with empty downloads
    }).whenComplete(() {
      if (!mounted) return;
      _addTranslationResultTab(
        taskId,
        downloads,
        title: l10n.reeditTitle,
        tabId: 'translate_reedit_tab',
        tabIcon: Icons.edit,
        overrideFileName: widget.reeditFileName,
        overrideWorkflowType: widget.reeditWorkflowType,
      );
    });
  }

  /// Open or switch to Glossary tab
  void _openGlossaryTab(state, notifier) {
    final PreviewTabsNotifier tabsNotifier = widget.flowId != null
        ? ref.read(previewTabsProviderFamily(widget.flowId!).notifier)
        : ref.read(previewTabsProvider.notifier);
    final PreviewTabsState tabsState = widget.flowId != null
        ? ref.read(previewTabsProviderFamily(widget.flowId!))
        : ref.read(previewTabsProvider);

    // Check if Glossary tab already exists
    const String glossaryTabId = 'glossary_tab';
    final int existingIndex =
        tabsState.tabs.indexWhere((PreviewTab t) => t.id == glossaryTabId);

    if (existingIndex >= 0) {
      // Tab exists, switch to it
      tabsNotifier.switchToTab(existingIndex);
      return;
    }

    // Tab doesn't exist, create a new one
    // Get glossary data from FlowContext if available, otherwise empty
    final Map<String, dynamic> glossaryData = <String, dynamic>{};
    if (widget.flowId != null) {
      try {
        final FlowStateModel flowState =
            ref.read(flowProviderFamily(widget.flowId!));
        final GlossaryArtifacts glossaryArtifacts = flowState.context.glossary;
        if (glossaryArtifacts.confirmedTerms != null &&
            glossaryArtifacts.confirmedTerms!.isNotEmpty) {
          for (final Map<String, dynamic> term
              in glossaryArtifacts.confirmedTerms!) {
            final String src = term['src']?.toString() ?? '';
            final String dst = term['dst']?.toString() ?? '';
            if (src.isNotEmpty && dst.isNotEmpty) {
              glossaryData[src] = dst;
            }
          }
        }
      } catch (_) {}
    }

    // Get target language from Quick Settings for the glossary
    final TranslationQuickSettings qs = widget.flowId != null
        ? ref.read(translationQuickSettingsProviderFamily(widget.flowId!))
        : ref.read(translationQuickSettingsProvider);
    final String targetLang = _convertLangCodeToName(qs.toLang);

    final GlossaryPreview previewContent = GlossaryPreview(
      glossaryId: glossaryTabId,
      glossaryData: glossaryData,
      flowId: widget.flowId,
      targetLang: targetLang,
      onGenerateGlossary: () => _onGenerateGlossary(state, notifier),
      onCancelGlossary: () => _cancelGlossaryGeneration(notifier),
      onSave: (Map<String, dynamic> updatedGlossary) {
        // Save callback (glossary will be auto-applied to FlowContext if flowId is set)
        if (mounted) {
          _showSnackBar('Glossary saved and applied', Colors.green);
        }
      },
      onEditingStateChanged: (bool isEditing) {
        // Update glossary editing state to disable/enable translate button
        if (mounted) {
          setState(() {
            _isGlossaryEditing = isEditing;
          });
        }
      },
    );

    final PreviewTab tab = PreviewTab(
      id: glossaryTabId,
      type: PreviewTabType.glossary,
      title: AppLocalizations.of(context)!.homePhaseGlossary,
      icon: Icons.book,
      content: previewContent,
      dataRef: <String, dynamic>{
        'glossaryData': glossaryData,
        'flowId': widget.flowId,
        'targetLang': targetLang,
      },
    );

    tabsNotifier.updateOrAddTab(tab);
  }

  void _addGlossaryTab(Map<String, dynamic> glossaryData) {
    debugPrint(
      '[TRANSLATION_SCREEN] _addGlossaryTab called with ${glossaryData.length} entries',
    );
    debugPrint(
      '[TRANSLATION_SCREEN] GlossaryData type: ${glossaryData.runtimeType}',
    );
    debugPrint(
      '[TRANSLATION_SCREEN] GlossaryData keys (first 5): ${glossaryData.keys.take(5).toList()}',
    );

    final PreviewTabsNotifier tabsNotifier = widget.flowId != null
        ? ref.read(previewTabsProviderFamily(widget.flowId!).notifier)
        : ref.read(previewTabsProvider.notifier);

    // Auto-apply glossary immediately when generated
    if (widget.flowId != null) {
      try {
        final FlowStateNotifier flowNotifier =
            ref.read(flowProviderFamily(widget.flowId!).notifier);
        final List<Map<String, String>> terms = glossaryData.entries
            .map(
              (MapEntry<String, dynamic> e) => <String, String>{
                'src': e.key.toString(),
                'dst': e.value.toString(),
              },
            )
            .toList();
        flowNotifier.setGlossaryArtifacts(
          GlossaryArtifacts(terms: terms, confirmedTerms: terms),
        );
        debugPrint(
          '[TRANSLATION_SCREEN] Applied ${terms.length} terms to FlowContext',
        );
      } catch (e) {
        debugPrint(
          '[TRANSLATION_SCREEN] Error applying glossary to FlowContext: $e',
        );
      }
    }
    setState(() {
      _glossarySkipped = false;
    }); // Reset skip flag when glossary is generated

    // Get target language from Quick Settings for the glossary
    final TranslationQuickSettings qs = widget.flowId != null
        ? ref.read(translationQuickSettingsProviderFamily(widget.flowId!))
        : ref.read(translationQuickSettingsProvider);
    final String targetLang = _convertLangCodeToName(qs.toLang);

    // Use fixed ID for Glossary tab
    const String glossaryId = 'glossary_tab';

    final dynamic translationState = widget.flowId != null
        ? ref.read(translationStateProviderFamily(widget.flowId!))
        : ref.read(translationStateProvider);
    final dynamic translationNotifier = widget.flowId != null
        ? ref.read(translationStateProviderFamily(widget.flowId!).notifier)
        : ref.read(translationStateProvider.notifier);

    debugPrint(
      '[TRANSLATION_SCREEN] Creating GlossaryPreview with ${glossaryData.length} entries, targetLang=$targetLang',
    );

    final GlossaryPreview previewContent = GlossaryPreview(
      glossaryId: glossaryId,
      glossaryData: glossaryData,
      flowId: widget.flowId,
      targetLang: targetLang,
      onGenerateGlossary: () =>
          _onGenerateGlossary(translationState, translationNotifier),
      onCancelGlossary: () => _cancelGlossaryGeneration(translationNotifier),
      onSave: (Map<String, dynamic> updatedGlossary) {
        // Save callback (glossary will be auto-applied to FlowContext if flowId is set)
        if (mounted) {
          _showSnackBar('Glossary saved and applied', Colors.green);
        }
      },
      onEditingStateChanged: (bool isEditing) {
        // Update glossary editing state to disable/enable translate button
        if (mounted) {
          setState(() {
            _isGlossaryEditing = isEditing;
          });
        }
      },
    );

    // Ensure glossaryData is properly converted to a regular Map for persistence
    // Convert from any Map type (e.g., IdentityMap) to a regular Map
    final Map<String, dynamic> glossaryDataForRef = <String, dynamic>{};
    glossaryData.forEach((String key, value) {
      glossaryDataForRef[key.toString()] = value;
    });
    debugPrint(
      '[TRANSLATION_SCREEN] _addGlossaryTab: Converted glossaryData to regular Map: ${glossaryDataForRef.length} entries',
    );
    debugPrint(
      '[TRANSLATION_SCREEN] _addGlossaryTab: First 3 keys: ${glossaryDataForRef.keys.take(3).toList()}',
    );

    final PreviewTab tab = PreviewTab(
      id: glossaryId,
      type: PreviewTabType.glossary,
      title: AppLocalizations.of(context)!.homePhaseGlossary,
      icon: Icons.book,
      content: previewContent,
      dataRef: <String, dynamic>{
        'glossaryData': glossaryDataForRef,
        'flowId': widget.flowId,
        'targetLang': targetLang,
      },
    );

    // Check if tab already exists before adding
    final PreviewTabsState tabsStateBefore = widget.flowId != null
        ? ref.read(previewTabsProviderFamily(widget.flowId!))
        : ref.read(previewTabsProvider);
    final int existingIndex =
        tabsStateBefore.tabs.indexWhere((PreviewTab t) => t.id == glossaryId);
    debugPrint(
      '[TRANSLATION_SCREEN] Before updateOrAddTab: existingIndex=$existingIndex, total tabs=${tabsStateBefore.tabs.length}, activeTabIndex=${tabsStateBefore.activeTabIndex}',
    );
    debugPrint(
      '[TRANSLATION_SCREEN] Before updateOrAddTab: all tabs=${tabsStateBefore.tabs.map((PreviewTab t) => '${t.id}(${t.type})').toList()}',
    );

    tabsNotifier.updateOrAddTab(tab);
    debugPrint(
      '[TRANSLATION_SCREEN] Glossary tab added: id=$glossaryId, type=${tab.type}',
    );

    // Verify tab was added by reading state immediately after
    final PreviewTabsState tabsStateAfter = widget.flowId != null
        ? ref.read(previewTabsProviderFamily(widget.flowId!))
        : ref.read(previewTabsProvider);
    final int tabIndexAfter =
        tabsStateAfter.tabs.indexWhere((PreviewTab t) => t.id == glossaryId);
    debugPrint(
      '[TRANSLATION_SCREEN] Tab verification after add: found at index=$tabIndexAfter, total tabs=${tabsStateAfter.tabs.length}, activeTabIndex=${tabsStateAfter.activeTabIndex}',
    );
    debugPrint(
      '[TRANSLATION_SCREEN] All tabs after add: ${tabsStateAfter.tabs.map((PreviewTab t) => '${t.id}(${t.type})').toList()}',
    );

    // Note: updateOrAddTab should automatically switch to the tab if it exists or was just added
    // But we'll still call _switchToGlossaryTab as a safety measure
  }

  /// Switch to glossary tab after adding it
  void _switchToGlossaryTab() {
    final PreviewTabsNotifier tabsNotifier = widget.flowId != null
        ? ref.read(previewTabsProviderFamily(widget.flowId!).notifier)
        : ref.read(previewTabsProvider.notifier);
    final PreviewTabsState tabsState = widget.flowId != null
        ? ref.read(previewTabsProviderFamily(widget.flowId!))
        : ref.read(previewTabsProvider);

    debugPrint(
      '[TRANSLATION_SCREEN] _switchToGlossaryTab: current tabs count=${tabsState.tabs.length}, activeTabIndex=${tabsState.activeTabIndex}',
    );
    debugPrint(
      '[TRANSLATION_SCREEN] _switchToGlossaryTab: all tabs=${tabsState.tabs.map((PreviewTab t) => '${t.id}(${t.type})').toList()}',
    );

    const String glossaryTabId = 'glossary_tab';
    final int tabIndex =
        tabsState.tabs.indexWhere((PreviewTab t) => t.id == glossaryTabId);

    if (tabIndex >= 0) {
      debugPrint(
        '[TRANSLATION_SCREEN] Switching to glossary tab at index $tabIndex (current activeTabIndex=${tabsState.activeTabIndex})',
      );
      tabsNotifier.switchToTab(tabIndex);

      // Verify switch was successful
      WidgetsBinding.instance.addPostFrameCallback((_) {
        final PreviewTabsState tabsStateAfterSwitch = widget.flowId != null
            ? ref.read(previewTabsProviderFamily(widget.flowId!))
            : ref.read(previewTabsProvider);
        debugPrint(
          '[TRANSLATION_SCREEN] After switch: activeTabIndex=${tabsStateAfterSwitch.activeTabIndex}, expected=$tabIndex',
        );
        if (tabsStateAfterSwitch.activeTabIndex != tabIndex) {
          debugPrint(
            '[TRANSLATION_SCREEN] WARNING: Tab switch may have failed! Expected index=$tabIndex, but activeTabIndex=${tabsStateAfterSwitch.activeTabIndex}',
          );
        }
      });
    } else {
      debugPrint(
        '[TRANSLATION_SCREEN] WARNING: Glossary tab not found after adding, current tabs: ${tabsState.tabs.map((PreviewTab t) => '${t.id}(${t.type})').toList()}',
      );
    }
  }

  void _addExtractTab(String taskId) {
    final PreviewTabsNotifier tabsNotifier = widget.flowId != null
        ? ref.read(previewTabsProviderFamily(widget.flowId!).notifier)
        : ref.read(previewTabsProvider.notifier);

    final ExtractPreview content = ExtractPreview(
      taskId: taskId,
      flowId: widget.flowId,
    );
    // Use fixed ID for Extract tab
    final PreviewTab tab = PreviewTab(
      id: 'extract_tab',
      type: PreviewTabType.translationResult, // reuse type for tab behavior
      title: AppLocalizations.of(context)!.homePhaseExtract,
      icon: Icons.fact_check,
      content: content,
      dataRef: <String, dynamic>{
        'taskId': taskId,
        'flowId': widget.flowId,
      },
    );
    tabsNotifier.updateOrAddTab(tab);

    // After ensuring the Extract tab exists/updated, switch to it so that
    // users always see the Extract preview immediately after importing
    // a document, regardless of which tab was previously active.
    final List<PreviewTab> currentTabs = widget.flowId != null
        ? ref.read(previewTabsProviderFamily(widget.flowId!)).tabs
        : ref.read(previewTabsProvider).tabs;
    final int tabIndex =
        currentTabs.indexWhere((PreviewTab t) => t.id == 'extract_tab');
    if (tabIndex >= 0) {
      tabsNotifier.switchToTab(tabIndex);
    }
  }

  void _addFormatConversionTab(String taskId, Map<String, String> downloads) {
    final PreviewTabsNotifier tabsNotifier = widget.flowId != null
        ? ref.read(previewTabsProviderFamily(widget.flowId!).notifier)
        : ref.read(previewTabsProvider.notifier);
    final dynamic state = widget.flowId != null
        ? ref.read(translationStateProviderFamily(widget.flowId!))
        : ref.read(translationStateProvider);
    final dynamic notifier = widget.flowId != null
        ? ref.read(translationStateProviderFamily(widget.flowId!).notifier)
        : ref.read(translationStateProvider.notifier);

    // Create format conversion preview with progress widget
    final ConvertProgressWidget previewContent = ConvertProgressWidget(
      taskId: taskId,
      flowId: widget.flowId,
      downloads: downloads,
      onDownload: (String fileType, String url) => _downloadFile(
        fileType,
        url,
        state,
        notifier,
        isConvertDownload: true,
      ),
    );

    // Use fixed ID for Convert tab
    final PreviewTab tab = PreviewTab(
      id: 'convert_tab',
      type: PreviewTabType.formatConversion,
      title: 'Convert',
      icon: Icons.transform,
      content: previewContent,
      dataRef: <String, dynamic>{
        'taskId': taskId,
        'downloads': downloads,
        'flowId': widget.flowId,
      },
    );

    tabsNotifier.updateOrAddTab(tab);

    // Switch to the Convert tab after creating/updating it
    // This ensures users can see the progress even if window is minimized
    final List<PreviewTab> currentTabs = widget.flowId != null
        ? ref.read(previewTabsProviderFamily(widget.flowId!)).tabs
        : ref.read(previewTabsProvider).tabs;
    final int tabIndex =
        currentTabs.indexWhere((PreviewTab t) => t.id == 'convert_tab');
    if (tabIndex >= 0) {
      tabsNotifier.switchToTab(tabIndex);
    }
  }

  bool _isMineruAuthError(String? message) {
    if (message == null) return false;
    final String lower = message.toLowerCase();
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
    const String instruction =
        'MinerU parsing engine requires a valid Token. Please open Settings -> AI Platform -> MinerU to configure it.';
    _showSnackBar(
      instruction,
      Colors.orange,
      duration: const Duration(seconds: 4),
    );

    if (!_hasShownMineruTokenPrompt && mounted) {
      _hasShownMineruTokenPrompt = true;
      await showDialog(
        context: context,
        builder: (BuildContext dialogContext) => AlertDialog(
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

  /// Update excluded segments for target language
  /// Called when target language changes
  Future<void> _updateExcludedSegmentsForLanguage(
    String taskId,
    String targetLang,
  ) async {
    if (_isUpdatingExcluded) {
      return; // Already updating, skip
    }

    setState(() {
      _isUpdatingExcluded = true;
    });

    try {
      final TranslationService svc = TranslationService();

      // CRITICAL: Check if task has segments ready before updating excluded segments
      // If Extract is still in progress, segments may not be available yet
      try {
        final Map<String, dynamic> status = await svc.getStatus(taskId);
        final String? taskStatus = status['status'] as String?;
        final Map<String, dynamic>? sourcePreview =
            status['source_preview'] as Map<String, dynamic>?;
        final bool previewReady = sourcePreview?['ready'] as bool? ?? false;
        final int totalSegments = sourcePreview?['total_segments'] as int? ?? 0;

        // Check if Extract is still in progress or segments are not ready
        if (taskStatus == 'processing' ||
            taskStatus == 'pending' ||
            !previewReady ||
            totalSegments == 0) {
          _translationScreenLog(
            '[UPDATE-EXCLUDED] Extract still in progress (status=$taskStatus, ready=$previewReady, segments=$totalSegments). '
            'Skipping excluded segments update. Will retry when Extract completes.',
            level: LogLevel.warn,
          );
          // Don't show error to user - this is expected during Extract phase
          return;
        }
      } catch (e) {
        // If status check fails, log but continue (may be transient error)
        _translationScreenLog(
          '[UPDATE-EXCLUDED] Failed to check task status before updating excluded segments: $e',
          level: LogLevel.warn,
        );
        // Continue anyway - API call will handle the error
      }

      Map<String, dynamic> detectionResult;
      try {
        // Step 1: First call API in detection mode (autoExclude=false) to check for language-matched segments
        detectionResult = await svc.updateExcludedSegmentsForLanguage(
          taskId,
          targetLang,
        );
      } on DioException catch (e) {
        // If task has been released or not found, backend returns 404.
        // In this case, silently skip update to avoid confusing the user.
        final int? statusCode = e.response?.statusCode;
        if (statusCode == 404) {
          _translationScreenLog(
            '[UPDATE-EXCLUDED] Task not found (possibly released), skipping excluded segments update for taskId=$taskId, targetLang=$targetLang',
            level: LogLevel.warn,
          );
          return;
        }
        rethrow;
      }

      final bool requiresConfirmation =
          detectionResult['requires_confirmation'] as bool? ?? false;
      final List<dynamic>? languageMatchedSegments =
          detectionResult['language_matched_segments'] as List<dynamic>?;
      final int languageMatchedCount =
          detectionResult['language_matched_count'] as int? ?? 0;

      // Step 2: If there are language-matched segments, check if user has already made a choice
      bool shouldExclude = false;
      final bool? previousChoice = _languageExclusionChoices[targetLang];

      if (requiresConfirmation &&
          languageMatchedSegments != null &&
          languageMatchedSegments.isNotEmpty) {
        // Check if user has already made a choice for this target language
        if (previousChoice != null) {
          // User has already made a choice, use it without showing dialog
          shouldExclude = previousChoice;
          _translationScreenLog(
            '[UPDATE-EXCLUDED] Using previous choice for target_lang=$targetLang: exclude=$shouldExclude',
          );
        } else {
          // No previous choice, show confirmation dialog
          final String targetLangName = _convertLangCodeToName(targetLang);
          final bool? confirmed = await showDialog<bool>(
            context: context,
            builder: (BuildContext context) => AlertDialog(
              title: const Text('Language Match Detection'),
              content: SingleChildScrollView(
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: <Widget>[
                    Text(
                      'Found $languageMatchedCount segment(s) that match the target language ($targetLangName). '
                      'These segments will not be translated as they are already in the target language.',
                      style: const TextStyle(fontSize: 14),
                    ),
                    const SizedBox(height: 16),
                    const Text(
                      'Sample segments:',
                      style:
                          TextStyle(fontWeight: FontWeight.bold, fontSize: 14),
                    ),
                    const SizedBox(height: 8),
                    ...languageMatchedSegments.take(5).map<Widget>((segment) {
                      final int index = segment['index'] as int? ?? 0;
                      final String preview =
                          segment['preview'] as String? ?? '';
                      return Padding(
                        padding: const EdgeInsets.symmetric(vertical: 4),
                        child: Text(
                          'Segment $index: $preview',
                          style: const TextStyle(
                            fontSize: 12,
                            fontStyle: FontStyle.italic,
                          ),
                        ),
                      );
                    }),
                    if (languageMatchedCount > 5)
                      Text(
                        '... and ${languageMatchedCount - 5} more segment(s)',
                        style: const TextStyle(
                          fontSize: 12,
                          fontStyle: FontStyle.italic,
                        ),
                      ),
                    const SizedBox(height: 16),
                    const Text(
                      'Do you want to exclude these segments from translation?',
                      style:
                          TextStyle(fontWeight: FontWeight.bold, fontSize: 14),
                    ),
                  ],
                ),
              ),
              actions: <Widget>[
                TextButton(
                  onPressed: () => Navigator.of(context).pop(false),
                  child: const Text('No'),
                ),
                TextButton(
                  onPressed: () => Navigator.of(context).pop(true),
                  style: TextButton.styleFrom(
                    foregroundColor: Theme.of(context).colorScheme.primary,
                  ),
                  child: const Text('Yes, Exclude'),
                ),
              ],
            ),
          );

          shouldExclude = confirmed ?? false;
          // Remember user's choice for this target language
          _languageExclusionChoices[targetLang] = shouldExclude;
          // Persist user's choice to SharedPreferences
          await _saveLanguageExclusionChoices();
          _translationScreenLog(
            '[UPDATE-EXCLUDED] User choice for target_lang=$targetLang: exclude=$shouldExclude (saved for future)',
          );
        }
      }

      // Step 3: Process based on user choice
      if (shouldExclude || !requiresConfirmation) {
        // User confirmed or no confirmation needed - exclude language-matched segments
        final Map<String, dynamic> result =
            await svc.updateExcludedSegmentsForLanguage(
          taskId,
          targetLang,
          autoExclude: true,
        );

        final int excludedCount = result['excluded_count'] as int? ?? 0;
        final int totalSegments = result['total_segments'] as int? ?? 0;

        _translationScreenLog(
          '[UPDATE-EXCLUDED] Updated excluded segments for target_lang=$targetLang: '
          '$excludedCount excluded out of $totalSegments total segments',
        );

        if (mounted) {
          if (requiresConfirmation && shouldExclude) {
            MessageService.showInfo(
              context,
              'Excluded $excludedCount segment(s) that match the target language "$targetLang"',
            );
          } else if (!requiresConfirmation) {
            MessageService.showInfo(
              context,
              'Updated excluded segments: $excludedCount out of $totalSegments segments excluded for target language "$targetLang"',
            );
          }

          // Trigger refresh of TranslationResultPreview to update excluded labels
          triggerTranslationRefresh(ref);
          // CRITICAL: Also trigger Extract page refresh to update excluded labels
          triggerExtractRefresh(ref);
        }
      } else {
        // User chose not to exclude - clear language-based exclusions
        // The detectionResult already contains only non-language-based exclusions
        // We need to ensure backend state is updated with this (it should already be updated from detection call)
        // But we should refresh UI to reflect the cleared state

        _translationScreenLog(
          '[UPDATE-EXCLUDED] User chose not to exclude language-matched segments. '
          'Clearing language-based exclusions (keeping non-language exclusions).',
        );

        if (mounted) {
          // The detectionResult call (autoExclude=false) already updated backend with only non-language exclusions
          // We just need to refresh UI to show the updated state
          final int excludedCount =
              detectionResult['excluded_count'] as int? ?? 0;
          final int totalSegments =
              detectionResult['total_segments'] as int? ?? 0;

          MessageService.showInfo(
            context,
            'Cleared language-based exclusions. $excludedCount non-language segment(s) remain excluded out of $totalSegments total segments.',
          );

          // Trigger refresh of TranslationResultPreview to update excluded labels
          triggerTranslationRefresh(ref);
          // CRITICAL: Also trigger Extract page refresh to update excluded labels
          triggerExtractRefresh(ref);
        }
      }
    } catch (e) {
      // Check if error is due to Extract still in progress (404 with "No segments found")
      final bool isExtractInProgress = e.toString().contains('404') &&
          (e.toString().contains('No segments found') ||
              e.toString().contains('completed extraction'));

      if (isExtractInProgress) {
        // Extract is still in progress - this is expected, don't show error to user
        _translationScreenLog(
          '[UPDATE-EXCLUDED] Extract still in progress, segments not ready yet. '
          'Will retry when Extract completes. Error: $e',
          level: LogLevel.warn,
        );
        // Don't show error message to user - this is expected behavior
      } else {
        // Other errors - log and show to user
        _translationScreenLog(
          '[UPDATE-EXCLUDED] Failed to update excluded segments: $e',
          level: LogLevel.error,
        );
        if (mounted) {
          MessageService.showError(
            context,
            'Failed to update excluded segments: $e',
          );
        }
      }
    } finally {
      if (mounted) {
        setState(() {
          _isUpdatingExcluded = false;
        });
      }
    }
  }

  void _showSnackBar(String message, Color color, {Duration? duration}) {
    // Check if widget is still mounted before showing message
    if (!mounted) return;

    // Use unified MessageService for all messages
    // Error messages use longer duration so user has time to read
    if (color == Colors.red || color == Colors.red.shade700) {
      MessageService.showError(
        context,
        message,
        duration: duration ?? const Duration(seconds: 10),
      );
    } else if (color == Colors.green || color == Colors.green.shade700) {
      MessageService.showSuccess(context, message, duration: duration);
    } else if (color == Colors.orange || color == Colors.orange.shade700) {
      MessageService.showWarning(context, message, duration: duration);
    } else if (color == Colors.blue || color == Colors.blue.shade700) {
      MessageService.showInfo(context, message, duration: duration);
    } else {
      MessageService.showMessage(
        context,
        message,
        color: color,
        duration: duration,
      );
    }
  }

  /// Format language distribution as "Lang1: X%, Lang2: Y%, ..." sorted by percentage descending.
  String _formatLanguageDistributionSorted(
      Map<String, double> languageDistribution,) {
    final sortedEntries = languageDistribution.entries.toList()
      ..sort(
        (MapEntry<String, double> a, MapEntry<String, double> b) =>
            b.value.compareTo(a.value),
      );
    return sortedEntries.map((MapEntry<String, double> e) {
      final String langName = _convertLangCodeToName(e.key);
      return '$langName: ${(e.value * 100).toStringAsFixed(1)}%';
    }).join(', ');
  }

  /// Show multilingual prompt dialog and update Quick Settings
  Future<bool?> _showMultilingualPromptDialog(
    String detectedLanguage,
    Map<String, double> languageDistribution,
  ) async {
    final l10n = AppLocalizations.of(context)!;
    var option1Selected = false;
    var option2Selected = false;

    return DialogHelper.showDialog<bool>(
      context: context,
      builder: (BuildContext context) => StatefulBuilder(
        builder: (BuildContext context, setState) => AlertDialog(
          title: Text(l10n.translationDialogMixedLangTitle),
          content: SingleChildScrollView(
            child: Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.start,
              children: <Widget>[
                Text(
                  l10n.translationDialogMixedLangContent(
                    _formatLanguageDistributionSorted(languageDistribution),
                  ),
                  style: const TextStyle(fontSize: 14),
                ),
                const SizedBox(height: 16),
                Text(
                  l10n.translationDialogMixedLangPromptTitle,
                  style: const TextStyle(
                    fontWeight: FontWeight.bold,
                    fontSize: 14,
                  ),
                ),
                const SizedBox(height: 12),
                // Option 1: Only translate text in source language
                CheckboxListTile(
                  title: Text(
                    l10n.translationDialogMixedLangOption1Title,
                  ),
                  subtitle: Text(
                    l10n.translationDialogMixedLangOption1Subtitle(
                      _convertLangCodeToName(detectedLanguage),
                    ),
                    style: const TextStyle(fontSize: 12),
                  ),
                  value: option1Selected,
                  onChanged: (bool? value) {
                    setState(() {
                      option1Selected = value ?? false;
                    });
                  },
                  contentPadding: EdgeInsets.zero,
                ),
                // Option 2: Keep code and technical terms unchanged
                CheckboxListTile(
                  title: Text(
                    l10n.translationDialogMixedLangOption2Title,
                  ),
                  subtitle: Text(
                    l10n.translationDialogMixedLangOption2Subtitle,
                    style: const TextStyle(fontSize: 12),
                  ),
                  value: option2Selected,
                  onChanged: (bool? value) {
                    setState(() {
                      option2Selected = value ?? false;
                    });
                  },
                  contentPadding: EdgeInsets.zero,
                ),
              ],
            ),
          ),
          actions: <Widget>[
            TextButton(
              onPressed: () => Navigator.of(context).pop(),
              child: Text(l10n.translationDialogMixedLangCancel),
            ),
            TextButton(
              onPressed: () => Navigator.of(context).pop(false),
              child: Text(l10n.translationDialogMixedLangSkip),
            ),
            TextButton(
              onPressed: () {
                if (option1Selected || option2Selected) {
                  _updateCustomPromptFromOptions(
                    option1Selected: option1Selected,
                    option2Selected: option2Selected,
                    sourceLanguage: detectedLanguage,
                  );
                }
                Navigator.of(context).pop(true);
              },
              child: Text(l10n.translationDialogMixedLangApply),
            ),
          ],
        ),
      ),
    );
  }

  /// Update custom prompt in Quick Settings based on selected options
  void _updateCustomPromptFromOptions({
    required bool option1Selected,
    required bool option2Selected,
    required String sourceLanguage,
  }) {
    final TranslationQuickSettingsNotifier qsNotifier = widget.flowId != null
        ? ref.read(
            translationQuickSettingsProviderFamily(widget.flowId!).notifier,
          )
        : ref.read(translationQuickSettingsProvider.notifier);

    final List<String> promptParts = <String>[];

    if (option1Selected) {
      promptParts.add('Only translate text in $sourceLanguage language.');
    }

    if (option2Selected) {
      promptParts.add(
        'Keep code blocks, technical terms, function names, and text in other languages unchanged.',
      );
    }

    if (promptParts.isNotEmpty) {
      final String customPrompt = promptParts.join(' ');
      // Enable advanced prompt mode and set taskNote
      qsNotifier.updatePromptMode('advanced');
      qsNotifier.updateTaskNote(customPrompt);
      if (mounted) {
        _showSnackBar('Prompt instructions updated', Colors.green);
      }
    }
  }
}

/// Dialog widget for selecting glossary detection mode and action
class _GlossaryDetectionDialog extends StatefulWidget {
  const _GlossaryDetectionDialog({
    required this.hasEntries,
    required this.entriesCount,
  });
  final bool hasEntries;
  final int entriesCount;

  @override
  State<_GlossaryDetectionDialog> createState() =>
      _GlossaryDetectionDialogState();
}

class _GlossaryDetectionDialogState extends State<_GlossaryDetectionDialog> {
  String selectedMode = 'uncertain'; // Default to uncertain mode
  String actionMode = 'replace'; // Default to replace: 'replace' or 'merge'

  @override
  Widget build(BuildContext context) => AlertDialog(
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
                onChanged: (value) {
                  if (value != null) {
                    setState(() {
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
                onChanged: (value) {
                  if (value != null) {
                    setState(() {
                      selectedMode = value;
                    });
                  }
                },
              ),
              // Show replace/merge option if glossary has entries
              if (widget.hasEntries) ...<Widget>[
                const SizedBox(height: 24),
                const Divider(),
                const SizedBox(height: 8),
                Text(
                  'Current glossary has ${widget.entriesCount} entries. Choose action:',
                  style: const TextStyle(
                    fontSize: 14,
                    fontWeight: FontWeight.bold,
                  ),
                ),
                const SizedBox(height: 16),
                RadioListTile<String>(
                  title: const Text(
                    'Replace Current Glossary',
                    style: TextStyle(fontWeight: FontWeight.bold),
                  ),
                  subtitle: const Text(
                    'Replace the current glossary with the newly detected terms. '
                    'All existing entries will be removed.',
                    style: TextStyle(fontSize: 12),
                  ),
                  value: 'replace',
                  groupValue: actionMode,
                  onChanged: (value) {
                    if (value != null) {
                      setState(() {
                        actionMode = value;
                      });
                    }
                  },
                ),
                const SizedBox(height: 8),
                RadioListTile<String>(
                  title: const Text(
                    'Merge with Current Glossary',
                    style: TextStyle(fontWeight: FontWeight.bold),
                  ),
                  subtitle: const Text(
                    'Merge the newly detected terms with the current glossary. '
                    'Existing entries will be updated if duplicates are found.',
                    style: TextStyle(fontSize: 12),
                  ),
                  value: 'merge',
                  groupValue: actionMode,
                  onChanged: (value) {
                    if (value != null) {
                      setState(() {
                        actionMode = value;
                      });
                    }
                  },
                ),
              ],
            ],
          ),
        ),
        actions: <Widget>[
          TextButton(
            onPressed: () {
              Navigator.of(context).pop();
            },
            child: const Text('Cancel'),
          ),
          ElevatedButton(
            onPressed: () {
              Navigator.of(context).pop(<String, String>{
                'mode': selectedMode,
                'action': actionMode,
              });
            },
            child: const Text('Continue'),
          ),
        ],
      );
}
