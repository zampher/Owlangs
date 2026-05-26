import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:flutter/foundation.dart' show kIsWeb;
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import '../../../l10n/app_localizations.dart';
import 'package:shared_preferences/shared_preferences.dart';
import '../../../app/app_router.dart';
import '../../../shared/services/config_service.dart';
import '../../../shared/services/translation_service.dart';
import '../../../shared/providers/settings_provider.dart';
import '../../../shared/providers/admin_permissions_provider.dart';
import '../../../shared/providers/auth_provider.dart';
import '../../../shared/widgets/admin_required_dialog.dart';
import '../../../widgets/ad_placeholder.dart' show AdPlaceholder, AdType;
import '../../settings/screens/ai_platform_settings.dart';
import '../models/preview_tab.dart';
import '../providers/translation_state_provider_family.dart';
import '../providers/preview_tabs_provider.dart';

// 翻译快速设置状态管理
final StateNotifierProvider<TranslationQuickSettingsNotifier,
        TranslationQuickSettings> translationQuickSettingsProvider =
    StateNotifierProvider<TranslationQuickSettingsNotifier,
        TranslationQuickSettings>(
  (
    StateNotifierProviderRef<TranslationQuickSettingsNotifier, TranslationQuickSettings> ref,
  ) =>
      TranslationQuickSettingsNotifier(),
);

final StateNotifierProviderFamily<TranslationQuickSettingsNotifier,
        TranslationQuickSettings, String>
    translationQuickSettingsProviderFamily = StateNotifierProvider.family<
        TranslationQuickSettingsNotifier, TranslationQuickSettings, String>((
  StateNotifierProviderRef<TranslationQuickSettingsNotifier, TranslationQuickSettings> ref,
  String flowId,
) {
  // Keep provider alive to avoid reloading when switching flows
  ref.keepAlive();
  return TranslationQuickSettingsNotifier(flowId: flowId);
});

class TranslationQuickSettings {
  const TranslationQuickSettings({
    this.sourceLang = 'auto',
    this.toLang = 'en',
    this.workflowType = 'docx',
    this.usePrompt = false,
    this.selectedGlossaries = const <String>[],
    this.glossarySelectorExpanded = true, // Default: expanded
    this.promptMode = 'off',
    this.promptStyle,
    this.taskNote,
    this.autoSelectWorkflow = true, // Default: enable auto-select
    this.qtTsSkipExistingTranslations = true,
    this.qtTsTranslateUnfinished = true,
    this.qtTsTranslateVanished = true,
    this.qtTsTranslateObsolete = true,
    this.deepSplit = true,
    this.temperature,
  });

  factory TranslationQuickSettings.fromJson(Map<String, dynamic> json) =>
      TranslationQuickSettings(
        sourceLang: json['sourceLang'] ?? 'auto',
        toLang: json['toLang'] ?? 'zh',
        workflowType: json['workflowType'] ?? 'docx',
        selectedGlossaries:
            List<String>.from(json['selectedGlossaries'] ?? <dynamic>[]),
        glossarySelectorExpanded:
            json['glossarySelectorExpanded'] ?? true, // Default: expanded
        promptMode: json['promptMode'] ?? 'off',
        promptStyle: json['promptStyle'],
        taskNote: json['taskNote'],
        autoSelectWorkflow: json['autoSelectWorkflow'] ?? true,
        qtTsSkipExistingTranslations:
            json['qtTsSkipExistingTranslations'] ?? true,
        qtTsTranslateUnfinished: json['qtTsTranslateUnfinished'] ?? true,
        qtTsTranslateVanished: json['qtTsTranslateVanished'] ?? true,
        qtTsTranslateObsolete: json['qtTsTranslateObsolete'] ?? true,
        deepSplit: json['deepSplit'] ?? true,
        temperature: json['temperature'] != null
            ? (json['temperature'] as num).toDouble()
            : null,
      );
  final String sourceLang;
  final String toLang;
  final String workflowType;
  final bool usePrompt;
  final List<String> selectedGlossaries;
  final bool glossarySelectorExpanded;
  final String promptMode; // off | simple | advanced
  final String?
      promptStyle; // literal | fluent | academic | business | technical
  final String? taskNote;
  final bool autoSelectWorkflow; // Auto-select workflow based on file extension

  // Qt .ts specific settings
  final bool qtTsSkipExistingTranslations;
  final bool qtTsTranslateUnfinished;
  final bool qtTsTranslateVanished;
  final bool qtTsTranslateObsolete;
  final bool deepSplit;

  // Temperature setting (null means use platform default)
  final double? temperature;

  TranslationQuickSettings copyWith({
    String? sourceLang,
    String? toLang,
    String? workflowType,
    bool? usePrompt,
    List<String>? selectedGlossaries,
    bool? glossarySelectorExpanded,
    String? promptMode,
    String? promptStyle,
    String? taskNote,
    bool? autoSelectWorkflow,
    bool? qtTsSkipExistingTranslations,
    bool? qtTsTranslateUnfinished,
    bool? qtTsTranslateVanished,
    bool? qtTsTranslateObsolete,
    bool? deepSplit,
    double? temperature,
  }) =>
      TranslationQuickSettings(
        sourceLang: sourceLang ?? this.sourceLang,
        toLang: toLang ?? this.toLang,
        workflowType: workflowType ?? this.workflowType,
        usePrompt: usePrompt ?? this.usePrompt,
        selectedGlossaries: selectedGlossaries ?? this.selectedGlossaries,
        glossarySelectorExpanded:
            glossarySelectorExpanded ?? this.glossarySelectorExpanded,
        promptMode: promptMode ?? this.promptMode,
        promptStyle: promptStyle ?? this.promptStyle,
        taskNote: taskNote ?? this.taskNote,
        autoSelectWorkflow: autoSelectWorkflow ?? this.autoSelectWorkflow,
        qtTsSkipExistingTranslations:
            qtTsSkipExistingTranslations ?? this.qtTsSkipExistingTranslations,
        qtTsTranslateUnfinished:
            qtTsTranslateUnfinished ?? this.qtTsTranslateUnfinished,
        qtTsTranslateVanished:
            qtTsTranslateVanished ?? this.qtTsTranslateVanished,
        qtTsTranslateObsolete:
            qtTsTranslateObsolete ?? this.qtTsTranslateObsolete,
        deepSplit: deepSplit ?? this.deepSplit,
        temperature: temperature ?? this.temperature,
      );

  Map<String, dynamic> toJson() => <String, dynamic>{
        'sourceLang': sourceLang,
        'toLang': toLang,
        'workflowType': workflowType,
        'selectedGlossaries': selectedGlossaries,
        'glossarySelectorExpanded': glossarySelectorExpanded,
        'promptMode': promptMode,
        'promptStyle': promptStyle,
        'taskNote': taskNote,
        'autoSelectWorkflow': autoSelectWorkflow,
        'qtTsSkipExistingTranslations': qtTsSkipExistingTranslations,
        'qtTsTranslateUnfinished': qtTsTranslateUnfinished,
        'qtTsTranslateVanished': qtTsTranslateVanished,
        'qtTsTranslateObsolete': qtTsTranslateObsolete,
        'deepSplit': deepSplit,
        if (temperature != null) 'temperature': temperature,
      };
}

class TranslationQuickSettingsNotifier
    extends StateNotifier<TranslationQuickSettings> {
  TranslationQuickSettingsNotifier({this.flowId})
      : super(const TranslationQuickSettings()) {
    _loadSettings();
  }
  final String? flowId;

  Future<void> _loadSettings() async {
    try {
      final SharedPreferences prefs = await SharedPreferences.getInstance();
      final keysToCheck = <String>[
        if (flowId != null) 'translation_quick_settings_$flowId',
        'translation_quick_settings',
      ];

      for (final String key in keysToCheck) {
        final String? settingsJson = prefs.getString(key);
        if (settingsJson != null) {
          final Map<String, dynamic> settingsMap =
              jsonDecode(settingsJson) as Map<String, dynamic>;
          final loadedSettings = TranslationQuickSettings.fromJson(settingsMap);
          // Force autoSelectWorkflow to true to ensure automatic workflow selection
          state = loadedSettings.copyWith(autoSelectWorkflow: true);
          return;
        }
      }
    } catch (e) {
      // If loading fails, use default settings
      print('Error loading translation quick settings: $e');
    }
  }

  Future<void> _saveSettings() async {
    try {
      final SharedPreferences prefs = await SharedPreferences.getInstance();
      final String settingsJson = jsonEncode(state.toJson());
      const String globalKey = 'translation_quick_settings';
      final String? flowKey =
          flowId != null ? 'translation_quick_settings_$flowId' : null;

      if (flowKey != null) {
        await prefs.setString(flowKey, settingsJson);
      }
      await prefs.setString(globalKey, settingsJson);
    } catch (e) {
      print('Error saving translation quick settings: $e');
    }
  }

  void updateToLang(String toLang, {String? taskId}) {
    final String oldLang = state.toLang;

    // CRITICAL: Log language change for debugging
    print(
        '[TranslationQuickSettings] updateToLang called: oldLang=$oldLang, newLang=$toLang, taskId=$taskId',);

    state = state.copyWith(toLang: toLang);
    _saveSettings();

    // CRITICAL: Immediately send target language to backend if taskId is available
    // This ensures MinerU processing uses the latest target language
    // This is especially important for PDF files where MinerU processing takes a long time
    if (oldLang != toLang && taskId != null && taskId.isNotEmpty) {
      print(
          '[TranslationQuickSettings] Language changed from $oldLang to $toLang, sending to backend for task=$taskId',);
      // Send target language to backend immediately (fire and forget)
      // This ensures backend has the latest target language for MinerU processing
      _sendTargetLangToBackend(taskId, toLang);
    } else {
      print(
          '[TranslationQuickSettings] Language change skipped: oldLang==newLang=${oldLang == toLang}, taskId=${taskId?.isNotEmpty ?? false}',);
    }
  }

  /// Update source language (used as MinerU OCR language hint for markdown_based workflows).
  void updateSourceLang(String sourceLang) {
    state = state.copyWith(sourceLang: sourceLang);
    _saveSettings();
  }

  /// Send target language to backend immediately
  /// This ensures MinerU processing uses the latest target language
  Future<void> _sendTargetLangToBackend(
      String taskId, String targetLang,) async {
    try {
      final TranslationService svc = TranslationService();
      // Call API in detection mode (autoExclude=false) to update target language
      // This will store target_lang in segments_metadata.last_target_lang_for_language_match
      await svc.updateExcludedSegmentsForLanguage(
        taskId,
        targetLang,
      );
      print(
          '[TranslationQuickSettings] Successfully sent target_lang=$targetLang to backend for task=$taskId',);
    } catch (e) {
      // Log error but don't block UI - this is a background update
      print(
          '[TranslationQuickSettings] Failed to send target_lang to backend: $e',);
    }
  }

  void updateWorkflowType(String workflowType) {
    // Update workflow type even when auto-select is enabled
    // This allows the dropdown to display the correct selected value
    state = state.copyWith(workflowType: workflowType);
    _saveSettings();
  }

  void updateAutoSelectWorkflow(bool autoSelectWorkflow) {
    state = state.copyWith(autoSelectWorkflow: autoSelectWorkflow);
    _saveSettings();
  }

  void updateUsePrompt(bool usePrompt) {
    state = state.copyWith(usePrompt: usePrompt);
  }

  /// Auto-select workflow type based on file extension
  String? selectWorkflowFromExtension(String? fileExtension) {
    if (fileExtension == null || fileExtension.isEmpty) return null;

    final String ext = fileExtension.toLowerCase().replaceAll('.', '');
    switch (ext) {
      case 'txt':
        return 'txt';
      case 'md':
      case 'pdf':
      case 'png':
      case 'jpg':
      case 'jpeg':
        return 'markdown_based';
      case 'json':
      case 'arb':
        return 'json';
      case 'xlsx':
      case 'xls':
      case 'csv':
        return 'xlsx';
      case 'srt':
        return 'srt';
      case 'epub':
        return 'epub';
      case 'mobi':
      case 'azw':
        return 'mobi';
      case 'html':
      case 'htm':
        return 'html';
      case 'ts':
        return 'qt_ts';
      case 'docx':
      case 'doc':
        return 'docx';
      case 'pptx':
        return 'pptx';
      default:
        return 'markdown_based'; // Default fallback
    }
  }

  void updatePromptMode(String mode) {
    state = state.copyWith(promptMode: mode);
    _saveSettings();
    _persistPromptPrefs();
  }

  void updatePromptStyle(String? style) {
    state = state.copyWith(promptStyle: style);
    _saveSettings();
    _persistPromptPrefs();
  }

  void updateTaskNote(String? note) {
    state = state.copyWith(taskNote: note);
    _saveSettings();
    _persistPromptPrefs();
  }

  Future<void> _persistPromptPrefs() async {
    try {
      final SharedPreferences sp = await SharedPreferences.getInstance();
      final String toLang = state.toLang;
      await sp.setString('prompt_mode_$toLang', state.promptMode);
      if (state.promptStyle != null) {
        await sp.setString('prompt_style_$toLang', state.promptStyle!);
      }
      if (state.taskNote != null) {
        await sp.setString('prompt_note_$toLang', state.taskNote!);
      }
    } catch (_) {
      // ignore persistence errors
    }
  }

  void updateSelectedGlossaries(List<String> selectedGlossaries) {
    state = state.copyWith(selectedGlossaries: selectedGlossaries);
    _saveSettings();
  }

  void toggleGlossary(String glossaryId) {
    final List<String> current = List<String>.from(state.selectedGlossaries);
    if (current.contains(glossaryId)) {
      current.remove(glossaryId);
    } else {
      current.add(glossaryId);
    }
    state = state.copyWith(selectedGlossaries: current);
  }

  /// Restore settings from backend task_params (used when entering reedit mode).
  /// Maps backend payload field names to frontend quick settings.
  void restoreFromTaskParams(Map<String, dynamic> params) {
    final String? toLang = params['to_lang'] as String?;
    final String? workflowType = params['workflow_type'] as String?;
    final String? promptMode = params['prompt_mode'] as String?;
    final String? promptStyle = params['prompt_style'] as String?;
    final String? taskNote = params['custom_note'] as String?;
    final bool? deepSplit = params['deep_split'] as bool?;
    final double? temperature = params['temperature'] != null
        ? (params['temperature'] as num).toDouble()
        : null;

    state = state.copyWith(
      toLang: toLang,
      workflowType: workflowType,
      promptMode: promptMode,
      promptStyle: promptStyle,
      taskNote: taskNote,
      deepSplit: deepSplit,
      temperature: temperature,
      autoSelectWorkflow: false, // Preserve the original workflow, don't auto-detect
    );
    _saveSettings();
  }

  void reset() {
    state = const TranslationQuickSettings();
  }

  // Qt .ts specific settings update methods
  void updateQtTsSkipExistingTranslations(bool value) {
    state = state.copyWith(qtTsSkipExistingTranslations: value);
    _saveSettings();
  }

  void updateQtTsTranslateUnfinished(bool value) {
    state = state.copyWith(qtTsTranslateUnfinished: value);
    _saveSettings();
  }

  void updateQtTsTranslateVanished(bool value) {
    state = state.copyWith(qtTsTranslateVanished: value);
    _saveSettings();
  }

  void updateQtTsTranslateObsolete(bool value) {
    state = state.copyWith(qtTsTranslateObsolete: value);
    _saveSettings();
  }

  // Removed: updateDeepSplit - Deep split is now always enabled, no need to update

  /// Update temperature and sync to platform configuration
  /// Note: This method should be called from Widget context with WidgetRef
  Future<void> updateTemperature(
    double temperature,
    AIPlatformSettingsNotifier aiPlatformNotifier,
    String currentPlatform,
    AIPlatformInfo? platformInfo,
  ) async {
    state = state.copyWith(temperature: temperature);
    _saveSettings();

    // Sync to platform configuration
    if (platformInfo != null) {
      try {
        // Update platform temperature
        final AIPlatformInfo updatedPlatform = platformInfo.copyWith(
          temperature: temperature,
        );
        await aiPlatformNotifier.updatePlatformConfig(
          currentPlatform,
          updatedPlatform,
        );
      } catch (e) {
        print('Error syncing temperature to platform config: $e');
      }
    }
  }

  /// Update temperature from platform configuration (called when platform changes)
  void updateTemperatureFromPlatform(
    AIPlatformInfo platformInfo,
  ) {
    // Only update if current temperature is null or different from platform
    if (state.temperature == null ||
        (state.temperature! - platformInfo.temperature).abs() > 0.01) {
      state = state.copyWith(temperature: platformInfo.temperature);
      _saveSettings();
    }
  }
}

/// Flags for whether the active tab allows editing target language (Extract / Glossary).
class _TabLanguageFlags {
  const _TabLanguageFlags({required this.extract, required this.glossary});
  final bool extract;
  final bool glossary;
  @override
  bool operator ==(Object other) =>
      identical(this, other) ||
      other is _TabLanguageFlags &&
          extract == other.extract &&
          glossary == other.glossary;
  @override
  int get hashCode => Object.hash(extract, glossary);
}

class TranslationQuickSettingsWidget extends ConsumerWidget {
  const TranslationQuickSettingsWidget({super.key, this.flowId});
  final String? flowId;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final TranslationQuickSettings settings = flowId != null
        ? ref.watch(translationQuickSettingsProviderFamily(flowId!))
        : ref.watch(translationQuickSettingsProvider);
    final TranslationQuickSettingsNotifier notifier = flowId != null
        ? ref.read(translationQuickSettingsProviderFamily(flowId!).notifier)
        : ref.read(translationQuickSettingsProvider.notifier);

    // Target language is editable on Extract and Glossary tabs (synced with Extract);
    // disabled only during Translate phase to avoid changing language mid-translation.
    bool isOnExtractTab = false;
    bool isOnGlossaryTab = false;
    bool hasTask = false;
    if (flowId != null) {
      try {
        final tabFlags = ref.watch(
          previewTabsProviderFamily(flowId!).select((tabsState) {
            if (tabsState.tabs.isEmpty ||
                tabsState.activeTabIndex >= tabsState.tabs.length) {
              return const _TabLanguageFlags(extract: false, glossary: false);
            }
            final activeTab =
                tabsState.tabs[tabsState.activeTabIndex];
            return _TabLanguageFlags(
              extract: activeTab.id == 'extract_tab' ||
                  activeTab.title == 'Extract',
              glossary: activeTab.type == PreviewTabType.glossary,
            );
          }),
        );
        isOnExtractTab = tabFlags.extract;
        isOnGlossaryTab = tabFlags.glossary;
        hasTask = ref.watch(
          translationStateProviderFamily(flowId!).select((s) => s.taskId != null),
        );
      } catch (e) {
        isOnExtractTab = false;
        isOnGlossaryTab = false;
        hasTask = false;
      }
    }
    // Disable target language only in Translate phase (has task and not on Extract/Glossary)
    final bool isTranslatePhase =
        hasTask && !isOnExtractTab && !isOnGlossaryTab;

    final showAds = ref.watch(showAdsProvider).value ?? false;

    return Card(
      elevation: 2,
      child: Padding(
        padding: const EdgeInsets.all(6), // Reduced from 8 to 6
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: <Widget>[
            Row(
              children: <Widget>[
                Icon(Icons.settings,
                    color: Colors.blue.shade700,
                    size: 18,), // Reduced from 20 to 18
                const SizedBox(width: 6), // Reduced from 8 to 6
                Expanded(
                  child: Text(
                    AppLocalizations.of(context)!.translationQuickSettingsTitle,
                    style: TextStyle(
                      fontSize: 14, // Reduced from 16 to 14
                      fontWeight: FontWeight.bold,
                      color: Colors.blue.shade700,
                    ),
                    overflow: TextOverflow.ellipsis,
                  ),
                ),
              ],
            ),
            const SizedBox(height: 8), // Reduced from 16 to 8

            // Group 1: Source Language + Parsing Platform (MinerU OCR)
            // Shown only for markdown_based workflow (PDF, images, markdown)
            if (settings.workflowType == 'markdown_based') ...<Widget>[
              _buildSourceLanguageSelector(
                  context, settings, notifier, isTranslatePhase,),
              const SizedBox(height: 8),
              _buildParsingPlatformSection(context, ref),
              const SizedBox(height: 8), // Reduced from 16 to 8
            ],

            // Group 2: Target Language + LLM Platform (Translation)
            _buildLanguageSelector(
                context, settings, notifier, isTranslatePhase, ref,),
            const SizedBox(height: 8), // Reduced from 16 to 8
            _buildLLMAndTemperatureSection(context, ref, settings, notifier),
            const SizedBox(height: 8),

            // 工作流类型（仅在 Debug 模式下显示）
            //if (kDebugMode) ...<Widget>[
            //  _buildWorkflowTypeSelector(settings, notifier),
            //  const SizedBox(height: 8),
            //],

            // Qt .ts 配置（条件显示）
            if (settings.workflowType == 'qt_ts') ...<Widget>[
              _buildQtTsSettings(context, settings, notifier),
              const SizedBox(height: 8), // Reduced from 16 to 8
            ],

            // 质量设置已移除

            // Prompt 模式与风格
            _buildPromptControls(context, settings, notifier),

            if (showAds) const SizedBox(height: 8), // Reduced from 16 to 8

            // Ad Placeholder - Region F (Bottom of Quick Settings Card)
            if (showAds) _buildAdPlaceholderF(),
          ],
        ),
      ),
    );
  }

  /// Build ad placeholder for Region F (Bottom of Quick Settings Card)
  Widget _buildAdPlaceholderF() => const _FlowAdPlaceholder();

  // NOTE:
  // Legacy prompt_mode_/prompt_style_/prompt_note_ language-scoped recovery
  // is intentionally disabled for OpenSource behavior.
  // Source of truth is the latest local TranslationQuickSettings JSON.

  /// Wraps a Quick Settings block (e.g. Target Language, MinerU, LLM) in a bordered
  /// container so label and control share one frame and look consistent with dropdowns.
  static Widget _wrapQuickSettingSection(BuildContext context,
      {required Widget child,}) {
    final Color borderColor = Theme.of(context).dividerColor;
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 8),
      decoration: BoxDecoration(
        border: Border.all(color: borderColor),
        borderRadius: BorderRadius.circular(6),
      ),
      child: child,
    );
  }

  Widget _buildLanguageSelector(
    BuildContext context,
    TranslationQuickSettings settings,
    TranslationQuickSettingsNotifier notifier,
    bool isTranslatePhase,
    WidgetRef ref,
  ) {
    // code + native (script in parentheses, kept as original in all locales)
    final List<Map<String, String>> languageEntries = <Map<String, String>>[
      <String, String>{'code': 'ar', 'native': 'العربية'},
      <String, String>{'code': 'bn', 'native': 'বাংলা'},
      <String, String>{'code': 'ca', 'native': 'Català'},
      <String, String>{'code': 'zh', 'native': '中文'},
      <String, String>{'code': 'zh-TW', 'native': '繁體中文'},
      <String, String>{'code': 'cs', 'native': 'Čeština'},
      <String, String>{'code': 'hr', 'native': 'Hrvatski'},
      <String, String>{'code': 'da', 'native': 'Dansk'},
      <String, String>{'code': 'nl', 'native': 'Nederlands'},
      <String, String>{'code': 'en', 'native': 'English'},
      <String, String>{'code': 'fil', 'native': 'Filipino'},
      <String, String>{'code': 'fi', 'native': 'Suomi'},
      <String, String>{'code': 'fr', 'native': 'Français'},
      <String, String>{'code': 'de', 'native': 'Deutsch'},
      <String, String>{'code': 'el', 'native': 'Ελληνικά'},
      <String, String>{'code': 'he', 'native': 'עברית'},
      <String, String>{'code': 'hi', 'native': 'हिन्दी'},
      <String, String>{'code': 'it', 'native': 'Italiano'},
      <String, String>{'code': 'ja', 'native': '日本語'},
      <String, String>{'code': 'ko', 'native': '한국어'},
      <String, String>{'code': 'km', 'native': 'ភាសាខ្មែរ'},
      <String, String>{'code': 'lt', 'native': 'Lietuvių'},
      <String, String>{'code': 'mk', 'native': 'Македонски'},
      <String, String>{'code': 'ms', 'native': 'Bahasa Melayu'},
      <String, String>{'code': 'nb', 'native': 'Norwegian Bokmål'},
      <String, String>{'code': 'pl', 'native': 'Polski'},
      <String, String>{'code': 'pt', 'native': 'Português'},
      <String, String>{'code': 'ro', 'native': 'Română'},
      <String, String>{'code': 'ru', 'native': 'Русский'},
      <String, String>{'code': 'sl', 'native': 'Slovenščina'},
      <String, String>{'code': 'es', 'native': 'Español'},
      <String, String>{'code': 'sv', 'native': 'Svenska'},
      <String, String>{'code': 'th', 'native': 'ไทย'},
      <String, String>{'code': 'tr', 'native': 'Türkçe'},
      <String, String>{'code': 'uk', 'native': 'Українська'},
      <String, String>{'code': 'ur', 'native': 'اردو'},
      <String, String>{'code': 'vi', 'native': 'Tiếng Việt'},
    ];
    final l10n = AppLocalizations.of(context)!;

    return _wrapQuickSettingSection(
      context,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: <Widget>[
          Text(
            AppLocalizations.of(context)!.quickSettingsTargetLanguage,
            style: const TextStyle(fontWeight: FontWeight.w500, fontSize: 13),
          ),
          const SizedBox(height: 4),
          DropdownButtonFormField<String>(
            initialValue: settings.toLang,
            isExpanded: true,
            decoration: const InputDecoration(
              border: OutlineInputBorder(),
              contentPadding: EdgeInsets.symmetric(horizontal: 10, vertical: 6),
              isDense: true,
            ),
            items: languageEntries
                .map(
                  (Map<String, String> lang) => DropdownMenuItem<String>(
                    value: lang['code'],
                    child: Text(
                      _languageDisplayName(
                        l10n,
                        lang['code']!,
                        lang['native']!,
                      ),
                    ),
                  ),
                )
                .toList(),
            // CRITICAL: Disable language switching in Translate phase
            // Language switching is only allowed in Extract phase
            onChanged: isTranslatePhase
                ? null // Disable dropdown in Translate phase
                : (String? value) {
                    if (value != null) {
                      // CRITICAL: Get taskId from translationState if available
                      // This allows immediate update to backend for MinerU processing
                      String? taskId;
                      if (flowId != null) {
                        try {
                          final translationState = ref.read(
                            translationStateProviderFamily(flowId!),
                          );
                          taskId = translationState.taskId?.toString();
                        } catch (e) {
                          // If translationState is not available, taskId will be null
                          // updateToLang will handle this gracefully
                        }
                      }
                      notifier.updateToLang(value, taskId: taskId);
                    }
                  },
          ),
          // Show hint only when language switching is disabled; no fixed slot so layout adapts when hint is hidden
          if (isTranslatePhase)
            Padding(
              padding: const EdgeInsets.only(top: 4),
              child: Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: <Widget>[
                  Icon(
                    Icons.info_outline,
                    size: 14,
                    color: Colors.orange.shade700,
                  ),
                  const SizedBox(width: 4),
                  Expanded(
                    child: Text(
                      AppLocalizations.of(context)!
                          .quickSettingsLanguageSwitchDisabled,
                      style: TextStyle(
                        fontSize: 11,
                        color: Colors.orange.shade700,
                        fontStyle: FontStyle.italic,
                      ),
                      maxLines: 2,
                      overflow: TextOverflow.ellipsis,
                    ),
                  ),
                ],
              ),
            ),
        ],
      ),
    );
  }

  /// Source language selector for MinerU OCR (markdown_based workflow only).
  /// Default is "auto" which lets MinerU auto-detect the language.
  Widget _buildSourceLanguageSelector(
    BuildContext context,
    TranslationQuickSettings settings,
    TranslationQuickSettingsNotifier notifier,
    bool isTranslatePhase,
  ) {
    // MinerU OCR supports a limited set of language codes.
    // Align source language options with MinerU's supported values.
    // 显示规则：括号外是可做 l10n 的英文描述，括号内是该语言自己的名称。
    final List<Map<String, String>> languageEntries = <Map<String, String>>[
      <String, String>{'code': 'auto',        'native': 'Auto'},
      <String, String>{'code': 'ch',          'native': 'Chinese (中文)'},
      <String, String>{'code': 'ch_server',   'native': 'Chinese (Server) (中文)'},
      <String, String>{'code': 'ch_lite',     'native': 'Chinese (Lite) (中文)'},
      <String, String>{'code': 'chinese_cht', 'native': 'Chinese (Traditional) (繁體中文)'},
      <String, String>{'code': 'en',          'native': 'English (English)'},
      <String, String>{'code': 'korean',      'native': 'Korean (한국어)'},
      <String, String>{'code': 'japan',       'native': 'Japanese (日本語)'},
      <String, String>{'code': 'ta',          'native': 'Tamil (தமிழ்)'},
      <String, String>{'code': 'te',          'native': 'Telugu (తెలుగు)'},
      <String, String>{'code': 'ka',          'native': 'Kannada (ಕನ್ನಡ)'},
      <String, String>{'code': 'th',          'native': 'Thai (ไทย)'},
      <String, String>{'code': 'el',          'native': 'Greek (Ελληνικά)'},
      <String, String>{'code': 'latin',       'native': 'Latin (Latin)'},
      <String, String>{'code': 'arabic',      'native': 'Arabic (العربية)'},
      <String, String>{'code': 'east_slavic', 'native': 'East Slavic (East Slavic)'},
      <String, String>{'code': 'cyrillic',    'native': 'Cyrillic (Cyrillic)'},
      <String, String>{'code': 'devanagari',  'native': 'Devanagari (देवनागरी)'},
    ];

    final Set<String> mineruCodes = languageEntries
        .map((Map<String, String> e) => e['code']!)
        .toSet();
    final String effectiveSourceLang =
        _coerceMineruOcrSourceLang(settings.sourceLang, mineruCodes);

    return _wrapQuickSettingSection(
      context,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: <Widget>[
          Text(
            AppLocalizations.of(context)!.quickSettingsSourceLanguage,
            style: const TextStyle(fontWeight: FontWeight.w500, fontSize: 13),
          ),
          const SizedBox(height: 4),
          DropdownButtonFormField<String>(
            key: ValueKey<String>(
              'mineruOcr:${settings.sourceLang}|$effectiveSourceLang',
            ),
            initialValue: effectiveSourceLang,
            isExpanded: true,
            decoration: const InputDecoration(
              border: OutlineInputBorder(),
              contentPadding: EdgeInsets.symmetric(horizontal: 10, vertical: 6),
              isDense: true,
            ),
            items: languageEntries
                .map(
                  (Map<String, String> lang) => DropdownMenuItem<String>(
                    value: lang['code'],
                    child: Text('${lang['native']} (${lang['code']})'),
                  ),
                )
                .toList(),
            onChanged: isTranslatePhase
                ? null
                : (String? value) {
                    if (value != null) {
                      notifier.updateSourceLang(value);
                    }
                  },
          ),
        ],
      ),
    );
  }

  /// Maps persisted/UI language codes to MinerU OCR tokens and guarantees a valid dropdown value.
  static String _coerceMineruOcrSourceLang(String raw, Set<String> mineruCodes) {
    final String trimmed = raw.trim();
    String mapped = trimmed.isEmpty ? 'auto' : trimmed;
    // Translation target codes and ISO-style aliases are not valid MinerU OCR codes.
    switch (mapped) {
      case 'zh':
      case 'zh-CN':
      case 'zh-Hans':
        mapped = 'auto';
        break;
      case 'zh-TW':
      case 'zh-Hant':
        mapped = 'chinese_cht';
        break;
      case 'ja':
        mapped = 'japan';
        break;
      case 'ko':
        mapped = 'korean';
        break;
      default:
        break;
    }
    if (mineruCodes.contains(mapped)) {
      return mapped;
    }
    return 'auto';
  }

  /// Returns localized language label + " (native)" for dropdown display.
  static String _languageDisplayName(
    AppLocalizations l10n,
    String code,
    String native,
  ) {
    final String label = switch (code) {
      'ar' => l10n.translationLangArabic,
      'bn' => l10n.translationLangBengali,
      'ca' => l10n.translationLangCatalan,
      'zh' => l10n.translationLangChinese,
      'zh-TW' => l10n.translationLangChineseTraditional,
      'cs' => l10n.translationLangCzech,
      'hr' => l10n.translationLangCroatian,
      'da' => l10n.translationLangDanish,
      'nl' => l10n.translationLangDutch,
      'en' => l10n.translationLangEnglish,
      'fil' => l10n.translationLangFilipino,
      'fi' => l10n.translationLangFinnish,
      'fr' => l10n.translationLangFrench,
      'de' => l10n.translationLangGerman,
      'el' => l10n.translationLangGreek,
      'he' => l10n.translationLangHebrew,
      'hi' => l10n.translationLangHindi,
      'it' => l10n.translationLangItalian,
      'ja' => l10n.translationLangJapanese,
      'ko' => l10n.translationLangKorean,
      'km' => l10n.translationLangKhmer,
      'lt' => l10n.translationLangLithuanian,
      'mk' => l10n.translationLangMacedonian,
      'ms' => l10n.translationLangMalay,
      'nb' => l10n.translationLangNorwegian,
      'pl' => l10n.translationLangPolish,
      'pt' => l10n.translationLangPortuguese,
      'ro' => l10n.translationLangRomanian,
      'ru' => l10n.translationLangRussian,
      'sl' => l10n.translationLangSlovenian,
      'es' => l10n.translationLangSpanish,
      'sv' => l10n.translationLangSwedish,
      'th' => l10n.translationLangThai,
      'tr' => l10n.translationLangTurkish,
      'uk' => l10n.translationLangUkrainian,
      'ur' => l10n.translationLangUrdu,
      'vi' => l10n.translationLangVietnamese,
      _ => code,
    };
    return '$label ($native)';
  }

  /// Parsing Platform section: same style as LLM Platform, supports both MinerU Cloud and Local.
  /// Shown only for markdown_based workflow.
  Widget _buildParsingPlatformSection(BuildContext context, WidgetRef ref) {
    final AIPlatformSettings aiPlatformSettings =
        ref.watch(aiPlatformSettingsProvider);
    final AIPlatformSettingsNotifier aiPlatformNotifier =
        ref.read(aiPlatformSettingsProvider.notifier);
    final GlobalSettings globalSettings = ref.watch(globalSettingsProvider);
    final GlobalSettingsNotifier globalNotifier =
        ref.read(globalSettingsProvider.notifier);

    final String selectedParser = globalSettings.parsingEngine;
    final List<String> parserOptions = <String>['mineru', 'mineru_local'];

    AIPlatformInfo? getParserInfo(String key) => aiPlatformSettings.platforms[key];

    Color parserStatusColor(AIPlatformInfo? info) {
      final bool? available = info?.isApiAvailable;
      final bool configured = info?.isConfigured ?? false;
      if (available ?? false) return Colors.green;
      if (available == false) return Colors.red;
      if (!configured) return Colors.grey;
      return Colors.grey;
    }

    String parserStatusTooltip(AIPlatformInfo? info) {
      final bool? available = info?.isApiAvailable;
      final bool configured = info?.isConfigured ?? false;
      final l10n = AppLocalizations.of(context)!;
      if (available ?? false) return l10n.quickSettingsApiOk;
      if (available == false) {
        return info?.lastTestError ?? l10n.quickSettingsApiUnavailable;
      }
      if (!configured) return l10n.quickSettingsNotConfigured;
      return l10n.quickSettingsNotTestedYet;
    }

    final l10n = AppLocalizations.of(context)!;
    final String testLabel = selectedParser == 'mineru_local'
        ? 'MinerU Local'
        : 'MinerU';

    return _wrapQuickSettingSection(
      context,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: <Widget>[
          Row(
            children: <Widget>[
              Text(
                l10n.quickSettingsParsingPlatform,
                style: const TextStyle(fontWeight: FontWeight.w500, fontSize: 13),
              ),
              const Spacer(),
              Tooltip(
                message: l10n.quickSettingsTestMineru,
                child: IconButton(
                  icon: const Icon(Icons.wifi_tethering),
                  iconSize: 20,
                  padding: EdgeInsets.zero,
                  constraints:
                      const BoxConstraints(minWidth: 32, minHeight: 32),
                  onPressed: () async {
                    try {
                      final String apiKey = selectedParser == 'mineru_local'
                          ? (getParserInfo('mineru_local')?.apiKey ?? '')
                          : '';
                      final result =
                          await ConfigService().testAIPlatform(
                            selectedParser,
                            apiKey,
                            baseUrl: getParserInfo(selectedParser)?.url,
                          );
                      await aiPlatformNotifier.refreshPlatformStatus();
                      if (!context.mounted) return;
                      final success = result?['success'] == true;
                      final l10nSnack = AppLocalizations.of(context)!;
                      final message = result?['message']?.toString() ??
                          (success
                              ? l10nSnack.quickSettingsConnectionSuccessful
                              : l10nSnack.quickSettingsMineruConnectionFailed);
                      ScaffoldMessenger.of(context).showSnackBar(
                        SnackBar(
                          content: Text(
                            l10nSnack.quickSettingsPlatformMessage(
                              testLabel,
                              message,
                            ),
                          ),
                          duration: const Duration(seconds: 3),
                          backgroundColor: success
                              ? Colors.green.shade700
                              : Colors.red.shade700,
                          behavior: SnackBarBehavior.floating,
                        ),
                      );
                    } catch (e) {
                      await aiPlatformNotifier.refreshPlatformStatus();
                      if (!context.mounted) return;
                      final l10nErr = AppLocalizations.of(context)!;
                      ScaffoldMessenger.of(context).showSnackBar(
                        SnackBar(
                          content: Text(
                            l10nErr.quickSettingsPlatformTestFailed(
                              testLabel,
                              e.toString(),
                            ),
                          ),
                          backgroundColor: Colors.red.shade700,
                          behavior: SnackBarBehavior.floating,
                        ),
                      );
                    }
                  },
                ),
              ),
              if (!kIsWeb ||
                  (ref.watch(canAccessAdminSettingsProvider).valueOrNull ?? false) ||
                  (kIsWeb &&
                      ref.watch(authProvider).maybeWhen(
                        unauthenticated: () => true,
                        orElse: () => false,
                      )))
                IconButton(
                  icon: const Icon(Icons.settings),
                  iconSize: 20,
                  padding: EdgeInsets.zero,
                  constraints: const BoxConstraints(minWidth: 32, minHeight: 32),
                  tooltip: l10n.quickSettingsOpenMineruSettings,
                  onPressed: () {
                    if (kIsWeb &&
                        (ConfigService().authRequired ?? false) &&
                        ref.read(authProvider).maybeWhen(
                          unauthenticated: () => true,
                          orElse: () => false,
                        )) {
                      context.go(AppRouter.loginRoute);
                      return;
                    }
                    context.push('${AppRouter.settingsRoute}?tab=1');
                  },
                ),
            ],
          ),
          const SizedBox(height: 4),
          DropdownButtonFormField<String>(
            key: ValueKey<String>('parser:$selectedParser'),
            initialValue: parserOptions.contains(selectedParser) ? selectedParser : parserOptions.first,
            isExpanded: true,
            decoration: const InputDecoration(
              border: OutlineInputBorder(),
              contentPadding: EdgeInsets.symmetric(horizontal: 10, vertical: 6),
              isDense: true,
            ),
            items: parserOptions.map((String code) {
              final info = getParserInfo(code);
              final color = parserStatusColor(info);
              final tooltip = parserStatusTooltip(info);
              final String label = info?.name.isNotEmpty ?? false
                  ? info!.name
                  : (code == 'mineru_local'
                      ? 'MinerU Local'
                      : l10n.quickSettingsMineruLabel);
              return DropdownMenuItem<String>(
                value: code,
                child: Tooltip(
                  message: tooltip,
                  child: Row(
                    mainAxisSize: MainAxisSize.min,
                    children: <Widget>[
                      Icon(Icons.circle, size: 10, color: color),
                      const SizedBox(width: 8),
                      Expanded(
                        child: Text(
                          label,
                          overflow: TextOverflow.ellipsis,
                        ),
                      ),
                    ],
                  ),
                ),
              );
            }).toList(),
            onChanged: (String? value) {
              if (value != null && value != selectedParser) {
                globalNotifier.updateParsingEngineSettings(
                  parsingEngine: value,
                );
              }
            },
          ),
        ],
      ),
    );
  }

  Widget _buildPrimaryAIPlatform(BuildContext context, WidgetRef ref) {
    final l10n = AppLocalizations.of(context)!;
    final AIPlatformSettings aiPlatformSettings =
        ref.watch(aiPlatformSettingsProvider);
    final AIPlatformSettingsNotifier aiPlatformNotifier =
        ref.read(aiPlatformSettingsProvider.notifier);

    final List<AIPlatformInfo> allPlatforms =
        aiPlatformSettings.platforms.values.toList();
    List<AIPlatformInfo> llmPlatforms = allPlatforms
        .where((AIPlatformInfo p) => p.platformType == 'llm')
        .toList();
    if (llmPlatforms.isEmpty) {
      llmPlatforms = allPlatforms;
    }
    final String current = aiPlatformSettings.defaultPlatform;
    final String? validSelected =
        llmPlatforms.any((AIPlatformInfo p) => p.key == current)
            ? current
            : null;

    // Key so dropdown rebuilds when platform status (e.g. after test in Settings) changes
    final platformStatusKey = llmPlatforms
        .map((AIPlatformInfo p) => '${p.key}:${p.isApiAvailable}')
        .join(';');

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: <Widget>[
        Row(
          children: <Widget>[
            Text(
              l10n.quickSettingsLlmPlatform,
              style: const TextStyle(fontWeight: FontWeight.w500, fontSize: 13),
            ),
            const Spacer(),
            Tooltip(
              message: l10n.quickSettingsTestLlmPlatform,
              child: IconButton(
                icon: const Icon(Icons.wifi_tethering),
                iconSize: 20,
                padding: EdgeInsets.zero,
                constraints: const BoxConstraints(minWidth: 32, minHeight: 32),
                onPressed: validSelected == null
                    ? null
                    : () async {
                        final platformKey = validSelected;
                        final info = aiPlatformSettings.platforms[platformKey];
                        try {
                          final result = await ConfigService().testAIPlatform(
                            platformKey,
                            '', // backend uses stored secrets
                            baseUrl: info?.url,
                            modelName: info?.model,
                          );
                          await aiPlatformNotifier.refreshPlatformStatus();
                          if (!context.mounted) return;
                          final success = result?['success'] == true;
                          final l10nSnack = AppLocalizations.of(context)!;
                          final message = result?['message']?.toString() ??
                              (success
                                  ? l10nSnack.quickSettingsConnectionSuccessful
                                  : l10nSnack.quickSettingsTestFailed);
                          final platformLabel = info?.name ?? platformKey;
                          ScaffoldMessenger.of(context).showSnackBar(
                            SnackBar(
                              content: Text(
                                l10nSnack.quickSettingsPlatformMessage(
                                  platformLabel,
                                  message,
                                ),
                              ),
                              duration: const Duration(seconds: 3),
                              backgroundColor: success
                                  ? Colors.green.shade700
                                  : Colors.red.shade700,
                              behavior: SnackBarBehavior.floating,
                            ),
                          );
                        } catch (e) {
                          await aiPlatformNotifier.refreshPlatformStatus();
                          if (!context.mounted) return;
                          final platformLabel = info?.name ?? platformKey;
                          final l10nErr = AppLocalizations.of(context)!;
                          ScaffoldMessenger.of(context).showSnackBar(
                            SnackBar(
                              content: Text(
                                l10nErr.quickSettingsPlatformTestFailed(
                                  platformLabel,
                                  e.toString(),
                                ),
                              ),
                              backgroundColor: Colors.red.shade700,
                              behavior: SnackBarBehavior.floating,
                            ),
                          );
                        }
                      },
              ),
            ),
            if (!kIsWeb ||
                (ref.watch(canAccessAdminSettingsProvider).valueOrNull ?? false) ||
                (kIsWeb &&
                    ref.watch(authProvider).maybeWhen(
                      unauthenticated: () => true,
                      orElse: () => false,
                    )))
              IconButton(
                icon: const Icon(Icons.settings),
                iconSize: 20,
                padding: EdgeInsets.zero,
                constraints: const BoxConstraints(minWidth: 32, minHeight: 32),
                tooltip: l10n.quickSettingsOpenAiPlatformsSettings,
                onPressed: () {
                  if (kIsWeb &&
                      ref.read(authProvider).maybeWhen(
                        unauthenticated: () => true,
                        orElse: () => false,
                      )) {
                    showAdminRequiredDialog(context);
                    return;
                  }
                  context.push('${AppRouter.settingsRoute}?tab=1');
                },
              ),
          ],
        ),
        const SizedBox(height: 4),
        DropdownButtonFormField<String>(
          key: ValueKey<String>(platformStatusKey),
          initialValue: validSelected,
          isExpanded: true,
          decoration: const InputDecoration(
            border: OutlineInputBorder(),
            contentPadding: EdgeInsets.symmetric(horizontal: 10, vertical: 6),
            isDense: true,
          ),
          items: llmPlatforms.map((AIPlatformInfo p) {
            final bool? available = p.isApiAvailable;
            // Prefer backend status: green when backend says available (including for normal users
            // who cannot see keys); red when backend says failed; grey when unknown/not configured
            final Color statusColor = (available ?? false)
                ? Colors.green
                : (available == false)
                    ? Colors.red
                    : Colors.grey;
            final String tooltip = (available ?? false)
                ? l10n.quickSettingsApiOk
                : (available == false)
                    ? (p.lastTestError ?? l10n.quickSettingsApiUnavailable)
                    : (!p.isConfigured
                        ? l10n.quickSettingsNotConfigured
                        : l10n.quickSettingsNotTestedYet);
            return DropdownMenuItem<String>(
              value: p.key,
              child: Tooltip(
                message: tooltip,
                child: Row(
                  mainAxisSize: MainAxisSize.min,
                  children: <Widget>[
                    Icon(Icons.circle, size: 10, color: statusColor),
                    const SizedBox(width: 8),
                    Expanded(
                      child: Text(
                        p.name,
                        overflow: TextOverflow.ellipsis,
                      ),
                    ),
                  ],
                ),
              ),
            );
          }).toList(),
          onChanged: (String? val) async {
            if (val == null) return;
            await aiPlatformNotifier.setDefaultPlatform(val);

            // Update temperature from new platform configuration
            final AIPlatformInfo? newPlatform =
                aiPlatformSettings.platforms[val];
            if (newPlatform != null) {
              final TranslationQuickSettingsNotifier quickSettingsNotifier =
                  flowId != null
                      ? ref.read(
                          translationQuickSettingsProviderFamily(flowId!)
                              .notifier,
                        )
                      : ref.read(translationQuickSettingsProvider.notifier);
              quickSettingsNotifier.updateTemperatureFromPlatform(newPlatform);
            }
          },
        ),
      ],
    );
  }

  /// LLM Platform + Temperature in one bordered section.
  Widget _buildLLMAndTemperatureSection(
    BuildContext context,
    WidgetRef ref,
    TranslationQuickSettings settings,
    TranslationQuickSettingsNotifier notifier,
  ) =>
      _wrapQuickSettingSection(
        context,
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: <Widget>[
            _buildPrimaryAIPlatform(context, ref),
            const SizedBox(height: 8),
            _buildTemperatureSlider(context, settings, notifier, ref),
          ],
        ),
      );

  // Commented out: Workflow Type selector - always use auto-select based on file extension
  /*
  Widget _buildWorkflowTypeSelector(
    TranslationQuickSettings settings,
    TranslationQuickSettingsNotifier notifier,
  ) {
    final List<Map<String, String>> workflowTypes = <Map<String, String>>[
      <String, String>{'code': 'docx', 'name': 'DOCX Translation (.docx)'},
      <String, String>{'code': 'pptx', 'name': 'PPTX Translation (.pptx)'},
      <String, String>{'code': 'xlsx', 'name': 'XLSX Translation (.xlsx/.csv)'},
      <String, String>{
        'code': 'markdown_based',
        'name': 'Parse and Translate (.pdf/.md/.png, etc.)',
      },
      <String, String>{'code': 'txt', 'name': 'Plain Text Translation (.txt)'},
      <String, String>{'code': 'json', 'name': 'JSON Translation (.json)'},
      <String, String>{
        'code': 'srt',
        'name': 'SRT Subtitle Translation (.srt)'
      },
      <String, String>{'code': 'epub', 'name': 'EPUB Translation (.epub)'},
      <String, String>{'code': 'mobi', 'name': 'MOBI Translation (.mobi/)'},
      <String, String>{'code': 'html', 'name': 'HTML Translation (.html)'},
      <String, String>{'code': 'qt_ts', 'name': 'Qt .ts Translation (.ts)'},
    ];

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: <Widget>[
        Row(
          children: <Widget>[
            const Expanded(
              child: Text(
                'Workflow Type',
                style: TextStyle(fontWeight: FontWeight.w500),
                overflow: TextOverflow.ellipsis,
              ),
            ),
            Switch(
              value: settings.autoSelectWorkflow,
              onChanged: notifier.updateAutoSelectWorkflow,
              materialTapTargetSize: MaterialTapTargetSize.shrinkWrap,
            ),
            const SizedBox(width: 8),
            const Flexible(
              child: Text(
                'Auto',
                style: TextStyle(fontSize: 12),
                overflow: TextOverflow.ellipsis,
              ),
            ),
          ],
        ),
        const SizedBox(height: 8),
        DropdownButtonFormField<String>(
          initialValue: settings.workflowType,
          isExpanded: true,
          decoration: InputDecoration(
            border: const OutlineInputBorder(),
            contentPadding:
                const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
            hintText: settings.autoSelectWorkflow
                ? 'Auto-selected by file type'
                : null,
          ),
          items: workflowTypes
              .map((Map<String, String> type) => DropdownMenuItem(
                    value: type['code'],
                    child: Text(
                      type['name']!,
                      overflow: TextOverflow.ellipsis,
                    ),
                  ))
              .toList(),
          onChanged: settings.autoSelectWorkflow
              ? null // Disable when auto-select is enabled
              : (String? value) => notifier.updateWorkflowType(value!),
        ),
        if (settings.autoSelectWorkflow)
          Padding(
            padding: const EdgeInsets.only(top: 4),
            child: Text(
              'Workflow will be automatically selected based on file extension',
              style: TextStyle(
                fontSize: 11,
                color: Colors.grey.shade600,
                fontStyle: FontStyle.italic,
              ),
              overflow: TextOverflow.ellipsis,
              maxLines: 2,
            ),
          ),
      ],
    );
  }
  */

  // 质量设置组件已移除

  Widget _buildQtTsSettings(
    BuildContext context,
    TranslationQuickSettings settings,
    TranslationQuickSettingsNotifier notifier,
  ) {
    final l10n = AppLocalizations.of(context)!;
    return Card(
        color: Colors.blue.shade50,
        child: Padding(
          padding: const EdgeInsets.all(8), // Reduced from 12 to 8
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: <Widget>[
              Row(
                children: <Widget>[
                  Icon(Icons.translate,
                      size: 16,
                      color: Colors.blue.shade700,), // Reduced from 18 to 16
                  const SizedBox(width: 6), // Reduced from 8 to 6
                  Expanded(
                    child: Text(
                      l10n.quickSettingsQtTsOptions,
                      style: TextStyle(
                        fontSize: 13, // Reduced from 14 to 13
                        fontWeight: FontWeight.w600,
                        color: Colors.blue.shade700,
                      ),
                      overflow: TextOverflow.ellipsis,
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 8), // Reduced from 12 to 8
              _buildQtTsCheckbox(
                context,
                l10n.quickSettingsQtTsSkipExisting,
                l10n.quickSettingsQtTsSkipExistingSubtitle,
                settings.qtTsSkipExistingTranslations,
                notifier.updateQtTsSkipExistingTranslations,
              ),
              const SizedBox(height: 4), // Reduced from 8 to 4
              _buildQtTsCheckbox(
                context,
                l10n.quickSettingsQtTsTranslateUnfinished,
                l10n.quickSettingsQtTsTranslateUnfinishedSubtitle,
                settings.qtTsTranslateUnfinished,
                notifier.updateQtTsTranslateUnfinished,
              ),
              const SizedBox(height: 4), // Reduced from 8 to 4
              _buildQtTsCheckbox(
                context,
                l10n.quickSettingsQtTsTranslateVanished,
                l10n.quickSettingsQtTsTranslateVanishedSubtitle,
                settings.qtTsTranslateVanished,
                notifier.updateQtTsTranslateVanished,
              ),
              const SizedBox(height: 4), // Reduced from 8 to 4
              _buildQtTsCheckbox(
                context,
                l10n.quickSettingsQtTsTranslateObsolete,
                l10n.quickSettingsQtTsTranslateObsoleteSubtitle,
                settings.qtTsTranslateObsolete,
                notifier.updateQtTsTranslateObsolete,
              ),
            ],
          ),
        ),
      );
  }

  Widget _buildQtTsCheckbox(
    BuildContext context,
    String title,
    String subtitle,
    bool value,
    ValueChanged<bool> onChanged,
  ) =>
      CheckboxListTile(
        title: Text(
          title,
          style: const TextStyle(fontSize: 12), // Reduced from 13 to 12
          overflow: TextOverflow.ellipsis,
          maxLines: 1,
        ),
        subtitle: Text(
          subtitle,
          style: TextStyle(
              fontSize: 10,
              color: Colors.grey.shade600,), // Reduced from 11 to 10
          overflow: TextOverflow.ellipsis,
          maxLines: 2,
        ),
        value: value,
        onChanged: (bool? newValue) {
          if (newValue != null) {
            onChanged(newValue);
          }
        },
        dense: true,
        contentPadding: EdgeInsets.zero,
        controlAffinity: ListTileControlAffinity.leading,
        visualDensity: VisualDensity.compact, // Added to reduce height
      );

  // Removed: _buildSwitchOptions - Deep split is now always enabled by default

  // Removed: _buildSelectedAIPlatform (migrated to toolbar)

  Widget _buildTemperatureSlider(
    BuildContext context,
    TranslationQuickSettings settings,
    TranslationQuickSettingsNotifier notifier,
    WidgetRef ref,
  ) {
    final AIPlatformSettings aiPlatformSettings =
        ref.watch(aiPlatformSettingsProvider);
    final String currentPlatform = aiPlatformSettings.defaultPlatform;
    final AIPlatformInfo? platformInfo =
        aiPlatformSettings.platforms[currentPlatform];

    // Get temperature from settings or platform default
    final double currentTemperature =
        settings.temperature ?? (platformInfo?.temperature ?? 0.3);

    // Get temperature min and max from platform
    final double temperatureMin = platformInfo?.temperatureMin ?? 0.0;
    final double temperatureMax = platformInfo?.temperatureMax ?? 2.0;
    final int divisions = ((temperatureMax - temperatureMin) * 10).round();

    // Update temperature from platform if not set
    if (settings.temperature == null && platformInfo != null) {
      WidgetsBinding.instance.addPostFrameCallback((_) {
        notifier.updateTemperatureFromPlatform(platformInfo);
      });
    }

    final l10n = AppLocalizations.of(context)!;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: <Widget>[
        Row(
          children: <Widget>[
            Text(
              l10n.quickSettingsTemperature,
              style: const TextStyle(
                  fontWeight: FontWeight.w500, fontSize: 13,), // Added fontSize
            ),
            const SizedBox(width: 6), // Reduced from 8 to 6
            Flexible(
              child: Text(
                currentTemperature.toStringAsFixed(1),
                style: TextStyle(
                    color: Colors.grey.shade600,
                    fontSize: 12,), // Added fontSize
                overflow: TextOverflow.ellipsis,
              ),
            ),
            const SizedBox(width: 6), // Reduced from 8 to 6
            Flexible(
              child: Text(
                '(${temperatureMin.toStringAsFixed(1)} - ${temperatureMax.toStringAsFixed(1)})',
                style: TextStyle(
                  fontSize: 11, // Reduced from 12 to 11
                  color: Colors.grey.shade600,
                ),
                overflow: TextOverflow.ellipsis,
              ),
            ),
          ],
        ),
        const SizedBox(height: 4), // Reduced from 8 to 4
        Slider(
          value: currentTemperature.clamp(temperatureMin, temperatureMax),
          min: temperatureMin,
          max: temperatureMax,
          divisions: divisions,
          label: currentTemperature.toStringAsFixed(1),
          onChanged: (double value) {
            final AIPlatformSettingsNotifier aiPlatformNotifier =
                ref.read(aiPlatformSettingsProvider.notifier);
            final String currentPlatform = aiPlatformSettings.defaultPlatform;
            final AIPlatformInfo? platformInfo =
                aiPlatformSettings.platforms[currentPlatform];
            notifier.updateTemperature(
              value,
              aiPlatformNotifier,
              currentPlatform,
              platformInfo,
            );
          },
        ),
        Text(
          l10n.quickSettingsTemperatureHint,
          style: TextStyle(
              fontSize: 11,
              color: Colors.grey.shade600,), // Reduced from 12 to 11
          overflow: TextOverflow.ellipsis,
          maxLines: 2,
        ),
      ],
    );
  }

  Widget _buildPromptControls(
    BuildContext context,
    TranslationQuickSettings settings,
    TranslationQuickSettingsNotifier notifier,
  ) {
    final l10n = AppLocalizations.of(context)!;
    final List<Map<String, String>> modes = <Map<String, String>>[
      <String, String>{'code': 'off', 'name': l10n.quickSettingsPromptModeOff},
      <String, String>{'code': 'simple', 'name': l10n.quickSettingsPromptModeSimple},
      <String, String>{'code': 'advanced', 'name': l10n.quickSettingsPromptModeAdvanced},
    ];
    final List<Map<String, String>> styles = <Map<String, String>>[
      <String, String>{'code': 'literal', 'name': l10n.quickSettingsStyleLiteral},
      <String, String>{'code': 'fluent', 'name': l10n.quickSettingsStyleFluent},
      <String, String>{'code': 'academic', 'name': l10n.quickSettingsStyleAcademic},
      <String, String>{'code': 'business', 'name': l10n.quickSettingsStyleBusiness},
      <String, String>{'code': 'technical', 'name': l10n.quickSettingsStyleTechnical},
    ];

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: <Widget>[
        Text(l10n.quickSettingsPrompt,
            style: const TextStyle(
                fontWeight: FontWeight.w500, fontSize: 13,),), // Added fontSize
        const SizedBox(height: 4), // Reduced from 8 to 4
        // Prompt Mode (vertical layout)
        DropdownButtonFormField<String>(
          initialValue: settings.promptMode,
          isExpanded: true,
          decoration: InputDecoration(
            labelText: l10n.quickSettingsPromptMode,
            border: const OutlineInputBorder(),
            contentPadding: const EdgeInsets.symmetric(
                horizontal: 10, vertical: 6,), // Reduced padding
            isDense: true, // Added isDense to reduce height
          ),
          items: modes
              .map(
                (Map<String, String> m) => DropdownMenuItem(
                  value: m['code'],
                  child: Text(m['name']!),
                ),
              )
              .toList(),
          onChanged: (String? v) => notifier.updatePromptMode(v ?? 'off'),
        ),
        // Style (shown when prompt mode is not 'off')
        if (settings.promptMode != 'off') ...<Widget>[
          const SizedBox(height: 6), // Reduced from 12 to 6
          DropdownButtonFormField<String>(
            initialValue: settings.promptStyle,
            isExpanded: true,
            decoration: InputDecoration(
              labelText: l10n.quickSettingsStyle,
              border: const OutlineInputBorder(),
              contentPadding: const EdgeInsets.symmetric(
                  horizontal: 10, vertical: 6,), // Reduced padding
              isDense: true, // Added isDense to reduce height
            ),
            items: styles
                .map(
                  (Map<String, String> s) => DropdownMenuItem(
                    value: s['code'],
                    child: Text(s['name']!),
                  ),
                )
                .toList(),
            onChanged: notifier.updatePromptStyle,
          ),
        ],
        // Task Note (shown when prompt mode is 'advanced')
        if (settings.promptMode == 'advanced') ...<Widget>[
          const SizedBox(height: 6), // Reduced from 12 to 6
          _TaskNoteTextField(
            initialValue: settings.taskNote ?? '',
            onChanged: notifier.updateTaskNote,
          ),
        ],
      ],
    );
  }
}

/// Stateful widget to manage TextField controller for Task Note
/// This prevents cursor from jumping to the beginning when typing
class _TaskNoteTextField extends StatefulWidget {
  const _TaskNoteTextField({
    required this.initialValue,
    required this.onChanged,
  });
  final String initialValue;
  final ValueChanged<String> onChanged;

  @override
  State<_TaskNoteTextField> createState() => _TaskNoteTextFieldState();
}

class _TaskNoteTextFieldState extends State<_TaskNoteTextField> {
  late TextEditingController _controller;
  late ScrollController _scrollController;

  /// Fixed height for ~3-4 lines (fontSize 13, line height ~20, 4 lines + padding)
  static const double _taskNoteHeight = 96;

  @override
  void initState() {
    super.initState();
    _controller = TextEditingController(text: widget.initialValue);
    _scrollController = ScrollController();
  }

  @override
  void didUpdateWidget(_TaskNoteTextField oldWidget) {
    super.didUpdateWidget(oldWidget);
    // Only update text if it changed externally (not from user input)
    // This preserves cursor position when user is typing
    if (oldWidget.initialValue != widget.initialValue &&
        _controller.text != widget.initialValue) {
      // Save cursor position
      final TextSelection selection = _controller.selection;
      _controller.text = widget.initialValue;
      // Restore cursor position if it was valid
      if (selection.isValid && selection.end <= widget.initialValue.length) {
        _controller.selection = selection;
      } else {
        // If cursor position is invalid, place at end
        _controller.selection = TextSelection.collapsed(
          offset: widget.initialValue.length,
        );
      }
    }
  }

  @override
  void dispose() {
    _controller.dispose();
    _scrollController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => Scrollbar(
        controller: _scrollController,
        thumbVisibility: true,
        child: SizedBox(
          height: _taskNoteHeight,
          child: TextField(
            controller: _controller,
            scrollController: _scrollController,
            onChanged: widget.onChanged,
            maxLines: null,
            maxLength: 200,
            style: const TextStyle(fontSize: 13),
            decoration: InputDecoration(
              labelText: AppLocalizations.of(context)!.quickSettingsTaskNoteLabel,
              hintText: AppLocalizations.of(context)!.quickSettingsTaskNoteHint,
              border: const OutlineInputBorder(),
              contentPadding: const EdgeInsets.symmetric(horizontal: 10, vertical: 8),
              alignLabelWithHint: true,
              counterText: '',
            ),
          ),
        ),
      );
}

/// Ad placeholder widget for flow area with independent owl pose seed.
class _FlowAdPlaceholder extends StatefulWidget {
  const _FlowAdPlaceholder();

  @override
  State<_FlowAdPlaceholder> createState() => _FlowAdPlaceholderState();
}

class _FlowAdPlaceholderState extends State<_FlowAdPlaceholder> {
  /// Seed for owl pose/position in flow ad placeholder; independent from banner.
  int _flowOwlPoseSeed = 0;

  @override
  void initState() {
    super.initState();
    // Initialize with a random seed so it differs from banner
    _flowOwlPoseSeed = DateTime.now().millisecondsSinceEpoch % 1000;
  }

  @override
  Widget build(BuildContext context) => ConstrainedBox(
        constraints: const BoxConstraints(
          maxWidth: 300,
          minWidth: 250,
        ),
        child: IntrinsicWidth(
          child: AdPlaceholder(
            width: 300,
            height: 250,
            label: AppLocalizations.of(context)!.quickSettingsAdRegionF,
            type: AdType.rectangle,
            poseSeed: _flowOwlPoseSeed,
          ),
        ),
      );
}
