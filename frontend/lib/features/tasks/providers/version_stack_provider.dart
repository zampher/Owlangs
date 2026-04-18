// SPDX-FileCopyrightText: 2025 QinHan
// SPDX-License-Identifier: MPL-2.0

import 'package:flutter_riverpod/flutter_riverpod.dart';

class VersionSnapshot<T> {
  const VersionSnapshot(this.data);
  final T data;
}

class VersionStackState<T> {
  const VersionStackState({
    this.past = const <VersionSnapshot<Never>>[],
    this.present,
    this.future = const <VersionSnapshot<Never>>[],
  });
  final List<VersionSnapshot<T>> past;
  final VersionSnapshot<T>? present;
  final List<VersionSnapshot<T>> future;

  bool get canUndo => past.isNotEmpty;
  bool get canRedo => future.isNotEmpty;
}

class VersionStackNotifier<T> extends StateNotifier<VersionStackState<T>> {
  VersionStackNotifier({this.maxHistory = 100})
      : super(const VersionStackState());
  final int maxHistory;

  void initialize(T initial) {
    state = VersionStackState(present: VersionSnapshot(initial));
  }

  void push(T next) {
    final List<VersionSnapshot<T>> past = <VersionSnapshot<T>>[...state.past];
    if (state.present != null) past.add(state.present!);
    if (past.length > maxHistory) past.removeAt(0);
    state = VersionStackState(past: past, present: VersionSnapshot(next));
  }

  void undo() {
    if (!state.canUndo) return;
    final List<VersionSnapshot<T>> past = <VersionSnapshot<T>>[...state.past];
    final VersionSnapshot<T> last = past.removeLast();
    final List<VersionSnapshot<T>> future = <VersionSnapshot<T>>[
      if (state.present != null) state.present!,
      ...state.future,
    ];
    state = VersionStackState(past: past, present: last, future: future);
  }

  void redo() {
    if (!state.canRedo) return;
    final List<VersionSnapshot<T>> future = <VersionSnapshot<T>>[
      ...state.future,
    ];
    final VersionSnapshot<T> next = future.removeAt(0);
    final List<VersionSnapshot<T>> past = <VersionSnapshot<T>>[
      if (state.present != null) state.present!,
      ...state.past,
    ];
    state = VersionStackState(past: past, present: next, future: future);
  }
}

// Family provider for text content versioning per taskId
final StateNotifierProviderFamily<VersionStackNotifier<String>,
        VersionStackState<String>, String> textVersionStackProvider =
    StateNotifierProvider.family<VersionStackNotifier<String>,
        VersionStackState<String>, String>(
  (
    StateNotifierProviderRef<VersionStackNotifier<String>, VersionStackState<String>> ref,
    String taskId,
  ) {
    // Keep provider alive to avoid reloading when switching flows
    ref.keepAlive();
    return VersionStackNotifier<String>();
  },
);
