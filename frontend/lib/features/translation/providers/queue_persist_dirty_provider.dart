// SPDX-FileCopyrightText: 2026 Zampher
// SPDX-License-Identifier: MPL-2.0

import 'package:flutter_riverpod/flutter_riverpod.dart';

/// Scope key when [TranslationScreen] has no workspace flow id.
const String kQueuePersistStandaloneScope = '__standalone__';

class QueuePersistDirtyNotifier extends StateNotifier<bool> {
  QueuePersistDirtyNotifier() : super(false);

  void markDirty() => state = true;

  void clear() => state = false;
}

/// True when the user edited segments or ran Retry after the last successful persist-to-queue.
final StateNotifierProviderFamily<QueuePersistDirtyNotifier, bool, String>
    queuePersistDirtyProvider =
    StateNotifierProvider.family<QueuePersistDirtyNotifier, bool, String>(
  (Ref ref, String scope) => QueuePersistDirtyNotifier(),
);
