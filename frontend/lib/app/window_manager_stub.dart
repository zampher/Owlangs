// SPDX-FileCopyrightText: 2025 Owlangs
// SPDX-License-Identifier: MPL-2.0

/// Stub for window_manager on web (package does not support web). No-op implementations.
library;

class _WindowManagerStub {
  Future<void> ensureInitialized() async {}
  Future<void> setPreventClose(bool v) async {}
  Future<void> setTitle(String title) async {}
  void addListener(l) {}
  void removeListener(l) {}
  Future<void> destroy() async {}
}

final _WindowManagerStub windowManager = _WindowManagerStub();

mixin WindowListener {
  void onWindowClose() {}
}
