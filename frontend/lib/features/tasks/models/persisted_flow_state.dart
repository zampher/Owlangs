// SPDX-FileCopyrightText: 2025 QinHan
// SPDX-License-Identifier: MPL-2.0

import '../models/task.dart';
import '../models/flow.dart';

/// Download information for persistence
class PersistedDownloadInfo {
  // Flow creation time (for 30-day expiry calculation)

  PersistedDownloadInfo({
    required this.taskId,
    required this.fileType,
    this.flowCreatedAt,
  });

  factory PersistedDownloadInfo.fromJson(Map<String, dynamic> json) =>
      PersistedDownloadInfo(
        taskId: json['taskId'] as String,
        fileType: json['fileType'] as String,
        flowCreatedAt: json['flowCreatedAt'] != null
            ? DateTime.parse(json['flowCreatedAt'] as String)
            : null,
      );
  final String taskId;
  final String fileType;
  final DateTime? flowCreatedAt;

  /// Build download URL dynamically (from config base URL)
  String buildDownloadUrl(String baseUrl) =>
      '$baseUrl/service/download/$taskId/$fileType';

  /// Check if expired (15 days, consistent with Flow lifecycle)
  bool isExpired(DateTime? flowCreatedAt) {
    if (flowCreatedAt == null) return false;
    final expiryDate = flowCreatedAt.add(const Duration(days: 30));
    return DateTime.now().isAfter(expiryDate);
  }

  Map<String, dynamic> toJson() => <String, dynamic>{
        'taskId': taskId,
        'fileType': fileType,
        'flowCreatedAt': flowCreatedAt?.toIso8601String(),
      };
}

/// Persisted Flow Context
class PersistedFlowContext {
  PersistedFlowContext({
    this.sourceFileName,
    this.sourceFilePath,
    this.sourceFileHash,
    this.sourceText,
    this.selectedGlossaryIds,
    this.personalGlossaryEnabled,
    this.tempGlossaryId,
    this.translateTaskId,
    this.translateDownloadTypes,
    this.translateTaskCreatedAt,
    this.translateStats,
    this.translateProgress,
    this.anonymizedText,
    this.anonymizeMappings,
    this.anonymizeWorkflowId,
    this.reviewModifications,
    this.deAnonymizedText,
  });

  /// Convert from FlowContext
  /// Note: selectedGlossaryIds should be passed from TranslationQuickSettings, not from GlossaryArtifacts
  factory PersistedFlowContext.fromFlowContext(
    FlowContext context, {
    DateTime? flowCreatedAt,
    DateTime?
        translateTaskCreatedAt, // Translation task creation time (if available)
    List<String>? selectedGlossaryIds, // From TranslationQuickSettings
  }) =>
      PersistedFlowContext(
        sourceFileName: context.source.fileName,
        sourceFilePath: context.source.filePath,
        sourceText: context.source.text,
        selectedGlossaryIds: selectedGlossaryIds, // From Quick Settings
        personalGlossaryEnabled: context.glossary.terms?.isNotEmpty ?? false,
        translateTaskId: context.translate.backendTaskId,
        translateDownloadTypes: context.translate.downloads?.keys.toList(),
        // Use translateTaskCreatedAt if provided, otherwise fallback to flowCreatedAt
        translateTaskCreatedAt: translateTaskCreatedAt ?? flowCreatedAt,
        translateStats: context.translate.stats,
        anonymizedText: context.anonymize.anonymizedText,
        anonymizeMappings: context.anonymize.mappings,
        anonymizeWorkflowId: context.anonymize
            .workflowId, // Save workflowId for restoring Anonymize button state
        reviewModifications: context.review.modifications,
        deAnonymizedText: context.deAnonymize.restoredText,
      );

  factory PersistedFlowContext.fromJson(Map<String, dynamic> json) =>
      PersistedFlowContext(
        sourceFileName: json['sourceFileName'] as String?,
        sourceFilePath: json['sourceFilePath'] as String?,
        sourceFileHash: json['sourceFileHash'] as String?,
        sourceText: json['sourceText'] as String?,
        selectedGlossaryIds: json['selectedGlossaryIds'] != null
            ? List<String>.from(json['selectedGlossaryIds'] as List)
            : null,
        personalGlossaryEnabled: json['personalGlossaryEnabled'] as bool?,
        tempGlossaryId: json['tempGlossaryId'] as String?,
        translateTaskId: json['translateTaskId'] as String?,
        translateDownloadTypes: json['translateDownloadTypes'] != null
            ? List<String>.from(json['translateDownloadTypes'] as List)
            : null,
        translateTaskCreatedAt: json['translateTaskCreatedAt'] != null
            ? DateTime.parse(json['translateTaskCreatedAt'] as String)
            : null,
        translateStats: json['translateStats'] != null
            ? Map<String, dynamic>.from(json['translateStats'] as Map)
            : null,
        translateProgress: json['translateProgress'] != null
            ? (json['translateProgress'] as num).toDouble()
            : null,
        anonymizedText: json['anonymizedText'] as String?,
        anonymizeMappings: json['anonymizeMappings'] != null
            ? Map<String, dynamic>.from(json['anonymizeMappings'] as Map)
            : null,
        anonymizeWorkflowId: json['anonymizeWorkflowId'] as String?,
        reviewModifications: json['reviewModifications'] != null
            ? Map<int, String>.from(
                (json['reviewModifications'] as Map).map(
                    (k, v) => MapEntry(int.parse(k.toString()), v.toString()),),
              )
            : null,
        deAnonymizedText: json['deAnonymizedText'] as String?,
      );
  // Source
  final String?
      sourceFileName; // File name only, no path (environment-dependent)
  final String?
      sourceFilePath; // Absolute or platform-dependent file path (desktop only)
  final String?
      sourceFileHash; // Optional: file hash for verifying file changes
  final String? sourceText; // Text content (if text input)

  // Glossary
  final List<String>? selectedGlossaryIds; // Global glossary ID list
  final bool? personalGlossaryEnabled;
  final String? tempGlossaryId; // Temporary generated glossary ID (if exists)
  // Note: Do not save full glossary content (load from backend)

  // Translate
  final String? translateTaskId; // Backend task ID (for building download URL)
  final List<String>?
      translateDownloadTypes; // Downloadable file types list (e.g., ["html", "md", "docx"])
  final DateTime? translateTaskCreatedAt; // Task creation time (for recording)
  final Map<String, dynamic>? translateStats;
  final double? translateProgress; // 0-100
  // Note: Do not save full download URL (environment-dependent), only save task ID and file types, build URL dynamically

  // Anonymize
  final String? anonymizedText;
  final Map<String, dynamic>? anonymizeMappings;
  final String?
      anonymizeWorkflowId; // Store anonymize workflow ID for restoring Anonymize button state

  // Review & De-anonymize
  final Map<int, String>? reviewModifications;
  final String? deAnonymizedText;

  /// Convert to FlowContext (partial, only for restore)
  FlowContext toFlowContext() => FlowContext(
        source: FlowSource(
          fileName: sourceFileName,
          text: sourceText,
          // filePath is not restored (environment-dependent)
        ),
        glossary: GlossaryArtifacts(
          terms: selectedGlossaryIds
              ?.map((String id) => <String, String>{'glossary_id': id})
              .toList(),
          confirmedTerms: selectedGlossaryIds
              ?.map((String id) => <String, String>{'glossary_id': id})
              .toList(),
        ),
        translate: TranslateArtifacts(
          backendTaskId: translateTaskId,
          stats: translateStats,
        ),
        anonymize: AnonymizeArtifacts(
          anonymizedText: anonymizedText,
          mappings: anonymizeMappings,
          workflowId:
              anonymizeWorkflowId, // Restore workflowId to enable Anonymize button
        ),
        review: ReviewArtifacts(
          modifications: reviewModifications,
        ),
        deAnonymize: DeAnonymizeArtifacts(
          restoredText: deAnonymizedText,
        ),
      );

  /// Get download info list (with expiry based on Flow creation time)
  List<PersistedDownloadInfo> getDownloads(DateTime? flowCreatedAt) {
    if (translateTaskId == null) return <PersistedDownloadInfo>[];
    return (translateDownloadTypes ?? <String>[])
        .map(
          (type) => PersistedDownloadInfo(
            taskId: translateTaskId!,
            fileType: type,
            flowCreatedAt: flowCreatedAt,
          ),
        )
        .toList();
  }

  Map<String, dynamic> toJson() => <String, dynamic>{
        'sourceFileName': sourceFileName,
        'sourceFilePath': sourceFilePath,
        'sourceFileHash': sourceFileHash,
        'sourceText': sourceText,
        'selectedGlossaryIds': selectedGlossaryIds,
        'personalGlossaryEnabled': personalGlossaryEnabled,
        'tempGlossaryId': tempGlossaryId,
        'translateTaskId': translateTaskId,
        'translateDownloadTypes': translateDownloadTypes,
        'translateTaskCreatedAt': translateTaskCreatedAt?.toIso8601String(),
        'translateStats': translateStats,
        'translateProgress': translateProgress,
        'anonymizedText': anonymizedText,
        'anonymizeMappings': anonymizeMappings,
        'anonymizeWorkflowId': anonymizeWorkflowId,
        'reviewModifications': reviewModifications
            ?.map((int k, String v) => MapEntry(k.toString(), v)),
        'deAnonymizedText': deAnonymizedText,
      };
}

/// Steps state for persistence
class PersistedStepsState {
  // De-anonymize step completed

  PersistedStepsState({
    this.uploadCompleted = false,
    this.extractCompleted = false,
    this.glossaryCompleted = false,
    this.glossarySkipped = false,
    this.translateCompleted = false,
    this.anonymizeCompleted = false,
    this.deAnonymizeCompleted = false,
  });

  factory PersistedStepsState.fromJson(Map<String, dynamic> json) =>
      PersistedStepsState(
        uploadCompleted: json['uploadCompleted'] as bool? ?? false,
        extractCompleted: json['extractCompleted'] as bool? ?? false,
        glossaryCompleted: json['glossaryCompleted'] as bool? ?? false,
        glossarySkipped: json['glossarySkipped'] as bool? ?? false,
        translateCompleted: json['translateCompleted'] as bool? ?? false,
        anonymizeCompleted: json['anonymizeCompleted'] as bool? ?? false,
        deAnonymizeCompleted: json['deAnonymizeCompleted'] as bool? ?? false,
      );
  final bool uploadCompleted; // Upload step completed
  final bool extractCompleted; // Extract step completed
  final bool glossaryCompleted; // Glossary step completed (or skipped)
  final bool glossarySkipped; // Glossary step was skipped
  final bool translateCompleted; // Translate step completed
  final bool anonymizeCompleted; // Anonymize step completed
  final bool deAnonymizeCompleted;

  Map<String, dynamic> toJson() => <String, dynamic>{
        'uploadCompleted': uploadCompleted,
        'extractCompleted': extractCompleted,
        'glossaryCompleted': glossaryCompleted,
        'glossarySkipped': glossarySkipped,
        'translateCompleted': translateCompleted,
        'anonymizeCompleted': anonymizeCompleted,
        'deAnonymizeCompleted': deAnonymizeCompleted,
      };
}

/// Persisted Flow UI State
class PersistedFlowUIState {
  // Steps completion state

  PersistedFlowUIState({
    this.activeTabIndex = 0,
    this.quickSettings,
    this.stepsState,
  });

  factory PersistedFlowUIState.fromJson(Map<String, dynamic> json) =>
      PersistedFlowUIState(
        activeTabIndex: json['activeTabIndex'] as int? ?? 0,
        quickSettings: json['quickSettings'] != null
            ? Map<String, dynamic>.from(json['quickSettings'] as Map)
            : null,
        stepsState: json['stepsState'] != null
            ? PersistedStepsState.fromJson(
                json['stepsState'] as Map<String, dynamic>,
              )
            : null,
      );
  final int activeTabIndex;

  final Map<String, dynamic>? quickSettings;

  final PersistedStepsState? stepsState;

  Map<String, dynamic> toJson() => <String, dynamic>{
        'activeTabIndex': activeTabIndex,
        'quickSettings': quickSettings,
        'stepsState': stepsState?.toJson(),
      };
}

/// Persisted Flow State
class PersistedFlowState {
  // Last access time (for 30-day auto-cleanup)

  PersistedFlowState({
    required this.flowId,
    required this.title,
    required this.sourceType,
    required this.flowType,
    required this.activePhase,
    required this.phases,
    required this.context,
    required this.uiState,
    required this.createdAt,
    required this.updatedAt,
    this.lastAccessedAt,
  });

  /// Convert from FlowStateModel
  /// Note: selectedGlossaryIds should be passed from TranslationQuickSettings
  factory PersistedFlowState.fromFlowStateModel(
    FlowStateModel state, {
    int activeTabIndex = 0,
    Map<String, dynamic>? quickSettings,
    List<String>? selectedGlossaryIds, // From TranslationQuickSettings
    PersistedStepsState? stepsState, // Steps completion state
  }) =>
      PersistedFlowState(
        flowId: state.flowId,
        title: state.title,
        sourceType: state.sourceType,
        flowType: state.flowType,
        activePhase: state.activeTaskType,
        phases: state.phases,
        context: PersistedFlowContext.fromFlowContext(
          state.context,
          flowCreatedAt: DateTime.now(),
          selectedGlossaryIds: selectedGlossaryIds,
        ),
        uiState: PersistedFlowUIState(
          activeTabIndex: activeTabIndex,
          quickSettings: quickSettings,
          stepsState: stepsState,
        ),
        createdAt: DateTime.now(),
        updatedAt: DateTime.now(),
        lastAccessedAt: DateTime.now(),
      );

  factory PersistedFlowState.fromJson(Map<String, dynamic> json) {
    // Parse enums
    TaskType sourceType;
    try {
      sourceType = TaskType.values.firstWhere(
        (TaskType e) => e.toString() == json['sourceType'],
        orElse: () => TaskType.file,
      );
    } catch (_) {
      sourceType = TaskType.file;
    }

    TaskFlow flowType;
    try {
      flowType = TaskFlow.values.firstWhere(
        (TaskFlow e) => e.toString() == json['flowType'],
        orElse: () => TaskFlow.translate,
      );
    } catch (_) {
      flowType = TaskFlow.translate;
    }

    PipelinePhase activePhase;
    try {
      activePhase = PipelinePhase.values.firstWhere(
        (PipelinePhase e) => e.toString() == json['activePhase'],
        orElse: () => PipelinePhase.importPhase,
      );
    } catch (_) {
      activePhase = PipelinePhase.importPhase;
    }

    List<PipelinePhase> phases;
    try {
      phases = (json['phases'] as List)
          .map(
            (p) => PipelinePhase.values.firstWhere(
              (PipelinePhase e) => e.toString() == p.toString(),
              orElse: () => PipelinePhase.importPhase,
            ),
          )
          .toList();
    } catch (_) {
      phases = <PipelinePhase>[PipelinePhase.importPhase];
    }

    return PersistedFlowState(
      flowId: json['flowId'] as String,
      title: json['title'] as String,
      sourceType: sourceType,
      flowType: flowType,
      activePhase: activePhase,
      phases: phases,
      context: PersistedFlowContext.fromJson(
        json['context'] as Map<String, dynamic>,
      ),
      uiState: PersistedFlowUIState.fromJson(
        json['uiState'] as Map<String, dynamic>,
      ),
      createdAt: DateTime.parse(json['createdAt'] as String),
      updatedAt: DateTime.parse(json['updatedAt'] as String),
      lastAccessedAt: json['lastAccessedAt'] != null
          ? DateTime.parse(json['lastAccessedAt'] as String)
          : null,
    );
  }
  final String flowId;
  final String title;
  final TaskType sourceType;
  final TaskFlow flowType;
  final PipelinePhase activePhase;
  final List<PipelinePhase> phases;

  // Flow Context data
  final PersistedFlowContext context;

  // UI state
  final PersistedFlowUIState uiState;

  // Metadata
  final DateTime
      createdAt; // Flow creation time (for 30-day expiry calculation)
  final DateTime updatedAt;
  final DateTime? lastAccessedAt;

  /// Check if expired (7 days not accessed - reduced from 30 to prevent accumulation)
  static const int _expirationDays = 7;
  
  bool get isExpired {
    if (lastAccessedAt == null) {
      // If no access record, use creation time
      return DateTime.now().difference(createdAt).inDays > _expirationDays;
    }
    return DateTime.now().difference(lastAccessedAt!).inDays > _expirationDays;
  }

  /// Convert to FlowStateModel (partial, for restore)
  FlowStateModel toFlowStateModel() => FlowStateModel(
        flowId: flowId,
        sourceType: sourceType,
        flowType: flowType,
        title: title,
        activeTaskType: activePhase,
        phases: phases,
        context: context.toFlowContext(),
      );

  /// Update last accessed time
  PersistedFlowState updateLastAccessed() => PersistedFlowState(
        flowId: flowId,
        title: title,
        sourceType: sourceType,
        flowType: flowType,
        activePhase: activePhase,
        phases: phases,
        context: context,
        uiState: uiState,
        createdAt: createdAt,
        updatedAt: DateTime.now(),
        lastAccessedAt: DateTime.now(),
      );

  Map<String, dynamic> toJson() => <String, dynamic>{
        'flowId': flowId,
        'title': title,
        'sourceType': sourceType.toString(),
        'flowType': flowType.toString(),
        'activePhase': activePhase.toString(),
        'phases': phases.map((PipelinePhase p) => p.toString()).toList(),
        'context': context.toJson(),
        'uiState': uiState.toJson(),
        'createdAt': createdAt.toIso8601String(),
        'updatedAt': updatedAt.toIso8601String(),
        'lastAccessedAt': lastAccessedAt?.toIso8601String(),
      };
}
