// SPDX-FileCopyrightText: 2025 QinHan
// SPDX-License-Identifier: MPL-2.0

import 'package:flutter_riverpod/flutter_riverpod.dart';

/// Provider to trigger refresh of translation result preview
/// When the value changes, the preview widget should reload its content
final StateProvider<int> translationRefreshProvider =
    StateProvider<int>((StateProviderRef<int> ref) => 0);

/// Provider to update only specific segments without full refresh
/// When the value changes, the preview widget should update only the specified segments
final StateProvider<List<int>?> translationSegmentsUpdateProvider =
    StateProvider<List<int>?>((StateProviderRef<List<int>?> ref) => null);

/// Helper function to trigger a refresh
void triggerTranslationRefresh(WidgetRef ref) {
  ref.read(translationRefreshProvider.notifier).state++;
}

/// Helper function to update only specific segments
void triggerSegmentsUpdate(WidgetRef ref, List<int> segmentIndices) {
  ref.read(translationSegmentsUpdateProvider.notifier).state = segmentIndices;
}
