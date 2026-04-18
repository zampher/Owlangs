import 'package:flutter_riverpod/flutter_riverpod.dart';

/// Tracks in-flight exclusion updates (segment exclude/unexclude / reason edits).
///
/// Keyed by flowId when available, otherwise taskId.
final StateProviderFamily<int, String> exclusionUpdateInFlightProviderFamily =
    StateProvider.family<int, String>((StateProviderRef<int> ref, String key) => 0);

void beginExclusionUpdate(WidgetRef ref, String key) {
  ref.read(exclusionUpdateInFlightProviderFamily(key).notifier).state++;
}

void endExclusionUpdate(WidgetRef ref, String key) {
  final notifier = ref.read(exclusionUpdateInFlightProviderFamily(key).notifier);
  final v = notifier.state;
  notifier.state = v > 0 ? (v - 1) : 0;
}

