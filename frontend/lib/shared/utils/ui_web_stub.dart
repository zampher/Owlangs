// SPDX-FileCopyrightText: 2025 QinHan
// SPDX-License-Identifier: MPL-2.0

/// Stub for dart:ui_web on non-web platforms (e.g. Windows desktop).
/// Used by shared/widgets/unified_preview.dart when dart.library.io is available.
library;

class PlatformViewRegistry {
  void registerViewFactory(String viewTypeId, viewFactory) {
    // No-op on non-web platforms
  }
}

final PlatformViewRegistry platformViewRegistry = PlatformViewRegistry();
