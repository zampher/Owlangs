// SPDX-FileCopyrightText: 2025 QinHan
// SPDX-License-Identifier: MPL-2.0

import 'language_model_config.dart';

class DownloadState {
  const DownloadState({
    this.isDownloading = false,
    this.modelName,
    this.progress = 0,
    this.errorMessage,
  });

  factory DownloadState.fromJson(Map<String, dynamic> json) => DownloadState(
        isDownloading: json['isDownloading'] ?? false,
        modelName: json['modelName'],
        progress: (json['progress'] ?? 0).toDouble(),
        errorMessage: json['errorMessage'],
      );
  final bool isDownloading;
  final String? modelName;
  final double progress; // 0-100
  final String? errorMessage;

  DownloadState copyWith({
    bool? isDownloading,
    String? modelName,
    double? progress,
    String? errorMessage,
  }) =>
      DownloadState(
        isDownloading: isDownloading ?? this.isDownloading,
        modelName: modelName ?? this.modelName,
        progress: progress ?? this.progress,
        errorMessage: errorMessage ?? this.errorMessage,
      );

  Map<String, dynamic> toJson() => <String, dynamic>{
        'isDownloading': isDownloading,
        'modelName': modelName,
        'progress': progress,
        'errorMessage': errorMessage,
      };
}

class TestResult {
  const TestResult({
    required this.success,
    required this.message,
    this.entitiesCount,
    this.remediation,
  });

  factory TestResult.fromJson(Map<String, dynamic> json) => TestResult(
        success: json['success'] ?? false,
        message: json['message'] ?? '',
        entitiesCount: json['entitiesCount'],
        remediation: json['remediation'] != null
            ? List<String>.from(json['remediation'])
            : null,
      );
  final bool success;
  final String message;
  final int? entitiesCount;
  final List<String>? remediation;

  Map<String, dynamic> toJson() => <String, dynamic>{
        'success': success,
        'message': message,
        'entitiesCount': entitiesCount,
        'remediation': remediation,
      };
}

class TestState {
  const TestState({
    this.isTesting = false,
    this.result,
  });

  factory TestState.fromJson(Map<String, dynamic> json) => TestState(
        isTesting: json['isTesting'] ?? false,
        result:
            json['result'] != null ? TestResult.fromJson(json['result']) : null,
      );
  final bool isTesting;
  final TestResult? result;

  TestState copyWith({
    bool? isTesting,
    TestResult? result,
  }) =>
      TestState(
        isTesting: isTesting ?? this.isTesting,
        result: result ?? this.result,
      );

  Map<String, dynamic> toJson() => <String, dynamic>{
        'isTesting': isTesting,
        'result': result?.toJson(),
      };
}

class ModelStatus {
  // "installed" | "not_installed"

  const ModelStatus({
    required this.installed,
    required this.status,
  });

  factory ModelStatus.fromJson(Map<String, dynamic> json) => ModelStatus(
        installed: json['installed'] ?? false,
        status: json['status'] ?? 'not_installed',
      );
  final bool installed;
  final String status;

  Map<String, dynamic> toJson() => <String, dynamic>{
        'installed': installed,
        'status': status,
      };
}

class AnonymizationSettingsState {
  const AnonymizationSettingsState({
    this.languageConfigs = const <String, LanguageModelConfig>{},
    this.availableModelOptions = const <String, List<String>>{},
    this.modelStatus = const <String, Map<String, ModelStatus>>{},
    this.preferredEngine = 'presidio',
    this.defaultLanguage = 'zh',
    this.confidenceThreshold = 0.5,
    this.isLoading = false,
    this.errorMessage,
    this.downloadState = const DownloadState(),
    this.testState = const TestState(),
  });

  factory AnonymizationSettingsState.fromJson(Map<String, dynamic> json) {
    final languageConfigsMap =
        json['languageConfigs'] as Map<String, dynamic>? ?? <String, dynamic>{};
    final languageConfigs = languageConfigsMap.map(
      (key, value) => MapEntry(
        key,
        LanguageModelConfig.fromJson(value as Map<String, dynamic>),
      ),
    );

    final availableModelOptionsMap =
        json['availableModelOptions'] as Map<String, dynamic>? ??
            <String, dynamic>{};
    final availableModelOptions = availableModelOptionsMap.map(
      (key, value) => MapEntry(
        key,
        List<String>.from(value as List),
      ),
    );

    final modelStatusMap =
        json['modelStatus'] as Map<String, dynamic>? ?? <String, dynamic>{};
    final modelStatus = modelStatusMap.map(
      (lang, statusMap) => MapEntry(
        lang,
        (statusMap as Map<String, dynamic>).map(
          (model, status) => MapEntry(
            model,
            ModelStatus.fromJson(status as Map<String, dynamic>),
          ),
        ),
      ),
    );

    return AnonymizationSettingsState(
      languageConfigs: languageConfigs,
      availableModelOptions: availableModelOptions,
      modelStatus: modelStatus,
      preferredEngine: json['preferredEngine'] ?? 'presidio',
      defaultLanguage: json['defaultLanguage'] ?? 'zh',
      confidenceThreshold: (json['confidenceThreshold'] ?? 0.5).toDouble(),
      downloadState: json['downloadState'] != null
          ? DownloadState.fromJson(json['downloadState'])
          : const DownloadState(),
      testState: json['testState'] != null
          ? TestState.fromJson(json['testState'])
          : const TestState(),
    );
  }
  final Map<String, LanguageModelConfig> languageConfigs; // language -> config
  final Map<String, List<String>>
      availableModelOptions; // language -> list of model names
  final Map<String, Map<String, ModelStatus>>
      modelStatus; // language -> model_name -> status
  final String preferredEngine; // "presidio" | "simple"
  final String defaultLanguage; // "zh" | "en" | ...
  final double confidenceThreshold;
  final bool isLoading;
  final String? errorMessage;

  // Download state
  final DownloadState downloadState;

  // Test state
  final TestState testState;

  AnonymizationSettingsState copyWith({
    Map<String, LanguageModelConfig>? languageConfigs,
    Map<String, List<String>>? availableModelOptions,
    Map<String, Map<String, ModelStatus>>? modelStatus,
    String? preferredEngine,
    String? defaultLanguage,
    double? confidenceThreshold,
    bool? isLoading,
    String? errorMessage,
    DownloadState? downloadState,
    TestState? testState,
  }) =>
      AnonymizationSettingsState(
        languageConfigs: languageConfigs ?? this.languageConfigs,
        availableModelOptions:
            availableModelOptions ?? this.availableModelOptions,
        modelStatus: modelStatus ?? this.modelStatus,
        preferredEngine: preferredEngine ?? this.preferredEngine,
        defaultLanguage: defaultLanguage ?? this.defaultLanguage,
        confidenceThreshold: confidenceThreshold ?? this.confidenceThreshold,
        isLoading: isLoading ?? this.isLoading,
        errorMessage: errorMessage ?? this.errorMessage,
        downloadState: downloadState ?? this.downloadState,
        testState: testState ?? this.testState,
      );

  Map<String, dynamic> toJson() => <String, dynamic>{
        'languageConfigs': languageConfigs.map(
          (key, value) => MapEntry(key, value.toJson()),
        ),
        'availableModelOptions': availableModelOptions,
        'modelStatus': modelStatus.map(
          (lang, statusMap) => MapEntry(
            lang,
            statusMap.map(
              (model, status) => MapEntry(model, status.toJson()),
            ),
          ),
        ),
        'preferredEngine': preferredEngine,
        'defaultLanguage': defaultLanguage,
        'confidenceThreshold': confidenceThreshold,
        'downloadState': downloadState.toJson(),
        'testState': testState.toJson(),
      };
}
