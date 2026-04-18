// SPDX-FileCopyrightText: 2025 QinHan
// SPDX-License-Identifier: MPL-2.0

import 'package:flutter_riverpod/flutter_riverpod.dart';

/// Provider to trigger refresh of extract preview
/// When the value changes, the extract preview widget should reload its chunks
final StateProvider<int> extractRefreshProvider =
    StateProvider<int>((StateProviderRef<int> ref) => 0);

/// Helper function to trigger a refresh
void triggerExtractRefresh(WidgetRef ref) {
  ref.read(extractRefreshProvider.notifier).state++;
}
