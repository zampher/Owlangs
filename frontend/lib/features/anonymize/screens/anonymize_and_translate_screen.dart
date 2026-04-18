// SPDX-FileCopyrightText: 2025 QinHan
// SPDX-License-Identifier: MPL-2.0

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../tasks/models/flow.dart';
import '../../tasks/providers/tasks_provider.dart';
import '../../tasks/models/task.dart';
import '../../tasks/providers/flow_provider.dart';
import '../../translation/screens/translation_screen.dart';
import 'anonymize_screen.dart';

/// Combined screen for Anonymize+Translate flow
/// Dynamically shows Anonymize or Translate functionality based on current phase
class AnonymizeAndTranslateScreen extends ConsumerStatefulWidget {
  const AnonymizeAndTranslateScreen({super.key, this.flowId});
  final String? flowId;

  @override
  ConsumerState<AnonymizeAndTranslateScreen> createState() =>
      _AnonymizeAndTranslateScreenState();
}

class _AnonymizeAndTranslateScreenState
    extends ConsumerState<AnonymizeAndTranslateScreen> {
  @override
  Widget build(BuildContext context) {
    // Get current task to determine which phase we're in
    if (widget.flowId == null) {
      return const Center(child: Text('No flow ID provided'));
    }

    final TasksState tasks = ref.watch(tasksProvider);
    final Task task = tasks.tasks.firstWhere(
      (Task t) => t.id == widget.flowId,
      orElse: () => Task(
        id: widget.flowId!,
        type: TaskType.file,
        title: '',
        createdAt: DateTime.now(),
        updatedAt: DateTime.now(),
        currentFlow: TaskFlow.anonymizeAndTranslate,
        plannedPhases: <PipelinePhase>[],
      ),
    );

    // Get flow context to check if anonymize is completed
    final FlowStateModel flow = ref.watch(flowProviderFamily(widget.flowId!));
    final bool isAnonymizeCompleted =
        flow.context.anonymize.anonymizedText != null;

    // Determine which screen to show based on current phase and completion status
    // Phase 1: Import/Anonymize → Show AnonymizeScreen (with Translate buttons disabled until anonymize completes)
    // Phase 2: After anonymize completes → Show TranslationScreen (with Anonymize context)
    if (task.currentPhase == PipelinePhase.importPhase ||
        task.currentPhase == PipelinePhase.anonymize ||
        !isAnonymizeCompleted) {
      // Show AnonymizeScreen, but with Translate buttons enabled after anonymize completes
      // We'll use a modified version that includes Translate buttons
      return _AnonymizeWithTranslateScreen(flowId: widget.flowId);
    } else {
      // After anonymize completes, show TranslationScreen
      return TranslationScreen(flowId: widget.flowId);
    }
  }
}

/// Anonymize screen with Translate functionality integrated
/// This is used for the Anonymize+Translate flow
class _AnonymizeWithTranslateScreen extends ConsumerStatefulWidget {
  const _AnonymizeWithTranslateScreen({this.flowId});
  final String? flowId;

  @override
  ConsumerState<_AnonymizeWithTranslateScreen> createState() =>
      _AnonymizeWithTranslateScreenState();
}

class _AnonymizeWithTranslateScreenState
    extends ConsumerState<_AnonymizeWithTranslateScreen> {
  // This will be a wrapper around AnonymizeScreen that adds Translate buttons
  // For now, we'll use AnonymizeScreen and add Translate functionality via toolbar extension
  // In a full implementation, we could create a shared base class or use composition

  @override
  Widget build(BuildContext context) {
    // For now, delegate to AnonymizeScreen
    // The toolbar in AnonymizeScreen will be extended to include Translate buttons
    // when used in AnonymizeAndTranslateScreen context
    return AnonymizeScreen(flowId: widget.flowId);
  }
}
