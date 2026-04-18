// SPDX-FileCopyrightText: 2025 QinHan
// SPDX-License-Identifier: MPL-2.0

import 'package:flutter_riverpod/flutter_riverpod.dart';

/// Snapshot of a segment revision
class SegmentRevision {
  const SegmentRevision(this.text, this.timestamp);
  final String text;
  final DateTime timestamp;

  SegmentRevision copyWith({String? text, DateTime? timestamp}) =>
      SegmentRevision(
        text ?? this.text,
        timestamp ?? this.timestamp,
      );
}

/// Global revision operation (cross-segment)
class GlobalRevisionOperation {
  const GlobalRevisionOperation({
    required this.segmentIndex,
    required this.oldText,
    required this.newText,
    required this.timestamp,
  });
  final int segmentIndex;
  final String oldText; // Text before the operation
  final String newText; // Text after the operation
  final DateTime timestamp;
}

/// Undo/Redo state for a single segment
class SegmentUndoRedoState {
  // Redo stack (newest first)

  const SegmentUndoRedoState({
    this.past = const <SegmentRevision>[],
    this.present,
    this.future = const <SegmentRevision>[],
  });
  final List<SegmentRevision> past; // History stack (oldest first)
  final SegmentRevision? present; // Current revision
  final List<SegmentRevision> future;

  bool get canUndo => past.isNotEmpty;
  bool get canRedo => future.isNotEmpty;

  SegmentUndoRedoState copyWith({
    List<SegmentRevision>? past,
    SegmentRevision? present,
    List<SegmentRevision>? future,
  }) =>
      SegmentUndoRedoState(
        past: past ?? this.past,
        present: present ?? this.present,
        future: future ?? this.future,
      );
}

/// Undo/Redo state for all segments in a task
class TranslationSegmentsUndoRedoState {
  // Redo stack (newest first)

  const TranslationSegmentsUndoRedoState({
    this.segments = const <int, SegmentUndoRedoState>{},
    this.globalPast = const <GlobalRevisionOperation>[],
    this.globalFuture = const <GlobalRevisionOperation>[],
  });
  // Map: segmentIndex -> undo/redo state (per-segment local undo/redo)
  final Map<int, SegmentUndoRedoState> segments;

  // Global undo/redo stack (cross-segment, time-ordered)
  final List<GlobalRevisionOperation>
      globalPast; // History stack (oldest first)
  final List<GlobalRevisionOperation> globalFuture;

  // Per-segment undo/redo availability
  bool canUndo(int segmentIndex) => segments[segmentIndex]?.canUndo ?? false;

  bool canRedo(int segmentIndex) => segments[segmentIndex]?.canRedo ?? false;

  // Global undo/redo availability
  bool get canGlobalUndo => globalPast.isNotEmpty;
  bool get canGlobalRedo => globalFuture.isNotEmpty;

  TranslationSegmentsUndoRedoState copyWith({
    Map<int, SegmentUndoRedoState>? segments,
    List<GlobalRevisionOperation>? globalPast,
    List<GlobalRevisionOperation>? globalFuture,
  }) =>
      TranslationSegmentsUndoRedoState(
        segments: segments ?? this.segments,
        globalPast: globalPast ?? this.globalPast,
        globalFuture: globalFuture ?? this.globalFuture,
      );
}

/// Notifier for managing undo/redo for translation segments
class TranslationSegmentsUndoRedoNotifier
    extends StateNotifier<TranslationSegmentsUndoRedoState> {
  TranslationSegmentsUndoRedoNotifier({
    required this.taskId,
    this.maxHistoryDepth = 100,
  }) : super(const TranslationSegmentsUndoRedoState());
  final int maxHistoryDepth;
  final String taskId;

  /// Initialize or update segment's current text
  void initializeSegment(int segmentIndex, String initialText) {
    final currentState = state.segments[segmentIndex];
    if (currentState == null || currentState.present == null) {
      // First time initialization
      final revision = SegmentRevision(initialText, DateTime.now());
      final updatedSegments =
          Map<int, SegmentUndoRedoState>.from(state.segments);
      updatedSegments[segmentIndex] = SegmentUndoRedoState(present: revision);
      state = state.copyWith(segments: updatedSegments);
    }
  }

  /// Push a new revision when user saves an edit
  /// This updates both per-segment and global undo/redo stacks
  void pushRevision(int segmentIndex, String newText, {String? oldText}) {
    final currentState = state.segments[segmentIndex];
    final currentRevision = currentState?.present;
    final previousText = oldText ?? currentRevision?.text ?? '';

    // Only push if text actually changed
    if (previousText == newText) {
      return; // No change, skip
    }

    final now = DateTime.now();
    final newRevision = SegmentRevision(newText, now);
    final updatedSegments = Map<int, SegmentUndoRedoState>.from(state.segments);

    // Update per-segment undo/redo stack
    List<SegmentRevision> past = <SegmentRevision>[];
    if (currentState != null) {
      past = List<SegmentRevision>.from(currentState.past);
      if (currentRevision != null) {
        past.add(currentRevision);
        // Limit history depth
        if (past.length > maxHistoryDepth) {
          past.removeAt(0);
        }
      }
    }

    updatedSegments[segmentIndex] = SegmentUndoRedoState(
      past: past,
      present: newRevision,
    );

    // Update global undo/redo stack (cross-segment, time-ordered)
    final globalOperation = GlobalRevisionOperation(
      segmentIndex: segmentIndex,
      oldText: previousText,
      newText: newText,
      timestamp: now,
    );

    final globalPast = List<GlobalRevisionOperation>.from(state.globalPast);
    globalPast.add(globalOperation);
    // Limit global history depth
    if (globalPast.length > maxHistoryDepth) {
      globalPast.removeAt(0);
    }

    state = state.copyWith(
      segments: updatedSegments,
      globalPast: globalPast,
      globalFuture: const <GlobalRevisionOperation>[], // Clear global redo stack when new revision is pushed
    );
  }

  /// Undo: revert to previous revision (local per-segment undo)
  /// This operation is also recorded in the global stack as a new operation
  String? undo(int segmentIndex) {
    final currentState = state.segments[segmentIndex];
    if (currentState == null || !currentState.canUndo) {
      return null;
    }

    final currentText = currentState.present?.text ?? '';
    final past = List<SegmentRevision>.from(currentState.past);
    final previousRevision = past.removeLast();
    final previousText = previousRevision.text;
    final future = <SegmentRevision>[
      if (currentState.present != null) currentState.present!,
      ...currentState.future,
    ];

    // Update local stack
    final updatedSegments = Map<int, SegmentUndoRedoState>.from(state.segments);
    updatedSegments[segmentIndex] = SegmentUndoRedoState(
      past: past,
      present: previousRevision,
      future: future,
    );

    // Record this undo operation in global stack as a new operation
    final now = DateTime.now();
    final globalOperation = GlobalRevisionOperation(
      segmentIndex: segmentIndex,
      oldText: currentText, // Current text before undo
      newText: previousText, // Text after undo
      timestamp: now,
    );

    final globalPast = List<GlobalRevisionOperation>.from(state.globalPast);
    globalPast.add(globalOperation);
    // Limit global history depth
    if (globalPast.length > maxHistoryDepth) {
      globalPast.removeAt(0);
    }

    state = state.copyWith(
      segments: updatedSegments,
      globalPast: globalPast,
      globalFuture: const <GlobalRevisionOperation>[], // Clear global redo stack when new operation is pushed
    );

    return previousText;
  }

  /// Redo: restore to next revision (local per-segment redo)
  /// This operation is also recorded in the global stack as a new operation
  String? redo(int segmentIndex) {
    final currentState = state.segments[segmentIndex];
    if (currentState == null || !currentState.canRedo) {
      return null;
    }

    final currentText = currentState.present?.text ?? '';
    final future = List<SegmentRevision>.from(currentState.future);
    final nextRevision = future.removeAt(0);
    final nextText = nextRevision.text;
    final past = <SegmentRevision>[
      ...currentState.past,
      if (currentState.present != null) currentState.present!,
    ];

    // Update local stack
    final updatedSegments = Map<int, SegmentUndoRedoState>.from(state.segments);
    updatedSegments[segmentIndex] = SegmentUndoRedoState(
      past: past,
      present: nextRevision,
      future: future,
    );

    // Record this redo operation in global stack as a new operation
    final now = DateTime.now();
    final globalOperation = GlobalRevisionOperation(
      segmentIndex: segmentIndex,
      oldText: currentText, // Current text before redo
      newText: nextText, // Text after redo
      timestamp: now,
    );

    final globalPast = List<GlobalRevisionOperation>.from(state.globalPast);
    globalPast.add(globalOperation);
    // Limit global history depth
    if (globalPast.length > maxHistoryDepth) {
      globalPast.removeAt(0);
    }

    state = state.copyWith(
      segments: updatedSegments,
      globalPast: globalPast,
      globalFuture: const <GlobalRevisionOperation>[], // Clear global redo stack when new operation is pushed
    );

    return nextText;
  }

  /// Get current text for a segment
  String? getCurrentText(int segmentIndex) =>
      state.segments[segmentIndex]?.present?.text;

  /// Clear undo/redo history for a segment (e.g., when segment is deleted)
  void clearSegment(int segmentIndex) {
    final updatedSegments = Map<int, SegmentUndoRedoState>.from(state.segments);
    updatedSegments.remove(segmentIndex);

    // Also remove from global stack
    final globalPast = state.globalPast
        .where((op) => op.segmentIndex != segmentIndex)
        .toList();
    final globalFuture = state.globalFuture
        .where((op) => op.segmentIndex != segmentIndex)
        .toList();

    state = state.copyWith(
      segments: updatedSegments,
      globalPast: globalPast,
      globalFuture: globalFuture,
    );
  }

  /// Global Undo: revert the last operation across all segments (time-ordered)
  /// Returns the operation info (segmentIndex, oldText) for applying the undo
  GlobalRevisionOperation? globalUndo() {
    if (!state.canGlobalUndo) {
      return null;
    }

    final globalPast = List<GlobalRevisionOperation>.from(state.globalPast);
    final lastOperation = globalPast.removeLast();

    // Move current state to global future
    final globalFuture = <GlobalRevisionOperation>[
      lastOperation,
      ...state.globalFuture,
    ];

    // Update the segment's local state to reflect the undo
    final segmentIndex = lastOperation.segmentIndex;
    final updatedSegments = Map<int, SegmentUndoRedoState>.from(state.segments);
    final segmentState = updatedSegments[segmentIndex];

    if (segmentState != null) {
      // Move current present to future, get last from past
      final segmentPast = List<SegmentRevision>.from(segmentState.past);
      if (segmentPast.isNotEmpty) {
        final previousRevision = segmentPast.removeLast();
        final segmentFuture = <SegmentRevision>[
          if (segmentState.present != null) segmentState.present!,
          ...segmentState.future,
        ];

        updatedSegments[segmentIndex] = SegmentUndoRedoState(
          past: segmentPast,
          present: previousRevision,
          future: segmentFuture,
        );
      }
    }

    state = state.copyWith(
      segments: updatedSegments,
      globalPast: globalPast,
      globalFuture: globalFuture,
    );

    return lastOperation;
  }

  /// Global Redo: restore the next operation across all segments (time-ordered)
  /// Returns the operation info (segmentIndex, newText) for applying the redo
  /// This also updates the local stack of the affected segment
  GlobalRevisionOperation? globalRedo() {
    if (!state.canGlobalRedo) {
      return null;
    }

    final globalFuture = List<GlobalRevisionOperation>.from(state.globalFuture);
    final nextOperation = globalFuture.removeAt(0);

    // Move to global past
    final globalPast = <GlobalRevisionOperation>[
      ...state.globalPast,
      nextOperation,
    ];

    // Update the segment's local state to reflect the redo
    // We need to find or create the matching revision in the local stack
    final segmentIndex = nextOperation.segmentIndex;
    final updatedSegments = Map<int, SegmentUndoRedoState>.from(state.segments);
    final segmentState = updatedSegments[segmentIndex];

    if (segmentState != null) {
      final segmentPast = List<SegmentRevision>.from(segmentState.past);
      final segmentFuture = List<SegmentRevision>.from(segmentState.future);

      // Try to find matching revision in future stack
      int? matchingIndex;
      for (int i = 0; i < segmentFuture.length; i++) {
        if (segmentFuture[i].text == nextOperation.newText) {
          matchingIndex = i;
          break;
        }
      }

      if (matchingIndex != null) {
        // Found matching revision, move everything before it to past
        final matchingRevision = segmentFuture[matchingIndex];
        final revisionsToMove = segmentFuture.sublist(0, matchingIndex);
        final newPast = <SegmentRevision>[
          ...segmentPast,
          if (segmentState.present != null) segmentState.present!,
          ...revisionsToMove,
        ];
        final newFuture = segmentFuture.sublist(matchingIndex + 1);

        updatedSegments[segmentIndex] = SegmentUndoRedoState(
          past: newPast,
          present: matchingRevision,
          future: newFuture,
        );
      } else {
        // No exact match found, create a new revision based on newText
        final now = DateTime.now();
        final nextRevision = SegmentRevision(nextOperation.newText, now);
        final newPast = <SegmentRevision>[
          ...segmentPast,
          if (segmentState.present != null) segmentState.present!,
        ];

        updatedSegments[segmentIndex] = SegmentUndoRedoState(
          past: newPast,
          present: nextRevision,
          future: segmentFuture,
        );
      }
    }

    state = state.copyWith(
      segments: updatedSegments,
      globalPast: globalPast,
      globalFuture: globalFuture,
    );

    return nextOperation;
  }
}

/// Family provider for undo/redo per task
final StateNotifierProviderFamily<TranslationSegmentsUndoRedoNotifier,
        TranslationSegmentsUndoRedoState, String>
    translationSegmentsUndoRedoProvider = StateNotifierProvider.family<
        TranslationSegmentsUndoRedoNotifier,
        TranslationSegmentsUndoRedoState,
        String>(
  (
    ref,
    taskId,
  ) =>
      TranslationSegmentsUndoRedoNotifier(taskId: taskId),
);
