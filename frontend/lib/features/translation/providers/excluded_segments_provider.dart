// SPDX-FileCopyrightText: 2025 QinHan
// SPDX-License-Identifier: MPL-2.0

import 'package:flutter/foundation.dart' show setEquals;
import 'package:flutter_riverpod/flutter_riverpod.dart';

/// Provider for managing excluded segment indices for a task/flow
/// Key: taskId or flowId, Value: Set of excluded segment indices
final StateNotifierProviderFamily<ExcludedSegmentsNotifier, Set<int>, String>
    excludedSegmentsProviderFamily =
    StateNotifierProvider.family<ExcludedSegmentsNotifier, Set<int>, String>(
  (
    StateNotifierProviderRef<ExcludedSegmentsNotifier, Set<int>> ref,
    String taskIdOrFlowId,
  ) =>
      ExcludedSegmentsNotifier(),
);

class ExcludedSegmentsNotifier extends StateNotifier<Set<int>> {
  ExcludedSegmentsNotifier() : super(<int>{});

  /// Add a segment index to excluded set
  void exclude(int index) {
    state = <int>{...state, index};
  }

  /// Remove a segment index from excluded set
  void unexclude(int index) {
    state = <int>{...state}..remove(index);
  }

  /// Clear all excluded segments
  void clear() {
    state = <int>{};
  }

  /// Set excluded segments from a set.
  /// Skips state assignment when the new set has identical content
  /// to prevent unnecessary widget rebuilds (e.g., backend sync after
  /// optimistic update where the content is the same).
  void setExcluded(Set<int> indices) {
    if (setEquals(state, indices)) return;
    state = indices;
  }
}
