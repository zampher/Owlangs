// SPDX-FileCopyrightText: 2025 QinHan
// SPDX-License-Identifier: MPL-2.0

import 'dart:math';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../models/task.dart';
import '../models/persisted_flow_state.dart';

class TasksState {
  const TasksState({this.tasks = const <Task>[], this.activeTaskId});
  final List<Task> tasks;
  final String? activeTaskId;

  Task? get activeTask => tasks.where((t) => t.id == activeTaskId).isNotEmpty
      ? tasks.firstWhere((t) => t.id == activeTaskId)
      : null;

  TasksState copyWith({
    List<Task>? tasks,
    String? activeTaskId,
    bool clearActiveTaskId = false,
  }) =>
      TasksState(
        tasks: tasks ?? this.tasks,
        activeTaskId:
            clearActiveTaskId ? null : (activeTaskId ?? this.activeTaskId),
      );
}

class TasksNotifier extends StateNotifier<TasksState> {
  TasksNotifier() : super(const TasksState());

  String _genId() =>
      DateTime.now().millisecondsSinceEpoch.toString() +
      Random().nextInt(9999).toString();

  // Session-level counters for each flow type (reset on app start)
  final Map<TaskFlow, int> _flowCounters = <TaskFlow, int>{
    TaskFlow.translate: 0,
    TaskFlow.anonymize: 0,
    TaskFlow.anonymizeAndTranslate: 0,
  };

  void setActive(String taskId) {
    // Support selecting Home by passing empty string
    if (taskId.isEmpty) {
      state = state.copyWith(clearActiveTaskId: true);
      return;
    }
    if (state.tasks.any((t) => t.id == taskId)) {
      state = state.copyWith(activeTaskId: taskId);
    }
  }

  /// Create a new Flow with specified type and flow
  /// Returns the created Task (which serves as Flow)
  Future<Task> createFlow({
    required TaskType sourceType,
    required TaskFlow flowType,
  }) async {
    // Generate flowId
    final flowId = _genId();

    // Get default title based on flow type
    final defaultTitle = _getDefaultTitle(flowType);

    final now = DateTime.now();

    // Determine phases based on flowType
    List<PipelinePhase> phases;
    switch (flowType) {
      case TaskFlow.translate:
        phases = <PipelinePhase>[
          PipelinePhase.importPhase,
          PipelinePhase.glossary,
          PipelinePhase.translate,
          PipelinePhase.review,
        ];
        break;
      case TaskFlow.anonymize:
        phases = <PipelinePhase>[
          PipelinePhase.importPhase,
          PipelinePhase.anonymize,
          PipelinePhase.review,
        ];
        break;
      case TaskFlow.anonymizeAndTranslate:
        phases = <PipelinePhase>[
          PipelinePhase.importPhase,
          PipelinePhase.anonymize,
          PipelinePhase.glossary,
          PipelinePhase.translate,
          PipelinePhase.review,
          PipelinePhase.deAnonymize,
        ];
        break;
    }

    final task = Task(
      id: flowId,
      type: sourceType,
      title: defaultTitle,
      createdAt: now,
      updatedAt: now,
      currentFlow: flowType,
      plannedPhases: phases,
    );

    state = state
        .copyWith(tasks: <Task>[...state.tasks, task], activeTaskId: task.id);

    // Initialize FlowStateModel via flowProviderFamily (will auto-create with default title)
    // The flowProviderFamily will handle initialization and default title assignment
    return task;
  }

  /// Get default title based on flow type
  /// Counters start from 1 on each app start (session-level, not persisted)
  String _getDefaultTitle(TaskFlow flowType) {
    // Increment counter for this flow type
    _flowCounters[flowType] = (_flowCounters[flowType] ?? 0) + 1;
    final counter = _flowCounters[flowType]!;

    // Generate title based on flow type
    switch (flowType) {
      case TaskFlow.translate:
        return 'Translation-$counter';
      case TaskFlow.anonymize:
        return 'Anonymization-$counter';
      case TaskFlow.anonymizeAndTranslate:
        // For anonymize+translate, use anonymization format
        return 'Anonymization-$counter';
    }
  }

  /// Legacy method - use createFlow instead
  /// Note: All flows now use TaskType.file (unified)
  Future<Task> createTextTask() async =>
      createFlow(sourceType: TaskType.file, flowType: TaskFlow.translate);

  /// Legacy method - use createFlow instead
  Future<Task> createFileTask() async =>
      createFlow(sourceType: TaskType.file, flowType: TaskFlow.translate);

  void renameTask(String taskId, String title) {
    final updated = state.tasks
        .map(
          (t) => t.id == taskId
              ? t.copyWith(title: title, updatedAt: DateTime.now())
              : t,
        )
        .toList();
    state = state.copyWith(tasks: updated);
  }

  void setPhase(String taskId, PipelinePhase phase) {
    final updated = state.tasks
        .map(
          (t) => t.id == taskId
              ? t.copyWith(currentPhase: phase, updatedAt: DateTime.now())
              : t,
        )
        .toList();
    state = state.copyWith(tasks: updated);
  }

  void setFlow(String taskId, TaskFlow flow) {
    List<PipelinePhase> steps;
    switch (flow) {
      case TaskFlow.translate:
        // Upload File -> Glossary (optional) -> Translate -> Review
        steps = <PipelinePhase>[
          PipelinePhase.importPhase,
          PipelinePhase.glossary,
          PipelinePhase.translate,
          PipelinePhase.review,
        ];
        break;
      case TaskFlow.anonymize:
        // Upload File -> Anonymize -> Review -> De-anonymize
        steps = <PipelinePhase>[
          PipelinePhase.importPhase,
          PipelinePhase.anonymize,
          PipelinePhase.review,
          PipelinePhase.deAnonymize,
        ];
        break;
      case TaskFlow.anonymizeAndTranslate:
        // Upload File -> Anonymize -> Glossary (optional) -> Translate -> Review -> De-anonymize
        steps = <PipelinePhase>[
          PipelinePhase.importPhase,
          PipelinePhase.anonymize,
          PipelinePhase.glossary,
          PipelinePhase.translate,
          PipelinePhase.review,
          PipelinePhase.deAnonymize,
        ];
        break;
    }

    final updated = state.tasks.map((t) {
      if (t.id != taskId) return t;
      // Always start with importPhase when setting flow
      return t.copyWith(
        currentFlow: flow,
        plannedPhases: steps,
        currentPhase: PipelinePhase.importPhase,
        updatedAt: DateTime.now(),
      );
    }).toList();
    state = state.copyWith(tasks: updated);
  }

  void closeTask(String taskId) {
    final updated = state.tasks.where((t) => t.id != taskId).toList();
    // If all flows are closed, set activeTaskId to null to show Home screen
    // Otherwise, if closing the active flow, activate the last remaining flow
    // If closing a non-active flow, keep the current activeTaskId
    final newActive = updated.isEmpty
        ? null
        : (state.activeTaskId == taskId ? updated.last.id : state.activeTaskId);
    state = state.copyWith(tasks: updated, activeTaskId: newActive);
  }

  /// Restore a Flow from persisted state (Recent Activities / app restart).
  /// If a Task with the same ID already exists, it will just be activated.
  Future<Task> restoreFlowFromPersisted(PersistedFlowState flowState) async {
    final String flowId = flowState.flowId;

    // If task already exists in current session, just activate it.
    final int existingIndex =
        state.tasks.indexWhere((Task t) => t.id == flowId);
    if (existingIndex != -1) {
      final Task existing = state.tasks[existingIndex];
      state = state.copyWith(activeTaskId: existing.id);
      return existing;
    }

    // Build phases based on flow type (keep consistent with createFlow/setFlow).
    final TaskFlow flowType = flowState.flowType;
    List<PipelinePhase> phases;
    switch (flowType) {
      case TaskFlow.translate:
        phases = <PipelinePhase>[
          PipelinePhase.importPhase,
          PipelinePhase.glossary,
          PipelinePhase.translate,
          PipelinePhase.review,
        ];
        break;
      case TaskFlow.anonymize:
        phases = <PipelinePhase>[
          PipelinePhase.importPhase,
          PipelinePhase.anonymize,
          PipelinePhase.review,
          PipelinePhase.deAnonymize,
        ];
        break;
      case TaskFlow.anonymizeAndTranslate:
        phases = <PipelinePhase>[
          PipelinePhase.importPhase,
          PipelinePhase.anonymize,
          PipelinePhase.glossary,
          PipelinePhase.translate,
          PipelinePhase.review,
          PipelinePhase.deAnonymize,
        ];
        break;
    }

    final Task task = Task(
      id: flowId,
      type: TaskType.file,
      title: flowState.title,
      createdAt: flowState.createdAt,
      updatedAt: DateTime.now(),
      currentPhase: flowState.activePhase,
      currentFlow: flowType,
      plannedPhases: phases,
    );

    state = state.copyWith(
      tasks: <Task>[...state.tasks, task],
      activeTaskId: task.id,
    );

    return task;
  }
}

final StateNotifierProvider<TasksNotifier, TasksState> tasksProvider =
    StateNotifierProvider<TasksNotifier, TasksState>(
  (ref) => TasksNotifier(),
);
