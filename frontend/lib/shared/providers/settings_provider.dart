import 'package:flutter/foundation.dart' show kDebugMode;
import 'dart:ui' as ui;
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'dart:convert';
import '../services/settings_service.dart';
import '../services/config_service.dart';

// 全局设置状态管理
final StateNotifierProvider<GlobalSettingsNotifier, GlobalSettings>
    globalSettingsProvider =
    StateNotifierProvider<GlobalSettingsNotifier, GlobalSettings>(
  (
    ref,
  ) =>
      GlobalSettingsNotifier(),
);

/// System settings from backend (system.json). Source of truth for show_ads.
final FutureProvider<bool> showAdsProvider =
    FutureProvider<bool>((FutureProviderRef<bool> ref) async {
  final data = await ConfigService().getSystemSettings();
  if (data == null || data['ok'] != true) return false;
  final features = data['features'];
  if (features is! Map<String, dynamic>) return false;
  return (features['show_ads'] as bool?) ?? false;
});

class GlobalSettings {
  const GlobalSettings({
    // General
    this.darkMode = false,
    this.language = 'en',
    this.notifications = true,
    this.autoSave = true,
    this.previewFontSize = 14.0,
    this.editFontSize = 16.0, // Default: 2pt larger than preview

    // AI Platform
    this.defaultPlatform = 'openai',
    this.platformConfigs = const <String, dynamic>{},

    // Parsing Engine
    this.parsingEngine = 'mineru',
    this.ocrLanguage = 'auto',
    this.formulaOcr = true,
    this.tableOcr = true,
    this.parsingChunkSize = 1000,
    this.parsingConcurrent = 3,
    this.parsingTimeout = 300,
    this.pdfSplitMaxPages = 100,
    this.pdfSplitMaxWorkers = 2,
    this.requestRetryCount = 2,

    // Glossary
    this.useGlobalGlossary = false,
    this.globalGlossaryFile = '',
    this.glossaryGenerateEnable = true,
    this.glossaryEntries = const <Map<String, dynamic>>[],

    // Prompts
    this.defaultTranslationPrompt = '',
    this.defaultAnonymizationPrompt = '',
    this.translationPrompts = const <Map<String, dynamic>>[],
    this.anonymizationPrompts = const <Map<String, dynamic>>[],
    this.customPrompts = const <Map<String, dynamic>>[],

    // Translation
    this.translationEngine = 'openai',
    this.translationQuality = 'balanced',
    this.skipTranslation = false,
    this.useGlossary = false,
    this.usePrompt = false,

    // Detailed Translation Parameters
    this.temperature = 0.3,
    this.thinking = 'disable',
    this.retry = 3,
    this.segmentAutoRetryRounds = 3,
    this.customPrompt,

    // Anonymization
    this.anonymizationEngine = 'presidio',
    this.entityTypes = const <String>[
      'EMAIL_ADDRESS',
      'PHONE_NUMBER',
      'PERSON',
    ],
    this.anonymizeMode = 'placeholder',
    this.anonymizeConfidence = 0.6,
    this.customPlaceholder = '[REDACTED]',

    // Exclusion Defaults
    this.exclusionDefaults = const <String, bool>{
      'image': true,
      'formula': true,
      'reference': true,
      'identifier': true,
      'structural': false,
      'table': false,
      'language_match': false,
    },
  });

  factory GlobalSettings.fromJson(Map<String, dynamic> json) => GlobalSettings(
        darkMode: json['darkMode'] ?? false,
        language: json['language'] ?? 'en',
        notifications: json['notifications'] ?? true,
        autoSave: json['autoSave'] ?? true,
        previewFontSize: (json['previewFontSize'] ?? 14.0).toDouble(),
        editFontSize: (json['editFontSize'] ?? 16.0).toDouble(),
        defaultPlatform: json['defaultPlatform'] ?? 'openai',
        platformConfigs: Map<String, dynamic>.from(
            json['platformConfigs'] ?? <dynamic, dynamic>{},),
        parsingEngine: (json['parsingEngine'] as String?)?.isNotEmpty ?? false
            ? json['parsingEngine']
            : 'mineru',
        ocrLanguage: json['ocrLanguage'] ?? 'auto',
        formulaOcr: json['formulaOcr'] ?? true,
        tableOcr: json['tableOcr'] ?? true,
        parsingChunkSize: json['parsingChunkSize'] ?? 1000,
        parsingConcurrent: json['parsingConcurrent'] ?? 3,
        parsingTimeout: json['parsingTimeout'] ?? 300,
        pdfSplitMaxPages: json['pdfSplitMaxPages'] ?? 100,
        pdfSplitMaxWorkers: json['pdfSplitMaxWorkers'] ?? 2,
        requestRetryCount: json['requestRetryCount'] ?? 2,
        useGlobalGlossary: json['useGlobalGlossary'] ?? false,
        globalGlossaryFile: json['globalGlossaryFile'] ?? '',
        glossaryGenerateEnable: json['glossaryGenerateEnable'] ?? true,
        glossaryEntries: List<Map<String, dynamic>>.from(
            json['glossaryEntries'] ?? <dynamic>[],),
        defaultTranslationPrompt: json['defaultTranslationPrompt'] ?? '',
        defaultAnonymizationPrompt: json['defaultAnonymizationPrompt'] ?? '',
        translationPrompts: List<Map<String, dynamic>>.from(
            json['translationPrompts'] ?? <dynamic>[],),
        anonymizationPrompts: List<Map<String, dynamic>>.from(
            json['anonymizationPrompts'] ?? <dynamic>[],),
        customPrompts: List<Map<String, dynamic>>.from(
            json['customPrompts'] ?? <dynamic>[],),
        translationEngine: json['translationEngine'] ?? 'openai',
        translationQuality: json['translationQuality'] ?? 'balanced',
        skipTranslation: json['skipTranslation'] ?? false,
        useGlossary: json['useGlossary'] ?? false,
        usePrompt: json['usePrompt'] ?? false,
        temperature: (json['temperature'] ?? 0.3).toDouble(),
        thinking: json['thinking'] ?? 'disable',
        retry: json['retry'] ?? 3,
        segmentAutoRetryRounds: json['segment_auto_retry_rounds'] ?? 3,
        customPrompt: json['customPrompt'],
        anonymizationEngine: json['anonymizationEngine'] ?? 'presidio',
        entityTypes: List<String>.from(
          json['entityTypes'] ??
              <dynamic>['EMAIL_ADDRESS', 'PHONE_NUMBER', 'PERSON'],
        ),
        anonymizeMode: json['anonymizeMode'] ?? 'placeholder',
        anonymizeConfidence: (json['anonymizeConfidence'] ?? 0.6).toDouble(),
        customPlaceholder: json['customPlaceholder'] ?? '[REDACTED]',
        exclusionDefaults: Map<String, bool>.from(
          json['exclusionDefaults'] ??
              const <String, bool>{
                'image': true,
                'formula': true,
                'reference': true,
                'identifier': true,
                'structural': false,
                'table': false,
                'language_match': false,
              },
        ),
      );
  // General Settings (立即生效)
  final bool darkMode;
  final String language;
  final bool notifications;
  final bool autoSave;
  final double previewFontSize; // Font size for preview (source/target text)
  final double editFontSize; // Font size for editing translated segments

  // AI Platform Settings (立即生效)
  final String defaultPlatform;
  final Map<String, dynamic> platformConfigs;

  // Parsing Engine Settings (立即生效)
  final String parsingEngine;
  final String ocrLanguage;
  final bool formulaOcr;
  final bool tableOcr;
  final int parsingChunkSize;
  final int parsingConcurrent;
  final int parsingTimeout;
  final int pdfSplitMaxPages;
  final int pdfSplitMaxWorkers;
  final int requestRetryCount;

  // Glossary Settings (新任务生效)
  final bool useGlobalGlossary;
  final String globalGlossaryFile;
  final bool glossaryGenerateEnable;
  final List<Map<String, dynamic>> glossaryEntries;

  // Prompts Settings (新任务生效)
  final String defaultTranslationPrompt;
  final String defaultAnonymizationPrompt;
  final List<Map<String, dynamic>> translationPrompts;
  final List<Map<String, dynamic>> anonymizationPrompts;
  final List<Map<String, dynamic>> customPrompts;

  // Translation Settings (新任务生效)
  final String translationEngine;
  final String translationQuality;
  final bool skipTranslation;
  final bool useGlossary;
  final bool usePrompt;

  // Detailed Translation Parameters (新任务生效)
  final double temperature;
  final String thinking;
  final int retry;
  /// Queued mode: post-translation failed-segment auto batch rounds (not chunk retry).
  final int segmentAutoRetryRounds;
  final String? customPrompt;

  /// DEPRECATED: chunkSize and concurrent are now per-platform settings.
  /// Kept for backward compatibility (always returns 0).
  int get concurrent => 0;
  int get chunkSize => 0;

  // Anonymization Settings (新任务生效)
  final String anonymizationEngine;
  final List<String> entityTypes;
  final String anonymizeMode;
  final double anonymizeConfidence;
  final String customPlaceholder;

  // Exclusion Defaults (全局生效)
  final Map<String, bool> exclusionDefaults;

  GlobalSettings copyWith({
    // General
    bool? darkMode,
    String? language,
    bool? notifications,
    bool? autoSave,
    double? previewFontSize,
    double? editFontSize,

    // AI Platform
    String? defaultPlatform,
    Map<String, dynamic>? platformConfigs,

    // Parsing Engine
    String? parsingEngine,
    String? ocrLanguage,
    bool? formulaOcr,
    bool? tableOcr,
    int? parsingChunkSize,
    int? parsingConcurrent,
    int? parsingTimeout,
    int? pdfSplitMaxPages,
    int? pdfSplitMaxWorkers,
    int? requestRetryCount,

    // Glossary
    bool? useGlobalGlossary,
    String? globalGlossaryFile,
    bool? glossaryGenerateEnable,
    List<Map<String, dynamic>>? glossaryEntries,

    // Prompts
    String? defaultTranslationPrompt,
    String? defaultAnonymizationPrompt,
    List<Map<String, dynamic>>? translationPrompts,
    List<Map<String, dynamic>>? anonymizationPrompts,
    List<Map<String, dynamic>>? customPrompts,

    // Translation
    String? translationEngine,
    String? translationQuality,
    bool? skipTranslation,
    bool? useGlossary,
    bool? usePrompt,

    // Detailed Translation Parameters
    double? temperature,
    String? thinking,
    int? retry,
    int? segmentAutoRetryRounds,
    String? customPrompt,

    // Anonymization
    String? anonymizationEngine,
    List<String>? entityTypes,
    String? anonymizeMode,
    double? anonymizeConfidence,
    String? customPlaceholder,

    // Exclusion Defaults
    Map<String, bool>? exclusionDefaults,
  }) =>
      GlobalSettings(
        // General
        darkMode: darkMode ?? this.darkMode,
        language: language ?? this.language,
        notifications: notifications ?? this.notifications,
        autoSave: autoSave ?? this.autoSave,
        previewFontSize: previewFontSize ?? this.previewFontSize,
        editFontSize: editFontSize ?? this.editFontSize,

        // AI Platform
        defaultPlatform: defaultPlatform ?? this.defaultPlatform,
        platformConfigs: platformConfigs ?? this.platformConfigs,

        // Parsing Engine
        parsingEngine: parsingEngine ?? this.parsingEngine,
        ocrLanguage: ocrLanguage ?? this.ocrLanguage,
        formulaOcr: formulaOcr ?? this.formulaOcr,
        tableOcr: tableOcr ?? this.tableOcr,
        parsingChunkSize: parsingChunkSize ?? this.parsingChunkSize,
        parsingConcurrent: parsingConcurrent ?? this.parsingConcurrent,
        parsingTimeout: parsingTimeout ?? this.parsingTimeout,
        pdfSplitMaxPages: pdfSplitMaxPages ?? this.pdfSplitMaxPages,
        pdfSplitMaxWorkers: pdfSplitMaxWorkers ?? this.pdfSplitMaxWorkers,
        requestRetryCount: requestRetryCount ?? this.requestRetryCount,

        // Glossary
        useGlobalGlossary: useGlobalGlossary ?? this.useGlobalGlossary,
        globalGlossaryFile: globalGlossaryFile ?? this.globalGlossaryFile,
        glossaryGenerateEnable:
            glossaryGenerateEnable ?? this.glossaryGenerateEnable,
        glossaryEntries: glossaryEntries ?? this.glossaryEntries,

        // Prompts
        defaultTranslationPrompt:
            defaultTranslationPrompt ?? this.defaultTranslationPrompt,
        defaultAnonymizationPrompt:
            defaultAnonymizationPrompt ?? this.defaultAnonymizationPrompt,
        translationPrompts: translationPrompts ?? this.translationPrompts,
        anonymizationPrompts: anonymizationPrompts ?? this.anonymizationPrompts,
        customPrompts: customPrompts ?? this.customPrompts,

        // Translation
        translationEngine: translationEngine ?? this.translationEngine,
        translationQuality: translationQuality ?? this.translationQuality,
        skipTranslation: skipTranslation ?? this.skipTranslation,
        useGlossary: useGlossary ?? this.useGlossary,
        usePrompt: usePrompt ?? this.usePrompt,

        // Detailed Translation Parameters
        temperature: temperature ?? this.temperature,
        thinking: thinking ?? this.thinking,
        retry: retry ?? this.retry,
        segmentAutoRetryRounds:
            segmentAutoRetryRounds ?? this.segmentAutoRetryRounds,
        customPrompt: customPrompt ?? this.customPrompt,

        // Anonymization
        anonymizationEngine: anonymizationEngine ?? this.anonymizationEngine,
        entityTypes: entityTypes ?? this.entityTypes,
        anonymizeMode: anonymizeMode ?? this.anonymizeMode,
        anonymizeConfidence: anonymizeConfidence ?? this.anonymizeConfidence,
        customPlaceholder: customPlaceholder ?? this.customPlaceholder,

        // Exclusion Defaults
        exclusionDefaults: exclusionDefaults ?? this.exclusionDefaults,
      );

  Map<String, dynamic> toJson() => <String, dynamic>{
        'darkMode': darkMode,
        'language': language,
        'notifications': notifications,
        'autoSave': autoSave,
        'previewFontSize': previewFontSize,
        'editFontSize': editFontSize,
        'defaultPlatform': defaultPlatform,
        'platformConfigs': platformConfigs,
        'parsingEngine': parsingEngine,
        'ocrLanguage': ocrLanguage,
        'parsingChunkSize': parsingChunkSize,
        'parsingConcurrent': parsingConcurrent,
        'parsingTimeout': parsingTimeout,
        'pdfSplitMaxPages': pdfSplitMaxPages,
        'pdfSplitMaxWorkers': pdfSplitMaxWorkers,
        'requestRetryCount': requestRetryCount,
        'useGlobalGlossary': useGlobalGlossary,
        'globalGlossaryFile': globalGlossaryFile,
        'glossaryGenerateEnable': glossaryGenerateEnable,
        'glossaryEntries': glossaryEntries,
        'defaultTranslationPrompt': defaultTranslationPrompt,
        'defaultAnonymizationPrompt': defaultAnonymizationPrompt,
        'translationPrompts': translationPrompts,
        'anonymizationPrompts': anonymizationPrompts,
        'customPrompts': customPrompts,
        'translationEngine': translationEngine,
        'translationQuality': translationQuality,
        'skipTranslation': skipTranslation,
        'useGlossary': useGlossary,
        'usePrompt': usePrompt,
        'temperature': temperature,
        'thinking': thinking,
        'retry': retry,
        'segment_auto_retry_rounds': segmentAutoRetryRounds,
        'customPrompt': customPrompt,
        'anonymizationEngine': anonymizationEngine,
        'entityTypes': entityTypes,
        'anonymizeMode': anonymizeMode,
        'anonymizeConfidence': anonymizeConfidence,
        'customPlaceholder': customPlaceholder,
        'exclusionDefaults': exclusionDefaults,
      };
}

class GlobalSettingsNotifier extends StateNotifier<GlobalSettings> {
  GlobalSettingsNotifier() : super(const GlobalSettings()) {
    // Load settings from local cache immediately (async, non-blocking)
    // So that persisted UI language and other prefs apply as soon as load completes
    reloadSettings();
  }
  final SettingsService _settingsService = SettingsService();
  bool _isLoading = false;

  /// Reload settings from local cache and sync with backend.
  /// Call this after login to ensure the latest user settings are fetched.
  Future<void> reloadSettings() async {
    if (_isLoading) return;
    _isLoading = true;
    try {
      final prefs = await SharedPreferences.getInstance();
      final settingsJson = prefs.getString('global_settings');
      bool hadLocalSettings = false;
      if (settingsJson != null) {
        hadLocalSettings = true;
        final settingsMap = json.decode(settingsJson);
        state = GlobalSettings.fromJson(settingsMap);
      }

      // Log detected system locale for diagnostics
      if (kDebugMode) {
        final ui.Locale systemLocale =
            ui.PlatformDispatcher.instance.locale;
        final String sysLang = systemLocale.languageCode.toLowerCase();
        final String sysCountry =
            (systemLocale.countryCode ?? '').toUpperCase();
        final String sysTag = sysCountry.isNotEmpty
            ? '${sysLang}_$sysCountry'
            : sysLang;
        print(
          '🌐 [SETTINGS] Detected system locale="$sysTag"',
        );
      }

      // Sync with backend to ensure we have the latest user settings
      try {
        final configService = ConfigService();
        final appConfig = await configService.getAppConfig();
        if (appConfig != null) {
          // Map backend fields to frontend fields
          final backendSettings = <String, dynamic>{};

          // Map other translation settings
          if (appConfig.containsKey('translator_temperature')) {
            backendSettings['temperature'] =
                appConfig['translator_temperature'];
          }
          if (appConfig.containsKey('translator_thinking_mode')) {
            backendSettings['thinking'] = appConfig['translator_thinking_mode'];
          }
          if (appConfig.containsKey('retry')) {
            backendSettings['retry'] = appConfig['retry'];
          }
          if (appConfig.containsKey('segment_auto_retry_rounds')) {
            backendSettings['segment_auto_retry_rounds'] =
                appConfig['segment_auto_retry_rounds'];
          } else if (appConfig
              .containsKey('translator_segment_auto_retry_rounds')) {
            backendSettings['segment_auto_retry_rounds'] =
                appConfig['translator_segment_auto_retry_rounds'];
          }

          // Map exclusion_defaults from backend (global config)
          if (appConfig.containsKey('exclusion_defaults') &&
              appConfig['exclusion_defaults'] is Map) {
            backendSettings['exclusionDefaults'] =
                Map<String, bool>.from(appConfig['exclusion_defaults'] as Map);
          }

          // Map parsing engine settings from backend (critical: backend is source of truth)
          if (appConfig.containsKey('parsingEngine')) {
            backendSettings['parsingEngine'] = appConfig['parsingEngine'];
          } else if (appConfig.containsKey('translator_convert_engine')) {
            backendSettings['parsingEngine'] = appConfig['translator_convert_engine'];
          }
          if (appConfig.containsKey('formulaOcr')) {
            backendSettings['formulaOcr'] = appConfig['formulaOcr'];
          } else if (appConfig.containsKey('translator_formula_ocr')) {
            backendSettings['formulaOcr'] = appConfig['translator_formula_ocr'];
          }
          if (appConfig.containsKey('tableOcr')) {
            backendSettings['tableOcr'] = appConfig['tableOcr'];
          } else if (appConfig.containsKey('translator_table_ocr')) {
            backendSettings['tableOcr'] = appConfig['translator_table_ocr'];
          }
          // Map PDF split settings from backend
          if (appConfig.containsKey('translator_pdf_split_max_pages')) {
            backendSettings['pdfSplitMaxPages'] = appConfig['translator_pdf_split_max_pages'];
          }
          if (appConfig.containsKey('translator_pdf_split_max_workers')) {
            backendSettings['pdfSplitMaxWorkers'] = appConfig['translator_pdf_split_max_workers'];
          }
          if (appConfig.containsKey('translator_request_retry_count')) {
            backendSettings['requestRetryCount'] = appConfig['translator_request_retry_count'];
          }

          // Restore UI language from backend or system locale on first run
          String backendUiLanguage = '';
          if (appConfig.containsKey('ui_language') &&
              appConfig['ui_language'] is String) {
            backendUiLanguage = appConfig['ui_language'] as String? ?? '';
            if (kDebugMode) {
              print(
                '🌐 [SETTINGS] Backend ui_language="$backendUiLanguage", '
                'current language="${state.language}"',
              );
            }
          }
          if (backendUiLanguage.isNotEmpty) {
            // Backend already has ui_language, prefer backend value
            backendSettings['language'] = backendUiLanguage;
          } else if (!hadLocalSettings) {
            // First run with no local language settings: derive from system locale
            final ui.Locale systemLocale =
                ui.PlatformDispatcher.instance.locale;
            final String sysLang = systemLocale.languageCode.toLowerCase();
            const List<String> supportedLangs = <String>['zh', 'en', 'ja', 'ko'];
            final String initialLang =
                supportedLangs.contains(sysLang) ? sysLang : 'en';
            if (kDebugMode) {
              print(
                '🌐 [SETTINGS] No backend/local ui_language, using system locale '
                '"$sysLang" -> initial "$initialLang"',
              );
            }
            backendSettings['language'] = initialLang;
          }

          // Merge backend settings into current state (backend settings take priority)
          if (backendSettings.isNotEmpty) {
            final mergedSettings = state.toJson();
            mergedSettings.addAll(backendSettings);
            state = GlobalSettings.fromJson(mergedSettings);

            if (kDebugMode) {
              print(
                '🌐 [SETTINGS] Merged language in GlobalSettings is '
                '"${state.language}"',
              );
            }

            // Save merged settings back to local cache
            await _saveSettings();
          }
        }
      } catch (e) {
        if (kDebugMode) {
          print('⚠️ [SETTINGS] Error syncing settings from backend: $e');
        }
        // Continue with local cache if backend sync fails
      }
    } catch (e) {
      if (kDebugMode) {
        print('⚠️ [SETTINGS] Error loading settings: $e');
      }
    } finally {
      _isLoading = false;
    }
  }

  // 保存设置到本地缓存（立即）
  Future<void> _saveSettings() async {
    try {
      final prefs = await SharedPreferences.getInstance();
      final settingsJson = json.encode(state.toJson());
      await prefs.setString('global_settings', settingsJson);
    } catch (e) {
      print('Error saving settings: $e');
    }
  }

  // 立即生效的设置更新方法
  Future<void> updateGeneralSettings({
    bool? darkMode,
    String? language,
    bool? notifications,
    bool? autoSave,
    double? previewFontSize,
    double? editFontSize,
  }) async {
    state = state.copyWith(
      darkMode: darkMode,
      language: language,
      notifications: notifications,
      autoSave: autoSave,
      previewFontSize: previewFontSize,
      editFontSize: editFontSize,
    );
    await _saveSettings();

    // Persist UI language to backend so it survives restart and syncs across clients
    if (language != null) {
      await _settingsService.saveSetting('', 'ui_language', language);
    }

    // Save individual keys to backend
    if (previewFontSize != null) {
      await _settingsService.saveSetting(
        '',
        'previewFontSize',
        previewFontSize,
      );
    }
    if (editFontSize != null) {
      await _settingsService.saveSetting('', 'editFontSize', editFontSize);
    }
  }

  /// Update UI language only on this client (local cache), without syncing to backend.
  Future<void> updateUiLanguageLocalOnly(String language) async {
    state = state.copyWith(language: language);
    await _saveSettings();
  }

  Future<void> updateAIPlatformSettings({
    String? defaultPlatform,
    Map<String, dynamic>? platformConfigs,
  }) async {
    // 1. Immediately update local state
    state = state.copyWith(
      defaultPlatform: defaultPlatform,
      platformConfigs: platformConfigs,
    );

    // 2. Save entire state to local cache (for app restart recovery)
    await _saveSettings();

    // 3. Trigger batch save to backend (with debounce)
    // Note: SettingsService will also cache individual keys, but that's fine
    // as we need both whole state (for recovery) and individual keys (for quick access)
    if (defaultPlatform != null) {
      await _settingsService.saveSetting(
        '',
        'ai_platforms_default_platform',
        defaultPlatform,
      );
    }
  }

  Future<void> updateParsingEngineSettings({
    String? parsingEngine,
    String? ocrLanguage,
    bool? formulaOcr,
    bool? tableOcr,
    int? parsingChunkSize,
    int? parsingConcurrent,
    int? parsingTimeout,
    int? pdfSplitMaxPages,
    int? pdfSplitMaxWorkers,
    int? requestRetryCount,
  }) async {
    // 1. Immediately update local state
    state = state.copyWith(
      parsingEngine: parsingEngine,
      ocrLanguage: ocrLanguage,
      formulaOcr: formulaOcr,
      tableOcr: tableOcr,
      parsingChunkSize: parsingChunkSize,
      parsingConcurrent: parsingConcurrent,
      parsingTimeout: parsingTimeout,
      pdfSplitMaxPages: pdfSplitMaxPages,
      pdfSplitMaxWorkers: pdfSplitMaxWorkers,
      requestRetryCount: requestRetryCount,
    );

    // 2. Save entire state to local cache (for app restart recovery)
    await _saveSettings();

    // 3. Trigger batch save to backend (with debounce)
    if (parsingEngine != null) {
      await _settingsService.saveSetting('', 'parsingEngine', parsingEngine);
      // Map to backend key if needed
      if (parsingEngine == 'mineru' || parsingEngine == 'mineru_local') {
        await _settingsService.saveSetting(
          '',
          'translator_convert_engine',
          parsingEngine,
        );
      }
    }
    if (ocrLanguage != null) {
      await _settingsService.saveSetting('', 'ocrLanguage', ocrLanguage);
    }
    if (formulaOcr != null) {
      await _settingsService.saveSetting('', 'translator_formula_ocr', formulaOcr);
    }
    if (tableOcr != null) {
      await _settingsService.saveSetting('', 'translator_table_ocr', tableOcr);
    }
    if (pdfSplitMaxPages != null) {
      await _settingsService.saveSetting('', 'translator_pdf_split_max_pages', pdfSplitMaxPages);
    }
    if (pdfSplitMaxWorkers != null) {
      await _settingsService.saveSetting('', 'translator_pdf_split_max_workers', pdfSplitMaxWorkers);
    }
    if (requestRetryCount != null) {
      await _settingsService.saveSetting('', 'translator_request_retry_count', requestRetryCount);
    }
  }

  // 新任务生效的设置更新方法
  Future<void> updateGlossarySettings({
    bool? useGlobalGlossary,
    String? globalGlossaryFile,
    bool? glossaryGenerateEnable,
    List<Map<String, dynamic>>? glossaryEntries,
  }) async {
    state = state.copyWith(
      useGlobalGlossary: useGlobalGlossary,
      globalGlossaryFile: globalGlossaryFile,
      glossaryGenerateEnable: glossaryGenerateEnable,
      glossaryEntries: glossaryEntries,
    );
    await _saveSettings();
  }

  Future<void> updatePromptsSettings({
    String? defaultTranslationPrompt,
    String? defaultAnonymizationPrompt,
    List<Map<String, dynamic>>? translationPrompts,
    List<Map<String, dynamic>>? anonymizationPrompts,
    List<Map<String, dynamic>>? customPrompts,
  }) async {
    state = state.copyWith(
      defaultTranslationPrompt: defaultTranslationPrompt,
      defaultAnonymizationPrompt: defaultAnonymizationPrompt,
      translationPrompts: translationPrompts,
      anonymizationPrompts: anonymizationPrompts,
      customPrompts: customPrompts,
    );
    await _saveSettings();
  }

  Future<void> updateTranslationSettings({
    String? translationEngine,
    String? translationQuality,
    bool? skipTranslation,
    bool? useGlossary,
    bool? usePrompt,
    double? temperature,
    String? thinking,
    int? retry,
    int? segmentAutoRetryRounds,
    String? customPrompt,
  }) async {
    // 1. Immediately update local state (for fast UI response)
    state = state.copyWith(
      translationEngine: translationEngine,
      translationQuality: translationQuality,
      skipTranslation: skipTranslation,
      useGlossary: useGlossary,
      usePrompt: usePrompt,
      temperature: temperature,
      thinking: thinking,
      retry: retry,
      segmentAutoRetryRounds: segmentAutoRetryRounds,
      customPrompt: customPrompt,
    );

    // 2. Save entire state to local cache (for app restart recovery)
    await _saveSettings();

    // 3. Trigger batch save to backend (with debounce)
    // Note: SettingsService handles individual key caching internally
    if (translationEngine != null) {
      await _settingsService.saveSetting(
        '',
        'translationEngine',
        translationEngine,
      );
    }
    if (translationQuality != null) {
      await _settingsService.saveSetting(
        '',
        'translationQuality',
        translationQuality,
      );
    }
    if (skipTranslation != null) {
      await _settingsService.saveSetting(
        '',
        'skipTranslation',
        skipTranslation,
      );
    }
    if (useGlossary != null) {
      await _settingsService.saveSetting('', 'useGlossary', useGlossary);
    }
    if (usePrompt != null) {
      await _settingsService.saveSetting('', 'usePrompt', usePrompt);
    }
    if (temperature != null) {
      await _settingsService.saveSetting('', 'temperature', temperature);
    }
    if (thinking != null) {
      await _settingsService.saveSetting('', 'thinking', thinking);
    }
    if (retry != null) {
      await _settingsService.saveSetting('', 'retry', retry);
    }
    if (segmentAutoRetryRounds != null) {
      await _settingsService.saveSetting(
        '',
        'segment_auto_retry_rounds',
        segmentAutoRetryRounds,
      );
    }
    if (customPrompt != null) {
      await _settingsService.saveSetting('', 'customPrompt', customPrompt);
    }
  }

  Future<void> updateAnonymizationSettings({
    String? anonymizationEngine,
    List<String>? entityTypes,
    String? anonymizeMode,
    double? anonymizeConfidence,
    String? customPlaceholder,
  }) async {
    state = state.copyWith(
      anonymizationEngine: anonymizationEngine,
      entityTypes: entityTypes,
      anonymizeMode: anonymizeMode,
      anonymizeConfidence: anonymizeConfidence,
      customPlaceholder: customPlaceholder,
    );
    await _saveSettings();
  }

  // Update exclusion default settings (global, immediate effect)
  Future<void> updateExclusionDefaults({
    Map<String, bool>? exclusionDefaults,
  }) async {
    if (exclusionDefaults == null) return;

    // 1. Update local state
    state = state.copyWith(exclusionDefaults: exclusionDefaults);

    // 2. Save to local cache
    await _saveSettings();

    // 3. Sync to backend (global setting)
    await _settingsService.saveSetting(
      '',
      'exclusion_defaults',
      exclusionDefaults,
    );
  }

  // 重置所有设置
  Future<void> resetAllSettings() async {
    state = const GlobalSettings();
    await _saveSettings();
  }

  // 获取新任务的默认设置
  GlobalSettings getNewTaskDefaults() => state;
}
