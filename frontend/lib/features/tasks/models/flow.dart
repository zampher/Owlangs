// SPDX-FileCopyrightText: 2025 QinHan
// SPDX-License-Identifier: MPL-2.0

import '../models/task.dart';

class FlowSource {
  const FlowSource({this.filePath, this.fileName, this.text});
  final String? filePath;
  final String? fileName;
  final String? text;

  FlowSource copyWith({String? filePath, String? fileName, String? text}) =>
      FlowSource(
        filePath: filePath ?? this.filePath,
        fileName: fileName ?? this.fileName,
        text: text ?? this.text,
      );
}

class AnonymizeArtifacts {
  // Anonymized segments for AnonymizedResultView (segment mode)
  const AnonymizeArtifacts({
    this.anonymizedText,
    this.originalText,
    this.mappings,
    this.workflowId,
    this.entitiesExpanded,
    this.segments,
    this.separators,
    this.originalSegments,
    this.anonymizedSegments,
  });
  final String? anonymizedText;
  final String? originalText; // Store original text from anonymize result
  final Map<String, dynamic>? mappings;
  final String? workflowId; // Store anonymize workflow ID
  final List<dynamic>?
      entitiesExpanded; // Backend-expanded entities (complete list)
  // Cached segments data for ExtractPreview and AnonymizedResultView
  final List<String>? segments; // All original segments (for ExtractPreview)
  final List<String>? separators; // All separators (for ExtractPreview)
  final List<String>?
      originalSegments; // Original segments for AnonymizedResultView (segment mode)
  final List<String>? anonymizedSegments;

  AnonymizeArtifacts copyWith({
    String? anonymizedText,
    String? originalText,
    Map<String, dynamic>? mappings,
    String? workflowId,
    List<dynamic>? entitiesExpanded,
    List<String>? segments,
    List<String>? separators,
    List<String>? originalSegments,
    List<String>? anonymizedSegments,
  }) =>
      AnonymizeArtifacts(
        anonymizedText: anonymizedText ?? this.anonymizedText,
        originalText: originalText ?? this.originalText,
        mappings: mappings ?? this.mappings,
        workflowId: workflowId ?? this.workflowId,
        entitiesExpanded: entitiesExpanded ?? this.entitiesExpanded,
        segments: segments ?? this.segments,
        separators: separators ?? this.separators,
        originalSegments: originalSegments ?? this.originalSegments,
        anonymizedSegments: anonymizedSegments ?? this.anonymizedSegments,
      );
}

class GlossaryArtifacts {
  const GlossaryArtifacts({this.terms, this.confirmedTerms});
  final List<Map<String, dynamic>>? terms;
  final List<Map<String, dynamic>>? confirmedTerms;
}

class TranslateArtifacts {
  const TranslateArtifacts({this.backendTaskId, this.downloads, this.stats});
  final String? backendTaskId;
  final Map<String, String>? downloads;
  final Map<String, dynamic>? stats;

  TranslateArtifacts copyWith({
    String? backendTaskId,
    Map<String, String>? downloads,
    Map<String, dynamic>? stats,
  }) =>
      TranslateArtifacts(
        backendTaskId: backendTaskId ?? this.backendTaskId,
        downloads: downloads ?? this.downloads,
        stats: stats ?? this.stats,
      );
}

class ReviewArtifacts {
  const ReviewArtifacts({this.modifications});
  final Map<int, String>? modifications;
}

class DeAnonymizeArtifacts {
  const DeAnonymizeArtifacts({this.restoredText});
  final String? restoredText;
}

class FlowContext {
  const FlowContext({
    this.source = const FlowSource(),
    this.anonymize = const AnonymizeArtifacts(),
    this.glossary = const GlossaryArtifacts(),
    this.translate = const TranslateArtifacts(),
    this.review = const ReviewArtifacts(),
    this.deAnonymize = const DeAnonymizeArtifacts(),
  });
  final FlowSource source;
  final AnonymizeArtifacts anonymize;
  final GlossaryArtifacts glossary;
  final TranslateArtifacts translate;
  final ReviewArtifacts review;
  final DeAnonymizeArtifacts deAnonymize;

  FlowContext copyWith({
    FlowSource? source,
    AnonymizeArtifacts? anonymize,
    GlossaryArtifacts? glossary,
    TranslateArtifacts? translate,
    ReviewArtifacts? review,
    DeAnonymizeArtifacts? deAnonymize,
  }) =>
      FlowContext(
        source: source ?? this.source,
        anonymize: anonymize ?? this.anonymize,
        glossary: glossary ?? this.glossary,
        translate: translate ?? this.translate,
        review: review ?? this.review,
        deAnonymize: deAnonymize ?? this.deAnonymize,
      );
}

class FlowStateModel {
  const FlowStateModel({
    required this.flowId,
    required this.sourceType,
    required this.flowType,
    required this.title,
    required this.activeTaskType,
    required this.phases,
    this.context = const FlowContext(),
  });
  final String flowId;
  final TaskType sourceType;
  final TaskFlow flowType;
  final String title;
  final PipelinePhase activeTaskType;
  final List<PipelinePhase> phases;
  final FlowContext context;

  FlowStateModel copyWith({
    TaskType? sourceType,
    TaskFlow? flowType,
    String? title,
    PipelinePhase? activeTaskType,
    List<PipelinePhase>? phases,
    FlowContext? context,
  }) =>
      FlowStateModel(
        flowId: flowId,
        sourceType: sourceType ?? this.sourceType,
        flowType: flowType ?? this.flowType,
        title: title ?? this.title,
        activeTaskType: activeTaskType ?? this.activeTaskType,
        phases: phases ?? this.phases,
        context: context ?? this.context,
      );
}
