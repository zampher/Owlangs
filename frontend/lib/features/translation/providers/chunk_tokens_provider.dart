// SPDX-FileCopyrightText: 2025 QinHan
// SPDX-License-Identifier: MPL-2.0

import 'package:flutter_riverpod/flutter_riverpod.dart';

/// Provider to store total estimated input tokens for chunks
final StateProviderFamily<int?, String> chunkTokensProviderFamily =
    StateProvider.family<int?, String>(
  (StateProviderRef<int?> ref, String taskId) => null,
);
