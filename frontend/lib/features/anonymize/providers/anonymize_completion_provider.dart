// SPDX-FileCopyrightText: 2025 QinHan
// SPDX-License-Identifier: MPL-2.0

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter/foundation.dart' show kDebugMode;

/// Event indicating anonymize completion for a specific flow
class AnonymizeCompletionEvent {
  AnonymizeCompletionEvent({
    required this.flowId,
    DateTime? timestamp,
  }) : timestamp = timestamp ?? DateTime.now();
  final String flowId;
  final DateTime timestamp;

  @override
  bool operator ==(Object other) =>
      identical(this, other) ||
      other is AnonymizeCompletionEvent &&
          runtimeType == other.runtimeType &&
          flowId == other.flowId;

  @override
  int get hashCode => flowId.hashCode;
}

/// Provider to handle anonymize completion events
/// This allows ExtractPreview to notify completion without direct callback dependency
class AnonymizeCompletionNotifier
    extends StateNotifier<AnonymizeCompletionEvent?> {
  AnonymizeCompletionNotifier() : super(null);

  /// Notify that anonymize is complete for a flow
  void notifyCompletion(String flowId) {
    if (kDebugMode) {
      print('[AnonymizeCompletionProvider] notifyCompletion: flowId=$flowId');
    }
    state = AnonymizeCompletionEvent(flowId: flowId);
    // Reset state after a delay to allow all listeners to react
    // Use a longer delay to ensure all AnonymizeScreen instances have time to process
    Future.delayed(const Duration(milliseconds: 500), () {
      if (mounted && state?.flowId == flowId) {
        if (kDebugMode) {
          print(
            '[AnonymizeCompletionProvider] Clearing event for flowId=$flowId',
          );
        }
        state = null;
      }
    });
  }

  /// Clear the current event
  void clear() {
    if (kDebugMode && state != null) {
      print('[AnonymizeCompletionProvider] clear: flowId=${state!.flowId}');
    }
    state = null;
  }
}

/// Global provider for anonymize completion events
final StateNotifierProvider<AnonymizeCompletionNotifier,
        AnonymizeCompletionEvent?> anonymizeCompletionProvider =
    StateNotifierProvider<AnonymizeCompletionNotifier,
        AnonymizeCompletionEvent?>(
  (
    StateNotifierProviderRef<AnonymizeCompletionNotifier, AnonymizeCompletionEvent?> ref,
  ) =>
      AnonymizeCompletionNotifier(),
);
