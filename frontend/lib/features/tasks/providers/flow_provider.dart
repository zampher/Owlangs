// SPDX-FileCopyrightText: 2025 QinHan
// SPDX-License-Identifier: MPL-2.0

import 'dart:async';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../models/task.dart';
import '../models/flow.dart';
import '../services/flow_state_persistence.dart';
import '../models/persisted_flow_state.dart';
import 'tasks_provider.dart';

List<PipelinePhase> _phasesForFlow(TaskFlow flowType) {
  switch (flowType) {
    case TaskFlow.translate:
      // Upload File -> Glossary (optional) -> Translate -> Review
      return <PipelinePhase>[
        PipelinePhase.importPhase,
        PipelinePhase.glossary,
        PipelinePhase.translate,
        PipelinePhase.review,
      ];
    case TaskFlow.anonymize:
      // Upload File -> Anonymize -> De-anonymize
      return <PipelinePhase>[
        PipelinePhase.importPhase,
        PipelinePhase.anonymize,
        PipelinePhase.deAnonymize,
      ];
    case TaskFlow.anonymizeAndTranslate:
      // Upload File -> Anonymize -> Glossary (optional) -> Translate -> Review -> De-anonymize
      return <PipelinePhase>[
        PipelinePhase.importPhase,
        PipelinePhase.anonymize,
        PipelinePhase.glossary,
        PipelinePhase.translate,
        PipelinePhase.review,
        PipelinePhase.deAnonymize,
      ];
  }
}

class FlowStateNotifier extends StateNotifier<FlowStateModel> {
  FlowStateNotifier(super.state) : flowId = state.flowId {
    // Try to load persisted state on initialization
    _loadPersistedState();
    // Initialize default title if using placeholder
    _initDefaultTitleIfNeeded();
  }
  final String flowId;
  Timer? _saveDebounceTimer;
  static const Duration _saveDebounceDelay = Duration(milliseconds: 500);

  @override
  set state(FlowStateModel newState) {
    super.state = newState;
    // Auto-save with debounce
    _saveStateDebounced();
  }

  /// Initialize default title (Flow-001, Flow-002, ...) if still placeholder
  Future<void> _initDefaultTitleIfNeeded() async {
    try {
      if (state.title == 'Flow' || state.title.trim().isEmpty) {
        final String nextTitle =
            await FlowStatePersistence.getNextDefaultTitle();
        state = state.copyWith(title: nextTitle);
        await saveStateImmediately();
      }
    } catch (e) {
      // Fallback: keep placeholder title on failure
    }
  }

  /// Load persisted state from storage
  Future<void> _loadPersistedState() async {
    try {
      final PersistedFlowState? persisted =
          await FlowStatePersistence.loadFlowState(flowId);
      if (persisted != null) {
        final FlowStateModel restored = persisted.toFlowStateModel();
        // Only restore if current state is default (no user changes yet)
        if (state.title == 'Flow' &&
            state.activeTaskType == PipelinePhase.importPhase) {
          state = restored;
        }
        // Steps state is stored in persisted.uiState.stepsState
        // It will be accessed by TranslationScreen via FlowStatePersistence
      }
    } catch (e) {
      print('Error loading persisted state: $e');
      // Fail silently - use default state
    }
  }

  /// Get persisted steps state (for TranslationScreen to access)
  PersistedStepsState? getPersistedStepsState() {
    // This will be called from TranslationScreen to get steps state
    // We need to access it from FlowStatePersistence, not from current state
    // For now, return null - TranslationScreen will load it directly
    return null;
  }

  /// Save state with debounce (avoid frequent writes)
  void _saveStateDebounced() {
    _saveDebounceTimer?.cancel();
    _saveDebounceTimer = Timer(_saveDebounceDelay, _saveState);
  }

  /// Save state to persistent storage
  /// Note: selectedGlossaryIds should be passed from TranslationQuickSettings (not available here)
  Future<void> _saveState({
    List<String>? selectedGlossaryIds,
    PersistedStepsState? stepsState,
  }) async {
    try {
      final PersistedFlowState persisted =
          PersistedFlowState.fromFlowStateModel(
        state,
        selectedGlossaryIds: selectedGlossaryIds,
        stepsState: stepsState,
      );
      await FlowStatePersistence.saveFlowState(persisted);
    } catch (e) {
      print('Error saving state: $e');
      // Fail silently - persistence is optional
    }
  }

  /// Save state with glossary IDs and steps state (called from TranslationScreen)
  Future<void> saveStateWithGlossaryIds(
    List<String> selectedGlossaryIds, {
    PersistedStepsState? stepsState,
  }) async {
    _saveDebounceTimer?.cancel();
    await _saveState(
      selectedGlossaryIds: selectedGlossaryIds,
      stepsState: stepsState,
    );
  }

  /// Save state immediately (for important state changes)
  Future<void> saveStateImmediately() async {
    _saveDebounceTimer?.cancel();
    await _saveState();
  }

  void setActivePhase(PipelinePhase phase) {
    state = state.copyWith(activeTaskType: phase);
    saveStateImmediately(); // Save immediately for phase changes
  }

  void updateSource(FlowSource source) {
    state = state.copyWith(context: state.context.copyWith(source: source));
    saveStateImmediately(); // Save immediately for source changes
  }

  void setAnonymizeArtifacts(AnonymizeArtifacts artifacts) {
    state =
        state.copyWith(context: state.context.copyWith(anonymize: artifacts));
    saveStateImmediately(); // Save immediately for important artifacts
  }

  void setGlossaryArtifacts(GlossaryArtifacts artifacts) {
    state =
        state.copyWith(context: state.context.copyWith(glossary: artifacts));
    saveStateImmediately(); // Save immediately for glossary changes
  }

  void setTranslateArtifacts(TranslateArtifacts artifacts) {
    state =
        state.copyWith(context: state.context.copyWith(translate: artifacts));
    saveStateImmediately(); // Save immediately for translation changes
  }

  void setReviewArtifacts(ReviewArtifacts artifacts) {
    state = state.copyWith(context: state.context.copyWith(review: artifacts));
  }

  void setDeAnonymizeArtifacts(DeAnonymizeArtifacts artifacts) {
    state =
        state.copyWith(context: state.context.copyWith(deAnonymize: artifacts));
  }

  /// Clean up when Flow is closed
  Future<void> cleanup() async {
    _saveDebounceTimer?.cancel();
    // Delete persisted state when Flow is closed
    await FlowStatePersistence.deleteFlowState(flowId);
  }

  @override
  void dispose() {
    _saveDebounceTimer?.cancel();
    super.dispose();
  }
}

final StateNotifierProviderFamily<FlowStateNotifier, FlowStateModel, String>
    flowProviderFamily =
    StateNotifierProvider.family<FlowStateNotifier, FlowStateModel, String>((
  StateNotifierProviderRef<FlowStateNotifier, FlowStateModel> ref,
  String flowId,
) {
  // Try to get flow type from tasks provider
  final TasksState tasks = ref.read(tasksProvider);
  final Task task = tasks.tasks.firstWhere(
    (Task t) => t.id == flowId,
    orElse: () => Task(
      id: flowId,
      type: TaskType.file,
      title: 'Flow',
      createdAt: DateTime.now(),
      updatedAt: DateTime.now(),
      plannedPhases: <PipelinePhase>[],
    ),
  );

  // Use task's flowType, or default to translate
  final TaskFlow flowType = task.currentFlow;

  final FlowStateModel initial = FlowStateModel(
    flowId: flowId,
    sourceType: task.type,
    flowType: flowType,
    title: task.title,
    activeTaskType: task.currentPhase,
    phases: _phasesForFlow(flowType),
  );
  return FlowStateNotifier(initial);
});
