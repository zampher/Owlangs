// SPDX-FileCopyrightText: 2025 QinHan
// SPDX-License-Identifier: MPL-2.0

enum TaskType { file, text }

enum PipelinePhase {
  importPhase,
  anonymize,
  glossary,
  translate,
  review,
  deAnonymize,
  exportPhase,
}

enum TaskFlow {
  translate, // Glossary -> Translate -> Review
  anonymize, // Anonymize -> Review
  anonymizeAndTranslate, // Anonymize -> Glossary -> Translate -> Review -> De-anonymize
}

class Task {
  const Task({
    required this.id,
    required this.type,
    required this.title,
    required this.createdAt,
    required this.updatedAt,
    this.currentPhase = PipelinePhase.importPhase,
    this.progress = 0,
    this.status = 'idle',
    this.currentFlow = TaskFlow.translate,
    this.plannedPhases = const <PipelinePhase>[],
  });
  final String id;
  final TaskType type;
  final String title;
  final DateTime createdAt;
  final DateTime updatedAt;
  final PipelinePhase currentPhase;
  final double progress; // 0-100
  final String status; // idle|processing|completed|failed
  final TaskFlow currentFlow;
  final List<PipelinePhase> plannedPhases;

  Task copyWith({
    String? id,
    TaskType? type,
    String? title,
    DateTime? createdAt,
    DateTime? updatedAt,
    PipelinePhase? currentPhase,
    double? progress,
    String? status,
    TaskFlow? currentFlow,
    List<PipelinePhase>? plannedPhases,
  }) =>
      Task(
        id: id ?? this.id,
        type: type ?? this.type,
        title: title ?? this.title,
        createdAt: createdAt ?? this.createdAt,
        updatedAt: updatedAt ?? this.updatedAt,
        currentPhase: currentPhase ?? this.currentPhase,
        progress: progress ?? this.progress,
        status: status ?? this.status,
        currentFlow: currentFlow ?? this.currentFlow,
        plannedPhases: plannedPhases ?? this.plannedPhases,
      );
}
