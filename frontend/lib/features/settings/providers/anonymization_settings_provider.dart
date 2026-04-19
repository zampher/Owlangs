// SPDX-FileCopyrightText: 2025 QinHan
// SPDX-License-Identifier: MPL-2.0

import 'dart:convert';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:shared_preferences/shared_preferences.dart';
import '../models/anonymization_settings_state.dart';
import '../models/language_model_config.dart';
import '../../../shared/services/anonymization_settings_service.dart';

final StateNotifierProvider<AnonymizationSettingsNotifier,
        AnonymizationSettingsState> anonymizationSettingsProvider =
    StateNotifierProvider<AnonymizationSettingsNotifier,
        AnonymizationSettingsState>(
  (
    StateNotifierProviderRef<AnonymizationSettingsNotifier, AnonymizationSettingsState> ref,
  ) =>
      AnonymizationSettingsNotifier(),
);

class AnonymizationSettingsNotifier
    extends StateNotifier<AnonymizationSettingsState> {
  AnonymizationSettingsNotifier() : super(const AnonymizationSettingsState()) {
    _loadSettings();
    _loadLanguageModels();
  }
  final AnonymizationSettingsService _service = AnonymizationSettingsService();
  static const String _storageKey = 'anonymization_settings';

  // Store model options from backend
  Map<String, List<String>> _modelOptions = <String, List<String>>{};

  /// Load settings from local storage
  Future<void> _loadSettings() async {
    try {
      final SharedPreferences prefs = await SharedPreferences.getInstance();
      final String? settingsJson = prefs.getString(_storageKey);
      if (settingsJson != null) {
        final settingsMap = json.decode(settingsJson);
        state = AnonymizationSettingsState.fromJson(settingsMap);
      }
    } catch (e) {
      print('Error loading anonymization settings: $e');
    }
  }

  /// Save settings to local storage
  Future<void> _saveSettings() async {
    try {
      final SharedPreferences prefs = await SharedPreferences.getInstance();
      final String settingsJson = json.encode(state.toJson());
      await prefs.setString(_storageKey, settingsJson);
    } catch (e) {
      print('Error saving anonymization settings: $e');
    }
  }

  /// Load language models from backend
  Future<void> _loadLanguageModels() async {
    state = state.copyWith(isLoading: true);
    try {
      final Map<String, dynamic> result = await _service.getLanguageModels();
      if (result['success'] == true) {
        final Map<String, dynamic> models =
            result['models'] as Map<String, dynamic>? ?? <String, dynamic>{};
        final Map<String, dynamic> options =
            result['options'] as Map<String, dynamic>? ?? <String, dynamic>{};

        // Store model options in state (all available languages)
        final Map<String, List<String>> availableModelOptions = options.map(
          (String key, value) =>
              MapEntry(key, List<String>.from(value as List)),
        );

        // Also store in local _modelOptions for backward compatibility
        _modelOptions = Map<String, List<String>>.from(availableModelOptions);

        // Store model status
        final Map<String, dynamic> modelStatusData =
            result['model_status'] as Map<String, dynamic>? ??
                <String, dynamic>{};
        final Map<String, Map<String, ModelStatus>> modelStatus =
            modelStatusData.map(
          (String lang, statusMap) => MapEntry(
            lang,
            (statusMap as Map<String, dynamic>).map(
              (String model, status) => MapEntry(
                model,
                ModelStatus.fromJson(status as Map<String, dynamic>),
              ),
            ),
          ),
        );

        // Convert backend models to LanguageModelConfig (only configured languages)
        final Map<String, LanguageModelConfig> languageConfigs =
            <String, LanguageModelConfig>{};
        for (final MapEntry<String, dynamic> entry in models.entries) {
          final String lang = entry.key;
          final Map<String, dynamic> config =
              entry.value as Map<String, dynamic>;
          languageConfigs[lang] = LanguageModelConfig(
            preferred: config['preferred'] ?? '',
            modelsDir: config['models_dir'],
            fallback: config['fallback'] ?? true,
          );
        }

        // Auto-select highest priority model for languages without configuration
        // Priority: trf > lg > md > sm
        for (final String lang in availableModelOptions.keys) {
          if (!languageConfigs.containsKey(lang)) {
            // Find the highest priority installed model
            final List<String> modelOptions =
                availableModelOptions[lang] ?? <String>[];
            final Map<String, ModelStatus> langModelStatus =
                modelStatus[lang] ?? <String, ModelStatus>{};

            // Priority order: trf > lg > md > sm
            final List<String> priorityOrder = <String>[
              'trf',
              'lg',
              'md',
              'sm',
            ];
            String? selectedModel;

            for (final String priority in priorityOrder) {
              // Find models with this priority suffix (e.g., _trf, _lg, _md, _sm)
              for (final String model in modelOptions) {
                // Check if model name contains the priority suffix
                // e.g., "zh_core_web_trf" contains "_trf"
                if (model.contains('_$priority')) {
                  final ModelStatus? status = langModelStatus[model];
                  if (status?.installed ?? false) {
                    selectedModel = model;
                    break;
                  }
                }
              }
              if (selectedModel != null) break;
            }

            // If no installed model found, select the first available model (highest priority)
            if (selectedModel == null && modelOptions.isNotEmpty) {
              selectedModel = modelOptions.first;
            }

            // Set fixed models directory for desktop version
            const String fixedModelsDir =
                r'C:\ProgramData\Owlangs\models\spacy';

            if (selectedModel != null) {
              languageConfigs[lang] = LanguageModelConfig(
                preferred: selectedModel,
                modelsDir: fixedModelsDir,
              );
            }
          } else {
            // Update existing configs to use fixed models directory
            final LanguageModelConfig existingConfig = languageConfigs[lang]!;
            const String fixedModelsDir =
                r'C:\ProgramData\Owlangs\models\spacy';
            languageConfigs[lang] =
                existingConfig.copyWith(modelsDir: fixedModelsDir);
          }
        }

        // Merge with existing state (preserve local changes)
        final Map<String, LanguageModelConfig> mergedConfigs =
            Map<String, LanguageModelConfig>.from(state.languageConfigs);
        mergedConfigs.addAll(languageConfigs);

        state = state.copyWith(
          languageConfigs: mergedConfigs,
          availableModelOptions: availableModelOptions,
          modelStatus: modelStatus,
          isLoading: false,
        );
        await _saveSettings();
      } else {
        state = state.copyWith(
          isLoading: false,
          errorMessage: result['message'] ?? 'Failed to load language models',
        );
      }
    } catch (e) {
      state = state.copyWith(
        isLoading: false,
        errorMessage: 'Error loading language models: $e',
      );
    }
  }

  /// Get model options for a language
  List<String> getModelOptionsForLanguage(String language) =>
      _modelOptions[language] ?? <String>[];

  /// Update language model configuration
  Future<void> updateLanguageModelConfig(
    String language,
    LanguageModelConfig config,
  ) async {
    // Update local state immediately
    final Map<String, LanguageModelConfig> updatedConfigs =
        Map<String, LanguageModelConfig>.from(state.languageConfigs);
    updatedConfigs[language] = config;
    state = state.copyWith(languageConfigs: updatedConfigs);
    await _saveSettings();

    // Save to backend
    try {
      final Map<String, dynamic> result =
          await _service.saveLanguageModel(language, config);
      if (result['success'] != true) {
        state = state.copyWith(errorMessage: result['message']);
      }
    } catch (e) {
      state = state.copyWith(errorMessage: 'Error saving to backend: $e');
    }
  }

  /// Update preferred engine (deprecated - always uses Presidio)
  @Deprecated(
    'Engine is fixed to Presidio, this method is kept for compatibility',
  )
  Future<void> updatePreferredEngine(String engine) async {
    // Always use Presidio, ignore the parameter
    state = state.copyWith(preferredEngine: 'presidio');
    await _saveSettings();
  }

  /// Update default language
  Future<void> updateDefaultLanguage(String language) async {
    state = state.copyWith(defaultLanguage: language);
    await _saveSettings();
  }

  /// Update confidence threshold
  Future<void> updateConfidenceThreshold(double threshold) async {
    state = state.copyWith(confidenceThreshold: threshold);
    await _saveSettings();
  }

  /// Test model
  Future<void> testModel(
    String language,
    String modelName,
    String? modelsDir,
    String? testText,
  ) async {
    state = state.copyWith(
      testState: state.testState.copyWith(isTesting: true),
    );

    try {
      final Map<String, dynamic> result =
          await _service.testModel(language, modelName, modelsDir, testText);
      final TestResult testResult = TestResult(
        success: result['success'] ?? false,
        message: result['message'] ?? '',
        entitiesCount: result['entitiesCount'],
        remediation: result['remediation'] != null
            ? List<String>.from(result['remediation'])
            : null,
      );

      state = state.copyWith(
        testState: state.testState.copyWith(
          isTesting: false,
          result: testResult,
        ),
      );
    } catch (e) {
      state = state.copyWith(
        testState: state.testState.copyWith(
          isTesting: false,
          result: TestResult(
            success: false,
            message: 'Error testing model: $e',
          ),
        ),
      );
    }
  }

  /// Download model
  Future<void> downloadModel(
    String language,
    String modelName,
    String? modelsDir, {
    Function(double)? onProgress,
  }) async {
    state = state.copyWith(
      downloadState: state.downloadState.copyWith(
        isDownloading: true,
        modelName: modelName,
        progress: 0,
      ),
    );

    try {
      // Simulate progress (backend might not support progress callback)
      if (onProgress != null) {
        for (var i = 0; i <= 100; i += 10) {
          await Future.delayed(const Duration(milliseconds: 200));
          onProgress(i.toDouble());
          state = state.copyWith(
            downloadState: state.downloadState.copyWith(progress: i.toDouble()),
          );
        }
      }

      final Map<String, dynamic> result =
          await _service.downloadModel(language, modelName, modelsDir);

      if (result['success'] == true) {
        state = state.copyWith(
          downloadState: state.downloadState.copyWith(
            isDownloading: false,
            progress: 100,
          ),
        );

        // Refresh model status after successful download
        await _refreshModelStatus(language, modelName);
      } else {
        state = state.copyWith(
          downloadState: state.downloadState.copyWith(
            isDownloading: false,
            errorMessage: result['message'] ?? 'Download failed',
          ),
        );
      }
    } catch (e) {
      state = state.copyWith(
        downloadState: state.downloadState.copyWith(
          isDownloading: false,
          errorMessage: 'Error downloading model: $e',
        ),
      );
    }
  }

  /// Refresh model status for a specific model
  Future<void> _refreshModelStatus(String language, String modelName) async {
    try {
      // Reload language models to get updated status
      await _loadLanguageModels();
    } catch (e) {
      // If reload fails, manually update the status
      final Map<String, Map<String, ModelStatus>> updatedStatus =
          Map<String, Map<String, ModelStatus>>.from(state.modelStatus);
      if (!updatedStatus.containsKey(language)) {
        updatedStatus[language] = <String, ModelStatus>{};
      }
      updatedStatus[language]![modelName] = const ModelStatus(
        installed: true,
        status: 'installed',
      );
      state = state.copyWith(modelStatus: updatedStatus);
    }
  }

  /// Refresh all model statuses
  Future<void> refreshAllModelStatuses() async {
    await _loadLanguageModels();
  }

  /// Clear test state
  void clearTestState() {
    state = state.copyWith(
      testState: const TestState(),
    );
  }

  /// Clear download state
  void clearDownloadState() {
    state = state.copyWith(
      downloadState: const DownloadState(),
    );
  }
}
